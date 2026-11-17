import errno
import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from jobot.sistema import instancia, processo
from jobot.sistema.instancia import (
    Trava,
    pid_do_servidor,
    pid_e_porta_do_servidor,
    porta,
    porta_do_servidor,
)

_SO_POSIX = pytest.mark.skipif(sys.platform == "win32", reason="modo, symlink e /proc do POSIX")


def test_segunda_instancia_nao_pega_a_trava(tmp_path: Path) -> None:
    primeira = Trava(tmp_path, 47615)
    segunda = Trava(tmp_path, 47615)
    assert primeira.pegar() is True
    assert segunda.pegar() is False
    primeira.soltar()
    assert segunda.pegar() is True  # solta a trava, a outra pega
    segunda.soltar()


@_SO_POSIX
def test_trava_guarda_pid_e_porta_com_modo_0600(tmp_path: Path) -> None:
    trava = Trava(tmp_path, 50000)
    assert trava.pegar() is True
    arquivo = tmp_path / "jobot.lock"
    assert arquivo.read_text() == f"{os.getpid()}\n50000\n"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    trava.soltar()


def test_pid_do_servidor_so_vale_com_a_trava_presa(tmp_path: Path) -> None:
    assert pid_do_servidor(tmp_path) is None  # sem arquivo
    trava = Trava(tmp_path, 47615)
    assert trava.pegar() is True
    assert pid_do_servidor(tmp_path) == os.getpid()
    trava.soltar()
    # o arquivo ainda guarda o PID, mas ninguém prende a trava: PID velho
    assert (tmp_path / "jobot.lock").read_text().startswith(str(os.getpid()))
    assert pid_do_servidor(tmp_path) is None


def test_pid_do_servidor_ignora_conteudo_estragado(tmp_path: Path) -> None:
    arquivo = tmp_path / "jobot.lock"
    trava = Trava(tmp_path, 47615)
    assert trava.pegar() is True
    for lixo in ("", "abc\n1\n", "0\n1\n", "-5\n1\n"):
        arquivo.write_text(lixo)
        assert pid_do_servidor(tmp_path) is None
    trava.soltar()


def test_porta_do_servidor_so_vale_com_a_trava_presa(tmp_path: Path) -> None:
    assert porta_do_servidor(tmp_path) is None  # sem arquivo
    trava = Trava(tmp_path, 50000)
    assert trava.pegar() is True
    assert porta_do_servidor(tmp_path) == 50000
    trava.soltar()
    assert porta_do_servidor(tmp_path) is None  # porta velha de trava solta


@pytest.mark.parametrize("lixo", ["", "123\n", "123\nabc\n", "123\n0\n", "123\n70000\n"])
def test_porta_do_servidor_ignora_porta_estragada(tmp_path: Path, lixo: str) -> None:
    trava = Trava(tmp_path, 47615)
    assert trava.pegar() is True
    (tmp_path / "jobot.lock").write_text(lixo)
    assert porta_do_servidor(tmp_path) is None
    trava.soltar()


@_SO_POSIX
def test_trava_na_ponta_alheia_nao_segue_symlink(tmp_path: Path) -> None:
    alvo = tmp_path / "alheio"
    alvo.write_text("x")
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "jobot.lock").symlink_to(alvo)
    assert pid_do_servidor(pasta) is None
    with pytest.raises(OSError):
        Trava(pasta, 47615).pegar()
    assert alvo.read_text() == "x"


