"""Tela de fontes no navegador: desligar e ligar, pontos, link de reporte e rede (T50)."""

from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import semear
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao, gravar_saude

pytestmark = pytest.mark.tela

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    """Uma busca antiga ok e uma recente em que a remoteok quebrou."""
    app_painel.state.relogio = RelogioFalso(AGORA)
    with closing(abrir(tmp_path / "jobot.db")) as con:
        semear(con)  # as fontes cadastradas; a semente da tela só traz as das vagas
        for horas, estado, motivo in ((3, "ok", None), (1, "falhou", "saude.formato_mudou")):
            inicio = AGORA - timedelta(hours=horas)
            id_ = abrir_execucao(con, "busca", "agenda", inicio)
            assert id_ is not None
            gravar_saude(con, id_, "remoteok", "", estado, motivo=motivo, vagas=2, pedidos=1)  # type: ignore[arg-type]
            fechar_execucao(con, id_, inicio + timedelta(minutes=5))
    return app_painel


def _cartao(page: Page, chave: str) -> Locator:
    return page.locator(f"#fonte-{chave}")


def test_desligar_e_ligar_muda_o_estado_na_tela(page: Page, painel: str) -> None:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.goto(f"{painel}/fontes")
    cartao = _cartao(page, "remotive")
    expect(cartao).to_be_visible()

    cartao.get_by_role("button", name="Desligar").click()
    expect(_cartao(page, "remotive").locator(".selo")).to_have_text("Desligada")
    expect(_cartao(page, "remotive").get_by_role("button", name="Ligar")).to_be_visible()

    _cartao(page, "remotive").get_by_role("button", name="Ligar").click()
    expect(_cartao(page, "remotive").get_by_role("button", name="Desligar")).to_be_visible()
    assert erros == []


def test_tela_cabe_no_celular_sem_rolagem_lateral(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 360, "height": 740})
    page.goto(f"{painel}/fontes")
    largura = page.evaluate("document.documentElement.scrollWidth")
    assert largura <= 360


def test_pontos_e_link_de_reporte_aparecem_na_fonte_quebrada(page: Page, painel: str) -> None:
    page.goto(f"{painel}/fontes")
    cartao = _cartao(page, "remoteok")
    # dos mais antigos para os mais novos: ok, depois falhou (texto para leitor de tela)
    pontos = cartao.locator(".ponto .so-leitor")
    expect(pontos).to_have_text(["Ok", "Falhou"])
    link = cartao.get_by_role("link", name="Reportar problema")
    expect(link).to_be_visible()
    assert link.get_attribute("target") == "_blank"
    assert link.get_attribute("rel") == "noopener noreferrer"
    consulta = parse_qs(urlsplit(link.get_attribute("href") or "").query)
    assert consulta == {
        "template": ["fonte-quebrou.yml"],
        "fonte": ["remoteok"],
        "motivo": ["saude.formato_mudou"],
    }
    expect(cartao.locator(".reportar")).to_contain_text("já preenchidos")
    # fonte que não quebrou não leva link
    expect(_cartao(page, "remotive").get_by_role("link", name="Reportar problema")).to_have_count(0)


def test_tela_de_fontes_nao_faz_pedido_externo(page: Page, painel: str) -> None:
    pedidos: list[str] = []
    page.on("request", lambda r: pedidos.append(r.url))
    page.goto(f"{painel}/fontes")
    page.wait_for_load_state("networkidle")
    assert _cartao(page, "remoteok").get_by_role("link", name="Reportar problema").is_visible()
    assert pedidos, "a página não fez nem os pedidos dela"
    assert {urlsplit(u).hostname for u in pedidos} == {"127.0.0.1"}, pedidos
    # o link só é aberto pelo clique da pessoa: nenhum pedido foi para o GitHub
    assert not any("github.com" in u for u in pedidos)
