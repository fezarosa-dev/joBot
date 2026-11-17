"""Captura de exemplos de um site com login (desenho A10), pelo navegador que a própria pessoa usa.

Uso: uv run python scripts/capturar_logado.py [<leitor>] --caso <nome> [--host H]... [--campo C]...
[--login URL] [--recorte SELETOR]... [--tirar REGEX]...

Abre o navegador do joBot (o mesmo perfil da leitura com login) e espera: a pessoa entra no site
com a própria senha, vai até a página que quer guardar e aperta Enter no terminal. O joBot nunca
digita senha. Com `--login URL`, a pessoa entra antes, numa janela comum do navegador (a mesma do
login pelo painel, sem automação): fecha a janela e a captura segue na janela da captura, já
logada. Sem `--login`, entra na janela da captura, como antes.

Com `--recorte SELETOR` (repetível), cada página HTML guarda só o título e os nós que casam com
algum seletor (um seletor sem nó não recusa; todos sem nó, sim, com o código 2), os links do site
(subdomínios e `srcset` incluídos) perdem o valor da query (menos `url=`) e nenhuma resposta JSON é
guardada. Com `--tirar REGEX` (repetível), o texto e os atributos que casam viram `<limpo>` só no
HTML gravado (as respostas JSON não passam por ele); o que ainda casar no HTML pronto (num
comentário, por exemplo) recusa a gravação. Em todo HTML gravado, o endereço de toda imagem
(`src`, `srcset`, `poster`, `href` de imagem SVG e `url(...)` de `style`) vira `<limpo>`.
As duas listas entram na `.meta.json` quando há recorte.
Com leitor, guarda as respostas dos `hosts` dele que casam com `respostas`, a partir da
`url_entrada`; sem leitor, `--host` é obrigatório e entra todo JSON desses hosts e o HTML final da
página. Cada resposta é limpa pela posição (`campos_conta` do leitor e cada `--campo`: caminho JSON
`$.a.b`, nome de campo JSON ou seletor CSS) e pelos segredos de sessão (campos e parâmetros com
`csrf`, `token`, `session`, `secret`, `password`, `auth` e afins, JWT `eyJ...`), passa por
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
from urllib.parse import parse_qsl, unquote, unquote_plus, urldefrag, urlsplit, urlunsplit

from capturar import (
    CASO,
    FIXTURES,
    achar_pessoais,
    limpar_pessoais,
    problemas,
    reduzir,
)
from selectolax.lexbor import LexborHTMLParser, SelectolaxError

from jobot import __version__
from jobot.navegador import limites
from jobot.navegador.abrir import abrir_contexto
from jobot.navegador.execucao import Dependencias, dependencias_de_producao
from jobot.navegador.janela_comum import JanelaComum, janela_de_producao
from jobot.navegador.login_manual import abrir_e_esperar
from jobot.navegador.pagina import ouvir_respostas
from jobot.navegador.politica import dentro_dos_hosts
from jobot.nucleo.leitores.base import LeitorComLogin, RespostaCapturada
from jobot.nucleo.leitores.registro import leitores
from jobot.nucleo.modelo import confere_http
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
_SEM_JANELA = {
    "em_uso": "O navegador do joBot já está aberto. Feche-o e tente de novo.",
    "sem_tela": "Não há tela para abrir a janela do navegador.",
    "sem_navegador": "Não achei um navegador para abrir a janela (instale o Chrome ou o Chromium).",
}
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


def meta_logado(
    url: str,
    status: int,
    tipo: str,
    *,
    recorte: Sequence[str] = (),
    tirar: Sequence[str] = (),
) -> dict[str, object]:
    """O meta sem cabeçalho nenhum (logo sem `Set-Cookie`) e sem valor de query nem fragmento."""
    partes = urlsplit(urldefrag(url).url)
    host = partes.hostname or ""
    host = f"[{host}]" if ":" in host else host  # IPv6
    onde = f"{host}:{partes.port}" if partes.port else host  # sem usuário e senha da URL
    nomes = "&".join(nome for nome, _ in parse_qsl(partes.query, keep_blank_values=True))
    meta: dict[str, object] = {
        "url": urlunsplit((partes.scheme, onde, partes.path, nomes, "")),
        "codigo": status,
        "cabecalhos": {},
        "tipo": tipo,
    }
    if recorte:  # as expressões do `--tirar` são genéricas: a `.meta.json` pode levá-las
        meta |= {"recorte": list(recorte), "tirar": list(tirar)}
    return meta


class RecorteSemNo(ValueError):
    """Nenhum seletor de `--recorte` casou nada na página."""


class _SemJanela(Exception):
    """A janela comum do `--login` não abriu (o texto vai para a pessoa)."""


def _sem_valores(link: str, host: str) -> str:
    """Troca o valor de cada parâmetro da query por `MARCADOR`, menos o `url`, nos links do site."""
    try:
        partes = urlsplit(link)
        base = host.removeprefix("www.")
        de_fora = partes.hostname is not None and not (
            partes.hostname == host
            or partes.hostname == base
            or partes.hostname.endswith("." + base)
        )
    except ValueError:
        return MARCADOR  # não se lê: não dá para dizer que a query não tem segredo
    if de_fora:
        return link
    pares = []
    for par in partes.query.split("&"):
        nome, igual, _ = par.partition("=")
        pares.append(par if not igual or unquote_plus(nome) == "url" else f"{nome}={MARCADOR}")
    return urlunsplit(partes._replace(query="&".join(pares)))


def _srcset_sem_valores(valor: str, host: str) -> str:
    """Cada URL do `srcset` passa por `_sem_valores`; descritores e separadores ficam como estão.

    Lê como o padrão HTML: pula espaços e vírgulas; a URL é a sequência sem espaço (pode ter vírgula
    dentro); se termina em vírgula, tira-as e não há descritor; senão o descritor vai até a vírgula.
    """
    saida: list[str] = []
    i = 0
    while i < len(valor):
        i = _casar(r"[\s,]*", valor, i, saida)
        if i >= len(valor):
            break
        fim = re.compile(r"\S+").match(valor, i)
        assert fim is not None  # sobrou algo que não é espaço
        url, i = fim.group(), fim.end()
        limpa = url.rstrip(",")
        saida.append(_sem_valores(limpa, host) + url[len(limpa) :])
        if limpa == url:
            i = _casar(r"[^,]*", valor, i, saida)
    return "".join(saida)


def _casar(padrao: str, texto: str, i: int, saida: list[str]) -> int:
    achado = re.compile(padrao).match(texto, i)
    assert achado is not None  # os padrões casam o vazio
    saida.append(achado.group())
    return achado.end()


def recortar(html: str, seletores: Sequence[str], host: str) -> str:
    """O título e o HTML dos nós que casam (sem repetir o que está dentro de outro que casou)."""
    arvore = LexborHTMLParser(html)
    achados = arvore.css(", ".join(seletores))  # a ordem do documento, sem repetir nó
    if not achados:
        raise RecorteSemNo(f"recorte sem nó: {', '.join(seletores)}")
    ids = {no.mem_id for no in achados}
    pedacos: list[str] = []
    for no in achados:
        pai = no.parent
        while pai is not None and pai.mem_id not in ids:
            pai = pai.parent
        if pai is not None:
            continue
        for alvo in (no, *no.css("[href], [src], [srcset]")):
            for atributo in ("href", "src"):
                if (valor := alvo.attributes.get(atributo)) is not None:
                    alvo.attrs[atributo] = _sem_valores(valor, host)
            if (valor := alvo.attributes.get("srcset")) is not None:
                alvo.attrs["srcset"] = _srcset_sem_valores(valor, host)
        pedacos.append(no.html or "")
    titulo = arvore.css_first("title")
    return (
        f"<html><head>{titulo.html if titulo else ''}</head><body>{''.join(pedacos)}</body></html>"
    )


def tirar(html: str, padroes: Sequence[str]) -> str:
    """Troca por `MARCADOR` o texto e o valor de atributo que casam com algum padrão."""
    regexes = [re.compile(p, re.IGNORECASE) for p in padroes]

    def casa(texto: str) -> bool:
        return any(r.search(texto) for r in regexes)

    arvore = LexborHTMLParser(html)
    if arvore.root is None:
        return html
    for no in list(arvore.root.traverse(include_text=True)):
        if no.tag == "-text":
            if casa(no.text(deep=False)):
                no.replace_with(MARCADOR)
            continue
        for nome, valor in no.attributes.items():
            if valor is not None and casa(valor):
                no.attrs[nome] = MARCADOR
    return arvore.html or html


_IMAGEM_ATRIBUTOS = {
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "video": ("poster",),
    "image": ("href", "xlink:href"),  # SVG
}
# shortcut: aspas com escape (url("a\")b")), `url(` sem `)` e image-set() com string sem url() não
# são cobertos; rever se aparecer numa captura.
_URL_CSS = re.compile(r"""url\(\s*(?:'[^']*'|"[^"]*"|[^)]*?)\s*\)""", re.IGNORECASE)


def sem_imagens(html: str) -> str:
    """Troca por `MARCADOR` o endereço de toda imagem: nenhum leitor lê imagem, e o logo de uma
    escola ou empresa vizinho do texto limpo diria o que a pessoa não quer mostrar."""
    arvore = LexborHTMLParser(html)
    if arvore.root is None:
        return html
    for no in arvore.root.traverse():
        nomes = _IMAGEM_ATRIBUTOS.get(no.tag or "", ())
        for nome in nomes:
            if nome in no.attributes:
                no.attrs[nome] = MARCADOR
        if nomes:  # carregamento preguiçoso: data-src, data-delayed-url etc. levam o mesmo endereço
            for nome, valor in list(no.attributes.items()):
                if (
                    nome.startswith("data-")
                    and valor
                    and ("://" in valor or valor.startswith("//"))
                ):
                    no.attrs[nome] = MARCADOR
        if (estilo := no.attributes.get("style")) is not None:
            no.attrs["style"] = _URL_CSS.sub(f"url({MARCADOR})", estilo)
    return arvore.html or html


def conferir_tirar(html: str, padroes: Sequence[str]) -> list[str]:
    """O que ainda casa no HTML inteiro (comentário, nome de atributo); nunca traz o trecho."""
    return [
        f"padrão {n} do --tirar reaparece na posição {m.start()}"
        for n, padrao in enumerate(padroes, start=1)
        for m in re.finditer(padrao, html, re.IGNORECASE)
    ]


def preparar(
    texto: str,
    tipo: str,
    campos: Sequence[str],
    fonte: str | None,
    *,
    host: str | None = None,
    recorte: Sequence[str] = (),
    padroes_tirar: Sequence[str] = (),
) -> tuple[bytes, frozenset[str]]:
    """Recorta, troca endereços de imagem, tira, limpa pela posição, tira dado pessoal, reduz."""
    formato: Literal["json", "html"] = "json" if "json" in tipo else "html"
    if formato == "html":
        if recorte:
            texto = recortar(texto, recorte, host or "")
        texto = sem_imagens(texto)
        if padroes_tirar:
            texto = tirar(texto, padroes_tirar)
    limpo, trocados = limpar_logado(texto, tipo, campos)
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
    recorte: bool = False,
    com_login: bool = False,
) -> list[RespostaCapturada]:
    contexto = await abrir_contexto(deps.dados, deps.ambiente(), deps.lancar)
    try:
        page = await contexto.new_page()
        ouvidas = ouvir_respostas(page, hosts, padroes)
        await page.goto(entrada)
        if com_login:  # a pessoa já entrou na janela comum
            print("Abra a página que quer guardar e aperte Enter aqui.")
        else:
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
        if recorte or padroes is None:  # o HTML final da página; sem leitor, também todo JSON
            capturadas = [] if recorte else [r for r in capturadas if "json" in r.tipo]
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
    analisador.add_argument("--recorte", action="append", default=[])
    analisador.add_argument(
        "--tirar",
        action="append",
        default=[],
        help="regex; vale só para o HTML gravado (as respostas JSON não passam por ela)",
    )
    analisador.add_argument("--login")
    return analisador


