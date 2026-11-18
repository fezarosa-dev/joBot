"""Tela de buscas no navegador: criar, editar, desligar, apagar e o seletor (T52, T259)."""

import re

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.console import anotar_erros
from apoio.relogio import RelogioFalso

pytestmark = pytest.mark.tela

PRESENCIAL = "Analista de Sistemas"  # a única vaga semeada que a busca "Só remoto" esconde


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()
    return app_painel


def _cartoes(page: Page) -> Locator:
    return page.locator("#lista-buscas > li")


def _cartao(page: Page, nome: str) -> Locator:
    return _cartoes(page).filter(has=page.get_by_role("heading", name=nome, exact=True))


def _criar(page: Page, painel: str, nome: str, *, remoto: bool = False, salario: str = "") -> None:
    page.goto(f"{painel}/buscas")
    formulario = page.locator(".nova form")
    formulario.locator("#busca-nome").fill(nome)
    formulario.locator("#busca-salario").fill(salario)
    if remoto:
        formulario.get_by_label("Remoto").check()
    formulario.get_by_role("button", name="Criar busca").click()


def test_criar_busca_com_erro_de_digitacao_e_depois_certo(page: Page, painel: str) -> None:
    # o 422 do primeiro envio é esperado e o navegador o registra no console
    erros = anotar_erros(page, ignorar="422")
    page.goto(f"{painel}/buscas")
    expect(_cartoes(page)).to_have_count(1)

    formulario = page.locator(".nova form")
    formulario.locator("#busca-nome").fill("Dados em Curitiba")
    formulario.locator("#busca-cargos").fill("analista de dados")
    formulario.locator("#busca-cidades").fill("Curitiba, PR")
    formulario.locator("#busca-salario").fill("abc")
    formulario.get_by_role("button", name="Criar busca").click()
    expect(page.get_by_role("alert")).to_contain_text("Salário inválido")
    expect(page.locator(".nova #busca-nome")).to_have_value("Dados em Curitiba")
    expect(page.locator(".nova #busca-salario")).to_have_value("abc")
    expect(_cartoes(page)).to_have_count(1)

    page.locator(".nova #busca-salario").fill("5.000,50")
    page.locator(".nova").get_by_label("Remoto").check()
    page.locator(".nova").get_by_role("button", name="Criar busca").click()
    expect(page).to_have_url(re.compile(r"/buscas$"))
    expect(_cartoes(page)).to_have_count(2)
    expect(_cartao(page, "Dados em Curitiba")).to_contain_text("R$ 5.000,50")
    expect(_cartao(page, "Dados em Curitiba")).to_contain_text("Curitiba, PR")
    assert erros == []


def test_editar_muda_o_nome_e_mostra_o_formulario_preenchido(page: Page, painel: str) -> None:
    _criar(page, painel, "Dados em Curitiba", remoto=True, salario="5000")
    _cartao(page, "Dados em Curitiba").get_by_role("link", name="Editar busca").click()
    expect(page).to_have_url(re.compile(r"/buscas/\d+$"))
    expect(page.locator("#busca-nome")).to_have_value("Dados em Curitiba")
    expect(page.locator("#busca-salario")).to_have_value("5000")
    expect(page.get_by_label("Remoto")).to_be_checked()
    expect(page.get_by_label("Presencial")).not_to_be_checked()

    page.locator("#busca-nome").fill("Dados em Londrina")
    page.get_by_role("button", name="Salvar").click()
    expect(page).to_have_url(re.compile(r"/buscas$"))
    expect(_cartao(page, "Dados em Londrina")).to_have_count(1)
    expect(_cartao(page, "Dados em Curitiba")).to_have_count(0)


def test_desligar_e_ligar_pelo_interruptor(page: Page, painel: str) -> None:
    _criar(page, painel, "Outra busca")
    cartao = _cartao(page, "Outra busca")
    expect(cartao.get_by_text("Desligada", exact=True)).to_have_count(0)
    expect(cartao.get_by_role("switch")).to_be_checked()

    cartao.get_by_role("switch").click()
    expect(_cartao(page, "Outra busca").get_by_text("Desligada", exact=True)).to_be_visible()
    expect(_cartao(page, "Outra busca").get_by_role("switch")).not_to_be_checked()
    _cartao(page, "Outra busca").get_by_role("switch").click()
    expect(_cartao(page, "Outra busca").get_by_text("Desligada", exact=True)).to_have_count(0)


def test_interruptor_mini_pelo_teclado(page: Page, painel: str) -> None:
    """O interruptor é um checkbox: Tab chega nele e o Espaço liga e desliga, sem o mouse."""
    _criar(page, painel, "Outra busca")
    chave = _cartao(page, "Outra busca").get_by_role("switch")
    chave.focus()
    expect(chave).to_be_focused()
    page.keyboard.press("Space")
    expect(_cartao(page, "Outra busca").get_by_text("Desligada", exact=True)).to_be_visible()
    _cartao(page, "Outra busca").get_by_role("switch").focus()
    page.keyboard.press("Space")
    expect(_cartao(page, "Outra busca").get_by_text("Desligada", exact=True)).to_have_count(0)


