"""Preparar candidatura no navegador (plano T438; desenho 9 da fase 4; D234).

Com JavaScript, o botão troca a seção pela espera, que pergunta a cada 2 s até o resultado; sem
JavaScript, o POST volta à página e o "Preparando" leva a recarregar. A fábrica de backends é
falsa: nada sai da máquina. Nenhum teste espera tempo real do navegador (`page.clock`).
"""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Browser, Page, expect

from apoio.cofre_falso import CofreFalso
from apoio.console import anotar_erros
from apoio.relogio import RelogioFalso
from apoio.semear import AGORA, inserir_vaga
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.perfil import gravar_habilidades
from jobot.nucleo.ia.contrato import Pedido, Resposta, conferir
from jobot.sistema.cofre import Cofre

pytestmark = pytest.mark.tela

CARTA = "Prezada equipe, trabalho com Python há três anos."
RESPOSTA = {
    "idioma": "pt",
    "carta": CARTA,
    "resumo": "Analista de dados com Python.",
    "perguntar": [],
    "usou": ["habilidades"],
}


class _Fabrica:
    """`app.state.ia` falsa: responde `RESPOSTA`; com `soltar` armado, o pedido espera por ele."""

    def __init__(self) -> None:
        self.soltar: threading.Event | None = None

    def __call__(self, backend: str, modelo: str) -> _Fabrica:
        return self

    def pedir(self, pedido: Pedido) -> Resposta:
        if self.soltar is not None:
            assert self.soltar.wait(10)
        return conferir(pedido, RESPOSTA, "gemini")

    def fechar(self) -> None:
        pass


@pytest.fixture
def fabrica() -> _Fabrica:
    return _Fabrica()


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path, fabrica: _Fabrica) -> FastAPI:
    cofre = Cofre(tmp_path, CofreFalso())
    cofre.gravar("ia_gemini", "chave-gemini-1234567890")
    app_painel.state.cofre = cofre
    app_painel.state.relogio = RelogioFalso()
    app_painel.state.modelo_local = lambda: None
    app_painel.state.ia_pessoa = set()
    app_painel.state.ia = fabrica
    return app_painel


@pytest.fixture
def vaga(tmp_path: Path) -> int:
    """Uma vaga, a tarefa ligada no Gemini e o perfil com uma habilidade."""
    with closing(abrir(tmp_path / "jobot.db")) as con:
        vaga_id = inserir_vaga(con, titulo="Pessoa analista", descricao_texto="Pede Python.")
        con.commit()
        gravar_config(
            con,
            "ia_tarefas",
            {"candidatura": {"ligada": True, "backend": "gemini", "modelo": "g"}},
        )
        gravar_habilidades(con, ["Python"], AGORA)
    return vaga_id


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> Iterator[None]:
    erros = anotar_erros(page)
    yield
    assert erros == []


def _esperar(condicao: Callable[[], bool]) -> None:
    """O servidor terminar (a tarefa de fundo é de verdade); o navegador não espera nada."""
    fim = time.monotonic() + 5
    while not condicao():
        assert time.monotonic() < fim
        time.sleep(0.01)


def test_preparar_mostra_a_espera_e_o_resultado_chega_pela_pergunta(
    page: Page, painel: str, vaga: int, app_painel: FastAPI, fabrica: _Fabrica
) -> None:
    fabrica.soltar = threading.Event()
    page.clock.install()  # sem `pause_at`: a pergunta do htmx precisa dos timers
    page.goto(f"{painel}/vagas/{vaga}")
    secao = page.locator("#preparo")
    frase = "O seu perfil e o texto da vaga vão para o Google Gemini."
    expect(secao.get_by_text(frase, exact=False)).to_be_visible()  # junto do botão
    with page.expect_response(f"{painel}/vagas/{vaga}/candidatura/preparar"):
        secao.get_by_role("button", name="Preparar candidatura", exact=True).click()
    secao = page.locator("#preparo")
    expect(secao).to_have_attribute("hx-trigger", "every 2s")  # antes do 1º fast_forward
    expect(secao.get_by_role("status").filter(has_text="Preparando")).to_be_visible()
    fabrica.soltar.set()
    _esperar(lambda: not app_painel.state.ia_pessoa)
    page.clock.fast_forward(2000)
    carta = page.get_by_role("textbox", name="Carta", exact=True)
    expect(carta).to_have_value(CARTA)
    expect(carta).to_have_attribute("lang", "pt")
    expect(page.get_by_text("Confira antes de usar: a IA pode errar.")).to_be_visible()
    expect(page.get_by_role("button", name="Copiar a carta", exact=True)).to_be_visible()
    expect(page.locator("#preparo")).not_to_have_attribute("hx-trigger", "every 2s")
    expect(page.get_by_role("button", name="Preparar de novo", exact=True)).to_be_visible()


def test_sem_javascript_volta_a_pagina_e_recarregar_mostra_o_resultado(
    browser: Browser, painel: str, vaga: int, app_painel: FastAPI, fabrica: _Fabrica
) -> None:
    fabrica.soltar = threading.Event()
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        pagina = contexto.new_page()
        pagina.goto(f"{painel}/vagas/{vaga}")
        pagina.get_by_role("button", name="Preparar candidatura", exact=True).click()
        expect(pagina.get_by_text("Preparando: a IA escreve a carta", exact=False)).to_be_visible()
        fabrica.soltar.set()
        _esperar(lambda: not app_painel.state.ia_pessoa)
        pagina.get_by_role("link", name="Recarregue a página para ver o resultado.").click()
        expect(pagina.get_by_role("textbox", name="Carta", exact=True)).to_have_value(CARTA)
        # o "Copiar" vem escondido e só aparece com JavaScript
        expect(pagina.get_by_role("button", name="Copiar a carta", exact=True)).to_be_hidden()
    finally:
        contexto.close()
