"""Coletor Oracle HCM (apêndice 3.3, desenho 8.6): API REST pública, um escopo por empresa e país.

O escopo é `<host>|<site_number>|<site>|<PAÍS>`: o cadastro guarda o host do tenant no
identificador e `site_number` (`CX_45001`) e `site` (`jobsearch`) em `parametros`; o país (ISO,
maiúsculas) vem das buscas ativas (DR-53), e sem nenhum é o Brasil. A coleta faz um pedido de
descoberta sem filtro de local, lê das facetas (`locationsFacet`) o `Id` da geografia do país (o id
muda por empresa e não é guardado) e pagina a lista filtrada de 25 em 25, com `limit` e `offset`
dentro do `finder`. A lista não traz descrição: o `detalhar` busca o detalhe da vaga.
"""

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Literal
from urllib.parse import urlsplit

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import ErroDeRede, HttpEducado
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.tratamento.locais import ler_locais

_LIMITES = limites("oracle_hcm")
_DOMINIO = "oraclecloud.com"
_POR_PAGINA = 25
MAX_PAGINAS = 100  # trava contra lista sem fim: 2.500 vagas num país numa empresa já é anomalia
# shortcut: só tenants em `*.oraclecloud.com`; domínio próprio da empresa fica de fora até
# aparecer um no cadastro (o resolver também recusa).
_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+oraclecloud\.com")
_SITE_NUMBER = re.compile(r"[A-Za-z0-9_]{1,50}")
_SITE = re.compile(r"[A-Za-z0-9_-]{1,100}")
_PAIS = re.compile(r"[A-Z]{2}")
_ID = re.compile(r"\d{1,20}")  # `Id` da vaga e da faceta: entram na URL
_SITE_NUMBER_HTML = re.compile(r'data-sitenumber="([A-Za-z0-9_]{1,50})"')
_PADRAO = "BR"  # sem país nas buscas (o "testar" do painel), como no Workday
_CABECALHOS = {"Accept": "application/json"}
_DESCRICAO = ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")


class _FormatoMudou(Exception):
    """A resposta não é o JSON esperado, ou nenhuma vaga dela é legível."""