def _abrir_alerta(page: Page, nome: str) -> Locator:
    _cartao(page, nome).get_by_role("button", name="Apagar", exact=True).click()
    alerta = page.get_by_role("alertdialog")
    expect(alerta).to_be_visible()
    return alerta


def test_apagar_abre_o_alerta_e_cancelar_nao_apaga(page: Page, painel: str) -> None:
    _criar(page, painel, "Outra busca")
    alerta = _abrir_alerta(page, "Outra busca")
    expect(alerta).to_contain_text("Apagar a busca «Outra busca»?")
    expect(alerta).to_contain_text("As vagas que ela trouxe continuam.")
    expect(alerta).to_be_focused()  # o foco fica no próprio alerta, nunca num botão (E13)

    alerta.get_by_role("button", name="Cancelar").click()
    expect(alerta).to_be_hidden()
    expect(
        _cartao(page, "Outra busca").get_by_role("button", name="Apagar", exact=True)
    ).to_be_focused()
    expect(_cartoes(page)).to_have_count(2)

    alerta = _abrir_alerta(page, "Outra busca")
    alerta.get_by_role("button", name="Apagar", exact=True).click()
    expect(_cartoes(page)).to_have_count(1)
    expect(_cartao(page, "Outra busca")).to_have_count(0)


def test_menu_de_contexto_apagar_abre_o_alerta_e_esc_devolve_o_foco(
    page: Page, painel: str
) -> None:
    _criar(page, painel, "Outra busca")
    _cartao(page, "Outra busca").click(button="right", position={"x": 40, "y": 12})
    page.get_by_role("menuitem", name="Apagar…").click()
    alerta = page.get_by_role("alertdialog")
    expect(alerta).to_be_visible()
    expect(alerta).to_contain_text("Outra busca")
    page.keyboard.press("Control+.")  # Command+ponto no Mac: o mesmo atalho de cancelar
    expect(alerta).to_be_hidden()
    expect(_cartoes(page)).to_have_count(2)
    expect(
        _cartao(page, "Outra busca").get_by_role("button", name="Apagar", exact=True)
    ).to_be_focused()

    _cartao(page, "Outra busca").click(button="right", position={"x": 40, "y": 12})
    page.get_by_role("menuitem", name="Apagar…").click()
    page.keyboard.press("Escape")
    expect(page.get_by_role("alertdialog")).to_be_hidden()


def test_return_ao_abrir_nao_apaga(page: Page, painel: str) -> None:
    _criar(page, painel, "Outra busca")
    alerta = _abrir_alerta(page, "Outra busca")
    page.keyboard.press("Enter")
    expect(alerta).to_be_visible()
    page.reload()
    expect(_cartoes(page)).to_have_count(2)
    expect(_cartao(page, "Outra busca")).to_have_count(1)


def test_esc_cancela(page: Page, painel: str) -> None:
    _criar(page, painel, "Outra busca")
    alerta = _abrir_alerta(page, "Outra busca")
    page.keyboard.press("Escape")
    expect(alerta).to_be_hidden()
    expect(_cartoes(page)).to_have_count(2)


def test_clique_no_veu_nao_fecha_e_tab_fica_dentro(page: Page, painel: str) -> None:
    _criar(page, painel, "Outra busca")
    alerta = _abrir_alerta(page, "Outra busca")
    page.mouse.click(5, 5)  # o véu
    expect(alerta).to_be_visible()
    for _ in range(6):
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.closest('dialog') !== null")


def test_seletor_da_lista_muda_a_url_e_a_lista(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    # o seletor é um menu na barra da lista (T254): só aparece com duas buscas ou mais
    expect(page.locator("#busca-escolhida")).to_have_count(0)  # uma busca só: sem seletor

    _criar(page, painel, "Só remoto", remoto=True)
    page.goto(f"{painel}/vagas?aba=todas")
    seletor = page.locator(".barra-lista #busca-escolhida")
    opcoes = seletor.locator("option")
    expect(opcoes).to_have_count(2)
    primeira = opcoes.nth(0).get_attribute("value")
    segunda = opcoes.nth(1).get_attribute("value")
    assert primeira and segunda
    expect(seletor).to_have_value(primeira)
    titulos = page.locator("#lista-vagas .linha-titulo", has_text=PRESENCIAL)
    expect(titulos).to_have_count(1)

    seletor.select_option(segunda)  # o form muda sozinho no change (HTMX)
    expect(page).to_have_url(re.compile(rf"[?&]busca={segunda}\b"))
    expect(page).to_have_url(re.compile(r"[?&]aba=todas"))  # a aba fica
    expect(page.locator("#busca-escolhida")).to_have_value(segunda)
    expect(titulos).to_have_count(0)

    page.reload()  # a URL reabre a mesma busca
    expect(page.locator("#busca-escolhida")).to_have_value(segunda)
    expect(page.locator("#lista-vagas .linha-titulo", has_text=PRESENCIAL)).to_have_count(0)
