"""Tela de buscas no navegador: criar, editar, desligar, apagar e o seletor da lista (T52)."""

import re

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.relogio import RelogioFalso

pytestmark = pytest.mark.tela

PRESENCIAL = "Analista de Sistemas"  # a única vaga semeada que a busca "Só remoto" esconde


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()
    return app_painel


def _cartoes(page: Page) -> Locator:
    return page.locator("#lista-buscas li.cartao")


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
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on(
        "console",
        # o 422 do primeiro envio é esperado e o navegador o registra no console
        lambda m: erros.append(m.text) if m.type == "error" and "422" not in m.text else None,
    )
    page.on("pageerror", lambda e: erros.append(str(e)))
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


def test_desligar_ligar_e_apagar(page: Page, painel: str) -> None:
    _criar(page, painel, "Outra busca")
    cartao = _cartao(page, "Outra busca")
    expect(cartao.get_by_text("Desligada", exact=True)).to_have_count(0)

    cartao.get_by_role("button", name="Desligar").click()
    expect(_cartao(page, "Outra busca").get_by_text("Desligada", exact=True)).to_be_visible()
    _cartao(page, "Outra busca").get_by_role("button", name="Ligar").click()
    expect(_cartao(page, "Outra busca").get_by_text("Desligada", exact=True)).to_have_count(0)

    cartao = _cartao(page, "Outra busca")
    expect(cartao.get_by_role("button", name="Apagar mesmo")).to_be_hidden()
    cartao.get_by_text("Apagar", exact=True).click()  # o resumo abre a confirmação, sem JS
    cartao.get_by_role("button", name="Apagar mesmo").click()
    expect(_cartoes(page)).to_have_count(1)
    expect(_cartao(page, "Outra busca")).to_have_count(0)


def test_seletor_da_lista_muda_a_url_e_a_lista(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    expect(page.locator("nav.seletor-busca")).to_have_count(0)  # uma busca só: sem seletor

    _criar(page, painel, "Só remoto", remoto=True)
    page.goto(f"{painel}/vagas?aba=todas")
    links = page.locator("nav.seletor-busca a")
    expect(links).to_have_count(2)
    expect(links.nth(0)).to_have_attribute("aria-current", "true")
    titulos = page.locator("main h3.cartao-titulo", has_text=PRESENCIAL)
    expect(titulos).to_have_count(1)

    links.nth(1).click()
    expect(page).to_have_url(re.compile(r"[?&]busca=\d+"))
    expect(links.nth(1)).to_have_attribute("aria-current", "true")
    expect(links.nth(0)).not_to_have_attribute("aria-current", "true")
    expect(titulos).to_have_count(0)

    page.reload()  # a URL reabre a mesma busca
    expect(page.locator("nav.seletor-busca a").nth(1)).to_have_attribute("aria-current", "true")
    expect(page.locator("main h3.cartao-titulo", has_text=PRESENCIAL)).to_have_count(0)
