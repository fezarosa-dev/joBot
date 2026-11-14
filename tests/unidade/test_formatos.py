"""Textos de salário, data e local do cartão da vaga (desenho 13.4; plano T45)."""

from typing import Any

import pytest

from jobot.banco.leitura import Item
from jobot.nucleo.modelo import Local
from jobot.painel import formatos

_BASE: dict[str, Any] = {
    "id": 1,
    "titulo": "Vaga",
    "empresa": "Empresa",
    "url": "https://exemplo.test/1",
    "area": None,
    "nivel": None,
    "modalidade": None,
    "contrato": None,
    "status": "nova",
    "avisos": (),
    "sal_moeda": None,
    "sal_min_centavos": None,
    "sal_max_centavos": None,
    "sal_periodo": None,
    "sal_mensal_min_centavos": None,
    "sal_mensal_min_brl": None,
    "sal_mensal_max_brl": None,
    "sal_cotacao_data": None,
    "sal_cotacao_venda": None,
    "sal_plausivel": None,
    "prazo": None,
    "publicada_em": None,
    "primeira_vista_em": "2026-11-13T12:00:00+00:00",
    "fechada": False,
    "nova": True,
    "fecha_logo": False,
    "nota": None,
    "encaixe": None,
    "motivos": (),
    "oculta_motivo": None,
    "locais": (),
}
_USD: dict[str, Any] = {
    "sal_moeda": "USD",
    "sal_min_centavos": 500000,
    "sal_periodo": "mes",
    "sal_mensal_min_centavos": 500000,
    "sal_mensal_min_brl": 28250,
    "sal_cotacao_data": "2026-11-13",
    "sal_cotacao_venda": "5.65",
    "sal_plausivel": True,
}


def _item(**campos: Any) -> Item:
    return Item(**(_BASE | campos))


@pytest.mark.parametrize(
    ("centavos", "moeda", "idioma", "esperado"),
    [
        (500000, "USD", "pt", "US$ 5.000"),
        (500000, "USD", "en", "US$ 5,000"),
        (800050, "BRL", "pt", "R$ 8.000,50"),
        (800050, "BRL", "en", "R$ 8,000.50"),
        (800000, "BRL", "pt", "R$ 8.000"),
        (150000, "PLN", "pt", "PLN 1.500"),
        (99900, "EUR", "pt", "€ 999"),
        (123456789, "GBP", "en", "£ 1,234,567.89"),
    ],
)
def test_dinheiro(centavos: int, moeda: str, idioma: str, esperado: str) -> None:
    assert formatos.dinheiro(centavos, moeda, idioma) == esperado


@pytest.mark.parametrize(
    ("venda", "idioma", "esperado"),
    [
        ("5.65", "pt", "5,65"),
        ("5.6512", "en", "5.6512"),
        ("5", "pt", "5,00"),
        ("5.1000", "pt", "5,10"),
    ],
)
def test_taxa_de_cambio(venda: str, idioma: str, esperado: str) -> None:
    assert formatos.taxa(venda, idioma) == esperado


@pytest.mark.parametrize(
    ("data", "idioma", "curta", "completa"),
    [
        ("2026-11-13", "pt", "13/11", "13/11/2026"),
        ("2026-11-13", "en", "11/13", "11/13/2026"),
        ("2026-11-13T12:00:00+00:00", "pt", "13/11", "13/11/2026"),
    ],
)
def test_datas(data: str, idioma: str, curta: str, completa: str) -> None:
    assert formatos.data_curta(data, idioma) == curta
    assert formatos.data_completa(data, idioma) == completa


def test_data_ilegivel_volta_como_veio() -> None:
    assert formatos.data_curta("amanhã", "pt") == "amanhã"
    assert formatos.data_completa("amanhã", "pt") == "amanhã"


def test_salario_em_moeda_estrangeira_mostra_cotacao_e_reais() -> None:
    texto = formatos.salario_texto(_item(**_USD), "pt")
    assert texto is not None
    assert texto.original == "US$ 5.000/mês"
    assert texto.cotacao == "US$ 1 = R$ 5,65 (PTAX de 13/11)"
    assert texto.em_reais == "≈ R$ 28.250/mês"


def test_salario_em_ingles() -> None:
    texto = formatos.salario_texto(_item(**_USD), "en")
    assert texto is not None
    assert texto.original == "US$ 5,000/month"
    assert texto.cotacao == "US$ 1 = R$ 5.65 (PTAX of 11/13)"
    assert texto.em_reais == "≈ R$ 28,250/month"


def test_salario_em_reais_nao_tem_cotacao() -> None:
    campos = {"sal_moeda": "BRL", "sal_min_centavos": 800000, "sal_periodo": "mes"}
    texto = formatos.salario_texto(_item(**campos, sal_plausivel=True), "pt")
    assert texto is not None
    assert (texto.original, texto.cotacao, texto.em_reais) == ("R$ 8.000/mês", None, None)


def test_salario_sem_cotacao_mostra_so_o_valor_original() -> None:
    campos = _USD | {
        "sal_cotacao_venda": None,
        "sal_cotacao_data": None,
        "sal_mensal_min_brl": None,
    }
    texto = formatos.salario_texto(_item(**campos), "pt")
    assert texto is not None
    assert (texto.original, texto.cotacao, texto.em_reais) == ("US$ 5.000/mês", None, None)


def test_salario_com_faixa_e_periodo_anual() -> None:
    campos = _USD | {
        "sal_max_centavos": 700000,
        "sal_mensal_min_brl": 28250,
        "sal_mensal_max_brl": 39550,
    }
    texto = formatos.salario_texto(_item(**campos), "pt")
    assert texto is not None
    assert texto.original == "US$ 5.000 a US$ 7.000/mês"
    assert texto.em_reais == "≈ R$ 28.250 a R$ 39.550/mês"
    anual = formatos.salario_texto(
        _item(sal_moeda="BRL", sal_min_centavos=12000000, sal_periodo="ano", sal_plausivel=True),
        "en",
    )
    assert anual is not None
    assert anual.original == "R$ 120,000/year"


@pytest.mark.parametrize(
    "campos",
    [
        {},
        {
            "sal_moeda": "BRL",
            "sal_min_centavos": 99999900,
            "sal_periodo": "mes",
            "sal_plausivel": False,
        },
    ],
)
def test_sem_salario_ou_implausivel_nao_mostra_valor(campos: dict[str, Any]) -> None:
    assert formatos.salario_texto(_item(**campos), "pt") is None


@pytest.mark.parametrize(
    ("locais", "esperado"),
    [
        ((), ""),
        ((Local(cidade="São Paulo", uf="SP", pais="BR"),), "São Paulo, SP"),
        ((Local(uf="SP", pais="BR"),), "SP"),
        ((Local(cidade="Austin", pais="US"),), "Austin, US"),
        ((Local(pais="PT"),), "PT"),
        (tuple(Local(uf=u) for u in ("SP", "RJ", "MG", "BA", "PR")), "SP, RJ, MG +2"),
    ],
)
def test_locais(locais: tuple[Local, ...], esperado: str) -> None:
    assert formatos.locais_texto(locais) == esperado
