import contextlib
import os
import signal
import subprocess
import sys

import pytest

from jobot.sistema import processo


class _Proc:
    pid = 4242

    def __init__(self) -> None:
        self.chamadas: list[str] = []
        self.returncode: int | None = None

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


def _taskkill(monkeypatch: pytest.MonkeyPatch, codigo: int) -> list[list[str]]:
    chamados: list[list[str]] = []

    def rodar(args: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        chamados.append(args)
        return subprocess.CompletedProcess(args, codigo)

    monkeypatch.setattr(subprocess, "run", rodar)
    return chamados


@pytest.mark.parametrize("forcar", [False, True])
def test_encerrar_grupo_windows_mata_a_arvore_com_taskkill(
    monkeypatch: pytest.MonkeyPatch, forcar: bool
) -> None:
    enviados: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pid, s: enviados.append((pid, s)), raising=False)
    chamados = _taskkill(monkeypatch, 0)
    proc = _Proc()
    processo.encerrar_grupo(proc, forcar=forcar, plataforma="win32")
    assert chamados == [["taskkill", "/T", "/F", "/PID", "4242"]]
    assert proc.chamadas == []
    assert enviados == []


@pytest.mark.parametrize(("forcar", "metodo"), [(False, "terminate"), (True, "kill")])
def test_encerrar_grupo_windows_sem_taskkill_usa_o_processo(
    monkeypatch: pytest.MonkeyPatch, forcar: bool, metodo: str
) -> None:
    _taskkill(monkeypatch, 128)
    proc = _Proc()
    processo.encerrar_grupo(proc, forcar=forcar, plataforma="win32")
    assert proc.chamadas == [metodo]


@pytest.mark.parametrize("forcar", [False, True])
def test_encerrar_grupo_windows_processo_encerrado_nao_chama_taskkill(
    monkeypatch: pytest.MonkeyPatch, forcar: bool
) -> None:
    # Sem a alça do processo morto, o PID pode já ser de outro: o taskkill /T mataria a árvore dele.
    chamados = _taskkill(monkeypatch, 0)
    proc = _Proc()
    proc.returncode = 0
    processo.encerrar_grupo(proc, forcar=forcar, plataforma="win32")
    assert chamados == []
    assert proc.chamadas == []


@pytest.mark.skipif(sys.platform != "win32", reason="prova da árvore no Windows de verdade")
def test_encerrar_grupo_windows_leva_o_neto_junto() -> None:
    import ctypes

    neto = "import time; time.sleep(120)"
    filho = (
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen([sys.executable, '-c', {neto!r}])\n"
        "print(p.pid, flush=True)\n"
        "time.sleep(120)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", filho], stdout=subprocess.PIPE, text=True, **processo.destacar()
    )
    assert proc.stdout is not None
    pid_neto = int(proc.stdout.readline())
    kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined,unused-ignore]
    alca = kernel32.OpenProcess(0x00100000, False, pid_neto)  # SYNCHRONIZE
    assert alca
    try:
        processo.encerrar_grupo(proc)
        assert proc.wait(timeout=30) is not None
        assert kernel32.WaitForSingleObject(alca, 30_000) == 0  # WAIT_OBJECT_0: o neto saiu
    finally:
        kernel32.CloseHandle(alca)


# o filho faz o que o `jobot ferramentas baixar navegador` faz: neto em sessão própria (fora do
# grupo), encerrado por ele no SIGTERM
_FILHO_COM_NETO = (
    "import signal, subprocess, sys, time\n"
    "neto = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'],"
    " start_new_session=True)\n"
    "def sair(*_):\n"
    "    neto.kill(); neto.wait(); sys.exit(0)\n"
    "signal.signal(signal.SIGTERM, sair)\n"
    "print(neto.pid, flush=True)\n"
    "time.sleep(300)\n"
)


@pytest.mark.skipif(sys.platform == "win32", reason="no Windows é o taskkill /T (teste acima)")
def test_encerrar_arvore_leva_o_neto_de_outra_sessao() -> None:
    """D183.24: SIGTERM antes do SIGKILL, senão o neto de outra sessão fica órfão."""
    proc = subprocess.Popen(
        [sys.executable, "-c", _FILHO_COM_NETO], stdout=subprocess.PIPE, text=True,
        start_new_session=True,
    )  # fmt: skip
    assert proc.stdout is not None
    neto = int(proc.stdout.readline())
    try:
        processo.encerrar_arvore(proc)
        assert proc.returncode == 0  # saiu pelo SIGTERM, não pelo SIGKILL
        with pytest.raises(ProcessLookupError):
            os.kill(neto, 0)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(neto, signal.SIGKILL)
