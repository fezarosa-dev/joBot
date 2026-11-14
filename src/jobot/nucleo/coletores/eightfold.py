"""Coletor Eightfold (apêndice 3.3): um escopo por empresa, o host do quadro.

Cada empresa está numa de duas gerações da API, guardadas em `parametros` com o domínio
(desenho, seção 8.6): PCSX (`/api/pcsx/search`, total em `data.count`) e v2
(`/api/apply/v2/jobs`, total em `count`). As duas trazem 10 vagas por página. A lista PCSX vem
sem descrição (o `detalhar` busca o HTML); a lista v2 já traz o texto achatado, que fica como a
descrição em texto: o detalhe só pede vaga sem descrição, então o `detalhar` v2 só roda se alguém o
chamar por fora.

Microsoft: nunca mandar o filtro `work_site` (deu 429 duas vezes). O ritmo de 5 s, a vez por dia e
o 429 que encerra só ela vêm de `por_escopo` no `fontes.json`, cuja chave é o host.
"""

import json
import math
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal, NamedTuple
from urllib.parse import parse_qs, quote, urlsplit

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import Bloqueio, ErroDeRede, HttpEducado, host_local
from jobot.nucleo.modelo import VagaColetada, confere_http

_LIMITES = limites("eightfold")
_POR_PAGINA = 10  # fixo nas duas gerações (apêndice 3.3)
MAX_PAGINAS = 100  # por país: trava contra `count` mentiroso (mil vagas no Brasil já é anomalia)
_HOST = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+")
_ID = re.compile(r"[A-Za-z0-9_-]{1,100}")
_DOMINIO_NO_ROBOTS = re.compile(r"[?&]domain=([A-Za-z0-9.-]+)")
# Quadros vistos no apêndice 3.3 cujo domínio não é o nome do host.
_DOMINIOS = {"apply.careers.microsoft.com": "microsoft.com", "jobs.nvidia.com": "nvidia.com"}
# A API filtra pelo nome do país em inglês; código fora daqui fica de fora (DR-53). Sem nenhum
# país (o "testar" do painel), busca no Brasil: sem `location` a API devolveria o mundo todo.
_PAISES_EN = {
    "BR": "Brazil",
    "PT": "Portugal",
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "DE": "Germany",
    "ES": "Spain",
    "FR": "France",
    "IT": "Italy",
    "NL": "Netherlands",
    "IE": "Ireland",
    "AR": "Argentina",
    "CL": "Chile",
    "CO": "Colombia",
    "MX": "Mexico",
    "UY": "Uruguay",
    "PE": "Peru",
    "IN": "India",
}
_PADRAO = ("Brazil",)


class _NaoEncontrado(Exception):
    """404 no primeiro pedido: o quadro não existe (chega como `ErroDeRede` com status 404)."""


class _FormatoMudou(Exception):
    """A resposta não traz a lista de vagas, ou nenhuma vaga dela é legível."""


class _Cadastro(NamedTuple):
    nome: str
    dominio: str
    geracao: Literal["pcsx", "v2"]


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _http(valor: object) -> str | None:
    """O endereço como veio, se for http(s); senão `None` (nunca reescreve)."""
    if not isinstance(valor, str):
        return None
    try:
        confere_http(valor, "url")
    except ValueError:
        return None
    return valor


def _id(valor: object) -> str | None:
    texto = str(valor) if isinstance(valor, int) and not isinstance(valor, bool) else valor
    return texto if isinstance(texto, str) and _ID.fullmatch(texto) else None


def _epoch(valor: object) -> datetime | None:
    """Epoch em segundos (número ou texto numérico); fora de faixa vira `None`."""
    if isinstance(valor, str):
        try:
            valor = float(valor.strip())
        except ValueError:
            return None
    if not isinstance(valor, int | float) or isinstance(valor, bool):
        return None
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    try:
        return datetime.fromtimestamp(valor, UTC)
    except OverflowError, OSError, ValueError:
        return None


