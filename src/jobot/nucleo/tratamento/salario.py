"""Leitura de salário (desenho 10.3, DR-25, DP4). Só biblioteca padrão.

Valores de `Salario` em centavos da moeda original. As faixas de `dados/salario.json` vêm em
unidades inteiras da moeda, mensais: `mensal` é a faixa plausível; `hora_ate` e `ano_desde`
deduzem o período pela ordem de grandeza quando o texto não diz. Moeda sem faixa: implausível
(não dá para conferir). O valor em reais não é daqui.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import MAX_PREC, Context, Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from jobot.nucleo.modelo import Periodo, Salario, SalarioBruto


def _simples(texto: str) -> str:
    """Minúsculo e sem acento; cada caractere vira um só."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in texto).lower()


def _alternativas(termos: list[str]) -> str:
    return "|".join(re.escape(t) for t in sorted(termos, key=len, reverse=True))


_DADOS: dict[str, Any] = json.loads(
    (Path(__file__).parent.parent / "dados" / "salario.json").read_text(encoding="utf-8")
)
_MOEDAS: dict[str, str] = {_simples(k): v for k, v in _DADOS["moedas"].items()}
_BENEFICIOS: dict[str, str] = {
    _simples(termo): nome for nome, termos in _DADOS["beneficios"].items() for termo in termos
}
_FAIXAS: dict[str, dict[str, Any]] = _DADOS["faixas"]

_PADRAO_POR_IDIOMA = {"pt": "BRL", "en": "USD"}  # DP4: sem moeda no texto
_LIMITE_TEXTO = 2000  # caracteres
# contas de Decimal exatas: o contexto padrão (28 dígitos) arredonda número grande em silêncio
_EXATO = Context(prec=MAX_PREC)
PARA_MENSAL: dict[Periodo, Fraction] = {
    "hora": Fraction(160),
    "dia": Fraction(21),
    "semana": Fraction(433, 100),
    "mes": Fraction(1),
    "ano": Fraction(1, 12),
}

_MULTIPLICADORES = {
    "k": 1000,
    "mil": 1000,
    "thousand": 1000,
    "m": 1_000_000,
    "mi": 1_000_000,
    "milhao": 1_000_000,
    "milhoes": 1_000_000,
    "million": 1_000_000,
    "millions": 1_000_000,
}
_MOEDA_TXT = rf"(?<![a-z])(?:{_alternativas(list(_MOEDAS))})(?![a-z])"
# "401k" logo depois de símbolo ou código de moeda é valor, não benefício ("$401k", "US$ 401k",
# "USD 401k"); "$401(k)" e "$ bonus" seguem benefício. O lookbehind tem largura fixa: o texto
# chega com espaços repetidos reduzidos a um só (`ler_salario`). O `\b` barra palavra que termina
# no código ("years 401k", "Fraud 401k"); código colado no número já cai no `(?<![a-z])`.
_SIMBOLO = "[" + re.escape("".join(sorted({m[-1] for m in _MOEDAS if not m[-1].isalnum()}))) + "]"
_APOS_CODIGO = "|".join(rf"(?<=\b{re.escape(c)}\s)\d+k" for c in _MOEDAS if c[-1].isalnum())
_BENEFICIO_TXT = (
    rf"(?<![a-z])(?!(?<={_SIMBOLO})\d+k|(?<={_SIMBOLO}\s)\d+k|{_APOS_CODIGO})"
    rf"(?:{_alternativas(list(_BENEFICIOS))})(?![a-z])"
)
# "m²"/"m³"/"m2"/"m3" (área, volume) não é milhão: o lookahead barra expoente e dígito
_NUMERO_TXT = rf"\d+(?:[.,]\d+)*(?:\s*(?:{_alternativas(list(_MULTIPLICADORES))})(?![a-z²³\d]))?"
_RE_MOEDA = re.compile(_MOEDA_TXT)
_RE_BENEFICIO = re.compile(_BENEFICIO_TXT)
# benefício com o valor dele ("R$ 600 de VR", "VR de R$ 30", "bônus de até 3") sai do salário
_RE_BENEFICIO_COM_VALOR = re.compile(
    rf"(?:(?:{_MOEDA_TXT})?\s*{_NUMERO_TXT}\s*(?:de|of|em|in)\s+)?{_BENEFICIO_TXT}"
    rf"(?:\s*(?:de|of|:|=|\()?\s*(?:ate|up to)?\s*(?:{_MOEDA_TXT})?\s*{_NUMERO_TXT})?"
)
_RE_SEGMENTO = re.compile(r"\s*(?:[+;|\n]|,\s)\s*")
_RE_VALOR = re.compile(
    rf"(?<![\w.,])(\d+(?:[.,]\d+)*)(?:\s*({_alternativas(list(_MULTIPLICADORES))})(?![a-z²³\d]))?"
)
# número que é duração, porcentagem, ordinal ou parte de palavra ("40 horas", "10%", "13º", "6x1")
_RE_NAO_VALOR = re.compile(
    r"[a-z%ºª°]|\s*(?:%|hs?\b|hrs?\b|horas\b|hours\b|dias\b|days\b|semanas\b|weeks\b"
    r"|meses\b|months\b|anos\b|years\b)"
)
# rótulos que não quebram a faixa ("Min $50k - Max $70k")
_RE_ROTULO = re.compile(r"\b(?:min|minimo|minimum|max|maximo|maximum)\b\.?:?")
_RE_LIGA = re.compile(r"\s*(?:-|–|—|~|a|ate|to|e|and)\s*")
_RE_SO_MAXIMO = re.compile(r"\b(?:ate|up to|max|maximo)\b")
_RE_SO_MINIMO = re.compile(
    r"\b(?:a partir de|from|starting at|acima de|mais de|min|minimo|desde)\b"
)
_PERIODOS: tuple[tuple[Periodo, re.Pattern[str]], ...] = (
    ("hora", re.compile(r"/\s*(?:h|hr|hora|hour)\b|\b(?:por hora|per hour|an hour|hourly)\b")),
    ("dia", re.compile(r"/\s*(?:dia|day)\b|\b(?:por dia|per day|daily|diaria)\b")),
    ("semana", re.compile(r"/\s*(?:semana|week|wk)\b|\b(?:por semana|per week|weekly|semanal)\b")),
    (
        "mes",
        re.compile(
            r"/\s*(?:mes|month|mo|mth)\b"
            r"|\b(?:por mes|ao mes|mes|per month|a month|monthly|mensal|mensais|mensalmente)\b"
        ),
    ),
    (
        "ano",
        re.compile(
            r"/\s*(?:ano|year|yr)\b"
            r"|\b(?:por ano|ao ano|anual|anuais|anualmente|per year|a year|per annum|annual"
            r"|annually|yearly)\b|\ba\.a\.?(?!\w)"
        ),
    ),
)


