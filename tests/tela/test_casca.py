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
    "/static/css/casca.css",
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


GERAL = "/configuracoes/geral"


def _escolher(page: Page, preferencia: str, valor: str) -> None:
    """Tema e idioma saíram da barra (T251): ficam em Configurações > Geral, que recarrega."""
    with page.expect_navigation():
        page.locator(f"[data-preferencia={preferencia}]").get_by_role("combobox").select_option(
            valor
        )


def _escolhido(page: Page, preferencia: str) -> Locator:
    return page.locator(f"[data-preferencia={preferencia}]").get_by_role("combobox")


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
    page.goto(painel + GERAL)
    _escolher(page, "tema", "escuro")
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
    page.goto(painel + GERAL)
    expect(html).to_have_attribute("lang", "pt")
    expect(html).to_have_attribute("data-tema", "sistema")
    expect(_escolhido(page, "tema")).to_have_value("sistema")
    escuro_do_sistema = _fundo(page)

    _escolher(page, "tema", "claro")
    expect(html).to_have_attribute("data-tema", "claro")
    page.reload()
    expect(html).to_have_attribute("data-tema", "claro")
    expect(_escolhido(page, "tema")).to_have_value("claro")
    assert _fundo(page) != escuro_do_sistema
    assert urlsplit(page.url).path == GERAL

    _escolher(page, "idioma", "en")
    expect(html).to_have_attribute("lang", "en")
    page.reload()
    expect(html).to_have_attribute("lang", "en")
    expect(_escolhido(page, "tema")).to_have_value("claro")
    expect(_escolhido(page, "idioma")).to_have_value("en")
    # a barra não tem mais tema nem idioma
    expect(page.get_by_role("banner").get_by_role("combobox")).to_have_count(0)
    expect(page.get_by_role("banner").get_by_role("button", name="Dark")).to_have_count(0)


