"""Coletor Jobicy (apêndice 2.2): API JSON pública, uma lista só, paginada por cursor.

`geo=brazil`, 100 vagas por página; a página seguinte vem de `nextCursor` enquanto `hasMore`.
A descrição já vem na lista: não há `detalhar`. Salário estruturado é pouco confiável: só entra
o que é número positivo.
"""

import json
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
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

_LIMITES = limites("jobicy")
_API = "https://jobicy.com/api/jobs"
_POR_PAGINA = "100"
_MAX_PAGINAS = 50  # só vagas dos últimos 7 dias: passar disso é lista que não acaba
_PERIODOS: Mapping[str, Periodo] = {
    "hourly": "hora",
    "daily": "dia",
    "weekly": "semana",
    "monthly": "mes",
    "yearly": "ano",
}


class _FormatoMudou(Exception):
    """A resposta não traz a lista `jobs`, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _lista(valor: object) -> tuple[str, ...]:
    """Itens de texto de uma lista da fonte (`jobIndustry`, `jobType`); outro tipo = vazio."""
    if not isinstance(valor, list):
        return ()
    return tuple(t for item in valor if (t := _texto(item)))


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _locais(valor: object) -> tuple[str, ...]:
    """`jobGeo` é texto livre ("LATAM,  USA", espaços duplos): vírgula separa, espaço se junta."""
    if not isinstance(valor, str):
        return ()
    return tuple(t for parte in valor.split(",") if (t := " ".join(parte.split())))


def _valor(valor: object) -> float | None:
    """Número positivo e finito, como a fonte mandou (inteiro continua inteiro)."""
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    # Comparar com o maior float evita converter inteiro gigante (OverflowError); nan/inf caem.
    return valor if 0 < valor <= sys.float_info.max else None


def _salario(job: dict[str, object]) -> SalarioBruto | None:
    minimo, maximo = _valor(job.get("salaryMin")), _valor(job.get("salaryMax"))
    if minimo is None and maximo is None:
        return None
    moeda = _texto(job.get("salaryCurrency")).upper()
    periodo = job.get("salaryPeriod")
    return SalarioBruto(
        moeda=moeda if len(moeda) == 3 and moeda.isascii() and moeda.isalpha() else None,
        minimo_unidades=minimo,
        maximo_unidades=maximo,
        periodo=_PERIODOS.get(periodo) if isinstance(periodo, str) else None,
    )


def _vaga(job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    titulo, empresa = _texto(job.get("jobTitle")), _texto(job.get("companyName"))
    if not titulo or not empresa:
        return None
    id_externo = job.get("id")
    try:
        return VagaColetada(
            fonte="jobicy",
            escopo="",
            url=_texto(job.get("url")),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            descricao=_texto(job.get("jobDescription")),
            id_externo=str(id_externo) if isinstance(id_externo, int | str) else None,
            locais=_locais(job.get("jobGeo")),
            contrato_declarado=", ".join(_lista(job.get("jobType"))) or None,
            salario_estruturado=_salario(job),
            publicada_em=_data_hora(job.get("pubDate")),
            etiquetas=_lista(job.get("jobIndustry")),
        )
    except ValueError:  # url fora de http/https
        return None


def _ler(dados: object) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis da página e quantas foram puladas."""
    jobs = dados.get("jobs") if isinstance(dados, dict) else None
    if not isinstance(jobs, list):
        raise _FormatoMudou
    vagas = [v for v in map(_vaga, jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    return vagas, len(jobs) - len(vagas)


def _proximo_cursor(dados: object) -> str | None:
    """O cursor da próxima página, ou `None` quando a lista acabou (`hasMore` falso)."""
    if not isinstance(dados, dict) or dados.get("hasMore") is not True:
        return None
    cursor = dados.get("nextCursor")
    return cursor if isinstance(cursor, str) and cursor else ""  # "": veio hasMore sem cursor


class Jobicy:
    chave: str = "jobicy"
    nome: str = "Jobicy"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("jobicy.com",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return [""]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        incompleta = pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal incompleta, pulados
            vistos: set[str] = set()
            cursor: str | None = None
            for n in range(_MAX_PAGINAS):
                params = {"count": _POR_PAGINA, "geo": "brazil"}
                if cursor is not None:
                    params["cursor"] = cursor
                # o validador só vale na primeira página: a URL do cursor não se repete
                resposta = await http.pedir("GET", _API, params=params, condicional=n == 0)
                if resposta.status == 304:
                    yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                    return
                try:
                    dados = json.loads(resposta.texto)
                    vagas, n_pulados = _ler(dados)
                except (ValueError, _FormatoMudou) as erro:
                    if n == 0:
                        raise _FormatoMudou from erro
                    incompleta += 1  # página ruim no meio: as boas já lidas ficam
                    return
                pulados += n_pulados
                yield vagas  # antes de qualquer teste de fim: a página lida é nova
                proximo = _proximo_cursor(dados)
                if proximo in vistos:  # a fonte repetiu o cursor: a próxima seria a mesma
                    incompleta += 1
                    return
                if proximo is None:
                    return
                if not proximo:  # hasMore sem cursor utilizável
                    incompleta += 1
                    return
                vistos.add(proximo)
                cursor = proximo
            incompleta += 1  # passou do teto de páginas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if (pulados or incompleta) and resultado.estado == "ok":
            # shortcut: a contagem não vai no motivo (não há chave `saude.*` com `n` para isso;
            # D45). Trocar quando a chave existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A Jobicy é uma lista só, sem empresa nem identificador a resolver."""
        raise ValueError(f"a Jobicy não tem identificador: {identificador!r}")


COLETOR = Jobicy()
