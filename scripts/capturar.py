"""Captura de exemplos das fontes (desenho 9.2): o único script que fala com a rede de propósito.

Uso: uv run python scripts/capturar.py <fonte> [--escopo <id>] --caso <nome>

Faz UM pedido ao vivo pelo mesmo `HttpEducado` e user agent do app (a coleta para na primeira
resposta, para não pesar na fonte), tira dado pessoal, reduz para 5 itens e 50 KB e grava
`tests/fixtures/<fonte>/<caso>.<json|html|xml>` com `<caso>.meta.json` ao lado. Nada é gravado
se sobrar dado pessoal. A redução e a limpeza são sempre feitas aqui, nunca à mão no meio do JSON.

shortcut: nomes de pessoa só saem de campos conhecidos (CAMPOS_NOME e as tags XML); nome em
texto livre ou em HTML não é achado, então a primeira captura de cada fonte é lida por gente.
shortcut: telefone só vale com `+`, parênteses ou separadores (o 9 do celular pode vir separado ou
colado ao número, "11 987654321"); número colado ("11987654321") fica, porque confunde com id,
salvo logo depois de `wa.me/`, `tel:` ou `phone=` (`sms:`, `callto:` e outros não são marcadores);
CPF sem pontos só vale com os dígitos verificadores certos. Em JSON, todo número sob um campo
pessoal (CAMPOS_NOME ou CAMPOS_SENSIVEIS, nome exato da chave) vira 0, inclusive `user.id`; em
outra chave (`phoneNumber`) o número fica, e só texto é conferido.
shortcut: no HTML só `&nbsp;` e `%40` são desfeitos antes de trocar; o detector olha também o texto
decodificado (entidade e `%xx`) e a captura é recusada se sobrar algo, em vez de limpar.
shortcut: fuso colado a ano ("+0000 2018") depois de horário não é telefone, salvo se vier outro
grupo de dígitos logo depois (aí vira telefone, falha fechado); telefone logo depois de um horário
só escapa se tiver 4 dígitos, um ano (19xx ou 20xx) e nada mais ("10:00 +5511 2034" fica).
shortcut: o limite de 5 itens vale para a maior lista (JSON) ou o elemento mais repetido (HTML,
XML); só o tamanho em bytes é conferido depois, então a primeira captura também é lida por gente.
shortcut: HTML só é reduzido por corte da lista repetida; página que ainda passa de 50 KB é
recusada (`ValueError`), e a captura dessa fonte precisa de um pedido mais estreito.
"""

import argparse
import asyncio
import hashlib
import html
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import AsyncGenerator, Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, Literal, NoReturn
from urllib.parse import unquote

import httpx
from selectolax.lexbor import LexborHTMLParser

from jobot import __version__
from jobot.nucleo.coletores.base import Coletor, ContextoColeta
from jobot.nucleo.coletores.registro import descobrir
from jobot.nucleo.http import ClienteEducado, HttpDoEscopo, Resposta, Validadores
from jobot.nucleo.relogio import Relogio, RelogioReal

Formato = Literal["json", "html", "xml"]
MAX_ITENS = 5
MAX_BYTES = 50 * 1024
RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = RAIZ / "tests" / "fixtures"
EXEMPLO = "exemplo"
EMAIL_EXEMPLO = "exemplo@exemplo.invalid"
TEL_EXEMPLO = "+55 11 90000-0000"
CPF_EXEMPLO = "000.000.000-00"
CAMPOS_NOME = frozenset(
    {
        "login",
        "by",
        "user",
        "assignee",
        "assignees",
        "closed_by",
        "recruiter",
        "recrutador",
        "autor",
        "author",
        "creator",
        "contact",
        "contato",
    }
)
CAMPOS_SENSIVEIS = frozenset({"cpf", "telefone", "phone", "celular", "whatsapp", "email", "e-mail"})
_PESSOAIS = CAMPOS_NOME | CAMPOS_SENSIVEIS
CABECALHOS_UTEIS = ("Content-Type", "ETag", "Last-Modified", "Retry-After")
CAMPOS_META = ("url", "data", "codigo", "cabecalhos", "sha256", "versao")

