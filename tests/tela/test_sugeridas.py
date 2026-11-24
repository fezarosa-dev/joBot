"""Tela de empresas sugeridas no navegador: lista, aprovar uma a uma e descartar (T74).

Sem rede de fora: a aprovação de Greenhouse não faz pedido, e o painel usa o
`httpx.MockTransport` de `app.state.transporte` para o resto.
"""

import re
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.console import anotar_erros
from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import adicionar_empresa, remover_empresa
from jobot.banco.conexao import abrir
from jobot.banco.sugeridas import gravar_sugestoes
from jobot.nucleo.coletores.descoberta_cc import Sugestao
from jobot.nucleo.modelo import Empresa

pytestmark = pytest.mark.tela

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
FAIXA = "#faixa-desfazer"


def _sem_rede(pedido: httpx.Request) -> httpx.Response:
    raise AssertionError(f"teste não fala com {pedido.url}")


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    """Três sugestões pendentes; a do Vitta é de uma empresa que a pessoa já removeu (D71)."""
    app_painel.state.relogio = RelogioFalso(AGORA)
    app_painel.state.transporte = httpx.MockTransport(_sem_rede)
    with closing(abrir(tmp_path / "jobot.db")) as con:
        con.execute("INSERT INTO fonte (chave, leva) VALUES ('greenhouse', 'A')")
        con.commit()
        gravar_sugestoes(
            con,
            [
                Sugestao("greenhouse", "alfa", "https://boards.greenhouse.io/alfa"),
                Sugestao("greenhouse", "beta", "https://boards.greenhouse.io/beta"),
                Sugestao("greenhouse", "vitta", "https://boards.greenhouse.io/vitta"),
            ],
            AGORA,
        )
        id_ = adicionar_empresa(
            con, Empresa(nome="Vitta", fonte="greenhouse", identificador="vitta", origem="pessoa")
        )
        remover_empresa(con, id_, AGORA)
    return app_painel


def _cartao(page: Page, nome: str) -> Locator:
    return page.locator("#lista-sugeridas li.linha-busca").filter(
        has=page.get_by_role("heading", name=nome, exact=True)
    )


def test_lista_as_pendentes_e_avisa_da_removida(page: Page, painel: str) -> None:
    erros = anotar_erros(page)  # violação do CSP aparece como erro no console
    page.goto(f"{painel}/empresas/sugeridas")

    expect(page.get_by_role("heading", level=1)).to_have_text("Empresas sugeridas")
    expect(page.locator("#lista-sugeridas li.linha-busca")).to_have_count(3)
    expect(_cartao(page, "alfa")).to_contain_text("Greenhouse")
    expect(_cartao(page, "alfa")).not_to_contain_text("Você removeu esta empresa")
    expect(_cartao(page, "vitta")).to_contain_text("Você removeu esta empresa em 13/11/2026")
    assert erros == []


