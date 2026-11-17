"""`Ouvidas.prontas` não espera para sempre um corpo em fluxo (T242)."""

import asyncio
from collections.abc import Callable
from typing import Any, cast

import pytest
from playwright.async_api import Page, Response

from jobot.navegador import limites
from jobot.navegador.pagina import ouvir_respostas

pytestmark = pytest.mark.anyio

HOSTS = ("www.exemplo.test",)


class _PaginaFalsa:
    def __init__(self) -> None:
        self.ouvintes: dict[str, Callable[[Any], None]] = {}

    def on(self, evento: str, ouvinte: Callable[[Any], None]) -> None:
        self.ouvintes[evento] = ouvinte


class _RespostaFalsa:
    def __init__(self, caminho: str, corpo: bytes | None) -> None:
        self.url = f"https://www.exemplo.test{caminho}"
        self.status = 200
        self.headers = {"content-type": "application/json"}
        self._corpo = corpo  # None: resposta em fluxo, o corpo nunca termina
        self.cancelada = False

    async def body(self) -> bytes:
        if self._corpo is not None:
            return self._corpo
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelada = True
            raise
        raise AssertionError("inalcançável")


async def test_prontas_desiste_do_corpo_preso_e_guarda_o_que_terminou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "PRAZO_CORPOS_S", 0.05)
    pagina = _PaginaFalsa()
    ouvidas = ouvir_respostas(cast(Page, pagina), HOSTS, None)
    boa = _RespostaFalsa("/boa", b"{}")
    presa = _RespostaFalsa("/presa", None)
    for resposta in (boa, presa):
        pagina.ouvintes["response"](cast(Response, resposta))
    tarefa = asyncio.create_task(ouvidas.prontas())
    feitas, _ = await asyncio.wait({tarefa}, timeout=2)
    if not feitas:
        tarefa.cancel()
    assert feitas, "prontas() não respeitou PRAZO_CORPOS_S"
    await tarefa
    assert [r.url for r in ouvidas] == [boa.url]
    assert not ouvidas._lendo
    await asyncio.sleep(0)  # a tarefa cancelada termina de sair
    assert presa.cancelada
