"""Banco e migrações (desenho 7.3 e 7.4; plano T03)."""

import shutil
import sqlite3
from pathlib import Path

import pytest

from jobot.banco import migrar as modulo_migrar
from jobot.banco.conexao import abrir, tem_fts5
from jobot.banco.migrar import MIGRACOES, BancoMaisNovo, migrar

TABELAS = {
    "fonte",
    "empresa",
    "empresa_sugerida",
    "execucao",
    "saude",
    "vaga",
    "local_vaga",
    "ocorrencia",
    "busca",
    "encaixe",
    "correcao",
    "evento",
    "cotacao",
    "cache_http",
    "enriquecimento",
    "pagina_acompanhada",
    "mudanca_pagina",
    "config",
}
INDICES = {
    "execucao_uma_por_tipo",
    "vaga_lista",
    "vaga_primeira_vista",
    "vaga_prazo",
    "vaga_empresa",
    "local_vaga_uf",
    "ocorrencia_escopo",
    "ocorrencia_vaga",
    "encaixe_ordem",
}
GATILHOS = {"vaga_sem_delete", "evento_sem_update", "evento_sem_delete"}
AGORA = "2026-11-13T12:00:00Z"


def _nomes(con: sqlite3.Connection, tipo: str) -> set[str]:
    linhas = con.execute("SELECT name FROM sqlite_master WHERE type = ?", (tipo,)).fetchall()
    return {nome for (nome,) in linhas}


def _gatilhos_fts(con: sqlite3.Connection) -> list[str]:
    linhas = con.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND sql LIKE '%vaga_fts%'"
    ).fetchall()
    return [sql.upper() for (sql,) in linhas]


def _versao(con: sqlite3.Connection) -> int:
    versao: int = con.execute("PRAGMA user_version").fetchone()[0]
    return versao


def _novo(tmp_path: Path) -> tuple[sqlite3.Connection, Path]:
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    migrar(con, caminho)
    return con, caminho


def _vaga(con: sqlite3.Connection, url_hash: str = "h1", oculta_manual: int = 0) -> int:
    cursor = con.execute(
        "INSERT INTO vaga (url_hash, titulo, empresa, url, primeira_vista_em, ultima_vista_em,"
        " oculta_manual, versao_regras) VALUES (?, 'Dev', 'Acme', 'https://x/1', ?, ?, ?, 'v1')",
        (url_hash, AGORA, AGORA, oculta_manual),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _vaga_com_filhos(con: sqlite3.Connection) -> int:
    con.execute("INSERT INTO fonte (chave, leva) VALUES ('remotive', 'A')")
    vaga_id = _vaga(con)
    con.execute(
        "INSERT INTO ocorrencia (vaga_id, fonte, url, coletada, primeira_vista_em,"
        " ultima_vista_em) VALUES (?, 'remotive', 'https://x/1', '{}', ?, ?)",
        (vaga_id, AGORA, AGORA),
    )
    con.execute(
        "INSERT INTO local_vaga (vaga_id, cidade, uf, pais) VALUES (?, 'Recife', 'PE', 'BR')",
        (vaga_id,),
    )
    con.commit()
    return vaga_id


def _pasta_com(tmp_path: Path, **extras: str) -> Path:
    pasta = tmp_path / "migracoes"
    pasta.mkdir(exist_ok=True)
    shutil.copy(MIGRACOES / "0001_inicial.sql", pasta)
    for nome, sql in extras.items():
        (pasta / f"{nome}.sql").write_text(sql, encoding="utf-8")
    return pasta


def test_pragmas(tmp_path: Path) -> None:
    con = abrir(tmp_path / "jobot.db")
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_vazio_recebe_esquema(tmp_path: Path) -> None:
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho) == 1
    assert _versao(con) == 1
    tabelas = _nomes(con, "table")
    assert TABELAS <= tabelas
    assert INDICES <= _nomes(con, "index")
    assert GATILHOS <= _nomes(con, "trigger")
    if tem_fts5(con):
        assert "vaga_fts" in tabelas
        gatilhos = _gatilhos_fts(con)
        assert len(gatilhos) == 2
        assert sum("AFTER INSERT ON VAGA" in g for g in gatilhos) == 1
        assert sum("AFTER UPDATE" in g for g in gatilhos) == 1
        assert not any("DELETE ON VAGA" in g for g in gatilhos)
        # o gatilho de UPDATE mantém o índice igual à vaga
        vaga_id = _vaga(con)
        con.execute("UPDATE vaga SET titulo = 'Analista de dados' WHERE id = ?", (vaga_id,))
        achadas = con.execute("SELECT rowid FROM vaga_fts WHERE vaga_fts MATCH 'analista'")
        assert achadas.fetchall() == [(vaga_id,)]
        assert con.execute("SELECT rowid FROM vaga_fts WHERE vaga_fts MATCH 'dev'").fetchall() == []
    # oculta_manual aceita só -1, 0 e 1 (DP2)
    _vaga(con, "h-menos-um", -1)
    with pytest.raises(sqlite3.IntegrityError):
        _vaga(con, "h-dois", 2)


def test_migra_sem_fts5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_migrar, "tem_fts5", lambda con: False)
    con, _ = _novo(tmp_path)
    assert _versao(con) == 1
    assert "vaga_fts" not in _nomes(con, "table")
    assert _gatilhos_fts(con) == []
    _vaga(con)


