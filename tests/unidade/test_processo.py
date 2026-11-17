import os
import signal
import sys

import pytest

from jobot.sistema import processo


class _Proc:
    pid = 4242

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def terminate(self) -> None:
        self.chamadas.append("terminate")

    def kill(self) -> None:
        self.chamadas.append("kill")


def test_destacar_posix_abre_sessao_nova() -> None:
    assert processo.destacar("linux") == {"start_new_session": True}
    assert processo.destacar("darwin") == {"start_new_session": True}


def test_destacar_windows_usa_grupo_novo_e_desligado() -> None:
    # CREATE_NEW_PROCESS_GROUP (0x200) | DETACHED_PROCESS (0x8), valores da API do Windows
    assert processo.destacar("win32") == {"creationflags": 0x200 | 0x8}


@pytest.mark.skipif(sys.platform == "win32", reason="killpg e SIGKILL só existem no POSIX")
@pytest.mark.parametrize(
    ("forcar", "sinal"), [(False, signal.SIGTERM), (True, getattr(signal, "SIGKILL", 9))]
)
def test_encerrar_grupo_posix_manda_sinal_ao_grupo(
    monkeypatch: pytest.MonkeyPatch, forcar: bool, sinal: int
) -> None:
    enviados: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pid, s: enviados.append((pid, s)), raising=False)
    proc = _Proc()
    processo.encerrar_grupo(proc, forcar=forcar, plataforma="linux")
    assert enviados == [(4242, sinal)]
    assert proc.chamadas == []


@pytest.mark.parametrize(("forcar", "metodo"), [(False, "terminate"), (True, "kill")])
def test_encerrar_grupo_windows_usa_o_processo(
    monkeypatch: pytest.MonkeyPatch, forcar: bool, metodo: str
) -> None:
    enviados: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pid, s: enviados.append((pid, s)), raising=False)
    proc = _Proc()
    processo.encerrar_grupo(proc, forcar=forcar, plataforma="win32")
    assert proc.chamadas == [metodo]
    assert enviados == []