@dataclass(frozen=True)
class _Valor:
    ini: int
    fim: int
    numero: Decimal
    multiplicador: int

    @property
    def unidades(self) -> Decimal:
        return _EXATO.multiply(self.numero, self.multiplicador)


def _numero(token: str) -> Decimal:
    """`5.000,00`, `5,000.00`, `5.000`, `5,5`: o último separador com 1-2 dígitos é decimal."""
    if "." in token and "," in token:
        decimal = "." if token.rfind(".") > token.rfind(",") else ","
        inteiro, _, fracao = token.rpartition(decimal)
        return Decimal(re.sub(r"[.,]", "", inteiro) + "." + fracao)
    partes = re.split(r"[.,]", token)
    if len(partes) == 2 and len(partes[1]) != 3:
        return Decimal(partes[0] + "." + partes[1])
    return Decimal("".join(partes))


def _valores(trecho: str) -> list[_Valor]:
    achados = []
    for m in _RE_VALOR.finditer(trecho):
        if m.group(2) is None and _RE_NAO_VALOR.match(trecho, m.end()):
            continue
        multiplicador = _MULTIPLICADORES[m.group(2)] if m.group(2) else 1
        valor = _Valor(m.start(), m.end(), _numero(m.group(1)), multiplicador)
        if valor.unidades > 0:  # "R$ 0,00" marca "a combinar"
            achados.append(valor)
    return achados


def _periodo(trecho: str) -> Periodo | None:
    achados = [(m.start(), p) for p, r in _PERIODOS if (m := r.search(trecho))]
    return min(achados)[1] if achados else None


def _moeda(*trechos: str) -> str | None:
    for trecho in trechos:
        if m := _RE_MOEDA.search(trecho):
            return _MOEDAS[m.group()]
    return None


_Lido = tuple[str | None, Decimal | None, Decimal | None, Periodo | None]


def _do_texto(simples: str) -> _Lido | None:
    for trecho in _RE_SEGMENTO.split(_RE_BENEFICIO_COM_VALOR.sub(";", simples)):
        if valores := _valores(trecho):
            break
    else:
        return None
    primeiro = valores[0]
    minimo: Decimal | None = primeiro.unidades
    maximo: Decimal | None = primeiro.unidades
    entre = trecho[primeiro.fim : valores[1].ini] if len(valores) > 1 else ""
    entre = _RE_ROTULO.sub("", _RE_MOEDA.sub("", entre))
    # "R$ 4.000 por mês a R$ 6.000" é faixa; "R$ 25/hora e R$ 4.000/mês" não. Vale só o período
    # colado no segundo valor, até o próximo número ou parêntese ("(13 salários por ano)")
    p_entre = _periodo(entre)
    p_colado = None
    if len(valores) > 1:
        colado = re.split(r"[\d(]", trecho[valores[1].fim :], maxsplit=1)[0]
        p_colado = _periodo(colado)
        if p_colado in (None, p_entre):
            for _, termo in _PERIODOS:
                entre = termo.sub("", entre)
    if len(valores) > 1 and _RE_LIGA.fullmatch(entre):
        segundo = valores[1]
        # "120-150k": o "k" do segundo vale para o primeiro
        um = primeiro.unidades
        if primeiro.multiplicador == 1 < segundo.multiplicador and primeiro.numero < segundo.numero:
            um = _EXATO.multiply(primeiro.numero, segundo.multiplicador)
        minimo, maximo = sorted((um, segundo.unidades))
        # só um lado diz o período e o máximo passa de 10 vezes o mínimo: não é faixa, vale o
        # valor que tem período (d2 da T10)
        if (p_entre is None) != (p_colado is None) and maximo > _EXATO.multiply(minimo, 10):
            minimo = maximo = (primeiro if p_entre else segundo).unidades
    else:
        antes = _RE_MOEDA.sub("", trecho[: primeiro.ini])
        if _RE_SO_MAXIMO.search(antes):
            minimo = None
        elif _RE_SO_MINIMO.search(antes):
            maximo = None
    return _moeda(trecho, simples), minimo, maximo, _periodo(trecho)


