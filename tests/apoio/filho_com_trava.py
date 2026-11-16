"""Processo filho que prende a trava do servidor, para os testes de `abrir` e `sair`."""

import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_FILHO = (
    "import signal, sys, time\n"
    "from pathlib import Path\n"
    "from jobot.sistema.instancia import Trava\n"
    "if sys.argv[2] == 'ignora':\n"
    "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "assert Trava(Path(sys.argv[1]), 1234).pegar()\n"
    "print('pronto', flush=True)\n"
    "time.sleep(60)\n"
)


@contextmanager
def filho_com_trava(dados: Path, modo: str = "morre") -> Iterator[subprocess.Popen[str]]:
    filho = subprocess.Popen(
        [sys.executable, "-c", _FILHO, str(dados), modo],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert filho.stdout is not None
        assert filho.stdout.readline().strip() == "pronto"
        yield filho
    finally:
        filho.kill()
        filho.wait()
