"""Guarda de rede do `tests/conftest.py`: sem DNS nos testes (D41, plano T88)."""

import socket

import pytest


def test_getaddrinfo_fora_de_127_e_bloqueado() -> None:
    with pytest.raises((RuntimeError, OSError)) as erro:  # OSError: o gaierror da resolução real
        socket.getaddrinfo("exemplo.invalid", 80)
    assert erro.type is RuntimeError
    assert "rede bloqueada" in str(erro.value)
    assert socket.getaddrinfo("127.0.0.1", 80)
    assert socket.getaddrinfo("::1", 80)
