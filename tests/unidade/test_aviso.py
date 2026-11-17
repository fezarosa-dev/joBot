"""Aviso no computador pelo `notify-send` (D132.10; desenho A8, "Aviso no computador")."""

import logging
from collections.abc import Sequence

import pytest

from jobot.sistema.aviso import avisar
from jobot.sistema.segundo_plano_linux import Resultado


class _Executor:
    def __init__(self, codigo: int = 0) -> None:
        self.codigo = codigo
        self.chamadas: list[tuple[str, ...]] = []

    def __call__(self, comando: Sequence[str]) -> Resultado:
        self.chamadas.append(tuple(comando))
        return Resultado(self.codigo, "", "erro do notify-send")


def test_aviso_usa_notify_send() -> None:
    executor = _Executor()
    avisar("joBot", "Uma frase curta.", {"HOME": "/x"}, executor)
    assert executor.chamadas == [("notify-send", "joBot", "Uma frase curta.")]


def test_aviso_no_container_passa_pelo_host() -> None:
    executor = _Executor()
    avisar("joBot", "Uma frase curta.", {"CONTAINER_ID": "caixa"}, executor)
    assert executor.chamadas == [
        ("distrobox-host-exec", "notify-send", "joBot", "Uma frase curta.")
    ]


def test_sem_notify_send_fica_quieto(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="jobot")
    executor = _Executor(127)  # o programa não existe no sistema
    avisar("joBot", "Uma frase curta.", {}, executor)
    assert len(executor.chamadas) == 1
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_notify_send_que_falha_so_vai_ao_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="jobot")
    executor = _Executor(1)
    avisar("joBot", "Uma frase curta.", {}, executor)  # não levanta
    avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert avisos == ["aviso no computador: notify-send saiu com código 1"]
