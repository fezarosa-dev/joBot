"""Salvas que fecham em até 7 dias (plano T282, desenho 5.2), no dia de calendário local."""

import sqlite3
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from apoio.semear import inserir_vaga
from jobot.banco.conexao import abrir
from jobot.banco.leitura import Fechando, salvas_que_fecham
from jobot.banco.migrar import migrar

BRASILIA = timezone(timedelta(hours=-3))
AGORA = datetime(2026, 11, 16, 23, 30, tzinfo=BRASILIA)  # 02:30 do dia 17 em UTC


@pytest.fixture(autouse=True)
def fuso_local() -> Iterator[None]:
    """Fuso -03 sem depender do tzdata da máquina; desfeito no fim."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TZ", "<-03>3")
        time.tzset()
        yield
    time.tzset()


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    yield c
    c.close()


def _salva(con: sqlite3.Connection, prazo: str, **campos: Any) -> int:
    return inserir_vaga(con, status="salva", prazo=prazo, **campos)


def test_prazo_hoje_ate_7_dias_dia_local(con: sqlite3.Connection) -> None:
    ontem = _salva(con, "2026-11-15")
    hoje = _salva(con, "2026-11-16")
    limite = _salva(con, "2026-11-23")
    depois = _salva(con, "2026-11-24")
    ids = [f.vaga_id for f in salvas_que_fecham(con, AGORA, 10)]
    assert ids == [hoje, limite]
    assert ontem not in ids and depois not in ids


def test_dia_local_e_nao_utc(con: sqlite3.Connection) -> None:
    # em UTC já é dia 17: o prazo 16 ficaria "ontem" e o 24 entraria
    _salva(con, "2026-11-16")
    agora_utc = AGORA.astimezone(UTC)
    assert [f.prazo for f in salvas_que_fecham(con, agora_utc, 10)] == ["2026-11-16"]


def test_so_salvas(con: sqlite3.Connection) -> None:
    nova = inserir_vaga(con, status="nova", prazo="2026-11-18")
    salva = _salva(con, "2026-11-18")
    assert [f.vaga_id for f in salvas_que_fecham(con, AGORA, 10)] == [salva]
    assert nova not in [f.vaga_id for f in salvas_que_fecham(con, AGORA, 10)]


def test_limite_e_ordem(con: sqlite3.Connection) -> None:
    prazos = ["2026-11-22", "2026-11-18", "2026-11-20", "2026-11-17", "2026-11-23",
              "2026-11-19", "2026-11-21"]  # fmt: skip
    ids = {p: _salva(con, p) for p in prazos}
    achadas = salvas_que_fecham(con, AGORA, 5)
    assert [f.prazo for f in achadas] == sorted(prazos)[:5]
    assert [f.vaga_id for f in achadas] == [ids[p] for p in sorted(prazos)[:5]]


def test_mesmo_prazo_desempata_pelo_id(con: sqlite3.Connection) -> None:
    a = _salva(con, "2026-11-18")
    b = _salva(con, "2026-11-18")
    assert [f.vaga_id for f in salvas_que_fecham(con, AGORA, 10)] == [a, b]


def test_salva_fechada_na_fonte_fica_fora(con: sqlite3.Connection) -> None:
    fechada = _salva(con, "2026-11-18", fechada_em="2026-11-14T10:00:00+00:00")
    aberta = _salva(con, "2026-11-18")
    assert [f.vaga_id for f in salvas_que_fecham(con, AGORA, 10)] == [aberta]
    con.execute("UPDATE vaga SET fechada_em = NULL WHERE id = ?", (fechada,))
    con.commit()
    assert [f.vaga_id for f in salvas_que_fecham(con, AGORA, 10)] == [fechada, aberta]


def test_salva_oculta_entra(con: sqlite3.Connection) -> None:
    oculta = _salva(con, "2026-11-18", oculta_manual=1)
    assert [f.vaga_id for f in salvas_que_fecham(con, AGORA, 10)] == [oculta]


def test_campos_do_fechando(con: sqlite3.Connection) -> None:
    vaga = _salva(con, "2026-11-18", titulo="Dev", empresa="Acme")
    assert salvas_que_fecham(con, AGORA, 10) == [Fechando(vaga, "Dev", "Acme", "2026-11-18")]
