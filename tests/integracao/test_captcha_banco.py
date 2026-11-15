"""Interruptor, portão e teto diário do 2Captcha no banco (plano T181; ADR 0022, E7 e E8)."""

import json
import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from jobot.banco import cadastros, captcha
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.captcha import TETO_DIA, captcha_pronto, reservar_resolucao
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar

CHAVE = "abcdef0123456789abcd"
DIA = date(2026, 11, 15)


@pytest.fixture
def con() -> Iterator[sqlite3.Connection]:
    con = abrir(Path(":memory:"))
    migrar(con, Path(":memory:"))
    yield con
    con.close()


def _uso(con: sqlite3.Connection) -> object:
    return json.loads(
        con.execute("SELECT valor FROM config WHERE chave = 'captcha_uso'").fetchone()[0]
    )


def test_captcha_ligado_nasce_desligado(con: sqlite3.Connection) -> None:
    assert cadastros.PADROES["captcha_ligado"] is False
    assert ler_config(con, "captcha_ligado") is False  # sem linha vale o padrão
    gravar_config(con, "captcha_ligado", True)
    assert ler_config(con, "captcha_ligado") is True
    gravar_config(con, "captcha_ligado", False)
    assert ler_config(con, "captcha_ligado") is False


@pytest.mark.parametrize(
    ("ligado", "chave", "esperado"),
    [(None, CHAVE, False), (True, None, False), (False, CHAVE, False), (True, CHAVE, True)],
)
def test_pronto_so_com_chave_e_ligado(
    con: sqlite3.Connection, ligado: bool | None, chave: str | None, esperado: bool
) -> None:
    if ligado is not None:
        gravar_config(con, "captcha_ligado", ligado)
    assert captcha_pronto(con, chave) is esperado


def test_reserva_ate_o_teto_e_recusa_a_seguinte(con: sqlite3.Connection) -> None:
    assert [reservar_resolucao(con, DIA) for _ in range(TETO_DIA)] == [True] * TETO_DIA
    assert reservar_resolucao(con, DIA) is False
    assert _uso(con) == {"dia": "2026-11-15", "n": 30}


def test_reserva_zera_no_dia_seguinte(con: sqlite3.Connection) -> None:
    for _ in range(TETO_DIA):
        reservar_resolucao(con, DIA)
    assert reservar_resolucao(con, date(2026, 11, 16)) is True
    assert _uso(con) == {"dia": "2026-11-16", "n": 1}


@pytest.mark.parametrize(
    "valor",
    ["lixo", '"lixo"', '{"dia": "2026-11-15", "n": "x"}', '{"dia": "2026-11-15", "n": true}', "[]"],
)
def test_reserva_com_valor_torto_recomeca(con: sqlite3.Connection, valor: str) -> None:
    con.execute("INSERT INTO config (chave, valor) VALUES ('captcha_uso', ?)", (valor,))
    assert reservar_resolucao(con, DIA) is True
    assert _uso(con) == {"dia": "2026-11-15", "n": 1}


def test_reserva_e_um_comando_so(con: sqlite3.Connection) -> None:
    comandos: list[str] = []
    con.set_trace_callback(comandos.append)
    assert reservar_resolucao(con, DIA) is True
    con.set_trace_callback(None)
    # o `with con` do driver põe BEGIN e COMMIT em volta; fora deles, um comando só
    dados = [c for c in comandos if c.strip().upper() not in ("BEGIN", "COMMIT")]
    assert len(dados) == 1
    assert dados[0].lstrip().upper().startswith("INSERT")
    assert "ON CONFLICT" in dados[0].upper()
    assert "WHERE" in dados[0].upper()


def test_teto_e_lido_na_chamada(con: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(captcha, "TETO_DIA", 2)
    assert [reservar_resolucao(con, DIA) for _ in range(3)] == [True, True, False]
    assert _uso(con) == {"dia": "2026-11-15", "n": 2}


def _duas_conexoes(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection]]:
    arquivo = tmp_path / "jobot.db"
    primeira = abrir(arquivo)
    migrar(primeira, arquivo)
    segunda = abrir(arquivo)
    try:
        yield primeira, segunda
    finally:
        primeira.close()
        segunda.close()


@pytest.fixture
def duas(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection]]:
    yield from _duas_conexoes(tmp_path)


def test_outra_conexao_ve_o_teto_cheio(duas: tuple[sqlite3.Connection, sqlite3.Connection]) -> None:
    a, b = duas
    assert all(reservar_resolucao(a, DIA) for _ in range(TETO_DIA))
    assert reservar_resolucao(b, DIA) is False
    assert _uso(a) == {"dia": "2026-11-15", "n": 30}


def test_so_uma_conexao_leva_a_ultima_vaga(
    duas: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    a, b = duas
    assert all(reservar_resolucao(a, DIA) for _ in range(TETO_DIA - 1))  # n = 29
    resultados = [reservar_resolucao(a, DIA), reservar_resolucao(b, DIA)]
    assert sorted(resultados) == [False, True]
    assert _uso(a) == {"dia": "2026-11-15", "n": 30}


def test_reserva_com_contador_negativo_conta_como_teto(con: sqlite3.Connection) -> None:
    valor = '{"dia": "2026-11-15", "n": -5}'
    con.execute("INSERT INTO config (chave, valor) VALUES ('captcha_uso', ?)", (valor,))
    assert reservar_resolucao(con, DIA) is False
    assert (
        con.execute("SELECT valor FROM config WHERE chave = 'captcha_uso'").fetchone()[0] == valor
    )


def test_reserva_com_contador_negativo_de_outro_dia_recomeca(con: sqlite3.Connection) -> None:
    valor = '{"dia": "2026-11-14", "n": -5}'
    con.execute("INSERT INTO config (chave, valor) VALUES ('captcha_uso', ?)", (valor,))
    assert reservar_resolucao(con, DIA) is True
    assert _uso(con) == {"dia": "2026-11-15", "n": 1}
