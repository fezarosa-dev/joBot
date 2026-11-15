"""Motivo da parada de uma execução (T153, D106): banco, agenda, tela do andamento e `buscar`."""

import argparse
import asyncio
import inspect
import json
import logging
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from jobot.agenda import descoberta as agenda_descoberta
from jobot.agenda import execucao as agenda_execucao
from jobot.agenda import paginas as agenda_paginas
from jobot.agenda.descoberta import executar_descoberta
from jobot.agenda.execucao import executar_busca, parada_de
from jobot.agenda.paginas import executar_paginas
from jobot.banco.cadastros import gravar_config, semear
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import (
    abrir_execucao,
    fechar_execucao,
    interromper_execucao,
    marcar_interrompidas,
)
from jobot.banco.migrar import MIGRACOES, migrar
from jobot.cli import buscar
from jobot.painel.app import criar_app
from jobot.painel.i18n import t

pytestmark = pytest.mark.anyio

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
PARADAS = ("fechado", "sem_batimento", "banco", "erro")
PORTA = 47623
BASE = f"http://127.0.0.1:{PORTA}"
HTMX = {"HX-Request": "true"}
I18N = Path(__file__).resolve().parents[2] / "src" / "jobot" / "painel" / "i18n"


def _parada(con: sqlite3.Connection, id_: int) -> tuple[str, str | None]:
    linha = con.execute("SELECT estado, parada FROM execucao WHERE id = ?", (id_,)).fetchone()
    return (linha[0], linha[1])


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    with closing(abrir(caminho)) as c:
        migrar(c, caminho)
        semear(c)
        yield c


# --- banco ---


@pytest.mark.parametrize("parada", ["fechado", "banco", "erro"])
def test_interromper_grava_a_parada(con: sqlite3.Connection, parada: Any) -> None:
    id_ = abrir_execucao(con, "busca", "agora", AGORA)
    assert id_ is not None
    interromper_execucao(con, id_, AGORA + timedelta(seconds=5), parada=parada)
    assert _parada(con, id_) == ("interrompida", parada)


def test_interromper_execucao_encerrada_nao_grava_parada(con: sqlite3.Connection) -> None:
    id_ = abrir_execucao(con, "busca", "agora", AGORA)
    assert id_ is not None
    fechar_execucao(con, id_, AGORA + timedelta(minutes=1))
    interromper_execucao(con, id_, AGORA + timedelta(minutes=2), parada="erro")
    assert _parada(con, id_) == ("concluida", None)


def test_marcar_interrompidas_grava_sem_batimento(con: sqlite3.Connection) -> None:
    velha = abrir_execucao(con, "busca", "agenda", AGORA)
    viva = abrir_execucao(con, "paginas", "agenda", AGORA + timedelta(minutes=8))
    assert velha is not None and viva is not None
    assert marcar_interrompidas(con, AGORA + timedelta(minutes=10)) == 1
    assert _parada(con, velha) == ("interrompida", "sem_batimento")
    assert _parada(con, viva) == ("rodando", None)


def test_check_recusa_parada_fora_da_lista(con: sqlite3.Connection) -> None:
    id_ = abrir_execucao(con, "busca", "agora", AGORA)
    assert id_ is not None
    con.execute("UPDATE execucao SET parada = 'banco' WHERE id = ?", (id_,))  # controle válido
    con.commit()
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        con.execute("UPDATE execucao SET parada = 'outra' WHERE id = ?", (id_,))
    con.rollback()
    assert _parada(con, id_) == ("rodando", "banco")


# --- migração ---


def _na_versao_tres(tmp_path: Path) -> tuple[sqlite3.Connection, Path]:
    pasta = tmp_path / "ate_a_terceira"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:3]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    assert migrar(c, caminho, pasta) == 3
    return c, caminho


def _colunas(con: sqlite3.Connection) -> list[str]:
    return [r[1] for r in con.execute("PRAGMA table_info(execucao)")]


