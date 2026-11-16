"""Menu de contexto da vaga no navegador (T257; desenho 5.4): botão direito, Shift+F10, Esc e
Ocultar pelo menu com a faixa de desfazer."""

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.relogio import RelogioFalso

pytestmark = pytest.mark.tela

NOVA = "Engenheira de Integração"
OCULTA = "Vaga Ocultada"
MENU = "#menu-vaga"
ITENS = ("Abrir", "Abrir no site da vaga", "Salvar", "Ocultar", "Copiar link")


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    # o semeado é datado de `AGORA`: com o relógio real as vagas sairiam das abas de novas
    app_painel.state.relogio = RelogioFalso()
    return app_painel


def _linha(page: Page, titulo: str) -> Locator:
    return page.locator('#lista-vagas > [role="option"]').filter(has_text=titulo)


def _item(page: Page, nome: str) -> Locator:
    return page.get_by_role("menuitem", name=nome, exact=True)


def _abrir_pelo_teclado(page: Page, titulo: str) -> Locator:
    linha = _linha(page, titulo)
    linha.focus()
    page.keyboard.press("Shift+F10")
    expect(page.locator(MENU)).to_be_visible()
    return linha


def test_botao_direito_abre(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    linha = _linha(page, NOVA)
    linha.click(button="right", position={"x": 40, "y": 12})
    menu = page.locator(MENU)
    expect(menu).to_be_visible()
    expect(page.get_by_role("menuitem")).to_have_text(list(ITENS))
    # o menu nasce no ponteiro, não no meio da tela como o popover padrão; sem espaço embaixo,
    # abre para cima (a caixa da linha é lida depois do clique, que a rola para a vista)
    caixa, aberto = linha.bounding_box(), menu.bounding_box()
    assert caixa and aberto
    x, y = caixa["x"] + 40, caixa["y"] + 12
    assert abs(aberto["x"] - x) <= 1
    assert abs(aberto["y"] - y) <= 1 or abs(aberto["y"] + aberto["height"] - y) <= 1
    # pelo ponteiro nenhum item vem realçado: o foco fica no menu
    expect(menu).to_be_focused()
    # clique fora fecha (popover automático)
    page.locator("h1").click()
    expect(menu).to_be_hidden()
    # na vaga já oculta, Ocultar não está no menu: a HIG esconde o que não vale, não apaga
    page.goto(f"{painel}/vagas?aba=ocultas")
    _linha(page, OCULTA).click(button="right")
    expect(menu).to_be_visible()
    expect(_item(page, "Ocultar")).to_have_count(0)
    expect(_item(page, "Abrir")).to_be_visible()


def test_shift_f10_abre(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    # pelo teclado o primeiro item já vem realçado; as setas andam e dão a volta
    expect(_item(page, "Abrir")).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(_item(page, "Abrir no site da vaga")).to_be_focused()
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowUp")
    expect(_item(page, "Copiar link")).to_be_focused()
    page.keyboard.press("Home")
    expect(_item(page, "Abrir")).to_be_focused()


def test_esc_fecha_e_foco_volta(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    linha = _abrir_pelo_teclado(page, NOVA)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Escape")
    expect(page.locator(MENU)).to_be_hidden()
    expect(linha).to_be_focused()
    # o teclado da lista segue valendo
    page.keyboard.press("End")
    expect(page.locator('#lista-vagas > [role="option"]').last).to_be_focused()


def test_esc_do_menu_nao_fecha_o_detalhe_sobreposto(page: Page, painel: str) -> None:
    """Janela média: o detalhe abre por cima da lista e também fecha com Esc; com o menu aberto o
    primeiro Esc é só do menu (o ouvinte do detalhe respeita o `defaultPrevented`)."""
    page.set_viewport_size({"width": 1000, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    linha = _linha(page, NOVA)
    linha.focus()
    page.keyboard.press("Enter")
    detalhe = page.locator("#detalhe-vaga")
    expect(detalhe.get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    _abrir_pelo_teclado(page, NOVA)
    page.keyboard.press("Escape")
    expect(page.locator(MENU)).to_be_hidden()
    expect(linha).to_be_focused()
    expect(detalhe).to_be_visible()
    page.keyboard.press("Escape")
    expect(detalhe).to_be_hidden()


def test_esc_do_menu_nao_fecha_a_lateral_sobreposta(page: Page, painel: str) -> None:
    """O ouvinte de Esc da lateral sobreposta não olha o `defaultPrevented`: só o `stopPropagation`
    do menu (captura) a mantém aberta no primeiro Esc."""
    page.set_viewport_size({"width": 800, "height": 700})
    page.goto(f"{painel}/vagas?aba=todas")
    botao = page.get_by_role("banner").locator("[data-recolher]")
    botao.click()
    lateral = page.locator("aside.lateral")
    expect(lateral).to_be_visible()
    _abrir_pelo_teclado(page, NOVA)
    page.keyboard.press("Escape")
    expect(page.locator(MENU)).to_be_hidden()
    expect(lateral).to_be_visible()
    page.keyboard.press("Escape")
    expect(lateral).to_be_hidden()


def test_atalho_que_tira_a_linha_fecha_o_menu(page: Page, painel: str) -> None:
    """⇧⌘Z refaz o Ocultar e a linha sai da lista (sem `htmx:beforeSwap`): o menu aberto nela
    fecha junto, em vez de ficar apontando para uma vaga que já saiu."""
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    _item(page, "Ocultar").click()
    expect(page.locator("#faixa-desfazer")).to_contain_text("Vaga ocultada")
    expect(_linha(page, NOVA)).to_have_count(0)
    page.keyboard.press("ControlOrMeta+z")
    expect(page.locator("#faixa-desfazer")).to_contain_text("Vaga mostrada de novo")
    expect(_linha(page, NOVA)).to_be_focused()  # o foco só volta com a lista já recarregada
    _abrir_pelo_teclado(page, NOVA)
    page.keyboard.press("ControlOrMeta+Shift+z")
    expect(page.locator(MENU)).to_be_hidden()
    expect(page.locator("#faixa-desfazer")).to_contain_text("Vaga ocultada")
    expect(_linha(page, NOVA)).to_have_count(0)


def test_item_do_menu_com_o_alvo_fora_da_pagina_nao_age(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    pedidos: list[str] = []
    page.on("request", lambda r: pedidos.append(r.url) if r.method == "POST" else None)
    # a linha sai por um caminho que o menu não vê
    _linha(page, NOVA).evaluate("el => el.remove()")
    _item(page, "Ocultar").click()
    expect(page.locator(MENU)).to_be_hidden()
    page.wait_for_load_state("networkidle")
    assert pedidos == []


def test_ocultar_pelo_menu_traz_a_faixa(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    _linha(page, NOVA).click(button="right")
    with page.expect_response(lambda r: r.url.endswith("/ocultar")) as resposta:
        _item(page, "Ocultar").click()
    assert resposta.value.ok
    expect(page.locator(MENU)).to_be_hidden()
    expect(page.locator("#faixa-desfazer")).to_contain_text("Vaga ocultada")
    expect(_linha(page, NOVA)).to_have_count(0)
    # o foco fica numa linha que existe, como no Ocultar do detalhe ao lado
    expect(page.locator('#lista-vagas > [role="option"]:focus')).to_have_count(1)
