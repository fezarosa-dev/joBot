"""Menu de contexto da vaga no navegador (T257; desenho 5.4): botão direito, Shift+F10, Esc,
Ocultar pelo menu com a faixa de desfazer, busca por letra e Copiar link (T305)."""

from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from jobot.banco.conexao import abrir
from jobot.painel.i18n import t

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


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://x.test/vaga"])
def test_menu_sem_data_site_desabilita_abrir_no_site(
    page: Page, painel: str, tmp_path: Path, url: str
) -> None:
    """T305 (d): endereço que não é `http`/`https` não vira `data-site` na linha; o menu abre sem
    "Abrir no site da vaga" e sem "Copiar link" (a HIG esconde o que não vale) e nada navega."""
    with closing(abrir(tmp_path / "jobot.db")) as con:
        vaga_id = inserir_vaga(con, titulo="Vaga Sem Site")
        # o modelo recusa esse endereço na coleta: simula dado antigo ou estragado no banco
        con.execute("UPDATE vaga SET url = ? WHERE id = ?", (url, vaga_id))
        con.commit()
    page.goto(f"{painel}/vagas?aba=todas")
    endereco = page.url
    linha = _abrir_pelo_teclado(page, "Vaga Sem Site")
    assert linha.get_attribute("data-site") is None
    expect(page.get_by_role("menuitem")).to_have_text(["Abrir", "Salvar", "Ocultar"])
    menu = page.locator(MENU)
    expect(menu.locator('a[data-requer="site"]')).to_be_hidden()
    expect(menu.locator('[href^="javascript"], [href^="ftp"]')).to_have_count(0)
    # as setas e as letras só andam pelos itens que valem: o link escondido nunca é escolhido
    page.keyboard.press("End")
    expect(_item(page, "Ocultar")).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(_item(page, "Abrir")).to_be_focused()
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    assert page.url == endereco


def test_letra_pula_para_o_item(page: Page, painel: str) -> None:
    """T305 (e): como no menu do Mac, a letra leva ao item que começa por ela; letras digitadas
    em até 500 ms se juntam (relógio do navegador, parado aqui e movido só pelo fast_forward)."""
    page.goto(f"{painel}/vagas?aba=todas")
    page.clock.install(time=0)
    page.clock.pause_at(1000)
    _abrir_pelo_teclado(page, NOVA)
    expect(_item(page, "Abrir")).to_be_focused()
    page.keyboard.press("s")
    expect(_item(page, "Salvar")).to_be_focused()
    page.clock.fast_forward(600)
    page.keyboard.press("c")
    expect(_item(page, "Copiar link")).to_be_focused()
    # "co" junto segue no Copiar link; sozinho, o "o" iria ao Ocultar
    page.keyboard.press("o")
    expect(_item(page, "Copiar link")).to_be_focused()
    page.clock.fast_forward(600)
    page.keyboard.press("o")
    expect(_item(page, "Ocultar")).to_be_focused()
    # a mesma letra de novo percorre os itens que começam por ela, dando a volta
    page.clock.fast_forward(600)
    page.keyboard.press("a")
    expect(_item(page, "Abrir")).to_be_focused()
    page.clock.fast_forward(600)
    page.keyboard.press("A")
    expect(_item(page, "Abrir no site da vaga")).to_be_focused()
    # letra sem item que case deixa o realce onde está
    page.clock.fast_forward(600)
    page.keyboard.press("z")
    expect(_item(page, "Abrir no site da vaga")).to_be_focused()
    expect(page.locator(MENU)).to_be_visible()


def test_letra_repetida_depressa_cicla_como_no_finder(page: Page, painel: str) -> None:
    """T311 (b): a mesma letra repetida dentro de 500 ms cicla entre os itens que começam por
    ela (não vira "aa", que não casa com nada); o relógio do navegador fica parado."""
    page.goto(f"{painel}/vagas?aba=todas")
    page.clock.install(time=0)
    page.clock.pause_at(1000)
    _abrir_pelo_teclado(page, NOVA)
    expect(_item(page, "Abrir")).to_be_focused()
    page.keyboard.press("a")
    expect(_item(page, "Abrir no site da vaga")).to_be_focused()
    page.keyboard.press("a")  # sem fast_forward: ainda na janela de 500 ms
    expect(_item(page, "Abrir")).to_be_focused()
    page.keyboard.press("a")
    expect(_item(page, "Abrir no site da vaga")).to_be_focused()


def test_copiar_link_negado_mostra_nao_copiou(page: Page, painel: str) -> None:
    """T305 (f): a cópia recusada (ou sem `clipboard`) cai no `catch` do `copiarLink` e a região
    viva do menu diz que não copiou, sem erro no console."""
    erros: list[str] = []
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.add_init_script(
        "navigator.clipboard.writeText = () => Promise.reject(new Error('negado'))"
    )
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    _item(page, "Copiar link").click()
    expect(page.locator(MENU)).to_be_hidden()
    expect(page.locator(f"{MENU}-aviso")).to_have_text(t("pt", "vagas.menu.nao_copiou"))
    assert erros == []
