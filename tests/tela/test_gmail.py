"""Cartão do Gmail no navegador (plano T278): "Salvar e conferir" conecta e esvazia o campo da
senha; "Remover" pergunta no alerta da T259; tudo anda pelo teclado.

O IMAP é um abridor falso em `app.state.abrir_imap` e o cofre é o `CofreFalso`: nada sai da máquina.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from jobot.nucleo import gmail
from jobot.sistema.cofre import Cofre

pytestmark = pytest.mark.tela

AGORA = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
ENDERECO = "pessoa.teste@gmail.com"
SENHA = "abcd efgh ijkl mnop"
REMOVER = "**/configuracoes/gmail/remover"


class ImapFalso:
    def __init__(self) -> None:
        self.logins: list[tuple[str, str]] = []

    def __call__(self) -> ImapFalso:
        return self

    def login(self, user: str, password: str) -> tuple[str, list[Any]]:
        self.logins.append((user, password))
        return "OK", [b"logado"]

    def select(self, mailbox: str = "INBOX", readonly: bool = False) -> tuple[str, list[Any]]:
        return "OK", [b"1"]

    def logout(self) -> tuple[str, list[Any]]:
        return "BYE", [b"tchau"]


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    app_painel.state.leitores = ()  # sem leitor a aba mostra só o Gmail (E13)
    app_painel.state.cofre = Cofre(tmp_path, CofreFalso())
    app_painel.state.abrir_imap = ImapFalso()
    app_painel.state.relogio = RelogioFalso(AGORA)
    return app_painel


def _cofre(app: FastAPI) -> tuple[Any, Any]:
    cofre: Cofre = app.state.cofre
    return cofre.ler(gmail.NOME_SENHA), cofre.ler(gmail.NOME_CONTA)


def test_salvar_conecta_e_esvazia_a_senha(page: Page, painel: str, app_painel: FastAPI) -> None:
    page.goto(f"{painel}/configuracoes/contas")
    cartao = page.locator("#conta-gmail")
    expect(cartao.get_by_text("Nunca entrou")).to_be_visible()
    cartao.get_by_label("Endereço do Gmail", exact=True).fill(ENDERECO)
    cartao.get_by_label("Senha de app", exact=True).fill(SENHA)
    cartao.get_by_role("button", name="Salvar e conferir", exact=True).click()
    expect(page.locator("#conta-gmail").get_by_text("Conectado", exact=True)).to_be_visible()
    expect(page.locator("#conta-gmail").get_by_label("Senha de app", exact=True)).to_have_value("")
    assert app_painel.state.abrir_imap.logins == [(ENDERECO, "abcdefghijklmnop")]


def test_remover_pergunta_e_cancelar_nao_apaga(
    page: Page, painel: str, app_painel: FastAPI
) -> None:
    app_painel.state.cofre.gravar(gmail.NOME_SENHA, "abcdefghijklmnop")
    app_painel.state.cofre.gravar(gmail.NOME_CONTA, ENDERECO)
    page.goto(f"{painel}/configuracoes/contas")
    remover = page.locator("#conta-gmail").get_by_role("button", name="Remover", exact=True)
    remover.click()
    alerta = page.get_by_role("alertdialog", name="Remover a senha de app do Gmail?")
    expect(alerta).to_be_visible()
    alerta.get_by_role("button", name="Cancelar", exact=True).click()
    expect(alerta).to_be_hidden()
    expect(remover).to_be_focused()  # o foco volta ao botão que abriu
    assert _cofre(app_painel)[0] is not None

    remover.click()
    with page.expect_response(REMOVER) as resposta:
        page.get_by_role("alertdialog").get_by_role("button", name="Remover", exact=True).click()
    assert resposta.value.status == 200
    expect(page.locator("#conta-gmail").get_by_text("Nunca entrou")).to_be_visible()
    expect(page.get_by_role("alertdialog")).to_have_count(0)
    assert _cofre(app_painel) == (None, None)


def test_botoes_pelo_teclado(page: Page, painel: str, app_painel: FastAPI) -> None:
    page.goto(f"{painel}/configuracoes/contas")
    cartao = page.locator("#conta-gmail")
    cartao.get_by_label("Endereço do Gmail", exact=True).fill(ENDERECO)
    senha = cartao.get_by_label("Senha de app", exact=True)
    senha.fill(SENHA)
    senha.press("Enter")  # o Return no campo manda o formulário, como o botão
    expect(page.locator("#conta-gmail").get_by_text("Conectado", exact=True)).to_be_visible()
    # a troca levou o campo focado: o foco vai ao cartão novo e o estado é anunciado (C3)
    expect(page.locator("#conta-gmail")).to_be_focused()
    expect(page.locator("#status-gmail")).to_contain_text("Gmail: Conectado.")

    remover = page.locator("#conta-gmail").get_by_role("button", name="Remover", exact=True)
    for _ in range(8):  # do cartão até o "Remover" só pelo Tab
        if remover.evaluate("e => e === document.activeElement"):
            break
        page.keyboard.press("Tab")
    expect(remover).to_be_focused()
    page.keyboard.press("Enter")
    alerta = page.get_by_role("alertdialog")
    expect(alerta).to_be_visible()
    page.keyboard.press("Escape")
    expect(alerta).to_be_hidden()
    expect(remover).to_be_focused()
    assert _cofre(app_painel)[0] is not None

    page.keyboard.press("Enter")
    expect(alerta).to_be_visible()
    page.keyboard.press("Tab")  # do <dialog> ao primeiro botão, o "Remover"
    with page.expect_response(REMOVER):
        page.keyboard.press("Enter")
    expect(page.locator("#conta-gmail").get_by_text("Nunca entrou")).to_be_visible()
    expect(page.locator("#conta-gmail")).to_be_focused()
    assert _cofre(app_painel) == (None, None)
