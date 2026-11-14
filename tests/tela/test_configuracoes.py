"""Configurações no navegador: abas, interruptores, aparência e privacidade (plano T54)."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.relogio import RelogioFalso
from apoio.segundo_plano_falso import FalsoSistema

pytestmark = pytest.mark.tela


@pytest.fixture
def sistema(tmp_path: Path) -> FalsoSistema:
    return FalsoSistema(home=str(tmp_path / "casa"))


@pytest.fixture
def app_painel(app_painel: FastAPI, sistema: FalsoSistema, tmp_path: Path) -> FastAPI:
    # nenhum systemctl de verdade: o segundo plano e o ambiente são falsos
    casa = tmp_path / "casa"
    casa.mkdir()
    app_painel.state.relogio = RelogioFalso()
    app_painel.state.rodar_comando = sistema
    app_painel.state.ambiente = {"HOME": str(casa)}
    app_painel.state.plataforma = "linux"
    return app_painel


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> list[str]:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    return erros


def test_menu_leva_as_configuracoes_e_cada_aba_abre_o_seu_grupo(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas")
    page.get_by_role("navigation", name="Principal").get_by_role(
        "link", name="Configurações"
    ).click()
    expect(page).to_have_url(f"{painel}/configuracoes/fontes")
    grupos = page.get_by_role("navigation", name="Grupos de configurações")
    expect(grupos.get_by_role("link", name="Fontes")).to_have_attribute("aria-current", "page")
    for nome, caminho in (
        ("Funções", "funcoes"),
        ("Segundo plano", "segundo-plano"),
        ("Aparência", "aparencia"),
        ("Privacidade", "privacidade"),
    ):
        grupos.get_by_role("link", name=nome).click()
        expect(page).to_have_url(f"{painel}/configuracoes/{caminho}")
        expect(grupos.get_by_role("link", name=nome)).to_have_attribute("aria-current", "page")


def test_desligar_destaques_tira_a_aba_e_o_painel_abre_em_todas(
    page: Page, painel: str, _sem_erro_no_console: list[str]
) -> None:
    page.goto(f"{painel}/configuracoes/funcoes")
    for rotulo in (
        "Descoberta de empresas pelo Common Crawl",
        "Páginas acompanhadas",
        "Enriquecimento",
        "Destaques de hoje",
        "Conversão de moeda",
        "Regras de ocultar",
    ):
        expect(page.get_by_label(rotulo, exact=True)).to_be_checked()
    page.get_by_label("Destaques de hoje", exact=True).uncheck()
    page.get_by_role("button", name="Salvar").click()
    expect(page).to_have_url(f"{painel}/configuracoes/funcoes")
    expect(page.get_by_label("Destaques de hoje", exact=True)).not_to_be_checked()

    page.goto(f"{painel}/vagas")
    expect(page.get_by_role("link", name="Todas")).to_have_attribute("aria-current", "page")
    expect(page.get_by_role("link", name="Destaques")).to_have_count(0)
    assert _sem_erro_no_console == []


def test_numero_de_destaques_invalido_mostra_o_aviso_e_nao_grava(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/funcoes")
    page.get_by_label("Conversão de moeda", exact=True).uncheck()
    # o navegador barra fora de 1 a 100; tira as regras do campo para chegar ao servidor
    page.locator("#destaques_n").evaluate("e => { e.removeAttribute('max'); e.value = '500' }")
    page.get_by_role("button", name="Salvar").click()
    expect(page.get_by_role("alert")).to_contain_text("de 1 a 100")
    page.goto(f"{painel}/configuracoes/funcoes")
    expect(page.get_by_label("Conversão de moeda", exact=True)).to_be_checked()


def test_privacidade_mostra_a_pasta_e_o_aviso_de_versao_nasce_desligado_e_grava(
    page: Page, painel: str, tmp_path: Path
) -> None:
    page.goto(f"{painel}/configuracoes/privacidade")
    expect(page.get_by_text("sem telemetria")).to_be_visible()
    expect(page.get_by_text("criptografar o disco")).to_be_visible()
    expect(page.locator("code")).to_have_text(str(tmp_path))
    aviso = page.get_by_label("Avisar quando houver versão nova")
    expect(aviso).not_to_be_checked()
    aviso.check()
    page.get_by_role("button", name="Salvar").click()
    expect(page).to_have_url(f"{painel}/configuracoes/privacidade")
    expect(page.get_by_label("Avisar quando houver versão nova")).to_be_checked()


def test_segundo_plano_liga_pela_tela_e_mostra_o_estado(
    page: Page, painel: str, sistema: FalsoSistema
) -> None:
    page.goto(f"{painel}/configuracoes/segundo-plano")
    page.get_by_label("Iniciar o joBot sozinho").check()
    page.get_by_role("button", name="Salvar").click()
    expect(page.get_by_label("Iniciar o joBot sozinho")).to_be_checked()
    expect(page.get_by_text("Serviço instalado:")).to_be_visible()
    assert ("enable", "--now", "jobot.service") in sistema.systemctl()


def test_segundo_plano_recusado_mostra_o_motivo(
    page: Page, painel: str, sistema: FalsoSistema
) -> None:
    sistema.systemd_ok = False
    page.goto(f"{painel}/configuracoes/segundo-plano")
    page.get_by_label("Iniciar o joBot sozinho").check()
    page.get_by_role("button", name="Salvar").click()
    expect(page.get_by_role("alert")).to_contain_text("o systemd do usuário não responde")


def test_aparencia_troca_tema_e_idioma_e_fica_na_pagina(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/aparencia")
    page.locator("[data-preferencia=tema]").get_by_role("button", name="Escuro").click()
    expect(page).to_have_url(f"{painel}/configuracoes/aparencia")
    expect(page.locator("html")).to_have_attribute("data-tema", "escuro")
    page.locator("[data-preferencia=idioma]").get_by_role("button", name="English").click()
    expect(page).to_have_url(f"{painel}/configuracoes/aparencia")
    expect(page.get_by_role("heading", name="Settings")).to_be_visible()


def test_fontes_desliga_uma_e_ela_volta_desmarcada(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/fontes")
    remotive = page.get_by_label("Remotive", exact=True)
    expect(remotive).to_be_checked()
    remotive.uncheck()
    page.get_by_role("button", name="Salvar").click()
    expect(page.get_by_label("Remotive", exact=True)).not_to_be_checked()
    expect(page.get_by_label("Himalayas", exact=True)).to_be_checked()


def test_so_pelo_teclado_liga_e_desliga_a_chave(page: Page, painel: str) -> None:
    page.goto(f"{painel}/configuracoes/funcoes")
    chave = page.get_by_label("Páginas acompanhadas", exact=True)
    chave.focus()
    page.keyboard.press("Space")
    expect(chave).not_to_be_checked()
    page.keyboard.press("Space")
    expect(chave).to_be_checked()
