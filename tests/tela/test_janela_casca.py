"""O painel dentro da casca (T334; desenho 5.3): os círculos da janela, o arraste e o Mac."""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from playwright.sync_api import Locator, Page, expect

from jobot.painel.seguranca import renderizar

pytestmark = pytest.mark.tela

CASCA = "/_casca"
NAVEGADOR = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko)"
FILEIRA = "[data-janela-botoes]"
# a ponte falsa: mesma forma do `withGlobalTauri` (window.__TAURI__.window.getCurrentWindow())
PONTE = """
window.__chamadas = [];
window.__maximizada = false;
window.__TAURI__ = { window: { getCurrentWindow: () => ({
  close: async () => { window.__chamadas.push('close'); },
  minimize: async () => { window.__chamadas.push('minimize'); },
  toggleMaximize: async () => {
    window.__chamadas.push('toggleMaximize');
    window.__maximizada = !window.__maximizada;
  },
  startDragging: async () => { window.__chamadas.push('startDragging'); },
  isMaximized: async () => window.__maximizada,
}) } };
"""
ERROS = """
window.__erros = [];
window.addEventListener('error', (e) => window.__erros.push(String(e.message)));
window.addEventListener('unhandledrejection', (e) => window.__erros.push(String(e.reason)));
"""