def _lista(valor: object) -> list[str]:
    return [_texto(v) for v in valor] if isinstance(valor, list) else []


def _unicos(valores: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(filter(None, valores)))


def _vaga(host: str, empresa: str, v2: bool, job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar `id` ou `name` (DR-08)."""
    if not isinstance(job, dict):
        return None
    ident, titulo = _id(job.get("id")), _texto(job.get("name"))
    if ident is None or not titulo:
        return None
    propria = f"https://{host}/careers/job/{ident}"
    if v2:
        locais = _lista(job.get("locations")) or [_texto(job.get("location"))]
        return VagaColetada(
            fonte="eightfold",
            escopo=host,
            url=_http(job.get("canonicalPositionUrl")) or propria,
            titulo=titulo,
            empresa=empresa,
            descricao_formato="texto",
            descricao=_texto(job.get("job_description")),
            id_externo=ident,
            locais=_unicos(locais),
            modalidade_declarada=_texto(job.get("work_location_option")) or None,
            publicada_em=_epoch(job.get("t_create")),
            etiquetas=_unicos([_texto(job.get("department")), _texto(job.get("business_unit"))]),
        )
    return VagaColetada(
        fonte="eightfold",
        escopo=host,
        url=propria,
        titulo=titulo,
        empresa=empresa,
        descricao_formato="html",  # a descrição vem no `detalhar`
        id_externo=ident,
        locais=_unicos(_lista(job.get("locations"))),
        modalidade_declarada=_texto(job.get("workLocationOption")) or None,
        publicada_em=_epoch(job.get("postedTs")),
        etiquetas=_unicos([_texto(job.get("department"))]),
    )


def _ler(
    host: str, empresa: str, v2: bool, texto: str
) -> tuple[list[VagaColetada], int, int, int | None]:
    """As vagas legíveis, quantas foram puladas, quantas vieram e o total (se for legível)."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    caixa = (dados if v2 else dados.get("data")) if isinstance(dados, dict) else None
    posicoes = caixa.get("positions") if isinstance(caixa, dict) else None
    if not isinstance(caixa, dict) or not isinstance(posicoes, list):
        raise _FormatoMudou
    vagas = [v for v in (_vaga(host, empresa, v2, p) for p in posicoes) if v is not None]
    if posicoes and not vagas:
        raise _FormatoMudou
    total = caixa.get("count")
    valido = isinstance(total, int) and not isinstance(total, bool) and total >= 0
    return vagas, len(posicoes) - len(vagas), len(posicoes), total if valido else None


def _params(v2: bool, dominio: str, local: str, inicio: int) -> dict[str, str]:
    """Os da lista, sem `work_site` (a Microsoft devolve 429 com ele)."""
    if v2:
        return {
            "domain": dominio,
            "start": str(inicio),
            "num": str(_POR_PAGINA),
            "location": local,
            "sort_by": "timestamp",
        }
    return {
        "domain": dominio,
        "query": "",
        "location": local,
        "start": str(inicio),
        "sort_by": "timestamp",
    }


def _url_lista(host: str, v2: bool) -> str:
    return f"https://{host}/api/apply/v2/jobs" if v2 else f"https://{host}/api/pcsx/search"


def _locais(paises: Sequence[str]) -> tuple[str, ...]:
    """Os nomes da API; vazio se há países e nenhum está no mapa (não cai para o Brasil)."""
    if not paises:
        return _PADRAO
    nomes = (_PAISES_EN.get(p.strip().upper()) for p in paises)
    return tuple(dict.fromkeys(n for n in nomes if n))


class Eightfold:
    chave: str = "eightfold"
    nome: str = "Eightfold"
    leva: Literal["A", "B"] = _LIMITES.leva
    # Os quadros vistos no apêndice 3.3; o host de cada empresa vem do cadastro.
    hosts: tuple[str, ...] = (
        "mercadolibre.eightfold.ai",
        "jobs.nvidia.com",
        "apply.careers.microsoft.com",
        "bayer.eightfold.ai",
    )
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def __init__(self) -> None:
        # shortcut: `coletar(escopo, http)` não recebe o cadastro; nome, domínio, geração e países
        # ficam aqui, guardados por `escopos`. Trocar se o contrato do coletor passar a entregar a
        # empresa (R4, ver duvidas da T28).
        self._empresas: dict[str, _Cadastro] = {}
        self._paises: tuple[str, ...] = _PADRAO

    def _cadastro(self, host: str) -> _Cadastro | None:
        """O cadastro do escopo; sem ele, só os quadros de domínio conhecido (para o "testar")."""
        if not _HOST.fullmatch(host):
            return None
        cadastro = self._empresas.get(host) or _Cadastro(host, _DOMINIOS.get(host, ""), "pcsx")
        return cadastro if _HOST.fullmatch(cadastro.dominio) else None

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        empresas: dict[str, _Cadastro] = {}
        for e in ctx.empresas:
            dominio = _texto(e.parametros.get("dominio")).lower() or _DOMINIOS.get(e.identificador)
            geracao: Literal["pcsx", "v2"] = "v2" if e.parametros.get("geracao") == "v2" else "pcsx"
            # duplicata na chamada: o primeiro vale
            empresas.setdefault(e.identificador, _Cadastro(e.nome, dominio or "", geracao))
        self._empresas = empresas  # a cada chamada, o cadastro atual substitui o anterior
        self._paises = _locais(ctx.paises)
        return list(empresas) if self._paises else []  # nenhum país da API: nada a pedir

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        cadastro = self._cadastro(escopo)
        if cadastro is None:  # sem domínio não há como pedir (nem host válido)
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.empresa_nao_encontrada", pedidos)
        v2 = cadastro.geracao == "v2"
        url = _url_lista(escopo, v2)
        vistos: set[str] = set()
        lidas = pulados = 0
        truncou = cortou = False

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal lidas, pulados, truncou, cortou
            for local in self._paises:
                inicio = 0
                for _ in range(MAX_PAGINAS):
                    params = _params(v2, cadastro.dominio, local, inicio)
                    try:
                        resposta = await http.pedir("GET", url, params=params)
                    except ErroDeRede as erro:
                        if erro.status == 404 and not lidas:
                            raise _NaoEncontrado from erro
                        raise
                    try:
                        vagas, n_pulados, n_itens, total = _ler(
                            escopo, cadastro.nome, v2, resposta.texto
                        )
                    except _FormatoMudou:
                        if not lidas:
                            raise
                        cortou = True  # página seguinte ilegível: fica o que já foi lido
                        return
                    lidas += 1
                    pulados += n_pulados
                    novas = [v for v in vagas if v.id_externo not in vistos]
                    vistos.update(v.id_externo for v in novas if v.id_externo)
                    yield novas
                    inicio += n_itens
                    if n_itens < _POR_PAGINA or (total is not None and inicio >= total):
                        break
                else:
                    truncou = True

        try:
            resultado = await juntar_paginas(http, paginas())
        except (_NaoEncontrado, _FormatoMudou) as erro:
            motivo = (
                "saude.empresa_nao_encontrada"
                if isinstance(erro, _NaoEncontrado)
                else "saude.formato_mudou"
            )
            return ResultadoEscopo((), "falhou", motivo, getattr(http, "pedidos", 0))
        if resultado.estado != "ok":
            return resultado
        if truncou:  # lista incompleta: só fecha o que tem 30+ dias
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.limite_atingido", resultado.pedidos
            )
        if pulados or cortou:
            # shortcut: sem a contagem de pulados no motivo (D45, opção b); trocar com a D45.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """Troca a descrição pelo HTML do detalhe; `None` se não houver o que trocar.

        A `url` e os demais campos da lista ficam como estão (a URL é a chave da vaga).
        """
        if not isinstance(item, VagaColetada) or not _ID.fullmatch(item.id_externo or ""):
            return None
        cadastro = self._cadastro(item.escopo)
        if cadastro is None or item.id_externo is None:
            return None
        if cadastro.geracao == "v2":
            url = f"https://{item.escopo}/api/apply/v2/jobs/{quote(item.id_externo, safe='')}"
            params = {"domain": cadastro.dominio}
        else:
            url = f"https://{item.escopo}/api/pcsx/position_details"
            params = {"position_id": item.id_externo, "domain": cadastro.dominio, "hl": "pt-BR"}
        try:
            resposta = await http.pedir("GET", url, params=params)
        except ErroDeRede as erro:
            if erro.status == 404:  # a vaga fechou entre a lista e o detalhe
                return None
            raise
        try:
            dados = json.loads(resposta.texto)
        except ValueError:
            return None
        if not isinstance(dados, dict):
            return None
        if cadastro.geracao == "v2":
            descricao = _texto(dados.get("job_description"))
        else:
            caixa = dados.get("data")
            descricao = _texto(caixa.get("jobDescription")) if isinstance(caixa, dict) else ""
        if not descricao:
            return None
        return replace(item, descricao=descricao, descricao_formato="html")

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o host ou um endereço do quadro; devolve host, domínio e geração.

        O domínio sai do parâmetro `domain` do endereço, da lista de conhecidos ou do `Sitemap`
        do robots.txt. A geração é a primeira que responde com lista (PCSX, depois v2).
        `ValueError` se não for um quadro do Eightfold.
        """
        texto = identificador.strip()
        partes = urlsplit(texto if "://" in texto else f"https://{texto}")
        if partes.scheme not in ("http", "https") or partes.username or partes.password:
            raise ValueError(f"endereço não aceito: {identificador!r}")
        if partes.port is not None:  # `port` inválida também dá ValueError
            raise ValueError(f"endereço com porta: {identificador!r}")
        host = (partes.hostname or "").rstrip(".")
        if not _HOST.fullmatch(host) or host_local(host):
            raise ValueError(f"host inválido: {identificador!r}")
        dominio = _texto(parse_qs(partes.query).get("domain", [""])[0]).lower()
        dominio = dominio or _DOMINIOS.get(host, "")
        if dominio and not _HOST.fullmatch(dominio):
            raise ValueError(f"domínio inválido: {identificador!r}")
        dominio = dominio or await _dominio_do_robots(host, http)
        if not dominio:
            raise ValueError(f"domínio do Eightfold não encontrado: {identificador!r}")
        return {
            "identificador": host,
            "dominio": dominio,
            "geracao": await _geracao(host, dominio, http),
        }


