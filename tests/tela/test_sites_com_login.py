"""Grupo "Sites com login" no navegador: o interruptor grava na hora (plano T218).

Nenhum navegador de verdade abre aqui: o painel só lê o que o teste põe em `app.state`.
"""

from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela

CHAVE = "falso_logado"
INTERRUPTOR = f"**/configuracoes/sites-com-login/{CHAVE}/interruptor"


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
