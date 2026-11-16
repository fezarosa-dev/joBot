"""Migração 0010 (T270): `sessao_site` e `sessao_conta`, só CREATE TABLE, com CHECK e chave."""

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from jobot.banco.cadastros import semear
from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0010_sessao_site.sql"
AGORA = "2026-11-16T12:00:00+00:00"
MOTIVOS_SITE = [
    "sem_rede",
    "desafio",
    "bloqueio",
    "no_limite",
    "sem_tela",
    "sem_navegador",
    "em_uso",
    "erro",
    "esquecido",
]


def _arquivo_da_0010() -> Path:
    """Afirma que o arquivo existe: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Banco só até a 0010: migrações novas não mudam o esquema que este teste confere."""
    _arquivo_da_0010()
    pasta = tmp_path / "ate_a_decima"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:10]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    c.execute("PRAGMA foreign_keys = ON")
    assert migrar(c, caminho, pasta) == 10
    semear(c)
    yield c
    c.close()


def _aceita(con: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> bool:
    """Verdadeiro se o INSERT entra; `False` no `IntegrityError`. Desfaz o que entrou."""
    con.execute("SAVEPOINT t")
    try:
        con.execute(sql, params)
    except sqlite3.IntegrityError:
        return False
    finally:
        con.execute("ROLLBACK TO t")
        con.execute("RELEASE t")
    return True


def _site(con: sqlite3.Connection, fonte: str = "linkedin_logado", **campos: Any) -> bool:
    v = {"estado": "conectado", "motivo": None, **campos}
    return _aceita(
        con,
        "INSERT INTO sessao_site (fonte, estado, motivo, conferido_em) VALUES (?, ?, ?, ?)",
        (fonte, v["estado"], v["motivo"], AGORA),
    )


def _conta(con: sqlite3.Connection, conta: str = "gmail", **campos: Any) -> bool:
    v = {"estado": "conectado", "motivo": None, **campos}
    return _aceita(
        con,
        "INSERT INTO sessao_conta (conta, estado, motivo, conferido_em) VALUES (?, ?, ?, ?)",
        (conta, v["estado"], v["motivo"], AGORA),
    )


def test_check_estado(con: sqlite3.Connection) -> None:
    assert _site(con) is True  # controle positivo na mesma montagem
    assert _conta(con) is True
    assert _site(con, estado="logado") is False
    assert _conta(con, estado="logado") is False


def test_check_motivo_site_com_ramo_nulo(con: sqlite3.Connection) -> None:
    assert _site(con, estado="nao_conferiu", motivo=None) is True
    for motivo in MOTIVOS_SITE:
        assert _site(con, estado="nao_conferiu", motivo=motivo) is True, motivo
    assert _site(con, estado="nao_conferiu", motivo="outro") is False


def test_check_motivo_conta(con: sqlite3.Connection) -> None:
    for motivo in (None, "sem_rede", "bloqueio", "erro", "esquecido"):
        assert _conta(con, estado="nao_conferiu", motivo=motivo) is True, motivo
    assert _conta(con, estado="nao_conferiu", motivo="desafio") is False
    assert _conta(con, estado="nao_conferiu", motivo="em_uso") is False


def test_check_conta_so_gmail(con: sqlite3.Connection) -> None:
    assert _conta(con, "gmail") is True
    assert _conta(con, "outlook") is False


def test_fonte_desconhecida_recusada(con: sqlite3.Connection) -> None:
    assert _site(con, "linkedin_logado") is True
    assert _site(con, "nao_existe") is False


def test_versao_e_10(con: sqlite3.Connection) -> None:
    # mutante: a 0010 com nome fora da numeração (`migrar` a pula e a versão fica abaixo)
    assert _arquivo_da_0010().name == "0010_sessao_site.sql"
    assert con.execute("PRAGMA user_version").fetchone()[0] == 10