class _NaoEncontrado(Exception):
    """O tenant ou o site não existe (404 na descoberta)."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _inteiro(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _dia(valor: object) -> date | None:
    """`2026-11-13` ou `2026-11-13T04:09:58+00:00`: só a data."""
    try:
        return date.fromisoformat(valor[:10]) if isinstance(valor, str) else None
    except ValueError:
        return None


def _instante(valor: object) -> datetime | None:
    try:
        lido = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lido.replace(tzinfo=UTC) if lido and lido.tzinfo is None else lido


def _separar(escopo: str) -> tuple[str, str, str, str]:
    """`<host>|<site_number>|<site>|<PAÍS>` em quatro partes; `ValueError` se alguma não servir."""
    partes = escopo.split("|")
    host, site_number, site, pais = partes if len(partes) == 4 else ("", "", "", "")
    if not (
        _HOST.fullmatch(host)
        and _SITE_NUMBER.fullmatch(site_number)
        and _SITE.fullmatch(site)
        and _PAIS.fullmatch(pais)
    ):
        raise ValueError(f"escopo do Oracle HCM inválido: {escopo!r}")
    return host, site_number, site, pais


def _busca(dados: object) -> dict[str, object]:
    """`items[0]` da resposta: a busca, com as vagas e as facetas."""
    itens = dados.get("items") if isinstance(dados, dict) else None
    if not isinstance(itens, list) or not itens or not isinstance(itens[0], dict):
        raise _FormatoMudou
    busca: dict[str, object] = itens[0]
    return busca


def _geografia(facetas: list[object], pais: str) -> str | None:
    """`Id` da faceta do país (nome sem vírgula: "SP, Brazil" é estado, não país)."""
    for faceta in facetas:
        if not isinstance(faceta, dict):
            continue
        nome, ident = _texto(faceta.get("Name")), faceta.get("Id")
        ident = str(ident) if _inteiro(ident) else _texto(ident)
        if (
            nome
            and "," not in nome
            and _ID.fullmatch(ident)
            and [lido.pais for lido in ler_locais([nome])] == [pais]
        ):
            return ident
    return None


def _vaga(escopo: str, empresa: str, item: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(item, dict):
        return None
    titulo, ident = _texto(item.get("Title")), item.get("Id")
    if not titulo or not isinstance(ident, str) or not _ID.fullmatch(ident):
        return None
    host, _, site, _ = _separar(escopo)
    secundarios = item.get("secondaryLocations")
    nomes = [item.get("PrimaryLocation")] + [
        s.get("Name")
        for s in (secundarios if isinstance(secundarios, list) else [])
        if isinstance(s, dict)
    ]
    publicada = _dia(item.get("PostedDate"))
    try:
        return VagaColetada(
            fonte="oracle_hcm",
            escopo=escopo,
            url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{ident}",
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            id_externo=ident,
            locais=tuple(n for n in map(_texto, nomes) if n),
            modalidade_declarada=_texto(item.get("WorkplaceType")) or None,
            publicada_em=(
                datetime(publicada.year, publicada.month, publicada.day, tzinfo=UTC)
                if publicada
                else None
            ),
            prazo=_dia(item.get("PostingEndDate")),
        )
    except ValueError:
        return None


class OracleHcm:
    chave: str = "oracle_hcm"
    nome: str = "Oracle HCM"
    leva: Literal["A", "B"] = _LIMITES.leva
    # Cada tenant é um subdomínio (`<tenant>.fa.<região>.oraclecloud.com`); o campo não é lido hoje.
    hosts: tuple[str, ...] = (_DOMINIO,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def __init__(self) -> None:
        # shortcut: `coletar(escopo, http)` não recebe o cadastro, e a lista do Oracle não traz o
        # nome da empresa; os nomes ficam aqui, guardados por `escopos` (como no Workday). Sem
        # passar por `escopos`, o primeiro rótulo do host serve de nome. Trocar com a D50.
        self._nomes: dict[str, str] = {}

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        """Um por empresa válida e país das buscas (DR-53); sem país nas buscas, o Brasil."""
        paises = (p.strip().upper() for p in ctx.paises) if ctx.paises else (_PADRAO,)
        validos = dict.fromkeys(p for p in paises if _PAIS.fullmatch(p))
        nomes: dict[str, str] = {}
        for e in ctx.empresas:
            host = e.identificador.strip().lower()
            site_number = e.parametros.get("site_number", "").strip()
            site = e.parametros.get("site", "").strip()
            for pais in validos:
                escopo = f"{host}|{site_number}|{site}|{pais}"
                try:
                    _separar(escopo)
                except ValueError:
                    continue
                nomes.setdefault(escopo, e.nome)  # duplicata na chamada: o primeiro vale
        self._nomes = nomes  # a cada chamada, o cadastro atual substitui o anterior
        return list(nomes)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        host, site_number, _, pais = _separar(escopo)
        empresa = self._nomes.get(escopo) or host.split(".")[0]
        pulados = lidas = total = 0
        truncou = quebrou = False

        async def pagina(offset: int, geografia: str | None) -> dict[str, object]:
            filtro = f",selectedLocationsFacet={geografia}" if geografia else ""
            url = (
                f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
                "?onlyData=true&expand=requisitionList.secondaryLocations"
                f"&finder=findReqs;siteNumber={site_number},"
                f"facetsList=LOCATIONS%3BWORKPLACE_TYPES%3BPOSTING_DATES,limit={_POR_PAGINA},"
                f"offset={offset},sortBy=POSTING_DATES_DESC{filtro}"
            )
            try:
                resposta = await http.pedir("GET", url, cabecalhos=_CABECALHOS)
            except ErroDeRede as erro:
                if erro.status == 404 and geografia is None:  # só a descoberta diz "não existe"
                    raise _NaoEncontrado from erro
                raise
            try:
                return _busca(json.loads(resposta.texto))
            except ValueError as erro:
                raise _FormatoMudou from erro

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, lidas, total, truncou, quebrou
            facetas = (descoberta := await pagina(0, None)).get("locationsFacet")
            if not _inteiro(descoberta.get("TotalJobsCount")) or not isinstance(facetas, list):
                raise _FormatoMudou
            geografia = _geografia(facetas, pais)
            if geografia is None:  # a empresa não tem vaga no país
                yield []
                return
            offset = 0
            for _ in range(MAX_PAGINAS):
                try:
                    busca = await pagina(offset, geografia)
                    itens = busca.get("requisitionList")
                    if offset == 0:  # o total da primeira página vale para a lista
                        bruto = busca.get("TotalJobsCount")
                        total = (
                            bruto if isinstance(bruto, int) and not isinstance(bruto, bool) else -1
                        )
                    if not isinstance(itens, list) or total < 0:
                        raise _FormatoMudou
                    vagas = [v for v in (_vaga(escopo, empresa, i) for i in itens) if v]
                    if itens and not vagas:
                        raise _FormatoMudou
                except _FormatoMudou:
                    if offset == 0:
                        raise
                    quebrou = True  # página seguinte ilegível: fica o que já foi lido
                    return
                pulados += len(itens) - len(vagas)
                lidas += len(vagas)
                yield vagas
                offset += len(itens)
                if len(itens) < _POR_PAGINA or offset >= total:
                    return
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
            motivo = "saude.limite_atingido"
        elif quebrou or pulados:
            # shortcut: sem a contagem de pulados no motivo (D45, opção b); trocar com a D45.
            motivo = "saude.formato_mudou"
        elif lidas < total:  # a lista acabou antes do total declarado
            motivo = "saude.listagem_incompleta"
        else:
            return resultado
        return ResultadoEscopo(resultado.vagas, "parcial", motivo, resultado.pedidos)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """Completa a vaga da lista com o detalhe; `None` se não houver o que acrescentar.

        A descrição junta os campos `External*Str` (HTML) que vierem; `ExternalPostedStartDate`
        só entra se a lista não deu a data, e `ExternalPostedEndDate` é o prazo. A `url` e os
        demais campos ficam como estão (a URL é a chave da vaga).
        """
        if not isinstance(item, VagaColetada) or not _ID.fullmatch(item.id_externo or ""):
            return None
        try:
            host, site_number, _, _ = _separar(item.escopo)
        except ValueError:
            return None
        url = (
            f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
            f"?expand=all&onlyData=true&finder=ById;Id=%22{item.id_externo}%22,"
            f"siteNumber={site_number}"
        )
        try:
            resposta = await http.pedir("GET", url, cabecalhos=_CABECALHOS)
        except ErroDeRede as erro:
            if erro.status == 404:  # a vaga fechou entre a lista e o detalhe
                return None
            raise
        try:
            detalhe = _busca(json.loads(resposta.texto))
        except ValueError, _FormatoMudou:
            return None
        descricao = "\n".join(t for t in (_texto(detalhe.get(c)) for c in _DESCRICAO) if t)
        inicio = _instante(detalhe.get("ExternalPostedStartDate"))
        prazo = _dia(detalhe.get("ExternalPostedEndDate"))
        if not (descricao or inicio or prazo):
            return None
        return replace(
            item,
            descricao=descricao or item.descricao,
            descricao_formato="html",
            publicada_em=item.publicada_em or inicio,
            prazo=prazo or item.prazo,
        )

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Lê host e `site` do endereço da página de carreira e o `site_number` do HTML dela.

        Aceita `https://<host>/hcmUI/CandidateExperience/<idioma>/sites/<site>[/...]`, com o host
        em `*.oraclecloud.com`; confere tudo antes do pedido. O `site_number` vem do atributo
        `data-sitenumber` da página. `ValueError` se não for uma página do Oracle HCM.
        """
        texto = identificador.strip()
        partes = urlsplit(texto if "://" in texto else f"https://{texto}")
        host = (partes.hostname or "").lower()
        caminho = [p for p in partes.path.split("/") if p]
        site = caminho[4] if len(caminho) > 4 else ""
        if (
            partes.scheme not in ("http", "https")
            or not _HOST.fullmatch(host)
            or caminho[:2] != ["hcmUI", "CandidateExperience"]
            or caminho[3:4] != ["sites"]
            or not _SITE.fullmatch(site)
        ):
            raise ValueError(f"não é uma página de carreira do Oracle HCM: {identificador!r}")
        url = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/jobs"
        try:
            resposta = await http.pedir("GET", url, cabecalhos={"Accept": "text/html"})
        except ErroDeRede as erro:
            if erro.status == 404:
                raise ValueError(f"página de carreira não encontrada: {identificador!r}") from erro
            raise
        achado = _SITE_NUMBER_HTML.search(resposta.texto)
        if achado is None:
            raise ValueError(f"página de carreira sem site_number: {identificador!r}")
        return {"identificador": host, "site_number": achado.group(1), "site": site}


COLETOR = OracleHcm()
