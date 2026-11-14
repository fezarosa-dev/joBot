"""Câmbio puro: conta em reais e leitura da PTAX (desenho 10.3, apêndice 6; plano T25)."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.cambio import MOEDAS, Cotacao, buscar_cotacao, em_reais
from jobot.nucleo.http import ClienteEducado, HttpEducado, LeitorValidadores, Validadores
from jobot.nucleo.relogio import Relogio

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ptax"
DOMINGO = date(2026, 11, 15)


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


class _Servidor:
    """Transporte falso: guarda os pedidos e responde sempre a mesma coisa."""

    def __init__(self, resposta: httpx.Response) -> None:
        self.pedidos: list[httpx.Request] = []
        self._resposta = resposta

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        return self._resposta


def _http(servidor: _Servidor) -> HttpEducado:
    relogio: Relogio = RelogioFalso()
    leitor: LeitorValidadores = _SemValidadores()
    return ClienteEducado(httpx.MockTransport(servidor), relogio, leitor, "9.9.9").escopo()


def _fixture(nome: str) -> httpx.Response:
    return httpx.Response(200, text=(FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


def test_valor_em_brl() -> None:
    # 5.000 USD são 500.000 centavos de dólar; a 5,65 viram 28.250 reais
    assert em_reais(500_000, Decimal("5.65")) == 28250


def test_arredonda_para_o_real_mais_proximo() -> None:
    assert em_reais(10_000, Decimal("5.6549")) == 565
    assert em_reais(10_000, Decimal("5.6551")) == 566
    # meio exato sobe (ROUND_HALF_UP): 564,5 vira 565, não 564 como no arredondamento par
    assert em_reais(10_000, Decimal("5.645")) == 565


def test_conta_exata_com_valor_enorme() -> None:
    # acima de 28 dígitos o contexto padrão do Decimal arredondaria em silêncio
    assert em_reais(10**30, Decimal("5.65")) == 565 * 10**26


@pytest.mark.parametrize("ruim", ["0", "-1", "NaN", "Infinity"])
def test_cotacao_invalida_levanta(ruim: str) -> None:
    with pytest.raises(ValueError):
        em_reais(100, Decimal(ruim))


def test_moedas_do_ptax() -> None:
    assert set(MOEDAS) == {"AUD", "CAD", "CHF", "DKK", "EUR", "GBP", "JPY", "NOK", "SEK", "USD"}
    assert "BRL" not in MOEDAS


@pytest.mark.anyio
async def test_fim_de_semana_usa_ultimo_dia_util() -> None:
    servidor = _Servidor(_fixture("usd_semana"))
    cotacao = await buscar_cotacao(_http(servidor), "USD", DOMINGO)
    assert cotacao == Cotacao(moeda="USD", data=date(2026, 11, 13), venda=Decimal("5.6549"))
    assert len(servidor.pedidos) == 1  # um pedido só, mesmo sem linha no dia


@pytest.mark.anyio
async def test_datas_no_formato_mm_dd_aaaa() -> None:
    servidor = _Servidor(_fixture("usd_semana"))
    await buscar_cotacao(_http(servidor), "USD", DOMINGO)
    pedido = servidor.pedidos[0]
    assert pedido.method == "GET"
    assert pedido.url.host == "olinda.bcb.gov.br"
    assert pedido.url.path.endswith(
        "/PTAX/versao/v1/odata/CotacaoMoedaPeriodo"
        "(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
    )
    # janela de 7 dias: de 8/11 até 15/11, MM-DD-AAAA entre aspas simples
    assert dict(pedido.url.params) == {
        "@moeda": "'USD'",
        "@dataInicial": "'11-08-2026'",
        "@dataFinalCotacao": "'11-15-2026'",
        "$format": "json",
        "$filter": "tipoBoletim eq 'Fechamento'",
    }


@pytest.mark.anyio
async def test_espaco_do_filtro_vai_como_percent20() -> None:
    # o servidor do Banco Central devolve 400 quando o espaço vai como "+"
    servidor = _Servidor(_fixture("usd_semana"))
    await buscar_cotacao(_http(servidor), "USD", DOMINGO)
    consulta = servidor.pedidos[0].url.query
    assert b"+" not in consulta
    assert b"tipoBoletim%20eq%20" in consulta


@pytest.mark.anyio
async def test_so_o_boletim_de_fechamento_vale() -> None:
    servidor = _Servidor(_fixture("usd_com_outros_boletins"))
    cotacao = await buscar_cotacao(_http(servidor), "USD", date(2026, 11, 13))
    assert cotacao == Cotacao(moeda="USD", data=date(2026, 11, 13), venda=Decimal("5.6549"))


@pytest.mark.anyio
async def test_usa_a_venda_exata_sem_float() -> None:
    corpo = {
        "value": [
            {
                "cotacaoVenda": 5.65,
                "dataHoraCotacao": "2026-11-13 13:05:20.75",
                "tipoBoletim": "Fechamento",
            }
        ]
    }
    servidor = _Servidor(httpx.Response(200, text=json.dumps(corpo)))
    cotacao = await buscar_cotacao(_http(servidor), "EUR", date(2026, 11, 13))
    assert cotacao is not None
    assert cotacao.venda == Decimal("5.65")
    assert cotacao.moeda == "EUR"


@pytest.mark.anyio
async def test_sem_linha_devolve_none() -> None:
    servidor = _Servidor(_fixture("vazio"))
    assert await buscar_cotacao(_http(servidor), "USD", DOMINGO) is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "corpo",
    [
        _fixture("formato_mudou").text,
        "<html>fora do ar</html>",
        "[]",
        '{"value": "nada"}',
        '{"value": [1, "a", null]}',
        '{"value": [{"cotacaoVenda": 0, "dataHoraCotacao": "2026-11-13 13:00:00", '
        '"tipoBoletim": "Fechamento"}]}',
        '{"value": [{"cotacaoVenda": 5.6, "dataHoraCotacao": "ontem", '
        '"tipoBoletim": "Fechamento"}]}',
    ],
)
async def test_formato_mudou_devolve_none(corpo: str) -> None:
    servidor = _Servidor(httpx.Response(200, text=corpo))
    assert await buscar_cotacao(_http(servidor), "USD", date(2026, 11, 13)) is None


@pytest.mark.anyio
async def test_linha_de_fora_da_janela_nao_vale() -> None:
    servidor = _Servidor(_fixture("usd_semana"))
    # a fixture vai de 9 a 13/11: para o dia 1/11 (janela 25/10 a 1/11) nada cabe
    assert await buscar_cotacao(_http(servidor), "USD", date(2026, 11, 1)) is None


@pytest.mark.anyio
async def test_moeda_fora_da_lista_nao_faz_pedido() -> None:
    servidor = _Servidor(_fixture("usd_semana"))
    for moeda in ("BRL", "MXN", "usd", "USD'&x='"):
        assert await buscar_cotacao(_http(servidor), moeda, DOMINGO) is None
    assert servidor.pedidos == []
