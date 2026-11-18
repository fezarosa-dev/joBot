"""O painel é um site comum (T351; D206, ADR 0027): nada dele depende de estar na janela da casca.

Saíram a marca da casca no user agent virando `data-casca`, a fileira de três círculos, o arraste
da janela e o fechar pela ponte do Tauri. Com a marca no user agent, a página sai igual.
"""

import json
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
from jobot.painel import globais
from jobot.painel.app import ESTATICOS, criar_app
from jobot.painel.seguranca import renderizar

PORTA = 47620
NAVEGADOR = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko)"
I18N = Path(globais.__file__).parent / "i18n"
# o que só existia para a janela da casca, procurado no HTML, no CSS e no JS do painel
RESTOS = ("data-casca", "janela-botoes", "data-janela-acao", "dataset.casca", "--janela-")
RESTOS_JS = ("__TAURI__", "startDragging", "toggleMaximize", "getCurrentWindow")


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

    app.router.routes.insert(0, Route("/_pagina", pagina))
    app.router.routes.insert(0, Route("/_sem_lateral", sem_lateral))
    return TestClient(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)


def _html(cliente: TestClient, caminho: str, agente: str) -> str:
    resposta = cliente.get(caminho, headers={"user-agent": agente})
    assert resposta.status_code == 200
    texto: str = resposta.text
    return texto


@pytest.mark.parametrize("caminho", ["/_pagina", "/_sem_lateral"])
@pytest.mark.parametrize("so", ["linux", "windows", "macos"])
def test_marca_no_user_agent_nao_muda_a_pagina(cliente: TestClient, caminho: str, so: str) -> None:
    comum = _html(cliente, caminho, NAVEGADOR)
    marcada = _html(cliente, caminho, f"{NAVEGADOR} joBot-casca/0.4.0 ({so})")
    assert "joBot" in comum  # controle: a página veio inteira
    assert marcada == comum
    assert [resto for resto in RESTOS if resto in marcada] == []


def test_css_e_js_sem_a_janela_da_casca() -> None:
    achados = []
    for arquivo in sorted([*ESTATICOS.glob("css/*.css"), *ESTATICOS.glob("js/*.js")]):
        texto = arquivo.read_text(encoding="utf-8")
        restos = RESTOS + RESTOS_JS if arquivo.suffix == ".js" else RESTOS
        achados += [f"{arquivo.name}: {resto}" for resto in restos if resto in texto]
    assert achados == []


def test_sem_marca_da_casca_nos_globais_nem_textos_da_janela() -> None:
    assert not hasattr(globais, "marca_da_casca")
    for idioma in ("pt", "en"):
        catalogo = json.loads((I18N / idioma / "casca.json").read_text(encoding="utf-8"))
        assert "casca.pular" in catalogo  # controle: o catálogo certo
        assert [chave for chave in catalogo if chave.startswith("casca.janela.")] == []
