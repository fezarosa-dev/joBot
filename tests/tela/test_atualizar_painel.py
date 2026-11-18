"""Atualizar pelo painel, no navegador (plano T332; desenho 5.6 e 6.3; D176).

O `jobot atualizar` e a abertura da página da release entram por `app.state` (falsos); o
`/saude-local` é respondido pelo `page.route`, e o relógio do navegador só anda no
`fast_forward`: nenhum teste espera os 2 s da pergunta nem os 120 s do prazo.
"""

from collections.abc import Callable, Mapping
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from playwright.sync_api import Page, Route, expect

from jobot import __version__
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.painel.seguranca import renderizar

pytestmark = pytest.mark.tela

CASCA = "/_casca"
REGIAO = "#aviso-versao"
RELEASE = "https://github.com/fezarosa-dev/joBot/releases/latest"


class Falsos:
    def __init__(self) -> None:
        self.lancados: list[Path] = []
        self.abertos: list[str] = []


class _Rodando:
    def poll(self) -> int | None:
        return None


@pytest.fixture
def falsos() -> Falsos:
    return Falsos()


@pytest.fixture
def app_painel(app_painel: FastAPI, falsos: Falsos) -> FastAPI:
    @app_painel.get(CASCA)
    async def casca(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    def lancar(dados: Path, ambiente: Mapping[str, str]) -> _Rodando:
        falsos.lancados.append(dados)
        return _Rodando()

    def abrir_endereco(endereco: str) -> bool:
        falsos.abertos.append(endereco)
        return True

    app_painel.state.lancar_atualizacao = lancar
    app_painel.state.abrir_endereco = abrir_endereco
    with closing(abrir(app_painel.state.banco)) as con:
        gravar_config(con, "aviso_versao_ligada", True)
        gravar_config(con, "versao_nova", "v99.0.0")
    return app_painel


def _saude(versoes: list[str]) -> Callable[[Route], None]:
    """Responde o `/saude-local` com as versões da lista; a última se repete."""

    def responder(route: Route) -> None:
        versao = versoes.pop(0) if len(versoes) > 1 else versoes[0]
        route.fulfill(json={"app": "jobot", "versao": versao, "segundo_plano": False})

    return responder


def _abrir_casca(page: Page, painel: str) -> None:
    with page.expect_response("**/aviso-versao"):
        page.goto(painel + CASCA)
    page.wait_for_load_state("networkidle")


def _clicar_atualizar(page: Page) -> None:
    with page.expect_response("**/atualizar"):
        page.locator(REGIAO).get_by_role("button", name="Atualizar agora").click()
    # o app.js marca a primeira pergunta agendada: só depois dela o fast_forward a dispara
    expect(page.locator(f"{REGIAO} [data-atualizando]")).to_have_attribute("data-perguntas", "1")


def test_atualizar_agora_mostra_o_progresso_e_recarrega_com_a_versao_nova(
    page: Page, painel: str, falsos: Falsos
) -> None:
    page.clock.install()
    page.route("**/saude-local", _saude([__version__, "99.0.0"]))
    _abrir_casca(page, painel)
    _clicar_atualizar(page)
    regiao = page.locator(REGIAO)
    barra = regiao.get_by_role("progressbar")
    expect(barra).to_be_visible()
    expect(barra).to_have_accessible_name(
        "Atualizando o joBot. O painel recarrega sozinho quando a versão nova abrir."
    )
    expect(regiao.get_by_role("button", name="Tentar de novo")).to_be_hidden()
    assert len(falsos.lancados) == 1
    page.evaluate("() => { window.__mesmaPagina = true; }")
    caixa = regiao.locator("[data-atualizando]")
    with page.expect_response("**/saude-local"):
        page.clock.fast_forward(2000)
    expect(caixa).to_have_attribute("data-perguntas", "2")  # mesma versão: segue esperando
    assert page.evaluate("() => window.__mesmaPagina") is True
    with page.expect_navigation():
        page.clock.fast_forward(2000)
    assert page.evaluate("() => window.__mesmaPagina") is None


def test_atualizar_pelo_teclado_leva_o_foco_para_a_espera(page: Page, painel: str) -> None:
    """Revisão da T332: o botão focado some na troca; o foco vai para a caixa da espera, que tem
    nome (a linha do progresso), e não cai no body."""
    page.clock.install()
    page.route("**/saude-local", _saude([__version__]))
    _abrir_casca(page, painel)
    regiao = page.locator(REGIAO)
    regiao.get_by_role("button", name="Atualizar agora").focus()
    with page.expect_response("**/atualizar"):
        page.keyboard.press("Enter")
    caixa = regiao.locator("[data-atualizando]")
    expect(caixa).to_be_focused()
    expect(caixa).to_have_accessible_name(
        "Atualizando o joBot. O painel recarrega sozinho quando a versão nova abrir."
    )


def test_depois_de_120_s_explica_e_oferece_tentar_de_novo(
    page: Page, painel: str, falsos: Falsos
) -> None:
    page.clock.install()
    page.route("**/saude-local", _saude([__version__]))
    _abrir_casca(page, painel)
    _clicar_atualizar(page)
    regiao = page.locator(REGIAO)
    caixa = regiao.locator("[data-atualizando]")
    demorou = regiao.locator("[data-atualizar-demorou]")
    perguntas = 0
    # o relógio da página também anda sozinho entre os pulos: o prazo cai na 59ª ou na 60ª
    while perguntas < 70 and demorou.is_hidden():
        perguntas += 1
        expect(caixa).to_have_attribute("data-perguntas", str(perguntas))
        with page.expect_response("**/saude-local"):
            page.clock.fast_forward(2000)
        if perguntas == 1:
            expect(demorou).to_be_hidden()
    assert 55 <= perguntas <= 61, perguntas
    expect(demorou).to_be_visible()
    # o foco estava na caixa (veio do botão apertado): vai ao "Tentar de novo"
    expect(regiao.get_by_role("button", name="Tentar de novo")).to_be_focused()
    expect(demorou).to_contain_text("logs/atualizar.log")
    expect(regiao.get_by_role("progressbar")).to_be_hidden()
    expect(caixa).to_have_attribute("data-perguntas", str(perguntas))  # parou de perguntar
    with page.expect_response("**/atualizar"):
        regiao.get_by_role("button", name="Tentar de novo").click()
    expect(regiao.get_by_role("progressbar")).to_be_visible()
    expect(regiao.locator("[data-atualizando]")).to_be_focused()
    # o falso ainda roda: o segundo POST só volta a esperar, sem outro `jobot atualizar`
    assert len(falsos.lancados) == 1


def test_casca_velha_baixa_a_janela_nova_pelo_python(
    page: Page, painel: str, falsos: Falsos
) -> None:
    page.set_viewport_size({"width": 390, "height": 700})  # celular: o caso mais apertado
    agente = page.evaluate("() => navigator.userAgent")
    page.set_extra_http_headers({"User-Agent": f"{agente} joBot-casca/0.4.0 (linux)"})
    _abrir_casca(page, painel)
    regiao = page.locator(REGIAO)
    expect(regiao).to_contain_text("Esta janela é de uma versão antiga do joBot")
    expect(regiao.get_by_role("button", name="Atualizar agora")).to_be_visible()
    rolagem = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert rolagem <= 0, f"a faixa estoura a largura em {rolagem}px"
    with page.expect_response("**/abrir-release"):
        regiao.get_by_role("button", name="Baixar a janela nova").click()
    aviso = regiao.get_by_text("A página da versão nova abriu no seu navegador.")
    expect(aviso).to_be_focused()  # o botão sumiu na troca: o foco não cai no body
    assert falsos.abertos == [RELEASE]
    expect(regiao.get_by_role("link")).to_have_count(0)  # o painel não abre nada de fora


def test_configuracoes_geral_atualiza_e_mostra_o_progresso_na_faixa(
    page: Page, painel: str, falsos: Falsos
) -> None:
    page.clock.install()
    page.route("**/saude-local", _saude([__version__]))
    page.goto(painel + "/configuracoes/geral")
    conteudo = page.locator("#conteudo")
    expect(conteudo).to_contain_text(f"Versão instalada: {__version__}")
    expect(conteudo).to_contain_text("Última versão conhecida: v99.0.0")
    with page.expect_response("**/atualizar"):
        conteudo.get_by_role("button", name="Atualizar agora").click()
    expect(page.locator(REGIAO).get_by_role("progressbar")).to_be_visible()
    assert len(falsos.lancados) == 1
