"""Tela de vagas no navegador: abas, URL, tecla /, ordens, mais, ações e teclado (T45, T254)."""

import json
import re
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from playwright.sync_api import Browser, Locator, Page, expect

from apoio.relogio import RelogioFalso
from apoio.semear import AGORA, inserir_vaga
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela

NOVA = "Engenheira de Integração"
HIMALAYAS = "Backend Engineer"


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    # o semeado é datado de `AGORA`: com o relógio real tudo viraria "velho" e fora dos destaques
    app_painel.state.relogio = RelogioFalso()
    return app_painel


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    return tmp_path / "jobot.db"


def _sql(banco: Path, texto: str, *params: Any) -> None:
    with closing(abrir(banco)) as con:
        con.execute(texto, params)
        con.commit()


def _config(banco: Path, chave: str, valor: object) -> None:
    _sql(
        banco,
        "INSERT INTO config (chave, valor) VALUES (?, ?)"
        " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        chave,
        json.dumps(valor),
    )


def _linhas(page: Page) -> Locator:
    """As linhas da lista: `<a role="option">` filhas diretas do listbox (T254)."""
    return page.locator('#lista-vagas > [role="option"]')


def _cartao(page: Page, titulo: str) -> Locator:
    return _linhas(page).filter(has_text=titulo)


def _titulos(page: Page) -> list[str]:
    return page.locator("#lista-vagas .linha-titulo").all_inner_texts()


def _sem_contagem(texto: str) -> str:
    return re.sub(r"\s+\d+$", "", texto.strip())


def _aguardar_lista(page: Page) -> None:
    expect(page.locator("#lista-vagas")).to_be_visible()


def test_abas_marcam_a_atual_e_a_url_reabre_a_tela(page: Page, painel: str) -> None:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.goto(f"{painel}/vagas?aba=todas")
    # as abas moram só na lateral (T254, D150 item 1): a tela não repete a fileira
    expect(page.locator("main nav.abas")).to_have_count(0)
    lateral = page.locator("#lateral-vagas")
    nomes = [_sem_contagem(n) for n in lateral.locator("a").all_inner_texts()]
    assert nomes == [
        "Destaques de hoje",
        "Todas",
        "Novas",
        "Fecham logo",
        "Salvas",
        "Candidatei",
        "Programas",
        "Ocultas",
    ]
    expect(page.locator('[aria-current="page"]')).to_have_count(1)
    todas = lateral.locator('[href^="/vagas?aba=todas"]')
    novas = lateral.locator('[href^="/vagas?aba=novas"]')
    expect(todas).to_have_attribute("aria-current", "page")
    novas.click()
    expect(page).to_have_url(re.compile(r"[?&]aba=novas"))
    expect(lateral.locator("[aria-current]")).to_have_count(1)
    expect(novas).to_have_attribute("aria-current", "page")
    expect(todas).not_to_have_attribute("aria-current", "page")

    page.reload()
    expect(novas).to_have_attribute("aria-current", "page")
    page.go_back()
    expect(todas).to_have_attribute("aria-current", "page")
    assert erros == []


def test_raiz_abre_nos_destaques(page: Page, painel: str, banco: Path) -> None:
    _config(banco, "primeira_execucao_concluida", True)
    page.goto(painel + "/")
    expect(page).to_have_url(re.compile(r"/vagas\?aba=destaques"))
    destaques = page.locator('#lateral-vagas [href^="/vagas?aba=destaques"]')
    expect(destaques).to_have_attribute("aria-current", "page")


