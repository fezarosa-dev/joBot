"""Migração 0009 (T246): tabelas `andamento` e `andamento_fonte`, sem mexer nas de hoje."""

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0009_andamento.sql"
AGORA = "2026-11-16T12:00:00+00:00"


def _arquivo_da_0009() -> Path:
    """Afirma que o arquivo existe antes de ler: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO


@pytest.fixture
def antes(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Path, Path]]:
    """Banco nas versões 0001 a 0008, mais a pasta onde a 0009 entra."""
    pasta = tmp_path / "ate_a_oitava"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:8]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho, pasta) == 8
    yield con, caminho, pasta
    con.close()


def _aplicar_0009(con: sqlite3.Connection, caminho: Path, pasta: Path) -> None:
    shutil.copy(_arquivo_da_0009(), pasta)
    assert migrar(con, caminho, pasta) == 9


def _execucao(con: sqlite3.Connection) -> int:
    cursor = con.execute(
        "INSERT INTO execucao (tipo, motivo, iniciada_em, batimento_em, estado)"
        " VALUES ('busca', 'agora', ?, ?, 'rodando')",
        (AGORA, AGORA),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _colunas(con: sqlite3.Connection, tabela: str) -> dict[str, tuple[str, int, int]]:
    """Nome -> (tipo, notnull, pk)."""
    linhas = con.execute(f"PRAGMA table_info({tabela})").fetchall()
    return {r[1]: (r[2], r[3], r[5]) for r in linhas}


def test_migracao_andamento_cria_as_tabelas(
    antes: tuple[sqlite3.Connection, Path, Path],
) -> None:
    con, caminho, pasta = antes
    _aplicar_0009(con, caminho, pasta)

    assert _colunas(con, "andamento") == {
        "execucao_id": ("INTEGER", 0, 1),
        "etapas": ("TEXT", 1, 0),
        "etapa": ("TEXT", 1, 0),
        "feitas": ("INTEGER", 0, 0),
        "total": ("INTEGER", 0, 0),
        "total_planejado": ("INTEGER", 0, 0),
        "partida": ("REAL", 1, 0),
        "mudou_em": ("TEXT", 1, 0),
    }
    assert _colunas(con, "andamento_fonte") == {
        "execucao_id": ("INTEGER", 1, 1),
        "fonte": ("TEXT", 1, 2),
        "estado": ("TEXT", 1, 0),
        "feitas": ("INTEGER", 1, 0),
        "total": ("INTEGER", 1, 0),
        "espera_ate": ("TEXT", 0, 0),
        "espera_motivo": ("TEXT", 0, 0),
    }
    con.execute("INSERT INTO fonte (chave, leva) VALUES ('a', 'A')")
    eid = _execucao(con)
    with pytest.raises(sqlite3.IntegrityError):  # etapa fora da lista
        con.execute(
            "INSERT INTO andamento (execucao_id, etapas, etapa, mudou_em)"
            " VALUES (?, '[]', 'inventada', ?)",
            (eid, AGORA),
        )
    with pytest.raises(sqlite3.IntegrityError):  # estado fora da lista
        con.execute(
            "INSERT INTO andamento_fonte (execucao_id, fonte, estado, total)"
            " VALUES (?, 'a', 'inventado', 1)",
            (eid,),
        )
    with pytest.raises(sqlite3.IntegrityError):  # motivo de espera fora da lista
        con.execute(
            "INSERT INTO andamento_fonte (execucao_id, fonte, estado, total, espera_motivo)"
            " VALUES (?, 'a', 'esperando', 1, 'inventado')",
            (eid,),
        )
    with pytest.raises(sqlite3.IntegrityError):  # fonte que não existe
        con.execute(
            "INSERT INTO andamento_fonte (execucao_id, fonte, estado, total)"
            " VALUES (?, 'nao_existe', 'fila', 1)",
            (eid,),
        )
    con.execute(
        "INSERT INTO andamento (execucao_id, etapas, etapa, mudou_em)"
        " VALUES (?, '[]', 'preparando', ?)",
        (eid, AGORA),
    )
    con.execute(
        "INSERT INTO andamento_fonte (execucao_id, fonte, estado, total, espera_motivo)"
        " VALUES (?, 'a', 'esperando', 1, NULL)",
        (eid,),
    )


def test_migracao_andamento_sobre_banco_antigo(
    antes: tuple[sqlite3.Connection, Path, Path],
) -> None:
    con, caminho, pasta = antes
    con.execute("INSERT INTO fonte (chave, leva) VALUES ('a', 'A')")
    eid = _execucao(con)
    con.execute(
        "INSERT INTO saude (execucao_id, fonte, escopo, estado) VALUES (?, 'a', '', 'ok')", (eid,)
    )
    con.execute(
        "INSERT INTO execucao_fonte (execucao_id, fonte, comecou_em) VALUES (?, 'a', ?)",
        (eid, AGORA),
    )
    con.commit()

    _aplicar_0009(con, caminho, pasta)

    assert con.execute("SELECT id, tipo, estado FROM execucao").fetchall() == [
        (eid, "busca", "rodando")
    ]
    assert con.execute("SELECT execucao_id, fonte, estado FROM saude").fetchall() == [
        (eid, "a", "ok")
    ]
    assert con.execute("SELECT execucao_id, fonte FROM execucao_fonte").fetchall() == [(eid, "a")]
    assert con.execute("SELECT count(*) FROM andamento").fetchone()[0] == 0