# a âncora evita varrer cada início de palavra até o fim (quadrático em "aaaa...")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+(?:@|%40)[\w-]+(?:\.[\w-]+)+")
_NBSP = re.compile(r"&(?:nbsp|#0*160|#x0*a0);", re.IGNORECASE)
_CPF_PONTOS = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
_CPF_SOLTO = re.compile(r"(?<![\d.])\d{11}(?!\d)")
_TEL = re.compile(
    "|".join(
        (
            # 8 dígitos no mínimo: "+0000" (fuso RFC 822) e "+15000 vagas" não são telefone;
            # "20:19:24 +0000 2018" (fuso e ano) também não: ano depois de horário é fuso, salvo
            # se vier outro grupo de dígitos ("10:00 +5511 2034-5678" é telefone)
            r"(?:(?<!:\d\d )(?<!:\d\d)\+|\+(?!\d{4}\s(?:19|20)\d\d(?![\s.-]?\d)))"
            r"(?=(?:[\s.()-]*\d){8})\d{1,3}[\s.-]?(?:\(\d{1,4}\)[\s.-]?)?\d{1,4}"
            # acaba no fim do número ("+5511987654321" inteiro, sem sobrar dígito); o grupo atômico
            # evita tentar toda divisão de uma sequência longa de dígitos depois do "+"
            r"(?:[\s.-]9)?(?>(?:[\s.-]?\d{2,5}){1,4})\d?(?!\d)",
            # o "9" do celular pode vir separado: "(11) 9 8765-4321", "11 9 8765-4321"
            r"\(\d{2,3}\)\s?(?:9[\s.-])?\d{4,5}[\s.-]?\d{4}",
            r"(?<![\d.+-])\d{2,3}[\s.-](?:9[\s.-])?\d{4,5}[\s.-]\d{4}(?!\d)",
            r"(?<![\d.+-])\d{2,3}[\s.-]9\d{8}(?!\d)",  # DDD e o celular colado: "11 987654321"
            r"(?<![\d.+-])\d{3}[\s.-]\d{3}[\s.-]\d{4}(?!\d)",
            # colado só depois de marcador de telefone: "wa.me/5511987654321", "tel:011987654321"
            r"(?i:(?:(?<=wa\.me/)|(?<=\btel:)|(?<=phone=))\+?\d{10,13}(?!\d))",
        )
    )
)
_TAG_NOME = re.compile(
    r"(<((?:[\w.-]+:)?(?:author|creator|recruiter|autor|contact|contato))\b[^>]*>)"
    r"(.*?)(</\2\s*>)",
    re.DOTALL | re.IGNORECASE,
)
_SCRIPT_JSON = re.compile(
    r"(<script\b[^>]*\btype\s*=\s*[\"']?[^\"'>]*json[^>]*>)(.*?)(</script\s*>)",
    re.DOTALL | re.IGNORECASE,
)
_CASO = re.compile(r"[a-z0-9_]+(?:-[a-z0-9_]+)*")


# ---- limpeza de dado pessoal -------------------------------------------------------------


def _cpf_valido(digitos: str) -> bool:
    if len(set(digitos)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(digitos[k]) * (n + 1 - k) for k in range(n))
        if (soma * 10 % 11) % 10 != int(digitos[n]):
            return False
    return True


def _numero(no: object) -> bool:
    return isinstance(no, int | float) and not isinstance(no, bool)


def _anonimizar(no: Any, dentro: bool = False) -> Any:
    """Troca texto por "exemplo" e número por 0 em tudo o que estiver sob um campo pessoal."""
    if isinstance(no, dict):
        return {k: _anonimizar(v, dentro or k.lower() in _PESSOAIS) for k, v in no.items()}
    if isinstance(no, list):
        return [_anonimizar(v, dentro) for v in no]
    if dentro and isinstance(no, str) and no:
        return EXEMPLO
    if dentro and _numero(no):
        return 0
    return no