def test_chip_vai_para_a_url_e_a_url_reabre_o_filtro(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    todos = len(_titulos(page))
    chip = page.locator("button.chip", has_text="Presencial")
    # os chips chegam depois da lista (T191): o expect espera por eles
    expect(chip).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#filtros-chips")).not_to_have_attribute("aria-busy", "true")
    esperado = int(chip.get_attribute("data-contagem") or "-1")
    assert 0 < esperado < todos

    chip.focus()
    page.keyboard.press("Enter")
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page).to_have_url(re.compile(r"modalidade=presencial"))
    assert len(_titulos(page)) == esperado
    # os chips novos chegam depois da lista: o foco tem de cair no chip clicado, não se perder
    expect(page.locator("button.chip", has_text="Presencial")).to_be_focused()

    page.reload()
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert len(_titulos(page)) == esperado

    page.locator("button.chip", has_text="Presencial").click()  # clicar de novo tira o filtro
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "false"
    )
    assert len(_titulos(page)) == todos


@pytest.mark.parametrize("falha", ["abort", "500"])
def test_chips_que_falham_deixam_de_esperar(page: Page, painel: str, falha: str) -> None:
    """Pedido dos chips com erro: o aria-busy sai e o texto de espera some (o aviso global fica)."""
    if falha == "abort":
        page.route("**/vagas/chips*", lambda rota: rota.abort())
    else:
        page.route("**/vagas/chips*", lambda rota: rota.fulfill(status=500, body="erro"))
    page.goto(f"{painel}/vagas?aba=todas")
    expect(page.locator("#lista-vagas")).to_be_visible()
    espera = page.locator("#filtros-chips")
    expect(espera).not_to_have_attribute("aria-busy", "true")
    expect(espera.locator("[data-espera]")).to_be_hidden()
    expect(page.locator("#aviso-erro")).to_be_visible()


def test_tecla_barra_foca_a_busca(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    # a busca mora na barra de ferramentas (T251) e manda o formulário da tela (form="busca")
    busca = page.get_by_role("banner").get_by_role("searchbox", name="Buscar em Vagas")
    expect(busca).to_have_attribute("data-busca", "")
    expect(busca).not_to_be_focused()
    page.keyboard.press("/")
    expect(busca).to_be_focused()
    expect(busca).to_have_value("")  # a barra não vai para dentro do campo
    page.keyboard.type("Backend")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"q=Backend"))
    assert _titulos(page) == [HIMALAYAS]
    page.reload()
    expect(page.locator("[data-busca]")).to_have_value("Backend")


