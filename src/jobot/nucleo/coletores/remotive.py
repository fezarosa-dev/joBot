"""Coletor Remotive (apêndice 2.2): API JSON pública, lista única, sem paginação nem `detalhar`.

A resposta traz, além de `jobs`, chaves de texto na raiz (`00-warning`, `0-legal-notice`): são
avisos legais da fonte, não vaga, e ficam de fora. Os filtros da API não mudam a resposta.
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
from jobot.nucleo.modelo import VagaColetada

_LIMITES = limites("remotive")
_URL = "https://remotive.com/api/remote-jobs"


class _FormatoMudou(Exception):
    """A resposta não traz a lista `jobs`, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _publicada_em(valor: object) -> datetime | None:
    """ISO 8601; a Remotive manda sem fuso, e sem fuso vale UTC (apêndice 2.2)."""
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida.replace(tzinfo=UTC) if lida is not None and lida.utcoffset() is None else lida


def _vaga(job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    titulo, empresa = _texto(job.get("title")), _texto(job.get("company_name"))
    if not titulo or not empresa:
        return None
    tags = job.get("tags")
    etiquetas = (
        *filter(None, [_texto(job.get("category"))]),
        *(t for x in (tags if isinstance(tags, list) else []) if (t := _texto(x))),
    )
    try:
        return VagaColetada(
            fonte="remotive",
            escopo="",
            url=_texto(job.get("url")),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            descricao=_texto(job.get("description")),
            id_externo=str(job["id"]) if isinstance(job.get("id"), int | str) else None,
            locais=tuple(filter(None, [_texto(job.get("candidate_required_location"))])),
            modalidade_declarada="remote",  # a Remotive só lista vaga remota
            contrato_declarado=_texto(job.get("job_type")) or None,
            salario_texto=_texto(job.get("salary")) or None,  # texto livre: o tratamento lê
            publicada_em=_publicada_em(job.get("publication_date")),
            etiquetas=etiquetas,
        )
    except ValueError:  # url fora de http/https
        return None


def _ler(texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis e quantas foram puladas."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    jobs = dados.get("jobs") if isinstance(dados, dict) else None
    if not isinstance(jobs, list):
        raise _FormatoMudou
    vagas = [v for v in map(_vaga, jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    return vagas, len(jobs) - len(vagas)


class Remotive:
    chave: str = "remotive"
    nome: str = "Remotive"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("remotive.com",)
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
            resposta = await http.pedir("GET", _URL, condicional=True)
            if resposta.status == 304:
                yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                return
            vagas, pulados = _ler(resposta.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (D45, opção b, como o Greenhouse).
            # Trocar quando a chave com `n` existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Fonte de escopo único: não há empresa para resolver."""
        raise ValueError(f"a Remotive não tem identificador: {identificador!r}")


COLETOR = Remotive()
