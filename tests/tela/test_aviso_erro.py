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
    "O joBot não respondeu. Ele pode ter sido fechado: abra de novo com jobot abrir"
    " (ou pelo atalho do menu)."
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


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_aviso_tem_contraste_nos_dois_temas(page: Page, painel: str, esquema: str) -> None:
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    _abrir(page, painel)
    _clicar(page, "b500")
    texto = page.locator(f"{REGIAO} [data-aviso-texto]")
    expect(texto).to_be_visible()
    razao = texto.evaluate(CONTRASTE)
    assert razao >= MINIMO, f"contraste do aviso de erro no tema {esquema}: {razao}"
