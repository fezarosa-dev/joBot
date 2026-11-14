"""Aviso de versão nova na casca, no navegador (plano T105; D64).

O aviso é o da rota real `/aviso-versao`: a config é gravada no banco semeado e o HTMX da casca
busca o fragmento no próprio painel (127.0.0.1), sem rede de fora.
"""

from contextlib import closing

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from playwright.sync_api import Page, expect

from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.painel.seguranca import renderizar
from tela.test_casca_menu import CONTRASTE

pytestmark = pytest.mark.tela

CASCA = "/_casca"
MINIMO = 4.5
REGIAO = "#aviso-versao"


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    @app_painel.get(CASCA)
    async def casca(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    return app_painel


@pytest.fixture
def aviso_ligado(app_painel: FastAPI) -> None:
    with closing(abrir(app_painel.state.banco)) as con:
        gravar_config(con, "aviso_versao_ligada", True)
        gravar_config(con, "versao_nova", "v99.0.0")


def _abrir_casca(page: Page, painel: str) -> None:
    # espera a resposta do fragmento: depois dela o HTMX já trocou (ou deixou vazio) o conteúdo
    with page.expect_response("**/aviso-versao") as resposta:
        page.goto(painel + CASCA)
    assert resposta.value.status == 200
    page.wait_for_load_state("networkidle")


def test_aviso_de_versao_aparece_na_casca_com_role_status(
    page: Page, painel: str, aviso_ligado: None
) -> None:
    page.set_viewport_size({"width": 390, "height": 700})  # celular: o caso mais apertado
    _abrir_casca(page, painel)
    regiao = page.get_by_role("status").filter(has=page.locator(".aviso-versao"))
    expect(regiao).to_have_count(1)
    expect(regiao).to_have_id("aviso-versao")
    aviso = regiao.locator(".aviso-versao")
    expect(aviso).to_be_visible()
    expect(aviso).to_contain_text("v99.0.0")
    # não corta o rodapé: o rodapé segue visível, abaixo do aviso, e nada estoura a largura
    rodape = page.locator("footer").get_by_role("link", name="Apoie o projeto")
    rodape.scroll_into_view_if_needed()
    expect(rodape).to_be_visible()
    caixas = page.evaluate(
        """() => {
          const r = s => document.querySelector(s).getBoundingClientRect();
          return {
            aviso: r('#aviso-versao .aviso-versao').toJSON(),
            rodape: r('footer').toJSON(),
            largura: document.documentElement.clientWidth,
            rolagem: document.documentElement.scrollWidth,
          };
        }"""
    )
    assert caixas["aviso"]["height"] > 0
    assert caixas["rodape"]["top"] >= caixas["aviso"]["bottom"] - 1  # não se sobrepõem
    assert caixas["aviso"]["left"] >= 0 and caixas["aviso"]["right"] <= caixas["largura"]
    assert caixas["rolagem"] <= caixas["largura"]
    # D64: o fragmento real não tem link (o plano supunha um; decisão provisória: sem link, o aviso
    # já diz como atualizar). Se um link entrar, este teste quebra de propósito: troque a linha
    # abaixo por target="_blank" e rel com noopener e noreferrer em cada link.
    expect(regiao.get_by_role("link")).to_have_count(0)


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_aviso_de_versao_tem_contraste_nos_dois_temas(
    page: Page, painel: str, aviso_ligado: None, esquema: str
) -> None:
    page.emulate_media(color_scheme=esquema)  # type: ignore[arg-type]
    _abrir_casca(page, painel)
    aviso = page.locator(f"{REGIAO} .aviso-versao")
    expect(aviso).to_be_visible()
    razao = aviso.evaluate(CONTRASTE)
    assert razao >= MINIMO, f"contraste do aviso no tema {esquema}: {razao}"


def test_aviso_vazio_nao_ocupa_linha(page: Page, painel: str) -> None:
    _abrir_casca(page, painel)  # aviso desligado (padrão): o fragmento sai vazio
    regiao = page.locator(REGIAO)
    expect(regiao).to_have_attribute("role", "status")
    expect(regiao).to_be_empty()
    expect(page.locator(".aviso-versao")).to_have_count(0)
    altura = regiao.evaluate("el => el.getBoundingClientRect().height")
    assert altura == 0, f"a região vazia ocupa {altura}px"
