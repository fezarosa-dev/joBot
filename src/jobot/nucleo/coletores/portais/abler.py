"""Coletor Abler (apêndice 3.1): o sitemap lista as vagas, a página de cada uma dá o detalhe.

`GET /sitemap.xml` traz todas as vagas abertas da plataforma (~14 mil `<url>`, ~3,6 MB, dentro
do teto de 5 MB), sem ETag nem Last-Modified. O `coletar` devolve uma `UrlListada` por vaga,
sem filtrar data (o filtro de 30 dias é do executor). O `detalhar` lê a página da vaga e tira o
estado de `window.__NUXT__` como texto: é uma expressão JS (função com variáveis), lida por um
leitor de literais que nunca executa nada. Campo que só sairia executando fica de fora. A API
`hulk-smash.abler.com.br` recusa pedidos de outra origem e não é usada.
"""

import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Literal
from urllib.parse import urlsplit

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import ErroDeRede, HttpEducado
from jobot.nucleo.modelo import SalarioBruto, VagaColetada

_LIMITES = limites("abler")
_HOST = "candidatos.abler.com.br"
_SITEMAP = f"https://{_HOST}/sitemap.xml"
_CAMINHO_VAGA = re.compile(r"/vagas/[^/]+")
_MARCA = "window.__NUXT__="
_PROFUNDIDADE = 100  # bem abaixo do limite de recursão do Python
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_NUMERO = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
_CONSTANTES: dict[str, object] = {"true": True, "false": False, "null": None, "undefined": None}


class _FormatoMudou(Exception):
    """O corpo não é XML, traz DTD ou não é um `<urlset>` de sitemap; ou alguma `<url>` foi
    descartada (sem `<loc>` ou fora do endereço de vaga) e nenhuma deu vaga."""


class _NaoLido(Exception):
    """O texto não é um literal que o leitor entende."""


class _Ilegivel:
    """Valor que só sairia executando o JS (chamada, conta, `new`...)."""


_ILEGIVEL = _Ilegivel()


class _Ref:
    """Variável da função do empacotador; o valor vem nos argumentos, depois do corpo."""

    def __init__(self, nome: str) -> None:
        self.nome = nome


# ---- sitemap ------------------------------------------------------------------------------


def _url_de_vaga(url: str) -> str | None:
    """`https://candidatos.abler.com.br/vagas/<slug>` refeito com host e esquema fixos."""
    partes = urlsplit(url)
    if (
        partes.scheme != "https"
        or partes.netloc != _HOST
        or partes.query
        or partes.fragment
        or not _CAMINHO_VAGA.fullmatch(partes.path)
    ):
        return None
    return f"https://{_HOST}{partes.path}"


def _local(tag: str) -> str:
    return tag.rpartition("}")[2]


def _data(texto: str | None) -> datetime | None:
    try:
        quando = datetime.fromisoformat(texto or "")
    except ValueError:
        return None
    return quando if quando.tzinfo else quando.replace(tzinfo=UTC)


def _ler_sitemap(texto: str) -> tuple[list[UrlListada], int, bool]:
    """As vagas do sitemap, quantas `<url>` foram puladas e se alguma veio sem `<loc>`."""
    if "<!DOCTYPE" in texto or "<!ENTITY" in texto:
        raise _FormatoMudou  # sitemap não tem DTD; fecha a porta a entidades
    try:
        raiz = ET.fromstring(texto)  # o ElementTree não busca entidade externa
    except ET.ParseError as erro:
        raise _FormatoMudou from erro
    if _local(raiz.tag) != "urlset":
        raise _FormatoMudou
    urls: list[UrlListada] = []
    pulados = 0
    sem_loc = False
    for no in raiz:
        if _local(no.tag) != "url":
            continue
        campos = {_local(f.tag): (f.text or "").strip() for f in no}
        loc = campos.get("loc")
        if not loc:
            sem_loc = True
            continue
        if loc.rstrip("/") == f"https://{_HOST}/vagas":
            continue  # a página da lista, não uma vaga
        url = _url_de_vaga(loc)
        try:
            if url is None:
                raise ValueError(loc)
            urls.append(UrlListada(url, _data(campos.get("lastmod"))))
        except ValueError:  # outro host, host local (decisão 19), outro caminho
            pulados += 1
    if (pulados or sem_loc) and not urls:
        raise _FormatoMudou  # nenhuma <url> deu vaga: "ok" vazio fecharia todas as vagas
    return urls, pulados, sem_loc


