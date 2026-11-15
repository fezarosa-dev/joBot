"""Migração 0007 (T201): `execucao` refeita para aceitar o tipo `login`, sem perder linha."""

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0007_execucao_login.sql"
AGORA = "2026-11-15T12:00:00+00:00"


def _arquivo_da_0007() -> Path:
    """Afirma que o arquivo existe antes de ler: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO


def _execucao(con: sqlite3.Connection, tipo: str, estado: str = "concluida", **extra: str) -> int:
    colunas = {
        "tipo": tipo,
        "motivo": "agora",
        "iniciada_em": AGORA,
        "batimento_em": AGORA,
        "estado": estado,
        **extra,
    }
    nomes = ", ".join(colunas)
    marcas = ", ".join("?" * len(colunas))
    cursor = con.execute(
        f"INSERT INTO execucao ({nomes}) VALUES ({marcas})", tuple(colunas.values())
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


@pytest.fixture
def antes(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Path, Path]]:
    """Banco nas versões 0001 a 0006, mais a pasta onde a 0007 entra."""
    pasta = tmp_path / "ate_a_sexta"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:6]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho, pasta) == 6
    yield con, caminho, pasta
    con.close()


def _aplicar_0007(con: sqlite3.Connection, caminho: Path, pasta: Path) -> None:
    shutil.copy(_arquivo_da_0007(), pasta)
    assert migrar(con, caminho, pasta) == 7


def _depois(antes: tuple[sqlite3.Connection, Path, Path]) -> sqlite3.Connection:
    """Aplica a 0007 no corpo do teste (não em fixture): sem o arquivo, o teste falha, não erra."""
    con, caminho, pasta = antes
    _aplicar_0007(con, caminho, pasta)
    return con


def test_0007_migra_sem_perder_linha(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    con, caminho, pasta = antes
    con.execute("INSERT INTO fonte (chave, leva) VALUES ('f', 'A')")
    ids = [
        _execucao(con, "busca", parada="fechado", terminada_em=AGORA, estado="interrompida"),
        _execucao(con, "descoberta", terminada_em=AGORA),
        _execucao(con, "paginas", estado="rodando"),
    ]
    for i in ids:
        con.execute("INSERT INTO saude (execucao_id, fonte, estado) VALUES (?, 'f', 'ok')", (i,))
        con.execute(
            "INSERT INTO execucao_fonte (execucao_id, fonte, comecou_em) VALUES (?, 'f', ?)",
            (i, AGORA),
        )
    con.commit()
    linhas = con.execute("SELECT * FROM execucao ORDER BY id").fetchall()

    _aplicar_0007(con, caminho, pasta)

    assert con.execute("SELECT * FROM execucao ORDER BY id").fetchall() == linhas
    assert [i for (i,) in con.execute("SELECT id FROM execucao ORDER BY id")] == ids
    assert con.execute("SELECT COUNT(*) FROM saude").fetchone()[0] == 3
    assert con.execute("SELECT COUNT(*) FROM execucao_fonte").fetchone()[0] == 3
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []


def test_0007_aceita_login(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    depois = _depois(antes)
    _execucao(depois, "login")
    with pytest.raises(sqlite3.IntegrityError):
        _execucao(depois, "outro")


def test_0007_parada_continua_valendo(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    depois = _depois(antes)
    with pytest.raises(sqlite3.IntegrityError):
        _execucao(depois, "login", parada="xyz")
    depois.execute(
        "INSERT INTO execucao (tipo, motivo, iniciada_em, batimento_em, estado, parada)"
        " VALUES ('login', 'agora', ?, ?, 'concluida', NULL)",
        (AGORA, AGORA),
    )


def test_0007_indice_unico_continua(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    depois = _depois(antes)
    _execucao(depois, "login", estado="rodando")
    with pytest.raises(sqlite3.IntegrityError):
        _execucao(depois, "login", estado="rodando")


def test_0007_chaves_estrangeiras_apontam_para_execucao(
    antes: tuple[sqlite3.Connection, Path, Path],
) -> None:
    depois = _depois(antes)
    for filha in ("saude", "execucao_fonte"):
        pais = {linha[2] for linha in depois.execute(f"PRAGMA foreign_key_list({filha})")}
        assert "execucao" in pais
        assert "execucao_nova" not in pais
    tabelas = {n for (n,) in depois.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "execucao_nova" not in tabelas
