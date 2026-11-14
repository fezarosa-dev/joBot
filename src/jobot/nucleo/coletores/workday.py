"""Coletor Workday (apêndice 3.3, desenho 8.6): API CXS pública, um escopo por empresa.

O escopo é `<tenant>/<site>|<wd>`: o cadastro guarda `tenant/site` no identificador e o `wd` (o
número do servidor, que muda o host) em `parametros["wd"]`. A coleta faz um pedido de descoberta
sem filtro, lê da resposta o id da faceta do Brasil (o id muda por tenant) e pagina a lista filtrada
de 20 em 20 (mais que 20 a API recusa com 400). O `total` só vem na primeira página. A lista não
traz descrição: o `detalhar` busca `jobPostingInfo`.
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

_LIMITES = limites("workday")
_DOMINIO = "myworkdayjobs.com"
_POR_PAGINA = 20  # máximo aceito pela API (com 50 ela responde 400)
MAX_PAGINAS = 100  # trava contra lista sem fim: 2 mil vagas no Brasil numa empresa já é anomalia
_NOME = re.compile(r"[A-Za-z0-9_-]{1,100}")  # tenant e site
_WD = re.compile(r"wd\d{1,3}")
_LOCALE = re.compile(r"[a-z]{2}-[A-Z]{2}")  # prefixo de idioma dos endereços (`pt-BR/<site>`)
_CAMINHO = re.compile(r"/job/[^\s?#\\]+")  # `externalPath` da vaga
_CABECALHOS = {"Accept": "application/json", "Accept-Language": "pt-BR"}
# shortcut: só o Brasil, como pede a linha T64 do plano; trocar pelos países das buscas ativas
# (DR-53) junto com a decisão registrada nas dúvidas da T64.
_PAIS = "BR"


class _FormatoMudou(Exception):
    """A resposta não é o JSON esperado, ou nenhuma vaga dela é legível."""


class _NaoEncontrado(Exception):
    """O tenant ou o site não existe (404)."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _inteiro(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _dia(valor: object) -> date | None:
    try:
        return date.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None


def _separar(escopo: str) -> tuple[str, str, str]:
    """`<tenant>/<site>|<wd>` em três partes; `ValueError` se alguma não servir para o endereço."""
    identificador, barra, wd = escopo.rpartition("|")
    tenant, _, site = identificador.partition("/")
    if not (barra and _WD.fullmatch(wd) and _NOME.fullmatch(tenant) and _NOME.fullmatch(site)):
        raise ValueError(f"escopo do Workday inválido: {escopo!r}")
    return tenant, site, wd


def _facetas(facetas: list[object]) -> dict[str, list[tuple[str, str]]]:
    """Valores `(descritor, id)` de cada `facetParameter`, inclusive das facetas aninhadas."""
    achadas: dict[str, list[tuple[str, str]]] = {}
    pendentes = list(facetas)
    while pendentes:
        faceta = pendentes.pop(0)
        if not isinstance(faceta, dict):
            continue
        parametro, valores = faceta.get("facetParameter"), faceta.get("values")
        if not isinstance(parametro, str) or not isinstance(valores, list):
            continue
        for valor in valores:
            if isinstance(valor, dict) and "facetParameter" in valor:
                pendentes.append(valor)  # grupo (`locationMainGroup` traz `locationCountry`)
            elif isinstance(valor, dict) and _texto(valor.get("id")):
                achadas.setdefault(parametro, []).append(
                    (_texto(valor.get("descriptor")), _texto(valor.get("id")))
                )
    return achadas


def _filtro(facetas: list[object]) -> dict[str, list[str]]:
    """`appliedFacets` que restringe ao país: a faceta de país, senão os locais dele; ou `{}`."""
    achadas = _facetas(facetas)

    def do_pais(parametro: str) -> list[str]:
        return [
            i
            for d, i in achadas.get(parametro, [])
            if any(local.pais == _PAIS for local in ler_locais([d]))
        ]

    for parametro in achadas:
        if "country" in parametro.lower() and (ids := do_pais(parametro)):
            return {parametro: ids}
    ids = do_pais("locations")
    return {"locations": ids} if ids else {}


