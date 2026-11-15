"""Captura de exemplos de um site com login (desenho A10), pelo navegador que a própria pessoa usa.

Uso: uv run python scripts/capturar_logado.py [<leitor>] --caso <nome> [--host H]... [--campo C]...

Abre o navegador do joBot (o mesmo perfil da leitura com login) e espera: a pessoa entra no site
com a própria senha, vai até a página que quer guardar e aperta Enter no terminal. O joBot nunca
digita senha. Com leitor, guarda as respostas dos `hosts` dele que casam com `respostas`, a partir
da `url_entrada`; sem leitor, `--host` é obrigatório e entra todo JSON desses hosts e o HTML final
da página. Cada resposta é limpa pela posição (`campos_conta` do leitor e cada `--campo`: caminho
JSON `$.a.b`, nome de campo JSON ou seletor CSS) e pelos segredos de sessão (campos e parâmetros
com `csrf`, `token`, `session`, `secret`, `password`, `auth` e afins, JWT `eyJ...`), passa por
`limpar_pessoais` e `reduzir` do `capturar.py` e é conferida de novo. Grava em
`tests/fixtures/<leitor ou caso>/` só se nada sobrar.

Enquanto roda, segura a trava do joBot (`jobot.lock`) sem porta: o painel não sobe junto, e
`jobot sair`, `jobot atualizar` e `jobot` avisam que há uma captura em andamento.

shortcut: valor trocado com menos de 3 caracteres não é procurado no resto do texto (um id "7"
apareceria em qualquer número); rever se um site tiver identificador curto.
shortcut: JSON dentro do HTML (num `<script>`) não é limpo pela posição: `$.a.b` vale só em
resposta JSON, e segredo com objeto no valor (`\\"csrf\\":{...}`) não é achado; a conferência só
vê valor simples. A primeira captura de cada site é lida por gente; ler o JSON do `<script>` quando
um site trouxer a conta ali.
"""

import argparse
import asyncio
import contextlib
import hashlib
import html
import json
import os
import re
import sys
import threading
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, unquote, urldefrag, urlsplit, urlunsplit

from capturar import (
    CASO,
    FIXTURES,
    achar_pessoais,
    limpar_pessoais,
    problemas,
    reduzir,
)
from selectolax.lexbor import LexborHTMLParser

from jobot import __version__
from jobot.navegador import limites
from jobot.navegador.abrir import abrir_contexto
from jobot.navegador.execucao import Dependencias, dependencias_de_producao
from jobot.navegador.pagina import ouvir_respostas
from jobot.navegador.politica import dentro_dos_hosts
from jobot.nucleo.leitores.base import LeitorComLogin, RespostaCapturada
from jobot.nucleo.leitores.registro import leitores
from jobot.nucleo.relogio import Relogio, RelogioReal
from jobot.sistema.instancia import Trava
from jobot.sistema.pastas import pasta_de_dados, preparar_pasta

MARCADOR = "<limpo>"
_MARCADOR_HTML = html.escape(MARCADOR)
_MIN_VALOR = 3  # ver o shortcut da docstring
_SEGREDO = r"csrf|xsrf|jsessionid|token|session|secret|passw|api[_-]?key|cookie|auth"
_NOME_SEGREDO = re.compile(_SEGREDO, re.IGNORECASE)
# nome de segredo logo antes de `:` ou `=` (JSON, query, JS, JSON escapado no HTML)
_ATRIBUIDO = re.compile(
    rf"""(?i)(?:{_SEGREDO})[\w.-]*["'\\]*\s*[:=]\s*\\?["']?(?P<v>[^"'\\&\s<>,;{{}}\[\]#]+)"""
)
_JWT = re.compile(r"(?<![\w-])(?P<v>eyJ[\w-]+\.[\w-]+\.[\w-]*)")
_TAG = re.compile(r"""<(?:[^<>"']|"[^"]*"|'[^']*')*>""")
_VALOR_NA_TAG = re.compile(
    r"""(?i)(?P<nome>\b(?:content|value)\s*=\s*)(?:"(?P<v1>[^"]*)"|'(?P<v2>[^']*)'|(?P<v3>[^\s"'>]+))"""
)
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*")
_AVISO_TRAVA = (
    "O joBot está aberto (ou outra captura está rodando). Feche-o com `jobot sair` e tente de novo."
)


def _guardar(trocados: set[str], valor: str) -> None:
    if len(valor) >= _MIN_VALOR and valor != MARCADOR:
        trocados.add(valor)


# ---- limpeza pela posição ----------------------------------------------------------------


def _folhas(no: Any) -> Iterator[str]:
    if isinstance(no, dict):
        for v in no.values():
            yield from _folhas(v)
    elif isinstance(no, list):
        for v in no:
            yield from _folhas(v)
    elif isinstance(no, str | int | float) and not isinstance(no, bool):
        yield str(no)


