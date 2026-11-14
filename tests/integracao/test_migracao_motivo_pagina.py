"""Migração do motivo da falha de página (T128, A49): coluna `motivo` em `pagina_acompanhada`."""

import shutil
import sqlite3
from pathlib import Path

from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar


def _colunas(con: sqlite3.Connection) -> list[str]:
    return [r[1] for r in con.execute("PRAGMA table_info(pagina_acompanhada)")]


def _na_versao_um(tmp_path: Path) -> tuple[sqlite3.Connection, Path]:
    pasta = tmp_path / "so_a_primeira"
    pasta.mkdir()
    shutil.copy(MIGRACOES / "0001_inicial.sql", pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho, pasta) == 1
    return con, caminho


def test_migracao_motivo_da_pagina(tmp_path: Path) -> None:
    """Sem a migração a coluna não existe; com ela existe; tudo numa transação desfeita."""
    con, _ = _na_versao_um(tmp_path)
    depois = "".join(p.read_text("utf-8") for p in sorted(MIGRACOES.glob("*.sql"))[1:])
    assert "motivo" not in _colunas(con)
    con.executescript(f"BEGIN;\n{depois}\n")
    try:
        assert "motivo" in _colunas(con)
        con.execute("INSERT INTO pagina_acompanhada (url, nome) VALUES ('https://x.example', 'X')")
        assert con.execute("SELECT motivo FROM pagina_acompanhada").fetchall() == [(None,)]
        con.execute("UPDATE pagina_acompanhada SET estado='falhou', motivo='bloqueada'")
        assert con.execute("SELECT motivo FROM pagina_acompanhada").fetchall() == [("bloqueada",)]
    finally:
        con.execute("ROLLBACK")
    assert "motivo" not in _colunas(con)
    assert con.execute("SELECT count(*) FROM pagina_acompanhada").fetchone()[0] == 0


def test_migrar_do_banco_na_versao_anterior_mantem_as_paginas(tmp_path: Path) -> None:
    con, caminho = _na_versao_um(tmp_path)
    con.execute(
        "INSERT INTO pagina_acompanhada (url, nome, texto, estado) VALUES"
        " ('https://x.example', 'X', 'texto', 'falhou')"
    )
    con.commit()
    ultima = len(list(MIGRACOES.glob("*.sql")))
    assert ultima >= 2
    assert migrar(con, caminho) == ultima
    assert con.execute("SELECT nome, texto, estado, motivo FROM pagina_acompanhada").fetchall() == [
        ("X", "texto", "falhou", None)
    ]
    assert "motivo" in _colunas(con)
