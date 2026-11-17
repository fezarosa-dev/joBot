"""Aba "Contas" no navegador: o interruptor grava na hora (plano T218), "Esquecer logins" confirma
na própria página (T219), o cartão mostra o selo e a hora da sessão (T275) e "Conferir agora"
espera e troca o cartão (T277).

Nenhum navegador de verdade abre aqui: o painel só lê o que o teste põe em `app.state`.
"""

import asyncio
import re
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager, closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, Route, expect

from apoio.relogio import RelogioFalso
from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.sessoes import gravar_sessao
from jobot.navegador.conferir import Conferencia
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.painel.rotas import configuracoes
from jobot.sistema.pastas import PASTA_NAVEGADOR

pytestmark = pytest.mark.tela

CHAVE = "falso_logado"
INTERRUPTOR = f"**/configuracoes/contas/{CHAVE}/interruptor"
CONFIRMAR = "**/configuracoes/contas/esquecer/confirmar"
LOGIN = f"/configuracoes/contas/{CHAVE}/login"
AGORA = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    leitor = LeitorFalso(base="http://127.0.0.1:9")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.semear(con)
        cadastros.semear_leitores(con, [leitor])
    app_painel.state.leitores = (leitor,)
    app_painel.state.navegador_instalado = "chrome"
    app_painel.state.relogio = RelogioFalso(AGORA)
    return app_painel


def _ligada(tmp_path: Path) -> int:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        return int(con.execute("SELECT ligada FROM fonte WHERE chave = ?", (CHAVE,)).fetchone()[0])


def _interruptor(page: Page) -> Locator:
    return page.get_by_role("switch", name="Site falso")


def test_interruptor_do_site_grava_na_hora(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}/configuracoes/contas")
    expect(page.get_by_role("link", name="Contas")).to_have_attribute("aria-current", "page")
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
    page.goto(f"{painel}/configuracoes/contas")
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
    page.goto(f"{painel}/configuracoes/contas")
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
    page.goto(f"{painel}/configuracoes/contas")
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
    page.goto(f"{painel}/configuracoes/contas")
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


# ------------------------------------------------------------------ T275: selo, hora e login


def _cartao(page: Page) -> Locator:
    return page.locator(f"#conta-{CHAVE}")


def _ligar_com_sessao(tmp_path: Path) -> None:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.ligar_fonte(con, CHAVE, True)
        gravar_sessao(con, "site", CHAVE, "conectado", None, AGORA)


@pytest.mark.parametrize(
    ("idioma", "aba", "selo", "hora"),
    [
        ("pt", "Contas", "Conectado", r"conferido hoje às \d\d:\d\d"),
        ("en", "Accounts", "Signed in", r"checked today at \d\d:\d\d"),
    ],
)
def test_aba_contas_mostra_selo_e_hora(
    page: Page, painel: str, tmp_path: Path, idioma: str, aba: str, selo: str, hora: str
) -> None:
    _ligar_com_sessao(tmp_path)
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.gravar_config(con, "idioma", idioma)
    page.goto(f"{painel}/configuracoes/contas")
    grupos = page.locator("nav.config-grupos")
    expect(grupos.get_by_role("link", name=aba)).to_have_attribute("aria-current", "page")
    expect(_cartao(page).locator(".selo")).to_have_text(selo)
    expect(_cartao(page)).to_contain_text(re.compile(hora))


class LoginFalso:
    """O `fazer_login` sem navegador: devolve `pronto` na hora."""

    async def __call__(self, leitor: LeitorComLogin, deps: Any, janela: Any) -> str:
        return "pronto"

    @asynccontextmanager
    async def dependencias(self, dados: Path, env: Mapping[str, str]) -> AsyncIterator[object]:
        yield object()


