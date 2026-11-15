"""O `ClienteEducado` das rotas do painel, num lugar só (plano T185).

`app.state.transporte` troca o transporte nos testes; a hora vem de `relogio_do_painel`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Request

from jobot import __version__
from jobot.nucleo.http import ClienteEducado
from jobot.painel.rotas.vagas import relogio_do_painel
from jobot.painel.sem_validadores import SemValidadores


@asynccontextmanager
async def cliente_do_painel(request: Request) -> AsyncIterator[ClienteEducado]:
    cliente = ClienteEducado(
        getattr(request.app.state, "transporte", None),
        relogio_do_painel(request),
        SemValidadores(),
        __version__,
    )
    try:
        yield cliente
    finally:
        await cliente.fechar()
