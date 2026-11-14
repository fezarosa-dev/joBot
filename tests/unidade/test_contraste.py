"""Contraste dos pares de cor do painel nos dois temas (desenho 13.11 e 13.12; critério 29)."""

import re

from jobot.painel.app import ESTATICOS

BASE_CSS = ESTATICOS / "css" / "base.css"
# cada cor do painel é `--nome: light-dark(#claro, #escuro);`, num lugar só do base.css
COR = re.compile(r"--([\w-]+):\s*light-dark\(\s*(#[0-9a-fA-F]{6})\s*,\s*(#[0-9a-fA-F]{6})\s*\)")
# o base.css lista os pares de texto sobre fundo: /* contraste: texto/fundo link/fundo ... */
PARES = re.compile(r"/\*\s*contraste:([^*]*)\*/")
MINIMO = 4.5


def _luminancia(cor: str) -> float:
    canais = [int(cor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canais)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _razao(a: str, b: str) -> float:
    clara, escura = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (clara + 0.05) / (escura + 0.05)


def test_formula_da_wcag() -> None:
    assert round(_razao("#000000", "#ffffff"), 2) == 21.0
    assert round(_razao("#777777", "#ffffff"), 2) == 4.48


def test_contraste_minimo() -> None:
    css = BASE_CSS.read_text(encoding="utf-8")
    cores = {nome: (claro, escuro) for nome, claro, escuro in COR.findall(css)}
    pares = [par.split("/") for bloco in PARES.findall(css) for par in bloco.split()]
    assert pares, "base.css sem a lista /* contraste: ... */"
    falhas = []
    for frente, fundo in pares:
        if frente not in cores or fundo not in cores:
            falhas.append(f"{frente}/{fundo}: cor sem light-dark() no base.css")
            continue
        for tema, i in (("claro", 0), ("escuro", 1)):
            razao = _razao(cores[frente][i], cores[fundo][i])
            if razao < MINIMO:
                falhas.append(f"{frente}/{fundo} no tema {tema}: {razao:.2f}")
    assert falhas == []
