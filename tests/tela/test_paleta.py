"""Paleta de comandos no navegador (T265; desenho 5.4 e 5.5): ⌘K e Ctrl+K, Esc, Return, o filtro
enquanto digita e as duas formas do atalho escrito."""

import re

import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.tela

PALETA = "#paleta"
LISTA = "/vagas?aba=todas"
# o Chromium de teste é Linux: para o ⌘K valer, a página se diz Mac antes de o app.js rodar
FINGE_MAC = (
    "Object.defineProperty(navigator, 'userAgentData', {get: () => undefined});"
    "Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});"
)


def _campo(page: Page) -> Locator:
    return page.get_by_role("combobox", name="Buscar comando", exact=True)


def _opcao(page: Page, nome: str) -> Locator:
    return page.locator(PALETA).get_by_role("option", name=nome, exact=True)


def _abrir(page: Page) -> None:
    page.keyboard.press("Control+k")
    expect(page.locator(PALETA)).to_be_visible()
    expect(_campo(page)).to_be_focused()


@pytest.mark.parametrize(("tecla", "sistema"), [("Meta+k", "mac"), ("Control+k", "outro")])
def test_cmd_k_e_ctrl_k_abrem(page: Page, painel: str, tecla: str, sistema: str) -> None:
    if sistema == "mac":
        page.add_init_script(FINGE_MAC)
    page.goto(f"{painel}{LISTA}")
    expect(page.locator("html")).to_have_attribute("data-sistema", sistema)
    paleta = page.locator(PALETA)
    expect(paleta).to_be_hidden()
    page.keyboard.press(tecla)
    expect(paleta).to_be_visible()
    expect(_campo(page)).to_be_focused()
    # a mesma tecla fecha; o botão da barra abre de novo
    page.keyboard.press(tecla)
    expect(paleta).to_be_hidden()
    page.get_by_role("banner").get_by_role("button", name="Comandos", exact=True).click()
    expect(paleta).to_be_visible()
    expect(_campo(page)).to_be_focused()


def test_esc_fecha(page: Page, painel: str) -> None:
    page.goto(f"{painel}{LISTA}")
    paleta = page.locator(PALETA)
    _abrir(page)
    page.keyboard.press("Escape")
    expect(paleta).to_be_hidden()
    _abrir(page)
    page.keyboard.press("Control+.")  # ⌘. fecha como o Esc (Ctrl+. fora do Mac)
    expect(paleta).to_be_hidden()


def test_return_executa(page: Page, painel: str) -> None:
    page.goto(f"{painel}{LISTA}")
    _abrir(page)
    _campo(page).fill("Salvas")
    page.keyboard.press("Enter")  # um link que já existe: a lateral
    expect(page).to_have_url(re.compile(r"/vagas\?aba=salvas"))
    expect(page.locator(PALETA)).to_be_hidden()
    expect(page.locator("html")).to_have_attribute("data-sistema", re.compile(".+"))  # app.js rodou
    # e um formulário que já existe, com o csrf_token dele: o tema escuro
    _abrir(page)
    _campo(page).fill("Escuro")
    page.keyboard.press("Enter")
    expect(page.locator("html")).to_have_attribute("data-tema", "escuro")


def test_filtra_enquanto_digita(page: Page, painel: str) -> None:
    page.goto(f"{painel}{LISTA}")
    _abrir(page)
    paleta = page.locator(PALETA)
    todas = paleta.get_by_role("option")
    estado = paleta.locator("[data-paleta-estado]")
    expect(todas.first).to_have_attribute("aria-selected", "true")
    expect(estado).to_have_text(re.compile(r"^\d\d+ comandos$"))
    _campo(page).fill("salv")  # sem diferença de caixa
    expect(todas).to_have_count(1)
    expect(_opcao(page, "Salvas")).to_have_attribute("aria-selected", "true")
    expect(_campo(page)).to_have_attribute(
        "aria-activedescendant", _opcao(page, "Salvas").get_attribute("id") or "?"
    )
    expect(estado).to_have_text("1 comando")
    _campo(page).fill("configuracoes")  # sem acento também acha
    expect(_opcao(page, "Configurações")).to_have_attribute("aria-selected", "true")
    page.keyboard.press("ArrowDown")
    expect(_opcao(page, "Configurações: Geral")).to_have_attribute("aria-selected", "true")
    expect(_opcao(page, "Configurações")).to_have_attribute("aria-selected", "false")
    _campo(page).fill("zzz")
    expect(todas).to_have_count(0)
    expect(estado).to_have_text("Nenhum comando")
    expect(paleta.locator(".paleta-vazio")).to_be_visible()
    _campo(page).fill("")
    expect(paleta.locator(".paleta-vazio")).to_be_hidden()
    expect(estado).to_have_text(re.compile(r"^\d\d+ comandos$"))


def test_so_uma_forma_do_atalho_visivel(page: Page, painel: str) -> None:
    page.goto(f"{painel}{LISTA}")
    page.get_by_role("banner").get_by_role("button", name="Comandos", exact=True).click()
    paleta = page.locator(PALETA)
    expect(paleta).to_be_visible()
    mac = paleta.locator('kbd[data-sistema="mac"]').first
    outro = paleta.locator('kbd[data-sistema="outro"]').first
    page.evaluate("document.documentElement.dataset.sistema = 'outro'")
    expect(mac).to_be_hidden()
    expect(outro).to_be_visible()
    page.evaluate("document.documentElement.dataset.sistema = 'mac'")
    expect(outro).to_be_hidden()
    expect(mac).to_be_visible()


def test_foco_volta_ao_abridor_ao_fechar(page: Page, painel: str) -> None:
    page.goto(f"{painel}{LISTA}")
    botao = page.get_by_role("banner").get_by_role("button", name="Comandos", exact=True)
    botao.click()
    expect(_campo(page)).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(PALETA)).to_be_hidden()
    expect(botao).to_be_focused()


def test_paleta_fechada_nao_rouba_o_foco_da_lista(page: Page, painel: str) -> None:
    """A opção marcada da paleta (aria-selected) não conta como a linha escolhida da lista. Sem
    nenhuma linha da lista marcada ao ocultar, o seletor antigo (qualquer listbox) achava a opção da
    paleta e o foco sumia no <dialog> fechado; agora cai numa linha da lista."""
    page.goto(f"{painel}{LISTA}")
    _abrir(page)
    page.keyboard.press("Escape")
    expect(page.locator(PALETA)).to_be_hidden()
    # a opção da paleta segue marcada (o caso que enganava o seletor)
    expect(page.locator('#paleta [role="option"][aria-selected="true"]')).to_have_count(1)
    nova = page.locator('#lista-vagas > [role="option"]').filter(
        has_text="Engenheira de Integração"
    )
    nova.focus()
    page.keyboard.press("Enter")
    lado = page.locator("#detalhe-vaga")
    expect(lado.get_by_role("heading", level=2, name="Engenheira de Integração")).to_be_visible()
    expect(page.locator(".htmx-settling")).to_have_count(0)
    # nenhuma linha da lista marcada: ocultar não pode escolher a vizinha por conta própria
    page.evaluate(
        "document.querySelectorAll('#lista-vagas > [role=option]')"
        ".forEach(o => o.setAttribute('aria-selected', 'false'))"
    )
    lado.get_by_role("button", name="Ocultar", exact=True).click()
    expect(page.locator("#faixa-desfazer")).to_contain_text("Vaga ocultada")
    expect(page.locator('#lista-vagas > [role="option"]:focus')).to_have_count(1)