def test_uma_execucao_rodando_por_tipo(tmp_path: Path) -> None:
    con, _ = _novo(tmp_path)
    sql = (
        "INSERT INTO execucao (tipo, motivo, iniciada_em, batimento_em, estado)"
        " VALUES (?, 'agenda', ?, ?, ?)"
    )
    con.execute(sql, ("busca", AGORA, AGORA, "rodando"))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(sql, ("busca", AGORA, AGORA, "rodando"))
    con.execute(sql, ("descoberta", AGORA, AGORA, "rodando"))
    con.execute(sql, ("busca", AGORA, AGORA, "concluida"))


def test_evento_so_acrescimo(tmp_path: Path) -> None:
    con, _ = _novo(tmp_path)
    vaga_id = _vaga(con)
    con.execute(
        "INSERT INTO evento (vaga_id, acao, criado_em) VALUES (?, 'salvou', ?)", (vaga_id, AGORA)
    )
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE evento SET acao = 'ocultou'")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM evento")
    assert con.execute("SELECT acao FROM evento").fetchall() == [("salvou",)]


def test_delete_em_vaga_recusado(tmp_path: Path) -> None:
    con, _ = _novo(tmp_path)
    vaga_id = _vaga_com_filhos(con)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM vaga WHERE id = ?", (vaga_id,))
    con.commit()
    assert con.execute("SELECT count(*) FROM vaga").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM ocorrencia").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM local_vaga").fetchone()[0] == 1


def _reconstroi_vaga(caminho: Path) -> str:
    """0002 que reconstrói vaga do jeito que o SQLite pede para mudar restrição."""
    con = sqlite3.connect(caminho)
    sql: str = con.execute("SELECT sql FROM sqlite_master WHERE name = 'vaga'").fetchone()[0]
    con.close()
    nova = sql.replace("CREATE TABLE vaga", "CREATE TABLE vaga_nova", 1)
    return (
        f"{nova};\n"
        "INSERT INTO vaga_nova SELECT * FROM vaga;\n"
        "DROP TABLE vaga;\n"
        "ALTER TABLE vaga_nova RENAME TO vaga;\n"
    )


def test_migracao_seguinte_nao_perde_dado(tmp_path: Path) -> None:
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    migrar(con, caminho, _pasta_com(tmp_path))
    vaga_id = _vaga_com_filhos(con)
    pasta = _pasta_com(tmp_path, **{"0002_reconstroi_vaga": _reconstroi_vaga(caminho)})

    assert migrar(con, caminho, pasta) == 2

    assert _versao(con) == 2
    assert con.execute("SELECT id, titulo FROM vaga").fetchall() == [(vaga_id, "Dev")]
    assert con.execute("SELECT vaga_id FROM ocorrencia").fetchall() == [(vaga_id,)]
    assert con.execute("SELECT vaga_id, cidade FROM local_vaga").fetchall() == [(vaga_id, "Recife")]
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_migracao_com_chave_quebrada_e_desfeita(tmp_path: Path) -> None:
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    migrar(con, caminho, _pasta_com(tmp_path))
    quebra = (
        "INSERT INTO fonte (chave, leva) VALUES ('remotive', 'A');\n"
        "INSERT INTO ocorrencia (vaga_id, fonte, url, coletada, primeira_vista_em,"
        " ultima_vista_em) VALUES (999, 'remotive', 'https://x/9', '{}',"
        f" '{AGORA}', '{AGORA}');\n"
    )
    pasta = _pasta_com(tmp_path, **{"0002_quebra": quebra})

    with pytest.raises(sqlite3.IntegrityError):
        migrar(con, caminho, pasta)

    assert _versao(con) == 1
    assert con.execute("SELECT count(*) FROM ocorrencia").fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM fonte").fetchone()[0] == 0
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert not con.in_transaction


def test_copia_antes_de_migrar(tmp_path: Path) -> None:
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    migrar(con, caminho, _pasta_com(tmp_path))
    _vaga(con)
    con.commit()
    for n in range(2, 7):
        pasta = _pasta_com(tmp_path, **{f"{n:04d}_tabela": f"CREATE TABLE t{n} (x);"})
        assert migrar(con, caminho, pasta) == n
        copia = tmp_path / f"jobot.db.antes-v{n - 1}"
        assert copia.exists()
        antiga = sqlite3.connect(copia)
        assert _versao(antiga) == n - 1
        assert antiga.execute("SELECT count(*) FROM vaga").fetchone()[0] == 1
        antiga.close()

    copias = sorted(p.name for p in tmp_path.glob("jobot.db.antes-v*"))
    assert copias == ["jobot.db.antes-v3", "jobot.db.antes-v4", "jobot.db.antes-v5"]


def test_banco_mais_novo_recusa_sem_tocar(tmp_path: Path) -> None:
    caminho = tmp_path / "jobot.db"
    con, _ = _novo(tmp_path)
    con.execute("PRAGMA user_version = 99")
    con.close()
    antes = caminho.read_bytes()

    con = abrir(caminho)
    with pytest.raises(BancoMaisNovo):
        migrar(con, caminho)
    con.close()

    assert caminho.read_bytes() == antes
    assert list(tmp_path.glob("jobot.db.antes-v*")) == []
