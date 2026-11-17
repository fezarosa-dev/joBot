import logging
import logging.handlers
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from jobot.sistema.pastas import configurar_log, pasta_de_dados, preparar_pasta

_SO_POSIX = pytest.mark.skipif(sys.platform == "win32", reason="modo e symlink do POSIX")


def test_ordem_das_pastas(tmp_path: Path) -> None:
    casa = str(tmp_path / "casa")
    xdg = str(tmp_path / "xdg")
    dados = str(tmp_path / "dados")
    tudo = {"JOBOT_DADOS": dados, "XDG_DATA_HOME": xdg, "HOME": casa}
    assert pasta_de_dados(tudo, plataforma="linux") == Path(dados)
    linux = Path(casa) / ".local" / "share" / "jobot"
    so_xdg = {"XDG_DATA_HOME": xdg, "HOME": casa}
    assert pasta_de_dados(so_xdg, plataforma="linux") == Path(xdg) / "jobot"
    assert pasta_de_dados({"HOME": casa}, plataforma="linux") == linux
    # variável vazia conta como ausente
    vazias = {"JOBOT_DADOS": "", "XDG_DATA_HOME": "", "HOME": casa}
    assert pasta_de_dados(vazias, plataforma="linux") == Path(casa) / ".local" / "share" / "jobot"


def test_pasta_windows(tmp_path: Path) -> None:
    local = str(tmp_path / "Local")
    env = {"LOCALAPPDATA": local, "USERPROFILE": str(tmp_path / "eu"), "XDG_DATA_HOME": "x"}
    assert pasta_de_dados(env, plataforma="win32") == Path(local) / "joBot"


def test_windows_sem_localappdata(tmp_path: Path) -> None:
    eu = str(tmp_path / "eu")
    esperado = Path(eu) / "AppData" / "Local" / "joBot"
    assert pasta_de_dados({"USERPROFILE": eu}, plataforma="win32") == esperado
    assert pasta_de_dados({"LOCALAPPDATA": "", "USERPROFILE": eu}, plataforma="win32") == esperado


def test_pasta_mac(tmp_path: Path) -> None:
    casa = str(tmp_path / "casa")
    env = {"HOME": casa, "XDG_DATA_HOME": str(tmp_path / "xdg")}
    esperado = Path(casa) / "Library" / "Application Support" / "joBot"
    assert pasta_de_dados(env, plataforma="darwin") == esperado


@pytest.mark.parametrize("plataforma", ["linux", "win32", "darwin"])
def test_jobot_dados_vence_em_todo_sistema(tmp_path: Path, plataforma: str) -> None:
    dados = str(tmp_path / "dados")
    env = {"JOBOT_DADOS": dados, "LOCALAPPDATA": "L", "HOME": "H", "USERPROFILE": "U"}
    assert pasta_de_dados(env, plataforma=plataforma) == Path(dados)