def _campos_pessoais(no: Any, campo: str | None = None) -> Iterator[tuple[str, Any]]:
    if isinstance(no, dict):
        for k, v in no.items():
            yield from _campos_pessoais(v, k.lower() if k.lower() in _PESSOAIS else campo)
    elif isinstance(no, list):
        for v in no:
            yield from _campos_pessoais(v, campo)
    elif campo and ((isinstance(no, str) and no not in ("", EXEMPLO)) or (_numero(no) and no != 0)):
        yield campo, no


def _json_ou_none(texto: str) -> Any:
    try:
        dado = json.loads(texto)
    except ValueError:
        return None
    return dado if isinstance(dado, dict | list) else None


def _embutir(dado: Any) -> str:
    return json.dumps(dado, ensure_ascii=False).replace("</", "<\\/")


def _strings(no: Any) -> Iterator[str]:
    if isinstance(no, dict):
        for k, v in no.items():
            yield k
            yield from _strings(v)
    elif isinstance(no, list):
        for v in no:
            yield from _strings(v)
    elif isinstance(no, str):
        yield no


def _limpar_texto(texto: str) -> str:
    texto = _NBSP.sub(" ", texto)
    texto = _TAG_NOME.sub(lambda m: f"{m[1]}{EXEMPLO}{m[4]}", texto)
    texto = _EMAIL.sub(EMAIL_EXEMPLO, texto)
    texto = _CPF_PONTOS.sub(CPF_EXEMPLO, texto)
    texto = _CPF_SOLTO.sub(lambda m: "0" * 11 if _cpf_valido(m[0]) else m[0], texto)
    return _TEL.sub(TEL_EXEMPLO, texto)


def _limpar_json(no: Any) -> Any:
    """Troca nos textos, pela árvore: no texto serializado, um CPF em número quebraria o JSON."""
    if isinstance(no, dict):
        return {k: _limpar_json(v) for k, v in no.items()}
    if isinstance(no, list):
        return [_limpar_json(v) for v in no]
    return _limpar_texto(no) if isinstance(no, str) else no


def _limpar_script(m: re.Match[str]) -> str:
    dado = _json_ou_none(m[2])
    if dado is None:  # JSON ilegível: limpa como texto, nunca deixa passar
        return f"{m[1]}{_limpar_texto(m[2])}{m[3]}"
    return f"{m[1]}{_embutir(_limpar_json(_anonimizar(dado)))}{m[3]}"


def _limpar_html(texto: str) -> str:
    """Limpa o texto por regex fora dos scripts JSON, que são limpos pela árvore."""
    partes, fim = [], 0
    for m in _SCRIPT_JSON.finditer(texto):
        partes += [_limpar_texto(texto[fim : m.start()]), _limpar_script(m)]
        fim = m.end()
    return "".join([*partes, _limpar_texto(texto[fim:])])


def limpar_pessoais(texto: str) -> str:
    """Troca e-mail, telefone, CPF e nome (campos conhecidos) por valores de exemplo."""
    dado = _json_ou_none(texto)
    if dado is not None:
        return json.dumps(_limpar_json(_anonimizar(dado)), ensure_ascii=False, indent=2)
    return _limpar_html(texto)


def _varrivel(texto: str) -> tuple[str, list[Any]]:
    """O texto a varrer por regex (JSON embutido entra só pelas strings) e os JSON embutidos."""
    partes, embutidos, fim = [], [], 0
    for m in _SCRIPT_JSON.finditer(texto):
        partes.append(texto[fim : m.start()])
        fim = m.end()
        dado = _json_ou_none(m[2])
        if dado is None:
            partes.append(m[0])
        else:
            embutidos.append(dado)
            partes.append("\n".join(_strings(dado)))
    return "\n".join([*partes, texto[fim:]]), embutidos


