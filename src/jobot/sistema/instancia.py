"""Instância única: `jobot.lock` travado guarda o PID e a porta do servidor (desenho 12.3).

Linux e Mac travam com `fcntl.flock`; Windows com `msvcrt.locking` num byte longe dos dados
(a trava do Windows é obrigatória: no mesmo byte dos dados, ninguém mais os leria).
"""

import contextlib
import os
import sys
from collections.abc import Mapping
from pathlib import Path

PORTA_PADRAO = 47615
_MODO = 0o600
# O_NOFOLLOW: o lock nunca segue symlink para fora da pasta de dados (não existe no Windows).
# O_BINARY: no Windows, sem ele o "\n" viraria "\r\n" e o formato mudaria.
_FLAGS = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_BINARY", 0)

if sys.platform == "win32":
    import msvcrt

    _BYTE_DA_TRAVA = 1 << 20  # além do fim dos dados: travar depois do fim do arquivo vale

    def _prender(fd: int, *, compartilhada: bool) -> bool:
        # o Windows não tem trava compartilhada: a leitura prende e solta na hora
        os.lseek(fd, _BYTE_DA_TRAVA, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _desprender(fd: int) -> None:
        os.lseek(fd, _BYTE_DA_TRAVA, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _prender(fd: int, *, compartilhada: bool) -> bool:
        modo = fcntl.LOCK_SH if compartilhada else fcntl.LOCK_EX
        try:
            fcntl.flock(fd, modo | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _desprender(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _fechar(fd: int) -> None:
    """Solta a trava e fecha; no Windows, fechar sem soltar deixa a trava presa por um tempo."""
    with contextlib.suppress(OSError):
        _desprender(fd)
    os.close(fd)


def _abrir(dados: Path, flags: int) -> int:
    return os.open(dados / "jobot.lock", flags | _FLAGS, _MODO)


def _gravar(fd: int, dados: bytes) -> None:
    if hasattr(os, "pwrite"):
        os.pwrite(fd, dados, 0)
    else:  # Windows
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, dados)


def _ler(fd: int) -> bytes:
    if hasattr(os, "pread"):
        return os.pread(fd, 64, 0)
    os.lseek(fd, 0, os.SEEK_SET)  # Windows
    return os.read(fd, 64)


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
        if not _prender(fd, compartilhada=False):
            os.close(fd)
            return False
        try:
            os.fchmod(fd, _MODO)
            os.ftruncate(fd, 0)
            _gravar(fd, f"{os.getpid()}\n{self._porta}\n".encode())
        except BaseException:
            _fechar(fd)  # sem isso a trava ficaria presa por um descritor sem dono
            raise
        self._fd = fd
        return True

    def soltar(self) -> None:
        if self._fd is not None:
            _fechar(self._fd)
            self._fd = None


def _linhas_da_trava(dados: Path) -> list[str] | None:
    """Linhas do `jobot.lock`, só se alguém prende a trava agora. Trava solta guarda dado velho."""
    try:
        fd = _abrir(dados, os.O_RDONLY)
    except OSError:
        return None
    try:
        if _prender(fd, compartilhada=True):
            return None  # ninguém prende a trava
        texto = _ler(fd).decode("ascii", "replace")
    finally:
        _fechar(fd)
    return texto.split("\n")


def _inteiro_positivo(texto: str) -> int:
    return int(texto) if texto.isascii() and texto.isdigit() else 0


def pid_e_porta_do_servidor(dados: Path) -> tuple[int | None, int | None]:
    """PID e porta do servidor numa só leitura da trava; trava solta ou estragada: None."""
    linhas = _linhas_da_trava(dados)
    pid = _inteiro_positivo(linhas[0]) if linhas else 0
    p = _inteiro_positivo(linhas[1]) if linhas and len(linhas) > 1 else 0
    return (pid if pid > 0 else None), (p if 1 <= p <= 65535 else None)


def pid_do_servidor(dados: Path) -> int | None:
    """PID do servidor, só se alguém prende a trava agora. PID de trava solta é velho: None."""
    return pid_e_porta_do_servidor(dados)[0]


def porta_do_servidor(dados: Path) -> int | None:
    """Porta gravada pelo servidor na trava presa (de 1 a 65535); estragada ou solta: None."""
    return pid_e_porta_do_servidor(dados)[1]


def porta(env: Mapping[str, str]) -> int:
    """`JOBOT_PORTA` quando é um número de 1 a 65535; senão 47615."""
    valor = env.get("JOBOT_PORTA", "").strip()
    if valor.isascii() and valor.isdigit() and 1 <= int(valor) <= 65535:
        return int(valor)
    return PORTA_PADRAO


AVISO_CAPTURA = (
    "Uma captura de exemplos com login está em andamento. "
    "Encerre-a no terminal dela e tente de novo."
)


def captura_em_andamento(dados: Path) -> bool:
    """Trava presa sem porta: quem a prende é o `capturar_logado.py` (`Trava(dados, 0)`)."""
    pid, p = pid_e_porta_do_servidor(dados)  # uma só leitura da trava
    return pid is not None and p is None
