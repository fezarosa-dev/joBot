"""Encerrar pelo painel no navegador (T333; desenho 6.4): Configurações › Geral, a paleta, o alerta
e a janela da casca que fecha junto."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.tela

PERGUNTA = "Encerrar o joBot?"
# a ponte do Tauri (withGlobalTauri) de mentira: cada documento novo a recebe antes do app.js
TAURI_FALSO = """
window.__fechou = 0;
window.__TAURI__ = {window: {getCurrentWindow: () => ({
  close: () => { window.__fechou += 1; return Promise.resolve(); },
})}};
"""


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


def test_na_casca_a_janela_fecha_junto(page: Page, painel: str, servidor: SimpleNamespace) -> None:
    page.add_init_script(TAURI_FALSO)
    page.goto(f"{painel}/configuracoes/geral")
    page.get_by_role("button", name="Encerrar o joBot", exact=True).click()
    assert page.evaluate("window.__fechou") == 0  # abrir o alerta não fecha nada
    page.get_by_role("alertdialog", name=PERGUNTA).get_by_role(
        "button", name="Encerrar", exact=True
    ).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("joBot encerrado")
    page.wait_for_function("window.__fechou === 1")
    assert servidor.should_exit is True


def test_fora_da_casca_nada_quebra(page: Page, painel: str, servidor: SimpleNamespace) -> None:
    erros: list[str] = []
    page.on("pageerror", lambda erro: erros.append(str(erro)))
    page.goto(f"{painel}/configuracoes/geral")
    page.get_by_role("button", name="Encerrar o joBot", exact=True).click()
    page.get_by_role("alertdialog", name=PERGUNTA).get_by_role(
        "button", name="Encerrar", exact=True
    ).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("joBot encerrado")
    assert erros == []
