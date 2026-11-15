"""Candidatas a detalhe, lidas do banco (plano T200; desenho 8.1, DR-70)."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import Candidata, candidatas_a_detalhe
from jobot.banco.migrar import migrar
from jobot.nucleo.url import canonica, hash_url

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
relogio = RelogioFalso(AGORA)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    yield c
    c.close()


def _dias(n: float) -> str:
    return (AGORA - timedelta(days=n)).isoformat()


def _vaga(con: sqlite3.Connection, n: int, **campos: Any) -> int:
    campos = {"descricao_texto": "", "url": f"https://a.exemplo.test/vagas/{n}"} | campos
    return int(inserir_vaga(con, fonte=str(campos.pop("fonte", "a")), **campos))


def _oid(con: sqlite3.Connection, vaga_id: int) -> int:
    return int(con.execute("SELECT id FROM ocorrencia WHERE vaga_id = ?", (vaga_id,)).fetchone()[0])


def test_candidatas_devolvem_ocorrencia_id_e_mais_novas_primeiro(con: sqlite3.Connection) -> None:
    velha = _vaga(con, 1, primeira_vista_em=_dias(5))
    empate_1 = _vaga(con, 2, primeira_vista_em=_dias(2))
    empate_2 = _vaga(con, 3, primeira_vista_em=_dias(2))
    fora_da_janela = _vaga(con, 4, primeira_vista_em=_dias(31))
    candidatas = candidatas_a_detalhe(con, ["a"], AGORA, relogio)
    assert [c.ocorrencia_id for c in candidatas] == [
        _oid(con, v) for v in (empate_1, empate_2, velha)
    ]
    assert _oid(con, fora_da_janela) not in [c.ocorrencia_id for c in candidatas]
    primeira = candidatas[0]
    assert isinstance(primeira, Candidata)
    assert (primeira.fonte, primeira.escopo) == ("a", "")
    assert primeira.vaga.url == "https://a.exemplo.test/vagas/2"
    assert primeira.vaga.descricao == ""


def test_candidatas_so_das_fontes_pedidas_e_de_ocorrencia_aberta(con: sqlite3.Connection) -> None:
    aberta = _vaga(con, 1)
    _vaga(con, 2, fonte="b")
    _vaga(con, 3, fechada_em=_dias(1))
    assert [c.ocorrencia_id for c in candidatas_a_detalhe(con, ["a"], AGORA, relogio)] == [
        _oid(con, aberta)
    ]
    assert candidatas_a_detalhe(con, [], AGORA, relogio) == []


def test_candidatas_sem_vaga_com_descricao_na_ocorrencia(con: sqlite3.Connection) -> None:
    _vaga(con, 1, descricao_texto="Texto que já veio na listagem.")
    so_tab = _vaga(con, 2, descricao_texto="\t\r")
    espacos = _vaga(con, 3, descricao_texto="  \n")
    sem_texto = _vaga(con, 4)
    candidatas = candidatas_a_detalhe(con, ["a"], AGORA, relogio)
    assert sorted(c.ocorrencia_id for c in candidatas) == sorted(
        _oid(con, v) for v in (so_tab, espacos, sem_texto)
    )


def _tentativa(con: sqlite3.Connection, url: str, dias: float) -> None:
    con.execute(
        "INSERT INTO enriquecimento (url_hash, buscado_em, conteudo) VALUES (?, ?, '')",
        (hash_url(canonica(url)), _dias(dias)),
    )
    con.commit()


def test_candidatas_sem_url_com_detalhe_recente_de_outra_fonte(con: sqlite3.Connection) -> None:
    recente = _vaga(con, 1)
    antiga = _vaga(con, 2)
    # o cache é por URL: a tentativa pode ter vindo de outra fonte
    _tentativa(con, "https://a.exemplo.test/vagas/1", 10)
    _tentativa(con, "https://a.exemplo.test/vagas/2", 31)
    candidatas = candidatas_a_detalhe(con, ["a"], AGORA, relogio)
    assert [c.ocorrencia_id for c in candidatas] == [_oid(con, antiga)]
    assert _oid(con, recente) not in [c.ocorrencia_id for c in candidatas]
