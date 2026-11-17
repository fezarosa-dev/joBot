"""Faixa de queda de sessão no topo, no navegador (plano T276; desenho 5.5).

Nenhum navegador de verdade abre aqui: o painel só lê o que o teste grava no banco.
"""

from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.relogio import RelogioFalso
from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.sessoes import gravar_sessao
from jobot.sistema.pastas import PASTA_NAVEGADOR

pytestmark = pytest.mark.tela

CHAVE = "falso_logado"
CONFIRMAR = "**/configuracoes/contas/esquecer/confirmar"
AGORA = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    """O site falso ligado e com a queda aberta (`conectado` e depois `precisa_entrar`)."""
    leitor = LeitorFalso(base="http://127.0.0.1:9")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.semear(con)
        cadastros.semear_leitores(con, [leitor])
        cadastros.ligar_fonte(con, CHAVE, True)
        gravar_sessao(con, "site", CHAVE, "conectado", None, AGORA - timedelta(hours=2))
        gravar_sessao(con, "site", CHAVE, "precisa_entrar", None, AGORA - timedelta(hours=1))
    app_painel.state.leitores = (leitor,)
    app_painel.state.navegador_instalado = "chrome"
    app_painel.state.relogio = RelogioFalso(AGORA)
    return app_painel


def test_faixa_aparece_em_vagas_e_o_link_leva_ao_cartao(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas")
    faixa = page.get_by_role("status").filter(has_text="Sua sessão no Site falso caiu.")
    expect(faixa).to_be_visible()
    faixa.get_by_role("link", name="Entrar de novo").click()
    expect(page).to_have_url(f"{painel}/configuracoes/contas#conta-{CHAVE}")
    expect(page.locator(f"#conta-{CHAVE}")).to_be_visible()


def test_esquecer_logins_tira_a_faixa_sem_recarregar(
    page: Page, painel: str, tmp_path: Path
) -> None:
    perfil = tmp_path / PASTA_NAVEGADOR
    (perfil / "Default").mkdir(parents=True)
    (perfil / "Default" / "Cookies").write_text("sessao")
    page.goto(f"{painel}/configuracoes/contas")
    faixa = page.locator(".aviso-contas")
    expect(faixa).to_have_count(1)  # controle: a faixa está lá antes de esquecer
    page.evaluate("window.semRecarregar = true")

    page.get_by_role("button", name="Esquecer logins").click()
    with page.expect_response(CONFIRMAR) as resposta:
        page.get_by_role("alertdialog").get_by_role("button", name="Esquecer", exact=True).click()
    assert resposta.value.status == 200
    expect(faixa).to_have_count(0)
    assert page.evaluate("window.semRecarregar") is True  # a página não recarregou
