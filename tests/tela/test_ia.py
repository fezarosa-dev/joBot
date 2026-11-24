"""Aba IA no navegador (plano T415; desenho 5.6, 6 e 10.3 da fase 4; D202).

Atalho pelo teclado, confirmação do custo com e sem JavaScript, a tabela por tarefa com erro
marcado e cores forçadas. O cofre é o `CofreFalso` e o modelo local vem de `app.state`. Nenhum
teste espera tempo real: `expect_navigation` e `expect`.
"""

import re
import threading
import time
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Browser, Page, expect

from apoio.cofre_falso import CofreFalso
from apoio.console import anotar_erros
from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import ler_config
from jobot.banco.conexao import abrir
from jobot.nucleo.ia.contrato import Falha, Pedido, Resposta
from jobot.sistema.cofre import Cofre

pytestmark = pytest.mark.tela

LOCAL = "Qwen3.5-4B-Q4_K_M"
CHAVE = "sk-ant-AbCd1234EfGh5678IjKl9012"
IA = "/configuracoes/ia"


@pytest.fixture
def cofre(tmp_path: Path) -> Cofre:
    return Cofre(tmp_path, CofreFalso())


@pytest.fixture
def app_painel(app_painel: FastAPI, cofre: Cofre) -> FastAPI:
    app_painel.state.cofre = cofre
    app_painel.state.relogio = RelogioFalso()
    app_painel.state.modelo_local = lambda: LOCAL
    return app_painel


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> Iterator[None]:
    # violação do CSP aparece como erro; o 422 do modelo inválido é a resposta esperada da página
    erros = anotar_erros(page, ignorar="422")
    yield
    assert erros == []


def _tarefas(tmp_path: Path) -> object:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        return ler_config(con, "ia_tarefas")