def achar_pessoais(texto: str) -> list[str]:
    """O que `limpar_pessoais` tiraria (vazio = limpo). Os valores de exemplo não contam."""
    dado = _json_ou_none(texto)
    if dado is not None:  # em JSON só os textos contam: um número de 11 dígitos é id, não CPF
        varrer, embutidos = "\n".join(_strings(dado)), [dado]
    else:
        varrer, embutidos = _varrivel(texto)
    varrer = _NBSP.sub(" ", varrer)
    achados: list[str] = []
    for t in dict.fromkeys((varrer, html.unescape(varrer), unquote(varrer))):
        achados += [f"email: {m[0]}" for m in _EMAIL.finditer(t) if m[0] != EMAIL_EXEMPLO]
        achados += [f"cpf: {m[0]}" for m in _CPF_PONTOS.finditer(t) if m[0] != CPF_EXEMPLO]
        achados += [f"cpf: {m[0]}" for m in _CPF_SOLTO.finditer(t) if _cpf_valido(m[0])]
        achados += [f"telefone: {m[0]}" for m in _TEL.finditer(t) if m[0] != TEL_EXEMPLO]
        achados += [
            f"{m[2].split(':')[-1].lower()}: {m[3]}"
            for m in _TAG_NOME.finditer(t)
            if m[3].strip() not in ("", EXEMPLO)
        ]
    for d in embutidos:
        achados += [f"{campo}: {valor}" for campo, valor in _campos_pessoais(d)]
    return list(dict.fromkeys(achados))


# ---- redução -----------------------------------------------------------------------------


def _listas(no: Any) -> Iterator[list[Any]]:
    if isinstance(no, list):
        yield no
        for v in no:
            yield from _listas(v)
    elif isinstance(no, dict):
        for v in no.values():
            yield from _listas(v)


# Fonte cuja maior lista nem sempre é a das vagas (as `tags` de uma vaga podem ser mais longas
# que o feed): a chave, na raiz do JSON, da lista de vagas. Fonte fora daqui corta a maior lista.
LISTA_DE_VAGAS = {"remotive": "jobs", "himalayas": "jobs"}


def _cortar_lista(dado: Any, fonte: str | None = None) -> None:
    """Corta a lista de vagas (a indicada para a fonte, senão a maior) para MAX_ITENS."""
    indicada = dado.get(LISTA_DE_VAGAS.get(fonte or "")) if isinstance(dado, dict) else None
    principal = (
        indicada if isinstance(indicada, list) else max(_listas(dado), key=len, default=None)
    )
    if principal is not None:
        del principal[MAX_ITENS:]


def _encurtar(no: Any, limite: int | None) -> Any:
    if limite is None:
        return no
    if isinstance(no, dict):
        return {k: _encurtar(v, limite) for k, v in no.items()}
    if isinstance(no, list):
        return [_encurtar(v, limite) for v in no]
    if isinstance(no, str) and len(no) > limite:
        return no[:limite] + "…"
    return no


def _caber(montar: Callable[[int | None], bytes]) -> bytes:
    """Tenta sem encurtar e depois com texto cada vez mais curto; recusa se ainda passar."""
    for limite in (None, 4000, 1000, 300):
        saida = montar(limite)
        if len(saida) <= MAX_BYTES:
            return saida
    raise ValueError(f"não coube em {MAX_BYTES // 1024} KB; capture um pedido mais estreito")


def _json_em_bytes(dado: Any) -> bytes:
    return (json.dumps(dado, ensure_ascii=False, indent=2) + "\n").encode("utf-8", "replace")


def _mais_repetido[T](
    pais: Iterator[T], filhos: Callable[[T], list[str]]
) -> tuple[int, T, str] | None:
    melhor: tuple[int, T, str] | None = None
    for pai in pais:
        contagem = Counter(filhos(pai)).most_common(1)
        if (
            contagem
            and contagem[0][1] > MAX_ITENS
            and (melhor is None or contagem[0][1] > melhor[0])
        ):
            melhor = (contagem[0][1], pai, contagem[0][0])
    return melhor


