"""Guarda de rede: nenhum teste fala com fora (desenho 9.4, DR-21)."""

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
