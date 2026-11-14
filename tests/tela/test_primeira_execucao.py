"""Assistente de primeira execução no navegador: dois passos, recusa e fim (plano T53)."""

import re
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


def _passo_1(page: Page) -> None:
    page.get_by_label("Cargos ou palavras-chave").fill("Python")
    page.get_by_label("Cidade 1").fill("Curitiba")
    page.locator("select[name=uf]").first.select_option("PR")
    page.get_by_label("Remoto").check()
    page.get_by_role("button", name="Continuar").click()


def test_fluxo_completo_vai_do_passo_1_ao_fim_e_para_nos_destaques(
    page: Page, painel: str, sistema: FalsoSistema
) -> None:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))

    page.goto(f"{painel}/")
    expect(page).to_have_url(f"{painel}/primeira-execucao/1")
    expect(page.get_by_role("heading", name="O que você procura?")).to_be_visible()
    _passo_1(page)

    expect(page).to_have_url(re.compile(r"/primeira-execucao/2\?busca=\d+$"))
    resumo = page.locator("[data-resumo]")
    expect(resumo).to_contain_text("Python")
    expect(resumo).to_contain_text("Curitiba, PR")
    expect(resumo).to_contain_text("Remoto")

    page.get_by_label("Não ligar agora").check()
    page.get_by_role("button", name="Concluir").click()
    expect(page.get_by_role("heading", name="Tudo pronto")).to_be_visible()
    expect(page.locator("#conteudo").get_by_role("button", name="Buscar agora")).to_be_visible()
    assert all(c[0] != "enable" for c in sistema.systemctl())

    page.get_by_role("link", name="Ir para as vagas").click()
    expect(page).to_have_url(f"{painel}/vagas?aba=destaques")
    page.goto(f"{painel}/")  # concluído: a raiz não volta ao assistente
    expect(page).to_have_url(f"{painel}/vagas?aba=destaques")
    assert erros == []


def test_pular_o_passo_1_segue_sem_resumo(page: Page, painel: str) -> None:
    page.goto(f"{painel}/primeira-execucao/1")
    page.get_by_role("button", name="Pular").click()
    expect(page).to_have_url(f"{painel}/primeira-execucao/2")
    expect(page.get_by_role("heading", name="Segundo plano")).to_be_visible()
    expect(page.locator("[data-resumo]")).to_have_count(0)


def test_salario_invalido_mostra_o_aviso_e_guarda_o_que_foi_digitado(
    page: Page, painel: str
) -> None:
    page.goto(f"{painel}/primeira-execucao/1")
    page.get_by_label("Cargos ou palavras-chave").fill("Python")
    page.get_by_label("Salário mínimo por mês").fill("muito")
    page.get_by_role("button", name="Continuar").click()
    expect(page.get_by_role("alert")).to_contain_text("Salário mínimo inválido")
    expect(page.get_by_label("Cargos ou palavras-chave")).to_have_value("Python")


def test_recusa_do_segundo_plano_aparece_traduzida_na_tela(
    page: Page, painel: str, sistema: FalsoSistema
) -> None:
    sistema.systemd_ok = False
    page.goto(f"{painel}/primeira-execucao/2")
    page.get_by_label("Ligar o segundo plano").check()
    page.get_by_role("button", name="Concluir").click()
    alerta = page.get_by_role("alert")
    expect(alerta).to_contain_text("o systemd do usuário não responde")
    expect(alerta).not_to_contain_text("segundo_plano.")
    # a pessoa escolhe de novo e conclui
    page.get_by_label("Não ligar agora").check()
    page.get_by_role("button", name="Concluir").click()
    expect(page.get_by_role("heading", name="Tudo pronto")).to_be_visible()