def _limpar_no(
    no: Any,
    caminho: tuple[str, ...],
    caminhos: set[tuple[str, ...]],
    nomes: set[str],
    trocados: set[str],
) -> Any:
    if isinstance(no, list):
        return [_limpar_no(v, caminho, caminhos, nomes, trocados) for v in no]
    if not isinstance(no, dict):
        return no
    saida: dict[str, Any] = {}
    for chave, valor in no.items():
        aqui = (*caminho, chave)  # índice de lista não entra: `$.vagas.id` vale em toda vaga
        if aqui in caminhos or chave in nomes or _NOME_SEGREDO.search(chave):
            for folha in _folhas(valor):
                _guardar(trocados, folha)
            saida[chave] = MARCADOR
        else:
            saida[chave] = _limpar_no(valor, aqui, caminhos, nomes, trocados)
    return saida


def _limpar_json(texto: str, campos: Sequence[str], trocados: set[str]) -> str:
    try:
        dado = json.loads(texto)
    except ValueError:
        return texto  # JSON torto: só a limpeza por padrão; o `reduzir` recusa depois
    caminhos = {tuple(c[2:].split(".")) for c in campos if c.startswith("$.")}
    nomes = {c for c in campos if not c.startswith("$")}
    return json.dumps(_limpar_no(dado, (), caminhos, nomes, trocados), ensure_ascii=False, indent=2)


def _limpar_html(texto: str, campos: Sequence[str], trocados: set[str]) -> str:
    seletores = [c for c in campos if not c.startswith("$")]
    if not seletores:
        return texto
    arvore = LexborHTMLParser(texto)
    mexeu = False
    for seletor in seletores:
        for no in arvore.css(seletor):
            _guardar(trocados, no.text(deep=True).strip())
            for filho in list(no.iter(include_text=True)):
                filho.decompose()
            no.insert_child(MARCADOR)
            for atributo in ("value", "content"):
                if (valor := no.attributes.get(atributo)) is not None:
                    _guardar(trocados, valor)
                    no.attrs[atributo] = MARCADOR
            mexeu = True
    return (arvore.html or texto) if mexeu else texto


def _trocar_na_tag(m: re.Match[str], trocados: set[str]) -> str:
    tag = m[0]
    if not re.search(r"(?i)csrf|xsrf", tag):
        return tag

    def trocar(v: re.Match[str]) -> str:
        valor = v["v1"] if v["v1"] is not None else v["v2"] if v["v2"] is not None else v["v3"]
        if html.unescape(valor) in ("", MARCADOR):
            return v[0]
        _guardar(trocados, html.unescape(valor))
        return f'{v["nome"]}"{_MARCADOR_HTML}"'

    return _VALOR_NA_TAG.sub(trocar, tag)


def _trocar_grupo(m: re.Match[str], trocados: set[str]) -> str:
    _guardar(trocados, unquote(html.unescape(m["v"])))
    inicio, fim = m.start("v") - m.start(), m.end("v") - m.start()
    return m[0][:inicio] + MARCADOR + m[0][fim:]


def limpar_logado(texto: str, tipo: str, campos: Sequence[str]) -> tuple[str, frozenset[str]]:
    """Troca por `MARCADOR` cada posição de `campos` e os segredos de sessão.

    Devolve o texto e os valores trocados (só em memória, para a conferência)."""
    trocados: set[str] = set()
    if "json" in tipo:
        texto = _limpar_json(texto, campos, trocados)
    else:
        texto = _limpar_html(texto, campos, trocados)
    texto = _TAG.sub(lambda m: _trocar_na_tag(m, trocados), texto)
    texto = _ATRIBUIDO.sub(lambda m: _trocar_grupo(m, trocados), texto)
    texto = _JWT.sub(lambda m: _trocar_grupo(m, trocados), texto)
    return texto, frozenset(trocados)


# ---- conferência -------------------------------------------------------------------------


def _desfeito(valor: str) -> str:
    return unquote(html.unescape(valor))


def conferir_logado(texto: str, trocados: frozenset[str]) -> list[str]:
    """O que sobrou no texto, por tipo e posição; nunca traz o valor achado."""
    achados = [f"jwt na posição {m.start()}" for m in _JWT.finditer(texto)]
    achados += [
        f"segredo de sessão fora do marcador na posição {m.start('v')}"
        for m in _ATRIBUIDO.finditer(texto)
        if _desfeito(m["v"]) != MARCADOR
    ]
    for tag in _TAG.finditer(texto):
        if re.search(r"(?i)csrf|xsrf", tag[0]):
            for v in _VALOR_NA_TAG.finditer(tag[0]):
                valor = (
                    v["v1"] if v["v1"] is not None else v["v2"] if v["v2"] is not None else v["v3"]
                )
                if _desfeito(valor) not in ("", MARCADOR):
                    achados.append(f"csrf/xsrf em tag fora do marcador na posição {tag.start()}")
    versoes = {texto, html.unescape(texto), unquote(texto)}
    for valor in sorted(trocados):
        padrao = re.compile(rf"(?<!\w){re.escape(valor)}(?!\w)")
        for versao in versoes:
            if m := padrao.search(versao):
                achados.append(f"valor trocado reaparece na posição {m.start()}")
                break
    # `achar_pessoais` traz "tipo: valor"; aqui só o tipo
    achados += [a.split(":")[0] for a in achar_pessoais(texto)]
    return achados


