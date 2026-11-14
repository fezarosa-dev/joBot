"""Tarefa da checagem de versão no lifespan do `serve` (plano T85; D31).

O laço da agenda e o da versão são trocados por falsos pelo nome importado em `cli/servir.py`.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from jobot.cli import servir
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.relogio import Relogio

PORTA = 47998
BASE = f"http://127.0.0.1:{PORTA}"
AGORA = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def _esperar(condicao: Callable[[], bool], s: float = 5.0) -> bool:
    fim = time.monotonic() + s
    while not condicao():
        if time.monotonic() >= fim:
            return False
        time.sleep(0.01)
    return True


def test_servir_inicia_a_tarefa_da_versao_e_a_cancela_ao_sair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recebidos: list[tuple[object, object, object]] = []
    canceladas: list[str] = []

    async def laco_falso(
        tarefas: Mapping[str, Callable[[], Awaitable[None]]],
        estado: object,
        relogio: Relogio,
        *,
        travas: Mapping[str, asyncio.Lock] | None = None,
    ) -> None:
        await asyncio.Event().wait()

    async def laco_versao_falso(banco: Path, cliente: ClienteEducado, relogio: Relogio) -> None:
        recebidos.append((banco, cliente, relogio))
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            canceladas.append("versao")
            raise

    monkeypatch.setattr(servir, "laco", laco_falso)
    monkeypatch.setattr(servir, "laco_versao", laco_versao_falso)
    relogio = RelogioFalso(AGORA)
    app, _ = servir.montar(tmp_path, PORTA, relogio=relogio)
    with TestClient(app, base_url=BASE):
        assert _esperar(lambda: bool(recebidos)), "a tarefa da versão não subiu"
        assert canceladas == []
        banco, cliente, recebido = recebidos[0]
        # recebe o caminho e abre a sua conexão: nada dividido com o laço da agenda
        assert banco == tmp_path / "jobot.db"
        assert isinstance(banco, Path)
        assert cliente is app.state.cliente
        assert recebido is relogio
    assert canceladas == ["versao"]
