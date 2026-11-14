"""Troca rápida de tema e idioma na casca (desenho 13.2; plano T36)."""

import json
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47615


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
