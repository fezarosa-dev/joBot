"""Coletor Eureca (apêndice 3.2): API pública do aplicativo de candidatos, escopo único.

`GET https://candidate-api.eureca.me/opportunities?page=N&pageSize=200` devolve
`{"items", "total", "page", "pageSize"}`, sem login (decisão A42). A lista já traz a descrição:
não há `detalhar`. A API não manda `ETag` nem `Last-Modified`: nada de pedido condicional.
O link da vaga sai da rota do aplicativo (`/vagas/$jobId` no JS de app.eureca.me), montado pelo
id; `/programs` lista programas (grupos de vagas), não vagas, e fica de fora.
"""

import json
import re
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import date, datetime
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
from jobot.nucleo.modelo import SalarioBruto, VagaColetada

_LIMITES = limites("eureca")
_API = "https://candidate-api.eureca.me/opportunities"
_LINK = "https://app.eureca.me/vagas/"
_TAMANHO = 200  # o padrão da API quando o pedido não diz
# shortcut: teto local de páginas (2000 vagas; hoje são 8). Ao esgotar, "parcial" com
# `saude.limite_atingido`. Trocar por `max_pedidos` em fontes.json se a fonte crescer.
MAX_PAGINAS = 10
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class _FormatoMudou(Exception):
    """A resposta não traz `items` e `total`, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _inteiro(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _instante(valor: object) -> datetime | None:
    try:
        lido = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lido if lido is not None and lido.utcoffset() is not None else None


def _prazo(valor: object) -> date | None:
    """`endApplying` é instante (`2027-01-01T02:59Z` = 23:59 de 31/12 em SP): vale o dia local."""
    fim = _instante(valor)
    return fim.astimezone().date() if fim is not None else None


def _reais(centavos: object) -> int | float | None:
    n = _inteiro(centavos)
    if n is None or not 0 < n <= sys.float_info.max:  # compara sem converter (10**400)
        return None
    # `SalarioBruto` guarda unidades (float no contrato): inteiro quando a divisão é exata
    return n // 100 if n % 100 == 0 else n / 100


def _salario(valor: object) -> SalarioBruto | None:
    """`{"display", "minCents", "maxCents"}`; "undisclosed" é salário escondido."""
    if not isinstance(valor, dict) or valor.get("display") == "undisclosed":
        return None
    minimo, maximo = _reais(valor.get("minCents")), _reais(valor.get("maxCents"))
    if minimo is None and maximo is None:
        return None
    # A Eureca só opera no Brasil e a faixa não traz período (bolsa de estágio, em geral mensal).
    return SalarioBruto(moeda="BRL", minimo_unidades=minimo, maximo_unidades=maximo)


def _vaga(job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    ident = _texto(job.get("id")).lower()
    titulo, empresa = _texto(job.get("name")), _texto(job.get("companyName"))
    if not _UUID.fullmatch(ident) or not titulo or not empresa:
        return None  # o id entra no caminho do link: só UUID
    local = ", ".join(filter(None, (_texto(job.get("cityName")), _texto(job.get("stateAcronym")))))
    modelos = job.get("workModels")
    # vários modelos (presencial e híbrido): a modalidade fica para o rotulador, pelo texto
    varios = isinstance(modelos, list) and len({_texto(m) for m in modelos} - {""}) > 1
    return VagaColetada(
        fonte="eureca",
        escopo="",
        url=_LINK + ident,
        titulo=titulo,
        empresa=empresa,
        descricao_formato="html",
        descricao=_texto(job.get("description")),
        id_externo=ident,
        locais=(local,) if local else (),
        modalidade_declarada=None if varios else _texto(job.get("workModel")) or None,
        contrato_declarado=_texto(job.get("contractTypeKey")) or None,
        salario_estruturado=_salario(job.get("salary")),
        publicada_em=_instante(job.get("publishedAt")) or _instante(job.get("createdAt")),
        prazo=_prazo(job.get("endApplying")),
    )


def _ler(texto: str) -> tuple[list[VagaColetada], int, int, int, int]:
    """(vagas, puladas, itens na página, total declarado, tamanho da página da resposta)."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    itens = dados.get("items") if isinstance(dados, dict) else None
    total = _inteiro(dados.get("total")) if isinstance(dados, dict) else None
    if not isinstance(itens, list) or total is None:
        raise _FormatoMudou
    vagas = [v for v in map(_vaga, itens) if v is not None]
    if itens and not vagas:
        raise _FormatoMudou
    tamanho = _inteiro(dados.get("pageSize"))
    tamanho = tamanho if tamanho is not None and tamanho > 0 else _TAMANHO
    return vagas, len(itens) - len(vagas), len(itens), total, tamanho


class Eureca:
    chave: str = "eureca"
    nome: str = "Eureca"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("candidate-api.eureca.me",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return [""]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = lidos = 0
        total: int | None = None
        quebrou = no_teto = False

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, lidos, total, quebrou, no_teto
            pagina = 1
            while True:
                params = {"page": str(pagina), "pageSize": str(_TAMANHO)}
                resposta = await http.pedir(
                    "GET", _API, params=params, cabecalhos={"Accept": "application/json"}
                )
                try:
                    vagas, ruins, itens, declarado, tamanho = _ler(resposta.texto)
                except _FormatoMudou:
                    if pagina == 1:
                        raise
                    quebrou = True  # as páginas já lidas ficam: "parcial"
                    return
                total = declarado if total is None else total  # o da página 1
                pulados += ruins
                lidos += len(vagas)
                yield vagas
                if itens < tamanho or pagina * tamanho >= declarado:
                    return
                if pagina >= MAX_PAGINAS:
                    no_teto = True
                    return
                pagina += 1

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if resultado.estado != "ok":
            return resultado
        motivo: str | None = None
        if quebrou or pulados:
            # shortcut: a contagem de pulados não vai no motivo (D45); trocar quando houver a chave.
            motivo = "saude.formato_mudou"
        elif no_teto:
            motivo = "saude.limite_atingido"
        elif total is not None and lidos + pulados < total:
            motivo = "saude.listagem_incompleta"  # a resposta declara mais vagas do que trouxe
        if motivo is None:
            return resultado
        return ResultadoEscopo(resultado.vagas, "parcial", motivo, resultado.pedidos)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A Eureca é uma lista só, sem empresa nem identificador a resolver."""
        raise ValueError(f"a Eureca não tem identificador: {identificador!r}")


COLETOR = Eureca()
