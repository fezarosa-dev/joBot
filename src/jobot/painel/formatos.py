"""Texto de dinheiro, taxa, data e local do cartão da vaga (desenho 13.4; plano T45).

Os valores já vêm tratados do banco: aqui só viram texto no idioma da pessoa.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from jobot.banco.leitura import Item
from jobot.nucleo.cambio import Cotacao, de_reais, taxa_cruzada
from jobot.nucleo.modelo import Local
from jobot.nucleo.texto import normalizar
from jobot.nucleo.tratamento.locais import codigos_de_pais, nome_do_pais, nome_em_ingles
from jobot.painel.i18n import t
from jobot.painel.moeda import INTEGER_MAX, Exibicao

_SIMBOLO = {
    "USD": "US$",
    "BRL": "R$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "C$",
    "AUD": "A$",
    "JPY": "¥",
}
_SEPARADORES = {"pt": (".", ","), "en": (",", ".")}  # milhar, decimal
_MAX_LOCAIS = 3
_E = {"pt": "e", "en": "and"}


@dataclass(frozen=True)
class SalarioTexto:
    original: str  # no valor e no período que a fonte deu
    convertido: str | None  # "≈ R$ 28.250/mês", sempre por mês
    cotacao: str | None  # "US$ 1 = R$ 5,65 (PTAX de 13/11)"


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


def _venda(texto: str | None) -> Decimal | None:
    """A venda lida do banco; ilegível, zero ou negativa vale como ausente."""
    try:
        venda = Decimal(texto or "")
    except InvalidOperation:
        return None
    return venda if venda.is_finite() and venda > 0 else None


def _convertido(item: Item, idioma: str, moeda: str, venda: Decimal | None) -> str | None:
    """O valor mensal em reais (`venda` None) ou em `moeda` (reais ÷ `venda`); só o máximo vale."""
    reais = (item.sal_mensal_min_brl, item.sal_mensal_max_brl or None)
    if reais == (None, None):
        return None
    inteiros = [None if v is None else v if venda is None else de_reais(v, venda) for v in reais]
    centavos = [None if v is None else v * 100 for v in inteiros]
    if any(v is not None and v > INTEGER_MAX for v in centavos):  # cotação minúscula: não é salário
        return None
    valor = _faixa(centavos, moeda, idioma)
    return t(idioma, "vagas.convertido", valor=valor + t(idioma, "vagas.periodo.mes"))


def _cotacao(idioma: str, moeda: str, taxa_texto: str, data: str) -> str:
    um = dinheiro(100, moeda, idioma)
    return t(idioma, "vagas.cotacao", um=um, taxa=taxa_texto, data=data_curta(data, idioma))


def _cotacao_cruzada(item: Item, idioma: str, venda_x: Decimal | None, y: Cotacao) -> str | None:
    """`US$ 1 = € 0,904 (PTAX de 12/11)`; vaga em reais, só a taxa do Y; sem a do X, nada."""
    moeda = item.sal_moeda or ""
    if moeda == "BRL":
        return _cotacao(idioma, y.moeda, "R$ " + taxa(str(y.venda), idioma), y.data.isoformat())
    data_x = _ler_data(item.sal_cotacao_data or "")
    if venda_x is None or data_x is None:
        return None
    try:
        cruzada = taxa_cruzada(venda_x, y.venda)
    except ArithmeticError:  # taxa que não cabe em 34 dígitos
        return None
    texto = f"{_SIMBOLO.get(y.moeda, y.moeda)} {taxa(str(cruzada), idioma)}"
    return _cotacao(idioma, moeda, texto, min(data_x.date(), y.data).isoformat())


def salario_texto(item: Item, idioma: str, exibicao: Exibicao | None = None) -> SalarioTexto | None:
    """O salário do cartão. Sem valor ou implausível (DR-25), nada: nunca um número duvidoso.

    O valor convertido e a cotação seguem a moeda de exibição Y; sem `exibicao`, vale Y = BRL com
    a conversão ligada. Vaga paga em Y, ou conversão desligada: só o `original`.
    """
    moeda = item.sal_moeda
    if moeda is None or item.sal_plausivel is False:
        return None
    if item.sal_min_centavos is None and item.sal_max_centavos is None:
        return None
    periodo = t(idioma, f"vagas.periodo.{item.sal_periodo}") if item.sal_periodo else ""
    original = _faixa((item.sal_min_centavos, item.sal_max_centavos), moeda, idioma) + periodo
    ex = exibicao or Exibicao("BRL", None, True)
    if moeda == ex.moeda or not ex.conversao_ligada:
        return SalarioTexto(original, None, None)
    venda_x = _venda(item.sal_cotacao_venda)
    if ex.moeda == "BRL":  # a vaga está em outra moeda
        cotacao = None
        if venda_x is not None and item.sal_cotacao_data:
            texto = "R$ " + taxa(str(venda_x), idioma)
            cotacao = _cotacao(idioma, moeda, texto, item.sal_cotacao_data)
        return SalarioTexto(original, _convertido(item, idioma, "BRL", None), cotacao)
    if ex.cotacao is None:  # sem a cotação de Y: o valor em reais, com a nota
        convertido = None if moeda == "BRL" else _convertido(item, idioma, "BRL", None)
        nota = t(idioma, "vagas.sem_cotacao_exibicao", moeda=ex.moeda) if convertido else None
        return SalarioTexto(original, convertido, nota)
    convertido = _convertido(item, idioma, ex.moeda, ex.cotacao.venda)
    return SalarioTexto(original, convertido, _cotacao_cruzada(item, idioma, venda_x, ex.cotacao))


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


def paises_texto(locais: Sequence[Local], idioma: str) -> str:
    """Países dos locais pelo nome: `Brasil, Portugal e Espanha`; mais de três: `A, B, C +2`.

    Vazio se nenhum local tem país.
    """
    nome = nome_em_ingles if idioma == "en" else nome_do_pais
    nomes = list(dict.fromkeys(nome(p.pais) or p.pais for p in locais if p.pais))
    if len(nomes) > _MAX_LOCAIS:
        return f"{', '.join(nomes[:_MAX_LOCAIS])} +{len(nomes) - _MAX_LOCAIS}"
    if len(nomes) > 1:
        return f"{', '.join(nomes[:-1])} {_E.get(idioma, _E['pt'])} {nomes[-1]}"
    return "".join(nomes)


def opcoes_de_pais(idioma: str) -> list[tuple[str, str]]:
    """(código, nome) de cada país que o leitor de locais conhece, em ordem alfabética do nome."""
    nome = nome_em_ingles if idioma == "en" else nome_do_pais
    pares = [(codigo, nome(codigo) or codigo) for codigo in codigos_de_pais()]
    return sorted(pares, key=lambda par: normalizar(par[1]))
