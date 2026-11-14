"""Guarda de rede: nenhum teste fala com fora (desenho 9.4, DR-21).

O fixture `laco_versao_parado` (T85, T104) é pedido só pelas suítes que sobem o lifespan.
"""

import asyncio
import socket
from collections.abc import Iterator
from typing import Any

import pytest

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


@pytest.fixture
def laco_versao_parado(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `RelogioFalso` volta do `dormir` sem soltar o laço de eventos: o laço da versão, que só
    dorme e checa, giraria sem parar no mesmo relógio da agenda. Fica parado. Pedir com
    `pytestmark = pytest.mark.usefixtures("laco_versao_parado")` na suíte que sobe o lifespan;
    quem testa o laço (`test_servir_versao.py`) o troca pelo seu falso."""
    from jobot.cli import servir  # só aqui: a raiz não importa o `servir` para todo teste

    async def parado(*_: object) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "laco_versao", parado)
