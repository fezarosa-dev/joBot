"""O painel dentro da casca (T334; desenho 5.3): marca no user agent, `data-casca` e a fileira."""

import re
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from starlette.routing import Route

from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.globais import marca_da_casca
from jobot.painel.seguranca import renderizar

PORTA = 47620
NAVEGADOR = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko)"
NOMES = {"pt": ["Fechar", "Minimizar", "Maximizar"], "en": ["Close", "Minimize", "Maximize"]}


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        gravar_config(con, "primeira_execucao_concluida", True)
    app = criar_app(tmp_path, PORTA)

    async def pagina(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    async def sem_lateral(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html", sem_lateral=True)

    app.router.routes.insert(0, Route("/_casca", pagina))
    app.router.routes.insert(0, Route("/_sem_lateral", sem_lateral))
    return TestClient(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)


def _html(cliente: TestClient, agente: str, caminho: str = "/_casca", idioma: str = "pt") -> str:
    resposta = cliente.get(caminho, headers={"user-agent": agente, "accept-language": idioma})
    assert resposta.status_code == 200
    texto: str = resposta.text
    return texto


def _raiz(html: str) -> str:
    achado = re.search(r"<html[^>]*>", html)
    assert achado
    return achado.group(0)


def _fileira(html: str) -> list[str]:
    bloco = re.search(r"<div[^>]*data-janela-botoes[^>]*>(.*?)</div>", html, re.S)
    if bloco is None:
        return []
    return re.findall(r'<button[^>]*aria-label="([^"]+)"', bloco.group(1))


@pytest.mark.parametrize(
    ("agente", "esperado"),
    [
        (f"{NAVEGADOR} joBot-casca/0.4.0 (linux)", ("0.4.0", "linux")),
        (f"{NAVEGADOR} joBot-casca/0.4.0 (windows)", ("0.4.0", "windows")),
        (f"{NAVEGADOR} joBot-casca/1.12.3 (macos)", ("1.12.3", "macos")),
        (NAVEGADOR, None),
        ("", None),
        (None, None),
        (f"{NAVEGADOR} joBot-casca/0.4.0 (beos)", None),
        (f"{NAVEGADOR} joBot-casca/x (linux)", None),
        (f"{NAVEGADOR}joBot-casca/0.4.0 (linux)", None),
    ],
)
def test_marca_da_casca(agente: str | None, esperado: tuple[str, str] | None) -> None:
    assert marca_da_casca(agente) == esperado


@pytest.mark.parametrize("so", ["linux", "windows"])
@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_linux_e_windows_tem_a_fileira(cliente: TestClient, so: str, idioma: str) -> None:
    html = _html(cliente, f"{NAVEGADOR} joBot-casca/0.4.0 ({so})", idioma=idioma)
    assert f'data-casca="{so}"' in _raiz(html)
    assert _fileira(html) == NOMES[idioma]
    # o rótulo de restaurar vai num data-, para o app.js trocar quando a janela maximiza
    assert ("Restaurar" if idioma == "pt" else "Restore") in html


def test_fileira_tambem_sem_lateral(cliente: TestClient) -> None:
    """O assistente não tem lateral; a janela continua com como fechar."""
    html = _html(cliente, f"{NAVEGADOR} joBot-casca/0.4.0 (linux)", "/_sem_lateral")
    assert 'data-casca="linux"' in _raiz(html)
    assert _fileira(html) == NOMES["pt"]


def test_mac_sem_fileira(cliente: TestClient) -> None:
    html = _html(cliente, f"{NAVEGADOR} joBot-casca/0.4.0 (macos)")
    assert 'data-casca="macos"' in _raiz(html)
    assert "data-janela-botoes" not in html


@pytest.mark.parametrize("agente", [NAVEGADOR, f"{NAVEGADOR} joBot-casca/0.4.0 (beos)"])
def test_sem_a_marca_nada_muda(cliente: TestClient, agente: str) -> None:
    html = _html(cliente, agente)
    assert "data-casca" not in html
    assert "data-janela-botoes" not in html
