"""O "Copiar endereço" do e-mail de candidatura no detalhe (T286; desenho 5.7)."""

from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.relogio import RelogioFalso
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela

USD = 1  # id na ordem em que o `semear` grava; sem link próprio de candidatura
REGIAO = ".email-candidatura [role=status]"


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()  # o semeado é datado de `AGORA`
    with closing(abrir(tmp_path / "jobot.db")) as con:
        con.execute(
            "UPDATE vaga SET descricao_texto = 'Envie o currículo para rh@example.com.'"
            " WHERE id = ?",
            (USD,),
        )
        con.commit()
    return app_painel


def test_copiar_aparece_com_js_e_copia(page: Page, painel: str, browser_name: str) -> None:
    # as permissões da área de transferência só existem no Chromium do Playwright; Firefox e WebKit
    # deixam o writeText no clique. O que foi escrito se lê pelo próprio writeText, que segue o real
    if browser_name == "chromium":
        page.context.grant_permissions(["clipboard-write"])
    page.add_init_script(
        "const escrever = navigator.clipboard.writeText.bind(navigator.clipboard);"
        "navigator.clipboard.writeText = (texto) => { window.__copiado = texto;"
        " return escrever(texto); };"
    )
    page.goto(f"{painel}/vagas/{USD}")
    botao = page.get_by_role("button", name="Copiar endereço", exact=True)
    expect(botao).to_be_visible()
    botao.click()
    expect(page.locator(REGIAO)).to_have_text("Endereço copiado.")
    assert page.evaluate("() => window.__copiado") == "rh@example.com"


def test_copiar_que_falha_avisa(page: Page, painel: str) -> None:
    # sem a permissão: a recusa vem fixa, sem depender de como o Chromium sem tela trata o pedido
    page.add_init_script(
        "navigator.clipboard.writeText = () => Promise.reject(new Error('negado'))"
    )
    page.goto(f"{painel}/vagas/{USD}")
    page.get_by_role("button", name="Copiar endereço", exact=True).click()
    expect(page.locator(REGIAO)).to_have_text("Não deu para copiar. Selecione o endereço e copie.")
