"""Menu principal da casca: sete áreas e `aria-current` na área aberta (decisão 22; T86)."""

import re
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from starlette.routing import Route

from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.seguranca import renderizar

PORTA = 47619
LINKS = {
    "pt": {
        "Vagas": "/vagas",
        "Buscas": "/buscas",
        "Fontes": "/fontes",
        "Empresas": "/empresas",
        "Sugeridas": "/empresas/sugeridas",
        "Sites": "/sites",
        "Configurações": "/configuracoes/fontes",
    },
    "en": {
        "Jobs": "/vagas",
        "Searches": "/buscas",
        "Sources": "/fontes",
        "Companies": "/empresas",
        "Suggested": "/empresas/sugeridas",
        "Sites": "/sites",
        "Settings": "/configuracoes/fontes",
    },
}
MENU = {"pt": "Principal", "en": "Main"}
NAV = re.compile(r"<nav\b[^>]*>.*?</nav>", re.S)
LINK = re.compile(r"<a\b([^>]*)>([^<]*)</a>")


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
    app = criar_app(tmp_path, PORTA)

    async def pagina(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    # a casca em caminhos que ainda não têm tela (e em "/", que redireciona): vão na frente
    for caminho in ("/", "/buscas", "/configuracoes/ia", "/vagasx", "/vagas/1/x"):
        app.router.routes.insert(0, Route(caminho, pagina))
    return TestClient(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)


def _menu(html: str, idioma: str) -> list[tuple[str, str, bool]]:
    """Os links do `<nav>` principal: (texto, href, marcado com aria-current="page")."""
    navs = [n for n in NAV.findall(html) if f'aria-label="{MENU[idioma]}"' in n]
    assert len(navs) == 1, f"nav principal ({MENU[idioma]}) não achado"
    itens = []
    for atributos, texto in LINK.findall(navs[0]):
        href = re.search(r'href="([^"]*)"', atributos)
        assert href is not None
        itens.append((texto, href.group(1), 'aria-current="page"' in atributos))
    return itens


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_menu_tem_sete_links_pt_e_en(cliente: TestClient, idioma: str) -> None:
    resposta = cliente.get("/vagas", headers={"Accept-Language": idioma})
    assert resposta.status_code == 200
    itens = _menu(resposta.text, idioma)
    assert {texto: href for texto, href, _ in itens} == LINKS[idioma]
    assert len(itens) == 7


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize(
    ("caminho", "href"),
    [
        ("/", "/vagas"),
        ("/vagas", "/vagas"),
        ("/vagas/1/x", "/vagas"),
        ("/buscas", "/buscas"),
        ("/empresas", "/empresas"),
        ("/empresas/sugeridas", "/empresas/sugeridas"),
        ("/configuracoes/ia", "/configuracoes/fontes"),
        ("/vagasx", None),
    ],
)
def test_aria_current_so_no_item_da_area(
    cliente: TestClient, idioma: str, caminho: str, href: str | None
) -> None:
    resposta = cliente.get(caminho, headers={"Accept-Language": idioma})
    assert resposta.status_code == 200
    marcados = [h for _, h, atual in _menu(resposta.text, idioma) if atual]
    assert marcados == ([] if href is None else [href])
