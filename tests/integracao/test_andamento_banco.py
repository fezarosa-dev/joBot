"""Dados do progresso no banco (plano T246; desenho 5.9)."""

import logging
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jobot.banco.andamento import (
    Etapa,
    FonteAndamento,
    abrir_andamento,
    ler_andamento,
    marcar_fonte,
    mudar_etapa,
    planejar,
)
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao
from jobot.banco.migrar import migrar

AGORA = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
ETAPAS = ("coleta", "detalhes", "encaixe")


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    c.executemany("INSERT INTO fonte (chave, leva) VALUES (?, 'A')", [("a",), ("b",)])
    c.commit()
    yield c
    c.close()


@pytest.fixture
def eid(con: sqlite3.Connection) -> int:
    id_ = abrir_execucao(con, "busca", "agora", AGORA)
    assert id_ is not None
    return id_


def _fonte(con: sqlite3.Connection, eid: int, chave: str) -> FonteAndamento:
    fontes = {f.fonte: f for f in ler_andamento(con, eid)[1]}
    assert chave in fontes
    return fontes[chave]


def test_abrir_andamento_nasce_preparando(con: sqlite3.Connection, eid: int) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)

    assert ler_andamento(con, eid) == (
        Etapa(ETAPAS, "preparando", None, None, None, 0.0, AGORA),
        (),
    )
    assert ler_andamento(con, eid + 1) == (None, ())  # outra execução não tem andamento


def test_abrir_andamento_de_novo_volta_ao_comeco(con: sqlite3.Connection, eid: int) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)
    mudar_etapa(con, eid, "detalhes", 1, 4, 0.5, AGORA)
    abrir_andamento(con, eid, ("coleta",), AGORA + timedelta(seconds=1))

    etapa, _ = ler_andamento(con, eid)
    assert etapa == Etapa(
        ("coleta",), "preparando", None, None, None, 0.0, AGORA + timedelta(seconds=1)
    )


def test_planejar_grava_total_e_fila(con: sqlite3.Connection, eid: int) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)
    depois = AGORA + timedelta(seconds=5)

    planejar(con, eid, {"a": 3, "b": 2}, depois)

    etapa, fontes = ler_andamento(con, eid)
    assert etapa == Etapa(ETAPAS, "coleta", 0, 5, 5, 0.0, depois)
    assert fontes == (
        FonteAndamento("a", "fila", 0, 3, None, None),
        FonteAndamento("b", "fila", 0, 2, None, None),
    )


def test_mudar_etapa_guarda_partida_e_instante(con: sqlite3.Connection, eid: int) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)
    planejar(con, eid, {"a": 3}, AGORA)
    depois = AGORA + timedelta(seconds=40)

    mudar_etapa(con, eid, "detalhes", 2, 7, 0.55, depois)

    etapa, _ = ler_andamento(con, eid)
    assert etapa == Etapa(ETAPAS, "detalhes", 2, 7, 3, 0.55, depois)  # total_planejado fica


def test_marcar_fonte_muda_a_propria_linha(con: sqlite3.Connection, eid: int) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)
    planejar(con, eid, {"a": 3, "b": 2}, AGORA)
    fim = AGORA + timedelta(minutes=1)

    marcar_fonte(con, eid, "a", "lendo")
    assert _fonte(con, eid, "a").estado == "lendo"
    marcar_fonte(con, eid, "a", "esperando", espera_ate=fim, espera_motivo="limite")
    assert _fonte(con, eid, "a") == FonteAndamento("a", "esperando", 0, 3, fim, "limite")
    marcar_fonte(con, eid, "a", "lendo")

    fontes = ler_andamento(con, eid)[1]
    assert [f.fonte for f in fontes] == ["a", "b"]  # uma linha só por fonte
    assert fontes[0] == FonteAndamento("a", "lendo", 0, 3, None, None)  # a espera sumiu
    assert fontes[1].estado == "fila"  # a outra não mudou


def test_marcar_fonte_feitas_none_mantem(con: sqlite3.Connection, eid: int) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)
    planejar(con, eid, {"a": 3}, AGORA)

    marcar_fonte(con, eid, "a", "lendo", feitas=2)
    marcar_fonte(con, eid, "a", "lendo")

    assert _fonte(con, eid, "a") == FonteAndamento("a", "lendo", 2, 3, None, None)


def test_marcar_fonte_sem_planejar_nao_cria_linha(
    con: sqlite3.Connection, eid: int, caplog: pytest.LogCaptureFixture
) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)

    with caplog.at_level(logging.WARNING, logger="jobot.banco.andamento"):
        marcar_fonte(con, eid, "a", "lendo", feitas=1)

    assert ler_andamento(con, eid)[1] == ()
    assert "andamento" in caplog.text  # o log diz o que faltou


def test_nada_apagado(con: sqlite3.Connection, eid: int) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)
    planejar(con, eid, {"a": 3, "b": 2}, AGORA)
    marcar_fonte(con, eid, "a", "pronto", feitas=3)
    marcar_fonte(con, eid, "b", "falhou")

    mudar_etapa(con, eid, "fim", None, None, 1.0, AGORA + timedelta(minutes=2))

    etapa, fontes = ler_andamento(con, eid)
    assert etapa is not None
    assert etapa.etapa == "fim"
    assert [(f.fonte, f.estado) for f in fontes] == [("a", "pronto"), ("b", "falhou")]


def test_gravacao_dentro_de_transacao_aberta_nao_confirma(
    con: sqlite3.Connection, eid: int
) -> None:
    con.execute("BEGIN IMMEDIATE")
    abrir_andamento(con, eid, ETAPAS, AGORA)
    planejar(con, eid, {"a": 3}, AGORA)
    marcar_fonte(con, eid, "a", "lendo")
    mudar_etapa(con, eid, "detalhes", 1, 2, 0.5, AGORA)
    assert con.in_transaction  # quem abriu a transação é quem confirma
    con.rollback()
    assert ler_andamento(con, eid) == (None, ())

    abrir_andamento(con, eid, ETAPAS, AGORA)  # sem transação aberta: confirma
    assert not con.in_transaction
    planejar(con, eid, {"a": 3}, AGORA)
    assert not con.in_transaction
    marcar_fonte(con, eid, "a", "lendo")
    assert not con.in_transaction
    mudar_etapa(con, eid, "detalhes", 1, 2, 0.5, AGORA)
    assert not con.in_transaction
    con.rollback()
    etapa, fontes = ler_andamento(con, eid)
    assert etapa is not None
    assert etapa.etapa == "detalhes"
    assert fontes[0].estado == "lendo"


def test_gravacao_com_erro_nao_deixa_transacao_aberta(con: sqlite3.Connection, eid: int) -> None:
    abrir_andamento(con, eid, ETAPAS, AGORA)
    with pytest.raises(sqlite3.IntegrityError):
        mudar_etapa(con, eid, "inventada", None, None, 0.0, AGORA)
    assert not con.in_transaction
