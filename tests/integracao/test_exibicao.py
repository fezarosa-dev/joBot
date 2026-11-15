"""Moeda de exibição do painel e o filtro de salário (plano T168)."""

import sqlite3
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from apoio.semear import AGORA
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.cotacoes import gravar_cotacao
from jobot.banco.migrar import migrar
from jobot.nucleo.cambio import Cotacao
from jobot.painel.moeda import (
    INTEGER_MAX,
    Exibicao,
    FiltroSalario,
    exibicao_do_painel,
    filtro_salario,
)

HOJE = date(2026, 11, 13)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    yield c
    c.close()


def _ex(moeda: str, venda: str | None = None, *, ligada: bool = True) -> Exibicao:
    cotacao = None if venda is None else Cotacao(moeda=moeda, data=HOJE, venda=Decimal(venda))
    return Exibicao(moeda, cotacao, ligada)


def test_filtro_salario_em_reais_sem_conversao() -> None:
    f = filtro_salario(5000, None, _ex("BRL"))
    assert f == FiltroSalario(5000, None, None, None, None, None)


def test_filtro_salario_converte_a_favor_da_vaga() -> None:
    f = filtro_salario(1000, 1000, _ex("USD", "5.6549"))
    assert (f.sal_de_brl, f.sal_ate_brl) == (5654, 5655)
    assert (f.sal_moeda, f.sal_de_centavos, f.sal_ate_centavos, f.aviso) == (None, None, None, None)


def test_filtro_salario_troca_de_e_ate() -> None:
    f = filtro_salario(9000, 7000, _ex("BRL"))
    assert (f.sal_de_brl, f.sal_ate_brl) == (7000, 9000)


def test_filtro_salario_sem_cotacao_desliga_e_avisa() -> None:
    f = filtro_salario(1000, 2000, _ex("USD"))
    assert f == FiltroSalario(None, None, None, None, None, "sem_cotacao")


def test_filtro_salario_conversao_desligada_compara_na_moeda() -> None:
    f = filtro_salario(7000, None, _ex("EUR", ligada=False))
    assert f == FiltroSalario(None, None, "EUR", 700000, None, "so_moeda")


def test_filtro_salario_sem_limite_nao_avisa() -> None:
    assert filtro_salario(None, None, _ex("USD")).aviso is None
    assert filtro_salario(None, None, _ex("EUR", ligada=False)).aviso is None


def test_filtro_salario_enorme_fica_no_teto() -> None:
    f = filtro_salario(10**12, None, _ex("USD", "99999999.9999"))
    assert f.sal_de_brl == 2**63 - 1 == INTEGER_MAX
    g = filtro_salario(None, 10**12, _ex("EUR", ligada=False))
    assert g.sal_ate_centavos == 10**14


def test_exibicao_do_painel(con: sqlite3.Connection) -> None:
    padrao = exibicao_do_painel(con, HOJE)
    assert (padrao.moeda, padrao.cotacao, padrao.conversao_ligada) == ("BRL", None, True)
    gravar_config(con, "moeda_exibicao", "EUR")
    gravar_cotacao(con, Cotacao(moeda="EUR", data=HOJE, venda=Decimal("6.1")), AGORA)
    ex = exibicao_do_painel(con, HOJE)
    assert ex.moeda == "EUR"
    assert ex.cotacao == Cotacao(moeda="EUR", data=HOJE, venda=Decimal("6.1"))
    gravar_config(con, "conversao_moeda_ligada", False)
    assert exibicao_do_painel(con, HOJE).conversao_ligada is False
    velha = exibicao_do_painel(con, HOJE + timedelta(days=8))
    assert velha.moeda == "EUR"
    assert velha.cotacao is None


@pytest.mark.parametrize("venda", ["NaN", "0", "-1"])
def test_cotacao_estragada_no_banco_vale_como_sem_cotacao(
    con: sqlite3.Connection, venda: str
) -> None:
    gravar_config(con, "moeda_exibicao", "EUR")
    gravar_cotacao(con, Cotacao(moeda="EUR", data=HOJE, venda=Decimal("6.1")), AGORA)
    assert exibicao_do_painel(con, HOJE).cotacao is not None  # controle: a linha boa vale
    con.execute("UPDATE cotacao SET venda = ? WHERE moeda = 'EUR'", (venda,))
    con.commit()
    ex = exibicao_do_painel(con, HOJE)
    assert ex.moeda == "EUR"
    assert ex.cotacao is None
