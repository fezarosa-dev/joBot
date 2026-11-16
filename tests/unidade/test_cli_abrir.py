"""Comandos `abrir` e `sair` no terminal (T267): o `cli` monta o abridor da janela."""

import functools
import signal
import socket
import sys
from argparse import Namespace
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from apoio.filho_com_trava import filho_com_trava
from jobot.cli import abrir as cli_abrir
from jobot.cli.abrir import executar
from jobot.sistema.abrir import abrir_janela


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _porta_alheia() -> Iterator[int]:
    """Alguém que escuta numa porta e não é o joBot."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        yield int(s.getsockname()[1])


def test_executar_abrir_com_porta_alheia_nao_sobe_nem_abre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subidas: list[int] = []
    navegadores: list[str] = []

    def abre(endereco: str, env: Mapping[str, str]) -> bool:
        navegadores.append(endereco)
        return True

    monkeypatch.setattr(cli_abrir, "subir_servidor", lambda: subidas.append(1))
    monkeypatch.setattr(cli_abrir, "abrir_janela", abre)
    with _porta_alheia() as porta:
        monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
        monkeypatch.setenv("JOBOT_PORTA", str(porta))
        monkeypatch.delenv("CONTAINER_ID", raising=False)
        assert executar(Namespace(comando="abrir")) != 0
    assert subidas == []
    assert navegadores == []


def test_executar_abrir_que_nao_consegue_subir_diz_numa_linha_e_sai_com_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    monkeypatch.setenv("JOBOT_PORTA", str(_porta_livre()))
    monkeypatch.delenv("CONTAINER_ID", raising=False)
    monkeypatch.setattr(sys, "executable", "/nao/existe/python-do-jobot")
    erro: OSError | None = None
    codigo = None
    try:
        codigo = executar(Namespace(comando="abrir"))
    except OSError as exc:
        erro = exc
    assert erro is None, f"OSError vazou: {erro!r}"
    assert codigo == 1
    linhas = capsys.readouterr().err.strip().splitlines()
    assert len(linhas) == 1
    assert "Traceback" not in linhas[0]


def test_executar_sair_usa_a_pasta_de_dados_do_ambiente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    with filho_com_trava(tmp_path) as filho:
        assert executar(Namespace(comando="sair")) == 0
        assert filho.wait(timeout=5) == -signal.SIGTERM


def test_abrir_passa_a_janela_ao_painel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recebidos: dict[str, Any] = {}

    def abrir_painel_falso(env: Mapping[str, str], dados: Path, **kwargs: Any) -> int:
        recebidos.update(kwargs)
        return 0

    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    monkeypatch.setattr(cli_abrir, "abrir_painel", abrir_painel_falso)
    assert executar(Namespace(comando="abrir")) == 0
    navegador: Callable[..., bool] = recebidos["navegador"]
    assert isinstance(navegador, functools.partial)
    assert navegador.func is abrir_janela
    assert navegador.keywords["sistema"] == sys.platform
    assert navegador.keywords["pasta_dados"] == tmp_path
    assert callable(navegador.keywords["existe"])
    assert callable(navegador.keywords["chromium"])
