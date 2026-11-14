"""Troca rápida de tema e idioma na casca (desenho 13.2; plano T36)."""

import json
import re
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from jinja2 import DictLoader

from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF, TEMPLATES, renderizar

PORTA = 47615
GLOBAIS = (
    "salario_texto",
    "locais_texto",
    "data_curta",
    "data_completa",
    "rotulo",
    "motivo",
    "dinheiro",
)


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
    app = criar_app(tmp_path, PORTA)
    return TestClient(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)


def _token(cliente: TestClient) -> str:
    app = cliente.app
    token: str = app.state.csrf  # type: ignore[attr-defined]
    return token


def _config(cliente: TestClient, chave: str) -> object:
    banco: Path = cliente.app.state.banco  # type: ignore[attr-defined]
    with closing(abrir(banco)) as con:
        linha = con.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return None if linha is None else json.loads(linha[0])


@pytest.mark.parametrize(
    ("rota", "campo", "valor"), [("tema", "tema", "escuro"), ("idioma", "idioma", "en")]
)
def test_grava_e_volta_para_a_pagina(
    cliente: TestClient, rota: str, campo: str, valor: str
) -> None:
    dados = {CAMPO_CSRF: _token(cliente), campo: valor, "voltar": "/vagas?aba=todas"}
    resposta = cliente.post(f"/preferencias/{rota}", data=dados)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/vagas?aba=todas"
    assert _config(cliente, campo) == valor
    # gravar de novo atualiza a mesma chave
    outro = "claro" if campo == "tema" else "pt"
    cliente.post(f"/preferencias/{rota}", data=dados | {campo: outro})
    assert _config(cliente, campo) == outro


@pytest.mark.parametrize("rota", ["tema", "idioma"])
def test_sem_csrf_403(cliente: TestClient, rota: str) -> None:
    resposta = cliente.post(f"/preferencias/{rota}", data={rota: "en", "voltar": "/"})
    assert resposta.status_code == 403
    assert _config(cliente, rota) is None


@pytest.mark.parametrize(("rota", "valor"), [("tema", "roxo"), ("idioma", "fr")])
def test_valor_fora_da_lista_nao_grava(cliente: TestClient, rota: str, valor: str) -> None:
    resposta = cliente.post(
        f"/preferencias/{rota}", data={CAMPO_CSRF: _token(cliente), rota: valor}
    )
    assert resposta.status_code == 422
    assert _config(cliente, rota) is None


@pytest.mark.parametrize(
    "voltar",
    ["https://evil.com/", "//evil.com/x", "/\t/evil.com", "javascript:alert(1)", "vagas", ""],
)
def test_voltar_so_para_o_proprio_painel(cliente: TestClient, voltar: str) -> None:
    dados = {CAMPO_CSRF: _token(cliente), "tema": "claro", "voltar": voltar}
    resposta = cliente.post("/preferencias/tema", data=dados)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def _data_tema(cliente: TestClient) -> str | None:
    achou = re.search(r"<html[^>]*\bdata-tema=\"([^\"]*)\"", cliente.get("/vagas").text)
    return achou.group(1) if achou else None


def test_tema_chega_ao_base_sem_global_do_jinja(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `criar_app` já importou `rotas/preferencias.py`: importar a rota não registra mais global
    assert "tema" not in TEMPLATES.env.globals
    assert _data_tema(cliente) == "sistema"  # sem tema salvo, segue o `prefers-color-scheme`
    dados = {CAMPO_CSRF: _token(cliente), "tema": "escuro", "voltar": "/"}
    assert cliente.post("/preferencias/tema", data=dados).status_code == 303
    assert _data_tema(cliente) == "escuro"  # o tema salvo continua em `<html data-tema>`

    # `renderizar` passa o tema no contexto do template
    monkeypatch.setattr(TEMPLATES.env, "loader", DictLoader({"t82.html": "{{ tema }}"}))

    @cast(FastAPI, cliente.app).get("/t82-tema")
    async def pagina(request: Request) -> HTMLResponse:
        return renderizar(request, "t82.html")

    assert cliente.get("/t82-tema").text == "escuro"


def test_globais_do_jinja_vem_do_modulo_explicito(cliente: TestClient) -> None:
    # `criar_app` já importou as rotas; os globais são de `painel/globais.py`, não delas
    globais = TEMPLATES.env.globals
    assert set(GLOBAIS) <= globais.keys()
    assert "tema" not in globais
    assert {globais["rotulo"].__module__, globais["motivo"].__module__} == {"jobot.painel.globais"}


_SO_TEMPLATES = """
import json, sys
from jobot.painel.seguranca import TEMPLATES
print(json.dumps({
    "globais": sorted(TEMPLATES.env.globals),
    "rotas": sorted(m for m in sys.modules if m.startswith("jobot.painel.rotas")),
}))
"""


def test_globais_do_jinja_sem_importar_as_rotas() -> None:
    # processo novo: só o módulo dos templates, nenhuma rota importada
    saida = subprocess.run(
        [sys.executable, "-c", _SO_TEMPLATES], capture_output=True, text=True, check=True
    ).stdout
    lido = json.loads(saida)
    assert lido["rotas"] == []
    assert set(GLOBAIS) <= set(lido["globais"])
    assert "tema" not in lido["globais"]