def test_trava_presa_por_outro_processo(tmp_path: Path) -> None:
    codigo = (
        "import os, sys, time\n"
        "from pathlib import Path\n"
        "from jobot.sistema.instancia import Trava\n"
        "assert Trava(Path(sys.argv[1]), 1234).pegar()\n"
        "print(os.getpid(), flush=True)\n"
        "time.sleep(60)\n"
    )
    filho = subprocess.Popen(
        [sys.executable, "-c", codigo, str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        **processo.destacar(),
    )
    try:
        assert filho.stdout is not None
        # No Windows o python.exe do venv é um lançador: quem pega a trava é o filho dele.
        pid = int(filho.stdout.readline())
        assert Trava(tmp_path, 47615).pegar() is False
        assert pid_do_servidor(tmp_path) == pid
    finally:
        processo.encerrar_grupo(filho, forcar=True)
        filho.wait()
    assert pid_do_servidor(tmp_path) is None  # morreu: a trava se solta sozinha


def test_porta_padrao_e_jobot_porta() -> None:
    assert porta({}) == 47615
    assert porta({"JOBOT_PORTA": "50123"}) == 50123
    assert porta({"JOBOT_PORTA": " 50123 "}) == 50123


@pytest.mark.parametrize("valor", ["", "abc", "0", "-1", "65536", "47615.5", "٤٧٦١٥"])
def test_jobot_porta_invalida_cai_no_padrao(valor: str) -> None:
    assert porta({"JOBOT_PORTA": valor}) == 47615


@_SO_POSIX
@pytest.mark.parametrize("chamada", ["fchmod", "ftruncate", "pwrite"])
def test_falha_ao_gravar_solta_a_trava_e_nao_vaza_fd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, chamada: str
) -> None:
    def quebra(*args: object) -> int:
        raise OSError(errno.EIO, "falha simulada")

    antes = len(os.listdir("/proc/self/fd"))
    trava = Trava(tmp_path, 47615)
    with monkeypatch.context() as m:
        m.setattr(os, chamada, quebra)
        with pytest.raises(OSError):
            trava.pegar()
    assert len(os.listdir("/proc/self/fd")) == antes  # nenhum descritor ficou aberto
    outra = Trava(tmp_path, 47615)
    assert outra.pegar() is True  # a trava ficou livre
    outra.soltar()
    assert trava.pegar() is True  # e a que falhou não ficou com estado pela metade
    trava.soltar()


def test_pid_e_porta_vem_juntos_da_mesma_leitura(tmp_path: Path) -> None:
    assert pid_e_porta_do_servidor(tmp_path) == (None, None)  # sem arquivo
    trava = Trava(tmp_path, 50000)
    assert trava.pegar() is True
    assert pid_e_porta_do_servidor(tmp_path) == (os.getpid(), 50000)
    (tmp_path / "jobot.lock").write_text("abc\n70000\n")
    assert pid_e_porta_do_servidor(tmp_path) == (None, None)
    trava.soltar()
    assert pid_e_porta_do_servidor(tmp_path) == (None, None)  # solta: dado velho


class _MsvcrtFalso:
    """`msvcrt.locking` de mentira: trava por (arquivo, posição), como o LockFile do Windows."""

    LK_UNLCK = 0
    LK_NBLCK = 2

    def __init__(self) -> None:
        self.presas: dict[tuple[int, int, int], int] = {}

    def locking(self, fd: int, modo: int, nbytes: int) -> None:
        st = os.fstat(fd)
        chave = (st.st_dev, st.st_ino, os.lseek(fd, 0, os.SEEK_CUR))
        assert nbytes == 1
        if modo == self.LK_NBLCK:
            if chave in self.presas:
                raise OSError(errno.EACCES, "presa")
            self.presas[chave] = fd
        elif modo == self.LK_UNLCK:
            if self.presas.get(chave) != fd:
                raise OSError(errno.EACCES, "não é dono")
            del self.presas[chave]
        else:
            raise AssertionError(f"modo inesperado {modo}")


def _instancia_no_windows(monkeypatch: pytest.MonkeyPatch, msvcrt: object) -> ModuleType:
    """Cópia nova de `instancia.py` importada como se fosse no Windows."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "msvcrt", msvcrt)
    spec = importlib.util.spec_from_file_location("_instancia_win", instancia.__file__)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_no_windows_trava_usa_msvcrt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    msvcrt = _MsvcrtFalso()
    win = _instancia_no_windows(monkeypatch, msvcrt)
    primeira = win.Trava(tmp_path, 50000)
    segunda = win.Trava(tmp_path, 50000)
    assert primeira.pegar() is True
    assert len(msvcrt.presas) == 1  # a trava é do msvcrt, não do flock
    assert segunda.pegar() is False
    assert (tmp_path / "jobot.lock").read_bytes() == f"{os.getpid()}\n50000\n".encode()
    assert win.pid_e_porta_do_servidor(tmp_path) == (os.getpid(), 50000)
    assert len(msvcrt.presas) == 1  # a leitura não deixou trava a mais
    primeira.soltar()
    assert msvcrt.presas == {}
    assert win.pid_e_porta_do_servidor(tmp_path) == (None, None)  # solta: dado velho
    assert segunda.pegar() is True
    segunda.soltar()


def test_no_windows_o_import_nao_pede_fcntl(monkeypatch: pytest.MonkeyPatch) -> None:
    fcntl_falso = ModuleType("fcntl")
    monkeypatch.setitem(sys.modules, "fcntl", fcntl_falso)
    win = _instancia_no_windows(monkeypatch, _MsvcrtFalso())
    assert fcntl_falso not in vars(win).values()
