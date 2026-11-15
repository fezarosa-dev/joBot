"""Migração 0005 (T162): índices dos filtros da 0.2.0, sem tocar tabela, gatilho nem FTS5."""

import re
import shutil
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jobot.banco.conexao import abrir
from jobot.banco.gravacao import gravar_escopo
from jobot.banco.migrar import MIGRACOES, migrar
from jobot.nucleo.coletores.base import ResultadoEscopo
from jobot.nucleo.coletores.executor import SaidaEscopo
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.tratamento.tratar import tratar

ARQUIVO = MIGRACOES / "0005_filtros.sql"
INDICES = {
    "local_vaga_vaga",
    "local_vaga_pais",
    "vaga_publicada_ou_vista",
    "vaga_sal_baixo_brl",
    "vaga_sal_alto_brl",
}
ULTIMA = len(list(MIGRACOES.glob("*.sql")))
T0 = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
ISO = "2026-11-13T12:00:00+00:00"


def _sql_da_0005() -> str:
    """Afirma que o arquivo existe antes de ler: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO.read_text("utf-8")


def _na_versao_quatro(tmp_path: Path) -> tuple[sqlite3.Connection, Path]:
    pasta = tmp_path / "ate_a_quarta"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:4]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho, pasta) == 4
    con.execute("INSERT INTO fonte (chave, leva) VALUES ('remotive', 'A')")
    con.commit()
    return con, caminho


def _nomes(con: sqlite3.Connection, tipo: str) -> set[str]:
    return {n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type = ?", (tipo,))}


def _contagens(con: sqlite3.Connection) -> list[int]:
    return [
        con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("vaga", "local_vaga", "ocorrencia", "evento")
    ]


def _gravar(
    con: sqlite3.Connection, vagas: list[VagaColetada], agora: datetime, estado: str = "ok"
) -> None:
    vagas = [replace(v, escopo="", fonte="remotive") for v in vagas]
    cur = con.execute(
        "INSERT INTO execucao (tipo, motivo, iniciada_em, batimento_em, estado)"
        " VALUES ('busca', 'agenda', ?, ?, 'concluida')",
        (agora.isoformat(), agora.isoformat()),
    )
    con.commit()
    assert cur.lastrowid is not None
    resultado = ResultadoEscopo(tuple(vagas), estado, None, 1)  # type: ignore[arg-type]
    saida = SaidaEscopo("remotive", "", resultado, 10, {}, (), ())
    gravar_escopo(con, cur.lastrowid, saida, [tratar(v) for v in vagas], agora)


def _vaga(n: int, **campos: object) -> VagaColetada:
    base: dict[str, object] = {
        "fonte": "remotive",
        "escopo": "",
        "url": f"https://exemplo.test/vagas/{n}",
        "titulo": f"Desenvolvedor Python {n}",
        "empresa": "Acme",
        "descricao_formato": "texto",
        "descricao": "Vaga de desenvolvedor Python remoto.",
        "locais": ("São Paulo, SP",),
    }
    return VagaColetada(**(base | campos))  # type: ignore[arg-type]


def test_migracao_0005_isolada(tmp_path: Path) -> None:
    con, _ = _na_versao_quatro(tmp_path)
    with closing(con):
        sql = _sql_da_0005()
        antes = (_nomes(con, "trigger"), _nomes(con, "table"))
        assert not INDICES & _nomes(con, "index")
        con.executescript(f"BEGIN;\n{sql}\n")
        try:
            assert INDICES <= _nomes(con, "index")
            assert (_nomes(con, "trigger"), _nomes(con, "table")) == antes
        finally:
            con.execute("ROLLBACK")
        assert not INDICES & _nomes(con, "index")


def test_0005_so_cria_indices() -> None:
    sql = re.sub(r"--[^\n]*", "", _sql_da_0005())
    comandos = [c.strip() for c in sql.split(";") if c.strip()]
    assert len(comandos) == len(INDICES)
    assert all(c.upper().startswith("CREATE INDEX") for c in comandos)


def test_0005_em_banco_semeado_mantem_as_vagas(tmp_path: Path) -> None:
    _sql_da_0005()
    con, caminho = _na_versao_quatro(tmp_path)
    with closing(con):
        _gravar(con, [_vaga(1, publicada_em=T0 - timedelta(days=2)), _vaga(2)], T0)
        antes = _contagens(con)
        assert antes[0] == 2
        assert antes[1] > 0
        assert antes[2] == 2
        assert migrar(con, caminho) == ULTIMA
        assert INDICES <= _nomes(con, "index")
        assert _contagens(con) == antes
        _gravar(con, [_vaga(1, titulo="Novo título")], T0 + timedelta(hours=1))
        titulo = con.execute("SELECT titulo FROM vaga WHERE url LIKE '%/1'").fetchone()[0]
        assert titulo == "Novo título"
        assert con.execute("SELECT COUNT(*) FROM vaga").fetchone()[0] == 2


def test_indice_de_data_recusa_now(tmp_path: Path) -> None:
    _sql_da_0005()
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    with closing(con):
        assert migrar(con, caminho) == ULTIMA
        con.execute("INSERT INTO fonte (chave, leva) VALUES ('remotive', 'A')")
        _gravar(con, [_vaga(1)], T0)
        with pytest.raises(sqlite3.OperationalError, match="non-deterministic"):
            con.execute("UPDATE vaga SET publicada_em = 'now'")
        con.execute("UPDATE vaga SET publicada_em = NULL")
        con.execute("UPDATE vaga SET publicada_em = ?", (ISO,))
