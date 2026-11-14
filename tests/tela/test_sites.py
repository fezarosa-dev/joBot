"""Tela de sites no navegador: adicionar, recusar endereço interno, desativar e remover (T75, T112).

Sem rede de fora: o DNS é trocado por um falso em `app.state.resolvedor` e a rota não baixa a
página; só a tela e o banco são exercitados. A aba Programas das vagas mostra "mudou em <data>".
"""

import re
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from jobot.banco.conexao import abrir
from jobot.banco.paginas import adicionar_pagina, gravar_leitura
from jobot.nucleo.coletores.paginas import Mudanca

pytestmark = pytest.mark.tela

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


async def _dns_publico(host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    """Duas páginas: a Alfa já mudou uma vez, a Beta só foi lida."""
    app_painel.state.resolvedor = _dns_publico
    with closing(abrir(tmp_path / "jobot.db")) as con:
        alfa = adicionar_pagina(con, "https://alfa.exemplo.test/trainee", "Trainee Alfa")
        gravar_leitura(con, alfa, Mudanca("inscrições abertas", "h1", None), AGORA)
        gravar_leitura(
            con,
            alfa,
            Mudanca("inscrições encerradas", "h2", "-inscrições abertas\n+inscrições encerradas"),
            AGORA,
        )
        beta = adicionar_pagina(con, "https://beta.exemplo.test/estagio", "Estágio Beta")
        gravar_leitura(con, beta, Mudanca("sem novidade", "h3", None), AGORA)
    return app_painel


def _cartao(page: Page, nome: str) -> Locator:
    return page.locator("#lista-sites li.cartao").filter(
        has=page.get_by_role("heading", name=nome, exact=True)
    )


def _adicionar(page: Page, nome: str, url: str) -> None:
    page.get_by_label("Nome", exact=True).fill(nome)
    page.get_by_label("Endereço da página").fill(url)
    page.get_by_role("button", name="Adicionar", exact=True).click()


def test_lista_as_paginas_com_estado_e_mudanca(page: Page, painel: str) -> None:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.goto(f"{painel}/sites")

    expect(page.get_by_role("heading", level=1)).to_have_text("Sites")
    expect(page.locator("#lista-sites li.cartao")).to_have_count(2)
    expect(_cartao(page, "Trainee Alfa")).to_contain_text("Mudou em 13/11/2026")
    expect(_cartao(page, "Estágio Beta")).not_to_contain_text("Mudou em")
    assert erros == []


def test_adicionar_pagina_publica_aparece_na_lista(page: Page, painel: str) -> None:
    page.goto(f"{painel}/sites")
    _adicionar(page, "Programa Gama", "https://gama.exemplo.test/vagas")

    expect(page).to_have_url(re.compile(r"/sites$"))
    expect(page.locator("#lista-sites li.cartao")).to_have_count(3)
    expect(_cartao(page, "Programa Gama")).to_contain_text("Ainda não lida")


@pytest.mark.parametrize(
    "endereco", ["http://127.0.0.1:8080/", "http://localhost/", "http://[::1]/"]
)
def test_endereco_interno_mostra_mensagem_e_nao_grava(
    page: Page, painel: str, endereco: str
) -> None:
    page.goto(f"{painel}/sites")
    _adicionar(page, "Meu roteador", endereco)

    expect(page.get_by_role("alert")).to_contain_text("Esse endereço não pode ser acompanhado")
    expect(page.get_by_label("Endereço da página")).to_have_value(endereco)  # o texto volta
    expect(page.locator("#lista-sites li.cartao")).to_have_count(2)


def test_desativar_marca_a_pagina_e_tira_o_botao(page: Page, painel: str) -> None:
    page.goto(f"{painel}/sites")
    _cartao(page, "Estágio Beta").get_by_role("button", name="Desativar").click()

    beta = _cartao(page, "Estágio Beta")
    expect(beta).to_contain_text("Desativada")
    expect(beta.get_by_role("button", name="Desativar")).to_have_count(0)


def test_remover_pede_confirmacao_e_apaga_a_pagina(page: Page, painel: str) -> None:
    page.goto(f"{painel}/sites")
    alfa = _cartao(page, "Trainee Alfa")
    alfa.locator("details.apagar", has_text="Remover").locator("summary").click()
    expect(alfa).to_contain_text("O texto guardado e as mudanças dela serão apagados")
    alfa.get_by_role("button", name="Remover mesmo").click()

    expect(_cartao(page, "Trainee Alfa")).to_have_count(0)
    expect(page.locator("#lista-sites li.cartao")).to_have_count(1)


def test_aba_programas_mostra_mudou_em_e_leva_para_sites(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=programas")

    secao = page.locator("#lista-programas-paginas")
    expect(secao.locator("li.cartao")).to_have_count(2)  # as duas ativas aparecem
    alfa = secao.locator("li.cartao").filter(has_text="Trainee Alfa")
    expect(alfa).to_contain_text("mudou em 13/11/2026")
    alfa.locator("summary").click()
    expect(alfa).to_contain_text("+inscrições encerradas")
    # o CSS de sites.css chega na tela de vagas: linha longa quebra em vez de estourar a largura
    expect(alfa.locator("pre.diferenca")).to_have_css("white-space", "pre-wrap")
    beta = secao.locator("li.cartao").filter(has_text="Estágio Beta")
    expect(beta).not_to_contain_text("mudou em")
    expect(beta).to_contain_text("sem mudança")
    alfa.get_by_role("link", name="Ver em Sites").click()
    expect(page).to_have_url(re.compile(r"/sites#site-\d+$"))


def test_menu_leva_para_a_tela_e_marca_so_ela(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas")
    menu = page.get_by_role("navigation", name="Principal")
    menu.get_by_role("link", name="Sites").click()
    expect(page).to_have_url(re.compile(r"/sites$"))
    expect(menu.locator("[aria-current=page]")).to_have_count(1)
    expect(menu.get_by_role("link", name="Sites")).to_have_attribute("aria-current", "page")
