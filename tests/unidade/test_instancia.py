import errno
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from jobot.sistema.instancia import (
    Trava,
    pid_do_servidor,
    pid_e_porta_do_servidor,
    porta,
    porta_do_servidor,
)


def test_segunda_instancia_nao_pega_a_trava(tmp_path: Path) -> None:
    primeira = Trava(tmp_path, 47615)
    segunda = Trava(tmp_path, 47615)
    assert primeira.pegar() is True
    assert segunda.pegar() is False
    primeira.soltar()
    assert segunda.pegar() is True  # solta a trava, a outra pega
    segunda.soltar()


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
        "import sys, time\n"
        "from pathlib import Path\n"
        "from jobot.sistema.instancia import Trava\n"
        "assert Trava(Path(sys.argv[1]), 1234).pegar()\n"
        "print('pronto', flush=True)\n"
        "time.sleep(60)\n"
    )
    filho = subprocess.Popen(
        [sys.executable, "-c", codigo, str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert filho.stdout is not None
        assert filho.stdout.readline().strip() == "pronto"
        assert Trava(tmp_path, 47615).pegar() is False
        assert pid_do_servidor(tmp_path) == filho.pid
    finally:
        filho.kill()
        filho.wait()
    assert pid_do_servidor(tmp_path) is None  # morreu: a trava se solta sozinha


def test_porta_padrao_e_jobot_porta() -> None:
    assert porta({}) == 47615
    assert porta({"JOBOT_PORTA": "50123"}) == 50123
    assert porta({"JOBOT_PORTA": " 50123 "}) == 50123


@pytest.mark.parametrize("valor", ["", "abc", "0", "-1", "65536", "47615.5", "٤٧٦١٥"])
def test_jobot_porta_invalida_cai_no_padrao(valor: str) -> None:
    assert porta({"JOBOT_PORTA": valor}) == 47615


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
