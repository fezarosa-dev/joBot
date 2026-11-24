"""Aviso na tela quando um clique do HTMX falha (T151; D106: "todo erro aparece").

Rotas só de teste respondem o erro; o aviso é o da casca real (`#aviso-erro`, em `base.html`).
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from playwright.sync_api import Page, expect

from jobot.painel.seguranca import renderizar
from tela.test_casca_menu import CONTRASTE

pytestmark = pytest.mark.tela

CASCA = "/_casca"
REGIAO = "#aviso-erro"
MINIMO = 4.5
GENERICO_4XX = "Não deu para fazer isso. Recarregue a página e tente de novo."
GENERICO_5XX = (
    "Algo deu errado no joBot. Tente de novo; se repetir, veja o arquivo de log do joBot."
)
GENERICO_REDE = (
    "O joBot não respondeu. Ele pode ter sido fechado: ligue de novo pelo botão Ligar da janela"
    " do joBot (o atalho do menu), ou com jobot abrir."
)
BOTOES = """() => {
  const main = document.querySelector('main');
  main.insertAdjacentHTML('beforeend', `
    <button id="b409" hx-post="/_t/409" hx-swap="none">409</button>
    <button id="b400" hx-post="/_t/400" hx-swap="none">400</button>
    <button id="b404" hx-post="/_t/404" hx-swap="none">404</button>
    <button id="b500" hx-post="/_t/500" hx-swap="none">500</button>
    <button id="b503" hx-post="/_t/503" hx-swap="none">503</button>
    <button id="bhtml" hx-post="/_t/html" hx-swap="none">html</button>
    <button id="bvazio" hx-post="/_t/vazio" hx-swap="none">vazio</button>
    <button id="brede" hx-post="/_t/rede" hx-swap="none">rede</button>
    <button id="bok" hx-get="/_t/ok" hx-swap="none">ok</button>
    <button id="bpush" hx-get="/_t/ok" hx-target="#alvo" hx-swap="innerHTML"
            hx-push-url="/_casca?p=1">push</button>
    <div id="alvo"></div>`);
  htmx.process(main);
}"""


def _resposta(corpo: str, status: int, tipo: str = "text/html") -> Response:
    return Response(content=corpo, status_code=status, media_type=tipo)


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    @app_painel.get(CASCA)
    async def casca(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    @app_painel.post("/_t/409")
    async def _409() -> Response:
        return _resposta("<p data-aviso-erro>Texto X</p>", 409)

    @app_painel.post("/_t/400")
    async def _400() -> Response:
        return _resposta("sem fragmento", 400, "text/plain")

    @app_painel.post("/_t/404")
    async def _404() -> Response:
        return _resposta("<h1>nada</h1>", 404)

    @app_painel.post("/_t/500")
    async def _500() -> Response:
        return _resposta("Internal Server Error", 500, "text/plain")

    @app_painel.post("/_t/503")
    async def _503() -> Response:
        return _resposta("<p>fora do ar</p>", 503)

    @app_painel.post("/_t/html")
    async def _html() -> Response:
        return _resposta(
            "<p data-aviso-erro>Texto <b>forte</b> &lt;i&gt;literal&lt;/i&gt;"
            '<img src="http://exemplo.invalid/x.png" onerror="window.invadiu=1"></p>',
            409,
        )

    @app_painel.post("/_t/vazio")
    async def _vazio() -> Response:
        return _resposta("<p data-aviso-erro>   </p>", 409)

    @app_painel.get("/_t/ok")
    async def _ok() -> Response:
        return _resposta("<p>ok</p>", 200)

    @app_painel.post("/_t/rede")
    async def _rede() -> Response:  # nunca chega: o teste aborta o pedido no navegador
        return _resposta("", 200)

    return app_painel


def _abrir(page: Page, painel: str) -> None:
    page.goto(painel + CASCA)
    page.wait_for_load_state("networkidle")
    page.evaluate(BOTOES)


def _clicar(page: Page, botao: str) -> None:
    page.locator(f"#{botao}").click()


def _contar_pedidos(page: Page) -> None:
    """`window.pedidos` conta os pedidos já tratados: o `afterRequest` vem depois dos avisos."""
    page.evaluate(
        "() => { window.pedidos = 0;"
        " document.addEventListener('htmx:afterRequest', () => { window.pedidos++; }); }"
    )


def _pedir(page: Page, botao: str) -> None:
    """Clica e espera o HTMX terminar de tratar o pedido (erro ou não)."""
    antes = page.evaluate("window.pedidos")
    _clicar(page, botao)
    page.wait_for_function("antes => window.pedidos > antes", arg=antes)


def _fechar(page: Page) -> None:
    page.locator(REGIAO).get_by_role("button", name="Fechar aviso").click()


def test_aviso_nasce_escondido(page: Page, painel: str) -> None:
    _abrir(page, painel)
    expect(page.locator(REGIAO)).to_be_hidden()
    expect(page.locator(REGIAO)).to_have_attribute("role", "alert")


def test_fragmento_do_servidor_aparece_como_texto(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _clicar(page, "b409")
    regiao = page.locator(REGIAO)
    expect(regiao).to_be_visible()
    expect(regiao).to_contain_text("Texto X")
    expect(regiao).not_to_contain_text(GENERICO_4XX)


def test_500_em_texto_puro_mostra_a_mensagem_de_5xx(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _clicar(page, "b500")
    expect(page.locator(REGIAO)).to_contain_text(GENERICO_5XX)
    expect(page.locator(REGIAO)).not_to_contain_text("Internal Server Error")


@pytest.mark.parametrize(
    ("botao", "esperado"),
    [
        ("b400", GENERICO_4XX),
        ("b404", GENERICO_4XX),
        ("b503", GENERICO_5XX),
        ("bvazio", GENERICO_4XX),  # marcador sem texto: cai no genérico
    ],
)
def test_sem_fragmento_vale_a_mensagem_da_faixa(
    page: Page, painel: str, botao: str, esperado: str
) -> None:
    _abrir(page, painel)
    _clicar(page, botao)
    expect(page.locator(REGIAO)).to_contain_text(esperado)


def test_falha_de_rede_mostra_a_mensagem_de_rede(page: Page, painel: str) -> None:
    _abrir(page, painel)
    page.route("**/_t/rede", lambda rota: rota.abort())
    _clicar(page, "brede")
    expect(page.locator(REGIAO)).to_contain_text(GENERICO_REDE)


VOLTOU = "() => dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}))"


@pytest.mark.parametrize("saida", ["beforeunload", "pagehide"])
def test_falha_de_rede_com_a_pagina_saindo_nao_liga_o_aviso(
    page: Page, painel: str, saida: str
) -> None:
    """O WebKit dá `error` (sendError no htmx) ao pedido que a saída da página corta, e o Safari
    pode devolver a página pelo Voltar: o "sem rede" falso não liga (T352; D209.5). Os eventos
    vêm sintéticos para a ordem ser a mesma nos três motores."""
    _abrir(page, painel)
    _contar_pedidos(page)
    page.route("**/_t/rede", lambda rota: rota.abort())
    page.evaluate(f"() => dispatchEvent(new Event('{saida}'))")
    _pedir(page, "brede")
    expect(page.locator(REGIAO)).to_be_hidden()
    # a página que volta pelo Voltar fala de novo
    page.evaluate(VOLTOU)
    _pedir(page, "brede")
    expect(page.locator(REGIAO)).to_contain_text(GENERICO_REDE)


def test_pagina_que_volta_pelo_voltar_chega_sem_aviso(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _clicar(page, "b500")
    expect(page.locator(REGIAO)).to_be_visible()
    page.evaluate(VOLTOU)
    expect(page.locator(REGIAO)).to_be_hidden()


def test_fechar_esconde_e_erro_novo_reabre_com_o_texto_novo(page: Page, painel: str) -> None:
    _abrir(page, painel)
    regiao = page.locator(REGIAO)
    _clicar(page, "b500")
    expect(regiao).to_contain_text(GENERICO_5XX)
    regiao.get_by_role("button", name="Fechar aviso").click()
    expect(regiao).to_be_hidden()
    _clicar(page, "b409")
    expect(regiao).to_contain_text("Texto X")
    expect(regiao).not_to_contain_text(GENERICO_5XX)


def test_erro_novo_troca_o_texto_do_aviso_aberto(page: Page, painel: str) -> None:
    _abrir(page, painel)
    regiao = page.locator(REGIAO)
    _clicar(page, "b500")
    expect(regiao).to_contain_text(GENERICO_5XX)
    _clicar(page, "b409")
    expect(regiao).to_contain_text("Texto X")
    expect(regiao).not_to_contain_text(GENERICO_5XX)
    expect(regiao).to_be_visible()


def test_o_texto_chega_como_texto_nunca_como_elemento(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _clicar(page, "bhtml")
    regiao = page.locator(REGIAO)
    expect(regiao).to_contain_text("<i>literal</i>")
    # nada do fragmento vira elemento: só o botão de fechar e o parágrafo do texto
    expect(regiao.locator("b, i, img")).to_have_count(0)
    assert page.evaluate("window.invadiu") is None


def _empurrar_e_voltar(page: Page) -> None:
    """Um clique com hx-push-url e o botão Voltar: o HTMX troca o conteúdo do body."""
    _clicar(page, "bpush")
    expect(page.locator("#alvo")).to_contain_text("ok")
    page.go_back()
    expect(page.locator("#alvo")).to_have_count(1)  # o snapshot do histórico voltou
    expect(page.locator("#alvo")).to_be_empty()


def test_erro_depois_de_voltar_no_historico_ainda_aparece_e_fecha(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _empurrar_e_voltar(page)
    regiao = page.locator(REGIAO)
    _clicar(page, "b409")
    expect(regiao).to_contain_text("Texto X")
    regiao.get_by_role("button", name="Fechar aviso").click()
    expect(regiao).to_be_hidden()


def test_aviso_aberto_nao_volta_aberto_pelo_historico(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _clicar(page, "b500")
    expect(page.locator(REGIAO)).to_be_visible()
    _empurrar_e_voltar(page)
    expect(page.locator(REGIAO)).to_be_hidden()


def test_aviso_nao_rouba_o_foco(page: Page, painel: str) -> None:
    _abrir(page, painel)
    page.locator("#b409").focus()
    page.locator("#b409").press("Enter")
    expect(page.locator(REGIAO)).to_be_visible()
    expect(page.locator("#b409")).to_be_focused()


def test_aviso_nao_cobre_a_navegacao_nem_o_link_de_pular(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 360, "height": 640})
    _abrir(page, painel)
    _clicar(page, "b500")
    expect(page.locator(REGIAO)).to_be_visible()
    caixas = page.evaluate(
        """() => {
          const r = s => document.querySelector(s).getBoundingClientRect().toJSON();
          return {
            aviso: r('#aviso-erro'),
            topo: r('.topo'),
            largura: document.documentElement.clientWidth,
            rolagem: document.documentElement.scrollWidth,
          };
        }"""
    )
    assert caixas["aviso"]["top"] >= caixas["topo"]["bottom"] - 1
    assert caixas["aviso"]["left"] >= 0
    assert caixas["aviso"]["right"] <= caixas["largura"]
    assert caixas["rolagem"] <= caixas["largura"]
    # o link de pular, ao receber o foco, aparece no topo e não fica sob o aviso
    pular = page.get_by_role("link", name="Pular para o conteúdo")
    pular.focus()
    expect(pular).to_be_focused()
    # o link de pular desliza até o lugar (transição): espera ele ser o elemento do próprio ponto
    page.wait_for_function(
        """() => {
          const el = document.querySelector('.pular');
          const c = el.getBoundingClientRect();
          const no = document.elementFromPoint(c.x + c.width / 2, c.y + c.height / 2);
          return c.top >= 0 && no === el;
        }"""
    )


def test_aviso_fica_logo_abaixo_da_barra(page: Page, painel: str) -> None:
    """Desenho 5.2 (T251): faixa no fluxo, colada à barra, na coluna ao lado da lateral."""
    page.set_viewport_size({"width": 1200, "height": 800})
    _abrir(page, painel)
    _clicar(page, "b500")
    expect(page.locator(REGIAO)).to_be_visible()
    caixas = page.evaluate(
        """() => {
          const r = s => document.querySelector(s).getBoundingClientRect().toJSON();
          return {aviso: r('#aviso-erro'), topo: r('.topo'), lateral: r('aside.lateral')};
        }"""
    )
    assert caixas["aviso"]["top"] == pytest.approx(caixas["topo"]["bottom"], abs=1)
    assert caixas["aviso"]["left"] >= caixas["lateral"]["right"] - 1


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_aviso_tem_contraste_nos_dois_temas(page: Page, painel: str, esquema: str) -> None:
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    _abrir(page, painel)
    _clicar(page, "b500")
    texto = page.locator(f"{REGIAO} [data-aviso-texto]")
    expect(texto).to_be_visible()
    razao = texto.evaluate(CONTRASTE)
    assert razao >= MINIMO, f"contraste do aviso de erro no tema {esquema}: {razao}"


def test_mesmo_aviso_nao_reabre_depois_de_fechado(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _contar_pedidos(page)
    regiao = page.locator(REGIAO)
    _pedir(page, "b500")
    expect(regiao).to_be_visible()
    _fechar(page)
    expect(regiao).to_be_hidden()
    _pedir(page, "b500")  # a mesma falha de novo: o aviso fechado fica fechado
    _pedir(page, "b500")
    expect(regiao).to_be_hidden()


def test_pedido_bom_zera_e_a_mesma_falha_reabre(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _contar_pedidos(page)
    regiao = page.locator(REGIAO)
    _pedir(page, "b500")
    _fechar(page)
    _pedir(page, "bok")
    expect(regiao).to_be_hidden()
    _pedir(page, "b500")
    expect(regiao).to_be_visible()
    expect(regiao).to_contain_text(GENERICO_5XX)


def test_texto_diferente_abre_e_o_fechado_antes_volta_a_valer(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _contar_pedidos(page)
    regiao = page.locator(REGIAO)
    _pedir(page, "b500")
    _fechar(page)
    _pedir(page, "b409")  # texto novo: abre normalmente
    expect(regiao).to_contain_text("Texto X")
    _fechar(page)
    _pedir(page, "b409")
    expect(regiao).to_be_hidden()
    _pedir(page, "b500")  # o aviso aberto depois do 5xx zerou o "fechado"
    expect(regiao).to_contain_text(GENERICO_5XX)


def test_aviso_aberto_sem_fechar_continua_aberto_com_o_mesmo_texto(page: Page, painel: str) -> None:
    _abrir(page, painel)
    _contar_pedidos(page)
    regiao = page.locator(REGIAO)
    _pedir(page, "b500")
    _pedir(page, "b500")
    expect(regiao).to_be_visible()
    expect(regiao).to_contain_text(GENERICO_5XX)


def test_carga_e_polling_avisam_mas_nao_insistem_depois_de_fechado(page: Page, painel: str) -> None:
    chamadas: list[str] = []

    def derrubar(rota: object) -> None:
        chamadas.append("x")
        rota.abort()  # type: ignore[attr-defined]

    page.route("**/_t/fora", derrubar)
    _abrir(page, painel)
    _contar_pedidos(page)
    regiao = page.locator(REGIAO)
    page.evaluate(
        """() => {
          const main = document.querySelector('main');
          main.insertAdjacentHTML('beforeend',
            '<div id="poll" hx-get="/_t/fora" hx-trigger="load, every 300ms"'
            + ' hx-swap="none"></div>');
          htmx.process(main);
        }"""
    )
    page.wait_for_function("() => window.pedidos >= 1")
    expect(regiao).to_contain_text(GENERICO_REDE)  # o pedido de carga avisou
    _fechar(page)
    visto = page.evaluate("window.pedidos")
    page.wait_for_function("visto => window.pedidos >= visto + 3", arg=visto)  # 3 rodadas
    expect(regiao).to_be_hidden()
    assert len(chamadas) >= 4