def test_migracao_0004_isolada(tmp_path: Path) -> None:
    """Sem a migração a coluna não existe; com ela existe e recusa valor fora da lista."""
    c, _ = _na_versao_tres(tmp_path)
    with closing(c):
        sql = (MIGRACOES / "0004_motivo_da_parada.sql").read_text("utf-8")
        assert "parada" not in _colunas(c)
        c.executescript(f"BEGIN;\n{sql}\n")
        try:
            assert "parada" in _colunas(c)
            c.execute(
                "INSERT INTO execucao (tipo, motivo, iniciada_em, batimento_em, estado, parada)"
                " VALUES ('busca', 'agora', 'x', 'x', 'interrompida', 'erro')"
            )
            with pytest.raises(sqlite3.IntegrityError):
                c.execute("UPDATE execucao SET parada = 'qualquer'")
        finally:
            c.execute("ROLLBACK")
        assert "parada" not in _colunas(c)


def test_migrar_da_versao_tres_deixa_as_antigas_sem_parada(tmp_path: Path) -> None:
    c, caminho = _na_versao_tres(tmp_path)
    with closing(c):
        c.execute(
            "INSERT INTO execucao (tipo, motivo, iniciada_em, batimento_em, terminada_em, estado)"
            " VALUES ('busca', 'agenda', 'a', 'b', 'c', 'interrompida'),"
            " ('busca', 'agora', 'd', 'e', 'f', 'concluida')"
        )
        c.commit()
        assert migrar(c, caminho) == len(list(MIGRACOES.glob("*.sql")))
        assert c.execute(
            "SELECT estado, terminada_em, parada FROM execucao ORDER BY id"
        ).fetchall() == [
            ("interrompida", "c", None),
            ("concluida", "f", None),
        ]


# --- agenda ---


@pytest.mark.parametrize(
    ("erro", "esperada"),
    [
        (asyncio.CancelledError(), "fechado"),
        (KeyboardInterrupt(), "fechado"),
        (SystemExit(), "fechado"),
        (sqlite3.OperationalError("disco cheio"), "banco"),
        (sqlite3.IntegrityError("x"), "banco"),
        (RuntimeError("x"), "erro"),
        (OSError("x"), "erro"),
    ],
)
def test_parada_de(erro: BaseException, esperada: str) -> None:
    assert parada_de(erro) == esperada


async def _busca(con: sqlite3.Connection, relogio: RelogioFalso) -> object:
    return await executar_busca(con, object(), relogio, "agora", coletores={})  # type: ignore[arg-type]


async def _descoberta(con: sqlite3.Connection, relogio: RelogioFalso) -> None:
    await executar_descoberta(con, object(), relogio)  # type: ignore[arg-type]


async def _paginas(con: sqlite3.Connection, relogio: RelogioFalso) -> object:
    return await executar_paginas(con, object(), relogio)  # type: ignore[arg-type]


# tipo -> (módulo, nome trocado para quebrar dentro do try, como rodar)
TIPOS: dict[str, tuple[Any, str, Any]] = {
    "busca": (agenda_execucao, "_coletar", _busca),
    "descoberta": (agenda_descoberta, "indice_mais_novo", _descoberta),
    "paginas": (agenda_paginas, "paginas", _paginas),
}


@pytest.fixture
def ligado(con: sqlite3.Connection) -> sqlite3.Connection:
    gravar_config(con, "descoberta_cc_ligada", True)
    gravar_config(con, "paginas_ligadas", True)
    return con


def _quebrar(monkeypatch: pytest.MonkeyPatch, tipo: str, erro: BaseException) -> Any:
    modulo, nome, rodar = TIPOS[tipo]

    def quebra(*_: object, **__: object) -> Any:
        raise erro

    async def quebra_async(*_: object, **__: object) -> Any:
        raise erro

    original = getattr(modulo, nome)
    monkeypatch.setattr(
        modulo, nome, quebra_async if inspect.iscoroutinefunction(original) else quebra
    )
    return rodar


