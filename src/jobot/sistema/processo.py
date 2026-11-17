"""Processo filho destacado do joBot e o seu encerramento, no POSIX e no Windows."""

import os
import signal
import sys
from typing import Any, Protocol

# Valores da API do Windows; o `subprocess` só os define lá.
_CREATE_NEW_PROCESS_GROUP = 0x200
_DETACHED_PROCESS = 0x8


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
    """POSIX: sinal ao grupo inteiro. Windows: `terminate`/`kill` no próprio processo."""
    if plataforma == "win32":
        # ponytail: no Windows os netos não saem junto; job object se algum ficar para trás
        if forcar:
            proc.kill()
        else:
            proc.terminate()
        return
    os.killpg(proc.pid, signal.SIGKILL if forcar else signal.SIGTERM)