def test_link_pular_para_o_conteudo(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    pular = page.get_by_role("link", name="Pular para o conteúdo")
    page.keyboard.press("Tab")
    expect(pular).to_be_focused()
    expect(pular).to_be_in_viewport()
    page.keyboard.press("Enter")
    expect(page.locator("main#conteudo")).to_be_focused()


@pytest.mark.parametrize("largura", [360, 800, 1280])
def test_link_pular_fica_acima_da_barra(page: Page, painel: str, largura: int) -> None:
    """WCAG 2.4.11: o primeiro foco não fica sob a barra (vidro) em nenhuma faixa de largura;
    entre 640 e 900px a barra ganha z-index para ficar por cima da lateral sobreposta."""
    page.set_viewport_size({"width": largura, "height": 700})
    page.goto(painel + "/vagas")
    page.keyboard.press("Tab")
    pular = page.get_by_role("link", name="Pular para o conteúdo")
    expect(pular).to_be_focused()
    # o link aparece com transição: espera ele ser o elemento do próprio centro
    page.wait_for_function(
        """() => {
          const el = document.querySelector('.pular');
          const c = el.getBoundingClientRect();
          const no = document.elementFromPoint(c.x + c.width / 2, c.y + c.height / 2);
          return c.top >= 0 && no === el;
        }"""
    )


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


# a cor do vidro e o filtro da barra e da lateral (.vidro) e de um .painel colocado no main
ESTILO_VIDRO = """() => {
  const main = document.querySelector('main');
  const painel = Object.assign(document.createElement('div'), {className: 'painel'});
  main.append(painel);
  const lido = el => {
    const s = getComputedStyle(el);
    return {filtro: s.backdropFilter, fundo: s.backgroundColor};
  };
  return {
    topo: lido(document.querySelector('header.topo')),
    lateral: lido(document.querySelector('aside.lateral')),
    painel: lido(painel),
  };
}"""


def _opaco(fundo: str) -> bool:
    """`rgb(r, g, b)` ou `rgba(..., 1)`; qualquer alfa (`/ a`) abaixo de 1 é translúcido."""
    return "/" not in fundo and not (fundo.startswith("rgba(") and not fundo.endswith(", 1)"))


def test_painel_e_translucido(page: Page, painel: str) -> None:
    # desenho 5.1: vidro só na barra (.vidro); o .painel é conteúdo e fica opaco, sem filtro
    page.goto(painel + CASCA)
    estilo = page.evaluate(ESTILO_VIDRO)
    for vidro in ("topo", "lateral"):
        assert "blur" in estilo[vidro]["filtro"], vidro
        assert not _opaco(estilo[vidro]["fundo"]), vidro
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
        assert estilo["lateral"]["filtro"] == "none", emulacao
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
    for vidro in ("topo", "lateral"):
        assert estilo[vidro]["filtro"] == "none", vidro
        assert _opaco(estilo[vidro]["fundo"]), vidro


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


# ---- barra lateral (T251; desenho 5.2) ----
LARGA = {"width": 1200, "height": 800}
ROLA_DE_LADO = "document.documentElement.scrollWidth > window.innerWidth"


def test_lateral_e_barra_com_vidro(page: Page, painel: str) -> None:
    page.set_viewport_size(LARGA)
    page.goto(painel + "/vagas")
    ordem = page.evaluate(
        "() => [...document.body.children].map(el => el.id || el.tagName.toLowerCase())"
    )
    esperado = ["lateral", "header", "aviso-erro", "aviso-versao", "faixa-contas"]
    assert [x for x in ordem if x in {*esperado, "faixa-desfazer"}] == [
        *esperado,
        "faixa-desfazer",
    ]
    altura = page.locator("header.topo").evaluate("el => el.getBoundingClientRect().height")
    assert altura == pytest.approx(52, abs=0.5)
    estilo = page.evaluate(ESTILO_VIDRO)
    for vidro in ("topo", "lateral"):
        assert "blur" in estilo[vidro]["filtro"], vidro
    menu = page.get_by_role("complementary").get_by_role("navigation", name="Principal")
    expect(menu).to_be_visible()


@pytest.mark.parametrize("texto", ["padrao", "maior"])
def test_360px_sem_rolagem_lateral(page: Page, painel: str, texto: str) -> None:
    page.set_viewport_size({"width": 360, "height": 740})
    page.goto(painel + "/vagas")
    page.evaluate("t => { document.documentElement.dataset.texto = t; }", texto)
    assert not page.evaluate(ROLA_DE_LADO)
    # abaixo de 640px a navegação é uma faixa no topo, visível, e o body volta a rolar
    menu = page.get_by_role("navigation", name="Principal")
    expect(menu).to_be_visible()
    expect(menu.get_by_role("link", name="Buscas")).to_be_in_viewport()


def test_abaixo_de_900_a_lateral_recolhe(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 800, "height": 700})
    page.goto(painel + "/vagas")
    lateral = page.locator("aside.lateral")
    # o nome do botão muda com o estado (Mostrar ou Recolher): o localizador não pode depender dele
    botao = page.get_by_role("banner").locator("[data-recolher]")
    expect(lateral).to_be_hidden()
    expect(botao).to_have_attribute("aria-expanded", "false")
    expect(botao).to_have_accessible_name("Mostrar barra lateral")

    # abre por cima do conteúdo; Esc fecha e devolve o foco ao botão
    botao.click()
    expect(lateral).to_be_visible()
    expect(page.locator("html")).to_have_attribute("data-lateral", "sobreposta")
    expect(botao).to_have_attribute("aria-expanded", "true")
    expect(botao).to_have_accessible_name("Recolher barra lateral")
    # a lateral começa abaixo da barra (nunca vidro sobre vidro): o botão segue à vista e clicável
    caixa_lateral, caixa_barra = lateral.bounding_box(), page.get_by_role("banner").bounding_box()
    assert caixa_lateral is not None and caixa_barra is not None
    assert caixa_lateral["y"] >= caixa_barra["y"] + caixa_barra["height"] - 1
    assert page.evaluate(
        "() => { const b = document.querySelector('[data-recolher]').getBoundingClientRect();"
        " const no = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);"
        " return no?.closest('[data-recolher]') !== null; }"
    )
    botao.click()
    expect(lateral).to_be_hidden()
    expect(botao).to_have_attribute("aria-expanded", "false")

    botao.click()
    expect(lateral).to_be_visible()
    page.keyboard.press("Escape")
    expect(lateral).to_be_hidden()
    expect(botao).to_be_focused()

    # clicar fora fecha
    botao.click()
    expect(lateral).to_be_visible()
    page.mouse.click(700, 400)
    expect(lateral).to_be_hidden()

    # escolher um item fecha e leva à tela
    botao.click()
    page.get_by_role("navigation", name="Principal").get_by_role("link", name="Buscas").click()
    expect(page).to_have_url(painel + "/buscas")
    expect(lateral).to_be_hidden()
    assert not page.evaluate(ROLA_DE_LADO)


