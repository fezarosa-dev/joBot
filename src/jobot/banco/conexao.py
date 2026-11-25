"""Abre o banco com os pragmas do desenho (seção 7.3)."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def abrir(caminho: Path) -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA secure_delete=ON")  # o que se apaga (perfil) vira zero no arquivo
    return con


def tem_fts5(con: sqlite3.Connection) -> bool:
    """Confere se o SQLite tem FTS5 criando uma tabela de teste no esquema temporário."""
    try:
        con.execute("CREATE VIRTUAL TABLE temp.jobot_teste_fts5 USING fts5(x)")
    except sqlite3.OperationalError:
        return False
    con.execute("DROP TABLE temp.jobot_teste_fts5")
    return True


@contextmanager
def quem_abriu_confirma(con: sqlite3.Connection) -> Iterator[None]:
    """Confirma, ou desfaz no erro, só se não havia transação aberta: senão, quem abriu confirma."""
    ja_aberta = con.in_transaction
    try:
        yield
    except BaseException:
        if not ja_aberta:
            con.rollback()
        raise
    if not ja_aberta:
        con.commit()
