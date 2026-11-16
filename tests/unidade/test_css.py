"""Regras do CSS do painel: vidro, movimento, tipo e controles (desenho 5.1, 5.3 e 5.7; T248)."""

import re
from typing import NamedTuple

import pytest

from jobot.painel.app import ESTATICOS

PASTA = ESTATICOS / "css"
BASE = PASTA / "base.css"
REDUZIDO = "@media (prefers-reduced-motion: reduce)"


class Regra(NamedTuple):
    contexto: tuple[str, ...]  # at-rules que envolvem a regra, de fora para dentro
    seletor: str
    corpo: str


def _sem_comentarios(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _fecha(texto: str, abre: int) -> int:
    """Índice logo depois do `}` que fecha o `{` em `abre` (chaves contadas)."""
    fundo = 0
    for i in range(abre, len(texto)):
        fundo += {"{": 1, "}": -1}.get(texto[i], 0)
        if fundo == 0:
            return i + 1
    raise AssertionError("chave sem par")


def _regras(texto: str, contexto: tuple[str, ...] = ()) -> list[Regra]:
    """Regras de um CSS sem comentários; `@media` e `@supports` são abertos, o resto é folha."""
    achadas: list[Regra] = []
    i = 0
    while (abre := texto.find("{", i)) != -1:
        cabeca = texto[i:abre].strip()
        fim = _fecha(texto, abre)
        corpo = texto[abre + 1 : fim - 1]
        if cabeca.startswith(("@media", "@supports")):
            achadas += _regras(corpo, (*contexto, cabeca))
        else:
            achadas.append(Regra(contexto, cabeca, corpo))
        i = fim
    return achadas


def _todas() -> list[tuple[str, Regra]]:
    achadas = []
    for arquivo in sorted(PASTA.glob("*.css")):
        css = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
        achadas += [(arquivo.name, r) for r in _regras(css)]
    return achadas


def _base() -> str:
    return _sem_comentarios(BASE.read_text(encoding="utf-8"))


def _seletores(regra: Regra) -> list[str]:
    return [s.strip() for s in regra.seletor.split(",")]


def _valor(regra: Regra, propriedade: str) -> str | None:
    achado = re.search(rf"(?:^|[;\s]){re.escape(propriedade)}\s*:\s*([^;]+)", regra.corpo)
    return achado.group(1).strip() if achado else None


def test_o_leitor_de_css_enxerga_as_regras() -> None:
    """Guarda dos testes abaixo: sem regras lidas, todos passariam por vazio."""
    todas = _todas()
    assert len(todas) > 100
    assert {nome for nome, _ in todas} >= {"base.css", "vagas.css", "configuracoes.css"}
    aninhada = _regras("@media (a) { .x, .y { c: d } } .z { e: f }")
    assert [(r.contexto, r.seletor) for r in aninhada] == [(("@media (a)",), ".x, .y"), ((), ".z")]


def test_backdrop_filter_so_no_vidro() -> None:
    fora = [
        f"{nome}: {r.seletor}"
        for nome, r in _todas()
        if "backdrop-filter" in r.corpo
        and not all(re.search(r"\.vidro(-grande)?(?![\w-])", s) for s in _seletores(r))
    ]
    assert fora == []


def test_sem_letter_spacing() -> None:
    com = [nome for nome, r in _todas() if "letter-spacing" in r.corpo]
    assert com == []


def _tamanho_em_px(valor: str) -> float:
    numero = float(re.match(r"[\d.]+", valor).group())  # type: ignore[union-attr]
    return numero * 16 if valor.endswith("rem") else numero


def test_nada_abaixo_de_10px() -> None:
    pequenos = []
    for nome, r in _todas():
        for achado in re.findall(r"font-size\s*:\s*([\d.]+(?:rem|px))", r.corpo):
            if _tamanho_em_px(achado) < 10:
                pequenos.append(f"{nome}: {r.seletor}: {achado}")
        # tokens de tipo: `--t-x: peso tamanho/entrelinha`
        for achado in re.findall(r"--t-[\w-]+\s*:\s*\d+\s+([\d.]+(?:rem|px))/", r.corpo):
            if _tamanho_em_px(achado) < 10:
                pequenos.append(f"{nome}: {r.seletor}: {achado}")
    assert pequenos == []


def test_tokens_de_tipo_da_escala_do_mac() -> None:
    corpo = "".join(r.corpo for _, r in _todas() if r.seletor == ":root")
    esperado = {
        "large": "26/32",
        "title1": "22/26",
        "title2": "17/22",
        "title3": "15/20",
        "headline": "13/16",
        "body": "13/16",
        "callout": "12/15",
        "sub": "11/14",
        "foot": "10/13",
        "cap1": "10/13",
        "cap2": "10/13",
    }
    achado = {}
    for nome, peso, tam, linha in re.findall(
        r"--t-([\w]+)\s*:\s*(\d+)\s+([\d.]+)rem/([\d.]+)rem", corpo
    ):
        assert int(peso) in (400, 500, 600, 700), nome
        achado[nome] = f"{round(float(tam) * 16)}/{round(float(linha) * 16)}"
    assert achado == esperado
    assert re.search(r"--t-headline\s*:\s*700\b", corpo)


def test_tokens_de_tipo_trazem_a_familia() -> None:
    """`font: var(--t-x)` só vale com a família no fim: sem ela o atalho é inválido na hora do
    valor computado, vira `unset` e o corpo sai em 16px em vez de 13px (CI da tela de texto)."""
    corpo = "".join(r.corpo for _, r in _todas() if r.seletor == ":root")
    assert _valor(next(r for _, r in _todas() if r.seletor == ":root"), "--familia")
    tokens = re.findall(r"(--t-[\w-]+)\s*:\s*([^;]+);", corpo)
    assert len(tokens) == 11
    sem_familia = [nome for nome, valor in tokens if not valor.strip().endswith("var(--familia)")]
    assert sem_familia == []


def test_font_com_token_de_tipo_nao_repete_a_familia() -> None:
    """A regra que usa `font: var(--t-x)` não leva `font-family` (a família já vem no token)."""
    usos = [(n, r) for n, r in _todas() if re.search(r"font\s*:\s*var\(--t-", r.corpo)]
    assert len(usos) >= 3  # guarda: sem usos lidos, o teste passaria por vazio
    com_familia = [f"{n}: {r.seletor}" for n, r in usos if "font-family" in r.corpo]
    assert com_familia == []


def test_html_respeita_o_tamanho_do_navegador() -> None:
    regra = next(r for _, r in _todas() if r.seletor == "html")
    assert _valor(regra, "font-size") == "100%"


def test_body_no_tamanho_do_corpo() -> None:
    regra = next(r for n, r in _todas() if n == "base.css" and r.seletor == "body")
    assert "var(--t-body)" in regra.corpo
    assert "1.0625rem" not in regra.corpo
    # a família vem no token (`--t-body` termina em `var(--familia)`), não em `font-family`
    assert "font-family" not in regra.corpo


def test_botoes_com_1_75rem() -> None:
    regras = [r for r in _regras(_base()) if not r.contexto]
    botao = next((r for r in regras if "button" in _seletores(r)), None)
    assert botao, "base.css sem regra de button"
    assert _valor(botao, "min-block-size") == "1.75rem"
    campo = next((r for r in regras if 'input[type="text"]' in _seletores(r)), None)
    assert campo, "base.css sem regra do campo de texto"
    assert _valor(campo, "min-block-size") == "1.75rem"
    assert _valor(campo, "border-radius") == "var(--raio-controle)"


def test_sem_min_height_de_2_5rem() -> None:
    """Nenhum botão, campo ou menu do painel fica com o 2.5rem de antes.

    Controles de 2rem e 2.25rem (.chip, .opcao, .config-grupos a) ficam para as
    tarefas de cada tela (T251 em diante)."""
    antigos = [f"{n}: {r.seletor}" for n, r in _todas() if "min-height: 2.5rem" in r.corpo]
    assert antigos == []


def test_cursor_pointer_so_em_link() -> None:
    erradas = [
        f"{nome}: {s}"
        for nome, r in _todas()
        if _valor(r, "cursor") == "pointer"
        for s in _seletores(r)
        if not (re.match(r"a\b", s) or "[href]" in s)
    ]
    assert erradas == []


def test_botao_tem_cursor_default() -> None:
    botao = next((r for r in _regras(_base()) if "button" in _seletores(r)), None)
    assert botao, "base.css sem regra de button"
    assert _valor(botao, "cursor") == "default"


def test_sem_scale_no_active() -> None:
    com = [
        f"{n}: {r.seletor}" for n, r in _todas() if ":active" in r.seletor and "scale(" in r.corpo
    ]
    assert com == []


def _mola(nome: str) -> list[float]:
    """Os valores de `linear(...)` do `:root` do base.css, na ordem."""
    achado = re.search(rf"--{nome}\s*:\s*linear\(([^)]*)\)", _base())
    assert achado, f"--{nome} sem linear(...)"
    return [float(item.split()[0]) for item in achado.group(1).split(",")]


@pytest.mark.parametrize("nome", ["mola-suave", "mola-leve"])
def test_mola_tem_vinte_pontos(nome: str) -> None:
    pontos = _mola(nome)
    assert len(pontos) >= 20
    assert pontos[0] == 0
    assert pontos[-1] == 1


def test_molas_sem_rebote_alem_do_previsto() -> None:
    assert max(_mola("mola-suave")) <= 1
    assert 1 < max(_mola("mola-leve")) <= 1.006


def test_mola_de_reserva_e_padrao() -> None:
    css = _base()
    assert "cubic-bezier(0.22, 1, 0.36, 1)" in css
    assert re.search(r"--mola\s*:\s*var\(--mola-suave\)", css)
    assert re.search(r"--duracao\s*:\s*190ms", css)


def test_caminho_solido_completo() -> None:
    regras = _regras(_base())

    def tira_o_filtro(contexto: str, seletor: str = ".vidro") -> list[Regra]:
        return [
            r
            for r in regras
            if (contexto in " ".join(r.contexto) or contexto in r.seletor)
            and any(re.search(rf"{re.escape(seletor)}(?![\w-])", s) for s in _seletores(r))
            and re.search(r"(?<!-webkit-)backdrop-filter\s*:\s*none", r.corpo)
        ]

    for contexto in (
        "@media (prefers-reduced-transparency: reduce)",
        "@media (prefers-contrast: more)",
        "@supports not (backdrop-filter",
        '[data-janela="inativa"]',
    ):
        assert tira_o_filtro(contexto), contexto
        assert tira_o_filtro(contexto, ".vidro-grande"), contexto
    mais = tira_o_filtro("@media (prefers-contrast: more)")
    assert any("1px solid var(--texto)" in r.corpo for r in mais)


def test_so_o_vidro_tem_filtro_e_o_fundo_solido_vem_do_token() -> None:
    css = _base()
    assert "--vidro-blur: 24px" in css
    assert "--vidro-blur-grande: 40px" in css
    assert "--vidro-sat: 1.4" in css
    assert re.search(r"--vidro-fundo\s*:\s*color-mix\(in srgb, var\(--solido-barra\) 72%", css)
    assert re.search(
        r"--vidro-fundo-grande\s*:\s*color-mix\(in srgb, var\(--solido-barra\) 85%", css
    )


def test_painel_e_topo_sem_vidro_proprio() -> None:
    regras = {r.seletor: r for r in _regras(_base()) if not r.contexto}
    assert "var(--superficie)" in regras[".painel"].corpo
    assert "backdrop-filter" not in regras[".painel"].corpo
    assert "backdrop-filter" not in regras[".topo"].corpo


def test_topo_usa_a_classe_vidro() -> None:
    template = (ESTATICOS.parent / "templates" / "base.html").read_text(encoding="utf-8")
    assert '<header class="topo vidro">' in template


def test_raios_e_sombras_novos() -> None:
    css = _base()
    for pedaco in (
        "--raio-controle: 6px",
        "--raio-grande: 10px",
        "--raio: 10px",
        "--raio-sheet: 18px",
        "--sombra-cor:",
        "--sombra-cor-forte:",
        "--borda-elevada:",
    ):
        assert pedaco in css, pedaco


def test_movimento_reduzido_por_ultimo_e_sem_transform() -> None:
    css = _base()
    inicio = css.rindex(REDUZIDO)
    fim = _fecha(css, css.index("{", inicio))
    assert css[fim:].strip() == "", "há regra depois do bloco de movimento reduzido"
    bloco = css[inicio:fim]
    assert re.search(r"transform\s*:\s*none\s*!important", bloco)
    assert re.search(r"animation(-name)?\s*:\s*none\s*!important", bloco)
    duracao = re.search(r"transition-duration\s*:\s*(\d+)ms", bloco)
    assert duracao and int(duracao.group(1)) <= 150
    assert "transform" not in re.search(r"transition-property\s*:([^;]+);", bloco).group(1)  # type: ignore[union-attr]


def test_lateral_sobreposta_comeca_abaixo_da_barra() -> None:
    """Janela média (T251): a lateral aberta por cima do conteúdo começa abaixo da barra, que fica
    por cima dela; nunca vidro sobre vidro, e o botão de recolher continua clicável. A lateral fica
    na grade, nas linhas abaixo da barra, e não num offset fixo: se a barra quebrar linha, ela segue
    a altura real."""
    css = _sem_comentarios((PASTA / "casca.css").read_text(encoding="utf-8"))
    media = {r.seletor: r for r in _regras(css) if any("899.98px" in c for c in r.contexto)}
    lateral = media[":root[data-js] .lateral"]
    assert _valor(lateral, "grid-row") == "2 / -1"
    assert _valor(lateral, "grid-column") == "1 / -1"
    assert _valor(lateral, "position") != "fixed"
    assert not re.search(r"(?:^|[;\s])inset", lateral.corpo)
    assert int(_valor(media[":root[data-js] .topo"], "z-index") or 0) > int(
        _valor(lateral, "z-index") or 0
    )
    raiz = next(r for r in _regras(_base()) if r.seletor == ":root" and not r.contexto)
    assert _valor(raiz, "--barra-altura") == "52px"
    topo = next(r for r in _regras(_base()) if r.seletor == ".topo" and not r.contexto)
    assert _valor(topo, "min-block-size") == "var(--barra-altura)"


def test_link_de_pular_fica_acima_da_barra() -> None:
    """O link de pular é o primeiro foco da página: nenhuma barra pode cobri-lo (WCAG 2.4.11),
    em nenhuma faixa de largura."""
    pular = next(r for r in _regras(_base()) if r.seletor == ".pular" and not r.contexto)
    barras = [
        int(z)
        for _, r in _todas()
        if any(re.search(r"\.topo(?![\w-])", s) for s in _seletores(r))
        and (z := _valor(r, "z-index")) is not None
    ]
    assert barras
    assert int(_valor(pular, "z-index") or 0) > max(barras)


def test_ancora_do_progresso_fica_no_proprio_componente() -> None:
    """O nome de âncora é global: com a barra do topo e o componente do corpo na mesma página, o
    popover de um se ancoraria no último .progresso do DOM. anchor-scope o prende ao seu (T252)."""
    css = _sem_comentarios((PASTA / "execucao.css").read_text(encoding="utf-8"))
    progresso = next(r for r in _regras(css) if r.seletor == ".progresso" and not r.contexto)
    assert _valor(progresso, "anchor-name") == "--andamento"
    assert _valor(progresso, "anchor-scope") == "--andamento"