# ---- window.__NUXT__ lido como texto ------------------------------------------------------


class _Leitor:
    """Literais JS (objeto, lista, texto, número, constante, variável); o resto vira `_ILEGIVEL`."""

    def __init__(self, texto: str, params: Sequence[str] = ()) -> None:
        self.s = texto
        self.i = 0
        self.params = set(params)

    def espaco(self) -> str:
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1
        return self.s[self.i] if self.i < len(self.s) else ""

    def espera(self, c: str) -> None:
        if self.espaco() != c:
            raise _NaoLido(f"esperava {c!r} em {self.i}")
        self.i += 1

    def valor(self, fundo: int = 0) -> object:
        if fundo > _PROFUNDIDADE:
            raise _NaoLido("fundo demais")
        inicio = self.i
        lido = self.primario(fundo)
        if self.espaco() not in (",", "}", "]", ")", ";", ""):
            # o literal continua numa expressão (`Math.max(...)`, `a+"x"`): não executa
            self.i = inicio
            self.pular()
            return _ILEGIVEL
        return lido

    def primario(self, fundo: int) -> object:
        if fundo > _PROFUNDIDADE:  # '!' e 'void' recursam sem passar por valor()
            raise _NaoLido("fundo demais")
        c = self.espaco()
        if c == "{":
            return self.objeto(fundo)
        if c == "[":
            return self.lista(fundo)
        if c in ("'", '"'):
            return self.texto()
        if c == "!":
            self.i += 1
            n = self.primario(fundo + 1)
            return n == 0 if isinstance(n, int | float) and not isinstance(n, bool) else _ILEGIVEL
        if numero := _NUMERO.match(self.s, self.i):
            self.i = numero.end()
            bruto = numero.group()
            if bruto.lstrip("-")[:2] in ("0x", "0X"):
                return int(bruto, 16)
            return float(bruto) if any(x in bruto for x in ".eE") else int(bruto)
        if ident := _IDENT.match(self.s, self.i):
            self.i = ident.end()
            nome = ident.group()
            if nome == "void":
                self.primario(fundo + 1)
                return None
            if nome in _CONSTANTES:
                return _CONSTANTES[nome]
            return _Ref(nome) if nome in self.params else _ILEGIVEL
        self.pular()
        return _ILEGIVEL

    def objeto(self, fundo: int) -> dict[str, object]:
        self.i += 1
        saida: dict[str, object] = {}
        while self.espaco() != "}":
            c = self.espaco()
            if c in ("'", '"'):
                chave = self.texto()
            elif m := (_IDENT.match(self.s, self.i) or _NUMERO.match(self.s, self.i)):
                self.i = m.end()
                chave = m.group()
            else:
                raise _NaoLido(f"chave em {self.i}")
            self.espera(":")
            saida[chave] = self.valor(fundo + 1)
            if self.espaco() == ",":
                self.i += 1
            elif self.espaco() != "}":
                raise _NaoLido(f"objeto em {self.i}")
        self.i += 1
        return saida

    def lista(self, fundo: int, fecho: str = "]") -> list[object]:
        """Lista `[...]`, ou os argumentos `(...)` da chamada com `fecho=")"`."""
        self.i += 1
        saida: list[object] = []
        while self.espaco() != fecho:
            saida.append(self.valor(fundo + 1))
            if self.espaco() == ",":
                self.i += 1
            elif self.espaco() != fecho:
                raise _NaoLido(f"lista em {self.i}")
        self.i += 1
        return saida

    def texto(self) -> str:
        aspa = self.s[self.i]
        self.i += 1
        partes: list[str] = []
        while True:
            if self.i >= len(self.s):
                raise _NaoLido("texto sem fim")
            c = self.s[self.i]
            self.i += 1
            if c == aspa:
                break
            if c != "\\":
                partes.append(c)
                continue
            e = self.s[self.i : self.i + 1]
            self.i += 1
            if e == "u" and self.s[self.i : self.i + 1] == "{":
                fim = self.s.find("}", self.i)
                partes.append(self.codigo(self.s[self.i + 1 : fim] if fim > 0 else ""))
                self.i = fim + 1
            elif e in ("u", "x"):
                tamanho = 4 if e == "u" else 2
                partes.append(self.codigo(self.s[self.i : self.i + tamanho], tamanho))
                self.i += tamanho
            elif e in ("\n", "\r", " ", " "):
                continue  # continuação de linha
            else:
                partes.append(_ESCAPES.get(e, e))
        # pares substitutos de `😀` viram um caractere; substituto solto vira U+FFFD
        return "".join(partes).encode("utf-16", "surrogatepass").decode("utf-16", "replace")

    @staticmethod
    def codigo(hexa: str, tamanho: int | None = None) -> str:
        valido = (tamanho is None or len(hexa) == tamanho) and 0 < len(hexa) <= 6
        if not valido or any(h not in "0123456789abcdefABCDEF" for h in hexa):
            raise _NaoLido(f"escape {hexa!r}")
        n = int(hexa, 16)
        if n > 0x10FFFF:
            raise _NaoLido(f"escape {hexa!r}")
        return chr(n)

    def pular(self) -> None:
        """Avança até a vírgula ou o fecho no mesmo nível, sem cair dentro de texto."""
        fundo = 0
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in ("'", '"', "`"):
                fim = self.i + 1
                while fim < len(self.s) and self.s[fim] != c:
                    fim += 2 if self.s[fim] == "\\" else 1
                self.i = fim + 1
                continue
            if c in "([{":
                fundo += 1
            elif c in ")]}":
                if fundo == 0:
                    return
                fundo -= 1
            elif c == "," and fundo == 0:
                return
            self.i += 1