# transição CSS anda no relógio do navegador: termina todas antes de medir
TERMINAR = "() => document.getAnimations().forEach(a => a.finish())"


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    @app_painel.get(CASCA)
    async def casca(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    return app_painel


def _abrir(page: Page, painel: str, so: str | None, *, ponte: bool = True) -> None:
    if so is not None:
        page.set_extra_http_headers({"user-agent": f"{NAVEGADOR} joBot-casca/0.4.0 ({so})"})
    page.add_init_script(ERROS)
    if ponte:
        page.add_init_script(PONTE)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{painel}{CASCA}")
    page.wait_for_load_state("load")


def _chamadas(page: Page) -> list[str]:
    chamadas: list[str] = page.evaluate("() => window.__chamadas")
    return chamadas


def _botao(page: Page, nome: str) -> Locator:
    return page.locator(FILEIRA).get_by_role("button", name=nome, exact=True)


@pytest.mark.parametrize("so", ["linux", "windows"])
def test_fileira_com_tres_botoes(page: Page, painel: str, so: str) -> None:
    _abrir(page, painel, so)
    expect(page.locator("html")).to_have_attribute("data-casca", so)
    botoes = page.locator(FILEIRA).get_by_role("button")
    expect(botoes).to_have_count(3)
    for nome in ("Fechar", "Minimizar", "Maximizar"):
        expect(_botao(page, nome)).to_be_visible()


def test_mac_sem_fileira_e_com_o_espaco_reservado(page: Page, painel: str) -> None:
    _abrir(page, painel, "macos")
    expect(page.locator("html")).to_have_attribute("data-casca", "macos")
    expect(page.locator(FILEIRA)).to_have_count(0)
    # os botões do sistema ficam por cima do canto: a lateral desce e a barra recua
    assert page.locator("#lateral").evaluate("e => getComputedStyle(e).paddingBlockStart") == "36px"
    page.get_by_role("button", name="Recolher barra lateral").click()
    recuo = page.locator(".topo").evaluate("e => getComputedStyle(e).paddingInlineStart")
    assert float(recuo.removesuffix("px")) >= 80


def test_sem_a_marca_nada_muda(page: Page, painel: str) -> None:
    _abrir(page, painel, None)
    assert page.locator("html").get_attribute("data-casca") is None
    expect(page.locator(FILEIRA)).to_have_count(0)
    assert page.locator("#lateral").evaluate("e => getComputedStyle(e).paddingBlockStart") == "0px"


def test_cada_botao_chama_a_ponte(page: Page, painel: str) -> None:
    _abrir(page, painel, "linux")
    _botao(page, "Minimizar").click()
    _botao(page, "Maximizar").click()
    # maximizada, o botão passa a se chamar Restaurar
    expect(_botao(page, "Restaurar")).to_be_visible()
    _botao(page, "Restaurar").click()
    expect(_botao(page, "Maximizar")).to_be_visible()
    _botao(page, "Fechar").click()
    assert [c for c in _chamadas(page) if c != "startDragging"] == [
        "minimize",
        "toggleMaximize",
        "toggleMaximize",
        "close",
    ]


def test_teclado_alcanca_os_botoes(page: Page, painel: str) -> None:
    _abrir(page, painel, "windows")
    _botao(page, "Fechar").focus()
    page.keyboard.press("Tab")
    expect(_botao(page, "Minimizar")).to_be_focused()
    page.keyboard.press("Enter")
    assert _chamadas(page) == ["minimize"]


def test_barra_arrasta_e_duplo_clique_maximiza(page: Page, painel: str) -> None:
    _abrir(page, painel, "linux")
    caixa = page.locator(".topo").bounding_box()
    assert caixa
    # meio da barra, longe dos controles: o espaço entre o título e a busca
    x, y = caixa["x"] + caixa["width"] * 0.45, caixa["y"] + caixa["height"] / 2
    controle = f"() => document.elementFromPoint({x}, {y}).closest('button, a, input')"
    assert page.evaluate(controle) is None
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.up()
    assert _chamadas(page) == ["startDragging"]
    page.mouse.dblclick(x, y)
    assert "toggleMaximize" in _chamadas(page)


def test_topo_da_lateral_arrasta(page: Page, painel: str) -> None:
    _abrir(page, painel, "linux")
    caixa = page.locator("#lateral").bounding_box()
    assert caixa
    page.mouse.move(caixa["x"] + caixa["width"] - 20, caixa["y"] + 10)
    page.mouse.down()
    page.mouse.up()
    assert _chamadas(page) == ["startDragging"]


def test_controle_da_barra_nao_arrasta(page: Page, painel: str) -> None:
    _abrir(page, painel, "linux")
    page.get_by_role("button", name="Recolher barra lateral").click()
    page.get_by_role("button", name="Comandos").dispatch_event("mousedown", {"button": 0})
    _botao(page, "Fechar").dispatch_event("mousedown", {"button": 0})
    page.locator(".topo").dispatch_event("mousedown", {"button": 2})
    assert _chamadas(page) == []


def test_sem_ponte_os_botoes_nao_quebram(page: Page, painel: str) -> None:
    _abrir(page, painel, "linux", ponte=False)
    _botao(page, "Fechar").click()
    page.locator(".topo").dispatch_event("mousedown", {"button": 0})
    assert page.evaluate("() => window.__erros") == []


def test_janela_inativa_deixa_os_tres_cinza(page: Page, painel: str) -> None:
    _abrir(page, painel, "linux")
    fundos = "es => es.map(e => getComputedStyle(e).backgroundColor)"
    botoes = page.locator(f"{FILEIRA} button")
    ativos = botoes.evaluate_all(fundos)
    assert len(set(ativos)) == 3
    page.evaluate("() => window.dispatchEvent(new Event('blur'))")
    expect(page.locator("html")).to_have_attribute("data-janela", "inativa")
    page.evaluate(TERMINAR)
    inativos = botoes.evaluate_all(fundos)
    assert len(set(inativos)) == 1
    assert inativos[0] not in ativos


def test_simbolo_aparece_no_hover_da_fileira(page: Page, painel: str) -> None:
    _abrir(page, painel, "linux")
    simbolos = page.locator(f"{FILEIRA} button span")
    opacidade = "es => es.map(e => getComputedStyle(e).opacity)"
    page.emulate_media(reduced_motion="reduce")
    assert set(simbolos.evaluate_all(opacidade)) == {"0"}
    _botao(page, "Minimizar").hover()
    page.evaluate(TERMINAR)
    assert set(simbolos.evaluate_all(opacidade)) == {"1"}


def test_cores_forcadas(page: Page, painel: str) -> None:
    _abrir(page, painel, "linux")
    page.emulate_media(forced_colors="active")
    page.evaluate(TERMINAR)
    botoes = page.locator(f"{FILEIRA} button")
    bordas = botoes.evaluate_all("es => es.map(e => getComputedStyle(e).borderTopStyle)")
    assert set(bordas) == {"solid"}
    simbolos = page.locator(f"{FILEIRA} button span")
    assert set(simbolos.evaluate_all("es => es.map(e => getComputedStyle(e).opacity)")) == {"1"}