def _modo(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


@_SO_POSIX
def test_permissoes(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    pasta = tmp_path / "jobot"
    pasta.mkdir(mode=0o755)
    pasta.chmod(0o755)
    (pasta / "jobot.db").write_text("x")
    (pasta / "jobot.db").chmod(0o644)
    with caplog.at_level(logging.INFO, logger="jobot"):
        preparar_pasta(pasta)
    assert _modo(pasta) == 0o700
    assert _modo(pasta / "jobot.db") == 0o600
    assert len(caplog.records) == 1

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="jobot"):
        preparar_pasta(pasta)
    assert caplog.records == []


@_SO_POSIX
def test_preparar_pasta_nao_desce_em_navegador(tmp_path: Path) -> None:
    pasta = tmp_path / "jobot"
    (pasta / "navegador" / "Default").mkdir(parents=True)
    (pasta / "outra").mkdir()
    cookies = pasta / "navegador" / "Default" / "Cookies"
    cookies.write_text("x")
    cookies.chmod(0o644)
    (pasta / "navegador").chmod(0o755)
    controle = pasta / "outra" / "a.txt"
    controle.write_text("x")
    controle.chmod(0o644)
    preparar_pasta(pasta)
    assert _modo(cookies) == 0o644
    assert _modo(pasta / "navegador") == 0o700
    assert _modo(controle) == 0o600


@_SO_POSIX
def test_preparar_pasta_nao_desce_na_pasta_da_casca(tmp_path: Path) -> None:
    # no Windows e no Mac a casca instala em <dados>/app (D181.6): o Python e o venv precisam
    # do bit de execução (achado da fumaça da T339, D183)
    pasta = tmp_path / "jobot"
    python = pasta / "app" / "venvs" / "venv-0.4.0" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("x")
    python.chmod(0o755)
    (pasta / "app").chmod(0o755)
    controle = pasta / "jobot.db"
    controle.write_text("x")
    controle.chmod(0o644)
    preparar_pasta(pasta)
    assert _modo(python) == 0o755
    assert _modo(pasta / "app") == 0o700
    assert _modo(controle) == 0o600


@_SO_POSIX
def test_preparar_pasta_nao_tira_o_x_das_ferramentas(tmp_path: Path) -> None:
    # (guarda) o `llama-server` baixado em <dados>/ferramentas precisa do bit de execução na
    # subida seguinte (T404; desenho 7; D185.18); controle: um arquivo frouxo fora fecha
    pasta = tmp_path / "jobot"
    programa = pasta / "ferramentas" / "llama" / "b12359" / "llama-server"
    programa.parent.mkdir(parents=True)
    programa.write_text("x")
    programa.chmod(0o755)
    (pasta / "ferramentas").chmod(0o755)
    controle = pasta / "logs" / "jobot.log"
    controle.parent.mkdir()
    controle.write_text("x")
    controle.chmod(0o755)
    preparar_pasta(pasta)
    assert _modo(programa) == 0o755
    assert _modo(pasta / "ferramentas") == 0o700
    assert _modo(controle) == 0o600


@_SO_POSIX
def test_preparar_pasta_nao_segue_navegador_symlink(tmp_path: Path) -> None:
    alvo = tmp_path / "fora"
    alvo.mkdir()
    (alvo / "Cookies").write_text("x")
    (alvo / "Cookies").chmod(0o644)
    alvo.chmod(0o755)
    pasta = tmp_path / "jobot"
    pasta.mkdir()
    (pasta / "navegador").symlink_to(alvo, target_is_directory=True)
    preparar_pasta(pasta)
    assert _modo(alvo) == 0o755
    assert _modo(alvo / "Cookies") == 0o644


@_SO_POSIX
def test_pasta_nova_nasce_fechada(tmp_path: Path) -> None:
    pasta = tmp_path / "a" / "jobot"
    preparar_pasta(pasta)
    assert _modo(pasta) == 0o700


@pytest.fixture
def _sem_handlers() -> Iterator[None]:
    raiz = logging.getLogger("jobot")
    antes = list(raiz.handlers)
    yield
    for h in list(raiz.handlers):
        if h not in antes:
            raiz.removeHandler(h)
            h.close()


@_SO_POSIX
@pytest.mark.usefixtures("_sem_handlers")
def test_log_rotativo_fechado(tmp_path: Path) -> None:
    pasta = tmp_path / "jobot"
    preparar_pasta(pasta)
    configurar_log(pasta)
    configurar_log(pasta)
    raiz = logging.getLogger("jobot")
    rotativos = [h for h in raiz.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
    assert len(rotativos) == 1
    logging.getLogger("jobot.teste").warning("oi")
    arquivo = pasta / "logs" / "jobot.log"
    assert "oi" in arquivo.read_text()
    assert _modo(arquivo) == 0o600
    assert _modo(pasta / "logs") == 0o700


@_SO_POSIX
def test_symlink_nao_e_seguido(tmp_path: Path) -> None:
    fora = tmp_path / "fora.txt"
    fora.write_text("x")
    fora.chmod(0o644)
    pasta = tmp_path / "jobot"
    pasta.mkdir(mode=0o700)
    (pasta / "valido").symlink_to(fora)
    (pasta / "pasta_ln").symlink_to(tmp_path)
    tmp_path.chmod(0o755)
    preparar_pasta(pasta)
    assert _modo(fora) == 0o644
    assert _modo(tmp_path) == 0o755


def test_symlink_quebrado_nao_derruba(tmp_path: Path) -> None:
    pasta = tmp_path / "jobot"
    pasta.mkdir(mode=0o700)
    (pasta / "quebrado").symlink_to(tmp_path / "nao_existe")
    preparar_pasta(pasta)
    assert (pasta / "quebrado").is_symlink()


@_SO_POSIX
@pytest.mark.usefixtures("_sem_handlers")
def test_arquivo_rotacionado_nasce_fechado(tmp_path: Path) -> None:
    pasta = tmp_path / "jobot"
    preparar_pasta(pasta)
    configurar_log(pasta)
    rotativo = next(
        h
        for h in logging.getLogger("jobot").handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    )
    rotativo.doRollover()
    logging.getLogger("jobot.teste").warning("depois")
    assert _modo(pasta / "logs" / "jobot.log.1") == 0o600
    assert _modo(pasta / "logs" / "jobot.log") == 0o600
