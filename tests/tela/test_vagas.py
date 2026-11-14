"""Tela de vagas no navegador: abas, URL, tecla /, ordens, mais, ações e teclado (T45)."""

import json
import re
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, expect

from apoio.relogio import RelogioFalso
from apoio.semear import AGORA, inserir_vaga
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela

NOVA = "Engenheira de Integração"
HIMALAYAS = "Backend Engineer"


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    # o semeado é datado de `AGORA`: com o relógio real tudo viraria "velho" e fora dos destaques
    app_painel.state.relogio = RelogioFalso()
    return app_painel


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    return tmp_path / "jobot.db"


def _sql(banco: Path, texto: str, *params: Any) -> None:
    with closing(abrir(banco)) as con:
        con.execute(texto, params)
        con.commit()


def _config(banco: Path, chave: str, valor: object) -> None:
    _sql(
        banco,
        "INSERT INTO config (chave, valor) VALUES (?, ?)"
        " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        chave,
        json.dumps(valor),
    )


def _cartao(page: Page, titulo: str) -> Locator:
    return page.locator("article", has_text=titulo)


def _titulos(page: Page) -> list[str]:
    return page.locator("main h3.cartao-titulo").all_inner_texts()


def _aguardar_lista(page: Page) -> None:
    expect(page.locator("#lista-vagas")).to_be_visible()


def test_abas_marcam_a_atual_e_a_url_reabre_a_tela(page: Page, painel: str) -> None:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.goto(f"{painel}/vagas?aba=todas")
    nomes = page.locator("nav.abas a").all_inner_texts()
    assert [n.rsplit(" ", 1)[0] for n in nomes] == [
        "Destaques",
        "Todas",
        "Novas",
        "Fecham logo",
        "Salvas",
        "Candidatei",
        "Programas",
        "Ocultas",
    ]
    expect(page.locator("nav.abas [aria-current]")).to_have_count(1)
    expect(page.locator("#aba-todas")).to_have_attribute("aria-current", "page")

    page.locator("#aba-novas").click()
    expect(page.locator("#aba-novas")).to_have_attribute("aria-current", "page")
    expect(page.locator("#aba-todas")).not_to_have_attribute("aria-current", "page")
    expect(page).to_have_url(re.compile(r"[?&]aba=novas"))

    page.reload()
    expect(page.locator("#aba-novas")).to_have_attribute("aria-current", "page")
    page.go_back()
    expect(page.locator("#aba-todas")).to_have_attribute("aria-current", "page")
    assert erros == []


def test_raiz_abre_nos_destaques(page: Page, painel: str, banco: Path) -> None:
    _config(banco, "primeira_execucao_concluida", True)
    page.goto(painel + "/")
    expect(page).to_have_url(re.compile(r"/vagas\?aba=destaques"))
    expect(page.locator("#aba-destaques")).to_have_attribute("aria-current", "page")


def test_chip_vai_para_a_url_e_a_url_reabre_o_filtro(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    todos = len(_titulos(page))
    chip = page.locator("button.chip", has_text="Presencial")
    expect(chip).to_have_attribute("aria-pressed", "false")
    esperado = int(chip.get_attribute("data-contagem") or "-1")
    assert 0 < esperado < todos

    chip.focus()
    page.keyboard.press("Enter")
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page).to_have_url(re.compile(r"modalidade=presencial"))
    assert len(_titulos(page)) == esperado

    page.reload()
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert len(_titulos(page)) == esperado

    page.locator("button.chip", has_text="Presencial").click()  # clicar de novo tira o filtro
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "false"
    )
    assert len(_titulos(page)) == todos


def test_tecla_barra_foca_a_busca(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    busca = page.locator("[data-busca]")
    expect(busca).not_to_be_focused()
    page.keyboard.press("/")
    expect(busca).to_be_focused()
    expect(busca).to_have_value("")  # a barra não vai para dentro do campo
    page.keyboard.type("Backend")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"q=Backend"))
    assert _titulos(page) == [HIMALAYAS]
    page.reload()
    expect(page.locator("[data-busca]")).to_have_value("Backend")