def _resolver(valor: object, variaveis: Mapping[str, object], fundo: int = 0) -> object:
    if isinstance(valor, _Ref):
        return variaveis.get(valor.nome)  # variável sem argumento é `undefined`
    if fundo > _PROFUNDIDADE:
        return _ILEGIVEL
    if isinstance(valor, dict):
        return {k: _resolver(v, variaveis, fundo + 1) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_resolver(v, variaveis, fundo + 1) for v in valor]
    return valor


_FUNCAO = re.compile(r"\s*\(\s*function\s*\(([^)]*)\)\s*\{\s*return\s+")


def _estado(pagina: str) -> object:
    """O valor de `window.__NUXT__`, na forma `(function(a,b){return {...}}(1,2))` ou `{...}`."""
    inicio = pagina.find(_MARCA)
    if inicio < 0:
        return None
    inicio += len(_MARCA)
    fim = pagina.find("</script>", inicio)
    texto = pagina[inicio : fim if fim >= 0 else len(pagina)]
    try:
        funcao = _FUNCAO.match(texto)
        if funcao is None:
            return _Leitor(texto).valor()
        params = [p.strip() for p in funcao.group(1).split(",") if p.strip()]
        leitor = _Leitor(texto, params)
        leitor.i = funcao.end()
        corpo = leitor.valor()
        leitor.espaco()
        if leitor.s.startswith(";", leitor.i):
            leitor.i += 1
        leitor.espera("}")
        if leitor.espaco() == ")":  # forma `(function(){...})(args)`
            leitor.i += 1
        if leitor.espaco() != "(":
            raise _NaoLido("sem argumentos")
        args = leitor.lista(0, fecho=")")
        return _resolver(corpo, dict(zip(params, args, strict=False)))
    except _NaoLido:
        return None


# ---- a vaga -------------------------------------------------------------------------------


def _campo(dados: object, *caminho: str) -> object:
    for chave in caminho:
        if not isinstance(dados, dict):
            return None
        dados = dados.get(chave)
    return dados


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _id(valor: object) -> str | None:
    """`bool` e texto vazio não viram `id_externo` (D57)."""
    if isinstance(valor, bool) or not isinstance(valor, int | str):
        return None
    return str(valor).strip() or None


def _valor_positivo(valor: object) -> float | int | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    return valor if 0 < valor <= sys.float_info.max else None


def _salario(vaga: Mapping[str, object]) -> SalarioBruto | None:
    minimo = _valor_positivo(vaga.get("initialSalaryRange"))
    maximo = _valor_positivo(vaga.get("finalSalaryRange"))
    if minimo is None and maximo is None:
        minimo = maximo = _valor_positivo(vaga.get("salaryValue"))
    if minimo is None and maximo is None:
        return None
    # shortcut: `salaryPeriodicity` vem "" na captura e não se sabe os valores; período fica
    # vazio até a fonte mostrar um preenchido
    return SalarioBruto(moeda="BRL", minimo_unidades=minimo, maximo_unidades=maximo)


