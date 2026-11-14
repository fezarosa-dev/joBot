"""Contrato do coletor (desenho 8.1, DR-70). Só biblioteca padrão e o núcleo."""

import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol
from urllib.parse import urlsplit

from jobot.nucleo.http import (
    Bloqueio,
    ErroDeRede,
    HttpEducado,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    host_local,
)
from jobot.nucleo.modelo import Empresa, VagaColetada, confere_http

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LimiteEscopo:
    intervalo_min: int | None = None
    espera_s: float | None = None
    para_no_429: bool = False


@dataclass(frozen=True)
class ContextoColeta:
    empresas: Sequence[Empresa]
    termos: Sequence[str]
    paises: Sequence[str]


@dataclass(frozen=True)
class UrlListada:
    """Item de fonte de sitemap (DR-70): só o endereço e a data; o `detalhar` cria a vaga."""

    url: str
    atualizada_em: datetime | None = None  # <lastmod>, com fuso

    def __post_init__(self) -> None:
        confere_http(self.url, "url")
        if host_local(urlsplit(self.url).hostname or ""):  # D13: a URL vem da fonte
            raise ValueError(f"url aponta para host local: {self.url!r}")
        if self.atualizada_em is not None and self.atualizada_em.utcoffset() is None:
            raise ValueError("atualizada_em precisa ter fuso")


Item = VagaColetada | UrlListada


class _SemMudanca(tuple[Item, ...]):
    """Página vazia que o coletor devolve quando a resposta foi 304 (compara por identidade)."""


# O coletor devolve exatamente este objeto, nunca cópia nem `()`: `tuple(SEM_MUDANCA)` perde o 304.
SEM_MUDANCA: tuple[Item, ...] = _SemMudanca()
Estado = Literal["ok", "sem_mudanca", "parcial", "falhou", "no_limite"]


@dataclass(frozen=True)
class ResultadoEscopo:
    vagas: tuple[Item, ...]
    estado: Estado
    motivo: str | None
    pedidos: int


@dataclass(frozen=True)
class LimitesDaFonte:
    leva: Literal["A", "B"] = "A"
    intervalo_min: int | None = None
    max_pedidos: int | None = None
    espera_s: float = 1.0
    credito_obrigatorio: bool = False
    por_escopo: Mapping[str, LimiteEscopo] = field(default_factory=dict)


class Coletor(Protocol):
    chave: str
    nome: str
    leva: Literal["A", "B"]
    hosts: tuple[str, ...]
    credito_obrigatorio: bool
    intervalo_min: int | None
    max_pedidos: int | None
    espera_s: float
    por_escopo: Mapping[str, LimiteEscopo]

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]: ...
    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo: ...
    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None: ...
    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]: ...


def _registrar(erro: Exception) -> None:
    log.warning("listagem parou: %s: %s", type(erro).__name__, erro)


async def juntar_paginas(
    http: HttpEducado, paginas: AsyncIterator[Sequence[Item]]
) -> ResultadoEscopo:
    """Soma as páginas de um escopo e traduz as exceções do `HttpEducado` em estado.

    Página `SEM_MUDANCA` = 304. Só "sem_mudanca" se todas forem 304; 304 misturado com 200
    é "parcial" com `saude.listagem_incompleta` (a lista não veio inteira, então só o que tem
    mais de 30 dias se fecha). Erro de rede ou limite sem nenhuma página lida é "falhou";
    depois de uma página é "parcial" (decisão 16). Exceção que não está na tabela
    sobe: o executor a captura e marca "falhou" com o tipo do erro. O texto do erro (Retry-After,
    URL) vai para o log: o resultado guarda só a chave `saude.*`.
    """
    vagas: list[Item] = []
    n_paginas = 0
    n_304 = 0
    estado: Estado = "ok"
    motivo: str | None = None
    try:
        async for pagina in paginas:
            n_paginas += 1
            n_304 += pagina is SEM_MUDANCA
            vagas.extend(pagina)
    except LimiteAtingido as erro:
        _registrar(erro)
        estado, motivo = "parcial" if n_paginas else "falhou", "saude.limite_atingido"
    except OrcamentoGasto:
        estado, motivo = "no_limite", "saude.orcamento"
    except Parou429 as erro:
        _registrar(erro)
        estado, motivo = "no_limite", "saude.parou_429"
    except Bloqueio as erro:
        _registrar(erro)
        estado, motivo, vagas = "falhou", "saude.bloqueio", []  # nada aproveitável
    except ErroDeRede as erro:
        _registrar(erro)
        motivo = "saude.erro_de_rede"
        if n_paginas:
            estado = "parcial"
        else:
            estado = "falhou"
    else:
        if n_paginas and n_304 == n_paginas:
            estado = "sem_mudanca"
        elif n_304:
            estado, motivo = "parcial", "saude.listagem_incompleta"
    pedidos: int = getattr(http, "pedidos", 0)  # HttpDoEscopo conta; outro HttpEducado, não
    return ResultadoEscopo(tuple(vagas), estado, motivo, pedidos)
