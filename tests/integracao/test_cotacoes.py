"""Cotações no banco e colunas `_brl` das vagas (desenho 7.3 e 10.3; plano T25)."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from jobot.banco.conexao import abrir
from jobot.banco.cotacoes import (
    aplicar_cotacoes,
    cotacao_mais_recente,
    falta_cotacao,
    gravar_cotacao,
    moedas_em_aberto,
)
from jobot.banco.migrar import migrar
from jobot.nucleo.cambio import Cotacao, buscar_cotacao
from jobot.nucleo.http import ClienteEducado, HttpEducado, LeitorValidadores, Validadores
from jobot.nucleo.relogio import Relogio

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ptax"
AGORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
SEXTA = date(2026, 11, 13)
SABADO = date(2026, 11, 14)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    yield c
    c.close()


def _cotar(con: sqlite3.Connection, moeda: str, venda: str, dia: date = SEXTA) -> None:
    gravar_cotacao(con, Cotacao(moeda=moeda, data=dia, venda=Decimal(venda)), AGORA)


def _brl(con: sqlite3.Connection, vaga_id: int) -> tuple[int | None, int | None, str | None]:
    linha = con.execute(
        "SELECT sal_mensal_min_brl, sal_mensal_max_brl, sal_cotacao_data FROM vaga WHERE id = ?",
        (vaga_id,),
    ).fetchone()
    return (linha[0], linha[1], linha[2])


def _usd(con: sqlite3.Connection, **campos: Any) -> int:
    base: dict[str, Any] = {
        "sal_moeda": "USD",
        "sal_min": 500_000,
        "sal_max": 600_000,
        "sal_periodo": "mes",
        "sal_mensal_min": 500_000,
    }
    return inserir_vaga(con, **(base | campos))


def _brl_vaga(con: sqlite3.Connection, **campos: Any) -> int:
    base: dict[str, Any] = {
        "sal_moeda": "BRL",
        "sal_min": 500_000,
        "sal_max": 700_000,
        "sal_periodo": "mes",
        "sal_mensal_min": 500_000,
    }
    return inserir_vaga(con, **(base | campos))


# --- cotação guardada ---


def test_gravar_e_ler_a_mais_recente(con: sqlite3.Connection) -> None:
    assert cotacao_mais_recente(con, "USD") is None
    _cotar(con, "USD", "5.60", date(2026, 11, 12))
    _cotar(con, "USD", "5.6549", SEXTA)
    _cotar(con, "EUR", "6.10", date(2026, 11, 14))
    assert cotacao_mais_recente(con, "USD") == Cotacao(
        moeda="USD", data=SEXTA, venda=Decimal("5.6549")
    )
    assert cotacao_mais_recente(con, "GBP") is None


def test_gravar_de_novo_atualiza_sem_duplicar(con: sqlite3.Connection) -> None:
    _cotar(con, "USD", "5.60")
    gravar_cotacao(
        con,
        Cotacao(moeda="USD", data=SEXTA, venda=Decimal("5.70")),
        AGORA + timedelta(days=1),
    )
    linhas = con.execute("SELECT moeda, data, venda, buscada_em FROM cotacao").fetchall()
    assert linhas == [("USD", "2026-11-13", "5.70", "2026-11-14T15:00:00+00:00")]
    assert not con.in_transaction


def test_gravar_recusa_valor_ruim(con: sqlite3.Connection) -> None:
    for venda in ("0", "-5", "NaN"):
        with pytest.raises(ValueError):
            _cotar(con, "USD", venda)
    with pytest.raises(ValueError):  # sem fuso
        gravar_cotacao(
            con,
            Cotacao(moeda="USD", data=SEXTA, venda=Decimal("5.6")),
            datetime(2026, 11, 13, 15, 0),
        )
    assert con.execute("SELECT COUNT(*) FROM cotacao").fetchone()[0] == 0


def test_so_moedas_de_vagas_abertas(con: sqlite3.Connection) -> None:
    _usd(con)
    _usd(con)  # repetida: a moeda sai uma vez
    _usd(con, sal_moeda="EUR", fechada_em="2026-11-01T00:00:00+00:00")  # vaga fechada
    _usd(con, sal_moeda="GBP")
    _brl_vaga(con)  # BRL não tem cotação
    _usd(con, sal_moeda="MXN")  # fora das 10 moedas do PTAX
    inserir_vaga(con)  # sem salário
    assert moedas_em_aberto(con) == ["GBP", "USD"]


@pytest.mark.anyio
async def test_um_pedido_por_moeda_por_dia(con: sqlite3.Connection) -> None:
    _usd(con)
    _usd(con, sal_moeda="EUR")
    pedidos: list[httpx.Request] = []

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return httpx.Response(200, text=(FIXTURES / "usd_semana.json").read_text("utf-8"))

    relogio: Relogio = RelogioFalso()
    leitor: LeitorValidadores = _SemValidadores()
    http: HttpEducado = ClienteEducado(
        httpx.MockTransport(servidor), relogio, leitor, "9.9.9"
    ).escopo(espera_s=0)

    async def ciclo(dia: date) -> None:
        for moeda in moedas_em_aberto(con):
            if falta_cotacao(con, moeda, dia):
                cotacao = await buscar_cotacao(http, moeda, dia)
                assert cotacao is not None
                gravar_cotacao(con, cotacao, datetime(dia.year, dia.month, dia.day, 15, tzinfo=UTC))

    await ciclo(SABADO)
    await ciclo(SABADO)  # de novo no mesmo dia: nenhum pedido
    assert len(pedidos) == 2  # EUR e USD, um cada
    await ciclo(SABADO + timedelta(days=1))  # dia seguinte: mais um por moeda
    assert len(pedidos) == 4
    assert sorted(p.url.params["@moeda"] for p in pedidos) == ["'EUR'", "'EUR'", "'USD'", "'USD'"]


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


def test_falta_cotacao_conta_o_dia_do_pedido(con: sqlite3.Connection) -> None:
    assert falta_cotacao(con, "USD", SABADO)
    # sábado: o boletim é de sexta, mas o pedido de sábado já foi feito
    gravar_cotacao(
        con,
        Cotacao(moeda="USD", data=SEXTA, venda=Decimal("5.6549")),
        datetime(2026, 11, 14, 8, 0, tzinfo=UTC),
    )
    assert not falta_cotacao(con, "USD", SABADO)
    assert falta_cotacao(con, "USD", SABADO + timedelta(days=1))
    assert falta_cotacao(con, "EUR", SABADO)  # outra moeda


# --- colunas _brl ---


def test_coluna_brl_fica_em_reais(con: sqlite3.Connection) -> None:
    _cotar(con, "USD", "5.65")
    vaga = _usd(con)  # 5.000 a 6.000 USD por mês
    # 30.000 a 72.000 USD por ano: 2.500 a 6.000 por mês (a coluna mensal vem do tratamento)
    anual = _usd(
        con, sal_min=3_000_000, sal_max=7_200_000, sal_periodo="ano", sal_mensal_min=250_000
    )
    assert aplicar_cotacoes(con) == 2
    assert _brl(con, vaga) == (28250, 33900, "2026-11-13")
    # 2.500 USD a 5,65 = 14.125 reais; o máximo anual vira 6.000 USD por mês = 33.900 reais
    assert _brl(con, anual) == (14125, 33900, "2026-11-13")
    assert not con.in_transaction


def test_aplicar_de_novo_nao_muda_nada(con: sqlite3.Connection) -> None:
    _cotar(con, "USD", "5.65")
    _usd(con)
    _brl_vaga(con)
    assert aplicar_cotacoes(con) == 2
    assert aplicar_cotacoes(con) == 0


def test_cotacao_nova_refaz_o_valor(con: sqlite3.Connection) -> None:
    vaga = _usd(con)
    _cotar(con, "USD", "5.65", date(2026, 11, 12))
    aplicar_cotacoes(con)
    _cotar(con, "USD", "6.00", SEXTA)
    assert aplicar_cotacoes(con) == 1
    assert _brl(con, vaga) == (30000, 36000, "2026-11-13")


def test_so_vaga_aberta_recebe_valor(con: sqlite3.Connection) -> None:
    _cotar(con, "USD", "5.65")
    fechada = _usd(con, fechada_em="2026-11-01T00:00:00+00:00")
    assert aplicar_cotacoes(con) == 0
    assert _brl(con, fechada) == (None, None, None)


def test_sem_cotacao_brl_fica_nulo_e_vaga_nao_some(con: sqlite3.Connection) -> None:
    velha = _usd(
        con, sal_mensal_min_brl=1234, sal_mensal_max_brl=4321, sal_cotacao_data="2026-01-01"
    )
    eur = _usd(con, sal_moeda="EUR")  # tabela cotacao vazia
    mxn = _usd(con, sal_moeda="MXN")  # fora das 10 moedas: nunca tem cotação
    sem_valor = inserir_vaga(con, sal_moeda="USD")  # moeda mas sem valor
    _cotar(con, "GBP", "7.10")  # cotação de outra moeda não serve
    aplicar_cotacoes(con)
    for vaga in (velha, eur, mxn, sem_valor):
        assert _brl(con, vaga) == (None, None, None)
    assert con.execute("SELECT COUNT(*) FROM vaga").fetchone()[0] == 4
    assert con.execute("SELECT sal_mensal_min FROM vaga WHERE id = ?", (eur,)).fetchone()[0] == (
        500_000
    )


def test_vaga_em_brl_tem_valor_em_reais_sem_cotacao(con: sqlite3.Connection) -> None:
    vaga = _brl_vaga(con)  # R$ 5.000,00 a R$ 7.000,00 por mês
    meio = _brl_vaga(con, sal_mensal_min=12_350, sal_max=12_349, sal_periodo="mes")
    assert con.execute("SELECT COUNT(*) FROM cotacao").fetchone()[0] == 0
    assert aplicar_cotacoes(con) == 2
    assert _brl(con, vaga) == (5000, 7000, None)
    assert _brl(con, meio) == (124, 123, None)  # 123,50 sobe; 123,49 desce


def test_conversao_desligada_zera_so_moeda_estrangeira(con: sqlite3.Connection) -> None:
    _cotar(con, "USD", "5.65")
    usd = _usd(con)
    fechada = _usd(con, fechada_em="2026-11-01T00:00:00+00:00", sal_mensal_min_brl=999)
    reais = _brl_vaga(con)
    aplicar_cotacoes(con)
    assert _brl(con, usd) == (28250, 33900, "2026-11-13")
    assert _brl(con, reais) == (5000, 7000, None)

    aplicar_cotacoes(con, conversao_ligada=False)
    assert _brl(con, usd) == (None, None, None)
    assert _brl(con, fechada) == (None, None, None)  # toda vaga em moeda estrangeira
    assert _brl(con, reais) == (5000, 7000, None)  # a em BRL mantém
    assert con.execute("SELECT COUNT(*) FROM cotacao").fetchone()[0] == 1  # cotação guardada

    # a vaga em BRL continua dona das colunas com a conversão desligada
    novo_brl = _brl_vaga(con, sal_mensal_min=800_000, sal_max=900_000)
    aplicar_cotacoes(con, conversao_ligada=False)
    assert _brl(con, novo_brl) == (8000, 9000, None)

    aplicar_cotacoes(con)  # ligando de novo, a em USD volta com a cotação guardada
    assert _brl(con, usd) == (28250, 33900, "2026-11-13")


def test_cotacao_com_mais_de_7_dias_nao_vale(con: sqlite3.Connection) -> None:
    _cotar(con, "USD", "5.65", date(2026, 11, 6))  # 7 dias antes de SEXTA: ainda vale
    _cotar(con, "EUR", "6.20", date(2026, 11, 5))  # 8 dias: venceu
    usd, eur = _usd(con), _usd(con, sal_moeda="EUR")

    assert cotacao_mais_recente(con, "USD", hoje=SEXTA) is not None
    assert cotacao_mais_recente(con, "EUR", hoje=SEXTA) is None
    assert cotacao_mais_recente(con, "EUR") is not None  # sem `hoje`, sem validade

    aplicar_cotacoes(con, hoje=SEXTA)
    assert _brl(con, usd) == (28250, 33900, "2026-11-06")
    assert _brl(con, eur) == (None, None, None)  # vaga não some, só fica sem valor em reais


def test_cotacao_velha_zera_o_valor_ja_gravado(con: sqlite3.Connection) -> None:
    _cotar(con, "USD", "5.65", date(2026, 11, 6))
    usd = _usd(con)
    aplicar_cotacoes(con, hoje=date(2026, 11, 13))
    assert _brl(con, usd)[0] == 28250
    aplicar_cotacoes(con, hoje=date(2026, 11, 14))  # um dia depois a cotação venceu
    assert _brl(con, usd) == (None, None, None)
