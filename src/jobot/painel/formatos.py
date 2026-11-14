"""Texto de dinheiro, taxa, data e local do cartão da vaga (desenho 13.4; plano T45).

Os valores já vêm tratados do banco: aqui só viram texto no idioma da pessoa.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from jobot.banco.leitura import Item
from jobot.nucleo.modelo import Local
from jobot.painel.i18n import t

_SIMBOLO = {"USD": "US$", "BRL": "R$", "EUR": "€", "GBP": "£"}
_SEPARADORES = {"pt": (".", ","), "en": (",", ".")}  # milhar, decimal
_MAX_LOCAIS = 3


@dataclass(frozen=True)
class SalarioTexto:
    original: str  # no valor e no período que a fonte deu
    cotacao: str | None  # "US$ 1 = R$ 5,65 (PTAX de 13/11)"
    em_reais: str | None  # sempre por mês


def _separadores(idioma: str) -> tuple[str, str]:
    return _SEPARADORES.get(idioma, _SEPARADORES["pt"])


def _milhar(inteiro: int, sep: str) -> str:
    return f"{inteiro:,}".replace(",", sep)


def dinheiro(centavos: int, moeda: str, idioma: str) -> str:
    """Valor com o símbolo da moeda; sem centavos quando for redondo (`US$ 5.000`)."""
    milhar, decimal = _separadores(idioma)
    inteiro, resto = divmod(centavos, 100)
    texto = _milhar(inteiro, milhar) + (f"{decimal}{resto:02d}" if resto else "")
    return f"{_SIMBOLO.get(moeda, moeda)} {texto}"


def taxa(venda: str, idioma: str) -> str:
    """Cotação com pelo menos duas casas, sem zeros à direita além delas."""
    try:
        numero = Decimal(venda)
    except InvalidOperation:
        return venda
    inteiro, _, fracao = f"{numero.normalize():f}".partition(".")
    _, decimal = _separadores(idioma)
    return f"{inteiro}{decimal}{fracao.ljust(2, '0')}"


def _ler_data(data: str) -> datetime | None:
    try:
        return datetime.fromisoformat(data)
    except ValueError:
        return None


def data_curta(data: str, idioma: str) -> str:
    """Dia e mês: `13/11` em português, `11/13` em inglês. Data ilegível volta como veio."""
    lida = _ler_data(data)
    if lida is None:
        return data
    return lida.strftime("%m/%d" if idioma == "en" else "%d/%m")


def data_completa(data: str, idioma: str) -> str:
    lida = _ler_data(data)
    if lida is None:
        return data
    return lida.strftime("%m/%d/%Y" if idioma == "en" else "%d/%m/%Y")


def _faixa(valores: Sequence[int | None], moeda: str, idioma: str) -> str:
    """Um valor, ou `de a até` quando os dois existem e são diferentes."""
    achados = [v for v in valores if v is not None]
    textos = [dinheiro(v, moeda, idioma) for v in dict.fromkeys(achados)]
    if len(textos) == 2:
        return t(idioma, "vagas.faixa", de=textos[0], ate=textos[1])
    return textos[0]


def salario_texto(item: Item, idioma: str) -> SalarioTexto | None:
    """O salário do cartão. Sem valor ou implausível (DR-25), nada: nunca um número duvidoso."""
    moeda = item.sal_moeda
    if moeda is None or item.sal_plausivel is False:
        return None
    if item.sal_min_centavos is None and item.sal_max_centavos is None:
        return None
    periodo = t(idioma, f"vagas.periodo.{item.sal_periodo}") if item.sal_periodo else ""
    original = _faixa((item.sal_min_centavos, item.sal_max_centavos), moeda, idioma) + periodo
    if moeda == "BRL":
        return SalarioTexto(original, None, None)
    cotacao = None
    if item.sal_cotacao_venda and item.sal_cotacao_data:
        cotacao = t(
            idioma,
            "vagas.cotacao",
            um=dinheiro(100, moeda, idioma),
            taxa=taxa(item.sal_cotacao_venda, idioma),
            data=data_curta(item.sal_cotacao_data, idioma),
        )
    em_reais = None
    if item.sal_mensal_min_brl is not None:  # reais inteiros: ×100 para o `dinheiro`
        reais = (item.sal_mensal_min_brl * 100, (item.sal_mensal_max_brl or 0) * 100 or None)
        valor = _faixa(reais, "BRL", idioma) + t(idioma, "vagas.periodo.mes")
        em_reais = t(idioma, "vagas.em_reais", valor=valor)
    return SalarioTexto(original, cotacao, em_reais)


def locais_texto(locais: Sequence[Local]) -> str:
    """`São Paulo, SP`; sem cidade, o estado ou o país. Mais de três: `SP, RJ, MG +2`."""
    textos: list[str] = []
    for local in locais:
        lugar = local.uf or local.pais
        texto = ", ".join(p for p in (local.cidade, lugar) if p)
        if texto and texto not in textos:
            textos.append(texto)
    visiveis = ", ".join(textos[:_MAX_LOCAIS])
    return f"{visiveis} +{len(textos) - _MAX_LOCAIS}" if len(textos) > _MAX_LOCAIS else visiveis
