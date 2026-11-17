"""Contraste dos pares de cor do painel nos dois temas (desenho 13.11 e 13.12; critério 29)."""

import re

from jobot.painel.app import ESTATICOS

BASE_CSS = ESTATICOS / "css" / "base.css"
# cada cor do painel é `--nome: light-dark(#claro, #escuro);`, num lugar só do base.css
COR = re.compile(r"--([\w-]+):\s*light-dark\(\s*(#[0-9a-fA-F]{6})\s*,\s*(#[0-9a-fA-F]{6})\s*\)")
# o base.css lista os pares de texto sobre fundo: /* contraste: texto/fundo link/fundo ... */
PARES = re.compile(r"/\*\s*contraste:([^*]*)\*/")
# par de objeto gráfico (a barra de progresso sobre o trilho), a 3:1: /* contraste-grafico: a/b */
PARES_GRAFICOS = re.compile(r"/\*\s*contraste-grafico:([^*]*)\*/")
MINIMO = 4.5
MINIMO_GRAFICO = 3.0
PARES_NOVOS = (
    "texto-2/fundo texto-2/sob-pagina texto-2/superficie texto/solido-barra "
    "texto-2/solido-barra texto/solido-elevado texto-2/solido-elevado texto/segmento"
).split()

# os botões da janela desenhados pelo painel (T334; desenho 5.3) sobre a barra e o fundo, a 3:1
PARES_JANELA = [
    f"janela-{botao}/{fundo}"
    for botao in ("fechar", "minimizar", "maximizar", "inativa")
    for fundo in ("solido-barra", "fundo")
]


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


def _cores(css: str) -> dict[str, tuple[str, str]]:
    return {nome: (claro, escuro) for nome, claro, escuro in COR.findall(css)}


def _falhas(pares: list[str], cores: dict[str, tuple[str, str]], minimo: float) -> list[str]:
    falhas = []
    for par in pares:
        frente, fundo = par.split("/")
        if frente not in cores or fundo not in cores:
            falhas.append(f"{par}: cor sem light-dark() no base.css")
            continue
        for tema, i in (("claro", 0), ("escuro", 1)):
            razao = _razao(cores[frente][i], cores[fundo][i])
            if razao < minimo:
                falhas.append(f"{par} no tema {tema}: {razao:.2f}")
    return falhas


def _lista(regex: re.Pattern[str], css: str) -> list[str]:
    return [par for bloco in regex.findall(css) for par in bloco.split()]


def test_contraste_minimo() -> None:
    css = BASE_CSS.read_text(encoding="utf-8")
    pares = _lista(PARES, css)
    assert pares, "base.css sem a lista /* contraste: ... */"
    assert _falhas(pares, _cores(css), MINIMO) == []


def test_pares_novos_presentes() -> None:
    css = BASE_CSS.read_text(encoding="utf-8")
    texto = _lista(PARES, css)
    assert set(PARES_NOVOS) <= set(texto), set(PARES_NOVOS) - set(texto)
    assert len(texto) == len(set(texto)), "par repetido na lista de texto"
    grafico = _lista(PARES_GRAFICOS, css)
    assert grafico == ["destaque/trilho-progresso", *PARES_JANELA]
    # o comentário de objeto gráfico não entra na conta de texto (4,5:1)
    assert "destaque/trilho-progresso" not in texto


def test_contraste_grafico_minimo() -> None:
    css = BASE_CSS.read_text(encoding="utf-8")
    pares = _lista(PARES_GRAFICOS, css)
    assert pares, "base.css sem a lista /* contraste-grafico: ... */"
    assert _falhas(pares, _cores(css), MINIMO_GRAFICO) == []


def test_contraste_grafico_reprova_trilho_igual_ao_destaque() -> None:
    """Guarda: o mutante (trilho do progresso igual ao destaque) tem de aparecer como falha."""
    css = BASE_CSS.read_text(encoding="utf-8")
    cores = _cores(css)
    cores["trilho-progresso"] = cores["destaque"]
    assert len(_falhas(["destaque/trilho-progresso"], cores, MINIMO_GRAFICO)) == 2


def test_alerta_tem_par_com_superficie_e_com_fundo() -> None:
    """O vermelho do prazo urgente (D56) sai nos dois fundos: os pares entram na lista."""
    css = BASE_CSS.read_text(encoding="utf-8")
    pares = {par for bloco in PARES.findall(css) for par in bloco.split()}
    assert {"alerta/superficie", "alerta/fundo"} <= pares


def test_sucesso_tem_par_com_superficie_e_com_fundo() -> None:
    """O verde do resultado do teste da chave sai nos dois fundos: os pares entram na lista."""
    css = BASE_CSS.read_text(encoding="utf-8")
    pares = {par for bloco in PARES.findall(css) for par in bloco.split()}
    assert {"sucesso/superficie", "sucesso/fundo"} <= pares


def test_barra_do_panorama_usa_o_par_grafico() -> None:
    """T288 (desenho 5.3): a barra do Panorama pinta `--destaque` sobre o trilho
    `--trilho-progresso`, o par que o teste gráfico confere a 3:1 nos dois temas."""
    css = (ESTATICOS / "css" / "panorama.css").read_text(encoding="utf-8")
    assert "destaque/trilho-progresso" in _lista(PARES_GRAFICOS, BASE_CSS.read_text("utf-8"))
    barra = re.search(r"\.barra\s*\{([^}]*)\}", css)
    preenchimento = re.search(r"\.barra rect\s*\{([^}]*)\}", css)
    assert barra and preenchimento
    assert "background-color: var(--trilho-progresso)" in barra.group(1)
    assert "fill: var(--destaque)" in preenchimento.group(1)


def test_botoes_da_janela_reprovam_com_as_cores_do_mac_no_claro() -> None:
    """Guarda: o amarelo do Mac (#febc2e) sobre a barra clara não chega a 3:1."""
    cores = _cores(BASE_CSS.read_text(encoding="utf-8"))
    cores["janela-minimizar"] = ("#febc2e", "#febc2e")
    assert _falhas(["janela-minimizar/solido-barra"], cores, MINIMO_GRAFICO) == [
        "janela-minimizar/solido-barra no tema claro: 1.56"
    ]
