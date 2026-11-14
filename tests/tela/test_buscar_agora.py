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

from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao
from jobot.painel.rotas import execucao as rota

pytestmark = pytest.mark.tela


@pytest.fixture
def liberar() -> threading.Event:
    return threading.Event()


@pytest.fixture
def chamadas() -> list[str]:
    return []


@pytest.fixture
def app_painel(
    app_painel: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    liberar: threading.Event,
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
        return id_

    monkeypatch.setattr(rota, "executar_busca", falsa)
    return app_painel


def test_buscar_agora_mostra_o_andamento_e_as_vagas_novas(
    page: Page, painel: str, liberar: threading.Event, chamadas: list[str]
) -> None:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.goto(f"{painel}/vagas?aba=todas")
    regiao = page.get_by_role("status", name="Andamento da busca")
    expect(regiao).to_have_attribute("aria-live", "polite")

    botao = page.get_by_role("banner").get_by_role("button", name="Buscar agora")
    botao.click()
    expect(regiao).to_contain_text("Buscando vagas")
    # outro clique com a busca rodando não dispara outra: avisa e mostra a que roda
    botao.click()
    expect(regiao).to_contain_text("Uma busca já está rodando")
    assert chamadas == ["agora"]

    liberar.set()  # a pergunta de 2 em 2 s traz o fim sem outro clique
    expect(regiao).to_contain_text("Busca concluída. Vagas novas: 2.", timeout=10_000)
    expect(regiao.locator("[hx-trigger]")).to_have_count(0)  # parou de perguntar
    assert chamadas == ["agora"]
    assert erros == []


def test_sair_encerra_o_servidor(page: Page, painel: str, app_painel: FastAPI) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    page.get_by_role("banner").get_by_role("button", name="Sair").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("joBot encerrado")
    assert app_painel.state.servidor.should_exit is True


def test_form_sem_htmx_chega_numa_pagina_que_ja_mostra_o_andamento(
    page: Page, painel: str, liberar: threading.Event, chamadas: list[str]
) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    # o form comum do fim da primeira execução (pronto.html): sem hx-post, volta por redirect
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
    regiao = page.get_by_role("status", name="Andamento da busca")
    expect(regiao).to_contain_text("Buscando vagas")
    liberar.set()
    expect(regiao).to_contain_text("Busca concluída. Vagas novas: 2.", timeout=10_000)
    assert chamadas == ["agora"]
