"""Abre o banco com os pragmas do desenho (seção 7.3)."""

import sqlite3
from pathlib import Path


def abrir(caminho: Path) -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def tem_fts5(con: sqlite3.Connection) -> bool:
    """Confere se o SQLite tem FTS5 criando uma tabela de teste no esquema temporário."""
    try:
        con.execute("CREATE VIRTUAL TABLE temp.jobot_teste_fts5 USING fts5(x)")
    except sqlite3.OperationalError:
        return False
    con.execute("DROP TABLE temp.jobot_teste_fts5")
    return True
