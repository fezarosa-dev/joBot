"""Cofre da chave (T180): cofre do sistema com reserva em arquivo 0600."""

import logging
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import keyring
import keyring.backends.fail
import pytest
from keyring.errors import InitError, KeyringLocked, NoKeyringError

from apoio.cofre_falso import CofreFalso
from jobot.sistema.cofre import SERVICO, Cofre

CHAVE = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
OUTRA = "f0e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5"
SEGREDO = "segredo-que-nao-pode-vazar"
NOME = "2captcha"
# o job do Windows na casca.yml roda este arquivo: lá não há os bits 0600 do POSIX
SO_POSIX = pytest.mark.skipif(sys.platform == "win32", reason="o Windows não tem os bits do POSIX")


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    p = tmp_path / "dados"
    p.mkdir()
    return p


@pytest.fixture(autouse=True)
def _log(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    caplog.set_level(logging.WARNING, logger="jobot")
    yield


def _modo(caminho: Path) -> int:
    return stat.S_IMODE(caminho.stat().st_mode)


def test_grava_le_e_apaga_no_cofre_do_sistema(pasta: Path) -> None:
    falso = CofreFalso()
    cofre = Cofre(pasta, falso)
    assert cofre.gravar(NOME, CHAVE) == "sistema"
    assert falso.guardado == {(SERVICO, NOME): CHAVE}
    assert cofre.ler(NOME) == (CHAVE, "sistema")
    assert not (pasta / f"{NOME}.segredo").exists()
    cofre.apagar(NOME)
    assert cofre.ler(NOME) is None
    assert falso.guardado == {}


@SO_POSIX
def test_cofre_que_falha_cai_no_arquivo_0600(pasta: Path, caplog: pytest.LogCaptureFixture) -> None:
    cofre = Cofre(pasta, CofreFalso(falha=RuntimeError(SEGREDO)))
    assert cofre.gravar(NOME, CHAVE) == "arquivo"
    arquivo = pasta / f"{NOME}.segredo"
    assert _modo(arquivo) == 0o600
    assert cofre.ler(NOME) == (CHAVE, "arquivo")
    assert SEGREDO not in caplog.text
    assert CHAVE not in caplog.text
    assert "RuntimeError" in caplog.text
    assert all(r.exc_info is None for r in caplog.records)


def test_reserva_no_arquivo_sem_o_cloexec_do_posix(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # o Windows não tem `os.O_CLOEXEC`: ler sem segredo, gravar o arquivo e o fsync da pasta
    # não podem estourar `AttributeError` por causa dele
    monkeypatch.delattr(os, "O_CLOEXEC", raising=False)  # no Windows já não existe
    cofre = Cofre(pasta, CofreFalso(falha=RuntimeError("fora do ar")))
    assert cofre.ler(NOME) is None
    assert cofre.gravar(NOME, CHAVE) == "arquivo"
    assert cofre.ler(NOME) == (CHAVE, "arquivo")


def test_cofre_que_engole_a_chave_cai_no_arquivo(pasta: Path) -> None:
    cofre = Cofre(pasta, CofreFalso(engole=True))
    assert cofre.gravar(NOME, CHAVE) == "arquivo"
    assert cofre.ler(NOME) == (CHAVE, "arquivo")


@SO_POSIX
def test_arquivo_nasce_0600_mesmo_com_umask_aberto(pasta: Path) -> None:
    antiga = os.umask(0)
    try:
        assert Cofre(pasta, CofreFalso(falha=RuntimeError())).gravar(NOME, CHAVE) == "arquivo"
    finally:
        os.umask(antiga)
    assert _modo(pasta / f"{NOME}.segredo") == 0o600


@SO_POSIX
def test_arquivo_existente_frouxo_fica_0600(pasta: Path) -> None:
    arquivo = pasta / f"{NOME}.segredo"
    arquivo.write_text(OUTRA)
    arquivo.chmod(0o644)
    assert Cofre(pasta, CofreFalso(falha=RuntimeError())).gravar(NOME, CHAVE) == "arquivo"
    assert _modo(arquivo) == 0o600
    assert arquivo.read_text() == CHAVE


def test_symlink_no_lugar_do_arquivo_e_recusado(pasta: Path, tmp_path: Path) -> None:
    fora = tmp_path / "fora"
    fora.mkdir()
    alvo = fora / "alvo"
    alvo.write_text("intacto")
    (pasta / f"{NOME}.segredo").symlink_to(alvo)
    cofre = Cofre(pasta, CofreFalso(falha=RuntimeError()))
    with pytest.raises(OSError):
        cofre.gravar(NOME, CHAVE)
    assert alvo.read_text() == "intacto"
    assert cofre.ler(NOME) is None


def test_symlink_quebrado_no_lugar_do_arquivo_e_recusado(pasta: Path, tmp_path: Path) -> None:
    destino = tmp_path / "fora" / "nao_existe"
    destino.parent.mkdir()
    (pasta / f"{NOME}.segredo").symlink_to(destino)
    cofre = Cofre(pasta, CofreFalso(falha=RuntimeError()))
    with pytest.raises(OSError):
        cofre.gravar(NOME, CHAVE)
    assert not destino.exists()
    assert list(destino.parent.iterdir()) == []


def test_gravar_no_cofre_apaga_o_arquivo_antigo(pasta: Path) -> None:
    arquivo = pasta / f"{NOME}.segredo"
    arquivo.write_text(OUTRA)
    cofre = Cofre(pasta, CofreFalso())
    assert cofre.gravar(NOME, CHAVE) == "sistema"
    assert not arquivo.exists()
    assert cofre.ler(NOME) == (CHAVE, "sistema")


def test_apagar_tira_dos_dois_lugares(pasta: Path) -> None:
    falso = CofreFalso()
    falso.guardado[(SERVICO, NOME)] = CHAVE
    arquivo = pasta / f"{NOME}.segredo"
    arquivo.write_text(OUTRA)
    cofre = Cofre(pasta, falso)
    cofre.apagar(NOME)
    assert cofre.ler(NOME) is None
    assert not arquivo.exists()
    assert falso.guardado == {}


def test_reserva_no_arquivo_nao_deixa_chave_velha_no_sistema(pasta: Path) -> None:
    falso = CofreFalso(engole=True)
    falso.guardado[(SERVICO, NOME)] = CHAVE
    cofre = Cofre(pasta, falso)
    assert cofre.gravar(NOME, OUTRA) == "arquivo"
    assert cofre.ler(NOME) == (OUTRA, "arquivo")
    assert falso.guardado == {}


def test_apagar_que_o_cofre_recusa_levanta(pasta: Path) -> None:
    falso = CofreFalso(recusa_apagar=True)
    falso.guardado[(SERVICO, NOME)] = CHAVE
    with pytest.raises(OSError, match="não apagou$") as erro:
        Cofre(pasta, falso).apagar(NOME)
    assert CHAVE not in str(erro.value)
    assert CHAVE not in repr(erro.value)


def test_apagar_o_que_nao_existe_e_silencioso(
    pasta: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cofre = Cofre(pasta, CofreFalso())
    cofre.apagar(NOME)
    assert cofre.ler(NOME) is None
    assert caplog.records == []


def test_nome_valido_passa(pasta: Path) -> None:
    cofre = Cofre(pasta, CofreFalso())
    assert cofre.gravar("abc_1", CHAVE) == "sistema"
    assert cofre.ler("abc_1") == (CHAVE, "sistema")
    cofre.apagar("abc_1")


@pytest.mark.parametrize("nome", ["../x", "", "A b", "a" * 33, "2captcha\n", "çaptcha"])
@pytest.mark.parametrize("metodo", ["ler", "gravar", "apagar"])
def test_nome_fora_do_padrao_e_recusado(pasta: Path, nome: str, metodo: str) -> None:
    falso = CofreFalso()
    cofre = Cofre(pasta, falso)
    argumentos = (nome, CHAVE) if metodo == "gravar" else (nome,)
    with pytest.raises(ValueError):
        getattr(cofre, metodo)(*argumentos)
    assert falso.guardado == {}
    assert list(pasta.iterdir()) == []


def test_testes_nunca_tocam_o_cofre_real() -> None:
    assert isinstance(keyring.get_keyring(), keyring.backends.fail.Keyring)


def test_cofre_padrao_usa_o_keyring(pasta: Path, caplog: pytest.LogCaptureFixture) -> None:
    cofre = Cofre(pasta)
    assert cofre.gravar(NOME, CHAVE) == "arquivo"
    caplog.set_level(logging.DEBUG, logger="jobot")
    assert cofre.ler(NOME) == (CHAVE, "arquivo")
    assert "NoKeyringError" in caplog.text


@pytest.mark.parametrize("erro", [KeyringLocked(SEGREDO), InitError(SEGREDO)])
def test_apagar_com_cofre_trancado_levanta(
    pasta: Path, erro: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    arquivo = pasta / f"{NOME}.segredo"
    arquivo.write_text(CHAVE)
    with pytest.raises(OSError, match="não confirmou") as levantado:
        Cofre(pasta, CofreFalso(falha=erro)).apagar(NOME)
    assert not arquivo.exists()
    assert levantado.value.__context__ is None
    assert levantado.value.__cause__ is None
    assert SEGREDO not in str(levantado.value)
    assert SEGREDO not in caplog.text
    assert type(erro).__name__ in caplog.text


def test_apagar_sem_cofre_tira_o_arquivo(pasta: Path) -> None:
    arquivo = pasta / f"{NOME}.segredo"
    arquivo.write_text(CHAVE)
    Cofre(pasta, CofreFalso(falha=NoKeyringError())).apagar(NOME)
    assert not arquivo.exists()


def test_sem_cofre_loga_em_debug_sem_aviso(pasta: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="jobot")
    cofre = Cofre(pasta, CofreFalso(falha=NoKeyringError(SEGREDO)))
    assert cofre.gravar(NOME, CHAVE) == "arquivo"
    assert cofre.ler(NOME) == (CHAVE, "arquivo")
    cofre.apagar(NOME)
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert any(
        r.levelno == logging.DEBUG and "NoKeyringError" in r.getMessage() for r in caplog.records
    )
    assert SEGREDO not in caplog.text


def test_outra_falha_do_cofre_segue_em_warning(
    pasta: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="jobot")
    assert Cofre(pasta, CofreFalso(falha=KeyringLocked())).gravar(NOME, CHAVE) == "arquivo"
    assert any(
        r.levelno == logging.WARNING and "KeyringLocked" in r.getMessage() for r in caplog.records
    )


def test_falha_na_escrita_mantem_o_arquivo_antigo_e_nao_deixa_tmp(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arquivo = pasta / f"{NOME}.segredo"
    arquivo.write_text(OUTRA)

    def _quebra(fd: int, modo: int) -> None:
        raise OSError("disco cheio")

    monkeypatch.setattr(os, "fchmod", _quebra)  # passo que o código antigo também fazia
    with pytest.raises(OSError, match="disco cheio"):
        Cofre(pasta, CofreFalso(falha=RuntimeError())).gravar(NOME, CHAVE)
    assert arquivo.read_text() == OUTRA
    assert sorted(p.name for p in pasta.iterdir()) == [arquivo.name]


@SO_POSIX
@pytest.mark.parametrize("mascara", [0o277, 0])
def test_arquivo_final_fica_0600_e_o_tmp_nunca_e_frouxo(
    pasta: Path, monkeypatch: pytest.MonkeyPatch, mascara: int
) -> None:
    modos: list[int] = []
    fchmod = os.fchmod

    def _mede(fd: int, modo: int) -> None:
        modos.append(os.fstat(fd).st_mode & 0o777)  # como o .tmp nasceu, antes do fchmod
        fchmod(fd, modo)

    monkeypatch.setattr(os, "fchmod", _mede)
    antiga = os.umask(mascara)
    try:
        Cofre(pasta, CofreFalso(falha=RuntimeError())).gravar(NOME, CHAVE)
    finally:
        os.umask(antiga)
    arquivo = pasta / f"{NOME}.segredo"
    assert len(modos) == 1
    assert modos[0] & ~0o600 == 0
    assert _modo(arquivo) == 0o600
    assert arquivo.read_text() == CHAVE
    assert [p.name for p in pasta.iterdir()] == [arquivo.name]


def test_tmp_velho_de_queda_anterior_nao_impede_a_gravacao(pasta: Path, tmp_path: Path) -> None:
    alvo = tmp_path / "alvo"
    alvo.write_text("intacto")
    (pasta / f"{NOME}.segredo.tmp").symlink_to(alvo)  # pior caso: o resto é um link
    assert Cofre(pasta, CofreFalso(falha=RuntimeError())).gravar(NOME, CHAVE) == "arquivo"
    assert (pasta / f"{NOME}.segredo").read_text() == CHAVE
    assert not (pasta / f"{NOME}.segredo.tmp").exists()
    assert alvo.read_text() == "intacto"


def test_apagar_tira_tambem_o_tmp_de_queda(pasta: Path) -> None:
    (pasta / f"{NOME}.segredo").write_text(CHAVE)
    (pasta / f"{NOME}.segredo.tmp").write_text(CHAVE)
    Cofre(pasta, CofreFalso()).apagar(NOME)
    assert list(pasta.iterdir()) == []


def test_gravar_no_sistema_tira_o_tmp_de_queda(pasta: Path) -> None:
    (pasta / f"{NOME}.segredo.tmp").write_text(CHAVE)
    assert Cofre(pasta, CofreFalso()).gravar(NOME, CHAVE) == "sistema"
    assert list(pasta.iterdir()) == []


def test_interrupcao_na_escrita_tambem_limpa_o_tmp(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _para(fd: int) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "fsync", _para)
    with pytest.raises(KeyboardInterrupt):
        Cofre(pasta, CofreFalso(falha=RuntimeError())).gravar(NOME, CHAVE)
    assert list(pasta.iterdir()) == []


@pytest.mark.skipif(sys.platform == "win32", reason="o Windows não abre pasta com os.open")
def test_falha_no_fsync_da_pasta_nao_derruba_a_gravacao(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fsync = os.fsync
    pasta_fd: list[int] = []
    abrir = os.open

    def _abre(caminho: object, flags: int, *resto: int) -> int:
        fd = abrir(caminho, flags, *resto)  # type: ignore[arg-type]
        if caminho == pasta:
            pasta_fd.append(fd)
        return fd

    def _fsync(fd: int) -> None:
        if fd in pasta_fd:
            raise OSError("sem fsync em diretório")
        fsync(fd)

    monkeypatch.setattr(os, "open", _abre)
    monkeypatch.setattr(os, "fsync", _fsync)
    assert Cofre(pasta, CofreFalso(falha=RuntimeError())).gravar(NOME, CHAVE) == "arquivo"
    assert pasta_fd  # a pasta foi mesmo aberta para o fsync
    assert (pasta / f"{NOME}.segredo").read_text() == CHAVE
