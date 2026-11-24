"""Aba IA no navegador (plano T415; desenho 5.6, 6 e 10.3 da fase 4; D202).

Atalho pelo teclado, confirmação do custo com e sem JavaScript, a tabela por tarefa com erro
marcado e cores forçadas. O cofre é o `CofreFalso` e o modelo local vem de `app.state`. Nenhum
teste espera tempo real: `expect_navigation` e `expect`.
"""

import re
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Browser, Page, expect

from apoio.cofre_falso import CofreFalso
from apoio.console import anotar_erros
from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import ler_config
from jobot.banco.conexao import abrir
from jobot.sistema.cofre import Cofre

pytestmark = pytest.mark.tela

LOCAL = "Qwen3.5-4B-Q4_K_M"
CHAVE = "sk-ant-AbCd1234EfGh5678IjKl9012"
IA = "/configuracoes/ia"


@pytest.fixture
def cofre(tmp_path: Path) -> Cofre:
    return Cofre(tmp_path, CofreFalso())


@pytest.fixture
def app_painel(app_painel: FastAPI, cofre: Cofre) -> FastAPI:
    app_painel.state.cofre = cofre
    app_painel.state.relogio = RelogioFalso()
    app_painel.state.modelo_local = lambda: LOCAL
    return app_painel


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> Iterator[None]:
    # violação do CSP aparece como erro; o 422 do modelo inválido é a resposta esperada da página
    erros = anotar_erros(page, ignorar="422")
    yield
    assert erros == []


def _tarefas(tmp_path: Path) -> object:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        return ler_config(con, "ia_tarefas")


def test_tudo_offline_pelo_teclado(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}{IA}")
    expect(
        page.locator("nav.config-grupos").get_by_role("link", name="IA", exact=True)
    ).to_have_attribute("aria-current", "page")
    expect(page.get_by_text("Agora: Desligada.")).to_be_visible()
    desligar = page.get_by_role("button", name="Desligar a IA", exact=True)
    desligar.focus()
    page.keyboard.press("Tab")  # do "Desligar a IA", o Tab chega no "Tudo offline"
    offline = page.get_by_role("button", name="Tudo offline", exact=True)
    expect(offline).to_be_focused()
    expect(offline).to_have_accessible_description(re.compile("modelo local"))
    with page.expect_navigation():
        page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"/configuracoes/ia(\?salvo=1)?$"))
    expect(page.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    expect(page.get_by_text("Agora: Tudo offline.")).to_be_visible()
    assert _tarefas(tmp_path) == {"encaixe": {"ligada": True, "backend": "local", "modelo": LOCAL}}


def test_custo_pede_confirmacao_e_voltar_nao_liga(
    page: Page, painel: str, tmp_path: Path, cofre: Cofre
) -> None:
    cofre.gravar("ia_anthropic", CHAVE)
    page.goto(f"{painel}{IA}")
    expect(page.get_by_text("API da Anthropic, cobrada por uso.", exact=False)).to_be_visible()
    with page.expect_navigation():
        page.get_by_role("button", name="Tudo Claude", exact=True).click()
    expect(page.get_by_role("heading", name="Ligar o encaixe num serviço cobrado?")).to_be_visible()
    expect(page.get_by_role("alert").filter(has_text="até 200 pedidos por dia")).to_be_visible()
    ligar = page.get_by_role("button", name="Ligar mesmo assim", exact=True)
    expect(ligar).to_be_focused()  # o `autofocus` leva direto à decisão
    with page.expect_navigation():
        page.get_by_role("link", name="Voltar sem ligar", exact=True).click()
    expect(page).to_have_url(re.compile(r"/configuracoes/ia$"))
    assert _tarefas(tmp_path) == {"encaixe": {"ligada": False, "backend": "", "modelo": ""}}


def test_custo_confirmado_sem_javascript(
    browser: Browser, painel: str, tmp_path: Path, cofre: Cofre
) -> None:
    cofre.gravar("ia_anthropic", CHAVE)
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        pagina = contexto.new_page()
        pagina.goto(f"{painel}{IA}")
        pagina.get_by_role("button", name="Tudo Claude", exact=True).click()
        expect(pagina.get_by_role("button", name="Ligar mesmo assim", exact=True)).to_be_visible()
        assert _tarefas(tmp_path) == {"encaixe": {"ligada": False, "backend": "", "modelo": ""}}
        pagina.get_by_role("button", name="Ligar mesmo assim", exact=True).click()
        expect(pagina).to_have_url(re.compile(r"/configuracoes/ia\?salvo=1$"))
        expect(pagina.get_by_text("Agora: Tudo Claude.")).to_be_visible()
    finally:
        contexto.close()
    modelo = "claude-haiku-5-5"
    assert _tarefas(tmp_path) == {
        "encaixe": {"ligada": True, "backend": "anthropic", "modelo": modelo}
    }


def test_tabela_com_modelo_invalido_marca_o_campo(
    page: Page, painel: str, tmp_path: Path, cofre: Cofre
) -> None:
    cofre.gravar("ia_openai", CHAVE)
    page.goto(f"{painel}{IA}")
    tarefa = page.get_by_role("group", name="Encaixe: o que cada vaga pede")
    tarefa.get_by_role("checkbox", name="Ligada", exact=True).check()
    onde = tarefa.get_by_role("combobox", name="Onde roda")
    onde.select_option("openai")
    expect(onde.locator('option[value="openai"]')).to_have_text("OpenAI (cobrada por uso)")
    # com o `datalist`, o campo de texto tem o papel de combobox
    modelo = tarefa.get_by_role("combobox", name="Modelo", exact=True)
    expect(modelo).to_have_accessible_description(re.compile("claude-haiku-5-5"))
    modelo.fill("gpt x")
    with page.expect_navigation():
        page.get_by_role("button", name="Salvar", exact=True).click()
    expect(page.get_by_role("alert").filter(has_text="sem espaço")).to_be_visible()
    modelo = page.get_by_role("combobox", name="Modelo", exact=True)
    expect(modelo).to_have_attribute("aria-invalid", "true")
    expect(modelo).to_have_value("gpt x")
    assert _tarefas(tmp_path) == {"encaixe": {"ligada": False, "backend": "", "modelo": ""}}


def test_campo_e_select_com_foco_visivel_em_cores_forcadas(page: Page, painel: str) -> None:
    page.emulate_media(forced_colors="active")
    page.goto(f"{painel}{IA}")
    modelo = page.get_by_role("combobox", name="Modelo", exact=True)
    modelo.focus()
    expect(modelo).to_be_focused()
    page.keyboard.press("Shift+Tab")  # pelo teclado: o select ganha o anel de foco
    onde = page.get_by_role("combobox", name="Onde roda")
    expect(onde).to_be_focused()
    for campo in (modelo, onde):
        borda = campo.evaluate("e => getComputedStyle(e).borderTopWidth")
        assert float(borda.removesuffix("px")) > 0
    contorno = onde.evaluate(
        "e => [getComputedStyle(e).outlineStyle, getComputedStyle(e).outlineWidth]"
    )
    assert contorno[0] != "none"
    assert float(contorno[1].removesuffix("px")) >= 2
