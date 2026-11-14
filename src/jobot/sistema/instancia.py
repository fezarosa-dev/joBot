"""Instância única: `jobot.lock` com flock guarda o PID e a porta do servidor (desenho 12.3)."""

import fcntl
import os
from collections.abc import Mapping
from pathlib import Path

PORTA_PADRAO = 47615
_MODO = 0o600


def _abrir(dados: Path, flags: int) -> int:
    # O_NOFOLLOW: o lock nunca segue symlink para fora da pasta de dados
    return os.open(dados / "jobot.lock", flags | os.O_NOFOLLOW | os.O_CLOEXEC, _MODO)


class Trava:
    def __init__(self, dados: Path, porta: int) -> None:
        self._dados = dados
        self._porta = porta
        self._fd: int | None = None

    def pegar(self) -> bool:
        """True se esta instância passou a ser a dona; False se outra já prende a trava."""
        if self._fd is not None:
            return True
        fd = _abrir(self._dados, os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        os.fchmod(fd, _MODO)
        os.ftruncate(fd, 0)
        os.pwrite(fd, f"{os.getpid()}\n{self._porta}\n".encode(), 0)
        self._fd = fd
        return True

    def soltar(self) -> None:
        if self._fd is not None:
            os.close(self._fd)  # fechar o descritor solta o flock
            self._fd = None


def _linhas_da_trava(dados: Path) -> list[str] | None:
    """Linhas do `jobot.lock`, só se alguém prende a trava agora. Trava solta guarda dado velho."""
    try:
        fd = _abrir(dados, os.O_RDONLY)
    except OSError:
        return None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            texto = os.pread(fd, 64, 0).decode("ascii", "replace")
        else:
            return None  # ninguém prende a trava
    finally:
        os.close(fd)  # fechar também solta o flock compartilhado
    return texto.split("\n")


def _inteiro_positivo(texto: str) -> int:
    return int(texto) if texto.isascii() and texto.isdigit() else 0


def pid_do_servidor(dados: Path) -> int | None:
    """PID do servidor, só se alguém prende a trava agora. PID de trava solta é velho: None."""
    linhas = _linhas_da_trava(dados)
    pid = _inteiro_positivo(linhas[0]) if linhas else 0
    return pid if pid > 0 else None


def porta_do_servidor(dados: Path) -> int | None:
    """Porta gravada pelo servidor na trava presa (de 1 a 65535); estragada ou solta: None."""
    linhas = _linhas_da_trava(dados)
    p = _inteiro_positivo(linhas[1]) if linhas and len(linhas) > 1 else 0
    return p if 1 <= p <= 65535 else None


def porta(env: Mapping[str, str]) -> int:
    """`JOBOT_PORTA` quando é um número de 1 a 65535; senão 47615."""
    valor = env.get("JOBOT_PORTA", "").strip()
    if valor.isascii() and valor.isdigit() and 1 <= int(valor) <= 65535:
        return int(valor)
    return PORTA_PADRAO