def meta_logado(url: str, status: int, tipo: str) -> dict[str, object]:
    """O meta sem cabeçalho nenhum (logo sem `Set-Cookie`) e sem valor de query nem fragmento."""
    partes = urlsplit(urldefrag(url).url)
    host = partes.hostname or ""
    host = f"[{host}]" if ":" in host else host  # IPv6
    onde = f"{host}:{partes.port}" if partes.port else host  # sem usuário e senha da URL
    nomes = "&".join(nome for nome, _ in parse_qsl(partes.query, keep_blank_values=True))
    return {
        "url": urlunsplit((partes.scheme, onde, partes.path, nomes, "")),
        "codigo": status,
        "cabecalhos": {},
        "tipo": tipo,
    }


def preparar(
    texto: str, tipo: str, campos: Sequence[str], fonte: str | None
) -> tuple[bytes, frozenset[str]]:
    """Limpa pela posição, tira dado pessoal e reduz, na ordem do `capturar.py`."""
    limpo, trocados = limpar_logado(texto, tipo, campos)
    formato: Literal["json", "html"] = "json" if "json" in tipo else "html"
    conteudo = reduzir(limpar_pessoais(limpo).encode("utf-8", "replace"), formato, fonte)
    if formato != "json":  # o parser decodifica entidade ao serializar ("&#64;" vira "@")
        conteudo = limpar_pessoais(conteudo.decode("utf-8", "replace")).encode("utf-8", "replace")
    return conteudo, trocados


# ---- navegador ---------------------------------------------------------------------------


async def _enter() -> None:
    """Espera o Enter no terminal sem parar o laço (o Playwright segue ouvindo as respostas)."""
    laco = asyncio.get_running_loop()
    pronto: asyncio.Future[None] = laco.create_future()

    def soltar() -> None:
        if not pronto.done():  # Ctrl+C já cancelou a espera
            pronto.set_result(None)

    def ler() -> None:
        sys.stdin.readline()
        laco.call_soon_threadsafe(soltar)

    threading.Thread(target=ler, daemon=True).start()
    await pronto


async def _navegar(
    deps: Dependencias,
    hosts: Sequence[str],
    padroes: Sequence[str] | None,
    entrada: str,
    enter: Callable[[], Awaitable[None]],
) -> list[RespostaCapturada]:
    contexto = await abrir_contexto(deps.dados, deps.ambiente(), deps.lancar)
    try:
        page = await contexto.new_page()
        ouvidas = ouvir_respostas(page, hosts, padroes)
        await page.goto(entrada)
        print(
            "Entre no site com a sua senha na janela do navegador, abra a página que quer "
            "guardar e aperte Enter aqui."
        )
        await enter()
        with contextlib.suppress(Exception):  # estouro do `networkidle` não impede a captura
            await page.wait_for_load_state("networkidle", timeout=limites.ESPERA_ASSENTAR_MS)
        await ouvidas.prontas()
        ouvidas.ativa = False
        capturadas = list({r.url: r for r in ouvidas}.values())  # a última de cada URL
        if padroes is None:  # sem leitor: todo JSON e o HTML final da página
            capturadas = [r for r in capturadas if "json" in r.tipo]
            final = urldefrag(page.url).url
            if dentro_dos_hosts(final, hosts):
                resposta = ouvidas.ultimas.get(final)
                status = resposta.status if resposta is not None else 200
                capturadas.append(
                    RespostaCapturada(final, status, "text/html", await page.content())
                )
        return capturadas
    finally:
        await contexto.close()


# ---- linha de comando --------------------------------------------------------------------


def _analisador() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(
        prog="capturar_logado.py", description=(__doc__ or "").split("\n")[0]
    )
    analisador.add_argument("leitor", nargs="?")
    analisador.add_argument("--caso", required=True)
    analisador.add_argument("--host", action="append", default=[])
    analisador.add_argument("--campo", action="append", default=[])
    return analisador


