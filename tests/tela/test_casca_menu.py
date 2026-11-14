"""Menu principal da casca no navegador: teclado, foco visível e contraste (decisão 22; T86)."""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from playwright.sync_api import Locator, Page, expect

from jobot.painel.seguranca import renderizar

pytestmark = pytest.mark.tela

CASCA = "/_casca"
MINIMO = 4.5
# cor de cada item sobre o que aparece atrás dele: sobe pelos fundos até um opaco e compõe as
# camadas (a barra do topo é translúcida); as cores chegam como rgb() ou color(srgb ...)
CONTRASTE = """el => {
  const canais = s => {
    const n = s.match(/-?[\\d.]+/g).map(Number);
    const k = s.startsWith('color(') ? 255 : 1;
    const a = s.includes('/') || n.length === 4 ? n[n.length - 1] : 1;
    return [n[0] * k, n[1] * k, n[2] * k, a];
  };
  const camadas = [];
  for (let e = el; e; e = e.parentElement) {
    const c = canais(getComputedStyle(e).backgroundColor);
    if (c[3] > 0) camadas.push(c);
    if (c[3] === 1) break;
  }
  let fundo = camadas.pop() ?? [255, 255, 255, 1];
  while (camadas.length) {
    const c = camadas.pop();
    fundo = [0, 1, 2].map(i => c[i] * c[3] + fundo[i] * (1 - c[3])).concat([1]);
  }
  const lum = ([r, g, b]) => {
    const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const texto = lum(canais(getComputedStyle(el).color));
  const [claro, escuro] = [texto, lum(fundo)].sort((a, b) => b - a);
  return (claro + 0.05) / (escuro + 0.05);
}"""


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    @app_painel.get(CASCA)
    async def casca(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    return app_painel


def _itens(page: Page) -> Locator:
    return page.get_by_role("navigation", name="Principal").get_by_role("link")


def test_tab_chega_no_menu_depois_do_pular(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    page.keyboard.press("Tab")
    expect(page.get_by_role("link", name="Pular para o conteúdo")).to_be_focused()
    itens = _itens(page)
    expect(itens).to_have_count(6)
    # a ordem do foco segue a do menu: a marca vem antes, depois os seis itens
    page.keyboard.press("Tab")
    expect(page.locator("a.marca")).to_be_focused()
    for i in range(6):
        page.keyboard.press("Tab")
        expect(itens.nth(i)).to_be_focused()


def test_foco_do_menu_e_visivel(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    item = _itens(page).first
    for _ in range(3):  # pular, marca, primeiro item
        page.keyboard.press("Tab")
    expect(item).to_be_focused()
    estilo = item.evaluate(
        """el => {
          const s = getComputedStyle(el);
          return [s.outlineStyle, parseFloat(s.outlineWidth)];
        }"""
    )
    assert estilo[0] != "none"
    assert estilo[1] >= 2


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_contraste_dos_itens_do_menu(page: Page, painel: str, esquema: str) -> None:
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    page.goto(painel + "/vagas")
    itens = _itens(page)
    assert itens.count() == 6
    razoes = [itens.nth(i).evaluate(CONTRASTE) for i in range(6)]
    # o item da área aberta tem outro fundo: entra na conta junto com os demais
    menu = page.get_by_role("navigation", name="Principal")
    expect(menu.locator("[aria-current=page]")).to_have_count(1)
    assert [r for r in razoes if r < MINIMO] == [], f"contraste no tema {esquema}: {razoes}"