def _login_ate_o_cartao_novo(page: Page, clicar: Callable[[], None]) -> None:
    """Clica em "Fazer login agora" e avança o relógio até o polling trazer o cartão novo."""
    with page.expect_response(lambda r: r.url.endswith(LOGIN) and r.request.method == "POST"):
        clicar()
    # a resposta do POST chega antes de o htmx trocar o HTML e armar o every 5s: avançar o
    # relógio antes disso não dispara pergunta nenhuma
    expect(page.locator(f'#conta-{CHAVE} [hx-trigger="every 5s"]')).to_have_count(1)
    # o login falso termina logo, mas a tarefa do servidor pode não ter acabado na 1ª pergunta
    for _ in range(5):
        with page.expect_response(
            lambda r: r.url.endswith(LOGIN) and r.request.method == "GET"
        ) as pergunta:
            page.clock.fast_forward(5000)
        if pergunta.value.status == 200:
            break
    assert pergunta.value.status == 200
    expect(_cartao(page)).not_to_have_class(re.compile(r"htmx-settling"))
    expect(_cartao(page).locator(".selo")).to_have_text("Conectado")


def _login_falso(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    falso = LoginFalso()
    monkeypatch.setattr(configuracoes, "fazer_login", falso)
    monkeypatch.setattr(configuracoes, "dependencias_de_producao", falso.dependencias)
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.ligar_fonte(con, CHAVE, True)


def test_fim_do_login_nao_tira_o_foco_de_outro_campo(
    page: Page, painel: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O login pode levar minutos: quem foi digitar em outro campo da aba continua nele."""
    _login_falso(monkeypatch, tmp_path)
    page.clock.install()  # sem pause_at: o polling (every 5s) precisa dos timers andando
    page.goto(f"{painel}/configuracoes/contas")
    campo = page.locator("#campo-horarios")

    def clicar_e_ir_ao_campo() -> None:
        _cartao(page).get_by_role("button", name="Fazer login agora").click()
        campo.focus()

    _login_ate_o_cartao_novo(page, clicar_e_ir_ao_campo)
    expect(_cartao(page)).to_contain_text("Login feito")
    expect(campo).to_be_focused()


def test_fazer_login_termina_no_cartao_novo(
    page: Page, painel: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_falso(monkeypatch, tmp_path)
    page.clock.install()  # sem pause_at: o polling (every 5s) precisa dos timers andando
    page.goto(f"{painel}/configuracoes/contas")
    expect(_cartao(page).locator(".selo")).to_have_text("Nunca entrou")

    _login_ate_o_cartao_novo(
        page, lambda: _cartao(page).get_by_role("button", name="Fazer login agora").click()
    )
    expect(_cartao(page).locator(".selo")).to_have_text("Conectado")
    expect(_cartao(page)).to_contain_text("Login feito")
    # o outerHTML troca a região viva do cartão: o anúncio vai à região fixa e o foco ao cartão
    expect(page.locator("#status-sites")).to_contain_text("Login feito")
    expect(_cartao(page)).to_be_focused()
    expect(page.locator(f'#conta-{CHAVE} [hx-trigger="every 5s"]')).to_have_count(0)


def test_esquecer_volta_os_cartoes_a_nunca_entrou(page: Page, painel: str, tmp_path: Path) -> None:
    _ligar_com_sessao(tmp_path)
    _perfil_com_login(tmp_path)
    page.goto(f"{painel}/configuracoes/contas")
    expect(_cartao(page).locator(".selo")).to_have_text("Conectado")
    page.get_by_role("button", name="Esquecer logins").click()
    with page.expect_response(CONFIRMAR):
        page.get_by_role("alertdialog").get_by_role("button", name="Esquecer", exact=True).click()
    expect(page.get_by_text("Logins apagados.")).to_be_visible()
    expect(_cartao(page).locator(".selo")).to_have_text("Nunca entrou")
    expect(_cartao(page)).not_to_contain_text("conferido")


# ------------------------------------------------------------------ T277: conferir agora


class ConferirFalso:
    """O `conferir_sessao` sem navegador: espera o teste soltar e devolve `conectado`. O `Event`
    vive no laço do servidor, então o teste o solta por `call_soon_threadsafe`."""

    def __init__(self) -> None:
        self.liberar = asyncio.Event()
        self.laco: asyncio.AbstractEventLoop | None = None

    async def __call__(self, leitor: LeitorComLogin, deps: Any, relogio: Any) -> Conferencia:
        self.laco = asyncio.get_running_loop()
        async with asyncio.timeout(30):  # teto: um teste errado não pendura o servidor
            await self.liberar.wait()
        return Conferencia("conectado", None)

    def soltar(self) -> None:
        assert self.laco is not None, "a conferência não começou"
        self.laco.call_soon_threadsafe(self.liberar.set)

    @asynccontextmanager
    async def dependencias(self, dados: Path, env: Mapping[str, str]) -> AsyncIterator[object]:
        yield object()


CONFERIR = f"/configuracoes/contas/{CHAVE}/conferir"


def _conferido_ha(tmp_path: Path, segundos: int, estado: Any, motivo: Any = None) -> None:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.ligar_fonte(con, CHAVE, True)
        gravar_sessao(con, "site", CHAVE, estado, motivo, AGORA - timedelta(seconds=segundos))


def test_conferir_agora_mostra_conferindo_e_o_cartao_novo(
    page: Page, painel: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    falso = ConferirFalso()
    monkeypatch.setattr(configuracoes, "conferir_sessao", falso)
    monkeypatch.setattr(configuracoes, "dependencias_de_producao", falso.dependencias)
    _conferido_ha(tmp_path, 700, "nao_conferiu", "sem_rede")
    page.clock.install()  # sem pause_at: o polling (every 2s) precisa dos timers andando
    page.goto(f"{painel}/configuracoes/contas")
    expect(_cartao(page).locator(".selo")).to_have_text("Não deu para conferir")

    with page.expect_response(lambda r: r.url.endswith(CONFERIR) and r.request.method == "POST"):
        _cartao(page).get_by_role("button", name="Conferir agora").click()
    expect(_cartao(page)).to_have_attribute("aria-busy", "true")
    expect(_cartao(page).get_by_role("progressbar", name="Conferindo…")).to_be_visible()
    # a pergunta só sai depois que o htmx troca o HTML e arma o every 2s
    expect(page.locator(f'#conta-{CHAVE} [hx-trigger="every 2s"]')).to_have_count(1)
    expect(_cartao(page)).not_to_have_class(re.compile(r"htmx-settling"))
    with page.expect_response(
        lambda r: r.url.endswith(CONFERIR) and r.request.method == "GET"
    ) as pergunta:
        page.clock.fast_forward(2000)
    assert pergunta.value.status == 204  # ainda conferindo: nada troca
    expect(_cartao(page)).to_contain_text("Conferindo…")

    falso.soltar()
    for _ in range(5):  # a tarefa do servidor pode não ter acabado na pergunta seguinte
        with page.expect_response(
            lambda r: r.url.endswith(CONFERIR) and r.request.method == "GET"
        ) as pergunta:
            page.clock.fast_forward(2000)
        if pergunta.value.status == 200:
            break
    assert pergunta.value.status == 200
    expect(_cartao(page)).not_to_have_class(re.compile(r"htmx-settling"))
    expect(_cartao(page).locator(".selo")).to_have_text("Conectado")
    expect(_cartao(page)).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(f'#conta-{CHAVE} [hx-trigger="every 2s"]')).to_have_count(0)
    # o outerHTML troca o cartão: o resultado é anunciado na região fixa e o foco vai ao cartão
    expect(page.locator("#status-sites")).to_contain_text("Site falso: Conectado")
    expect(_cartao(page)).to_be_focused()
    # conferido agora mesmo: o botão volta desabilitado, dentro do intervalo
    expect(_cartao(page).get_by_role("button", name="Conferir agora")).to_be_disabled()


def test_conferir_desabilitado_no_intervalo_com_hora_e_frase(
    page: Page, painel: str, tmp_path: Path
) -> None:
    _conferido_ha(tmp_path, 60, "conectado")
    page.goto(f"{painel}/configuracoes/contas")
    botao = _cartao(page).get_by_role("button", name="Conferir agora")
    expect(botao).to_be_disabled()
    expect(botao).to_have_accessible_description(
        "Conferido há pouco. Dá para conferir de novo em alguns minutos."
    )
    expect(_cartao(page)).to_contain_text(re.compile(r"conferido hoje às \d\d:\d\d"))
    expect(_cartao(page).get_by_text("Conferido há pouco.")).to_be_visible()