def _publicada(valor: object) -> datetime | None:
    try:
        quando = datetime.fromisoformat(_texto(valor))
    except ValueError:
        return None
    return quando if quando.tzinfo else None


def _prazo(valor: object) -> date | None:
    try:
        return datetime.fromisoformat(_texto(valor)).date()
    except ValueError:
        return None


def _locais(vaga: Mapping[str, object]) -> tuple[str, ...]:
    cidade = _texto(_campo(vaga, "address", "cityName"))
    uf = _texto(_campo(vaga, "address", "stateAbbr"))
    if cidade:
        return (f"{cidade}, {uf}" if uf else cidade,)
    texto = _texto(vaga.get("cityAndState"))
    return (texto,) if texto else ()


def _modalidade(vaga: Mapping[str, object]) -> str | None:
    tipos = vaga.get("workTypes")
    ids = {_texto(_campo(t, "id")) for t in tipos} if isinstance(tipos, list) else set()
    ids.discard("")
    return ids.pop() if len(ids) == 1 else None  # híbrida e remota juntas: não escolhe


def _etiquetas(vaga: Mapping[str, object]) -> tuple[str, ...]:
    niveis = vaga.get("levelOfInterests")
    nomes = (_texto(_campo(n, "name")) for n in niveis) if isinstance(niveis, list) else ()
    return tuple(dict.fromkeys(n for n in nomes if n))


def _descricao(vaga: Mapping[str, object]) -> str:
    campos = ("description", "roleDescription", "mandatoryRequirements", "desirableRequirements")
    partes = (_texto(vaga.get(c)) for c in campos)
    return "\n".join(dict.fromkeys(p for p in partes if p))  # description e roleDescription repetem


def _vaga(estado: object, url: str) -> VagaColetada | None:
    """A vaga de `state.candidate.vacancy.vacancy`, ou `None` sem título ou empresa (DR-70)."""
    vaga = _campo(estado, "state", "candidate", "vacancy", "vacancy")
    if not isinstance(vaga, dict):
        return None
    titulo = _texto(vaga.get("title"))
    empresa = _texto(vaga.get("companyName")) or _texto(_campo(vaga, "company", "name"))
    if not titulo or not empresa:
        return None
    return VagaColetada(
        fonte="abler",
        escopo="",
        url=url,  # a do sitemap: `fullUrl` fica no subdomínio da empresa e não casa com a lista
        titulo=titulo,
        empresa=empresa,
        descricao_formato="html",
        descricao=_descricao(vaga),
        id_externo=_id(vaga.get("id")),
        locais=_locais(vaga),
        modalidade_declarada=_modalidade(vaga),
        contrato_declarado=_texto(vaga.get("contractingRegime")) or None,
        salario_estruturado=_salario(vaga),
        publicada_em=_publicada(vaga.get("publishedAt")),
        prazo=_prazo(vaga.get("closeOn")),
        etiquetas=_etiquetas(vaga),
    )


class Abler:
    chave: str = "abler"
    nome: str = "Abler"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (_HOST,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return [""]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = 0
        sem_loc = False

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, sem_loc
            # sem `condicional`: o sitemap não traz ETag nem Last-Modified
            resposta = await http.pedir("GET", _SITEMAP, cabecalhos={"Accept": "application/xml"})
            urls, pulados, sem_loc = _ler_sitemap(resposta.texto)
            yield urls

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # HttpDoEscopo conta; outro, não
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if resultado.estado != "ok":
            return resultado
        if sem_loc:
            # shortcut: a contagem dos pulados se perde aqui (não há chave `saude.*` com `n`
            # para formato; D45). Trocar quando a chave existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        if pulados:
            motivo = f"saude.sem_detalhe_n:{pulados}"
            return ResultadoEscopo(resultado.vagas, "ok", motivo, resultado.pedidos)
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A página da vaga; `None` se o endereço não for de vaga, 404/410 ou faltar campo."""
        url = _url_de_vaga(item.url) if isinstance(item, UrlListada) else None
        if url is None:
            return None  # antes de qualquer pedido: o endereço veio de fora
        try:
            resposta = await http.pedir("GET", url, cabecalhos={"Accept": "text/html"})
        except ErroDeRede as erro:
            if erro.status in (404, 410):
                return None
            raise
        return _vaga(_estado(resposta.texto), url)

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A Abler é uma lista só (o sitemap), sem empresa nem identificador a resolver."""
        raise ValueError(f"a Abler não tem identificador: {identificador!r}")


COLETOR = Abler()
