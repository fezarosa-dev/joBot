"""Coletor RemoteOK (apêndice 2.6): uma lista JSON só, escopo único, sem paginação.

O primeiro elemento da lista não é vaga (traz `last_updated` e `legal`): é pulado. A lista
já traz a descrição, então não há `detalhar`. A leitura é sempre em UTF-8, porque o
`Content-Type` da fonte vem sem `charset` e o `HttpEducado` cai para UTF-8 nesse caso.
"""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from math import isfinite
from typing import Literal

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import HttpEducado
from jobot.nucleo.modelo import SalarioBruto, VagaColetada, confere_http

_LIMITES = limites("remoteok")
_API = "https://remoteok.com/api"


class _FormatoMudou(Exception):
    """A resposta não é uma lista, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _numero(valor: object) -> float | None:
    """Número positivo e finito (a fonte usa 0 para "ausente"); texto numérico também vale."""
    if isinstance(valor, bool) or not isinstance(valor, int | float | str):
        return None
    try:
        n = float(valor)
    except ValueError:
        return None
    return n if isfinite(n) and n > 0 else None


def _salario(job: Mapping[str, object]) -> SalarioBruto | None:
    minimo, maximo = _numero(job.get("salary_min")), _numero(job.get("salary_max"))
    if minimo is None and maximo is None:
        return None
    # dólar por ano (apêndice 2.6)
    return SalarioBruto(moeda="USD", minimo_unidades=minimo, maximo_unidades=maximo, periodo="ano")


def _publicada(job: Mapping[str, object]) -> datetime | None:
    """`date` (ISO com fuso); sem ele ou sem fuso, `epoch` (segundos, inteiro ou texto)."""
    data = job.get("date")
    try:
        lida = datetime.fromisoformat(data) if isinstance(data, str) else None
    except ValueError:
        lida = None
    if lida is not None and lida.utcoffset() is not None:
        return lida
    epoch = job.get("epoch")
    if isinstance(epoch, bool) or not isinstance(epoch, int | float | str):
        return None
    try:
        return datetime.fromtimestamp(float(epoch), tz=UTC)
    except ValueError, OverflowError, OSError:  # texto sem número, ou fora do calendário
        return None


def _url_candidatura(valor: object) -> str | None:
    """`apply_url` como veio (nunca reescrita); fora de http/https, a vaga fica sem ela."""
    url = _texto(valor)
    if not url:
        return None
    try:
        confere_http(url, "url_candidatura")
    except ValueError:
        return None
    return url


def _vaga(job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    titulo, empresa = _texto(job.get("position")), _texto(job.get("company"))
    if not titulo or not empresa:
        return None
    id_externo = job.get("id")
    etiquetas = job.get("tags")
    try:
        return VagaColetada(
            fonte="remoteok",
            escopo="",
            url=_texto(job.get("url")),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            descricao=_texto(job.get("description")),
            # shortcut: a caixa do id fica como vem (D45); a fonte manda o id como texto
            id_externo=str(id_externo) if isinstance(id_externo, int | str) else None,
            url_candidatura=_url_candidatura(job.get("apply_url")),
            locais=tuple(filter(None, [_texto(job.get("location"))])),
            salario_estruturado=_salario(job),
            publicada_em=_publicada(job),
            etiquetas=tuple(
                t for e in (etiquetas if isinstance(etiquetas, list) else []) if (t := _texto(e))
            ),
        )
    except ValueError:  # url fora de http/https
        return None


def _ler(texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis e quantas foram puladas (o primeiro elemento não conta)."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    if not isinstance(dados, list) or not dados:  # sem nem o elemento `legal`: formato mudou
        raise _FormatoMudou
    jobs = dados[1:]
    vagas = [v for v in map(_vaga, jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    return vagas, len(jobs) - len(vagas)


class RemoteOK:
    chave: str = "remoteok"
    nome: str = "RemoteOK"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("remoteok.com",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return [""]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            # sem ETag nem Last-Modified na captura: nada de pedido condicional (sem 304)
            resposta = await http.pedir("GET", _API)
            vagas, pulados = _ler(resposta.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (D45, opção b); trocar quando
            # a sessão decidir a chave `saude.pulados_n`.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Fonte de lista única: não há identificador nem endereço para colar."""
        raise ValueError(f"o RemoteOK não tem endereço para colar: {identificador!r}")


COLETOR = RemoteOK()
