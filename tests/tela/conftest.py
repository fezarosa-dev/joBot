"""Fixtures das telas: painel real em porta livre e guarda de rede no navegador (plano T36)."""

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import BrowserContext, Route

from apoio.semear import semear
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app

LOCAL = "127.0.0.1"


@pytest.fixture
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    # idioma fixo: o painel escolhe o idioma inicial pelo Accept-Language
    return {**browser_context_args, "locale": "pt-BR"}


@pytest.fixture
def porta() -> int:
    with socket.socket() as s:
        s.bind((LOCAL, 0))
        return int(s.getsockname()[1])


@pytest.fixture
def app_painel(tmp_path: Path, porta: int) -> FastAPI:
    """App real sobre um banco semeado; o módulo de teste pode sobrescrever e somar rotas."""
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        semear(con)
    return criar_app(tmp_path, porta)


@pytest.fixture
def painel(app_painel: FastAPI, porta: int) -> Iterator[str]:
    """Sobe o painel numa thread, só em 127.0.0.1, e devolve o endereço base."""
    config = uvicorn.Config(
        app_painel,
        host=LOCAL,
        port=porta,
        log_level="warning",
        server_header=False,
        proxy_headers=False,
        lifespan="off",
    )
    servidor = uvicorn.Server(config)
    linha = threading.Thread(target=servidor.run, daemon=True)
    linha.start()
    limite = time.monotonic() + 10
    while not servidor.started:
        assert linha.is_alive() and time.monotonic() < limite, "o painel não subiu"
        time.sleep(0.05)
    yield f"http://{LOCAL}:{porta}"
    servidor.should_exit = True
    linha.join(10)


@pytest.fixture(autouse=True)
def _so_127(context: BrowserContext) -> Iterator[list[str]]:
    """Todo pedido do navegador para fora de 127.0.0.1 é barrado e faz o teste falhar."""
    fora: list[str] = []

    def filtrar(route: Route) -> None:
        if urlsplit(route.request.url).hostname == LOCAL:
            route.continue_()
        else:
            fora.append(route.request.url)
            route.abort()

    context.route("**/*", filtrar)
    yield fora
    assert fora == [], f"pedido para fora de {LOCAL}: {fora}"