def _vaga(escopo: str, empresa: str, item: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(item, dict):
        return None
    titulo = _texto(item.get("title"))
    caminho = _texto(item.get("externalPath"))
    if not titulo or not _CAMINHO.fullmatch(caminho):
        return None
    tenant, site, wd = _separar(escopo)
    local = _texto(item.get("locationsText"))
    try:
        return VagaColetada(
            fonte="workday",
            escopo=escopo,
            url=f"https://{tenant}.{wd}.{_DOMINIO}/{site}{caminho}",
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            id_externo=caminho,
            locais=(local,) if local else (),
            # `postedOn` é texto relativo ("Publicado hoje"); a data vem no `detalhar`
        )
    except ValueError:
        return None


class Workday:
    chave: str = "workday"
    nome: str = "Workday"
    leva: Literal["A", "B"] = _LIMITES.leva
    # Cada tenant é um subdomínio (`<tenant>.<wd>.myworkdayjobs.com`); o campo não é lido hoje.
    hosts: tuple[str, ...] = (_DOMINIO,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def __init__(self) -> None:
        # shortcut: `coletar(escopo, http)` não recebe o cadastro, e a lista do Workday não traz o
        # nome da empresa; os nomes ficam aqui, guardados por `escopos` (como no Lever). Sem passar
        # por `escopos`, o tenant serve de nome. Trocar com a decisão da D50 (dúvidas da T64).
        self._nomes: dict[str, str] = {}

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        """Uma por empresa com `tenant/site` e `wd` válidos; as outras ficam de fora."""
        nomes: dict[str, str] = {}
        for e in ctx.empresas:
            escopo = f"{e.identificador.strip()}|{e.parametros.get('wd', '').strip()}"
            try:
                _separar(escopo)
            except ValueError:
                continue
            nomes.setdefault(escopo, e.nome)  # duplicata na chamada: o primeiro vale
        self._nomes = nomes  # a cada chamada, o cadastro atual substitui o anterior
        return list(nomes)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        tenant, site, wd = _separar(escopo)
        url = f"https://{tenant}.{wd}.{_DOMINIO}/wday/cxs/{tenant}/{site}/jobs"
        empresa = self._nomes.get(escopo) or tenant
        pulados = 0
        truncou = False

        async def pagina(filtro: Mapping[str, list[str]], offset: int) -> dict[str, object]:
            corpo = {"appliedFacets": filtro, "limit": _POR_PAGINA, "offset": offset}
            try:
                resposta = await http.pedir(
                    "POST",
                    url,
                    cabecalhos=_CABECALHOS | {"Content-Type": "application/json"},
                    corpo_json=corpo | {"searchText": ""},
                )
            except ErroDeRede as erro:
                if erro.status == 404:
                    raise _NaoEncontrado from erro
                raise
            try:
                dados = json.loads(resposta.texto)
            except ValueError as erro:
                raise _FormatoMudou from erro
            if not isinstance(dados, dict):
                raise _FormatoMudou
            return dados

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, truncou
            descoberta = await pagina({}, 0)
            facetas = descoberta.get("facets")
            if not _inteiro(descoberta.get("total")) or not isinstance(facetas, list):
                raise _FormatoMudou
            filtro = _filtro(facetas)
            if not filtro:  # a empresa não tem vaga no país
                yield []
                return
            offset = 0
            total = 0
            for _ in range(MAX_PAGINAS):
                dados = await pagina(filtro, offset)
                itens = dados.get("jobPostings")
                if offset == 0:  # nas páginas seguintes o `total` vem 0
                    bruto = dados.get("total")
                    total = bruto if isinstance(bruto, int) and not isinstance(bruto, bool) else -1
                if not isinstance(itens, list) or total < 0:
                    raise _FormatoMudou
                vagas = [v for v in (_vaga(escopo, empresa, i) for i in itens) if v is not None]
                if itens and not vagas:
                    raise _FormatoMudou
                pulados += len(itens) - len(vagas)
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
        if truncou and resultado.estado == "ok":  # lista incompleta: só fecha o que tem 30+ dias
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.limite_atingido", resultado.pedidos
            )
        if pulados and resultado.estado == "ok":
            # shortcut: sem a contagem de pulados no motivo (D45, opção b); trocar com a D45.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """Completa a vaga da lista com `jobPostingInfo`; `None` se não houver o que acrescentar.

        Lê a descrição (HTML), `startDate` (publicada em), `endDate` (prazo) e `timeType`. A `url`
        e os demais campos ficam como estão (a URL é a chave da vaga).
        """
        if not isinstance(item, VagaColetada) or not _CAMINHO.fullmatch(item.id_externo or ""):
            return None
        try:
            tenant, site, wd = _separar(item.escopo)
        except ValueError:
            return None
        url = f"https://{tenant}.{wd}.{_DOMINIO}/wday/cxs/{tenant}/{site}{item.id_externo}"
        try:
            resposta = await http.pedir("GET", url, cabecalhos=_CABECALHOS)
        except ErroDeRede as erro:
            if erro.status == 404:  # a vaga fechou entre a lista e o detalhe
                return None
            raise
        try:
            dados = json.loads(resposta.texto)
        except ValueError:
            return None
        info = dados.get("jobPostingInfo") if isinstance(dados, dict) else None
        descricao = _texto(info.get("jobDescription")) if isinstance(info, dict) else ""
        if not isinstance(info, dict) or not descricao:
            return None
        inicio = _dia(info.get("startDate"))
        return replace(
            item,
            descricao=descricao,
            descricao_formato="html",
            publicada_em=(
                datetime(inicio.year, inicio.month, inicio.day, tzinfo=UTC)
                if inicio
                else item.publicada_em
            ),
            prazo=_dia(info.get("endDate")) or item.prazo,
            contrato_declarado=_texto(info.get("timeType")) or item.contrato_declarado,
        )

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Lê `tenant/site` e o `wd` do endereço do quadro de vagas; sem pedido.

        Aceita `https://<tenant>.<wd>.myworkdayjobs.com/[<idioma>/]<site>[/...]` e o endereço da
        API (`/wday/cxs/<tenant>/<site>/...`). Só o identificador não basta: sem o `wd` não há host.
        `ValueError` se não for um quadro do Workday.
        """
        texto = identificador.strip()
        partes = urlsplit(texto if "://" in texto else f"https://{texto}")
        if partes.scheme not in ("http", "https"):
            raise ValueError(f"endereço não é http/https: {identificador!r}")
        rotulos = (partes.hostname or "").lower().split(".")
        if not (
            len(rotulos) == 4
            and ".".join(rotulos[2:]) == _DOMINIO
            and _WD.fullmatch(rotulos[1])
            and _NOME.fullmatch(rotulos[0])
        ):
            raise ValueError(f"não é um quadro do Workday: {identificador!r}")
        tenant, wd = rotulos[0], rotulos[1]
        caminho = [p for p in partes.path.split("/") if p]
        if caminho[:2] == ["wday", "cxs"]:
            tenant, site = (caminho[2], caminho[3]) if len(caminho) > 3 else (tenant, "")
        else:
            if caminho and _LOCALE.fullmatch(caminho[0]):
                caminho = caminho[1:]
            site = caminho[0] if caminho else ""
        if not _NOME.fullmatch(tenant) or not _NOME.fullmatch(site):
            raise ValueError(f"quadro do Workday sem tenant ou site: {identificador!r}")
        return {"identificador": f"{tenant}/{site}", "wd": wd}


COLETOR = Workday()