@pytest.mark.parametrize("tipo", list(TIPOS))
@pytest.mark.parametrize(
    ("erro", "esperada"),
    [
        (RuntimeError("quebrou"), "erro"),
        (sqlite3.OperationalError("disk I/O error"), "banco"),
        (asyncio.CancelledError(), "fechado"),
    ],
)
async def test_agenda_grava_a_parada_e_a_excecao_sobe(
    ligado: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    tipo: str,
    erro: BaseException,
    esperada: str,
) -> None:
    rodar = _quebrar(monkeypatch, tipo, erro)
    with pytest.raises(type(erro)) as pego:
        await rodar(ligado, RelogioFalso(AGORA))
    assert pego.value is erro
    linhas = ligado.execute("SELECT tipo, estado, parada FROM execucao").fetchall()
    assert linhas == [(tipo, "interrompida", esperada)]


@pytest.mark.parametrize("tipo", list(TIPOS))
async def test_excecao_original_sobe_quando_interromper_falha(
    ligado: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tipo: str,
) -> None:
    original = RuntimeError("a original")
    rodar = _quebrar(monkeypatch, tipo, original)

    def banco_quebrado(*_: object, **__: object) -> None:
        raise sqlite3.OperationalError("database disk image is malformed")

    monkeypatch.setattr(agenda_execucao, "interromper_execucao", banco_quebrado)
    monkeypatch.setattr(agenda_descoberta, "gravar_config", banco_quebrado)
    with caplog.at_level(logging.ERROR, logger="jobot"):
        with pytest.raises(RuntimeError) as pego:
            await rodar(ligado, RelogioFalso(AGORA))
    assert pego.value is original
    assert any(
        r.exc_info and isinstance(r.exc_info[1], sqlite3.OperationalError) for r in caplog.records
    ), "a falha ao marcar a parada vai para o log"
    assert not ligado.in_transaction


# --- tela do andamento ---


def _painel(tmp_path: Path, parada: str | None, idioma: str) -> str:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as c:
        migrar(c, banco)
        semear(c)
        gravar_config(c, "idioma", idioma)
        id_ = abrir_execucao(c, "busca", "agora", AGORA)
        assert id_ is not None
        if parada is None:  # execução antiga, de antes da coluna
            interromper_execucao(c, id_, AGORA + timedelta(minutes=2), parada="erro")
            c.execute("UPDATE execucao SET parada = NULL WHERE id = ?", (id_,))
            c.commit()
        else:
            interromper_execucao(c, id_, AGORA + timedelta(minutes=2), parada=parada)  # type: ignore[arg-type]
    app = criar_app(tmp_path, PORTA)
    with TestClient(app, base_url=BASE) as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert resposta.status_code == 200
    return unescape(resposta.text)


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize("parada", PARADAS)
def test_andamento_mostra_o_motivo(tmp_path: Path, parada: str, idioma: str) -> None:
    texto = _painel(tmp_path, parada, idioma)
    assert t(idioma, f"execucao.parada.{parada}") in texto
    assert t(idioma, "execucao.parada.novas", n=0) in texto
    assert t(idioma, "execucao.parada.tentar") in texto
    assert t(idioma, "execucao.interrompida", n=0) not in texto


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_andamento_sem_motivo_mantem_o_texto_antigo(tmp_path: Path, idioma: str) -> None:
    texto = _painel(tmp_path, None, idioma)
    assert t(idioma, "execucao.interrompida", n=0) in texto
    assert t(idioma, "execucao.parada.tentar") not in texto


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_textos_da_parada_existem_nas_duas_linguas(idioma: str) -> None:
    textos = json.loads((I18N / idioma / "execucao.json").read_text("utf-8"))
    chaves = {f"execucao.parada.{p}" for p in PARADAS} | {
        "execucao.parada.tentar",
        "execucao.parada.tentar_cli",
        "execucao.parada.novas",
    }
    assert sorted(c for c in chaves if not textos.get(c)) == []
    assert "{n}" in textos["execucao.parada.novas"]
    assert "logs/jobot.log" in textos["execucao.parada.erro"]


