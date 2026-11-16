"""Barra lateral da casca: seções, `aria-current` no item aberto e a barra (T86, T251)."""

import html as html_
import re
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from starlette.routing import Route

from apoio.relogio import RelogioFalso
from apoio.semear import semear
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.sugeridas import gravar_sugestoes
from jobot.nucleo.coletores.descoberta_cc import Sugestao
from jobot.painel.app import criar_app
from jobot.painel.seguranca import renderizar

PORTA = 47619
ABAS = ("todas", "novas", "fecham_logo", "salvas", "candidatei", "programas", "ocultas")
NOMES_ABAS = {
    "pt": ("Todas", "Novas", "Fecham logo", "Salvas", "Candidatei", "Programas", "Ocultas"),
    "en": ("All", "New", "Closing soon", "Saved", "Applied", "Programs", "Hidden"),
}
DESTAQUES = {"pt": "Destaques de hoje", "en": "Today's Highlights"}
ONDE = {
    "pt": [
        ("Buscas", "/buscas"),
        ("Empresas", "/empresas"),
        ("Fontes", "/fontes"),
        ("Sites", "/sites"),
    ],
    "en": [
        ("Searches", "/buscas"),
        ("Companies", "/empresas"),
        ("Sources", "/fontes"),
        ("Sites", "/sites"),
    ],
}
SUGERIDAS = {"pt": ("Sugeridas", "/empresas/sugeridas"), "en": ("Suggested", "/empresas/sugeridas")}
CONFIG = {
    "pt": ("Configurações", "/configuracoes/geral"),
    "en": ("Settings", "/configuracoes/geral"),
}
MENU = {"pt": "Principal", "en": "Main"}
NAV = re.compile(r"<nav\b[^>]*>.*?</nav>", re.S)
LINK = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.S)
CONTAGEM = re.compile(r'<span class="contagem">(\d+)</span>')
DESTAQUE_HREF = "/vagas?aba=destaques"


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    caminho = tmp_path / "jobot.db"
    with closing(abrir(caminho)) as con:
        migrar(con, caminho)
    return caminho


