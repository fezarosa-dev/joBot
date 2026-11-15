"""Visual e movimento do cartão do 2Captcha no navegador (plano T186; desenho E15 e E16).

O cofre é o `CofreFalso` e a API do 2Captcha é um `httpx.MockTransport`: nada toca o sistema
nem a rede. Nenhum teste espera tempo real: `expect_response` e `page.clock`.
"""

import re
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, Route, expect

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import ler_config
from jobot.banco.conexao import abrir
from jobot.painel.i18n import t
from jobot.sistema.cofre import Cofre

pytestmark = pytest.mark.tela

CHAVE = "AbCd1234EfGh5678IjKl9012MnOp3456"
DIGITADA = "ZyXw9876VuTs5432RqPo1098NmLk7654"
INTERRUPTOR = "**/configuracoes/servicos/captcha/interruptor"
TESTAR = "**/configuracoes/servicos/captcha/testar"
SALDO_OK = {"errorId": 0, "balance": 0.94}


@pytest.fixture
def api() -> dict[str, Any]:
    """O que a API do 2Captcha responde; o teste troca `corpo` antes de clicar."""
    return {"corpo": SALDO_OK}


@pytest.fixture
def cofre(tmp_path: Path) -> Cofre:
    return Cofre(tmp_path, CofreFalso())


@pytest.fixture
def app_painel(app_painel: FastAPI, cofre: Cofre, api: dict[str, Any]) -> FastAPI:
    app_painel.state.cofre = cofre
    app_painel.state.relogio = RelogioFalso()
    app_painel.state.transporte = httpx.MockTransport(
        lambda _pedido: httpx.Response(200, json=api["corpo"])
    )
    return app_painel


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> Iterator[None]:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    yield
    assert erros == []


def _interruptor(page: Page) -> Locator:
    return page.get_by_role("switch", name="Usar o 2Captcha")


def _testar(page: Page) -> Locator:
    # por atributo, não por nome: durante o pedido o nome acessível vira só o texto de espera
    return page.locator('#cartao-captcha button[hx-post$="/captcha/testar"]')


def _teste_da_chave(page: Page) -> None:
    """Digita uma chave de formato certo, testa e espera a resposta do painel."""
    page.get_by_label("Chave da API").fill(DIGITADA)
    with page.expect_response(TESTAR):
        _testar(page).click()


