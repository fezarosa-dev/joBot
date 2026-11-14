"""Link "Apoie o projeto" no rodapé da casca (plano T87; ADR 0020, ADR 0014).

Link comum, aberto só por clique: sem rastreio, sem script, sem pop-up. Nenhuma rota nova.
"""

import re
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.quebra import URL_REPOSITORIO
from jobot.painel.app import criar_app

PORTA = 47629
URL_PT = "https://github.com/fezarosa-dev/joBot/wiki/Apoie"
URL_EN = "https://github.com/fezarosa-dev/joBot/wiki/Support-the-project"
TEXTO = {"pt": "Apoie o projeto", "en": "Support the project"}
URL = {"pt": URL_PT, "en": URL_EN}
RODAPE = re.compile(r"<footer\b[^>]*>(.*?)</footer>", re.S)
ANCORA = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.S)


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
    return TestClient(criar_app(tmp_path, PORTA), base_url=f"http://127.0.0.1:{PORTA}")


def _link(html: str, texto: str) -> str:
    rodape = RODAPE.search(html)
    assert rodape is not None, "a casca não tem <footer>"
    achados = [attrs for attrs, interno in ANCORA.findall(rodape.group(1)) if texto in interno]
    assert len(achados) == 1, f"link {texto!r} no rodapé: {achados}"
    return str(achados[0])


def _href(atributos: str) -> str:
    achou = re.search(r'\bhref="([^"]*)"', atributos)
    assert achou is not None
    return achou.group(1)


def test_rodape_tem_o_link_apoie_em_pt(cliente: TestClient) -> None:
    html = cliente.get("/vagas", headers={"Accept-Language": "pt-BR"}).text
    assert _href(_link(html, "Apoie o projeto")) == URL_PT


def test_rodape_tem_o_link_apoie_em_en(cliente: TestClient) -> None:
    html = cliente.get("/vagas", headers={"Accept-Language": "en-US"}).text
    assert _href(_link(html, "Support the project")) == URL_EN


def test_link_apoie_sem_rastreio(cliente: TestClient) -> None:
    for idioma in ("pt", "en"):
        html = cliente.get("/vagas", headers={"Accept-Language": idioma}).text
        atributos = _link(html, TEXTO[idioma])
        href = _href(atributos)
        assert href == URL[idioma]
        assert "?" not in href and "#" not in href
        rel = re.search(r'\brel="([^"]*)"', atributos)
        assert rel is not None
        assert {"noopener", "noreferrer"} <= set(rel.group(1).split())
        assert "ping" not in atributos
        assert "onclick" not in atributos
        assert "<dialog" not in html
        assert 'role="dialog"' not in html
        assert "popover" not in html


@pytest.mark.parametrize("rota", ["/vagas", "/buscas", "/fontes"])
def test_apoie_aparece_nas_paginas_da_casca(cliente: TestClient, rota: str) -> None:
    resposta = cliente.get(rota, headers={"Accept-Language": "pt"})
    assert resposta.status_code == 200
    assert _href(_link(resposta.text, "Apoie o projeto")) == URL_PT


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_apoie_url_e_do_repositorio_do_projeto(cliente: TestClient, idioma: str) -> None:
    html = cliente.get("/vagas", headers={"Accept-Language": idioma}).text
    assert _href(_link(html, TEXTO[idioma])).startswith(f"{URL_REPOSITORIO}/wiki/")


def test_aviso_de_versao_fica_antes_do_conteudo_e_o_rodape_depois(cliente: TestClient) -> None:
    html = cliente.get("/vagas").text
    assert html.index('id="aviso-versao"') < html.index("<main") < html.index("<footer")
