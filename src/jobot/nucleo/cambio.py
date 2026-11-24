"""Câmbio: PTAX do Banco Central e a conta em reais (desenho 10.3; apêndice 6; plano T25).

Só o pedido passa pelo `HttpEducado`; a leitura da resposta e a conta são puras. Unidades: o valor
original entra em centavos da moeda; o valor em reais sai em reais inteiros (colunas `_brl`).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import (
    MAX_PREC,
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_UP,
    Context,
    Decimal,
    InvalidOperation,
)
from fractions import Fraction
from urllib.parse import quote

from jobot.nucleo.http import HttpEducado

MOEDAS = ("AUD", "CAD", "CHF", "DKK", "EUR", "GBP", "JPY", "NOK", "SEK", "USD")
MOEDAS_EXIBICAO: tuple[str, ...] = ("BRL", *MOEDAS)
BASE = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
JANELA_DIAS = 7  # o pedido cobre os 7 dias antes do dia pedido: fim de semana e feriado caem aqui
_RECURSO = (
    "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)
# contas de Decimal exatas: o contexto padrão (28 dígitos) arredonda número grande em silêncio
_EXATO = Context(prec=MAX_PREC)


@dataclass(frozen=True, kw_only=True)
class Cotacao:
    moeda: str
    data: date  # dia do boletim (pode ser anterior ao dia pedido)
    venda: Decimal  # reais por 1 unidade da moeda


def _mm_dd_aaaa(dia: date) -> str:
    return f"{dia.month:02d}-{dia.day:02d}-{dia.year:04d}"


def _url(moeda: str, dia: date) -> str:
    # O servidor responde 400 quando o espaço do $filter vai como "+": a consulta é montada aqui,
    # com %20, e não pelo `params` do httpx.
    params = {
        "@moeda": f"'{moeda}'",
        "@dataInicial": f"'{_mm_dd_aaaa(dia - timedelta(days=JANELA_DIAS))}'",
        "@dataFinalCotacao": f"'{_mm_dd_aaaa(dia)}'",
        "$format": "json",
        "$filter": "tipoBoletim eq 'Fechamento'",
    }
    consulta = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in params.items())
    return f"{BASE}{_RECURSO}?{consulta}"


def _venda(valor: object) -> Decimal | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):  # Decimal(int) direto: str(int) estoura o limite de 4.300 dígitos
        numero = Decimal(valor)
    elif isinstance(valor, Decimal):
        numero = valor
    else:
        return None
    return numero if numero.is_finite() and numero > 0 else None


def _linha(item: object, inicio: date, fim: date) -> tuple[datetime, Decimal] | None:
    if not isinstance(item, dict) or item.get("tipoBoletim") != "Fechamento":
        return None
    quando = item.get("dataHoraCotacao")
    venda = _venda(item.get("cotacaoVenda"))
    if venda is None or not isinstance(quando, str):
        return None
    try:
        momento = datetime.fromisoformat(quando)
    except ValueError:
        return None
    return (momento, venda) if inicio <= momento.date() <= fim else None


def _ler(texto: str, moeda: str, dia: date) -> Cotacao | None:
    try:
        dados = json.loads(texto, parse_float=Decimal)  # parse_float: a venda nunca passa por float
    except ValueError, RecursionError:
        return None
    itens = dados.get("value") if isinstance(dados, dict) else None
    if not isinstance(itens, list):
        return None
    inicio = dia - timedelta(days=JANELA_DIAS)
    linhas = [r for r in (_linha(i, inicio, dia) for i in itens) if r is not None]
    if not linhas:
        return None
    momento, venda = max(linhas, key=lambda r: r[0])
    return Cotacao(moeda=moeda, data=momento.date(), venda=venda)


async def buscar_cotacao(http: HttpEducado, moeda: str, dia: date) -> Cotacao | None:
    """PTAX de fechamento (cotação de venda) mais recente até `dia`, na janela de 7 dias.

    Devolve `None` para moeda fora de `MOEDAS` (sem pedido), janela sem fechamento ou resposta
    que não segue o formato. Falha de rede ou bloqueio sobe como as exceções do `HttpEducado`:
    quem chama decide (a vaga fica sem valor em reais, não some).
    """
    if moeda not in MOEDAS:
        return None
    resposta = await http.pedir("GET", _url(moeda, dia))
    return _ler(resposta.texto, moeda, dia) if resposta.status == 200 else None


def em_reais(valor_centavos: int, cotacao: Decimal) -> int:
    """Centavos da moeda original vezes a cotação, em reais inteiros (ROUND_HALF_UP)."""
    if not cotacao.is_finite() or cotacao <= 0:
        raise ValueError(f"cotação inválida: {cotacao!r}")
    try:
        reais = _EXATO.multiply(Decimal(valor_centavos), cotacao).scaleb(-2, _EXATO)
        return int(reais.quantize(Decimal(1), rounding=ROUND_HALF_UP, context=_EXATO))
    except InvalidOperation as erro:
        raise ValueError(f"valor fora do alcance: {valor_centavos!r}") from erro


MOEDA_DO_PAIS: Mapping[str, str] = {
    "BR": "BRL",
    **dict.fromkeys(("AT", "BE", "DE", "ES", "FI", "FR", "GR", "IE", "IT", "NL", "PT"), "EUR"),
    "US": "USD",
    "GB": "GBP",
    "CA": "CAD",
    "AU": "AUD",
    "CH": "CHF",
    "JP": "JPY",
    "SE": "SEK",
    "NO": "NOK",
    "DK": "DKK",
}


def moeda_do_pais(pais: str) -> str:
    """Moeda de exibição padrão do país; fora do mapa, o dólar."""
    return MOEDA_DO_PAIS.get(pais, "USD")


def em_reais_inteiros(unidades: int, venda: Decimal, *, para_cima: bool) -> int:
    """`unidades` da moeda vezes a venda, em reais inteiros: teto (`para_cima`) ou piso."""
    if not venda.is_finite() or venda <= 0:
        raise ValueError(f"cotação inválida: {venda!r}")
    reais = _EXATO.multiply(Decimal(unidades), venda)
    modo = ROUND_CEILING if para_cima else ROUND_FLOOR
    return int(reais.quantize(Decimal(1), rounding=modo, context=_EXATO))


def de_reais(reais: int, venda: Decimal) -> int:
    """Unidades inteiras da moeda que valem `reais`: `reais / venda`, meio para cima."""
    if not venda.is_finite() or venda <= 0:
        raise ValueError(f"cotação inválida: {venda!r}")
    razao = Fraction(reais) / Fraction(venda)  # exato: a divisão em Decimal pode não terminar
    q, r = divmod(razao.numerator, razao.denominator)
    return q + 1 if 2 * r >= razao.denominator else q


def taxa_cruzada(venda_x: Decimal, venda_y: Decimal) -> Decimal:
    """Quantas unidades de Y valem 1 de X (`venda_x / venda_y`), em 4 casas, meio para cima."""
    for venda in (venda_x, venda_y):
        if not venda.is_finite() or venda <= 0:
            raise ValueError(f"cotação inválida: {venda!r}")
    taxa = Context(prec=34, rounding=ROUND_HALF_UP).divide(venda_x, venda_y)
    return taxa.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
