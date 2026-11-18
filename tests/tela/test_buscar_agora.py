"""Buscar agora, andamento ao vivo e sair, no navegador (plano T49)."""

import asyncio
import threading
from contextlib import closing
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.console import anotar_erros
from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao
from jobot.painel.rotas import execucao as rota

pytestmark = pytest.mark.tela


@pytest.fixture
def liberar() -> threading.Event:
    return threading.Event()


@pytest.fixture
def terminou() -> threading.Event:
    return threading.Event()


@pytest.fixture
def chamadas() -> list[str]:
    return []


@pytest.fixture
def app_painel(
    app_painel: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    liberar: threading.Event,
    terminou: threading.Event,
    chamadas: list[str],
) -> FastAPI:
    # o que o lifespan do `serve` põe em app.state (D55, D58); aqui o lifespan fica desligado
    app_painel.state.relogio = RelogioFalso()
    app_painel.state.travas = {"busca": asyncio.Lock()}
    app_painel.state.cliente = None
    app_painel.state.servidor = SimpleNamespace(should_exit=False)
    banco = app_painel.state.banco

    async def falsa(con: Any, cliente: Any, relogio: Any, motivo: str, **kw: Any) -> int:
        chamadas.append(motivo)
        with closing(abrir(banco)) as propria:
            id_ = abrir_execucao(propria, "busca", "agora", datetime.now(UTC))
            assert id_ is not None
            while not liberar.is_set():  # a busca segue rodando até o teste soltar
                await asyncio.sleep(0.02)
            agora = datetime.now(UTC).isoformat()
            inserir_vaga(propria, primeira_vista_em=agora)
            inserir_vaga(propria, primeira_vista_em=agora)
            propria.commit()
            fechar_execucao(propria, id_, datetime.now(UTC))
        terminou.set()
        return id_

    monkeypatch.setattr(rota, "executar_busca", falsa)
    return app_painel


def _proxima_pergunta(page: Page, liberar: threading.Event, terminou: threading.Event) -> None:
    """Solta a busca, espera ela fechar no banco e adianta o relógio da página até a pergunta
    de 2 em 2 s do andamento (`hx-trigger="every 2s"`), sem esperar os 2 s de verdade."""
    liberar.set()
    assert terminou.wait(5)
    page.clock.fast_forward(2000)


def test_buscar_agora_mostra_o_andamento_e_as_vagas_novas(
    page: Page,
    painel: str,
    liberar: threading.Event,
    terminou: threading.Event,
    chamadas: list[str],
) -> None:
    erros = anotar_erros(page)  # violação do CSP aparece como erro no console
    page.clock.install()  # o tempo corre; só o fast_forward pula a espera da pergunta
    page.goto(f"{painel}/vagas?aba=todas")
    viva = page.locator("#andamento-etapa")  # a região viva fixa, fora do #andamento (T252)
    expect(viva).to_have_attribute("role", "status")
    expect(viva).to_have_attribute("aria-live", "polite")
    regiao = page.locator("#andamento")

    botao = page.get_by_role("banner").get_by_role("button", name="Buscar agora")
    botao.click()
    barra = regiao.get_by_role("progressbar", name="Andamento da busca")
    expect(barra).to_be_visible()  # passou o limiar de 1 s
    expect(regiao.locator(".progresso-linha")).to_have_text("Preparando as consultas")
    expect(viva).to_have_text("Preparando as consultas")
    # outro clique com a busca rodando não dispara outra: avisa e mostra a que roda
    botao.click()
    expect(regiao).to_contain_text("Uma busca já está rodando")
    expect(barra).to_be_visible()  # a que já rodava não some pelo limiar
    assert chamadas == ["agora"]

    _proxima_pergunta(page, liberar, terminou)  # a pergunta traz o fim sem outro clique
    expect(regiao).to_contain_text("Pronto. Vagas novas: 2.")
    expect(viva).to_have_text("Pronto. Vagas novas: 2.")
    expect(barra).to_have_attribute("aria-valuenow", "100.0")
    expect(regiao.locator("[hx-trigger]")).to_have_count(0)  # parou de perguntar
    assert chamadas == ["agora"]
    assert erros == []


def test_sair_encerra_o_servidor(page: Page, painel: str, app_painel: FastAPI) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    page.get_by_role("banner").get_by_role("button", name="Sair").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("joBot encerrado")
    assert app_painel.state.servidor.should_exit is True


def test_form_sem_htmx_chega_numa_pagina_que_ja_mostra_o_andamento(
    page: Page,
    painel: str,
    liberar: threading.Event,
    terminou: threading.Event,
    chamadas: list[str],
    app_painel: FastAPI,
) -> None:
    # sem `voltar` o redirect passa pelo "/", que só leva às Vagas (com a barra) depois da
    # primeira execução; antes dela vai ao passo 1 do assistente, que não tem barra (T263)
    with closing(abrir(app_painel.state.banco)) as con:
        gravar_config(con, "primeira_execucao_concluida", True)
    page.clock.install()
    page.goto(f"{painel}/vagas?aba=todas")
    # form comum, sem hx-post (montado por JS): volta por redirect
    with page.expect_navigation():
        page.evaluate(
            """() => {
              const form = document.createElement("form");
              form.method = "post";
              form.action = "/buscar-agora";
              const campo = document.createElement("input");
              campo.type = "hidden";
              campo.name = "csrf_token";
              campo.value = document.querySelector("input[name=csrf_token]").value;
              form.append(campo);
              document.body.append(form);
              form.submit();
            }"""
        )
    regiao = page.locator("#andamento")
    expect(regiao.locator(".progresso-linha")).to_have_text("Preparando as consultas")
    _proxima_pergunta(page, liberar, terminou)
    expect(regiao).to_contain_text("Pronto. Vagas novas: 2.")
    assert chamadas == ["agora"]
