"""Link "Apoie o projeto" e aviso de versão na casca, no navegador (plano T87)."""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from playwright.sync_api import Page, expect

from jobot.painel.seguranca import renderizar
from tela.test_casca_menu import CONTRASTE

pytestmark = pytest.mark.tela

CASCA = "/_casca"
MINIMO = 4.5


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    @app_painel.get(CASCA)
    async def casca(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    return app_painel


def test_link_apoie_visivel_e_alcancavel_pelo_teclado(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    link = page.locator("footer").get_by_role("link", name="Apoie o projeto")
    expect(link).to_be_visible()
    link.scroll_into_view_if_needed()
    for _ in range(40):  # Tab até chegar: pular, marca, menu, preferências e botões vêm antes
        page.keyboard.press("Tab")
        if link.evaluate("el => el === document.activeElement"):
            break
    expect(link).to_be_focused()
    estilo = link.evaluate(
        """el => {
          const s = getComputedStyle(el);
          return [s.outlineStyle, parseFloat(s.outlineWidth)];
        }"""
    )
    assert estilo[0] != "none"
    assert estilo[1] >= 2


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_contraste_do_link_apoie_e_do_aviso(page: Page, painel: str, esquema: str) -> None:
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    page.goto(painel + CASCA)
    # o aviso nasce vazio (desligado): põe o fragmento da T85 depois que o htmx já respondeu
    page.wait_for_load_state("networkidle")
    page.evaluate(
        "document.getElementById('aviso-versao').innerHTML ="
        " '<p class=\"aviso-versao\">Há uma versão nova do joBot: 9.9.9.</p>'"
    )
    link = page.locator("footer").get_by_role("link", name="Apoie o projeto")
    aviso = page.locator("#aviso-versao .aviso-versao")
    expect(aviso).to_be_visible()
    assert link.evaluate(CONTRASTE) >= MINIMO
    assert aviso.evaluate(CONTRASTE) >= MINIMO
