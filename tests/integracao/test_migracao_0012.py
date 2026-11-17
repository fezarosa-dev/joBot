"""Migração 0012 (T403): `perfil`, `habilidades_vaga` e `encaixe.nivel_base` (desenho 5.4, 8)."""

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0012_ia.sql"
AGORA = "2026-11-17T12:00:00+00:00"


def _arquivo_da_0012() -> Path:
    """Afirma que o arquivo existe: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO


@pytest.fixture
def antes(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Path, Path]]:
    """Banco nas versões 0001 a 0011, mais a pasta onde a 0012 entra."""
    _arquivo_da_0012()
    pasta = tmp_path / "ate_a_decima_primeira"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:11]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    con.execute("PRAGMA foreign_keys = ON")
    assert migrar(con, caminho, pasta) == 11
    yield con, caminho, pasta
    con.close()


def _aplicar_0012(con: sqlite3.Connection, caminho: Path, pasta: Path) -> None:
    shutil.copy(_arquivo_da_0012(), pasta)
    assert migrar(con, caminho, pasta) == 12


def _vaga(con: sqlite3.Connection, vaga_id: int) -> None:
    con.execute(
        "INSERT INTO vaga (id, url_hash, titulo, empresa, url, primeira_vista_em,"
        " ultima_vista_em, versao_regras) VALUES (?, ?, 't', 'e', ?, '2026-11-13',"
        " '2026-11-13', 'v1')",
        (vaga_id, f"h{vaga_id}", f"https://x.test/{vaga_id}"),
    )


def _busca(con: sqlite3.Connection) -> int:
    cur = con.execute("INSERT INTO busca (nome, criada_em) VALUES ('b', ?)", (AGORA,))
    assert cur.lastrowid is not None
    return cur.lastrowid


@pytest.fixture
def con(antes: tuple[sqlite3.Connection, Path, Path]) -> sqlite3.Connection:
    """Banco só até a 0012, com a vaga 1 e uma busca: migrações novas não mudam o que se confere."""
    c, caminho, pasta = antes
    _aplicar_0012(c, caminho, pasta)
    _vaga(c, 1)
    _busca(c)
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


def _colunas(con: sqlite3.Connection, tabela: str) -> dict[str, int]:
    """Nome da coluna -> posição na chave primária (0 = fora dela)."""
    return {nome: pk for _, nome, _, _, _, pk in con.execute(f"PRAGMA table_info({tabela})")}


def test_versao_sobe_para_12(con: sqlite3.Connection) -> None:
    assert con.execute("PRAGMA user_version").fetchone()[0] == 12


def test_perfil_tem_uma_linha_so(con: sqlite3.Connection) -> None:
    assert _colunas(con, "perfil") == {"id": 1, "habilidades": 0, "atualizado_em": 0}
    sql = "INSERT INTO perfil (id, habilidades, atualizado_em) VALUES (?, '[]', ?)"
    assert _recusa(con, sql, (1, AGORA)) is False  # controle positivo na mesma montagem
    assert _recusa(con, sql, (2, AGORA)) is True


def test_habilidades_vaga_colunas_e_chave(con: sqlite3.Connection) -> None:
    assert _colunas(con, "habilidades_vaga") == {
        "vaga_id": 1,
        "chave": 0,
        "pede": 0,
        "backend": 0,
        "modelo": 0,
        "versao": 0,
        "feito_em": 0,
        "falha": 0,
        "falha_em": 0,
        "falha_chave": 0,
        "falha_backend": 0,
        "tentativas": 0,
    }
    sql = "INSERT INTO habilidades_vaga (vaga_id) VALUES (?)"
    assert _recusa(con, sql, (1,)) is False
    assert _recusa(con, sql, (999,)) is True  # vaga_id referencia vaga


def test_falha_so_motivo_da_vaga(con: sqlite3.Connection) -> None:
    sql = "INSERT INTO habilidades_vaga (vaga_id, falha) VALUES (1, ?)"
    for motivo in (None, "recusa", "formato", "contexto"):
        assert _recusa(con, sql, (motivo,)) is False, motivo
    for motivo in ("sem_chave", "limite", "servico_fora", ""):  # do backend: não marca a vaga
        assert _recusa(con, sql, (motivo,)) is True, motivo


def test_tentativas_nao_negativas(con: sqlite3.Connection) -> None:
    sql = "INSERT INTO habilidades_vaga (vaga_id, tentativas) VALUES (1, ?)"
    assert _recusa(con, sql, (0,)) is False
    assert _recusa(con, sql, (-1,)) is True


def test_nivel_base_mesmo_check_de_nivel(con: sqlite3.Connection) -> None:
    sql = (
        "INSERT INTO encaixe (busca_id, vaga_id, nota, nivel, motivos, nivel_base)"
        " VALUES (1, 1, 50, ?, '[]', ?)"
    )
    for nivel in (None, "bom", "medio", "fraco"):
        assert _recusa(con, sql, (nivel, nivel)) is False, nivel
        assert _recusa(con, sql, ("bom", nivel)) is False, nivel
    assert _recusa(con, sql, ("bom", "otimo")) is True
    assert _recusa(con, sql, ("otimo", "bom")) is True  # o CHECK de nivel continua


def test_antes_nada_se_perde(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    con, caminho, pasta = antes
    for vaga_id in (1, 2, 3):
        _vaga(con, vaga_id)
    busca_id = _busca(con)
    for vaga_id, nota, nivel, oculta in (
        (1, 80, "bom", None),
        (2, 55, "medio", None),
        (3, None, None, "regra"),
    ):
        con.execute(
            "INSERT INTO encaixe (busca_id, vaga_id, nota, nivel, motivos, oculta_motivo)"
            ' VALUES (?, ?, ?, ?, \'[{"chave": "x"}]\', ?)',
            (busca_id, vaga_id, nota, nivel, oculta),
        )
    con.execute("UPDATE vaga SET status = 'salva', status_em = ? WHERE id = 2", (AGORA,))
    con.execute(
        "INSERT INTO evento (vaga_id, acao, de, para, criado_em)"
        " VALUES (2, 'salvou', 'nova', 'salva', ?)",
        (AGORA,),
    )
    con.execute("INSERT INTO candidatura (vaga_id, abriu_em) VALUES (2, ?)", (AGORA,))
    con.execute("INSERT INTO config (chave, valor) VALUES ('destaques_n', '7')")
    con.commit()
    tabelas = ("vaga", "evento", "candidatura", "config", "busca")
    guardadas = {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabelas}
    colunas_encaixe = "busca_id, vaga_id, nota, nivel, motivos, oculta_motivo"
    encaixes = con.execute(f"SELECT {colunas_encaixe} FROM encaixe ORDER BY vaga_id").fetchall()
    assert len(encaixes) == 3

    _aplicar_0012(con, caminho, pasta)

    for tabela, linhas in guardadas.items():
        assert con.execute(f"SELECT * FROM {tabela} ORDER BY 1").fetchall() == linhas, tabela
    depois = con.execute(f"SELECT {colunas_encaixe} FROM encaixe ORDER BY vaga_id").fetchall()
    assert depois == encaixes
    # sem o critério de habilidades, o nível sem ele é o próprio nível (D188)
    pares = con.execute("SELECT vaga_id, nivel, nivel_base FROM encaixe ORDER BY vaga_id")
    assert pares.fetchall() == [(1, "bom", "bom"), (2, "medio", "medio"), (3, None, None)]
    assert con.execute("SELECT count(*) FROM perfil").fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM habilidades_vaga").fetchone()[0] == 0
    assert con.execute("PRAGMA user_version").fetchone()[0] == 12