@pytest.fixture
def cliente(banco: Path) -> TestClient:
    app = criar_app(banco.parent, PORTA)

    async def pagina(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    # a casca em caminhos que ainda não têm tela (e em "/", que redireciona): vão na frente
    for caminho in ("/", "/buscas", "/configuracoes/ia", "/vagasx", "/vagas/1/x"):
        app.router.routes.insert(0, Route(caminho, pagina))
    return TestClient(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)


def _sugerir(banco: Path) -> None:
    with closing(abrir(banco)) as con:
        con.execute("INSERT INTO fonte (chave, leva, intervalo_min) VALUES ('lever', 'A', 60)")
        gravar_sugestoes(
            con, [Sugestao("lever", "pendente-a", "https://exemplo.test/a")], datetime.now(UTC)
        )


def _menu(html: str, idioma: str) -> list[tuple[str, str, str]]:
    """Os links do `<nav>` principal: (texto, href, valor do aria-current ou "")."""
    navs = [n for n in NAV.findall(html) if f'aria-label="{MENU[idioma]}"' in n]
    assert len(navs) == 1, f"nav principal ({MENU[idioma]}) não achado"
    itens = []
    for atributos, texto in LINK.findall(navs[0]):
        href = re.search(r'href="([^"]*)"', atributos)
        assert href is not None
        atual = re.search(r'aria-current="([^"]*)"', atributos)
        nome = html_.unescape(CONTAGEM.sub("", texto)).strip()  # a contagem é do `_contagens`
        itens.append((nome, href.group(1), atual.group(1) if atual else ""))
    return itens


def _contagens(html: str, idioma: str = "pt") -> dict[str, int]:
    """Por href (com `&amp;` desfeito), a contagem à direita de cada link do `<nav>` principal."""
    navs = [n for n in NAV.findall(html) if f'aria-label="{MENU[idioma]}"' in n]
    assert len(navs) == 1
    achadas = {}
    for atributos, texto in LINK.findall(navs[0]):
        href = re.search(r'href="([^"]*)"', atributos)
        numero = CONTAGEM.search(texto)
        assert href is not None
        achadas[html_.unescape(href.group(1))] = int(numero.group(1)) if numero else 0
    return achadas


def _esperado(idioma: str, *, destaques: bool, sugeridas: bool) -> list[tuple[str, str]]:
    vagas = [(DESTAQUES[idioma], DESTAQUE_HREF)] if destaques else []
    vagas += [(n, f"/vagas?aba={a}") for n, a in zip(NOMES_ABAS[idioma], ABAS, strict=True)]
    onde = list(ONDE[idioma])
    if sugeridas:
        onde.insert(2, SUGERIDAS[idioma])  # segundo nível, logo abaixo de Empresas
    return [*vagas, *onde, CONFIG[idioma]]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_menu_tem_os_itens_da_lateral_pt_e_en(cliente: TestClient, idioma: str) -> None:
    resposta = cliente.get("/vagas", headers={"Accept-Language": idioma})
    assert resposta.status_code == 200
    itens = [(texto, href) for texto, href, _ in _menu(resposta.text, idioma)]
    assert itens == _esperado(idioma, destaques=True, sugeridas=False)
    assert len([h for _, h in itens if h.startswith("/vagas?")]) == 8
    for titulo in {"pt": ("Vagas", "Onde buscar"), "en": ("Jobs", "Where to Look")}[idioma]:
        assert f">{titulo}<" in resposta.text


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_sugeridas_so_com_sugestao_pendente(cliente: TestClient, banco: Path, idioma: str) -> None:
    _sugerir(banco)
    resposta = cliente.get("/fontes", headers={"Accept-Language": idioma})
    itens = [(texto, href) for texto, href, _ in _menu(resposta.text, idioma)]
    assert itens == _esperado(idioma, destaques=True, sugeridas=True)


def test_sem_destaques_a_lateral_tira_o_item(cliente: TestClient, banco: Path) -> None:
    with closing(abrir(banco)) as con:
        gravar_config(con, "destaques_ligados", False)
    itens = _menu(cliente.get("/vagas").text, "pt")
    assert [(t, h) for t, h, _ in itens] == _esperado("pt", destaques=False, sugeridas=False)
    assert [h for _, h, atual in itens if atual] == ["/vagas?aba=todas"]


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize(
    ("caminho", "href", "valor"),
    [
        ("/", DESTAQUE_HREF, "page"),
        ("/vagas", DESTAQUE_HREF, "page"),
        ("/vagas?aba=salvas", "/vagas?aba=salvas", "page"),
        ("/vagas?aba=xyz", DESTAQUE_HREF, "page"),
        # página filha (detalhe): o item marca a área, mas não é a página aberta
        ("/vagas/1/x", DESTAQUE_HREF, "true"),
        ("/buscas", "/buscas", "page"),
        ("/empresas", "/empresas", "page"),
        ("/empresas/sugeridas", "/empresas", "true"),  # sem pendente o item some; a área é Empresas
        ("/configuracoes/geral", "/configuracoes/geral", "page"),
        ("/configuracoes/ia", "/configuracoes/geral", "true"),
        ("/vagasx", None, None),
    ],
)
def test_aria_current_so_no_item_da_area(
    cliente: TestClient, idioma: str, caminho: str, href: str | None, valor: str | None
) -> None:
    resposta = cliente.get(caminho, headers={"Accept-Language": idioma})
    assert resposta.status_code == 200
    marcados = [(h, atual) for _, h, atual in _menu(resposta.text, idioma) if atual]
    assert marcados == ([] if href is None else [(href, valor)])


def test_aria_current_em_sugeridas_com_pendente(cliente: TestClient, banco: Path) -> None:
    _sugerir(banco)
    menu = _menu(cliente.get("/empresas/sugeridas").text, "pt")
    assert [(h, atual) for _, h, atual in menu if atual] == [("/empresas/sugeridas", "page")]


def _corpo(html: str) -> str:
    return html[html.index("<body") :]


def test_lateral_antes_do_banner(cliente: TestClient) -> None:
    corpo = _corpo(cliente.get("/vagas").text)
    assert re.search(r'<aside\b[^>]*class="lateral vidro"', corpo)
    assert re.search(r'<header\b[^>]*class="topo vidro"', corpo)
    aside, header = corpo.index("<aside"), corpo.index("<header")
    assert aside < header
    # o header é filho do body: o aside fecha antes dele, e nada o envolve
    assert corpo.index("</aside>") < header
    antes = corpo[:header]
    assert antes.count("<div") == antes.count("</div>")
    assert antes.count("<main") == 0
    assert re.search(r'<header\b[^>]*class="topo vidro"[^>]*>', corpo)


def test_busca_na_barra_so_em_vagas(cliente: TestClient) -> None:
    html = cliente.get("/vagas").text
    header = html[html.index("<header") : html.index("</header>")]
    campo = re.search(r'<input\b[^>]*\bform="busca"[^>]*>', header)
    assert campo is not None
    assert 'type="search"' in campo.group(0) and 'name="q"' in campo.group(0)
    assert re.search(r'<form\b[^>]*\bid="busca"', html)
    assert html.count('name="q"') == 1, "um campo q só, o da barra"
    assert 'form="busca"' not in cliente.get("/buscas").text
    assert 'form="busca"' not in cliente.get("/fontes").text


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_campo_da_busca_tem_rotulo_e_dica(cliente: TestClient, idioma: str) -> None:
    html = cliente.get("/vagas", headers={"Accept-Language": idioma}).text
    campo = re.search(r'<input\b[^>]*\bform="busca"[^>]*>', html)
    assert campo is not None
    rotulo = {"pt": "Buscar em Vagas", "en": "Search Jobs"}[idioma]
    dica = {"pt": "Focar a busca (/)", "en": "Focus Search (/)"}[idioma]
    assert f'placeholder="{rotulo}"' in campo.group(0)
    assert f'aria-label="{rotulo}"' in campo.group(0)
    assert f'title="{dica}"' in campo.group(0)


def test_sem_tema_nem_idioma_na_barra(cliente: TestClient) -> None:
    html = cliente.get("/vagas").text
    header = html[html.index("<header") : html.index("</header>")]
    assert 'name="tema"' not in html
    assert 'name="idioma"' not in html
    assert "/preferencias/" not in header
    assert "Preferências" not in html


def test_assistente_sem_lateral(cliente: TestClient) -> None:
    """Guarda (mutante: tirar `{% set sem_lateral = true %}` de `primeira_execucao/pagina.html`)."""
    resposta = cliente.get("/primeira-execucao/1")
    assert resposta.status_code == 200
    assert "<aside" not in resposta.text
    assert "<header" in resposta.text  # a barra continua: Buscar agora e Sair valem no assistente


@pytest.mark.parametrize(
    ("caminho", "titulo"),
    [("/vagas", "Vagas"), ("/fontes", "Fontes"), ("/empresas", "Empresas")],
)
def test_titulo_da_secao_na_barra(cliente: TestClient, caminho: str, titulo: str) -> None:
    html = cliente.get(caminho).text
    header = html[html.index("<header") : html.index("</header>")]
    assert re.search(rf'class="topo-titulo"[^>]*>{titulo}<', header)


def test_botao_de_recolher_e_divisor(cliente: TestClient) -> None:
    html = cliente.get("/vagas").text
    botao = re.search(r"<button\b[^>]*\bdata-recolher\b[^>]*>", html)
    assert botao is not None
    assert 'aria-expanded="true"' in botao.group(0)
    assert 'aria-label="Recolher barra lateral"' in botao.group(0)
    assert 'data-mostrar="Mostrar barra lateral"' in botao.group(0)
    divisor = re.search(r'<div\b[^>]*role="separator"[^>]*>', html)
    assert divisor is not None
    for atributo in (
        'aria-orientation="vertical"',
        'aria-valuemin="180"',
        'aria-valuemax="320"',
        'aria-valuenow="240"',
        'tabindex="0"',
        'aria-label="Largura da barra lateral"',
    ):
        assert atributo in divisor.group(0), atributo


def test_faixas_na_ordem_logo_abaixo_da_barra(cliente: TestClient) -> None:
    corpo = _corpo(cliente.get("/vagas").text)
    fim_da_barra = corpo.index("</header>")
    posicoes = [
        corpo.index(marca)
        for marca in (
            'id="aviso-erro"',
            'id="aviso-versao"',
            'id="faixa-contas"',
            'id="faixa-desfazer"',
        )
    ]
    assert fim_da_barra < posicoes[0] < posicoes[1] < posicoes[2] < posicoes[3]
    assert posicoes[3] < corpo.index('<main id="conteudo"')
    desfazer = re.search(r'<div\b[^>]*id="faixa-desfazer"[^>]*>', corpo)
    assert desfazer is not None and 'role="status"' in desfazer.group(0)


def _com_vagas(banco: Path) -> tuple[TestClient, int]:
    """O app sobre um banco semeado, com o relógio parado em `AGORA`; devolve também a busca."""
    with closing(abrir(banco)) as con:
        busca = semear(con)["busca"]
    app = criar_app(banco.parent, PORTA)
    app.state.relogio = RelogioFalso()

    async def pagina(request: Request) -> HTMLResponse:
        return renderizar(request, "base.html")

    app.router.routes.insert(0, Route("/buscas", pagina))
    return TestClient(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False), busca


def test_lateral_conta_fora_de_vagas(banco: Path) -> None:
    """Em `/buscas` a lateral traz a contagem de cada aba e a de Destaques; o zero some."""
    cliente, busca = _com_vagas(banco)
    html = cliente.get("/buscas").text
    contagens = _contagens(html)
    esperadas = {
        "destaques": 1,
        "todas": 7,
        "novas": 1,
        "fecham_logo": 1,
        "salvas": 1,
        "candidatei": 0,
        "programas": 1,
        "ocultas": 2,
    }
    assert {h: n for h, n in contagens.items() if h.startswith("/vagas")} == {
        f"/vagas?aba={aba}&busca={busca}": n for aba, n in esperadas.items()
    }
    # o zero some: "Candidatei" não leva o span da contagem; os outros sete levam
    assert html.count('class="contagem"') == 7
    # as seções que não são de vagas ficam sem contagem
    assert contagens["/buscas"] == contagens["/fontes"] == 0


def test_sem_destaques_ligados_a_lateral_nao_conta_destaques(banco: Path) -> None:
    """Guarda: Destaques desligado tira o item e a conta (mutante: contar sempre)."""
    cliente, _ = _com_vagas(banco)
    with closing(abrir(banco)) as con:
        gravar_config(con, "destaques_ligados", False)
    contagens = _contagens(cliente.get("/buscas").text)
    assert not [h for h in contagens if "aba=destaques" in h]
