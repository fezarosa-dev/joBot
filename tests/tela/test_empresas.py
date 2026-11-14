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

from apoio.relogio import RelogioFalso
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


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
    return page.locator("#lista-empresas li.cartao").filter(
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
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.goto(f"{painel}/empresas")
    expect(page.locator(".vazio")).to_be_visible()

    formulario = _preencher(page, "  https://boards.greenhouse.io/Vitta/  ")
    formulario.get_by_role("button", name="Testar").click()
    expect(page.get_by_role("status")).to_contain_text("Vagas encontradas: 3")
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

    cartao.get_by_role("button", name="Desligar").click()
    expect(_cartao(page, "Vitta")).to_contain_text("Desligada")
    _cartao(page, "Vitta").get_by_role("button", name="Ligar").click()
    expect(_cartao(page, "Vitta")).not_to_contain_text("Desligada")

    _cartao(page, "Vitta").get_by_text("Remover", exact=True).click()
    _cartao(page, "Vitta").get_by_role("button", name="Remover mesmo").click()
    expect(page.locator(".vazio")).to_be_visible()


def test_endereco_vazio_nao_envia(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas")
    formulario = page.locator(".nova form")
    formulario.get_by_role("button", name="Testar").click()
    expect(page).to_have_url(re.compile(r"/empresas$"))
    expect(page.get_by_role("status")).to_have_count(0)  # o `required` do navegador segurou
