"""Processo filho destacado do joBot e o seu encerramento, no POSIX e no Windows."""

import contextlib
import os
import signal
import subprocess
import sys
from typing import Any, Protocol

# Valores da API do Windows; o `subprocess` só os define lá.
_CREATE_NEW_PROCESS_GROUP = 0x200
_DETACHED_PROCESS = 0x8
# CREATE_NO_WINDOW: o `taskkill` chamado do `pythonw` não pisca um console.
_SEM_JANELA: dict[str, Any] = {"creationflags": 0x08000000} if sys.platform == "win32" else {}


class Processo(Protocol):
    @property
    def pid(self) -> int: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...


def destacar(plataforma: str = sys.platform) -> dict[str, Any]:
    """Argumentos do `Popen`/`create_subprocess_exec` para o filho viver num grupo próprio."""
    if plataforma == "win32":
        return {"creationflags": _CREATE_NEW_PROCESS_GROUP | _DETACHED_PROCESS}
    return {"start_new_session": True}


def encerrar_grupo(proc: Processo, *, forcar: bool = False, plataforma: str = sys.platform) -> None:
    """POSIX: sinal ao grupo inteiro. Windows: `taskkill /T /F` na árvore (os netos não saem
    com o líder); sem ele (`taskkill` ausente ou falhou), `terminate`/`kill` no processo.
    No Windows, processo já encerrado não recebe nada: sem a alça, o PID pode ser de outro."""
    if plataforma == "win32":
        if getattr(proc, "returncode", None) is not None:
            return
        args = ["taskkill", "/T", "/F", "/PID", str(proc.pid)]
        feito = subprocess.run(args, capture_output=True, check=False, **_SEM_JANELA)
        if feito.returncode == 0:
            return
        if forcar:
            proc.kill()
        else:
            proc.terminate()
        return
    os.killpg(proc.pid, signal.SIGKILL if forcar else signal.SIGTERM)


def encerrar_arvore(proc: subprocess.Popen[Any], espera: float = 15.0) -> None:
    """Encerra um filho aberto em sessão própria e tudo o que ele subiu: SIGTERM ao grupo, que o
    `jobot ferramentas baixar navegador` pega para encerrar o `playwright install` (que vive em
    outra sessão, fora do grupo); depois de `espera` s, SIGKILL ao que sobrou no grupo. No
    Windows, `encerrar_grupo` já é o `taskkill /T /F` da árvore. Espera o filho sair."""
    with contextlib.suppress(ProcessLookupError):
        encerrar_grupo(proc)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.communicate(timeout=espera)
    with contextlib.suppress(ProcessLookupError):
        encerrar_grupo(proc, forcar=True)
    proc.communicate()
