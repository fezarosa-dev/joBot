import logging
import logging.handlers
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from jobot.sistema.pastas import configurar_log, pasta_de_dados, preparar_pasta


def test_ordem_das_pastas(tmp_path: Path) -> None:
    casa = str(tmp_path / "casa")
    xdg = str(tmp_path / "xdg")
    dados = str(tmp_path / "dados")
    assert pasta_de_dados({"JOBOT_DADOS": dados, "XDG_DATA_HOME": xdg, "HOME": casa}) == Path(dados)
    assert pasta_de_dados({"XDG_DATA_HOME": xdg, "HOME": casa}) == Path(xdg) / "jobot"
    assert pasta_de_dados({"HOME": casa}) == Path(casa) / ".local" / "share" / "jobot"
    # variável vazia conta como ausente
    vazias = {"JOBOT_DADOS": "", "XDG_DATA_HOME": "", "HOME": casa}
    assert pasta_de_dados(vazias) == Path(casa) / ".local" / "share" / "jobot"


def _modo(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


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
