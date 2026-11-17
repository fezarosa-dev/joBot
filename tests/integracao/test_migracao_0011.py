"""Migração 0011 (T281): `candidatura`, só CREATE, com CHECK, chave e gatilho contra DELETE."""

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0011_candidatura.sql"
AGORA = "2026-11-16T12:00:00+00:00"


def _arquivo_da_0011() -> Path:
    """Afirma que o arquivo existe: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO


@pytest.fixture
def antes(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Path, Path]]:
    """Banco nas versões 0001 a 0010, mais a pasta onde a 0011 entra."""
    _arquivo_da_0011()
    pasta = tmp_path / "ate_a_decima"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:10]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    con.execute("PRAGMA foreign_keys = ON")
    assert migrar(con, caminho, pasta) == 10
    yield con, caminho, pasta
    con.close()


def _aplicar_0011(con: sqlite3.Connection, caminho: Path, pasta: Path) -> None:
    shutil.copy(_arquivo_da_0011(), pasta)
    assert migrar(con, caminho, pasta) == 11


def _vaga(con: sqlite3.Connection, vaga_id: int) -> None:
    con.execute(
        "INSERT INTO vaga (id, url_hash, titulo, empresa, url, primeira_vista_em,"
        " ultima_vista_em, versao_regras) VALUES (?, ?, 't', 'e', ?, '2026-11-13',"
        " '2026-11-13', 'v1')",
        (vaga_id, f"h{vaga_id}", f"https://x.test/{vaga_id}"),
    )


@pytest.fixture
def con(antes: tuple[sqlite3.Connection, Path, Path]) -> sqlite3.Connection:
    """Banco só até a 0011, com a vaga 1: migrações novas não mudam o que este teste confere."""
    c, caminho, pasta = antes
    _aplicar_0011(c, caminho, pasta)
    _vaga(c, 1)
    c.commit()
    return c


def _recusa(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> bool:
    """Verdadeiro se o banco recusa o comando (`IntegrityError`). Desfaz o que entrou."""
    con.execute("SAVEPOINT t")
    try:
        con.execute(sql, params)
    except sqlite3.IntegrityError:
        return True
    finally:
        con.execute("ROLLBACK TO t")
        con.execute("RELEASE t")
    return False


def _inserir(perguntar: int, vaga_id: int = 1) -> tuple[str, tuple[Any, ...]]:
    return (
        "INSERT INTO candidatura (vaga_id, abriu_em, perguntar) VALUES (?, ?, ?)",
        (vaga_id, AGORA, perguntar),
    )


def test_candidatura_sem_delete(con: sqlite3.Connection) -> None:
    con.execute(*_inserir(1))
    con.commit()
    assert _recusa(con, "DELETE FROM candidatura WHERE vaga_id = 1") is True
    assert con.execute("SELECT count(*) FROM candidatura").fetchone()[0] == 1


def test_perguntar_so_0_ou_1(con: sqlite3.Connection) -> None:
    assert _recusa(con, *_inserir(0)) is False  # controle positivo na mesma montagem
    assert _recusa(con, *_inserir(1)) is False
    assert _recusa(con, *_inserir(2)) is True


def test_vaga_id_referencia_vaga(con: sqlite3.Connection) -> None:
    assert _recusa(con, *_inserir(1, vaga_id=1)) is False
    assert _recusa(con, *_inserir(1, vaga_id=999)) is True


def test_antes_nada_se_perde(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    con, caminho, pasta = antes
    for vaga_id in (1, 2):
        _vaga(con, vaga_id)
    con.execute("UPDATE vaga SET status = 'salva', status_em = ? WHERE id = 2", (AGORA,))
    con.execute(
        "INSERT INTO evento (vaga_id, acao, de, para, criado_em)"
        " VALUES (2, 'salvou', 'nova', 'salva', ?)",
        (AGORA,),
    )
    con.commit()
    vagas = con.execute("SELECT * FROM vaga ORDER BY id").fetchall()
    eventos = con.execute("SELECT * FROM evento ORDER BY id").fetchall()

    _aplicar_0011(con, caminho, pasta)

    assert con.execute("SELECT * FROM vaga ORDER BY id").fetchall() == vagas
    assert con.execute("SELECT * FROM evento ORDER BY id").fetchall() == eventos
    assert con.execute("PRAGMA user_version").fetchone()[0] == 11
