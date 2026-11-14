"""Coletor We Work Remotely (apêndice 2.2): RSS 2.0, um escopo por feed.

O feed traz a descrição em cada item: não há paginação nem `detalhar`. XML lido com `xml.etree`
(DR-49: expat protegido contra bomba de entidades e teto de 5 MB da resposta).
"""

import re
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from typing import Literal

from jobot.nucleo.coletores.base import (
    SEM_MUDANCA,
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import HttpEducado
from jobot.nucleo.modelo import VagaColetada

_LIMITES = limites("wwr")
_BASE = "https://weworkremotely.com"
_CATEGORIAS = (
    "all-other-remote-jobs",
    "remote-back-end-programming-jobs",
    "remote-customer-support-jobs",
    "remote-design-jobs",
    "remote-devops-sysadmin-jobs",
    "remote-front-end-programming-jobs",
    "remote-full-stack-programming-jobs",
    "remote-management-and-finance-jobs",
    "remote-product-jobs",
    "remote-programming-jobs",
    "remote-sales-and-marketing-jobs",
)
# escopo -> endereço do feed: "geral" é o feed de 100 itens; o resto é uma categoria
_FEEDS = {"geral": f"{_BASE}/remote-jobs.rss"} | {
    c: f"{_BASE}/categories/{c}.rss" for c in _CATEGORIAS
}
_SEM_BANDEIRA = re.compile(r"^[\W_]+")  # o país vem com o emoji da bandeira na frente


class _FormatoMudou(Exception):
    """O XML não abre, não tem canal ou nenhum item dele é legível."""


def _texto(item: ET.Element, nome: str) -> str:
    return (item.findtext(nome) or "").strip()


def _data_hora(valor: str) -> datetime | None:
    try:
        lida = parsedate_to_datetime(valor)
    except TypeError, ValueError:
        return None
    # "-0000" (fuso desconhecido) chega sem fuso: vale UTC
    return lida.replace(tzinfo=UTC) if lida.tzinfo is None else lida


def _data(valor: str) -> date | None:
    lida = _data_hora(valor)
    return lida.date() if lida else None


def _vaga(escopo: str, item: ET.Element) -> VagaColetada | None:
    """Uma vaga do feed, ou `None` se faltar campo obrigatório (DR-08)."""
    empresa, dois_pontos, titulo = _texto(item, "title").partition(": ")  # primeiro ": "
    empresa, titulo = empresa.strip(), titulo.strip()
    if not dois_pontos or not empresa or not titulo:
        return None
    locais = (
        _texto(item, "region"),
        _texto(item, "state"),
        _SEM_BANDEIRA.sub("", _texto(item, "country")),
    )
    try:
        return VagaColetada(
            fonte="wwr",
            escopo=escopo,
            url=_texto(item, "link"),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            descricao=_texto(item, "description"),  # o XML já tirou o escape: é HTML
            id_externo=_texto(item, "guid") or None,
            locais=tuple(dict.fromkeys(filter(None, locais))),
            modalidade_declarada="remote",  # o quadro só tem vaga remota
            contrato_declarado=_texto(item, "type") or None,
            publicada_em=_data_hora(_texto(item, "pubDate")),
            prazo=_data(_texto(item, "expires_at")),
            etiquetas=tuple(filter(None, [_texto(item, "category")])),
        )
    except ValueError:  # url vazia ou fora de http/https
        return None


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis e quantas foram puladas."""
    try:
        canal = ET.fromstring(texto).find("channel")
    except ET.ParseError as erro:
        raise _FormatoMudou from erro
    if canal is None:
        raise _FormatoMudou
    itens = canal.findall("item")
    vagas = [v for v in (_vaga(escopo, i) for i in itens) if v is not None]
    if itens and not vagas:
        raise _FormatoMudou
    return vagas, len(itens) - len(vagas)


class Wwr:
    chave: str = "wwr"
    nome: str = "We Work Remotely"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("weworkremotely.com",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return list(_FEEDS)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        url = _FEEDS[escopo]  # KeyError: escopo que `escopos` não devolveu
        pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            resposta = await http.pedir("GET", url, condicional=True)
            if resposta.status == 304:
                yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                return
            vagas, pulados = _ler(escopo, resposta.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (D45: sem chave `saude.*` com `n`
            # para isso). Trocar quando a chave existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """O feed já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A fonte não é por empresa: não há o que resolver."""
        raise ValueError(f"We Work Remotely não usa identificador: {identificador!r}")


COLETOR = Wwr()
