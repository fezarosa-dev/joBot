"""Migração 0006 (T192): índice que cobre o chip de fonte, sem tocar tabela, gatilho nem FTS5."""

import re
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from apoio.semear import inserir_vaga
from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0006_ocorrencia_fonte_vaga.sql"
INDICE = "ocorrencia_fonte_vaga"
ULTIMA = len(list(MIGRACOES.glob("*.sql")))


def _sql_da_0006() -> str:
    """Afirma que o arquivo existe antes de ler: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO.read_text("utf-8")


def _nomes(con: sqlite3.Connection, tipo: str) -> set[str]:
    return {n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type = ?", (tipo,))}


def _na_versao_cinco(tmp_path: Path) -> tuple[sqlite3.Connection, Path]:
    pasta = tmp_path / "ate_a_quinta"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:5]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho, pasta) == 5
    return con, caminho


def test_0006_so_cria_o_indice() -> None:
    sql = re.sub(r"--[^\n]*", "", _sql_da_0006())
    comandos = [c.strip() for c in sql.split(";") if c.strip()]
    assert len(comandos) == 1
    assert comandos[0].upper().startswith("CREATE INDEX")
    assert INDICE in comandos[0]


def test_0006_sobe_a_versao_e_mantem_o_resto(tmp_path: Path) -> None:
    _sql_da_0006()
    con, caminho = _na_versao_cinco(tmp_path)
    with closing(con):
        inserir_vaga(con)
        antes = (_nomes(con, "trigger"), _nomes(con, "table"), _nomes(con, "index"))
        assert INDICE not in antes[2]
        assert migrar(con, caminho) == ULTIMA
        assert con.execute("PRAGMA user_version").fetchone()[0] == ULTIMA
        gatilhos, tabelas, indices = (_nomes(con, t) for t in ("trigger", "table", "index"))
        assert (gatilhos, tabelas) == antes[:2]
        assert {"vaga_sem_delete", "evento_sem_update", "evento_sem_delete"} <= gatilhos
        assert indices == antes[2] | {INDICE}
        assert con.execute("SELECT COUNT(*) FROM ocorrencia").fetchone()[0] == 1
