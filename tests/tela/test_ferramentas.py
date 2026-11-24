"""Ferramentas › Modelo local no navegador (plano T417; desenho 10.2 da fase 4; D185.20).

A aba existe sem leitor com login, o Baixar pelo teclado troca o cartão pelo HTMX e mostra a
barra, e sem JavaScript o formulário volta à página. O comando entra por `app.state`
(`AbrirFalso`): nada baixa e nenhum teste espera tempo real.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.comando_falso import AbrirFalso
from apoio.console import anotar_erros
from jobot.sistema import ia_local

pytestmark = pytest.mark.tela

FERRAMENTAS = "/configuracoes/ferramentas"
MANIFESTO = ia_local.manifesto_local()


@pytest.fixture
def abrir_ia() -> Iterator[AbrirFalso]:
    abrir = AbrirFalso()
    abrir.comando.antes = [{"etapa": "ia_local", "feito": 300, "total": 1000}]
    yield abrir
    abrir.comando.liberar.set()


@pytest.fixture
def app_painel(app_painel: FastAPI, abrir_ia: AbrirFalso) -> FastAPI:
    app_painel.state.leitores = ()  # sem leitor com login: a aba fica, o navegador não
    app_painel.state.abrir_ia_local = abrir_ia
    return app_painel


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> Iterator[None]:
    erros = anotar_erros(page)  # violação do CSP aparece como erro
    yield
    assert erros == []


def _anotar(dados: Path, chave: str) -> None:
    servidor, modelo = MANIFESTO["llama_server"], MANIFESTO["modelos"][chave]
    anotacao = {
        "build": servidor["build"],
        "alvo": "ubuntu-x64",
        "programa": "llama/b/llama-server",
        "servidor_sha256": servidor["alvos"]["ubuntu-x64"]["sha256"],
        "modelo": chave,
        "arquivo": modelo["arquivo"],
        "modelo_sha256": modelo["sha256"],
    }
    (dados / "ferramentas").mkdir(exist_ok=True)
    (dados / "ferramentas" / ia_local.ANOTACAO).write_text(json.dumps(anotacao))


def test_baixar_pelo_teclado_sem_leitor(page: Page, painel: str, abrir_ia: AbrirFalso) -> None:
    page.goto(f"{painel}{FERRAMENTAS}")
    expect(
        page.locator("nav.config-grupos").get_by_role("link", name="Ferramentas", exact=True)
    ).to_have_attribute("aria-current", "page")
    expect(page.get_by_role("heading", name="Modelo local de IA")).to_be_visible()
    expect(page.get_by_text("Navegador dos sites com login")).to_have_count(0)
    expect(page.get_by_text("Não baixado", exact=True)).to_be_visible()
    baixar = page.get_by_role("button", name="Baixar", exact=True)
    baixar.focus()
    expect(baixar).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_text("Baixando", exact=True)).to_be_visible()
    expect(page.get_by_role("progressbar", name="Andamento do download")).to_be_visible()
    expect(page).to_have_url(re.compile(rf"{FERRAMENTAS}$"))  # o HTMX trocou só o cartão
    assert abrir_ia.comandos[0][0] == ["baixar", "ia-local"]


def test_baixar_sem_javascript(pagina_sem_js: Page, painel: str, abrir_ia: AbrirFalso) -> None:
    pagina_sem_js.goto(f"{painel}{FERRAMENTAS}")
    pagina_sem_js.get_by_role("button", name="Baixar", exact=True).click()
    expect(pagina_sem_js).to_have_url(re.compile(rf"{FERRAMENTAS}$"))
    expect(pagina_sem_js.get_by_text("Baixando", exact=True)).to_be_visible()
    expect(pagina_sem_js.get_by_role("progressbar", name="Andamento do download")).to_be_visible()
    assert abrir_ia.comandos[0][0] == ["baixar", "ia-local"]


def test_baixado_mostra_o_modelo_e_os_botoes(page: Page, painel: str, tmp_path: Path) -> None:
    _anotar(tmp_path, "4b")
    page.goto(f"{painel}{FERRAMENTAS}")
    expect(page.get_by_text("Modelo: Qwen3.5-4B-Q4_K_M, 2,7 GB.")).to_be_visible()
    expect(page.get_by_text("Licença: Apache-2.0.", exact=False)).to_be_visible()
    trocar = page.get_by_role("button", name="Trocar para Qwen3.5-2B-Q4_K_M (1,3 GB)")
    expect(trocar).to_be_visible()
    remover = page.get_by_role("button", name="Remover", exact=True)
    expect(remover).to_have_accessible_description(re.compile("desliga as tarefas de IA"))
    page.emulate_media(forced_colors="active")  # os botões seguem visíveis nas cores forçadas
    expect(trocar).to_be_visible()
    expect(remover).to_be_visible()