def test_aprovar_uma_a_uma_leva_a_empresa_para_a_lista_de_empresas(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas/sugeridas")

    _cartao(page, "alfa").get_by_role("button", name="Aprovar").click()
    expect(page).to_have_url(re.compile(r"/empresas/sugeridas$"))
    expect(_cartao(page, "alfa")).to_have_count(0)
    expect(_cartao(page, "beta")).to_have_count(1)  # só a aprovada saiu

    page.goto(f"{painel}/empresas")
    expect(page.locator("#lista-empresas").get_by_role("heading", name="alfa")).to_have_count(1)
    expect(page.locator("#lista-empresas").get_by_role("heading", name="beta")).to_have_count(0)


def test_descartar_some_da_lista_e_nao_cria_empresa(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas/sugeridas")

    _cartao(page, "beta").get_by_role("button", name="Descartar").click()  # sem pergunta (T260)
    expect(_cartao(page, "beta")).to_have_count(0)
    expect(page.locator("#lista-sugeridas li.linha-busca")).to_have_count(2)
    expect(page.locator(FAIXA)).to_contain_text("Sugestão descartada")

    page.goto(f"{painel}/empresas")
    expect(page.locator(".vazio")).to_be_visible()  # nenhuma empresa acompanhada


def test_descartar_desfazer_e_refazer_sem_recarregar(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas/sugeridas")
    marca = "marca-sem-recarregar"
    page.evaluate(f"window.name = '{marca}'")
    faixa = page.locator(FAIXA)

    _cartao(page, "beta").get_by_role("button", name="Descartar").click()
    expect(_cartao(page, "beta")).to_have_count(0)
    expect(faixa.get_by_role("button", name="Refazer")).to_have_count(0)

    faixa.get_by_role("button", name="Desfazer").click()
    expect(_cartao(page, "beta")).to_have_count(1)  # a mesma linha volta, no seu lugar
    expect(_cartao(page, "beta")).to_have_class(re.compile(r"linha-volta"))
    expect(faixa).to_contain_text("Sugestão restaurada")

    faixa.get_by_role("button", name="Refazer").click()
    expect(_cartao(page, "beta")).to_have_count(0)
    expect(faixa).to_contain_text("Sugestão descartada")
    assert page.evaluate("window.name") == marca  # nada recarregou a página


def test_descartar_atualiza_a_contagem_da_lateral_e_devolve_o_foco(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas/sugeridas")
    lateral = page.locator("#lateral-onde")
    sugeridas = lateral.get_by_role("link", name=re.compile(r"^Sugeridas"))
    expect(sugeridas).to_contain_text("3")
    faixa = page.locator(FAIXA)

    _cartao(page, "alfa").get_by_role("button", name="Descartar").click()
    expect(sugeridas).to_contain_text("2")  # sem recarregar a página
    expect(page.locator("#lista-sugeridas li.linha-busca").first).to_be_focused()  # o botão saiu

    faixa.get_by_role("button", name="Desfazer").click()
    expect(sugeridas).to_contain_text("3")
    expect(
        faixa.get_by_role("button", name="Refazer")
    ).to_be_focused()  # o botão apertado foi trocado

    for nome in ("alfa", "beta", "vitta"):  # o último descarte tira o item da lateral
        _cartao(page, nome).get_by_role("button", name="Descartar").click()
        expect(_cartao(page, nome)).to_have_count(0)
    expect(sugeridas).to_have_count(0)


def test_menu_de_contexto_descarta_e_abre_no_site(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas/sugeridas")

    _cartao(page, "alfa").click(button="right", position={"x": 40, "y": 12})
    expect(page.get_by_role("menuitem", name="Abrir no site")).to_have_attribute(
        "href", "https://boards.greenhouse.io/alfa"
    )
    page.get_by_role("menuitem", name="Descartar").click()
    expect(_cartao(page, "alfa")).to_have_count(0)
    page.locator(FAIXA).get_by_role("button", name="Desfazer").click()
    expect(_cartao(page, "alfa")).to_have_count(1)


def test_sem_pendentes_mostra_o_vazio(page: Page, painel: str) -> None:
    page.goto(f"{painel}/empresas/sugeridas")
    for nome in ("alfa", "beta", "vitta"):
        _cartao(page, nome).get_by_role("button", name="Descartar").click()
        expect(_cartao(page, nome)).to_have_count(0)
    expect(page.locator(".vazio")).to_contain_text("Nenhuma empresa sugerida")


def test_menu_leva_para_a_tela_e_marca_so_ela(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas")
    page.get_by_role("navigation", name="Principal").get_by_role("link", name="Sugeridas").click()
    expect(page).to_have_url(re.compile(r"/empresas/sugeridas$"))
    menu = page.get_by_role("navigation", name="Principal")
    expect(menu.locator("[aria-current=page]")).to_have_count(1)
    expect(menu.get_by_role("link", name="Sugeridas")).to_have_attribute("aria-current", "page")


def test_sugeridas_apoio_longe_do_cartao(page: Page, painel: str) -> None:
    """T301 item 9: o texto de apoio não encosta no primeiro cartão (pelo menos 12px)."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{painel}/empresas/sugeridas")
    apoio = page.locator(".apoio-titulo")
    cartao = page.locator("#lista-sugeridas li.linha-busca").first
    expect(cartao).to_be_visible()
    pe = apoio.evaluate("el => el.getBoundingClientRect().bottom")
    topo = cartao.evaluate("el => el.getBoundingClientRect().top")
    assert topo - pe >= 12