@pytest.mark.parametrize(
    ("ordem", "primeira"),
    [
        ("encaixe", "Desenvolvedor Python"),
        ("recentes", NOVA),
        ("prazo", "Analista de Dados python"),
        ("salario", "Desenvolvedor Python"),
        ("empresa", "Analista de Sistemas"),
    ],
)
def test_cinco_ordens(page: Page, painel: str, ordem: str, primeira: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas&ordem=recentes")
    seletor = page.locator("#ordem")
    assert seletor.locator("option").count() == 5
    seletor.focus()
    seletor.select_option(ordem)
    expect(page).to_have_url(re.compile(rf"ordem={ordem}"))
    expect(page.locator("#ordem")).to_have_value(ordem)
    expect(page.locator("#lista-vagas .linha-titulo").first).to_have_text(primeira)
    page.reload()
    expect(page.locator("#ordem")).to_have_value(ordem)
    expect(page.locator("#lista-vagas .linha-titulo").first).to_have_text(primeira)


def test_carregar_mais(page: Page, painel: str, banco: Path) -> None:
    with closing(abrir(banco)) as con:
        for n in range(55):
            inserir_vaga(con, titulo=f"Extra {n}", empresa=f"Extra SA {n}")
    page.goto(f"{painel}/vagas?aba=todas")
    assert len(_titulos(page)) == 50
    mais = page.get_by_role("button", name="Carregar mais vagas")
    mais.focus()
    page.keyboard.press("Enter")
    expect(_linhas(page)).to_have_count(62)
    # o foco vai para a 1ª vaga nova, que vira a escolhida (a marca data-foco vale uma vez)
    expect(_linhas(page).nth(50)).to_be_focused()
    expect(_linhas(page).nth(50)).to_have_attribute("aria-selected", "true")
    expect(page.locator("#lista-vagas [data-foco]")).to_have_count(0)
    expect(page.locator('#lista-vagas > [role="option"][tabindex="0"]')).to_have_count(1)
    expect(page.get_by_role("button", name="Carregar mais vagas")).to_have_count(0)
    titulos = _titulos(page)
    assert len(set(titulos)) == len(titulos)


LADO = "#detalhe-vaga"


def _abrir_pelo_teclado(page: Page, titulo: str) -> None:
    """Foca a linha da vaga e abre com Return: na janela larga do teste, o detalhe abre ao lado da
    lista (T255), com o título em h2 (o h1 é o da página)."""
    _cartao(page, titulo).focus()
    page.keyboard.press("Enter")
    expect(page.locator(LADO).get_by_role("heading", level=2, name=titulo)).to_be_visible()


def test_salvar_mudar_a_situacao_ocultar_e_trazer_de_volta(page: Page, painel: str) -> None:
    """As ações saíram da linha (D143.53): moram no detalhe, que se abre com Return."""
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    lado = page.locator(LADO)
    situacao = lado.locator(".situacao")
    expect(situacao).to_have_text("Situação: Nova")

    lado.get_by_role("button", name="Salvar", exact=True).focus()
    page.keyboard.press("Enter")
    expect(situacao).to_have_text("Situação: Salva")
    lado.get_by_role("button", name="Me candidatei", exact=True).focus()
    page.keyboard.press("Enter")
    expect(situacao).to_have_text("Situação: Candidatei")
    lado.get_by_role("button", name=re.compile("^Desfazer")).focus()
    page.keyboard.press("Enter")
    expect(situacao).to_have_text("Situação: Salva")

    page.goto(f"{painel}/vagas?aba=salvas")  # o que mudou está no banco, não só na tela
    expect(_cartao(page, NOVA)).to_be_visible()

    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    lado.get_by_role("button", name="Ocultar", exact=True).focus()
    page.keyboard.press("Enter")
    expect(lado.get_by_text("Oculta por você")).to_be_visible()
    page.goto(f"{painel}/vagas?aba=todas")
    assert NOVA not in _titulos(page)
    page.goto(f"{painel}/vagas?aba=ocultas")
    expect(_cartao(page, NOVA)).to_be_visible()
    expect(_cartao(page, NOVA).get_by_text("Oculta por você")).to_be_visible()

    _abrir_pelo_teclado(page, NOVA)
    lado.get_by_role("button", name="Trazer de volta", exact=True).focus()
    page.keyboard.press("Enter")
    expect(lado.get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    expect(lado.get_by_text("Oculta por você")).to_have_count(0)
    page.goto(f"{painel}/vagas?aba=todas")
    assert NOVA in _titulos(page)


def test_tab_real_chega_a_lista_e_return_abre_a_vaga(page: Page, painel: str) -> None:
    """Tab pressionado de verdade (sem `focus()`) chega à lista numa parada só (tabindex móvel)."""
    page.goto(f"{painel}/vagas?aba=todas")
    primeira = _linhas(page).first
    expect(primeira).to_be_visible()
    for _ in range(150):  # teto: a ordem do Tab não pode ficar presa nem passar da lista
        page.keyboard.press("Tab")
        if primeira.evaluate("el => el === document.activeElement"):
            break
    else:
        pytest.fail("o Tab não chegou à lista de vagas")
    page.keyboard.press("Tab")  # uma parada só: o próximo Tab sai da lista
    focada = page.evaluate("() => document.activeElement.getAttribute('role')")
    assert focada != "option"
    page.keyboard.press("Shift+Tab")
    expect(primeira).to_be_focused()
    titulo = primeira.locator(".linha-titulo").inner_text()
    page.keyboard.press("Enter")  # T255: o detalhe abre ao lado e a URL guarda a vaga
    expect(page).to_have_url(re.compile(r"/vagas\?aba=todas&vaga=\d+$"))
    expect(page.locator(LADO).get_by_role("heading", level=2, name=titulo)).to_be_visible()


def test_setas_j_k_home_end_movem_o_foco_na_lista(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    linhas = _linhas(page)
    n = linhas.count()
    assert n >= 3
    expect(page.locator('#lista-vagas > [role="option"][tabindex="0"]')).to_have_count(1)
    linhas.nth(0).focus()

    passos = [
        ("ArrowDown", 1),
        ("j", 2),
        ("k", 1),
        ("ArrowUp", 0),
        ("ArrowUp", 0),  # na ponta, fica onde está
        ("End", n - 1),
        ("ArrowDown", n - 1),
        ("Home", 0),
    ]
    for tecla, esperada in passos:
        page.keyboard.press(tecla)
        expect(linhas.nth(esperada)).to_be_focused()
        # a seleção segue o foco, e só a escolhida fica no Tab
        expect(linhas.nth(esperada)).to_have_attribute("aria-selected", "true")
        expect(linhas.nth(esperada)).to_have_attribute("tabindex", "0")
        expect(page.locator('#lista-vagas [aria-selected="true"]')).to_have_count(1)
    page.keyboard.press("j")
    expect(linhas.nth(1)).to_be_focused()
    page.keyboard.press("Enter")  # Return abre a vaga escolhida ao lado (T255)
    expect(page).to_have_url(re.compile(r"[?&]vaga=\d+$"))
    expect(page.locator(LADO)).to_be_visible()
    expect(linhas.nth(1)).to_be_focused()  # o teclado da lista segue com o detalhe aberto
    page.keyboard.press("ArrowDown")
    expect(linhas.nth(2)).to_be_focused()
    expect(linhas.nth(2)).to_have_attribute("aria-selected", "true")
    page.go_back()
    expect(page).to_have_url(re.compile(r"aba=todas$"))


def test_teclado_da_lista_nao_age_em_campo_de_texto(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    _linhas(page).nth(0).focus()
    page.keyboard.press("/")  # da lista, a barra leva para a busca
    busca = page.locator("[data-busca]")
    expect(busca).to_be_focused()
    page.keyboard.type("jk")
    page.keyboard.press("Home")
    page.keyboard.press("End")
    expect(busca).to_have_value("jk")  # as letras entram no campo; nada se move na lista
    expect(busca).to_be_focused()
    page.keyboard.press("Escape")  # Esc limpa o campo (desenho 5.5)
    expect(busca).to_have_value("")


def test_sem_js_a_linha_e_um_link_comum(browser: Browser, painel: str) -> None:
    contexto = browser.new_context(java_script_enabled=False)
    try:
        pagina = contexto.new_page()
        pagina.goto(f"{painel}/vagas?aba=todas")
        linha = pagina.locator('#lista-vagas > [role="option"]', has_text=NOVA)
        assert linha.get_attribute("tabindex") is None  # sem JS, cada linha é um link no Tab
        linha.click()
        expect(pagina).to_have_url(re.compile(r"/vagas/\d+$"))
        expect(pagina.get_by_role("heading", level=1, name=NOVA)).to_be_visible()
    finally:
        contexto.close()


def test_barra_da_lista_tem_a_busca_e_troca_a_busca_escolhida(
    page: Page, painel: str, banco: Path
) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    barra = page.locator(".barra-lista")
    expect(barra.locator("form#busca")).to_have_count(1)  # o form da busca mora na barra
    expect(barra.locator("#ordem")).to_have_attribute("form", "busca")
    expect(barra.locator("#busca-escolhida")).to_have_count(0)  # uma busca só: sem menu

    _sql(
        banco,
        "INSERT INTO busca (nome, cargos, modalidades, ativa, criada_em)"
        " VALUES ('Segunda', '[\"cobol\"]', '[]', 1, ?)",
        AGORA.isoformat(),
    )
    page.goto(f"{painel}/vagas?aba=novas")
    seletor = page.locator(".barra-lista #busca-escolhida")
    expect(seletor.locator("option")).to_have_count(2)
    segunda = seletor.locator("option", has_text="Segunda").get_attribute("value")
    assert segunda
    seletor.select_option(segunda)
    expect(page).to_have_url(re.compile(rf"[?&]busca={segunda}\b"))
    expect(page).to_have_url(re.compile(r"[?&]aba=novas"))  # a aba fica
    expect(page.locator("#busca-escolhida")).to_have_value(segunda)
    page.reload()
    expect(page.locator("#busca-escolhida")).to_have_value(segunda)


def test_lista_vazia_oferece_buscar_vagas(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas&q=zzzznadaachado")
    vazio = page.locator("#lista-vagas.vazio")
    expect(vazio.get_by_role("heading", name="Nenhuma vaga")).to_be_visible()
    expect(vazio.get_by_role("button", name="Buscar vagas")).to_be_visible()
    expect(page.get_by_role("listbox")).to_have_count(0)


def test_pular_para_a_lista_leva_o_foco_para_ela(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    page.get_by_role("link", name="Pular para a lista de vagas").focus()
    page.keyboard.press("Enter")
    # o listbox recebe o foco e o passa para a linha escolhida (T254)
    expect(_linhas(page).first).to_be_focused()


def test_links_de_pular_ficam_invisiveis_ate_receber_foco(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    # o do miolo cai atrás da barra do topo translúcida: sem foco não pode aparecer (T146)
    pulos = page.locator(".pular")
    assert pulos.count() == 2
    for i in range(2):
        expect(pulos.nth(i)).to_have_css("opacity", "0")
        expect(pulos.nth(i)).to_have_css("pointer-events", "none")  # invisível não pega o mouse
    # continua focável com Tab, e aparece inteiro quando focado
    lista = page.get_by_role("link", name="Pular para a lista de vagas")
    for _ in range(40):  # a barra do topo e o menu vêm antes do conteúdo
        page.keyboard.press("Tab")
        if lista.evaluate("e => e === document.activeElement"):
            break
    expect(lista).to_be_focused()
    expect(lista).to_have_css("opacity", "1")
    expect(lista).to_have_css("pointer-events", "auto")
    expect(lista).to_be_in_viewport(ratio=1)


def test_links_de_pular_sem_foco_nao_pegam_o_mouse(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    # o ponto do centro da caixa: se cai na janela, o link não pode ser o que está ali (T146)
    pontos: list[dict[str, bool]] = page.eval_on_selector_all(
        ".pular",
        """els => els.map(e => {
          const r = e.getBoundingClientRect();
          const x = r.left + r.width / 2, y = r.top + r.height / 2;
          const dentro = x >= 0 && y >= 0 && x < innerWidth && y < innerHeight;
          return {dentro, pega: dentro && document.elementFromPoint(x, y) === e};
        })""",
    )
    assert len(pontos) == 2
    assert any(p["dentro"] for p in pontos)  # o do miolo tem o centro na janela: não é vácuo
    assert not any(p["pega"] for p in pontos), pontos


def test_sem_preferencia_pede_o_que_procura_e_destaques_vem_por_data(
    page: Page, painel: str, banco: Path
) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    expect(page.locator("[data-aviso=sem-criterio]")).to_have_count(0)

    _sql(banco, "DELETE FROM busca")
    with closing(abrir(banco)) as con:
        inserir_vaga(
            con,
            titulo="Velha",
            empresa="Velha SA",
            primeira_vista_em=(AGORA - timedelta(hours=3)).isoformat(),
            publicada_em=(AGORA - timedelta(hours=10)).isoformat(),
        )
        inserir_vaga(
            con,
            titulo="Recente",
            empresa="Recente Ltda",
            primeira_vista_em=(AGORA - timedelta(hours=2)).isoformat(),
            publicada_em=(AGORA - timedelta(hours=5)).isoformat(),
        )
    page.goto(f"{painel}/vagas?aba=destaques")
    aviso = page.locator("[data-aviso=sem-criterio]")
    expect(aviso).to_be_visible()
    expect(aviso.get_by_role("link", name="Dizer o que procuro")).to_be_visible()
    _aguardar_lista(page)
    assert _titulos(page)[:2] == ["Recente", "Velha"]
    expect(page.locator("#ordem")).to_have_count(0)  # destaques não tem ordem para escolher


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_mais_filtros_preenche_manda_e_mostra_na_url(
    page: Page, painel: str, banco: Path, esquema: str
) -> None:
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    with closing(abrir(banco)) as con:
        inserir_vaga(
            con,
            titulo="Vaga em São Paulo",
            uf="SP",
            cidade="São Paulo",
            sal_moeda="BRL",
            sal_min=900000,
            sal_periodo="mes",
            sal_mensal_min=900000,
            sal_mensal_min_brl=9000,
            sal_plausivel=1,
        )
    page.goto(f"{painel}/vagas?aba=todas")
    assert len(_titulos(page)) > 1
    page.get_by_text("Mais filtros", exact=True).click()
    page.get_by_label("Cidade", exact=True).fill("sao")
    campo = page.get_by_label("Salário de", exact=True)
    campo.fill("7000")
    with page.expect_response(lambda r: "cidade=sao" in r.url and "sal_de=7000" in r.url):
        campo.press("Enter")
    expect(page).to_have_url(re.compile(r"cidade=sao"))
    expect(page).to_have_url(re.compile(r"sal_de=7000"))
    expect(page.locator("#lista-vagas .linha-titulo")).to_have_count(1)
    assert _titulos(page) == ["Vaga em São Paulo"]


COR_TEXTO_2 = """() => {
  const e = document.createElement('i');
  e.style.color = 'var(--texto-2)';
  document.body.append(e);
  const cor = getComputedStyle(e).color;
  e.remove();
  return cor;
}"""


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_linha_em_tres_linhas_no_claro_e_no_escuro(page: Page, painel: str, esquema: str) -> None:
    """Desenho 5.8: título, empresa e local, salário e data, cada um numa linha que não quebra."""
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    page.goto(f"{painel}/vagas?aba=todas")
    linha = _cartao(page, "Desenvolvedor Python")
    caixas = [linha.locator(f".linha-{n}").bounding_box() for n in (1, 2, 3)]
    assert all(c is not None for c in caixas)
    um, dois, tres = caixas
    assert um and dois and tres
    assert dois["y"] >= um["y"] + um["height"] - 1
    assert tres["y"] >= dois["y"] + dois["height"] - 1
    salario = linha.locator(".linha-salario")
    expect(salario).to_have_text("≈ R$ 28.250/mês")
    expect(salario).to_have_attribute("title", re.compile(r"^US\$ 5\.000/mês · "))
    tamanho = "el => parseFloat(getComputedStyle(el).fontSize)"
    assert linha.locator(".linha-2").evaluate(tamanho) < linha.locator(".linha-1").evaluate(tamanho)
    cor = "el => getComputedStyle(el).color"
    assert linha.locator(".linha-2").evaluate(cor) == page.evaluate(COR_TEXTO_2)
    for n in (1, 2, 3):  # texto longo corta com reticências, sem quebrar a linha
        assert linha.locator(f".linha-{n}").evaluate("el => getComputedStyle(el).whiteSpace") == (
            "nowrap"
        )


def test_linha_escolhida_pinta_todo_o_texto_com_a_cor_da_selecao(page: Page, painel: str) -> None:
    """Com o foco na lista, nem o "Salário não informado" (neto da linha) fica cinza no azul."""
    page.goto(f"{painel}/vagas?aba=todas")
    linha = _linhas(page).filter(has=page.locator(".nao-informado")).first
    linha.focus()
    expect(linha).to_have_attribute("aria-selected", "true")
    cor = "el => getComputedStyle(el).color"
    esperada = linha.evaluate(cor)
    assert esperada != page.evaluate(COR_TEXTO_2)
    for parte in linha.locator("span, time").all():
        assert parte.evaluate(cor) == esperada


# --- T255: o detalhe ao lado da lista ---

MODO = "el => getComputedStyle(el).getPropertyValue('--detalhe-modo').trim()"
FUNDO_DE = """(cor) => {
  const e = document.createElement('i');
  e.style.backgroundColor = cor;
  document.body.append(e);
  const fundo = getComputedStyle(e).backgroundColor;
  e.remove();
  return fundo;
}"""


def _abrir_ao_lado(page: Page, titulo: str) -> None:
    _cartao(page, titulo).click()
    expect(page.locator(LADO).get_by_role("heading", level=2, name=titulo)).to_be_visible()


def _largura_do_miolo(page: Page) -> float:
    return float(page.locator("#vagas-miolo").evaluate("el => el.getBoundingClientRect().width"))


def test_coluna_larga_abre_ao_lado(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas&ordem=recentes")
    assert _largura_do_miolo(page) >= 860
    expect(page.locator(LADO)).to_be_hidden()  # sem vaga na URL, nada ao lado
    _abrir_ao_lado(page, NOVA)
    # a URL guarda a vista (aba e ordem) e a vaga; a página não troca
    expect(page).to_have_url(re.compile(r"/vagas\?aba=todas&ordem=recentes&vaga=\d+$"))
    expect(page.get_by_role("heading", level=1, name="Vagas")).to_be_visible()
    assert page.locator(LADO).evaluate(MODO) == "coluna"
    lista = page.locator("#lista-vagas").bounding_box()
    lado = page.locator(LADO).bounding_box()
    assert lista and lado
    assert lado["x"] >= lista["x"] + lista["width"]  # ao lado, sem cobrir a lista
    assert 320 <= lado["width"] <= 380
    expect(_cartao(page, NOVA)).to_have_attribute("aria-selected", "true")
    assert not page.locator(LADO).evaluate("el => el.matches(':modal')")
    # fontes, motivo do encaixe e os botões que saíram da linha
    lado_loc = page.locator(LADO)
    expect(lado_loc.get_by_role("link", name=re.compile("^via "))).not_to_have_count(0)
    expect(lado_loc.get_by_role("heading", level=3, name="Encaixe com a sua busca")).to_be_visible()
    for nome in ("Salvar", "Ocultar"):
        expect(lado_loc.get_by_role("button", name=nome, exact=True)).to_be_visible()
    expect(lado_loc.get_by_role("link", name=re.compile("^Abrir no site"))).to_be_visible()


def test_coluna_entre_640_e_860_abre_sobreposto(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1000, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    assert 640 <= _largura_do_miolo(page) < 860
    _abrir_ao_lado(page, NOVA)
    assert page.locator(LADO).evaluate(MODO) == "sobreposto"
    assert not page.locator(LADO).evaluate("el => el.matches(':modal')")  # a lista segue usável
    lista = page.locator("#lista-vagas").bounding_box()
    lado = page.locator(LADO).bounding_box()
    assert lista and lado
    assert lado["x"] < lista["x"] + lista["width"]  # por cima da lista, encostado à direita
    assert abs((lado["x"] + lado["width"]) - (lista["x"] + lista["width"])) <= 2
    assert lado["width"] <= min(420, 0.6 * _largura_do_miolo(page)) + 1
    # clicar na lista, fora de uma linha, fecha o sobreposto; fora da lista, não
    page.locator(".barra-lista").dispatch_event("click")
    expect(page.locator(LADO)).to_be_visible()
    page.locator(".coluna-lista").dispatch_event("click")
    expect(page.locator(LADO)).to_be_hidden()
    expect(page).to_have_url(re.compile(r"/vagas\?aba=todas$"))


def test_recarregar_abre_a_mesma_vaga(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    url = page.url
    page.reload()
    expect(page).to_have_url(url)
    expect(page.locator(LADO).get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    expect(_cartao(page, NOVA)).to_have_attribute("aria-selected", "true")
    expect(page.locator('#lista-vagas [aria-selected="true"]')).to_have_count(1)


def test_esc_fecha_o_sobreposto(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1000, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    _cartao(page, NOVA).focus()
    page.keyboard.press("Enter")
    expect(page.locator(LADO).get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    assert page.locator(LADO).evaluate(MODO) == "sobreposto"
    page.keyboard.press("Escape")
    expect(page.locator(LADO)).to_be_hidden()
    expect(page).to_have_url(re.compile(r"/vagas\?aba=todas$"))
    expect(_cartao(page, NOVA)).to_be_focused()  # o foco volta à linha
    seguinte = _cartao(page, NOVA).locator("xpath=following-sibling::*[@role='option'][1]")
    page.keyboard.press("ArrowDown")  # e o teclado da lista segue valendo, a partir da linha
    expect(seguinte).to_be_focused()
    expect(seguinte).to_have_attribute("aria-selected", "true")


def test_janela_inativa_selecao_cinza(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    linha = _cartao(page, NOVA)
    linha.focus()
    expect(linha).to_be_focused()
    expect(linha).to_have_attribute("aria-selected", "true")
    fundo = "el => getComputedStyle(el).backgroundColor"
    destaque = page.evaluate(FUNDO_DE, "var(--destaque)")
    inativa = page.evaluate(FUNDO_DE, "var(--selecao-inativa)")
    assert destaque != inativa
    assert linha.evaluate(fundo) == destaque  # janela ativa, foco na lista: azul
    page.evaluate("() => { document.documentElement.dataset.janela = 'inativa'; }")
    expect(linha).to_be_focused()
    assert linha.evaluate(fundo) == inativa  # janela inativa: cinza, mesmo com o foco na lista
    # o foco no detalhe (a outra coluna) também deixa a linha cinza
    page.evaluate("() => { delete document.documentElement.dataset.janela; }")
    page.locator(LADO).get_by_role("button", name="Salvar", exact=True).focus()
    assert linha.evaluate(fundo) == inativa


def test_clique_sem_foco_marca_a_linha_aberta(page: Page, painel: str) -> None:
    """Safari e Firefox do Mac não focam o <a> clicado: a marca vem da resposta, não do foco."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    outra = _linhas(page).filter(has_not_text=NOVA).first
    titulo = outra.locator(".linha-titulo").inner_text()
    with page.expect_response(lambda r: "vaga=" in r.url):
        outra.evaluate("el => el.click()")  # clique que não leva o foco, como no Safari
    expect(page.locator(LADO).get_by_role("heading", level=2, name=titulo)).to_be_visible()
    expect(outra).not_to_be_focused()
    expect(outra).to_have_attribute("aria-selected", "true")
    expect(page.locator('#lista-vagas [aria-selected="true"]')).to_have_count(1)


def test_sem_foco_a_linha_aberta_fica_azul(page: Page, painel: str) -> None:
    """Desenho 5.2: sem foco em coluna nenhuma (aqui, depois de recarregar), a lista conta como
    ativa; com a janela inativa, a linha volta ao cinza."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    page.reload()
    linha = _cartao(page, NOVA)
    expect(linha).to_have_attribute("aria-selected", "true")
    assert page.evaluate("() => !document.querySelector(':focus')")
    fundo = "el => getComputedStyle(el).backgroundColor"
    assert linha.evaluate(fundo) == page.evaluate(FUNDO_DE, "var(--destaque)")
    page.evaluate("() => { document.documentElement.dataset.janela = 'inativa'; }")
    assert linha.evaluate(fundo) == page.evaluate(FUNDO_DE, "var(--selecao-inativa)")