def test_janela_larga_recolhe_e_lembra(page: Page, painel: str) -> None:
    page.set_viewport_size(LARGA)
    page.goto(painel + "/vagas")
    lateral = page.locator("aside.lateral")
    expect(lateral).to_be_visible()
    page.get_by_role("button", name="Recolher barra lateral").click()
    expect(lateral).to_be_hidden()
    page.reload()
    expect(lateral).to_be_hidden()
    botao = page.get_by_role("button", name="Mostrar barra lateral")
    expect(botao).to_have_attribute("aria-expanded", "false")
    botao.click()
    expect(lateral).to_be_visible()


def test_janela_inativa_tira_o_vidro(page: Page, painel: str) -> None:
    page.set_viewport_size(LARGA)
    page.goto(painel + CASCA)
    html = page.locator("html")
    page.evaluate("window.dispatchEvent(new Event('blur'))")
    expect(html).to_have_attribute("data-janela", "inativa")
    estilo = page.evaluate(ESTILO_VIDRO)
    for vidro in ("topo", "lateral"):
        assert estilo[vidro]["filtro"] == "none", vidro
        assert _opaco(estilo[vidro]["fundo"]), vidro
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(html).not_to_have_attribute("data-janela", "inativa")


def test_divisor_pelo_teclado(page: Page, painel: str) -> None:
    page.set_viewport_size(LARGA)
    page.goto(painel + "/vagas")
    divisor = page.get_by_role("separator", name="Largura da barra lateral")
    lateral = page.locator("aside.lateral")
    expect(divisor).to_have_attribute("aria-valuenow", "240")
    divisor.focus()
    for tecla, valor in (
        ("ArrowRight", "250"),
        ("ArrowLeft", "240"),
        ("ArrowLeft", "230"),
        ("Home", "180"),
        ("End", "320"),
    ):
        page.keyboard.press(tecla)
        expect(divisor).to_have_attribute("aria-valuenow", valor)
    assert lateral.evaluate("el => el.getBoundingClientRect().width") == pytest.approx(320, abs=1)
    page.keyboard.press("End")  # já no máximo: não passa
    expect(divisor).to_have_attribute("aria-valuenow", "320")

    page.reload()  # a largura fica guardada
    expect(divisor).to_have_attribute("aria-valuenow", "320")
    divisor.dblclick()
    expect(divisor).to_have_attribute("aria-valuenow", "240")

    divisor.focus()
    page.keyboard.press("Enter")
    expect(lateral).to_be_hidden()
    expect(page.get_by_role("button", name="Mostrar barra lateral")).to_be_focused()


def test_conteudo_rola_no_proprio_conteiner(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1200, "height": 600})
    page.goto(painel + CASCA)
    page.evaluate(
        """() => {
          const alto = document.createElement('div');
          alto.style.blockSize = '3000px';
          document.querySelector('main').append(alto);
        }"""
    )
    page.mouse.move(800, 400)
    page.mouse.wheel(0, 800)
    page.wait_for_function("document.querySelector('.coluna').scrollTop > 0")
    assert page.evaluate("document.scrollingElement.scrollTop") == 0
    expect(page.locator("header.topo")).to_be_in_viewport()
