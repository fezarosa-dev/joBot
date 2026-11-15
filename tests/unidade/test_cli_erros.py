"""T154 (D106): nenhum erro trava; o terminal nunca mostra traceback cru e diz onde está o log."""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from jobot import cli
from jobot.cli import servir


@pytest.fixture
def dados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    raiz = logging.getLogger("jobot")
    antes = list(raiz.handlers)
    yield tmp_path
    for h in list(raiz.handlers):
        if h not in antes:
            raiz.removeHandler(h)
            h.close()


def _comando(
    monkeypatch: pytest.MonkeyPatch, executar: Callable[[argparse.Namespace], int]
) -> None:
    monkeypatch.setitem(sys.modules, "jobot_comando_falso", SimpleNamespace(executar=executar))
    monkeypatch.setitem(cli.COMANDOS, "buscar", "jobot_comando_falso")


def _levanta(erro: BaseException) -> Callable[[argparse.Namespace], int]:
    def executar(args: argparse.Namespace) -> int:
        raise erro

    return executar


def test_erro_qualquer_vira_mensagem_curta_e_vai_para_o_log(
    dados: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _comando(monkeypatch, _levanta(RuntimeError("estourou aqui")))
    assert cli.main(["buscar"]) == 1
    err = capsys.readouterr().err
    log = dados / "logs" / "jobot.log"
    assert "Traceback" not in err
    assert "estourou aqui" not in err
    assert err.strip() == (
        f"O joBot encontrou um erro e parou. Detalhes em {log}. "
        "Se repetir, abra uma issue com esse arquivo."
    )
    texto = log.read_text(encoding="utf-8")
    assert "Traceback" in texto
    assert "RuntimeError: estourou aqui" in texto


def test_erro_do_banco_tem_mensagem_propria(
    dados: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _comando(monkeypatch, _levanta(sqlite3.OperationalError("database or disk is full")))
    assert cli.main(["buscar"]) == 1
    err = capsys.readouterr().err
    log = dados / "logs" / "jobot.log"
    assert "Traceback" not in err
    assert "disk is full" not in err
    assert err.strip() == (
        "Problema no banco de dados do joBot (pode ser disco cheio ou arquivo danificado). "
        f"Detalhes em {log}."
    )
    assert "sqlite3.OperationalError: database or disk is full" in log.read_text(encoding="utf-8")


def test_ctrl_c_sai_com_130_sem_traceback(
    dados: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _comando(monkeypatch, _levanta(KeyboardInterrupt()))
    assert cli.main(["buscar"]) == 130
    saida = capsys.readouterr()
    assert "Traceback" not in saida.err
    assert len(saida.err.strip().splitlines()) == 1


def test_sem_log_so_a_mensagem_curta(
    dados: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def log_quebrado(pasta: Path) -> None:
        raise OSError("sem permissão")

    monkeypatch.setattr(cli, "configurar_log", log_quebrado, raising=False)
    _comando(monkeypatch, _levanta(RuntimeError("x")))
    assert cli.main(["buscar"]) == 1
    err = capsys.readouterr().err
    assert err.strip() == "O joBot encontrou um erro e parou."
    assert "Traceback" not in err


def test_comando_que_devolve_codigo_segue_igual(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _comando(monkeypatch, lambda args: 3)
    assert cli.main(["buscar"]) == 3


def test_serve_com_erro_do_banco_na_preparacao_da_1_e_a_mensagem(
    dados: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def montar_quebrado(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(servir, "montar", montar_quebrado)
    assert servir.executar(argparse.Namespace(comando="serve")) == 1
    err = capsys.readouterr().err
    log = dados / "logs" / "jobot.log"
    assert "Traceback" not in err
    assert err.strip() == (
        "Problema no banco de dados do joBot (pode ser disco cheio ou arquivo danificado). "
        f"Detalhes em {log}."
    )
    assert "disk is full" in log.read_text(encoding="utf-8")
