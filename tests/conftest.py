"""Guarda de rede: nenhum teste fala com fora (desenho 9.4, DR-21).

Também para o laço da versão (T85) nos testes que sobem o lifespan do `serve`.
"""

import asyncio
import socket
from collections.abc import Iterator
from typing import Any

import pytest

from jobot.cli import servir

_LOCAIS = {"127.0.0.1", "::1"}


def _confere(endereco: Any) -> None:
    host = endereco[0] if isinstance(endereco, tuple) else endereco
    if host not in _LOCAIS:
        raise RuntimeError(f"rede bloqueada nos testes: {endereco!r}")


@pytest.fixture(autouse=True)
def _guarda_de_rede(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex
    getaddrinfo = socket.getaddrinfo

    def connect_guardado(self: socket.socket, endereco: Any) -> None:
        _confere(endereco)
        connect(self, endereco)

    def connect_ex_guardado(self: socket.socket, endereco: Any) -> int:
        _confere(endereco)
        return connect_ex(self, endereco)

    def getaddrinfo_guardado(host: Any, *args: Any, **kwargs: Any) -> Any:
        _confere(host)  # sem DNS nos testes (D41): só os endereços locais resolvem
        return getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect_guardado)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex_guardado)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo_guardado)
    yield


@pytest.fixture(autouse=True)
def _laco_versao_parado(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `RelogioFalso` volta do `dormir` sem soltar o laço de eventos: o laço da versão, que só
    dorme e checa, giraria sem parar no mesmo relógio da agenda. Fica parado; quem testa o laço
    no lifespan (`test_servir_versao.py`) o troca de novo pelo seu falso."""

    async def parado(*_: object) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "laco_versao", parado)