def _gravar(
    capturadas: Sequence[RespostaCapturada],
    caso: str,
    pasta: Path,
    campos: Sequence[str],
    fonte: str | None,
    relogio: Relogio,
    recorte: Sequence[str] = (),
    padroes_tirar: Sequence[str] = (),
) -> list[Path]:
    preparados: list[tuple[str, bytes, str]] = []
    todos: set[str] = set()
    for n, resposta in enumerate(capturadas, start=1):
        conteudo, trocados = preparar(
            resposta.texto,
            resposta.tipo,
            campos,
            fonte,
            host=urlsplit(resposta.url).hostname,
            recorte=recorte,
            padroes_tirar=padroes_tirar,
        )
        todos |= trocados
        meta = meta_logado(
            resposta.url, resposta.status, resposta.tipo, recorte=recorte, tirar=padroes_tirar
        ) | {
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
        if padroes_tirar and arquivo.endswith(".html"):  # nunca a `.meta.json`, que os guarda
            achados += [f"{arquivo}: {a}" for a in conferir_tirar(texto, padroes_tirar)]
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
    janela: JanelaComum | None = None,
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
    if args.login is not None:
        try:
            confere_http(args.login, "--login")
        except ValueError as erro:
            print(erro, file=sys.stderr)
            return 2
    try:
        for padrao in args.tirar:
            re.compile(padrao)
    except re.error as erro:
        print(f"--tirar inválido: {erro}", file=sys.stderr)
        return 2
    for seletor in args.recorte:
        try:
            LexborHTMLParser("<a></a>").css(seletor)
        except SelectolaxError:
            print(f"seletor do --recorte inválido: {seletor!r}", file=sys.stderr)
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
            if args.login is not None:
                print("Entre no site e feche a janela quando terminar.")
                fim = await abrir_e_esperar(
                    janela if janela is not None else janela_de_producao(),
                    dados,
                    deps.ambiente(),
                    args.login,
                )
                if fim in _SEM_JANELA:
                    raise _SemJanela(_SEM_JANELA[fim])
            capturadas = await _navegar(
                deps, hosts, padroes, entrada, enter, bool(args.recorte), args.login is not None
            )
        if not capturadas:
            raise RuntimeError("nenhuma resposta dos sites capturada")
        fonte = leitor.chave if leitor else None
        return _gravar(
            capturadas,
            args.caso,
            pasta,
            campos,
            fonte,
            relogio or RelogioReal(),
            args.recorte,
            args.tirar,
        )

    try:
        for arquivo in asyncio.run(rodar()):
            print(arquivo)
    except _SemJanela as erro:
        print(erro, file=sys.stderr)
        return 1
    except RecorteSemNo as erro:
        print(erro, file=sys.stderr)
        return 2
    except Exception as erro:  # a captura é manual: uma linha clara basta
        print(f"erro: {type(erro).__name__}: {erro}", file=sys.stderr)
        return 1
    finally:
        trava.soltar()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