async def _dominio_do_robots(host: str, http: HttpEducado) -> str:
    """O `domain` do endereço do `Sitemap` no robots.txt; "" se não houver."""
    try:
        resposta = await http.pedir("GET", f"https://{host}/robots.txt")
    except ErroDeRede as erro:
        if erro.status == 404:
            return ""
        raise
    achado = _DOMINIO_NO_ROBOTS.search(resposta.texto)
    dominio = achado.group(1).lower().rstrip(".") if achado else ""
    return dominio if _HOST.fullmatch(dominio) else ""


async def _geracao(host: str, dominio: str, http: HttpEducado) -> Literal["pcsx", "v2"]:
    """PCSX desligado devolve 403 ("PCSX is not enabled"): aí vale a v2 (apêndice 3.3)."""
    geracoes: tuple[Literal["pcsx", "v2"], ...] = ("pcsx", "v2")
    for geracao in geracoes:
        v2 = geracao == "v2"
        try:
            resposta = await http.pedir(
                "GET", _url_lista(host, v2), params=_params(v2, dominio, _PADRAO[0], 0)
            )
        except Bloqueio:
            continue
        except ErroDeRede as erro:
            if erro.status == 404:
                raise ValueError(f"quadro do Eightfold não encontrado: {host}") from erro
            raise
        try:
            _ler(host, host, v2, resposta.texto)
        except _FormatoMudou:
            continue
        return geracao
    raise ValueError(f"não é um quadro do Eightfold: {host}")


COLETOR = Eightfold()
