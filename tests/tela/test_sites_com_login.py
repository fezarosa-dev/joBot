"""Grupo "Sites com login" no navegador: o interruptor grava na hora (plano T218) e "Esquecer
logins" confirma na própria página (T219).

Nenhum navegador de verdade abre aqui: o painel só lê o que o teste põe em `app.state`.
"""

import re
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, Route, expect

from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.sistema.pastas import PASTA_NAVEGADOR

pytestmark = pytest.mark.tela

CHAVE = "falso_logado"
INTERRUPTOR = f"**/configuracoes/sites-com-login/{CHAVE}/interruptor"
CONFIRMAR = "**/configuracoes/sites-com-login/esquecer/confirmar"


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    leitor = LeitorFalso(base="http://127.0.0.1:9")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.semear(con)
        cadastros.semear_leitores(con, [leitor])
    app_painel.state.leitores = (leitor,)
    app_painel.state.navegador_instalado = "chrome"
    return app_painel


def _ligada(tmp_path: Path) -> int:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        return int(con.execute("SELECT ligada FROM fonte WHERE chave = ?", (CHAVE,)).fetchone()[0])


def _interruptor(page: Page) -> Locator:
    return page.get_by_role("switch", name="Site falso")


def test_interruptor_do_site_grava_na_hora(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}/configuracoes/sites-com-login")
    expect(page.get_by_role("link", name="Sites com login")).to_have_attribute(
        "aria-current", "page"
    )
    expect(_interruptor(page)).not_to_be_checked()  # nasce desligado
    assert _ligada(tmp_path) == 0

    with page.expect_response(INTERRUPTOR) as resposta:
        _interruptor(page).click()
    assert resposta.value.status == 200
    assert _ligada(tmp_path) == 1
    expect(_interruptor(page)).to_be_checked()  # o cartão que voltou do servidor
    expect(page.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()

    page.reload()  # o estado vem do banco, não de um resto da tela
    expect(_interruptor(page)).to_be_checked()

    with page.expect_response(INTERRUPTOR):
        _interruptor(page).click()
    assert _ligada(tmp_path) == 0
    expect(_interruptor(page)).not_to_be_checked()


def test_estado_do_navegador_e_botao_esquecer_na_tela(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/sites-com-login")
    expect(page.get_by_text("Chrome encontrado")).to_be_visible()
    expect(page.get_by_role("button", name="Esquecer logins")).to_be_visible()
    expect(page.get_by_label("Horários (hora local)")).to_have_value("09:00, 18:00")


def _perfil_com_login(tmp_path: Path) -> Path:
    perfil = tmp_path / PASTA_NAVEGADOR
    (perfil / "Default").mkdir(parents=True)
    (perfil / "Default" / "Cookies").write_text("sessao")
    return perfil


def test_esquecer_abre_o_alerta_e_cancelar_nao_apaga(
    page: Page, painel: str, tmp_path: Path
) -> None:
    perfil = _perfil_com_login(tmp_path)
    page.goto(f"{painel}/configuracoes/sites-com-login")
    esquecer = page.get_by_role("button", name="Esquecer logins")
    expect(esquecer).to_be_enabled()
    esquecer.click()
    alerta = page.get_by_role("alertdialog", name="Apagar os logins de todos os sites?")
    expect(alerta).to_be_visible()
    expect(alerta).to_be_focused()  # Return logo depois de abrir não aperta nenhum botão
    assert perfil.exists()  # abrir o alerta não apaga

    page.get_by_role("button", name="Cancelar").click()
    expect(alerta).to_be_hidden()
    expect(esquecer).to_be_focused()  # o foco volta ao botão que abriu
    assert (perfil / "Default" / "Cookies").exists()

    esquecer.click()  # Esc também cancela
    expect(alerta).to_be_visible()
    page.keyboard.press("Escape")
    expect(alerta).to_be_hidden()
    assert (perfil / "Default" / "Cookies").exists()


def test_esquecer_logins_confirma_pelo_alerta(page: Page, painel: str, tmp_path: Path) -> None:
    # sem tratador de `dialog`: um `confirm()` do navegador seria recusado e nada apagaria
    perfil = _perfil_com_login(tmp_path)
    page.goto(f"{painel}/configuracoes/sites-com-login")
    page.get_by_role("button", name="Esquecer logins").click()
    alerta = page.get_by_role("alertdialog")
    expect(alerta).to_be_visible()

    with page.expect_response(CONFIRMAR) as resposta:
        alerta.get_by_role("button", name="Esquecer", exact=True).click()
    assert resposta.value.status == 200
    expect(page.get_by_text("Logins apagados.")).to_be_visible()
    expect(page.get_by_role("alertdialog")).to_have_count(0)
    assert not perfil.exists()


# a animação do limiar de 1 s (`andamento-entrar`, a mesma do envoltório do andamento) anda no
# relógio do navegador, que `page.clock` não move: o teste a põe parada em `ms` e devolve o nome e
# o atraso de cada animação do componente
POSICIONAR_ANIMACAO = """(ms) => [...document.querySelector("#esquecer-progresso").getAnimations()]
  .map((a) => {
    a.pause();
    a.currentTime = ms;
    return [a.animationName, a.effect.getTiming().delay];
  })"""


# congela a animação no instante em que ela nasce (a classe `htmx-request` entra no componente),
# antes de qualquer passo do teste: sem isso, num runner lento o atraso de 1 s corre em tempo real
# durante o clique e a espera por polling, e o `fill` só `backwards` a tira de `getAnimations()`
CONGELAR_AO_NASCER = """() => {
  const el = document.querySelector("#esquecer-progresso");
  new MutationObserver(() => {
    if (el.classList.contains("htmx-request")) el.getAnimations().forEach((a) => a.pause());
  }).observe(el, {attributes: true, attributeFilter: ["class"]});
}"""


def test_esquecer_mostra_o_progresso_depois_de_1s(page: Page, painel: str, tmp_path: Path) -> None:
    perfil = _perfil_com_login(tmp_path)
    retidas: list[Route] = []

    def segurar(rota: Route) -> None:  # a resposta só sai quando o teste soltar
        retidas.append(rota)

    page.route(CONFIRMAR, segurar)
    page.goto(f"{painel}/configuracoes/sites-com-login")
    espera = page.locator("#esquecer-progresso")
    barra = espera.get_by_role("progressbar")
    expect(espera).to_be_hidden()  # sem pedido, nada de barra na página
    expect(barra).to_have_count(0)
    page.evaluate(CONGELAR_AO_NASCER)

    page.get_by_role("button", name="Esquecer logins").click()
    with page.expect_request(CONFIRMAR):
        page.get_by_role("alertdialog").get_by_role("button", name="Esquecer", exact=True).click()
    expect(page.get_by_role("alertdialog")).to_be_hidden()  # o véu sai: a barra não fica atrás dele

    # 999 ms depois do pedido: ainda escondido (o limiar é o de 1 s de sempre)
    assert page.evaluate(POSICIONAR_ANIMACAO, 999) == [["andamento-entrar", 1000]]
    expect(espera).to_be_hidden()
    expect(barra).to_have_count(0)
    # 1 s e um pouco: o componente aparece, indeterminado e com o nome da etapa
    page.evaluate(POSICIONAR_ANIMACAO, 1001)
    expect(barra).to_have_count(1)
    expect(barra).to_be_visible()
    expect(barra).not_to_have_attribute("aria-valuenow", re.compile(r".*"))
    expect(espera.get_by_text("Apagando os logins guardados")).to_be_visible()
    assert (perfil / "Default" / "Cookies").exists()  # a resposta ainda não saiu: nada apagado

    retidas[0].continue_()  # solta a resposta: o texto do resultado entra e o componente some
    expect(page.get_by_text("Logins apagados.")).to_be_visible()
    expect(espera).to_be_hidden()
    expect(barra).to_have_count(0)
    assert not perfil.exists()
