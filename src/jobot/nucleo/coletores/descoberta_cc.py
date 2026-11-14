"""Descoberta de empresas pelo índice bruto do Common Crawl (desenho 8.7, apêndice 5).

Lê o `cluster.idx` em fluxo (teto próprio de 128 MB, sem guardar o arquivo), escolhe os blocos
que cobrem os prefixos dos quatro ATS e busca só esses blocos com `Range`. Cada bloco é um gzip
independente com linhas `<surt> <data> <json>`. Todo pedido ao Common Crawl espera 10 s e tem
uma nova tentativa no máximo; quem chama decide o que fazer com o erro (503 = parar até o dia
seguinte). Não é coletor: o módulo não tem `COLETOR` e o registro o ignora.
"""

import json
import re
import zlib
from collections.abc import Mapping
from contextlib import aclosing
from dataclasses import dataclass
from urllib.parse import urlsplit

from jobot.nucleo.coletores import ashby, greenhouse, gupy, lever
from jobot.nucleo.coletores.base import Coletor
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import (
    Bloqueio,
    ClienteEducado,
    ErroDeRede,
    HttpDoEscopo,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    RespostaGrande,
)
from jobot.nucleo.modelo import Modalidade, VagaColetada, confere_http
from jobot.nucleo.tratamento.tratar import tratar

COLLINFO = "https://index.commoncrawl.org/collinfo.json"
_ARQUIVO_URL = "https://data.commoncrawl.org/cc-index/collections/{indice}/indexes/{arquivo}"
TETO_CLUSTER = 128 * 1024 * 1024  # o cluster.idx tem ~105 MB, acima do teto padrão de 5 MB
_TETO_BLOCO = 4 * 1024 * 1024  # blocos de 250 a 330 KB; acima disso o índice mudou de formato
_TETO_CDX = 64 * 1024 * 1024  # bloco descomprimido: barra gzip que explode
ESPERA_S = 10.0
_PEDIDOS = 2  # um pedido e uma nova tentativa, no máximo (apêndice 5)
PREFIXOS: Mapping[str, str] = {
    "io,greenhouse,boards)/": "greenhouse",
    "io,greenhouse,job-boards)/": "greenhouse",
    "co,lever,jobs)/": "lever",
    "com,ashbyhq,jobs)/": "ashby",
    "io,gupy,": "gupy",
}
_COLETORES: Mapping[str, Coletor] = {
    c.chave: c for c in (greenhouse.COLETOR, lever.COLETOR, ashby.COLETOR, gupy.COLETOR)
}
_INDICE = re.compile(r"CC-MAIN-[0-9]{4}-[0-9]{2}")
_ARQUIVO = re.compile(r"cdx-[0-9]{5}\.gz")
_NUMERO = re.compile(r"[0-9]{1,15}")
_SUBDOMINIO = re.compile(r"[a-z0-9-]{1,63}")
_GUPY_NAO_EMPRESA = frozenset({"portal", "www"})
_ERROS_DO_TESTE = (
    ValueError,
    Bloqueio,
    ErroDeRede,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    RespostaGrande,
)


@dataclass(frozen=True)
class Sugestao:
    fonte: str  # o ATS: greenhouse, lever, ashby ou gupy
    identificador: str
    url_exemplo: str  # o endereço que o índice viu


@dataclass(frozen=True)
class _Bloco:
    chave: str  # "<surt> <data>" da primeira linha do bloco
    arquivo: str
    offset: int
    tamanho: int


def _cc(cliente: ClienteEducado) -> HttpDoEscopo:
    """Escopo de um pedido ao Common Crawl: 10 s por host e uma nova tentativa no máximo."""
    return cliente.escopo(espera_s=ESPERA_S, condicional=False, max_pedidos=_PEDIDOS)


async def _baixar(
    cliente: ClienteEducado, url: str, teto: int, cabecalhos: Mapping[str, str] | None = None
) -> bytes:
    fluxo = _cc(cliente).ler_em_fluxo(url, teto_bytes=teto, cabecalhos=cabecalhos)
    async with aclosing(fluxo) as f:
        return b"".join([parte async for parte in f])


async def indice_mais_novo(http: ClienteEducado) -> str:
    """O id mais novo da lista de índices; `ValueError` se a lista não traz nenhum id válido."""
    dados = (await _cc(http).pedir("GET", COLLINFO)).json()
    ids = [d.get("id") for d in dados if isinstance(d, dict)] if isinstance(dados, list) else []
    validos = [i for i in ids if isinstance(i, str) and _INDICE.fullmatch(i)]
    if not validos:
        raise ValueError("collinfo.json sem índice reconhecível")
    return max(validos)  # CC-MAIN-AAAA-SS: a ordem do texto é a do tempo


def _fim(prefixo: str) -> str:
    """Menor texto maior que todo texto que começa com `prefixo`."""
    return prefixo[:-1] + chr(ord(prefixo[-1]) + 1)


def _cobre(bloco: _Bloco, proxima: str | None) -> bool:
    """O bloco vai de `bloco.chave` até `proxima` (exclusive): pode ter linha de algum prefixo?"""
    return any(bloco.chave < _fim(p) and (proxima is None or proxima > p) for p in PREFIXOS)


def _linha_do_cluster(linha: bytes) -> _Bloco | None:
    texto = linha.decode("utf-8").strip()
    if not texto:
        return None
    chave, arquivo, offset, tamanho, _ = texto.split("\t")  # ValueError: formato mudou
    if not (
        _ARQUIVO.fullmatch(arquivo) and _NUMERO.fullmatch(offset) and _NUMERO.fullmatch(tamanho)
    ):
        raise ValueError(f"linha do cluster.idx fora do formato: {texto[:200]!r}")
    if not 0 < int(tamanho) <= _TETO_BLOCO:
        raise ValueError(f"bloco de {tamanho} bytes no cluster.idx")
    return _Bloco(chave, arquivo, int(offset), int(tamanho))