def _decimal(valor: float) -> Decimal:
    # int direto: Decimal(str(int)) estoura acima de 4.300 dígitos
    return Decimal(valor if isinstance(valor, int) else str(valor))


def _positivo(valor: float | None) -> Decimal | None:
    # json.loads lê 1e400 como inf e inteiro grande como int (math.isfinite estoura): sem float
    numero = None if valor is None else _decimal(valor)
    return numero if numero is not None and numero.is_finite() and numero > 0 else None


def _do_estruturado(bruto: SalarioBruto | None) -> _Lido | None:
    if bruto is None:
        return None
    minimo, maximo = _positivo(bruto.minimo_unidades), _positivo(bruto.maximo_unidades)
    if minimo is None and maximo is None:  # RemoteOK: 0 quer dizer ausente
        return None
    codigo = (bruto.moeda or "").strip()
    moeda = _MOEDAS.get(_simples(codigo)) or (
        codigo.upper() if re.fullmatch(r"[A-Za-z]{3}", codigo) else None
    )
    return moeda, minimo, maximo, bruto.periodo


def _deduz_periodo(moeda: str, unidades: Decimal) -> Periodo:
    faixa = _FAIXAS.get(moeda)
    if faixa is None:
        return "mes"
    if unidades <= faixa["hora_ate"]:
        return "hora"
    if unidades >= faixa["ano_desde"]:
        return "ano"
    return "mes"


def _centavos(unidades: Decimal | None) -> int | None:
    return None if unidades is None else round(_EXATO.multiply(unidades, 100))


def mensal(centavos: int | None, periodo: Periodo) -> int | None:
    return None if centavos is None else round(centavos * PARA_MENSAL[periodo])


def ler_salario(texto: str | None, estruturado: SalarioBruto | None, idioma: str) -> Salario | None:
    # texto longo não é lido: as regex ficam quadráticas numa sequência longa de dígitos
    simples = _simples(texto) if texto and len(texto) <= _LIMITE_TEXTO else ""
    simples = re.sub(r"[^\S\n]+", " ", simples)  # espaço repetido vira um (a quebra de linha fica)
    lido = _do_estruturado(estruturado) or _do_texto(simples)
    if lido is None:
        return None
    moeda, minimo, maximo, periodo = lido
    moeda = moeda or _moeda(simples) or _PADRAO_POR_IDIOMA.get(idioma)  # DP4 só sem moeda escrita
    if moeda is None:
        return None
    deduzido = periodo is None
    if periodo is None:
        periodo = _deduz_periodo(moeda, minimo if minimo is not None else maximo or Decimal(0))
    minimo_c, maximo_c = _centavos(minimo), _centavos(maximo)
    mensal_minimo = mensal(minimo_c, periodo)
    referencia = mensal_minimo if mensal_minimo is not None else mensal(maximo_c, periodo)
    faixa = _FAIXAS.get(moeda)
    plausivel = (
        faixa is not None
        and referencia is not None
        and faixa["mensal"][0] * 100 <= referencia <= faixa["mensal"][1] * 100
    )
    if texto is None and estruturado is not None:
        numeros = (estruturado.minimo_unidades, estruturado.maximo_unidades)
        valores = "-".join(f"{_EXATO.normalize(_decimal(v)):f}" for v in numeros if v)
        partes = (estruturado.moeda, valores, estruturado.periodo)
        texto = " ".join(p for p in partes if p)
    return Salario(
        moeda=moeda,
        minimo=minimo_c,
        maximo=maximo_c,
        periodo=periodo,
        mensal_minimo=mensal_minimo,
        plausivel=plausivel,
        texto=texto or "",
        beneficios=tuple(
            dict.fromkeys(_BENEFICIOS[b.group()] for b in _RE_BENEFICIO.finditer(simples))
        ),
        periodo_deduzido=deduzido,
    )