@pytest.mark.parametrize(
    ("ordem", "primeira"),
    [
        ("encaixe", "Desenvolvedor Python"),
        ("recentes", NOVA),
        ("prazo", "Analista de Dados python"),
        ("salario", "Desenvolvedor Python"),
        ("empresa", "Analista de Sistemas"),
    ],
)
def test_cinco_ordens(page: Page, painel: str, ordem: str, primeira: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas&ordem=recentes")
    seletor = page.locator("#ordem")
    assert seletor.locator("option").count() == 5
    seletor.focus()
    seletor.select_option(ordem)
    expect(page).to_have_url(re.compile(rf"ordem={ordem}"))
    expect(page.locator("#ordem")).to_have_value(ordem)
    expect(page.locator("#lista-vagas h3").first).to_have_text(primeira)
    page.reload()
    expect(page.locator("#ordem")).to_have_value(ordem)
    expect(page.locator("#lista-vagas h3").first).to_have_text(primeira)


def test_carregar_mais(page: Page, painel: str, banco: Path) -> None:
    with closing(abrir(banco)) as con:
        for n in range(55):
            inserir_vaga(con, titulo=f"Extra {n}", empresa=f"Extra SA {n}")
    page.goto(f"{painel}/vagas?aba=todas")
    assert len(_titulos(page)) == 50
    mais = page.get_by_role("button", name="Carregar mais vagas")
    mais.focus()
    page.keyboard.press("Enter")
    expect(page.locator("main article")).to_have_count(62)
    expect(page.locator("a[data-foco]")).to_be_focused()  # o foco vai para a 1ª vaga nova
    expect(page.get_by_role("button", name="Carregar mais vagas")).to_have_count(0)
    titulos = _titulos(page)
    assert len(set(titulos)) == len(titulos)


def test_salvar_mudar_a_situacao_ocultar_e_trazer_de_volta(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    cartao = _cartao(page, NOVA)
    expect(cartao.locator(".situacao")).to_have_text("Situação: Nova")

    cartao.get_by_role("button", name="Salvar", exact=True).focus()
    page.keyboard.press("Enter")
    expect(cartao.locator(".situacao")).to_have_text("Situação: Salva")
    expect(cartao.locator(".situacao")).to_be_focused()  # o foco não se perde com a troca
    # foco sempre visível (13.12): o alvo de foco programático não esconde o contorno
    estilo = cartao.locator(".situacao").evaluate(
        "el => [getComputedStyle(el).outlineStyle, getComputedStyle(el).outlineWidth]"
    )
    assert estilo[0] != "none" and estilo[1] != "0px"
    cartao.get_by_role("button", name="Me candidatei", exact=True).focus()
    page.keyboard.press("Enter")
    expect(cartao.locator(".situacao")).to_have_text("Situação: Candidatei")
    cartao.get_by_role("button", name=re.compile("^Desfazer")).focus()
    page.keyboard.press("Enter")
    expect(cartao.locator(".situacao")).to_have_text("Situação: Salva")

    page.reload()  # o que mudou está no banco, não só na tela
    expect(_cartao(page, NOVA).locator(".situacao")).to_have_text("Situação: Salva")
    page.locator("#aba-salvas").click()
    expect(_cartao(page, NOVA)).to_be_visible()

    page.goto(f"{painel}/vagas?aba=todas")
    _cartao(page, NOVA).get_by_role("button", name="Ocultar", exact=True).focus()
    page.keyboard.press("Enter")
    expect(_cartao(page, NOVA).get_by_text("Oculta por você")).to_be_visible()
    page.goto(f"{painel}/vagas?aba=todas")
    assert NOVA not in _titulos(page)
    page.locator("#aba-ocultas").click()
    expect(_cartao(page, NOVA)).to_be_visible()

    _cartao(page, NOVA).get_by_role("button", name="Trazer de volta", exact=True).focus()
    page.keyboard.press("Enter")
    expect(_cartao(page, NOVA).get_by_text("Oculta por você")).to_have_count(0)
    page.goto(f"{painel}/vagas?aba=todas")
    assert NOVA in _titulos(page)


def test_tab_real_chega_ao_cartao_e_aciona_com_enter(page: Page, painel: str) -> None:
    """Tab pressionado de verdade (sem `focus()`) percorre a página até o botão do cartão."""
    page.goto(f"{painel}/vagas?aba=todas")
    cartao = _cartao(page, NOVA)
    salvar = cartao.get_by_role("button", name="Salvar", exact=True)
    expect(salvar).to_be_visible()
    for _ in range(150):  # teto: a ordem do Tab não pode ficar presa nem passar do botão
        page.keyboard.press("Tab")
        if salvar.evaluate("el => el === document.activeElement"):
            break
    else:
        pytest.fail("o Tab não chegou ao botão Salvar do cartão")
    expect(salvar).to_be_focused()
    page.keyboard.press("Enter")
    expect(cartao.locator(".situacao")).to_have_text("Situação: Salva")
    expect(cartao.locator(".situacao")).to_be_focused()


def test_via_fonte_e_link_para_a_vaga_original(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    link = _cartao(page, HIMALAYAS).get_by_role("link", name=re.compile(r"^via Himalayas"))
    expect(link).to_have_text("via Himalayas")
    expect(link).to_have_attribute("href", "https://himalayas.app/companies/beta/jobs/42")
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", re.compile("noopener"))


def test_pular_para_a_lista_leva_o_foco_para_ela(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    page.get_by_role("link", name="Pular para a lista de vagas").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#lista-vagas")).to_be_focused()


def test_links_de_pular_ficam_invisiveis_ate_receber_foco(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    # o do miolo cai atrás da barra do topo translúcida: sem foco não pode aparecer (T146)
    pulos = page.locator(".pular")
    assert pulos.count() == 2
    for i in range(2):
        expect(pulos.nth(i)).to_have_css("opacity", "0")
        expect(pulos.nth(i)).to_have_css("pointer-events", "none")  # invisível não pega o mouse
    # continua focável com Tab, e aparece inteiro quando focado
    lista = page.get_by_role("link", name="Pular para a lista de vagas")
    for _ in range(40):  # a barra do topo e o menu vêm antes do conteúdo
        page.keyboard.press("Tab")
        if lista.evaluate("e => e === document.activeElement"):
            break
    expect(lista).to_be_focused()
    expect(lista).to_have_css("opacity", "1")
    expect(lista).to_have_css("pointer-events", "auto")
    expect(lista).to_be_in_viewport(ratio=1)


def test_links_de_pular_sem_foco_nao_pegam_o_mouse(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    # o ponto do centro da caixa: se cai na janela, o link não pode ser o que está ali (T146)
    pontos: list[dict[str, bool]] = page.eval_on_selector_all(
        ".pular",
        """els => els.map(e => {
          const r = e.getBoundingClientRect();
          const x = r.left + r.width / 2, y = r.top + r.height / 2;
          const dentro = x >= 0 && y >= 0 && x < innerWidth && y < innerHeight;
          return {dentro, pega: dentro && document.elementFromPoint(x, y) === e};
        })""",
    )
    assert len(pontos) == 2
    assert any(p["dentro"] for p in pontos)  # o do miolo tem o centro na janela: não é vácuo
    assert not any(p["pega"] for p in pontos), pontos


def test_sem_preferencia_pede_o_que_procura_e_destaques_vem_por_data(
    page: Page, painel: str, banco: Path
) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    expect(page.locator("[data-aviso=sem-criterio]")).to_have_count(0)

    _sql(banco, "DELETE FROM busca")
    with closing(abrir(banco)) as con:
        inserir_vaga(
            con,
            titulo="Velha",
            empresa="Velha SA",
            primeira_vista_em=(AGORA - timedelta(hours=3)).isoformat(),
            publicada_em=(AGORA - timedelta(hours=10)).isoformat(),
        )
        inserir_vaga(
            con,
            titulo="Recente",
            empresa="Recente Ltda",
            primeira_vista_em=(AGORA - timedelta(hours=2)).isoformat(),
            publicada_em=(AGORA - timedelta(hours=5)).isoformat(),
        )
    page.goto(f"{painel}/vagas?aba=destaques")
    aviso = page.locator("[data-aviso=sem-criterio]")
    expect(aviso).to_be_visible()
    expect(aviso.get_by_role("link", name="Dizer o que procuro")).to_be_visible()
    _aguardar_lista(page)
    assert _titulos(page)[:2] == ["Recente", "Velha"]
    expect(page.locator("#ordem")).to_have_count(0)  # destaques não tem ordem para escolher
