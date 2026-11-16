"""Casca do painel: rede só local, preferências, link de pular, HTMX e movimento (plano T36)."""

from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from playwright.sync_api import Locator, Page, expect

from jobot.painel.seguranca import renderizar

pytestmark = pytest.mark.tela

CASCA = "/_casca"
ESTATICOS = {
    "/static/css/base.css",
    "/static/js/app.js",
    "/static/vendor/htmx.min.js",
    "/static/fontes/InterVariable.woff2",
}
# quantas durações de transição ou animação maiores que zero existem na página
MOVIMENTOS = """() => [...document.querySelectorAll('*')].flatMap(el => {
  const s = getComputedStyle(el);
  return [...s.transitionDuration.split(','), ...s.animationDuration.split(',')];
}).map(parseFloat).filter(d => d > 0).length"""

# movimento reduzido: o que ainda anima no transform, em animação, ou em transição acima de 150ms
TRANSICOES_DE_TRANSFORM = """() => [...document.querySelectorAll('*')].filter(el => {
  const s = getComputedStyle(el);
  const anima = s.transitionDuration.split(',').some(d => parseFloat(d) > 0);
  const props = s.transitionProperty.split(',').map(p => p.trim());
  return anima && props.some(p => p === 'transform' || p === 'all');
}).length"""
MOVIMENTOS_ACIMA_DE_150MS = """() => [...document.querySelectorAll('*')].flatMap(
  el => getComputedStyle(el).transitionDuration.split(',')
).map(parseFloat).filter(d => d > 0.15).length"""
ANIMACOES = """() => [...document.querySelectorAll('*')].filter(
  el => getComputedStyle(el).animationName !== 'none'
).length"""


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    """Uma página só com a casca; as telas de verdade chegam nas tarefas seguintes."""

    @app_painel.get(CASCA)
    async def casca(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    return app_painel


def _botao(page: Page, nome: str) -> Locator:
    return page.get_by_role("button", name=nome, exact=True)


def _escolher(page: Page, nome: str) -> None:
    """Clica e espera o POST de /preferencias/* voltar: um reload antes disso cancelaria o envio."""
    with page.expect_response(lambda r: "/preferencias/" in r.url and r.request.method == "POST"):
        _botao(page, nome).click()


def _fundo(page: Page) -> str:
    fundo: str = page.evaluate("getComputedStyle(document.body).backgroundColor")
    return fundo


def test_nenhum_pedido_sai_de_127(page: Page, painel: str, _so_127: list[str]) -> None:
    respostas: list[tuple[str, int]] = []
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("response", lambda r: respostas.append((r.url, r.status)))
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.goto(painel + CASCA)
    page.wait_for_load_state("networkidle")
    expect(_botao(page, "Escuro")).to_be_visible()
    _escolher(page, "Escuro")
    expect(page.locator("html")).to_have_attribute("data-tema", "escuro")
    page.wait_for_load_state("networkidle")

    servidos = {urlsplit(url).path for url, status in respostas if status < 400}
    assert ESTATICOS <= servidos
    assert [url for url, _ in respostas if urlsplit(url).hostname != "127.0.0.1"] == []
    assert [(url, s) for url, s in respostas if s >= 400] == []
    assert _so_127 == []
    assert erros == []


def test_tema_e_idioma_ficam_depois_de_recarregar(page: Page, painel: str) -> None:
    html = page.locator("html")
    page.emulate_media(color_scheme="dark")
    page.goto(painel + CASCA)
    expect(html).to_have_attribute("lang", "pt")
    expect(html).to_have_attribute("data-tema", "sistema")
    expect(_botao(page, "Sistema")).to_have_attribute("aria-pressed", "true")
    escuro_do_sistema = _fundo(page)

    _escolher(page, "Claro")
    expect(html).to_have_attribute("data-tema", "claro")
    page.reload()
    expect(html).to_have_attribute("data-tema", "claro")
    expect(_botao(page, "Claro")).to_have_attribute("aria-pressed", "true")
    assert _fundo(page) != escuro_do_sistema
    assert urlsplit(page.url).path == CASCA

    _escolher(page, "English")
    expect(html).to_have_attribute("lang", "en")
    page.reload()
    expect(html).to_have_attribute("lang", "en")
    expect(_botao(page, "Light")).to_have_attribute("aria-pressed", "true")
    expect(_botao(page, "English")).to_have_attribute("aria-pressed", "true")


def test_link_pular_para_o_conteudo(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    pular = page.get_by_role("link", name="Pular para o conteúdo")
    page.keyboard.press("Tab")
    expect(pular).to_be_focused()
    expect(pular).to_be_in_viewport()
    page.keyboard.press("Enter")
    expect(page.locator("main#conteudo")).to_be_focused()


def test_link_no_texto_tem_sublinhado(page: Page, painel: str) -> None:
    # só a cor separa link de texto no tema escuro com cerca de 2,8:1 (WCAG 1.4.1 pede 3:1)
    page.goto(painel + CASCA)
    page.evaluate(
        """() => {
          const p = document.createElement('p');
          const a = Object.assign(document.createElement('a'), {href: '/x', textContent: 'a vaga'});
          p.append('Veja ', a);
          document.querySelector('main').append(p);
        }"""
    )
    decoracao = "el => getComputedStyle(el).textDecorationLine"
    assert page.locator("main p a").evaluate(decoracao) == "underline"
    assert page.locator("a.marca").evaluate(decoracao) == "none"


# a cor do vidro e o filtro de uma barra .vidro e de um .painel colocados no main
ESTILO_VIDRO = """() => {
  const main = document.querySelector('main');
  const painel = Object.assign(document.createElement('div'), {className: 'painel'});
  main.append(painel);
  const lido = el => {
    const s = getComputedStyle(el);
    return {filtro: s.backdropFilter, fundo: s.backgroundColor};
  };
  return {topo: lido(document.querySelector('header.topo')), painel: lido(painel)};
}"""


def _opaco(fundo: str) -> bool:
    """`rgb(r, g, b)` ou `rgba(..., 1)`; qualquer alfa (`/ a`) abaixo de 1 é translúcido."""
    return "/" not in fundo and not (fundo.startswith("rgba(") and not fundo.endswith(", 1)"))


def test_painel_e_translucido(page: Page, painel: str) -> None:
    # desenho 5.1: vidro só na barra (.vidro); o .painel é conteúdo e fica opaco, sem filtro
    page.goto(painel + CASCA)
    estilo = page.evaluate(ESTILO_VIDRO)
    assert "blur" in estilo["topo"]["filtro"]
    assert not _opaco(estilo["topo"]["fundo"])
    assert estilo["painel"]["filtro"] == "none"
    assert _opaco(estilo["painel"]["fundo"])


def test_sem_vidro_com_mais_contraste_ou_cores_forcadas(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    for emulacao in ("contrast", "forced_colors"):
        if emulacao == "contrast":
            page.emulate_media(contrast="more")
        else:
            page.emulate_media(forced_colors="active")
        estilo = page.evaluate(ESTILO_VIDRO)
        assert estilo["topo"]["filtro"] == "none", emulacao
        assert estilo["painel"]["filtro"] == "none", emulacao
        page.emulate_media(contrast="no-preference", forced_colors="none")
        page.locator("main .painel").evaluate("el => el.remove()")


def test_sem_vidro_com_menos_transparencia(page: Page, painel: str) -> None:
    """O Playwright não emula `prefers-reduced-transparency`: vai pelo protocolo do Chromium."""
    page.goto(painel + CASCA)
    sessao = page.context.new_cdp_session(page)
    sessao.send(
        "Emulation.setEmulatedMedia",
        {"features": [{"name": "prefers-reduced-transparency", "value": "reduce"}]},
    )
    if not page.evaluate("matchMedia('(prefers-reduced-transparency: reduce)').matches"):
        pytest.skip("este Chromium não emula prefers-reduced-transparency")
    estilo = page.evaluate(ESTILO_VIDRO)
    assert estilo["topo"]["filtro"] == "none"
    assert _opaco(estilo["topo"]["fundo"])


def test_htmx_configurado(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    config = page.evaluate(
        """() => window.htmx ? {
          allowEval: htmx.config.allowEval,
          selfRequestsOnly: htmx.config.selfRequestsOnly,
          includeIndicatorStyles: htmx.config.includeIndicatorStyles,
        } : null"""
    )
    # selfRequestsOnly já é true por padrão no HTMX 2.0.11: só allowEval e
    # includeIndicatorStyles provam que o meta htmx-config foi lido
    assert config == {"allowEval": False, "selfRequestsOnly": True, "includeIndicatorStyles": False}
    # sem estilo injetado: o CSP (style-src 'self') barraria e o console acusaria
    assert page.evaluate("document.querySelectorAll('style').length") == 0


def test_htmx_manda_o_token_csrf(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    status = page.evaluate(
        """() => new Promise(fim => {
          if (!window.htmx) return fim(null);
          document.body.addEventListener('htmx:afterRequest', e => fim(e.detail.xhr.status),
            {once: true});
          htmx.ajax('POST', '/preferencias/tema',
            {source: document.body, swap: 'none', values: {tema: 'escuro', voltar: '/_casca'}});
        })"""
    )
    assert status == 200
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-tema", "escuro")


def test_reduced_motion_desliga_animacao(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    assert page.evaluate(MOVIMENTOS) > 0
    page.emulate_media(reduced_motion="reduce")
    # nenhuma transição de transform e nenhuma animação; as outras com até 150ms (desenho 5.1)
    assert page.evaluate(TRANSICOES_DE_TRANSFORM) == 0
    assert page.evaluate(MOVIMENTOS_ACIMA_DE_150MS) == 0
    assert page.evaluate(ANIMACOES) == 0