async def _blocos(cliente: ClienteEducado, indice: str) -> list[_Bloco]:
    """Lê o cluster.idx em fluxo e devolve os blocos que podem ter linha de algum prefixo."""
    url = _ARQUIVO_URL.format(indice=indice, arquivo="cluster.idx")
    escolhidos: list[_Bloco] = []
    anterior: _Bloco | None = None
    resto = b""

    def ver(linha: bytes) -> None:
        nonlocal anterior
        bloco = _linha_do_cluster(linha)
        if bloco is None:
            return
        if anterior is not None and _cobre(anterior, bloco.chave):
            escolhidos.append(anterior)
        anterior = bloco

    async with aclosing(_cc(cliente).ler_em_fluxo(url, teto_bytes=TETO_CLUSTER)) as fluxo:
        async for parte in fluxo:
            *linhas, resto = (resto + parte).split(b"\n")
            for linha in linhas:
                ver(linha)
    ver(resto)
    if anterior is not None and _cobre(anterior, None):
        escolhidos.append(anterior)
    return escolhidos


async def _ler_bloco(cliente: ClienteEducado, indice: str, bloco: _Bloco) -> str:
    url = _ARQUIVO_URL.format(indice=indice, arquivo=bloco.arquivo)
    faixa = {"Range": f"bytes={bloco.offset}-{bloco.offset + bloco.tamanho - 1}"}
    dados = await _baixar(cliente, url, bloco.tamanho, faixa)
    if len(dados) != bloco.tamanho:
        raise ErroDeRede(f"{url}: {len(dados)} bytes recebidos, {bloco.tamanho} pedidos")
    gz = zlib.decompressobj(wbits=31)  # cada bloco é um gzip independente
    texto = gz.decompress(dados, _TETO_CDX)
    if gz.unconsumed_tail:
        raise RespostaGrande(f"{url}: bloco descomprimido acima de {_TETO_CDX} bytes")
    return texto.decode("utf-8", errors="replace")


def _gupy(url: str) -> str:
    """Subdomínio de empresa da Gupy (`acme.gupy.io`); `ValueError` se não for um."""
    host = (urlsplit(url).hostname or "").lower()
    sub = host.removesuffix(".gupy.io")
    if sub == host or not _SUBDOMINIO.fullmatch(sub) or sub in _GUPY_NAO_EMPRESA:
        raise ValueError(f"não é página de empresa da Gupy: {url!r}")
    return sub


async def _sugestao(cliente: ClienteEducado, surt: str, url: str) -> Sugestao | None:
    fonte = next((f for p, f in PREFIXOS.items() if surt.startswith(p)), None)
    if fonte is None:
        return None
    try:
        confere_http(url, "url_exemplo")
        if fonte == "gupy":
            identificador = _gupy(url)
        else:  # o resolver dessas três fontes não faz pedido (D45)
            http = cliente.escopo(espera_s=ESPERA_S, max_pedidos=0)
            identificador = (await _COLETORES[fonte].resolver(url, http))["identificador"]
    except ValueError:
        return None
    return Sugestao(fonte, identificador, url)


async def sugerir(http: ClienteEducado, indice: str) -> list[Sugestao]:
    """Os quadros dos quatro ATS que o índice viu, um por (fonte, identificador sem caixa).

    Erros de rede, limite (503 incluído) e de formato sobem: quem chama para a descoberta.
    """
    if not _INDICE.fullmatch(indice):
        raise ValueError(f"índice inválido: {indice!r}")
    achadas: dict[tuple[str, str], Sugestao] = {}
    for bloco in await _blocos(http, indice):
        for linha in (await _ler_bloco(http, indice, bloco)).splitlines():
            surt, _, resto = linha.partition(" ")
            _, _, bruto = resto.partition(" ")
            if not any(surt.startswith(p) for p in PREFIXOS):
                continue
            try:
                url = json.loads(bruto).get("url")
            except ValueError, AttributeError:
                continue  # linha estragada: as outras do bloco valem
            if not isinstance(url, str):
                continue
            s = await _sugestao(http, surt, url)
            if s is not None:
                achadas.setdefault((s.fonte, s.identificador.lower()), s)
    return list(achadas.values())


def _no_brasil_ou_remota(vaga: VagaColetada) -> bool:
    t = tratar(vaga)
    return t.modalidade is Modalidade.REMOTO or any(local.pais == "BR" for local in t.locais)


async def testar(sugestao: Sugestao, http: ClienteEducado) -> bool:
    """Lê a primeira página do quadro no ATS: tem vaga no Brasil ou remota?

    Falha de rede, bloqueio ou quadro que não existe dá `False` (a empresa não vira sugestão).
    """
    coletor = _COLETORES[sugestao.fonte]
    escopo_http = http.escopo(
        espera_s=limites(sugestao.fonte).espera_s, condicional=False, max_pedidos=_PEDIDOS
    )
    escopo = sugestao.identificador
    try:
        if sugestao.fonte == "gupy":  # a API casa o nome da página, com caixa exata (decisão 29)
            nome = (await coletor.resolver(sugestao.identificador, escopo_http))["careerPageName"]
            escopo = f"empresa:{sugestao.identificador}:{nome}"
        resultado = await coletor.coletar(escopo, escopo_http)
    except _ERROS_DO_TESTE:
        return False
    return any(_no_brasil_ou_remota(v) for v in resultado.vagas if isinstance(v, VagaColetada))
