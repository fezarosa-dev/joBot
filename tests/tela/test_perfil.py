"""Aba Perfil no navegador (plano T413; desenho 8 da fase 4; D200).

Salvar pelo teclado, "Apagar perfil" pelo alerta e sem JavaScript, foco e cores forçadas. Nenhum
teste espera tempo real: `expect_navigation` e `expect`.
"""

import re
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from apoio.console import anotar_erros
from apoio.semear import AGORA
from jobot.banco.conexao import abrir
from jobot.banco.perfil import gravar_habilidades, habilidades

pytestmark = pytest.mark.tela


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> Iterator[None]:
    # violação do CSP aparece como erro; o 422 do teto é a resposta esperada da página
    erros = anotar_erros(page, ignorar="422")
    yield
    assert erros == []


def _gravar(tmp_path: Path, lista: list[str]) -> None:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravar_habilidades(con, lista, AGORA)


def _lidas(tmp_path: Path) -> tuple[int, list[str]]:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        return con.execute("SELECT count(*) FROM perfil").fetchone()[0], habilidades(con)


def test_salvar_pelo_teclado_grava_sem_repetidos(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}/configuracoes/perfil")
    expect(page.locator("nav.config-grupos").get_by_role("link", name="Perfil")).to_have_attribute(
        "aria-current", "page"
    )
    campo = page.get_by_role("textbox", name="Suas habilidades")
    expect(campo).to_have_accessible_description(re.compile("Uma por linha"))
    campo.fill("Python\n python \nGo,")
    page.keyboard.press("Tab")  # do campo, o Tab chega no Salvar
    salvar = page.get_by_role("button", name="Salvar", exact=True)
    expect(salvar).to_be_focused()
    with page.expect_navigation():
        page.keyboard.press("Enter")
    # o app.js tira o ?salvo= da URL depois de mostrar a mensagem
    expect(page).to_have_url(re.compile(r"/configuracoes/perfil(\?salvo=1)?$"))
    expect(page.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    expect(page.get_by_role("textbox", name="Suas habilidades")).to_have_value("Python\nGo")
    assert _lidas(tmp_path) == (1, ["Python", "Go"])


def test_apagar_pelo_alerta_e_cancelar_nao_apaga(page: Page, painel: str, tmp_path: Path) -> None:
    _gravar(tmp_path, ["Python"])
    page.goto(f"{painel}/configuracoes/perfil")
    abrir_alerta = page.get_by_role("button", name="Apagar perfil", exact=True)
    abrir_alerta.click()
    alerta = page.get_by_role("alertdialog", name="Apagar o perfil?")
    expect(alerta).to_be_visible()
    expect(alerta).to_be_focused()  # o foco fica no próprio alerta, nunca num botão (E13)
    alerta.get_by_role("button", name="Cancelar").click()
    expect(alerta).to_be_hidden()
    expect(abrir_alerta).to_be_focused()
    assert _lidas(tmp_path) == (1, ["Python"])

    abrir_alerta.click()
    with page.expect_navigation():
        alerta.get_by_role("button", name="Apagar", exact=True).click()
    expect(page).to_have_url(re.compile(r"/configuracoes/perfil\?apagado=1$"))
    expect(page.get_by_role("status").filter(has_text="Perfil apagado.")).to_be_visible()
    expect(page.get_by_role("textbox", name="Suas habilidades")).to_have_value("")
    expect(page.get_by_role("button", name="Apagar perfil", exact=True)).to_have_count(0)
    assert _lidas(tmp_path) == (0, [])


def test_apagar_sem_javascript_pede_confirmacao(
    browser: Browser, painel: str, tmp_path: Path
) -> None:
    _gravar(tmp_path, ["Python"])
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        pagina = contexto.new_page()
        pagina.goto(f"{painel}/configuracoes/perfil")
        pagina.get_by_role("button", name="Apagar perfil", exact=True).click()
        expect(pagina).to_have_url(re.compile(r"/configuracoes/perfil/apagar/confirmar\??$"))
        expect(pagina.get_by_role("heading", level=1)).to_have_text("Apagar o perfil?")
        pagina.get_by_role("link", name="Cancelar", exact=True).click()
        expect(pagina).to_have_url(re.compile(r"/configuracoes/perfil$"))
        assert _lidas(tmp_path) == (1, ["Python"])  # abrir e cancelar não apagou

        pagina.get_by_role("button", name="Apagar perfil", exact=True).click()
        pagina.get_by_role("button", name="Apagar", exact=True).click()
        expect(pagina).to_have_url(re.compile(r"/configuracoes/perfil\?apagado=1$"))
        assert _lidas(tmp_path) == (0, [])
    finally:
        contexto.close()


def test_campo_com_foco_visivel_em_cores_forcadas(page: Page, painel: str) -> None:
    page.emulate_media(forced_colors="active")
    page.goto(f"{painel}/configuracoes/perfil")
    campo = page.get_by_role("textbox", name="Suas habilidades")
    campo.focus()
    expect(campo).to_be_focused()
    borda = campo.evaluate("e => getComputedStyle(e).borderTopWidth")
    contorno = campo.evaluate(
        "e => [getComputedStyle(e).outlineStyle, getComputedStyle(e).outlineWidth]"
    )
    assert float(borda.removesuffix("px")) > 0
    assert contorno == ["solid", "2px"]  # o contorno transparente vira linha visível aqui


def test_erro_de_teto_marca_o_campo(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}/configuracoes/perfil")
    campo = page.get_by_role("textbox", name="Suas habilidades")
    campo.fill("x" * 101)
    with page.expect_navigation():
        page.get_by_role("button", name="Salvar", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Até 200 habilidades")
    expect(campo).to_have_attribute("aria-invalid", "true")
    expect(campo).to_have_value("x" * 101)
    assert _lidas(tmp_path) == (0, [])