def _reduzir_xml(bruto: bytes) -> bytes:
    padrao: str | None = None
    for _, (prefixo, uri) in ET.iterparse(io.BytesIO(bruto), events=("start-ns",)):
        if prefixo:
            ET.register_namespace(prefixo, uri)  # sem isso o ET troca o prefixo por ns0
        else:
            padrao = uri
    raiz = ET.fromstring(bruto)
    achado = _mais_repetido(raiz.iter(), lambda pai: [f.tag for f in pai])
    if achado is not None:
        _, pai, tag = achado
        for filho in [f for f in pai if f.tag == tag][MAX_ITENS:]:
            pai.remove(filho)

    def montar(limite: int | None) -> bytes:
        if limite is not None:
            for no in raiz.iter():
                for campo in ("text", "tail"):
                    valor: str | None = getattr(no, campo)
                    if valor and len(valor) > limite:
                        setattr(no, campo, valor[:limite] + "…")
        return bytes(
            ET.tostring(raiz, encoding="utf-8", xml_declaration=True, default_namespace=padrao)
        )

    return _caber(montar)


def _reduzir_html(texto: str) -> bytes:
    arvore = LexborHTMLParser(texto)
    for no in arvore.css("style, svg, noscript, iframe, template"):
        no.decompose()
    for no in arvore.css("script"):
        embutido = _json_ou_none(no.text()) if "json" in (no.attributes.get("type") or "") else None
        if embutido is None:  # script que não é dado (JSON-LD, __NEXT_DATA__) não serve de exemplo
            no.decompose()
            continue
        embutido = _anonimizar(embutido)
        _cortar_lista(embutido)
        no.inner_html = _embutir(embutido)
    achado = _mais_repetido(iter(arvore.css("*")), lambda pai: [f.tag or "" for f in pai.iter()])
    if achado is not None:
        _, pai, tag = achado
        for filho in [f for f in pai.iter() if f.tag == tag][MAX_ITENS:]:
            filho.decompose()
    saida = (arvore.html or "").encode("utf-8", "replace")
    return _caber(lambda _: saida)


def reduzir(conteudo: bytes, formato: Formato, fonte: str | None = None) -> bytes:
    """Deixa no máximo 5 itens (lista de vagas, maior lista ou elemento repetido) e 50 KB."""
    if formato == "json":
        dado = json.loads(conteudo)
        _cortar_lista(dado, fonte)
        return _caber(lambda limite: _json_em_bytes(_encurtar(dado, limite)))
    if formato == "xml":
        return _reduzir_xml(conteudo)
    return _reduzir_html(conteudo.decode("utf-8", "replace"))


# ---- conferência da pasta de um coletor --------------------------------------------------