def _gravar(
    capturadas: Sequence[RespostaCapturada],
    caso: str,
    pasta: Path,
    campos: Sequence[str],
    fonte: str | None,
    relogio: Relogio,
) -> list[Path]:
    preparados: list[tuple[str, bytes, str]] = []
    todos: set[str] = set()
    for n, resposta in enumerate(capturadas, start=1):
        conteudo, trocados = preparar(resposta.texto, resposta.tipo, campos, fonte)
        todos |= trocados
        meta = meta_logado(resposta.url, resposta.status, resposta.tipo) | {
            "data": relogio.agora().isoformat(),
            "sha256": hashlib.sha256(conteudo).hexdigest(),
            "versao": __version__,
        }
        texto_meta, trocados_meta = limpar_logado(
            json.dumps(meta, ensure_ascii=False, indent=2), "application/json", campos
        )
        todos |= trocados_meta
        nome = caso if len(capturadas) == 1 else f"{caso}_{n}"
        ext = "json" if "json" in resposta.tipo else "html"
        preparados += [(f"{nome}.{ext}", conteudo, ""), (f"{nome}.meta.json", b"", texto_meta)]
    # todo arquivo é conferido contra todos os valores trocados (o id pode vazar em outra resposta)
    achados: list[str] = []
    for arquivo, conteudo, texto_meta in preparados:
        texto = texto_meta or conteudo.decode("utf-8", "replace")
        achados += [f"{arquivo}: {a}" for a in conferir_logado(texto, frozenset(todos))]
    if achados:
        raise RuntimeError(f"sobrou dado da conta ou da sessão, nada gravado: {achados}")
    pasta.mkdir(parents=True, exist_ok=True)
    gravados = [pasta / arquivo for arquivo, _, _ in preparados]
    novos = [a for a in gravados if not a.exists()]
    for (_, conteudo, texto_meta), destino in zip(preparados, gravados, strict=True):
        if texto_meta:
            destino.write_text(texto_meta + "\n", encoding="utf-8")
        else:
            destino.write_bytes(conteudo)
    if falhas := problemas(pasta):
        for a in novos:  # nada fica na pasta de fixtures, pronto para entrar num commit
            a.unlink(missing_ok=True)
        raise RuntimeError("; ".join(falhas))
    return [a for a in gravados if not a.name.endswith(".meta.json")]


def main(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    dependencias: Callable[
        [Path, Mapping[str, str]], contextlib.AbstractAsyncContextManager[Dependencias]
    ] = dependencias_de_producao,
    enter: Callable[[], Awaitable[None]] = _enter,
    base: Path = FIXTURES,
    leitores_registrados: Callable[[], Sequence[LeitorComLogin]] = leitores,
    relogio: Relogio | None = None,
) -> int:
    args = _analisador().parse_args(list(argv))
    env = os.environ if env is None else env
    if not CASO.fullmatch(args.caso):
        print(f"caso inválido: {args.caso!r} (minúsculas, dígitos, _ e -)", file=sys.stderr)
        return 2
    if ruins := [h for h in args.host if not _HOST.fullmatch(h)]:
        print(f"host inválido: {ruins[0]!r} (só o nome, como site.com.br)", file=sys.stderr)
        return 2
    leitor: LeitorComLogin | None = None
    if args.leitor is not None:
        registrados = {lt.chave: lt for lt in leitores_registrados()}
        if args.leitor not in registrados:
            achados = ", ".join(sorted(registrados)) or "nenhum"
            print(f"leitor desconhecido: {args.leitor!r} (leitores: {achados})", file=sys.stderr)
            return 2
        leitor = registrados[args.leitor]
    elif not args.host:
        print("sem leitor, diga os sites com --host (um ou mais)", file=sys.stderr)
        return 2
    hosts = tuple(leitor.hosts) + tuple(args.host) if leitor else tuple(args.host)
    campos = [*(leitor.campos_conta if leitor else ()), *args.campo]
    entrada = leitor.url_entrada if leitor else f"https://{args.host[0]}/"
    padroes = tuple(leitor.respostas) if leitor else None
    pasta = base / (leitor.chave if leitor else args.caso)

    dados = pasta_de_dados(env)
    preparar_pasta(dados)
    trava = Trava(dados, 0)  # porta 0: o script não serve nada (`captura_em_andamento`)
    if not trava.pegar():
        print(_AVISO_TRAVA, file=sys.stderr)
        return 1

    async def rodar() -> list[Path]:
        async with dependencias(dados, env) as deps:
            capturadas = await _navegar(deps, hosts, padroes, entrada, enter)
        if not capturadas:
            raise RuntimeError("nenhuma resposta dos sites capturada")
        fonte = leitor.chave if leitor else None
        return _gravar(capturadas, args.caso, pasta, campos, fonte, relogio or RelogioReal())

    try:
        for arquivo in asyncio.run(rodar()):
            print(arquivo)
    except Exception as erro:  # a captura é manual: uma linha clara basta
        print(f"erro: {type(erro).__name__}: {erro}", file=sys.stderr)
        return 1
    finally:
        trava.soltar()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