def test_sem_chave_o_interruptor_esta_desativado_e_explica(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/servicos")
    expect(_interruptor(page)).to_be_disabled()
    expect(page.get_by_text("Salve uma chave primeiro.")).to_be_visible()


def test_salvar_chave_habilita_e_ligar_grava(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}/configuracoes/servicos")
    page.get_by_label("Chave da API").fill(CHAVE)
    page.get_by_role("button", name="Salvar", exact=True).click()
    expect(_interruptor(page)).to_be_enabled()
    page.clock.install(time=0)
    page.clock.pause_at(1000)  # parado: só o fast_forward abaixo faz o relógio andar
    with page.expect_response(INTERRUPTOR):
        _interruptor(page).click()
    expect(_interruptor(page)).to_be_checked()
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert ler_config(con, "captcha_ligado") is True
    mensagem = page.locator("#status-servicos [data-some-sozinho]")
    expect(mensagem).to_have_text("Salvo.")
    expect(mensagem).to_be_visible()
    page.clock.fast_forward(4999)  # ainda dentro dos 5 s
    expect(mensagem).to_be_visible()
    page.clock.fast_forward(1)
    expect(mensagem).to_be_hidden()


def test_espaco_liga_e_desliga(page: Page, painel: str, cofre: Cofre) -> None:
    cofre.gravar("2captcha", CHAVE)
    page.goto(f"{painel}/configuracoes/servicos")
    _interruptor(page).focus()
    for ligado in (True, False):
        velho = _interruptor(page).element_handle()
        with page.expect_response(INTERRUPTOR):
            page.keyboard.press("Space")
        # a resposta chega antes da troca (outerHTML): espera o nó velho sair do DOM
        velho.wait_for_element_state("hidden")
        # e o foco volta ao interruptor novo, onde a próxima tecla vai
        expect(_interruptor(page)).to_be_focused()
        # o HTMX só liga o hx-post do nó novo no fim do settle: antes disso a tecla não faz pedido
        expect(page.locator("#cartao-captcha")).not_to_have_class(re.compile(r"\bhtmx-settling\b"))
        expect(_interruptor(page)).to_be_checked(checked=ligado)


def test_testar_mostra_espera_e_depois_o_saldo(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/servicos")
    presos: list[Route] = []
    page.route("**/captcha/testar", lambda rota: presos.append(rota))
    page.get_by_label("Chave da API").fill(DIGITADA)
    botao = _testar(page)
    with page.expect_request(TESTAR):
        botao.click()
    expect(botao).to_be_disabled()
    expect(botao).to_have_class(re.compile(r"\bhtmx-request\b"))
    botao.click(force=True)  # desativado: não faz um segundo pedido
    expect(botao).to_be_disabled()
    assert len(presos) == 1
    presos[0].continue_()
    expect(page.locator("#resultado-captcha")).to_contain_text("Chave válida. Saldo: 0,94")
    expect(botao).to_be_enabled()


def test_testar_so_anuncia_a_espera_e_devolve_o_foco(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/servicos")
    presos: list[Route] = []
    page.route("**/captcha/testar", lambda rota: presos.append(rota))
    page.get_by_label("Chave da API").fill(DIGITADA)
    botao = _testar(page)
    expect(botao).to_have_accessible_name("Testar chave")
    with page.expect_request(TESTAR):
        botao.click()
    expect(botao).to_have_accessible_name("Testando…")  # o rótulo sai do nome durante o pedido
    presos[0].continue_()
    expect(page.locator("#resultado-captcha")).to_contain_text("Saldo")
    expect(botao).to_have_accessible_name("Testar chave")
    expect(botao).to_be_focused()


def test_cores_forcadas_mantem_ligado_e_desligado_distintos(
    page: Page, painel: str, cofre: Cofre
) -> None:
    cofre.gravar("2captcha", CHAVE)
    page.emulate_media(forced_colors="active")
    page.goto(f"{painel}/configuracoes/servicos")

    def aparencia() -> tuple[str, str]:
        chave = _interruptor(page)
        return (
            chave.evaluate("e => getComputedStyle(e).borderTopWidth"),
            chave.evaluate("e => getComputedStyle(e).backgroundColor"),
        )

    largura, fundo_desligado = aparencia()
    assert float(largura.removesuffix("px")) > 0
    with page.expect_response(INTERRUPTOR):
        _interruptor(page).click()
    expect(_interruptor(page)).to_be_checked()
    largura, fundo_ligado = aparencia()
    assert float(largura.removesuffix("px")) > 0
    assert fundo_ligado != fundo_desligado


def test_testar_com_erro_mostra_a_explicacao(page: Page, painel: str, api: dict[str, Any]) -> None:
    api["corpo"] = {"errorId": 1}
    page.goto(f"{painel}/configuracoes/servicos")
    _teste_da_chave(page)
    erro = page.locator("#resultado-captcha .resultado-erro")
    expect(erro).to_have_text(t("pt", "captcha.erro.chave_invalida"))


def test_olho_mostra_e_oculta_o_que_foi_digitado(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/servicos")
    campo = page.get_by_label("Chave da API")
    campo.fill(DIGITADA)
    expect(campo).to_have_attribute("type", "password")
    olho = page.get_by_role("button", name="Mostrar o que digitei")
    olho.click()
    expect(campo).to_have_attribute("type", "text")
    expect(olho).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_role("button", name="Mostrar o que digitei")).to_have_count(1)
    olho.click()
    expect(campo).to_have_attribute("type", "password")
    expect(olho).to_have_attribute("aria-pressed", "false")


def test_resultado_vazio_nao_ocupa_espaco(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/servicos")
    resultado = page.locator("#resultado-captcha")
    expect(resultado).to_have_attribute("aria-live", "polite")
    caixa = resultado.bounding_box()
    assert caixa is not None
    assert caixa["height"] == 0
    _teste_da_chave(page)
    expect(resultado).to_contain_text("Saldo")
    caixa = resultado.bounding_box()
    assert caixa is not None
    assert caixa["height"] > 0


def test_movimento_reduzido_zera_as_transicoes(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/servicos")
    chave = _interruptor(page)

    def duracoes() -> list[str]:
        return [
            chave.evaluate("(e, p) => getComputedStyle(e, p).transitionDuration", pseudo)
            for pseudo in ("", "::after")
        ]

    assert "0s" not in duracoes()  # controle: sem a emulação a chave se anima
    page.emulate_media(reduced_motion="reduce")
    assert duracoes() == ["0s", "0s"]


def test_nenhum_controle_padrao_no_cartao(page: Page, painel: str, cofre: Cofre) -> None:
    cofre.gravar("2captcha", CHAVE)
    page.goto(f"{painel}/configuracoes/servicos")
    cartao = page.locator("#cartao-captcha")
    expect(cartao.locator("input.chave")).to_have_count(1)
    expect(cartao.locator('input[type="checkbox"]:not(.chave)')).to_have_count(0)
    expect(cartao.locator("button:not(.botao)")).to_have_count(0)
    expect(cartao.locator("input:not(.chave):not(.campo-texto):not([type=hidden])")).to_have_count(
        0
    )


def test_salvo_e_anunciado_fora_do_cartao(page: Page, painel: str, cofre: Cofre) -> None:
    cofre.gravar("2captcha", CHAVE)
    page.goto(f"{painel}/configuracoes/servicos")
    status = page.locator("#status-servicos")
    status.evaluate("e => { e.dataset.marca = 'antes' }")
    with page.expect_response(INTERRUPTOR):
        _interruptor(page).click()
    expect(_interruptor(page)).to_be_checked()
    expect(status).to_contain_text("Salvo.")
    expect(status).to_have_attribute("data-marca", "antes")  # o mesmo nó: só a mensagem trocou
    expect(page.locator("#cartao-captcha #status-servicos")).to_have_count(0)


@pytest.mark.parametrize(
    ("esquema", "cor"),
    [("light", "rgb(30, 123, 52)"), ("dark", "rgb(48, 209, 88)")],
)
def test_resultado_ok_usa_o_token_nos_dois_temas(
    page: Page, painel: str, esquema: Literal["light", "dark"], cor: str
) -> None:
    page.emulate_media(color_scheme=esquema)
    page.goto(f"{painel}/configuracoes/servicos")
    _teste_da_chave(page)
    expect(page.locator("#resultado-captcha .resultado-ok")).to_have_css("color", cor)
