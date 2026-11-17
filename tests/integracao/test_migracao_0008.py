"""Migração 0008 (T202): `fonte.com_login`, 0 nas linhas antigas e só 0 ou 1."""

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0008_fonte_com_login.sql"


def _arquivo_da_0008() -> Path:
    """Afirma que o arquivo existe antes de ler: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO


@pytest.fixture
def antes(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Path, Path]]:
    """Banco nas versões 0001 a 0007, mais a pasta onde a 0008 entra."""
    pasta = tmp_path / "ate_a_setima"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:7]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho, pasta) == 7
    yield con, caminho, pasta
    con.close()


def _aplicar_0008(con: sqlite3.Connection, caminho: Path, pasta: Path) -> None:
    shutil.copy(_arquivo_da_0008(), pasta)
    assert migrar(con, caminho, pasta) == 8


def test_0008_da_com_login_zero_nas_antigas(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    con, caminho, pasta = antes
    con.execute("INSERT INTO fonte (chave, leva, ligada) VALUES ('antiga', 'A', 1)")
    con.commit()

    _aplicar_0008(con, caminho, pasta)

    assert con.execute("SELECT com_login, ligada FROM fonte WHERE chave = 'antiga'").fetchall() == [
        (0, 1)
    ]


def test_0008_recusa_valor_fora(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    con, caminho, pasta = antes
    _aplicar_0008(con, caminho, pasta)
    con.execute("INSERT INTO fonte (chave, leva, com_login) VALUES ('boa', 'A', 1)")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO fonte (chave, leva, com_login) VALUES ('ruim', 'A', 2)")
