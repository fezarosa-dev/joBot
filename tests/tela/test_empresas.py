"""Tela de empresas no navegador: testar antes de salvar, adicionar, desligar e remover (T51).

Sem rede de fora: o painel usa o `httpx.MockTransport` de `app.state.transporte`.
"""

import re
from contextlib import closing
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.console import anotar_erros
from apoio.relogio import RelogioFalso
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FAIXA = "#faixa-desfazer"


def _servidor() -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        assert pedido.url.host == "boards-api.greenhouse.io", f"teste não fala com {pedido.url}"
        texto = (FIXTURES / "greenhouse" / "normal.json").read_text(encoding="utf-8")
        return httpx.Response(200, text=texto, headers={"Content-Type": "application/json"})

    return httpx.MockTransport(responder)


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()
    app_painel.state.transporte = _servidor()
    with closing(abrir(tmp_path / "jobot.db")) as con:  # o cadastro só aceita fonte da tabela
        con.execute("INSERT INTO fonte (chave, leva) VALUES ('greenhouse', 'A')")
        con.commit()
    return app_painel


def _cartao(page: Page, nome: str) -> Locator:
    return page.locator("#lista-empresas li.linha-busca").filter(
        has=page.get_by_role("heading", name=nome, exact=True)
    )


def _preencher(page: Page, endereco: str) -> Locator:
    formulario = page.locator(".nova form")
    formulario.get_by_label("Sistema de vagas").select_option("greenhouse")
    formulario.get_by_label("Endereço do quadro de vagas").fill(endereco)
    return formulario


def test_testar_mostra_a_contagem_antes_de_salvar_e_depois_adiciona(
    page: Page, painel: str
) -> None:
    erros = anotar_erros(page)  # violação do CSP aparece como erro no console
    page.goto(f"{painel}/empresas")
    expect(page.locator(".vazio")).to_be_visible()

    formulario = _preencher(page, "  https://boards.greenhouse.io/Vitta/  ")
    formulario.get_by_role("button", name="Testar").click()
    expect(page.locator(".nova").get_by_role("status")).to_contain_text("Vagas encontradas: 3")
    expect(page.get_by_text("O identificador pode estar errado")).to_have_count(0)
    expect(page.locator("#lista-empresas")).to_have_count(0)  # testar não salva
    expect(page.get_by_label("Endereço do quadro de vagas")).to_have_value(
        "https://boards.greenhouse.io/Vitta/"
    )

    page.locator(".nova").get_by_role("button", name="Adicionar", exact=True).click()
    expect(page).to_have_url(re.compile(r"/empresas$"))
    expect(_cartao(page, "Vitta")).to_have_count(1)  # a caixa que o resolver devolveu
    assert erros == []


def test_desligar_ligar_e_remover(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas")
    _preencher(page, "Vitta").get_by_role("button", name="Adicionar", exact=True).click()
    cartao = _cartao(page, "Vitta")

    cartao.get_by_role("switch").click()  # a chave manda o formulário ao mudar
    expect(_cartao(page, "Vitta")).to_contain_text("Desligada")
    _cartao(page, "Vitta").get_by_role("switch").click()
    expect(_cartao(page, "Vitta")).not_to_contain_text("Desligada")

    _cartao(page, "Vitta").get_by_role("button", name="Remover").click()  # sem pergunta (T260)
    expect(page.locator(".vazio")).to_be_visible()
    expect(page.locator(FAIXA)).to_contain_text("Empresa removida")


def test_remover_desfazer_e_refazer_sem_recarregar(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas")
    _preencher(page, "Vitta").get_by_role("button", name="Adicionar", exact=True).click()
    _preencher(page, "Outra").get_by_role("button", name="Adicionar", exact=True).click()
    marca = "marca-sem-recarregar"
    page.evaluate(f"window.name = '{marca}'")
    faixa = page.locator(FAIXA)

    _cartao(page, "Vitta").get_by_role("button", name="Remover").click()
    expect(_cartao(page, "Vitta")).to_have_count(0)
    expect(faixa).to_contain_text("Empresa removida")
    expect(faixa.get_by_role("button", name="Refazer")).to_have_count(0)

    faixa.get_by_role("button", name="Desfazer").click()
    expect(_cartao(page, "Vitta")).to_have_count(1)  # a mesma linha volta, no seu lugar
    expect(_cartao(page, "Vitta")).to_have_class(re.compile(r"linha-volta"))
    # o realce aparece (o `--realce` vale na linha da Empresas) e depois some, com a classe
    assert page.evaluate(
        "getComputedStyle(document.querySelector('#lista-empresas li.linha-volta')).boxShadow"
    ) not in ("", "none")
    expect(_cartao(page, "Vitta")).not_to_have_class(re.compile(r"linha-volta"), timeout=3000)
    expect(faixa).to_contain_text("Empresa restaurada")

    faixa.get_by_role("button", name="Refazer").click()
    expect(_cartao(page, "Vitta")).to_have_count(0)
    expect(faixa).to_contain_text("Empresa removida")
    assert page.evaluate("window.name") == marca  # nada recarregou a página


def test_remover_e_desfazer_devolvem_o_foco(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas")
    _preencher(page, "Vitta").get_by_role("button", name="Adicionar", exact=True).click()
    _preencher(page, "Outra").get_by_role("button", name="Adicionar", exact=True).click()
    faixa = page.locator(FAIXA)

    _cartao(page, "Vitta").get_by_role("button", name="Remover").click()
    expect(_cartao(page, "Vitta")).to_have_count(0)
    expect(page.locator("#lista-empresas li.linha-busca").first).to_be_focused()  # o botão saiu

    faixa.get_by_role("button", name="Desfazer").click()
    expect(
        faixa.get_by_role("button", name="Refazer")
    ).to_be_focused()  # o botão apertado foi trocado


def test_menu_de_contexto_remove_com_a_faixa_de_desfazer(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas")
    _preencher(page, "Vitta").get_by_role("button", name="Adicionar", exact=True).click()

    _cartao(page, "Vitta").click(button="right", position={"x": 40, "y": 12})
    expect(page.get_by_role("menuitem", name="Ligar", exact=True)).to_be_hidden()  # já está ligada
    page.get_by_role("menuitem", name="Desligar", exact=True).click()
    expect(_cartao(page, "Vitta")).to_contain_text("Desligada")

    _cartao(page, "Vitta").click(button="right", position={"x": 40, "y": 12})
    expect(page.get_by_role("menuitem", name="Desligar", exact=True)).to_be_hidden()
    page.get_by_role("menuitem", name="Remover").click()
    expect(_cartao(page, "Vitta")).to_have_count(0)
    expect(page.locator("#conteudo")).to_be_focused()  # o botão do menu saiu: o foco não fica solto
    page.locator(FAIXA).get_by_role("button", name="Desfazer").click()
    expect(_cartao(page, "Vitta")).to_have_count(1)


def test_endereco_vazio_nao_envia(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas")
    formulario = page.locator(".nova form")
    formulario.get_by_role("button", name="Testar").click()
    expect(page).to_have_url(re.compile(r"/empresas$"))
    expect(page.locator(".nova").get_by_role("status")).to_have_count(
        0
    )  # o `required` do navegador segurou