def test_frase_do_terminal_tem_texto_proprio() -> None:
    pt = json.loads((I18N / "pt" / "execucao.json").read_text("utf-8"))
    en = json.loads((I18N / "en" / "execucao.json").read_text("utf-8"))
    assert (
        pt.get("execucao.parada.tentar_cli") == "Rode jobot buscar de novo para tentar outra vez."
    )
    assert en.get("execucao.parada.tentar_cli") == "Run jobot buscar again to try once more."
    assert "Clique em" in pt["execucao.parada.tentar"]  # a da tela segue como era


def test_textos_da_parada_diferem_entre_pt_e_en() -> None:
    pt = json.loads((I18N / "pt" / "execucao.json").read_text("utf-8"))
    en = json.loads((I18N / "en" / "execucao.json").read_text("utf-8"))
    for p in PARADAS:
        assert pt[f"execucao.parada.{p}"] != en[f"execucao.parada.{p}"]


# --- jobot buscar ---


@pytest.fixture
def isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """`executar` mexe no umask e no logger `jobot`: o teste devolve os dois como estavam."""
    import os

    dados = tmp_path / "dados"
    dados.mkdir()
    monkeypatch.setenv("JOBOT_DADOS", str(dados))
    umask = os.umask(0o022)
    os.umask(umask)
    raiz = logging.getLogger("jobot")
    handlers, nivel = list(raiz.handlers), raiz.level
    yield dados
    os.umask(umask)
    for handler in [h for h in raiz.handlers if h not in handlers]:
        raiz.removeHandler(handler)
        handler.close()
    raiz.setLevel(nivel)


@pytest.mark.parametrize(
    ("erro", "parada"),
    [
        (RuntimeError("quebrou no meio"), "erro"),
        (sqlite3.OperationalError("database or disk is full"), "banco"),
    ],
)
def test_buscar_imprime_o_motivo_da_parada(
    isolado: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    erro: BaseException,
    parada: str,
) -> None:
    async def busca_quebrada(*_: object) -> int | None:
        raise erro

    monkeypatch.setattr(buscar, "executar_busca", busca_quebrada)
    assert buscar.executar(argparse.Namespace(comando="buscar")) == 1
    err = capsys.readouterr().err
    assert t("pt", f"execucao.parada.{parada}") in err
    assert "Rode jobot buscar de novo para tentar outra vez." in err
    assert "Clique em" not in err
    assert "Traceback" not in err and "quebrou no meio" not in err


@pytest.mark.parametrize("erro", [KeyboardInterrupt(), asyncio.CancelledError()])
def test_buscar_com_ctrl_c_sai_com_130(
    isolado: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    erro: BaseException,
) -> None:
    async def busca_interrompida(*_: object) -> int | None:
        raise erro

    monkeypatch.setattr(buscar, "executar_busca", busca_interrompida)
    assert buscar.executar(argparse.Namespace(comando="buscar")) == 130
    err = capsys.readouterr().err
    assert err.strip() == "Interrompido."
    assert "Clique em" not in err and "Traceback" not in err


def test_buscar_com_erro_grava_o_traceback_no_log(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def busca_quebrada(*_: object) -> int | None:
        raise RuntimeError("quebrou no meio")

    monkeypatch.setattr(buscar, "executar_busca", busca_quebrada)
    assert buscar.executar(argparse.Namespace(comando="buscar")) == 1
    log = (isolado / "logs" / "jobot.log").read_text("utf-8")
    assert "Traceback" in log and "RuntimeError: quebrou no meio" in log
