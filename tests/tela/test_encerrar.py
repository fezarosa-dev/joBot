"""Encerrar pelo painel no navegador (T333; desenho 6.4): Configurações › Geral, a paleta e o
alerta."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.tela

PERGUNTA = "Encerrar o joBot?"


@pytest.fixture
def servidor(app_painel: FastAPI) -> SimpleNamespace:
    falso = SimpleNamespace(should_exit=False)
    app_painel.state.servidor = falso
    return falso


def test_geral_pergunta_e_encerra(page: Page, painel: str, servidor: SimpleNamespace) -> None:
    page.goto(f"{painel}/configuracoes/geral")
    encerrar = page.get_by_role("button", name="Encerrar o joBot", exact=True)
    encerrar.click()
    alerta = page.get_by_role("alertdialog", name=PERGUNTA)
    expect(alerta).to_be_visible()
    expect(alerta).to_be_focused()  # Return logo depois de abrir não aperta nenhum botão
    expect(alerta).to_contain_text("As buscas param até você abrir o joBot de novo.")
    alerta.get_by_role("button", name="Cancelar").click()
    expect(alerta).to_be_hidden()
    expect(encerrar).to_be_focused()
    assert servidor.should_exit is False

    encerrar.click()
    page.get_by_role("alertdialog", name=PERGUNTA).get_by_role(
        "button", name="Encerrar", exact=True
    ).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("joBot encerrado")
    expect(page.get_by_text("O joBot foi encerrado. Pode fechar esta janela.")).to_be_visible()
    assert servidor.should_exit is True


def test_paleta_abre_o_alerta(page: Page, painel: str, servidor: SimpleNamespace) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    abridor = page.get_by_role("banner").get_by_role("button", name="Comandos", exact=True)
    abridor.click()
    page.get_by_role("combobox", name="Buscar comando", exact=True).fill("Encerrar")
    page.keyboard.press("Enter")
    alerta = page.get_by_role("alertdialog", name=PERGUNTA)
    expect(alerta).to_be_visible()
    expect(page.locator("#paleta")).to_be_hidden()
    expect(alerta).to_be_focused()  # a paleta, ao fechar, não puxa o foco para trás do véu
    page.keyboard.press("Escape")
    expect(alerta).to_be_hidden()
    expect(abridor).to_be_focused()  # volta a quem abriu a paleta
    expect(page).to_have_url(f"{painel}/vagas?aba=todas")
    assert servidor.should_exit is False


def test_confirmacao_em_pagina_encerra(page: Page, painel: str, servidor: SimpleNamespace) -> None:
    page.goto(f"{painel}/sair/confirmar?voltar=/configuracoes/geral")
    expect(page.get_by_role("heading", level=1)).to_have_text(PERGUNTA)
    page.get_by_role("main").get_by_role("button", name="Encerrar", exact=True).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("joBot encerrado")
    assert servidor.should_exit is True


def test_despedida_sem_erro_na_pagina(page: Page, painel: str, servidor: SimpleNamespace) -> None:
    erros: list[str] = []
    page.on("pageerror", lambda erro: erros.append(str(erro)))
    page.goto(f"{painel}/configuracoes/geral")
    page.get_by_role("button", name="Encerrar o joBot", exact=True).click()
    page.get_by_role("alertdialog", name=PERGUNTA).get_by_role(
        "button", name="Encerrar", exact=True
    ).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("joBot encerrado")
    assert erros == []
