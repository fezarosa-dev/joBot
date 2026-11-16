"""A tela Panorama no navegador (plano T288; desenho 5.2, 5.3): teclado e "Para responder"."""

from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.relogio import RelogioFalso
from jobot.banco import acoes
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela

USD = 1  # "Desenvolvedor Python", Zeta Corp
HIMALAYAS = 3  # "Backend Engineer", beta labs
PERGUNTA_HIMALAYAS = "Você se candidatou a Backend Engineer (beta labs)?"


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()  # o semeado é datado de `AGORA`
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravar_config(con, "primeira_execucao_concluida", True)  # senão /panorama redireciona
    return app_painel


def _abrir_panorama(page: Page, painel: str) -> None:
    """Abre o Panorama e espera o GET da faixa que vem com a página (`load`)."""
    with page.expect_response("**/aviso-candidatura*"):
        page.goto(f"{painel}/panorama")


def _foco_visivel(alvo: Locator) -> None:
    expect(alvo).to_be_focused()
    assert alvo.evaluate("e => getComputedStyle(e).outlineStyle") != "none"


def test_teclado_pelos_numeros_e_barras(page: Page, painel: str) -> None:
    _abrir_panorama(page, painel)
    numeros = page.locator(".numeros a")
    expect(numeros).to_have_count(5)
    numeros.first.focus()
    for i in range(1, 5):
        page.keyboard.press("Tab")
        _foco_visivel(numeros.nth(i))
    barras = page.locator('[aria-labelledby="panorama-aparece-modalidade"] .barras a')
    expect(barras).to_have_count(3)  # remoto, presencial e híbrido no semeado
    barras.first.focus()
    for i in range(1, 3):
        page.keyboard.press("Tab")
        _foco_visivel(barras.nth(i))
    with page.expect_navigation():
        page.keyboard.press("Enter")
    assert "modalidade=" in page.url


def test_para_responder_atualiza_com_o_evento(page: Page, painel: str, tmp_path: Path) -> None:
    hora = RelogioFalso().agora()
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert acoes.abriu_candidatura(con, USD, hora)
        assert acoes.abriu_candidatura(con, HIMALAYAS, hora + timedelta(minutes=1))
    _abrir_panorama(page, painel)
    lista = page.locator("#para-responder")
    expect(lista.get_by_role("group")).to_have_count(2)
    page.evaluate("() => { window.__mesmaPagina = true; }")
    pergunta = lista.get_by_role("group", name=PERGUNTA_HIMALAYAS, exact=True)
    with page.expect_response("**/panorama/para-responder"):
        pergunta.get_by_role("button", name="Sim, me candidatei", exact=True).click()
    expect(page.locator("#aviso-candidatura")).to_contain_text(
        "Backend Engineer marcada como Candidatei."
    )
    expect(lista.get_by_role("group")).to_have_count(1)
    expect(lista).not_to_contain_text("Backend Engineer")
    assert page.evaluate("() => window.__mesmaPagina") is True  # sem recarregar a página
