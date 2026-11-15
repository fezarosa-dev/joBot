"""Textos de salário, data e local do cartão da vaga (desenho 13.4; plano T45)."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from jobot.banco.leitura import Item
from jobot.nucleo.cambio import Cotacao
from jobot.nucleo.modelo import Local
from jobot.painel import formatos, i18n
from jobot.painel.moeda import Exibicao

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
    assert texto.convertido == "≈ R$ 28.250/mês"


def test_salario_em_ingles() -> None:
    texto = formatos.salario_texto(_item(**_USD), "en")
    assert texto is not None
    assert texto.original == "US$ 5,000/month"
    assert texto.cotacao == "US$ 1 = R$ 5.65 (PTAX of 11/13)"
    assert texto.convertido == "≈ R$ 28,250/month"


def test_salario_em_reais_nao_tem_cotacao() -> None:
    campos = {"sal_moeda": "BRL", "sal_min_centavos": 800000, "sal_periodo": "mes"}
    texto = formatos.salario_texto(_item(**campos, sal_plausivel=True), "pt")
    assert texto is not None
    assert (texto.original, texto.convertido, texto.cotacao) == ("R$ 8.000/mês", None, None)


def test_salario_sem_cotacao_mostra_so_o_valor_original() -> None:
    campos = _USD | {
        "sal_cotacao_venda": None,
        "sal_cotacao_data": None,
        "sal_mensal_min_brl": None,
    }
    texto = formatos.salario_texto(_item(**campos), "pt")
    assert texto is not None
    assert (texto.original, texto.convertido, texto.cotacao) == ("US$ 5.000/mês", None, None)


def test_salario_com_faixa_e_periodo_anual() -> None:
    campos = _USD | {
        "sal_max_centavos": 700000,
        "sal_mensal_min_brl": 28250,
        "sal_mensal_max_brl": 39550,
    }
    texto = formatos.salario_texto(_item(**campos), "pt")
    assert texto is not None
    assert texto.original == "US$ 5.000 a US$ 7.000/mês"
    assert texto.convertido == "≈ R$ 28.250 a R$ 39.550/mês"
    anual = formatos.salario_texto(
        _item(sal_moeda="BRL", sal_min_centavos=12000000, sal_periodo="ano", sal_plausivel=True),
        "en",
    )
    assert anual is not None
    assert anual.original == "R$ 120,000/year"


def _exibicao(
    moeda: str, venda: str | None, dia: date = date(2026, 11, 12), ligada: bool = True
) -> Exibicao:
    cotacao = None if venda is None else Cotacao(moeda=moeda, data=dia, venda=Decimal(venda))
    return Exibicao(moeda, cotacao, ligada)


_USD_5000 = _USD | {"sal_mensal_min_brl": 5000}  # US$ 5.000 = R$ 5.000 na conta dos testes
_BRL_5000: dict[str, Any] = {
    "sal_moeda": "BRL",
    "sal_min_centavos": 500000,
    "sal_periodo": "mes",
    "sal_mensal_min_brl": 5000,
    "sal_plausivel": True,
}


def test_convertido_em_euro() -> None:
    ex = _exibicao("EUR", "6.25")
    texto = formatos.salario_texto(_item(**_USD_5000), "pt", ex)
    assert texto is not None
    assert texto.original == "US$ 5.000/mês"
    assert texto.convertido == "≈ € 800/mês"
    assert texto.cotacao == "US$ 1 = € 0,904 (PTAX de 12/11)"
    em_ingles = formatos.salario_texto(_item(**_USD_5000), "en", ex)
    assert em_ingles is not None
    assert em_ingles.convertido == "≈ € 800/month"
    assert em_ingles.cotacao == "US$ 1 = € 0.904 (PTAX of 11/12)"


def test_data_da_cotacao_cruzada_e_a_mais_antiga_das_duas() -> None:
    # USD de 13/11 e EUR de 10/11: vale 10/11; com o USD mais velho, vale o do USD
    nova = formatos.salario_texto(
        _item(**_USD_5000), "pt", _exibicao("EUR", "6.25", date(2026, 11, 10))
    )
    assert nova is not None and nova.cotacao is not None
    assert nova.cotacao.endswith("(PTAX de 10/11)")
    velha = _USD_5000 | {"sal_cotacao_data": "2026-11-09"}
    texto = formatos.salario_texto(
        _item(**velha), "pt", _exibicao("EUR", "6.25", date(2026, 11, 12))
    )
    assert texto is not None and texto.cotacao is not None
    assert texto.cotacao.endswith("(PTAX de 09/11)")


def test_convertido_em_iene_sem_centavos() -> None:
    texto = formatos.salario_texto(_item(**_USD_5000), "pt", _exibicao("JPY", "0.0368"))
    assert texto is not None
    assert texto.convertido == "≈ ¥ 135.870/mês"


def test_convertido_em_faixa_na_moeda_de_exibicao() -> None:
    campos = _USD_5000 | {"sal_max_centavos": 700000, "sal_mensal_max_brl": 7000}
    texto = formatos.salario_texto(_item(**campos), "pt", _exibicao("EUR", "6.25"))
    assert texto is not None
    assert texto.convertido == "≈ € 800 a € 1.120/mês"


def test_vaga_em_reais_com_moeda_euro() -> None:
    texto = formatos.salario_texto(_item(**_BRL_5000), "pt", _exibicao("EUR", "6.25"))
    assert texto is not None
    assert texto.convertido == "≈ € 800/mês"
    assert texto.cotacao == "€ 1 = R$ 6,25 (PTAX de 12/11)"


def test_vaga_em_reais_com_exibicao_em_reais_nao_tem_linha() -> None:
    for ex in (None, _exibicao("BRL", None)):
        texto = formatos.salario_texto(_item(**_BRL_5000), "pt", ex)
        assert texto is not None
        assert (texto.convertido, texto.cotacao) == (None, None)


def test_vaga_na_moeda_de_exibicao_sem_linha() -> None:
    campos = _USD_5000 | {"sal_moeda": "EUR"}
    texto = formatos.salario_texto(_item(**campos), "pt", _exibicao("EUR", "6.25"))
    assert texto is not None
    assert (texto.original, texto.convertido, texto.cotacao) == ("€ 5.000/mês", None, None)


@pytest.mark.parametrize(
    "ex", [_exibicao("BRL", None, ligada=False), _exibicao("EUR", "6.25", ligada=False)]
)
def test_conversao_desligada_sem_linha(ex: Exibicao) -> None:
    texto = formatos.salario_texto(_item(**_USD_5000), "pt", ex)
    assert texto is not None
    assert (texto.original, texto.convertido, texto.cotacao) == ("US$ 5.000/mês", None, None)


def test_sem_cotacao_da_exibicao_mostra_reais_com_nota() -> None:
    ex = _exibicao("EUR", None)
    texto = formatos.salario_texto(_item(**_USD), "pt", ex)
    assert texto is not None
    assert texto.convertido == "≈ R$ 28.250/mês"
    assert texto.cotacao == "em reais: ainda não temos a cotação de EUR"
    em_ingles = formatos.salario_texto(_item(**_USD), "en", ex)
    assert em_ingles is not None
    assert em_ingles.cotacao == "shown in reais: no EUR exchange rate yet"
    # sem valor em reais (a vaga não foi convertida), a nota "em reais" ficaria sem o que explicar
    sem_reais = formatos.salario_texto(_item(**_USD | {"sal_mensal_min_brl": None}), "pt", ex)
    assert sem_reais is not None
    assert (sem_reais.convertido, sem_reais.cotacao) == (None, None)
    # vaga em reais: o valor em reais repetiria o original, então nem linha nem nota
    em_reais = formatos.salario_texto(_item(**_BRL_5000), "pt", ex)
    assert em_reais is not None
    assert (em_reais.convertido, em_reais.cotacao) == (None, None)


@pytest.mark.parametrize(
    ("ex", "esperado"),
    [(None, "≈ R$ 8.000/mês"), (_exibicao("EUR", "6.25"), "≈ € 1.280/mês")],
)
def test_vaga_so_com_maximo_ganha_linha(ex: Exibicao | None, esperado: str) -> None:
    campos = _USD | {"sal_mensal_min_brl": None, "sal_mensal_max_brl": 8000}
    texto = formatos.salario_texto(_item(**campos), "pt", ex)
    assert texto is not None
    assert texto.convertido == esperado


def test_taxa_cruzada_que_nao_termina_na_tela() -> None:
    campos = _USD_5000 | {"sal_moeda": "JPY", "sal_cotacao_venda": "0.0368"}
    texto = formatos.salario_texto(_item(**campos), "pt", _exibicao("USD", "5.65"))
    assert texto is not None and texto.cotacao is not None
    assert "US$ 0,0065" in texto.cotacao


@pytest.mark.parametrize(
    ("ex", "convertido"),
    [(None, "≈ R$ 5.000/mês"), (_exibicao("EUR", "6.25"), "≈ € 800/mês")],
)
@pytest.mark.parametrize("venda_da_vaga", ["abc", "0", "-1", "NaN"])
def test_cotacao_da_vaga_estragada_some_so_a_cotacao(
    venda_da_vaga: str, ex: Exibicao | None, convertido: str
) -> None:
    campos = _USD_5000 | {"sal_cotacao_venda": venda_da_vaga}
    texto = formatos.salario_texto(_item(**campos), "pt", ex)
    assert texto is not None
    assert (texto.convertido, texto.cotacao) == (convertido, None)


@pytest.mark.parametrize(
    ("ex", "convertido"),
    [(None, "≈ R$ 5.000/mês"), (_exibicao("EUR", "6.25"), "≈ € 800/mês")],
)
def test_data_da_cotacao_da_vaga_ilegivel_some_so_a_cotacao(
    ex: Exibicao | None, convertido: str
) -> None:
    campos = _USD_5000 | {"sal_cotacao_data": "xx"}
    texto = formatos.salario_texto(_item(**campos), "pt", ex)
    assert texto is not None
    assert (texto.convertido, texto.cotacao) == (convertido, None)


def test_taxa_cruzada_gigante_nao_estoura() -> None:
    campos = _USD_5000 | {"sal_cotacao_venda": "9" * 30}
    texto = formatos.salario_texto(_item(**campos), "pt", _exibicao("EUR", "0.0000001"))
    assert texto is not None
    assert texto.convertido is not None
    assert texto.cotacao is None


def test_convertido_que_nao_cabe_no_inteiro_do_banco_some() -> None:
    # 9e16 reais a 1 por 1 são 9e18 centavos (cabe); 1e17 são 1e19 (passa de 2**63 - 1)
    cabe = formatos.salario_texto(
        _item(**_USD_5000 | {"sal_mensal_min_brl": 9 * 10**16}), "pt", _exibicao("EUR", "1")
    )
    assert cabe is not None and cabe.convertido is not None
    campos = _USD_5000 | {"sal_mensal_min_brl": 10**17}
    nao_cabe = formatos.salario_texto(_item(**campos), "pt", _exibicao("EUR", "1"))
    assert nao_cabe is not None
    assert nao_cabe.convertido is None


def test_cotacao_minuscula_da_exibicao_nao_estoura() -> None:
    # 5.000 / 1E-5000 tem mais de 4300 dígitos: o texto do inteiro levantaria ValueError
    texto = formatos.salario_texto(_item(**_USD_5000), "pt", _exibicao("EUR", "1E-5000"))
    assert texto is not None
    assert (texto.original, texto.convertido, texto.cotacao) == ("US$ 5.000/mês", None, None)


def test_simbolos_das_moedas_novas() -> None:
    assert formatos.dinheiro(100000, "CAD", "pt") == "C$ 1.000"
    assert formatos.dinheiro(100000, "AUD", "pt") == "A$ 1.000"
    assert formatos.dinheiro(100000, "JPY", "pt") == "¥ 1.000"
    assert formatos.dinheiro(100000, "SEK", "pt") == "SEK 1.000"


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_cotacao_sem_real_fixo_em_pt_e_en(idioma: str) -> None:
    assert "R$" not in i18n.carregar()[idioma]["vagas.cotacao"]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_chave_em_reais_saiu(idioma: str) -> None:
    catalogo = i18n.carregar()[idioma]
    assert "vagas.em_reais" not in catalogo
    assert "vagas.convertido" in catalogo


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


@pytest.mark.parametrize(
    ("paises", "idioma", "esperado"),
    [
        (("BR", "PT"), "pt", "Brasil e Portugal"),
        (("BR", "PT"), "en", "Brazil and Portugal"),
        (("BR", "PT", "ES", "US"), "en", "Brazil, Portugal, Spain +1"),
        (("XX",), "pt", "XX"),
        (("BR", "BR", "PT"), "pt", "Brasil e Portugal"),
        (("PT", "BR", "ES"), "pt", "Portugal, Brasil e Espanha"),
        ((), "pt", ""),
    ],
)
def test_paises_texto(paises: tuple[str, ...], idioma: str, esperado: str) -> None:
    assert formatos.paises_texto([Local(pais=p) for p in paises], idioma) == esperado


@pytest.mark.parametrize(
    ("valor", "idioma", "esperado"),
    [
        (Decimal("1234.567"), "pt", "1.234,56"),
        (Decimal("1234.567"), "en", "1,234.56"),
        (Decimal("0.9"), "pt", "0,90"),
        (Decimal("0"), "en", "0.00"),
        (Decimal("-1.234"), "pt", "-1,23"),
        (Decimal("-1.234"), "en", "-1.23"),
        (Decimal(10**15), "pt", "1.000.000.000.000.000,00"),
        (Decimal("0." + "9" * 29), "pt", "0,99"),  # passa da precisão do contexto: não arredonda
    ],
)
def test_decimal_curto(valor: Decimal, idioma: str, esperado: str) -> None:
    assert formatos.decimal_curto(valor, idioma) == esperado
