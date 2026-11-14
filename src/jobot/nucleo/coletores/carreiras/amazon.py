"""Coletor Amazon Jobs (apêndice 3.4): busca JSON do site, um escopo por país.

O escopo é o país em ISO de duas letras maiúsculas (`"BR"`); a API pede o código de três
(`BRA`). A lista traz a descrição e as qualificações: não há `detalhar`. Endereço não oficial,
sem limite publicado: 2 s entre pedidos (`fontes.json`) e teto de páginas, não de pedidos.
"""

import json
import re
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

_LIMITES = limites("amazon")
_SITE = "https://www.amazon.jobs"
_API = f"{_SITE}/en/search.json"
_LIMIT = 100  # a API recusa mais que 100 ("Result limit cannot be greater than 100")
# shortcut: teto de 30 páginas (3000 vagas) por país, para o escopo nunca virar laço sem fim se
# `hits` mentir; passa disso vira "parcial" com `saude.limite_atingido`. Subir se um país passar.
MAX_PAGINAS = 30
# shortcut: só os países de `tratamento/locais.py`; país fora da tabela não vira escopo. Acrescentar
# o par ISO de 2 e 3 letras quando uma busca pedir outro país.
_ISO3 = {
    "BR": "BRA", "PT": "PRT", "US": "USA", "GB": "GBR", "CA": "CAN", "DE": "DEU", "ES": "ESP",
    "FR": "FRA", "IT": "ITA", "NL": "NLD", "IE": "IRL", "AR": "ARG", "CL": "CHL", "CO": "COL",
    "MX": "MEX", "UY": "URY", "PE": "PER", "IN": "IND",
}  # fmt: skip
_CAMINHO = re.compile(r"/(?!/)[\w.~%/-]+")
_DATA = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})")
_MESES = {
    m: i
    for i, m in enumerate(
        (
            "january february march april may june july august september october november december"
        ).split(),
        start=1,
    )
}


class _FormatoMudou(Exception):
    """A resposta não traz `jobs` e `hits`, traz `error`, ou nenhuma vaga da página é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _inteiro(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _data(valor: object) -> datetime | None:
    """`posted_date` vem em inglês por extenso ("November 13, 2026"); sem hora, vale 00:00 UTC."""
    achado = _DATA.fullmatch(_texto(valor))
    mes = _MESES.get(achado.group(1).lower()) if achado else None
    if achado is None or mes is None:
        return None
    try:
        return datetime(int(achado.group(3)), mes, int(achado.group(2)), tzinfo=UTC)
    except ValueError:  # "February 30"
        return None


def _locations(valor: object) -> list[dict[str, object]]:
    """Cada item de `locations[]` é um texto JSON: o que não for objeto JSON é descartado."""
    achados: list[dict[str, object]] = []
    for bruto in valor if isinstance(valor, list) else ():
        try:
            item = json.loads(bruto) if isinstance(bruto, str) else None
        except ValueError:
            continue
        if isinstance(item, dict):
            achados.append(item)
    return achados


def _local(item: dict[str, object]) -> str:
    cidade = _texto(item.get("normalizedCityName")) or _texto(item.get("city"))
    return ", ".join(
        p
        for p in (cidade, _texto(item.get("region")), _texto(item.get("normalizedCountryName")))
        if p
    )


def _vaga(escopo: str, job: object) -> VagaColetada | None:
    """Uma vaga da página, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    bruto = job.get("id_icims")
    id_vaga = str(bruto) if isinstance(bruto, int | str) and not isinstance(bruto, bool) else ""
    caminho = _texto(job.get("job_path"))
    titulo, empresa = _texto(job.get("title")), _texto(job.get("company_name"))
    if not id_vaga.strip() or not titulo or not empresa or not _CAMINHO.fullmatch(caminho):
        return None
    locais = _locations(job.get("locations"))
    tipos = {t.lower() for item in locais if (t := _texto(item.get("type")))}
    partes = (
        job.get(c) for c in ("description", "basic_qualifications", "preferred_qualifications")
    )
    try:
        return VagaColetada(
            fonte="amazon",
            escopo=escopo,
            url=f"{_SITE}{caminho}",  # host fixo: o caminho da resposta nunca troca o host
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            descricao="<br/><br/>".join(t for p in partes if (t := _texto(p))),
            id_externo=id_vaga.strip(),
            locais=tuple(dict.fromkeys(t for item in locais if (t := _local(item)))),
            # type é ONSITE ou VIRTUAL; vagas com tipos mistos não declaram modalidade
            modalidade_declarada=next(iter(tipos)).upper() if len(tipos) == 1 else None,
            contrato_declarado=_texto(job.get("job_schedule_type")) or None,
            publicada_em=_data(job.get("posted_date")),
            etiquetas=tuple(t for c in ("job_category", "job_family") if (t := _texto(job.get(c)))),
        )
    except ValueError:
        return None


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, int]:
    """As vagas legíveis, quantas foram puladas e o `hits`."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    if not isinstance(dados, dict) or dados.get("error"):
        raise _FormatoMudou
    jobs, hits = dados.get("jobs"), _inteiro(dados.get("hits"))
    if not isinstance(jobs, list) or hits is None:
        raise _FormatoMudou
    vagas = [v for v in (_vaga(escopo, j) for j in jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    return vagas, len(jobs) - len(vagas), hits


class Amazon:
    chave: str = "amazon"
    nome: str = "Amazon"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("www.amazon.jobs",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        paises = [p.strip().upper() for p in ctx.paises] or ["BR"]
        return [p for p in dict.fromkeys(paises) if p in _ISO3]  # A21: sem país, Brasil

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        if escopo not in _ISO3:
            raise ValueError(f"escopo inválido: {escopo!r}")
        pulados = lidas = declarado = 0
        quebrou = truncada = False

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, lidas, declarado, quebrou, truncada
            for numero in range(MAX_PAGINAS):
                params = {
                    "normalized_country_code[]": _ISO3[escopo],
                    "result_limit": str(_LIMIT),
                    "offset": str(numero * _LIMIT),
                    "sort": "recent",
                }
                resposta = await http.pedir("GET", _API, params=params, condicional=True)
                if resposta.status == 304:
                    yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                    return
                try:
                    vagas, ruins, hits = _ler(escopo, resposta.texto)
                except _FormatoMudou:
                    if numero == 0:
                        raise
                    quebrou = True  # as páginas já lidas valem: "parcial", não "falhou"
                    return
                pulados += ruins
                declarado = max(declarado, hits)  # página vazia no fim traz hits 0
                yield vagas
                lidas += len(vagas) + ruins
                if len(vagas) + ruins == 0 or lidas >= hits:
                    return
            truncada = True

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if resultado.estado != "ok":
            return resultado
        # shortcut: a contagem de pulados não vai no motivo (não há chave `saude.*` com `n`; D45).
        if pulados or quebrou:
            motivo = "saude.formato_mudou"
        elif truncada:
            motivo = "saude.limite_atingido"
        elif lidas < declarado:
            motivo = "saude.listagem_incompleta"
        else:
            return resultado
        return ResultadoEscopo(resultado.vagas, "parcial", motivo, resultado.pedidos)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A Amazon busca por país, não por empresa: não há identificador a resolver."""
        raise ValueError("amazon não tem identificador de empresa")


COLETOR = Amazon()
