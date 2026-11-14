"""Coletor Himalayas (apêndice 2.2): API JSON de busca, um escopo por cargo e país das buscas.

O escopo é `"<país>|<cargo>"` (país ISO de duas letras, vazio sem país). A lista vem em páginas de
20, com a descrição: não há `detalhar`. O orçamento de 30 pedidos é do `HttpEducado` do escopo.
"""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
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
from jobot.nucleo.modelo import Periodo, SalarioBruto, VagaColetada

_LIMITES = limites("himalayas")
_BUSCA = "https://himalayas.app/jobs/api/search"
_PERIODOS: dict[str, Periodo] = {
    "hourly": "hora",
    "daily": "dia",
    "weekly": "semana",
    "monthly": "mes",
    "annual": "ano",
}


class _FormatoMudou(Exception):
    """A resposta não traz `jobs` e `totalCount`, ou nenhuma vaga da página é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _lista(valor: object) -> tuple[str, ...]:
    return tuple(t for v in valor if (t := _texto(v))) if isinstance(valor, list) else ()


def _numero(valor: object) -> int | float | None:
    ok = isinstance(valor, int | float) and not isinstance(valor, bool) and valor > 0
    return valor if ok else None  # type: ignore[return-value]


def _epoch(valor: object) -> datetime | None:
    """`pubDate` e `expiryDate` chegam em segundos (nunca milissegundos)."""
    if not isinstance(valor, int | float) or isinstance(valor, bool):
        return None
    try:
        return datetime.fromtimestamp(valor, UTC)
    except OverflowError, OSError, ValueError:
        return None


def _salario(job: dict[str, object]) -> SalarioBruto | None:
    minimo, maximo = _numero(job.get("minSalary")), _numero(job.get("maxSalary"))
    if minimo is None and maximo is None:
        return None
    return SalarioBruto(
        moeda=_texto(job.get("currency")) or None,
        minimo_unidades=minimo,
        maximo_unidades=maximo,
        periodo=_PERIODOS.get(_texto(job.get("salaryPeriod"))),
    )


def _vaga(escopo: str, job: object) -> VagaColetada | None:
    """Uma vaga da página, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    guid, titulo, empresa = (
        _texto(job.get("guid")),
        _texto(job.get("title")),
        _texto(job.get("companyName")),
    )
    if not guid or not titulo or not empresa:
        return None
    prazo = _epoch(job.get("expiryDate"))
    try:
        return VagaColetada(
            fonte="himalayas",
            escopo=escopo,
            url=guid,
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            descricao=_texto(job.get("description")),
            id_externo=guid,
            # sem nenhuma mudança: a Himalayas manda usar o link como veio (termos, cláusula 113)
            url_candidatura=_texto(job.get("applicationLink")) or None,
            locais=_lista(job.get("locationRestrictions")),
            modalidade_declarada="remote",  # a Himalayas só lista vagas remotas
            contrato_declarado=_texto(job.get("employmentType")) or None,
            salario_estruturado=_salario(job),
            publicada_em=_epoch(job.get("pubDate")),
            # shortcut: o dia é o do UTC; em Brasília a vaga que vence à noite aparece um dia
            # antes. Trocar junto com a D45 (prazo do Greenhouse) se o dono mandar o dia local.
            prazo=prazo.date() if prazo is not None else None,
            etiquetas=_lista(job.get("seniority")),
        )
    except ValueError:  # guid ou applicationLink fora de http/https
        return None


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, int]:
    """As vagas legíveis, quantas foram puladas e o `totalCount`."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    jobs = dados.get("jobs") if isinstance(dados, dict) else None
    total = dados.get("totalCount") if isinstance(dados, dict) else None
    if not isinstance(jobs, list) or not isinstance(total, int) or isinstance(total, bool):
        raise _FormatoMudou
    vagas = [v for v in (_vaga(escopo, j) for j in jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    return vagas, len(jobs), total


class Himalayas:
    chave: str = "himalayas"
    nome: str = "Himalayas"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("himalayas.app",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        cargos = [c for t in ctx.termos if (c := t.strip())]
        return list(dict.fromkeys(f"{p}|{c}" for p in (ctx.paises or [""]) for c in cargos))

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pais, separador, cargo = escopo.partition("|")
        if not separador:
            pais, cargo = "", escopo
        pulados = 0
        quebrou = False

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, quebrou
            lidas = 0
            numero = 1
            while True:
                params = {"q": cargo, "sort": "recent", "page": str(numero)}
                if pais:
                    params = {"q": cargo, "country": pais} | params
                resposta = await http.pedir("GET", _BUSCA, params=params, condicional=True)
                if resposta.status == 304:
                    yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                    return
                try:
                    vagas, n_jobs, total = _ler(escopo, resposta.texto)
                except _FormatoMudou:
                    if numero == 1:
                        raise
                    quebrou = True  # as páginas já lidas valem: "parcial", não "falhou"
                    return
                pulados += n_jobs - len(vagas)
                yield vagas
                lidas += n_jobs
                if n_jobs == 0 or lidas >= total:
                    return
                numero += 1

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if (pulados or quebrou) and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (não há chave `saude.*` com `n`
            # para isso; ver D45, igual ao Greenhouse). Trocar quando a chave existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A Himalayas busca por cargo e país, não por empresa: não há identificador a resolver."""
        raise ValueError("himalayas não tem identificador de empresa")


COLETOR = Himalayas()