def problemas(pasta: Path) -> list[str]:
    """Tudo o que a pasta `tests/fixtures/<fonte>` tem de errado (vazio = conforme)."""
    if not pasta.is_dir():
        return [f"{pasta.name}: pasta ausente"]
    arquivos = sorted(p for p in pasta.iterdir() if p.is_file())
    casos = [p for p in arquivos if not p.name.endswith(".meta.json") and ".editado." not in p.name]
    achados = [] if casos else [f"{pasta.name}: nenhum caso capturado"]
    for caso in casos:
        meta_arquivo = pasta / f"{caso.stem}.meta.json"
        if not meta_arquivo.is_file():
            achados.append(f"{caso.name}: falta {meta_arquivo.name} (cópia editada leva .editado.)")
            continue
        meta = _json_ou_none(meta_arquivo.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            achados.append(f"{meta_arquivo.name}: meta ilegível")
            continue
        faltam = [c for c in CAMPOS_META if c not in meta]
        if faltam:
            achados.append(f"{meta_arquivo.name}: meta sem {', '.join(faltam)}")
        elif meta["sha256"] != hashlib.sha256(caso.read_bytes()).hexdigest():
            achados.append(f"{caso.name}: sha256 diferente do meta (editado à mão? use .editado.)")
    for arquivo in arquivos:
        if (tamanho := arquivo.stat().st_size) > MAX_BYTES:
            achados.append(f"{arquivo.name}: {tamanho} bytes, acima de {MAX_BYTES // 1024} KB")
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        achados += [f"{arquivo.name}: {a}" for a in achar_pessoais(texto)]
    return achados


# ---- captura -----------------------------------------------------------------------------


class _Capturado(Exception):
    """Interrompe a coleta depois da primeira resposta."""


class _Gravador:
    """Embrulha o `HttpDoEscopo`: guarda a primeira resposta e para a coleta."""

    def __init__(self, http: HttpDoEscopo) -> None:
        self._http = http
        self.achado: dict[str, Any] | None = None

    async def pedir(
        self,
        metodo: Literal["GET", "POST"],
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        cabecalhos: Mapping[str, str] | None = None,
        corpo_json: object | None = None,
        condicional: bool = False,
        teto_bytes: int | None = None,
    ) -> NoReturn:
        resposta = await self._http.pedir(
            metodo,
            url,
            params=params,
            cabecalhos=cabecalhos,
            corpo_json=corpo_json,
            teto_bytes=teto_bytes,  # sem condicional: a captura quer o corpo, não o 304
        )
        self._guardar(metodo, url, params, corpo_json, resposta)
        raise _Capturado

    async def ler_em_fluxo(
        self, url: str, *, teto_bytes: int, cabecalhos: Mapping[str, str] | None = None
    ) -> AsyncGenerator[bytes]:
        corpo = b"".join(
            [
                p
                async for p in self._http.ler_em_fluxo(
                    url, teto_bytes=teto_bytes, cabecalhos=cabecalhos
                )
            ]
        )
        texto = corpo.decode("utf-8", "replace")
        # o fluxo não devolve cabeçalhos; ETag e Last-Modified saem dos validadores guardados
        validadores = self._http.validadores_novos.get(str(httpx.URL(url)))
        cabecalhos = {
            nome: valor
            for nome, valor in (
                ("ETag", validadores and validadores.etag),
                ("Last-Modified", validadores and validadores.last_modified),
            )
            if valor
        }
        self._guardar("GET", url, None, None, Resposta(200, texto, cabecalhos))
        raise _Capturado
        yield b""  # só para o Python tratar a função como gerador

    def _guardar(
        self,
        metodo: str,
        url: str,
        params: Mapping[str, str] | None,
        corpo_json: object | None,
        resposta: Resposta,
    ) -> None:
        minusculos = {k.lower(): v for k, v in resposta.cabecalhos.items()}
        self.achado = {
            "url": str(httpx.URL(url).copy_merge_params(params or {})),
            "metodo": metodo,
            "codigo": resposta.status,
            "cabecalhos": {
                n: minusculos[n.lower()] for n in CABECALHOS_UTEIS if n.lower() in minusculos
            },
            "texto": resposta.texto,
        }
        if corpo_json is not None:
            self.achado["corpo"] = corpo_json


def _formato(texto: str) -> Formato:
    inicio = texto.lstrip("\ufeff \t\r\n")
    if inicio[:1] in ("{", "["):
        return "json"
    if inicio.startswith("<?xml") or re.match(r"<(rss|feed|urlset|sitemapindex)\b", inicio):
        return "xml"
    return "html"


async def capturar(
    coletor: Coletor,
    escopo: str | None,
    caso: str,
    base: Path,
    cliente: ClienteEducado,
    relogio: Relogio,
    versao: str,
) -> Path:
    """Grava a primeira resposta do escopo, reduzida e limpa, em `base/<fonte>` com o meta."""
    if not _CASO.fullmatch(caso):
        raise ValueError(f"caso inválido: {caso!r} (minúsculas, dígitos, _ e -)")
    if escopo is None:
        todos = coletor.escopos(ContextoColeta((), (), ()))
        if not todos:
            raise ValueError("a fonte não tem escopo sem cadastro; passe --escopo")
        escopo = todos[0]
    limite = coletor.por_escopo.get(escopo)
    espera = limite.espera_s if limite and limite.espera_s is not None else coletor.espera_s
    gravador = _Gravador(
        cliente.escopo(
            espera_s=espera,
            condicional=False,
            max_pedidos=coletor.max_pedidos,
            para_no_429=bool(limite and limite.para_no_429),
        )
    )
    resultado = None
    try:
        resultado = await coletor.coletar(escopo, gravador)
    except _Capturado:
        pass
    achado = gravador.achado
    if achado is None:
        motivo = f"{resultado.estado}: {resultado.motivo}" if resultado else "sem pedido"
        raise RuntimeError(f"nada capturado ({motivo})")
    formato = _formato(achado["texto"])
    conteudo = reduzir(
        limpar_pessoais(achado["texto"]).encode("utf-8", "replace"), formato, coletor.chave
    )
    if formato != "json":  # o parser decodifica entidade ao serializar ("&#64;" vira "@")
        conteudo = limpar_pessoais(conteudo.decode("utf-8", "replace")).encode("utf-8", "replace")
    if sobras := achar_pessoais(conteudo.decode("utf-8", "replace")):
        raise RuntimeError(f"dado pessoal que a limpeza não pegou, nada gravado: {sobras}")
    meta = {
        "url": achado["url"],
        "data": relogio.agora().isoformat(),
        "codigo": achado["codigo"],
        "cabecalhos": achado["cabecalhos"],
        "sha256": hashlib.sha256(conteudo).hexdigest(),
        "versao": versao,
        "metodo": achado["metodo"],
    } | ({"corpo": achado["corpo"]} if "corpo" in achado else {})
    texto_meta = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    # a URL e o corpo do pedido também vão para o disco; "%40" na URL esconde o e-mail, e
    # achar_pessoais já varre o texto decodificado
    if sobras := achar_pessoais(texto_meta):
        raise RuntimeError(f"dado pessoal no meta, nada gravado: {sobras}")
    pasta = base / coletor.chave
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{caso}.{formato}"
    arquivo_meta = pasta / f"{caso}.meta.json"
    novos = [a for a in (arquivo, arquivo_meta) if not a.exists()]
    arquivo.write_bytes(conteudo)
    arquivo_meta.write_text(texto_meta, encoding="utf-8")
    if falhas := problemas(pasta):
        for a in novos:  # nada fica na pasta de fixtures, pronto para entrar num commit
            a.unlink(missing_ok=True)
        raise RuntimeError("; ".join(falhas))
    return arquivo


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _rodar(coletor: Coletor, escopo: str | None, caso: str) -> int:
    cliente = ClienteEducado(None, RelogioReal(), _SemValidadores(), __version__)
    try:
        print(await capturar(coletor, escopo, caso, FIXTURES, cliente, RelogioReal(), __version__))
    except Exception as erro:  # a captura é manual: uma linha clara basta
        print(f"erro: {type(erro).__name__}: {erro}", file=sys.stderr)
        return 1
    finally:
        await cliente.fechar()
    return 0


def main(argv: list[str]) -> int:
    analisador = argparse.ArgumentParser(prog="capturar.py", description=__doc__.split("\n")[0])
    analisador.add_argument("fonte")
    analisador.add_argument("--escopo")
    analisador.add_argument("--caso", required=True)
    args = analisador.parse_args(argv)
    coletores = descobrir()
    if args.fonte not in coletores:
        achadas = ", ".join(sorted(coletores)) or "nenhuma"
        print(f"fonte desconhecida: {args.fonte!r} (fontes: {achadas})", file=sys.stderr)
        return 1
    return asyncio.run(_rodar(coletores[args.fonte], args.escopo, args.caso))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