def test_tudo_offline_pelo_teclado(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}{IA}")
    expect(
        page.locator("nav.config-grupos").get_by_role("link", name="IA", exact=True)
    ).to_have_attribute("aria-current", "page")
    expect(page.get_by_text("Agora: Desligada.")).to_be_visible()
    desligar = page.get_by_role("button", name="Desligar a IA", exact=True)
    desligar.focus()
    page.keyboard.press("Tab")  # do "Desligar a IA", o Tab chega no "Tudo offline"
    offline = page.get_by_role("button", name="Tudo offline", exact=True)
    expect(offline).to_be_focused()
    expect(offline).to_have_accessible_description(re.compile("modelo local"))
    with page.expect_navigation():
        page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"/configuracoes/ia(\?salvo=1)?$"))
    expect(page.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    expect(page.get_by_text("Agora: Tudo offline.")).to_be_visible()
    no_local = {"ligada": True, "backend": "local", "modelo": LOCAL}
    assert _tarefas(tmp_path) == {"encaixe": no_local, "perguntas": no_local, "curriculo": no_local}


def test_custo_pede_confirmacao_e_voltar_nao_liga(
    page: Page, painel: str, tmp_path: Path, cofre: Cofre
) -> None:
    cofre.gravar("ia_anthropic", CHAVE)
    page.goto(f"{painel}{IA}")
    expect(page.get_by_text("API da Anthropic, cobrada por uso.", exact=False)).to_be_visible()
    with page.expect_navigation():
        page.get_by_role("button", name="Tudo Claude", exact=True).click()
    expect(page.get_by_role("heading", name="Ligar o encaixe num serviço cobrado?")).to_be_visible()
    expect(page.get_by_role("alert").filter(has_text="até 200 pedidos por dia")).to_be_visible()
    # o foco abre no aviso, não em "Ligar mesmo assim": o Return logo depois de abrir não grava
    aviso = page.get_by_role("region", name="Ligar o encaixe num serviço cobrado?")
    expect(aviso).to_be_focused()
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    expect(aviso).to_be_focused()
    assert _tarefas(tmp_path) == {"encaixe": {"ligada": False, "backend": "", "modelo": ""}}
    with page.expect_navigation():
        page.get_by_role("link", name="Voltar sem ligar", exact=True).click()
    expect(page).to_have_url(re.compile(r"/configuracoes/ia$"))
    assert _tarefas(tmp_path) == {"encaixe": {"ligada": False, "backend": "", "modelo": ""}}


def test_custo_confirmado_sem_javascript(
    browser: Browser, painel: str, tmp_path: Path, cofre: Cofre
) -> None:
    cofre.gravar("ia_anthropic", CHAVE)
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        pagina = contexto.new_page()
        pagina.goto(f"{painel}{IA}")
        pagina.get_by_role("button", name="Tudo Claude", exact=True).click()
        expect(pagina.get_by_role("button", name="Ligar mesmo assim", exact=True)).to_be_visible()
        assert _tarefas(tmp_path) == {"encaixe": {"ligada": False, "backend": "", "modelo": ""}}
        pagina.get_by_role("button", name="Ligar mesmo assim", exact=True).click()
        expect(pagina).to_have_url(re.compile(r"/configuracoes/ia\?salvo=1$"))
        expect(pagina.get_by_text("Agora: Tudo Claude.")).to_be_visible()
    finally:
        contexto.close()
    assert _tarefas(tmp_path) == {
        "encaixe": {"ligada": True, "backend": "anthropic", "modelo": "claude-haiku-5-5"},
        "perguntas": {"ligada": True, "backend": "anthropic", "modelo": "claude-sonnet-5-5"},
        "curriculo": {"ligada": True, "backend": "anthropic", "modelo": "claude-sonnet-5-5"},
    }


def test_tabela_com_modelo_invalido_marca_o_campo(
    page: Page, painel: str, tmp_path: Path, cofre: Cofre
) -> None:
    cofre.gravar("ia_openai", CHAVE)
    page.goto(f"{painel}{IA}")
    tarefa = page.get_by_role("group", name="Encaixe: o que cada vaga pede")
    tarefa.get_by_role("checkbox", name="Ligada", exact=True).check()
    onde = tarefa.get_by_role("combobox", name="Onde roda")
    onde.select_option("openai")
    expect(onde.locator('option[value="openai"]')).to_have_text("OpenAI (cobrada por uso)")
    # com o `datalist`, o campo de texto tem o papel de combobox
    modelo = tarefa.get_by_role("combobox", name="Modelo", exact=True)
    expect(modelo).to_have_accessible_description(re.compile("claude-haiku-5-5"))
    modelo.fill("gpt x")
    with page.expect_navigation():
        page.get_by_role("button", name="Salvar", exact=True).click()
    expect(page.get_by_role("alert").filter(has_text="sem espaço")).to_be_visible()
    tarefa = page.get_by_role("group", name="Encaixe: o que cada vaga pede")
    modelo = tarefa.get_by_role("combobox", name="Modelo", exact=True)
    expect(modelo).to_have_attribute("aria-invalid", "true")
    expect(modelo).to_have_value("gpt x")
    assert _tarefas(tmp_path) == {"encaixe": {"ligada": False, "backend": "", "modelo": ""}}


def test_campo_e_select_com_foco_visivel_em_cores_forcadas(page: Page, painel: str) -> None:
    page.emulate_media(forced_colors="active")
    page.goto(f"{painel}{IA}")
    tarefa = page.get_by_role("group", name="Encaixe: o que cada vaga pede")
    modelo = tarefa.get_by_role("combobox", name="Modelo", exact=True)
    modelo.focus()
    expect(modelo).to_be_focused()
    page.keyboard.press("Shift+Tab")  # pelo teclado: o select ganha o anel de foco
    onde = tarefa.get_by_role("combobox", name="Onde roda")
    expect(onde).to_be_focused()
    for campo in (modelo, onde):
        borda = campo.evaluate("e => getComputedStyle(e).borderTopWidth")
        assert float(borda.removesuffix("px")) > 0
    contorno = onde.evaluate(
        "e => [getComputedStyle(e).outlineStyle, getComputedStyle(e).outlineWidth]"
    )
    assert contorno[0] != "none"
    assert float(contorno[1].removesuffix("px")) >= 2


class _FabricaQueFalha:
    """`app.state.ia` falsa (T416): o pedido do teste espera `soltar` e falha sem rede."""

    def __init__(self) -> None:
        self.soltar = threading.Event()

    def __call__(self, backend: str, modelo: str) -> _FabricaQueFalha:
        return self

    def pedir(self, pedido: Pedido) -> Resposta:
        assert self.soltar.wait(10)
        raise Falha("sem_rede")

    def fechar(self) -> None:
        pass


def test_teste_ao_ligar_pergunta_e_mostra_a_falha_com_a_tarefa_desligada(
    page: Page, painel: str, tmp_path: Path, app_painel: FastAPI
) -> None:
    fabrica = _FabricaQueFalha()
    app_painel.state.ia = fabrica
    page.clock.install()  # sem `pause_at`: o polling do htmx precisa dos timers
    page.goto(f"{painel}{IA}")
    with page.expect_navigation():
        page.get_by_role("button", name="Tudo offline", exact=True).click()
    tarefa = page.locator("fieldset#ia-encaixe")
    expect(tarefa).to_have_attribute("hx-trigger", "every 2s")  # antes do 1º fast_forward
    expect(tarefa.get_by_text(re.compile("^Testando:"))).to_be_visible()
    expect(tarefa.get_by_role("checkbox", name="Ligada", exact=True)).to_be_checked()
    fabrica.soltar.set()
    fim = time.monotonic() + 5
    desligada = {"ligada": False, "backend": "local", "modelo": LOCAL}
    while _tarefas(tmp_path) != {
        "encaixe": desligada,
        "perguntas": desligada,  # o mesmo par: o teste é um só e as três caem (T437, T436)
        "curriculo": desligada,
    }:  # o resultado chega só pela pergunta periódica, depois do servidor terminar
        assert time.monotonic() < fim
        time.sleep(0.01)
    page.clock.fast_forward(2000)
    resultado = page.get_by_role("status").filter(has_text="O teste falhou")
    expect(resultado).to_be_visible()
    expect(resultado).to_contain_text("Confira a internet")
    tarefa = page.locator("fieldset#ia-encaixe")
    expect(tarefa).not_to_have_attribute("hx-trigger", re.compile("."))
    expect(tarefa.get_by_role("checkbox", name="Ligada", exact=True)).not_to_be_checked()
