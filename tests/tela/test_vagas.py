"""Tela de vagas no navegador: abas, URL, tecla /, ordens, mais, ações e teclado (T45, T254)."""

import json
import re
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, Route, expect

from apoio.console import anotar_erros
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


def _linhas(page: Page) -> Locator:
    """As linhas da lista: `<a role="option">` filhas diretas do listbox (T254)."""
    return page.locator('#lista-vagas > [role="option"]')


def _cartao(page: Page, titulo: str) -> Locator:
    return _linhas(page).filter(has_text=titulo)


def _titulos(page: Page) -> list[str]:
    return page.locator("#lista-vagas .linha-titulo").all_inner_texts()


def _sem_contagem(texto: str) -> str:
    return re.sub(r"\s+\d+$", "", texto.strip())


def _aguardar_lista(page: Page) -> None:
    expect(page.locator("#lista-vagas")).to_be_visible()


def _abrir_mais_filtros(page: Page) -> None:
    resumo = page.locator("details.mais-filtros > summary")
    resumo.click()
    expect(page.locator("details.mais-filtros")).to_have_attribute("open", "")


def test_abas_marcam_a_atual_e_a_url_reabre_a_tela(page: Page, painel: str) -> None:
    erros = anotar_erros(page)  # violação do CSP aparece como erro no console
    page.goto(f"{painel}/vagas?aba=todas")
    # as abas moram só na lateral (T254, D150 item 1): a tela não repete a fileira
    expect(page.locator("main nav.abas")).to_have_count(0)
    lateral = page.locator("#lateral-vagas")
    nomes = [_sem_contagem(n) for n in lateral.locator("a").all_inner_texts()]
    assert nomes == [
        "Destaques de hoje",
        "Todas",
        "Novas",
        "Fecham logo",
        "Salvas",
        "Candidatei",
        "Programas",
        "Ocultas",
    ]
    expect(page.locator('[aria-current="page"]')).to_have_count(1)
    todas = lateral.locator('[href^="/vagas?aba=todas"]')
    novas = lateral.locator('[href^="/vagas?aba=novas"]')
    expect(todas).to_have_attribute("aria-current", "page")
    # os pedidos `load` do htmx assentam antes de sair: no WebKit, o pedido que a navegação corta
    # com a página indo para o bfcache dá `htmx:sendError` depois do `pageshow` do go_back,
    # fora do intervalo que o `anotar_erros` perdoa
    page.wait_for_load_state("networkidle")
    novas.click()
    expect(page).to_have_url(re.compile(r"[?&]aba=novas"))
    expect(lateral.locator("[aria-current]")).to_have_count(1)
    expect(novas).to_have_attribute("aria-current", "page")
    expect(todas).not_to_have_attribute("aria-current", "page")

    page.reload()
    expect(novas).to_have_attribute("aria-current", "page")
    page.go_back()
    expect(todas).to_have_attribute("aria-current", "page")
    assert erros == []


def test_raiz_abre_nos_destaques(page: Page, painel: str, banco: Path) -> None:
    _config(banco, "primeira_execucao_concluida", True)
    page.goto(painel + "/")
    expect(page).to_have_url(re.compile(r"/vagas\?aba=destaques"))
    destaques = page.locator('#lateral-vagas [href^="/vagas?aba=destaques"]')
    expect(destaques).to_have_attribute("aria-current", "page")


def test_chip_vai_para_a_url_e_a_url_reabre_o_filtro(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    todos = len(_titulos(page))
    _abrir_mais_filtros(page)  # T301: os chips moram no "Mais filtros", que vem fechado
    chip = page.locator("button.chip", has_text="Presencial")
    # os chips chegam depois da lista (T191): o expect espera por eles
    expect(chip).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#filtros-chips")).not_to_have_attribute("aria-busy", "true")
    esperado = int(chip.get_attribute("data-contagem") or "-1")
    assert 0 < esperado < todos

    chip.focus()
    page.keyboard.press("Enter")
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page).to_have_url(re.compile(r"modalidade=presencial"))
    assert len(_titulos(page)) == esperado
    # os chips novos chegam depois da lista: o foco tem de cair no chip clicado, não se perder
    expect(page.locator("button.chip", has_text="Presencial")).to_be_focused()

    page.reload()
    # fechado mesmo com filtro ativo (T301); o resumo conta o chip
    expect(page.locator("details.mais-filtros")).not_to_have_attribute("open", re.compile(".*"))
    expect(page.locator("details.mais-filtros > summary")).to_have_text("Mais filtros (1)")
    _abrir_mais_filtros(page)
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert len(_titulos(page)) == esperado

    page.locator("button.chip", has_text="Presencial").click()  # clicar de novo tira o filtro
    expect(page.locator("button.chip", has_text="Presencial")).to_have_attribute(
        "aria-pressed", "false"
    )
    assert len(_titulos(page)) == todos


@pytest.mark.parametrize("falha", ["abort", "500"])
def test_chips_que_falham_deixam_de_esperar(page: Page, painel: str, falha: str) -> None:
    """Pedido dos chips com erro: o aria-busy sai e o texto de espera some (o aviso global fica)."""
    if falha == "abort":
        page.route("**/vagas/chips*", lambda rota: rota.abort())
    else:
        page.route("**/vagas/chips*", lambda rota: rota.fulfill(status=500, body="erro"))
    page.goto(f"{painel}/vagas?aba=todas")
    expect(page.locator("#lista-vagas")).to_be_visible()
    _abrir_mais_filtros(page)  # aberto, o texto de espera estaria à vista se ficasse
    espera = page.locator("#filtros-chips")
    expect(espera).not_to_have_attribute("aria-busy", "true")
    expect(espera.locator("[data-espera]")).to_be_hidden()
    expect(page.locator("#aviso-erro")).to_be_visible()


def test_tecla_barra_foca_a_busca(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    # a busca mora na barra de ferramentas (T251) e manda o formulário da tela (form="busca")
    busca = page.get_by_role("banner").get_by_role("searchbox", name="Buscar em Vagas")
    expect(busca).to_have_attribute("data-busca", "")
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
    expect(page.locator("#lista-vagas .linha-titulo").first).to_have_text(primeira)
    page.reload()
    expect(page.locator("#ordem")).to_have_value(ordem)
    expect(page.locator("#lista-vagas .linha-titulo").first).to_have_text(primeira)


def test_carregar_mais(page: Page, painel: str, banco: Path) -> None:
    with closing(abrir(banco)) as con:
        for n in range(55):
            inserir_vaga(con, titulo=f"Extra {n}", empresa=f"Extra SA {n}")
    page.goto(f"{painel}/vagas?aba=todas")
    assert len(_titulos(page)) == 50
    mais = page.get_by_role("button", name="Carregar mais vagas")
    mais.focus()
    page.keyboard.press("Enter")
    expect(_linhas(page)).to_have_count(62)
    # o foco vai para a 1ª vaga nova, que vira a escolhida (a marca data-foco vale uma vez)
    expect(_linhas(page).nth(50)).to_be_focused()
    expect(_linhas(page).nth(50)).to_have_attribute("aria-selected", "true")
    expect(page.locator("#lista-vagas [data-foco]")).to_have_count(0)
    expect(page.locator('#lista-vagas > [role="option"][tabindex="0"]')).to_have_count(1)
    expect(page.get_by_role("button", name="Carregar mais vagas")).to_have_count(0)
    titulos = _titulos(page)
    assert len(set(titulos)) == len(titulos)


def test_desfazer_depois_de_carregar_mais_mantem_as_linhas(
    page: Page, painel: str, banco: Path
) -> None:
    """T305 (a): o Desfazer recarrega a lista com as páginas que já estavam na tela, não só a 1ª
    (antes as linhas do "carregar mais" sumiam, e a vaga que voltou também, se era de lá)."""
    with closing(abrir(banco)) as con:
        for n in range(55):
            inserir_vaga(con, titulo=f"Extra {n:02d}", empresa=f"Extra SA {n:02d}")
    page.goto(f"{painel}/vagas?aba=todas")
    page.get_by_role("button", name="Carregar mais vagas").click()
    expect(_linhas(page)).to_have_count(62)
    titulo = _linhas(page).nth(55).locator(".linha-titulo").inner_text()
    _ocultar_pelo_detalhe(page, titulo)
    expect(_linhas(page)).to_have_count(61)
    page.locator(FAIXA).get_by_role("button", name="Desfazer").click()
    expect(page.locator(FAIXA)).to_contain_text("Vaga mostrada de novo")
    expect(_linhas(page)).to_have_count(62)
    expect(_cartao(page, titulo)).to_be_visible()
    expect(page.get_by_role("button", name="Carregar mais vagas")).to_have_count(0)
    titulos = _titulos(page)
    assert len(set(titulos)) == len(titulos)


LADO = "#detalhe-vaga"


def _abrir_pelo_teclado(page: Page, titulo: str) -> None:
    """Foca a linha da vaga e abre com Return: na janela larga do teste, o detalhe abre ao lado da
    lista (T255), com o título em h2 (o h1 é o da página). Espera o settle do htmx: antes dele, os
    hx-* do detalhe novo ainda não valem e um Return no Ocultar faria o POST nativo. Espera também
    antes de teclar: a linha que o "Carregar mais" acabou de trazer sem os hx-* navega a página."""
    expect(page.locator(".htmx-request, .htmx-swapping, .htmx-settling")).to_have_count(0)
    _cartao(page, titulo).focus()
    page.keyboard.press("Enter")
    expect(page.locator(LADO).get_by_role("heading", level=2, name=titulo)).to_be_visible()
    expect(page.locator(".htmx-settling")).to_have_count(0)


def test_salvar_mudar_a_situacao_ocultar_e_trazer_de_volta(page: Page, painel: str) -> None:
    """As ações saíram da linha (D143.53): moram no detalhe, que se abre com Return."""
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    lado = page.locator(LADO)
    situacao = lado.locator(".situacao")
    expect(situacao).to_have_text("Situação: Nova")

    lado.get_by_role("button", name="Salvar", exact=True).focus()
    page.keyboard.press("Enter")
    expect(situacao).to_have_text("Situação: Salva")
    lado.get_by_role("button", name="Me candidatei", exact=True).focus()
    page.keyboard.press("Enter")
    expect(situacao).to_have_text("Situação: Candidatei")
    lado.get_by_role("button", name=re.compile("^Desfazer")).focus()
    page.keyboard.press("Enter")
    expect(situacao).to_have_text("Situação: Salva")

    page.goto(f"{painel}/vagas?aba=salvas")  # o que mudou está no banco, não só na tela
    expect(_cartao(page, NOVA)).to_be_visible()

    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    lado.get_by_role("button", name="Ocultar", exact=True).focus()
    page.keyboard.press("Enter")
    # T256: a linha sai, o detalhe dela fecha e a faixa oferece Desfazer
    expect(page.locator(FAIXA)).to_contain_text("Vaga ocultada")
    expect(lado).to_be_hidden()
    expect(_cartao(page, NOVA)).to_have_count(0)
    page.goto(f"{painel}/vagas?aba=todas")
    assert NOVA not in _titulos(page)
    page.goto(f"{painel}/vagas?aba=ocultas")
    expect(_cartao(page, NOVA)).to_be_visible()
    expect(_cartao(page, NOVA).get_by_text("Oculta por você")).to_be_visible()

    _abrir_pelo_teclado(page, NOVA)
    lado.get_by_role("button", name="Trazer de volta", exact=True).focus()
    page.keyboard.press("Enter")
    expect(lado.get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    expect(lado.get_by_text("Oculta por você")).to_have_count(0)
    page.goto(f"{painel}/vagas?aba=todas")
    assert NOVA in _titulos(page)


FAIXA = "#faixa-desfazer"


def _ocultar_pelo_detalhe(page: Page, titulo: str) -> None:
    """Abre a vaga ao lado e clica em Ocultar: a linha sai e a faixa de desfazer aparece (T256)."""
    _abrir_pelo_teclado(page, titulo)
    page.locator(LADO).get_by_role("button", name="Ocultar", exact=True).click()
    expect(page.locator(FAIXA)).to_contain_text("Vaga ocultada")
    expect(_cartao(page, titulo)).to_have_count(0)


def _foco_numa_linha(page: Page) -> None:
    expect(page.locator('#lista-vagas > [role="option"]:focus')).to_have_count(1)


def test_cmd_z_desfaz_fora_do_campo(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    _ocultar_pelo_detalhe(page, NOVA)
    faixa = page.locator(FAIXA)
    expect(faixa).to_have_attribute("role", "status")
    # o foco não salta para a faixa: fica numa linha que existe
    _foco_numa_linha(page)
    expect(faixa.get_by_role("button", name="Desfazer")).not_to_be_focused()
    page.keyboard.press("ControlOrMeta+z")
    expect(faixa).to_contain_text("Vaga mostrada de novo")
    expect(faixa.get_by_role("button", name="Refazer")).to_be_visible()
    linha = _cartao(page, NOVA)
    expect(linha).to_be_visible()
    expect(linha).to_have_class(re.compile(r"\blinha-volta\b"))  # o realce mostra onde voltou
    page.goto(f"{painel}/vagas?aba=ocultas")  # voltou no banco, não só na tela
    expect(_cartao(page, NOVA)).to_have_count(0)


def test_cmd_z_logo_que_a_faixa_chega_vai_por_htmx(page: Page, painel: str) -> None:
    """⌘Z antes do settle da faixa (os hx-* dela ainda inativos) não vira POST nativo."""
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_pelo_teclado(page, NOVA)
    nativos: list[str] = []
    page.on(
        "request",
        lambda r: (
            nativos.append(r.url)
            if r.method == "POST" and r.headers.get("hx-request") != "true"
            else None
        ),
    )
    page.locator(LADO).get_by_role("button", name="Ocultar", exact=True).click()
    page.locator(FAIXA).get_by_text("Vaga ocultada").wait_for()
    page.keyboard.press("ControlOrMeta+z")
    expect(page.locator(FAIXA)).to_contain_text("Vaga mostrada de novo")
    expect(_cartao(page, NOVA)).to_be_visible()
    assert nativos == []


def test_cmd_z_no_campo_nao_desfaz_a_faixa(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    _ocultar_pelo_detalhe(page, NOVA)
    busca = page.locator("[data-busca]")
    busca.focus()
    page.keyboard.type("abc")
    page.keyboard.press("ControlOrMeta+z")
    # o ⌘Z ficou com o campo (desfez o texto digitado), não com a faixa
    expect(busca).to_have_value("")
    expect(page.locator(FAIXA)).to_contain_text("Vaga ocultada")
    expect(page.locator(FAIXA).get_by_role("button", name="Desfazer")).to_be_visible()
    expect(_cartao(page, NOVA)).to_have_count(0)


def test_cmd_z_com_o_foco_na_ordem_desfaz(page: Page, painel: str) -> None:
    """Só campo de texto fica com o ⌘Z: no seletor de ordem (um select), ele desfaz a faixa."""
    page.goto(f"{painel}/vagas?aba=todas")
    _ocultar_pelo_detalhe(page, NOVA)
    page.locator("#ordem").focus()
    page.keyboard.press("ControlOrMeta+z")
    expect(page.locator(FAIXA)).to_contain_text("Vaga mostrada de novo")
    expect(_cartao(page, NOVA)).to_be_visible()


def test_shift_cmd_z_refaz(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    _ocultar_pelo_detalhe(page, NOVA)
    faixa = page.locator(FAIXA)
    page.keyboard.press("ControlOrMeta+Shift+z")  # sem Refazer na faixa, nada acontece
    expect(faixa.get_by_role("button", name="Desfazer")).to_be_visible()
    page.keyboard.press("ControlOrMeta+z")
    expect(faixa.get_by_role("button", name="Refazer")).to_be_visible()
    expect(_cartao(page, NOVA)).to_be_visible()
    page.keyboard.press("ControlOrMeta+Shift+z")
    expect(faixa).to_contain_text("Vaga ocultada")
    expect(faixa.get_by_role("button", name="Desfazer")).to_be_visible()
    expect(_cartao(page, NOVA)).to_have_count(0)
    _foco_numa_linha(page)
    # o botão Fechar tira a faixa; aí o ⌘Z não faz nada
    faixa.get_by_role("button", name="Fechar").click()
    expect(faixa).to_be_empty()
    page.keyboard.press("ControlOrMeta+z")
    expect(_cartao(page, NOVA)).to_have_count(0)


def test_faixa_fica_ao_trocar_a_ordem(page: Page, painel: str) -> None:
    """A faixa sobrevive às trocas HTMX do miolo de Vagas (aqui, a ordem). A troca de aba pela
    lateral é página inteira e a leva, como outra página nova (D154)."""
    page.goto(f"{painel}/vagas?aba=todas&ordem=recentes")
    _ocultar_pelo_detalhe(page, NOVA)
    faixa = page.locator(FAIXA)
    page.locator("#ordem").select_option("empresa")
    expect(page).to_have_url(re.compile(r"[?&]ordem=empresa"))
    expect(page.locator("#lista-vagas .linha-titulo").first).to_have_text("Analista de Sistemas")
    expect(page.locator(".htmx-settling")).to_have_count(0)
    expect(faixa).to_contain_text("Vaga ocultada")  # a troca do miolo (HTMX) não a leva
    faixa.get_by_role("button", name="Desfazer").click()
    expect(faixa).to_contain_text("Vaga mostrada de novo")
    # a lista recarregada mantém a ordem de agora, e a lateral marca a aba de agora
    expect(page).to_have_url(re.compile(r"[?&]ordem=empresa"))
    expect(page.locator("#ordem")).to_have_value("empresa")
    todas = page.locator('#lateral-vagas [href^="/vagas?aba=todas"]')
    expect(todas).to_have_attribute("aria-current", "page")
    expect(_cartao(page, NOVA)).to_be_visible()
    expect(faixa.get_by_role("button", name="Refazer")).to_be_focused()
    page.goto(f"{painel}/vagas?aba=todas")  # página nova inteira: a faixa some
    expect(faixa).to_be_empty()
    assert NOVA in _titulos(page)


def test_tab_real_chega_a_lista_e_return_abre_a_vaga(page: Page, painel: str) -> None:
    """Tab pressionado de verdade (sem `focus()`) chega à lista numa parada só (tabindex móvel)."""
    page.goto(f"{painel}/vagas?aba=todas")
    primeira = _linhas(page).first
    expect(primeira).to_be_visible()
    for _ in range(150):  # teto: a ordem do Tab não pode ficar presa nem passar da lista
        page.keyboard.press("Tab")
        if primeira.evaluate("el => el === document.activeElement"):
            break
    else:
        pytest.fail("o Tab não chegou à lista de vagas")
    page.keyboard.press("Tab")  # uma parada só: o próximo Tab sai da lista
    focada = page.evaluate("() => document.activeElement.getAttribute('role')")
    assert focada != "option"
    page.keyboard.press("Shift+Tab")
    expect(primeira).to_be_focused()
    titulo = primeira.locator(".linha-titulo").inner_text()
    page.keyboard.press("Enter")  # T255: o detalhe abre ao lado e a URL guarda a vaga
    expect(page).to_have_url(re.compile(r"/vagas\?aba=todas&vaga=\d+$"))
    expect(page.locator(LADO).get_by_role("heading", level=2, name=titulo)).to_be_visible()


def test_setas_j_k_home_end_movem_o_foco_na_lista(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    linhas = _linhas(page)
    n = linhas.count()
    assert n >= 3
    expect(page.locator('#lista-vagas > [role="option"][tabindex="0"]')).to_have_count(1)
    linhas.nth(0).focus()

    passos = [
        ("ArrowDown", 1),
        ("j", 2),
        ("k", 1),
        ("ArrowUp", 0),
        ("ArrowUp", 0),  # na ponta, fica onde está
        ("End", n - 1),
        ("ArrowDown", n - 1),
        ("Home", 0),
    ]
    for tecla, esperada in passos:
        page.keyboard.press(tecla)
        expect(linhas.nth(esperada)).to_be_focused()
        # a seleção segue o foco, e só a escolhida fica no Tab
        expect(linhas.nth(esperada)).to_have_attribute("aria-selected", "true")
        expect(linhas.nth(esperada)).to_have_attribute("tabindex", "0")
        expect(page.locator('#lista-vagas [aria-selected="true"]')).to_have_count(1)
    page.keyboard.press("j")
    expect(linhas.nth(1)).to_be_focused()
    page.keyboard.press("Enter")  # Return abre a vaga escolhida ao lado (T255)
    expect(page).to_have_url(re.compile(r"[?&]vaga=\d+$"))
    expect(page.locator(LADO)).to_be_visible()
    expect(linhas.nth(1)).to_be_focused()  # o teclado da lista segue com o detalhe aberto
    page.keyboard.press("ArrowDown")
    expect(linhas.nth(2)).to_be_focused()
    expect(linhas.nth(2)).to_have_attribute("aria-selected", "true")
    page.go_back()
    expect(page).to_have_url(re.compile(r"aba=todas$"))


# o settle do detalhe é um setTimeout de 20 ms depois da troca: com o relógio parado, só o
# fast_forward o dispara; cada settle do #detalhe-vaga conta em `assentos`
_CONTAR_SETTLES = """() => {
    window.assentos = 0;
    document.addEventListener("htmx:afterSettle", (e) => {
        if (e.target.id === "detalhe-vaga") window.assentos += 1;
    });
}"""


def _relogio_parado(page: Page, painel: str) -> None:
    page.clock.install(time=0)
    page.goto(f"{painel}/vagas?aba=todas")
    page.clock.pause_at(1000)
    page.evaluate(_CONTAR_SETTLES)


def test_seta_logo_depois_do_return_vence_a_resposta(page: Page, painel: str) -> None:
    """A seta dada entre a troca do detalhe e o settle leva a escolha; a resposta não a devolve."""
    _relogio_parado(page, painel)
    linhas = _linhas(page)
    linhas.nth(1).focus()
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"[?&]vaga=\d+$"))
    expect(page.locator(LADO)).to_be_visible()
    page.keyboard.press("ArrowDown")
    expect(linhas.nth(2)).to_be_focused()
    assert page.evaluate("window.assentos") == 0  # a premissa: a seta veio antes do settle
    page.clock.fast_forward(20)
    assert page.evaluate("window.assentos") == 1
    expect(linhas.nth(2)).to_be_focused()
    expect(linhas.nth(2)).to_have_attribute("aria-selected", "true")
    expect(page.locator('#lista-vagas [aria-selected="true"]')).to_have_count(1)


def test_dois_pedidos_seguidos_nao_desfazem_a_seta(page: Page, painel: str) -> None:
    """Abrir A, descer, abrir B (preso na rede) e descer: o settle de A chega com B no ar, depois o
    de B. Cada resposta compara com a marca do seu próprio pedido, e a escolha fica no foco."""
    _relogio_parado(page, painel)
    linhas = _linhas(page)
    linhas.nth(0).focus()
    page.keyboard.press("Enter")  # A
    expect(page).to_have_url(re.compile(r"[?&]vaga=\d+$"))
    expect(page.locator(LADO)).to_be_visible()
    page.keyboard.press("ArrowDown")
    expect(linhas.nth(1)).to_be_focused()
    id_b = linhas.nth(1).get_attribute("data-id")
    presos: list[Route] = []
    page.route(re.compile(r"[?&]vaga=\d+$"), lambda rota: presos.append(rota))
    page.keyboard.press("Enter")  # B, que fica preso
    page.keyboard.press("ArrowDown")
    expect(linhas.nth(2)).to_be_focused()
    assert page.evaluate("window.assentos") == 0  # a premissa: as setas vieram antes dos settles
    page.clock.fast_forward(20)  # o settle de A, com B no ar
    assert page.evaluate("window.assentos") == 1
    assert len(presos) == 1
    presos[0].continue_()
    expect(page).to_have_url(re.compile(rf"[?&]vaga={id_b}$"))  # B trocou
    page.clock.fast_forward(20)  # o settle de B
    assert page.evaluate("window.assentos") == 2
    expect(linhas.nth(2)).to_be_focused()
    expect(linhas.nth(2)).to_have_attribute("aria-selected", "true")
    expect(page.locator('#lista-vagas [aria-selected="true"]')).to_have_count(1)


def test_teclado_da_lista_nao_age_em_campo_de_texto(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    _linhas(page).nth(0).focus()
    page.keyboard.press("/")  # da lista, a barra leva para a busca
    busca = page.locator("[data-busca]")
    expect(busca).to_be_focused()
    page.keyboard.type("jk")
    page.keyboard.press("Home")
    page.keyboard.press("End")
    expect(busca).to_have_value("jk")  # as letras entram no campo; nada se move na lista
    expect(busca).to_be_focused()
    page.keyboard.press("Escape")  # Esc limpa o campo (desenho 5.5)
    expect(busca).to_have_value("")


def test_sem_js_a_linha_e_um_link_comum(pagina_sem_js: Page, painel: str) -> None:
    pagina = pagina_sem_js
    pagina.goto(f"{painel}/vagas?aba=todas")
    linha = pagina.locator('#lista-vagas > [role="option"]', has_text=NOVA)
    assert linha.get_attribute("tabindex") is None  # sem JS, cada linha é um link no Tab
    linha.click()
    expect(pagina).to_have_url(re.compile(r"/vagas/\d+$"))
    expect(pagina.get_by_role("heading", level=1, name=NOVA)).to_be_visible()


def test_barra_da_lista_tem_a_busca_e_troca_a_busca_escolhida(
    page: Page, painel: str, banco: Path
) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    barra = page.locator(".barra-lista")
    expect(barra.locator("form#busca")).to_have_count(1)  # o form da busca mora na barra
    expect(barra.locator("#ordem")).to_have_attribute("form", "busca")
    expect(barra.locator("#busca-escolhida")).to_have_count(0)  # uma busca só: sem menu

    _sql(
        banco,
        "INSERT INTO busca (nome, cargos, modalidades, ativa, criada_em)"
        " VALUES ('Segunda', '[\"cobol\"]', '[]', 1, ?)",
        AGORA.isoformat(),
    )
    page.goto(f"{painel}/vagas?aba=novas")
    seletor = page.locator(".barra-lista #busca-escolhida")
    expect(seletor.locator("option")).to_have_count(2)
    segunda = seletor.locator("option", has_text="Segunda").get_attribute("value")
    assert segunda
    seletor.select_option(segunda)
    expect(page).to_have_url(re.compile(rf"[?&]busca={segunda}\b"))
    expect(page).to_have_url(re.compile(r"[?&]aba=novas"))  # a aba fica
    expect(page.locator("#busca-escolhida")).to_have_value(segunda)
    page.reload()
    expect(page.locator("#busca-escolhida")).to_have_value(segunda)


def test_lista_vazia_oferece_buscar_vagas(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas&q=zzzznadaachado")
    vazio = page.locator("#lista-vagas.vazio")
    expect(vazio.get_by_role("heading", name="Nenhuma vaga")).to_be_visible()
    expect(vazio.get_by_role("button", name="Buscar vagas")).to_be_visible()
    expect(page.get_by_role("listbox")).to_have_count(0)


def test_pular_para_a_lista_leva_o_foco_para_ela(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas?aba=todas")
    page.get_by_role("link", name="Pular para a lista de vagas").focus()
    page.keyboard.press("Enter")
    # o listbox recebe o foco e o passa para a linha escolhida (T254)
    expect(_linhas(page).first).to_be_focused()


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


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_mais_filtros_preenche_manda_e_mostra_na_url(
    page: Page, painel: str, banco: Path, esquema: str
) -> None:
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    with closing(abrir(banco)) as con:
        inserir_vaga(
            con,
            titulo="Vaga em São Paulo",
            uf="SP",
            cidade="São Paulo",
            sal_moeda="BRL",
            sal_min=900000,
            sal_periodo="mes",
            sal_mensal_min=900000,
            sal_mensal_min_brl=9000,
            sal_plausivel=1,
        )
    page.goto(f"{painel}/vagas?aba=todas")
    assert len(_titulos(page)) > 1
    page.get_by_text("Mais filtros", exact=True).click()
    page.get_by_label("Cidade", exact=True).fill("sao")
    campo = page.get_by_label("Salário de", exact=True)
    campo.fill("7000")
    with page.expect_response(lambda r: "cidade=sao" in r.url and "sal_de=7000" in r.url):
        campo.press("Enter")
    expect(page).to_have_url(re.compile(r"cidade=sao"))
    expect(page).to_have_url(re.compile(r"sal_de=7000"))
    expect(page.locator("#lista-vagas .linha-titulo")).to_have_count(1)
    assert _titulos(page) == ["Vaga em São Paulo"]


COR_TEXTO_2 = """() => {
  const e = document.createElement('i');
  e.style.color = 'var(--texto-2)';
  document.body.append(e);
  const cor = getComputedStyle(e).color;
  e.remove();
  return cor;
}"""


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_linha_em_tres_linhas_no_claro_e_no_escuro(page: Page, painel: str, esquema: str) -> None:
    """Desenho 5.8: título, empresa e local, salário e data, cada um numa linha que não quebra."""
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    page.goto(f"{painel}/vagas?aba=todas")
    linha = _cartao(page, "Desenvolvedor Python")
    caixas = [linha.locator(f".linha-{n}").bounding_box() for n in (1, 2, 3)]
    assert all(c is not None for c in caixas)
    um, dois, tres = caixas
    assert um and dois and tres
    assert dois["y"] >= um["y"] + um["height"] - 1
    assert tres["y"] >= dois["y"] + dois["height"] - 1
    salario = linha.locator(".linha-salario")
    expect(salario).to_have_text("≈ R$ 28.250/mês")
    expect(salario).to_have_attribute("title", re.compile(r"^US\$ 5\.000/mês · "))
    tamanho = "el => parseFloat(getComputedStyle(el).fontSize)"
    assert linha.locator(".linha-2").evaluate(tamanho) < linha.locator(".linha-1").evaluate(tamanho)
    cor = "el => getComputedStyle(el).color"
    assert linha.locator(".linha-2").evaluate(cor) == page.evaluate(COR_TEXTO_2)
    for n in (1, 2, 3):  # texto longo corta com reticências, sem quebrar a linha
        assert linha.locator(f".linha-{n}").evaluate("el => getComputedStyle(el).whiteSpace") == (
            "nowrap"
        )


def test_linha_escolhida_pinta_todo_o_texto_com_a_cor_da_selecao(page: Page, painel: str) -> None:
    """Com o foco na lista, nem o "Salário não informado" (neto da linha) fica cinza no azul."""
    page.goto(f"{painel}/vagas?aba=todas")
    linha = _linhas(page).filter(has=page.locator(".nao-informado")).first
    linha.focus()
    expect(linha).to_have_attribute("aria-selected", "true")
    cor = "el => getComputedStyle(el).color"
    esperada = linha.evaluate(cor)
    assert esperada != page.evaluate(COR_TEXTO_2)
    for parte in linha.locator("span, time").all():
        assert parte.evaluate(cor) == esperada


# --- T255: o detalhe ao lado da lista ---

MODO = "el => getComputedStyle(el).getPropertyValue('--detalhe-modo').trim()"
FUNDO_DE = """(cor) => {
  const e = document.createElement('i');
  e.style.backgroundColor = cor;
  document.body.append(e);
  const fundo = getComputedStyle(e).backgroundColor;
  e.remove();
  return fundo;
}"""


def _abrir_ao_lado(page: Page, titulo: str) -> None:
    _cartao(page, titulo).click()
    expect(page.locator(LADO).get_by_role("heading", level=2, name=titulo)).to_be_visible()


def _largura_do_miolo(page: Page) -> float:
    return float(page.locator("#vagas-miolo").evaluate("el => el.getBoundingClientRect().width"))


def test_coluna_larga_abre_ao_lado(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas&ordem=recentes")
    assert _largura_do_miolo(page) >= 860
    expect(page.locator(LADO)).to_be_hidden()  # sem vaga na URL, nada ao lado
    _abrir_ao_lado(page, NOVA)
    # a URL guarda a vista (aba e ordem) e a vaga; a página não troca
    expect(page).to_have_url(re.compile(r"/vagas\?aba=todas&ordem=recentes&vaga=\d+$"))
    expect(page.get_by_role("heading", level=1, name="Vagas")).to_be_visible()
    assert page.locator(LADO).evaluate(MODO) == "coluna"
    lista = page.locator("#lista-vagas").bounding_box()
    lado = page.locator(LADO).bounding_box()
    assert lista and lado
    assert lado["x"] >= lista["x"] + lista["width"]  # ao lado, sem cobrir a lista
    assert 320 <= lado["width"] <= 380
    expect(_cartao(page, NOVA)).to_have_attribute("aria-selected", "true")
    assert not page.locator(LADO).evaluate("el => el.matches(':modal')")
    # fontes, motivo do encaixe e os botões que saíram da linha
    lado_loc = page.locator(LADO)
    expect(lado_loc.get_by_role("link", name=re.compile("^via "))).not_to_have_count(0)
    expect(lado_loc.get_by_role("heading", level=3, name="Encaixe com a sua busca")).to_be_visible()
    for nome in ("Salvar", "Ocultar"):
        expect(lado_loc.get_by_role("button", name=nome, exact=True)).to_be_visible()
    expect(lado_loc.get_by_role("link", name=re.compile("^Abrir no site"))).to_be_visible()


def test_coluna_entre_640_e_860_abre_sobreposto(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1000, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    assert 640 <= _largura_do_miolo(page) < 860
    _abrir_ao_lado(page, NOVA)
    assert page.locator(LADO).evaluate(MODO) == "sobreposto"
    assert not page.locator(LADO).evaluate("el => el.matches(':modal')")  # a lista segue usável
    lista = page.locator("#lista-vagas").bounding_box()
    lado = page.locator(LADO).bounding_box()
    assert lista and lado
    assert lado["x"] < lista["x"] + lista["width"]  # por cima da lista, encostado à direita
    assert abs((lado["x"] + lado["width"]) - (lista["x"] + lista["width"])) <= 2
    assert lado["width"] <= min(420, 0.6 * _largura_do_miolo(page)) + 1
    # clicar na lista, fora de uma linha, fecha o sobreposto; fora da lista, não
    page.locator(".barra-lista").dispatch_event("click")
    expect(page.locator(LADO)).to_be_visible()
    page.locator(".coluna-lista").dispatch_event("click")
    expect(page.locator(LADO)).to_be_hidden()
    expect(page).to_have_url(re.compile(r"/vagas\?aba=todas$"))


def test_recarregar_abre_a_mesma_vaga(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    url = page.url
    page.reload()
    expect(page).to_have_url(url)
    expect(page.locator(LADO).get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    expect(_cartao(page, NOVA)).to_have_attribute("aria-selected", "true")
    expect(page.locator('#lista-vagas [aria-selected="true"]')).to_have_count(1)


def test_esc_fecha_o_sobreposto(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1000, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    _cartao(page, NOVA).focus()
    page.keyboard.press("Enter")
    expect(page.locator(LADO).get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    assert page.locator(LADO).evaluate(MODO) == "sobreposto"
    page.keyboard.press("Escape")
    expect(page.locator(LADO)).to_be_hidden()
    expect(page).to_have_url(re.compile(r"/vagas\?aba=todas$"))
    expect(_cartao(page, NOVA)).to_be_focused()  # o foco volta à linha
    seguinte = _cartao(page, NOVA).locator("xpath=following-sibling::*[@role='option'][1]")
    page.keyboard.press("ArrowDown")  # e o teclado da lista segue valendo, a partir da linha
    expect(seguinte).to_be_focused()
    expect(seguinte).to_have_attribute("aria-selected", "true")


def test_esc_limpa_a_busca_uma_vez_so(page: Page, painel: str) -> None:
    """T305 (b): com o detalhe sobreposto aberto, o 1º Esc no campo da busca só limpa o texto; o
    detalhe fica. Com o campo vazio, o Esc segue e fecha o detalhe."""
    page.set_viewport_size({"width": 1000, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    _cartao(page, NOVA).focus()
    page.keyboard.press("Enter")
    expect(page.locator(LADO).get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    assert page.locator(LADO).evaluate(MODO) == "sobreposto"
    busca = page.locator("[data-busca]")
    busca.focus()
    page.keyboard.type("python")
    page.keyboard.press("Escape")
    expect(busca).to_have_value("")
    expect(page.locator(LADO)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(LADO)).to_be_hidden()


def test_janela_inativa_selecao_cinza(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    linha = _cartao(page, NOVA)
    linha.focus()
    expect(linha).to_be_focused()
    expect(linha).to_have_attribute("aria-selected", "true")
    fundo = "el => getComputedStyle(el).backgroundColor"
    destaque = page.evaluate(FUNDO_DE, "var(--destaque)")
    inativa = page.evaluate(FUNDO_DE, "var(--selecao-inativa)")
    assert destaque != inativa
    assert linha.evaluate(fundo) == destaque  # janela ativa, foco na lista: azul
    page.evaluate("() => { document.documentElement.dataset.janela = 'inativa'; }")
    expect(linha).to_be_focused()
    assert linha.evaluate(fundo) == inativa  # janela inativa: cinza, mesmo com o foco na lista
    # o foco no detalhe (a outra coluna) também deixa a linha cinza
    page.evaluate("() => { delete document.documentElement.dataset.janela; }")
    page.locator(LADO).get_by_role("button", name="Salvar", exact=True).focus()
    assert linha.evaluate(fundo) == inativa


def test_clique_sem_foco_marca_a_linha_aberta(page: Page, painel: str) -> None:
    """Safari e Firefox do Mac não focam o <a> clicado: a marca vem da resposta, não do foco."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    outra = _linhas(page).filter(has_not_text=NOVA).first
    titulo = outra.locator(".linha-titulo").inner_text()
    with page.expect_response(lambda r: "vaga=" in r.url):
        outra.evaluate("el => el.click()")  # clique que não leva o foco, como no Safari
    expect(page.locator(LADO).get_by_role("heading", level=2, name=titulo)).to_be_visible()
    expect(outra).not_to_be_focused()
    expect(outra).to_have_attribute("aria-selected", "true")
    expect(page.locator('#lista-vagas [aria-selected="true"]')).to_have_count(1)


def test_sem_foco_a_linha_aberta_fica_azul(page: Page, painel: str) -> None:
    """Desenho 5.2: sem foco em coluna nenhuma (aqui, depois de recarregar), a lista conta como
    ativa; com a janela inativa, a linha volta ao cinza."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    page.reload()
    linha = _cartao(page, NOVA)
    expect(linha).to_have_attribute("aria-selected", "true")
    assert page.evaluate("() => !document.querySelector(':focus')")
    fundo = "el => getComputedStyle(el).backgroundColor"
    assert linha.evaluate(fundo) == page.evaluate(FUNDO_DE, "var(--destaque)")
    page.evaluate("() => { document.documentElement.dataset.janela = 'inativa'; }")
    assert linha.evaluate(fundo) == page.evaluate(FUNDO_DE, "var(--selecao-inativa)")


# T301: acertos da conferência visual
CAIXA = "el => { const r = el.getBoundingClientRect(); return [r.x, r.y, r.right, r.bottom]; }"


def _caixa(local: Locator) -> list[float]:
    return local.evaluate(CAIXA)  # type: ignore[no-any-return]


def _meio(local: Locator) -> float:
    _, topo, _, base = _caixa(local)
    return (topo + base) / 2


def test_lista_na_primeira_dobra(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    assert _caixa(_linhas(page).first)[1] < 320
    # uma linha de controles: a barra mal passa da altura do "Ordenar por"
    ordem = page.locator(".barra-lista #ordem")
    _, topo, _, base = _caixa(page.locator(".barra-lista"))
    _, o_topo, _, o_base = _caixa(ordem)
    assert base - topo < 2 * (o_base - o_topo)


@pytest.mark.parametrize("largura", [1280, 800, 600])
def test_mais_filtros_no_mesmo_lugar(page: Page, painel: str, largura: int) -> None:
    """O resumo é o último item da linha, logo depois de "Ordenar por", em toda largura."""
    page.set_viewport_size({"width": largura, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    resumo = page.locator("details.mais-filtros > summary")
    ordem = page.locator(".barra-lista #ordem")
    assert abs(_meio(resumo) - _meio(ordem)) <= 4
    assert _caixa(resumo)[0] >= _caixa(ordem)[2]


def test_sobreposto_preso_a_janela(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 800, "height": 700})
    page.goto(f"{painel}/vagas?aba=todas")
    assert 640 <= _largura_do_miolo(page) < 860
    _linhas(page).nth(1).click()
    lado = page.locator(LADO)
    expect(lado.get_by_role("heading", level=2)).to_be_visible()
    assert lado.evaluate(MODO) == "sobreposto"
    assert not lado.evaluate("el => el.matches(':modal')")
    pe_da_barra = _caixa(page.get_by_role("banner"))[3]
    x, topo, direita, base = _caixa(lado)
    assert pe_da_barra <= topo <= pe_da_barra + 16  # do pé da barra de ferramentas...
    assert base <= 700  # ... até dentro da janela
    for nome in ("Salvar", "Ocultar"):  # as ações presas no pé, inteiras à vista (E17)
        b_x, b_topo, b_direita, b_base = _caixa(lado.get_by_role("button", name=nome, exact=True))
        assert 0 <= b_x and b_direita <= 800 and 0 <= b_topo and b_base <= 700, nome
    corpo = page.locator(f"{LADO} > .detalhe")
    assert corpo.evaluate("el => el.scrollHeight > el.clientHeight")  # só o corpo rola
    # preso à janela: rolar a lista não leva o sobreposto junto
    page.locator(".coluna").evaluate("el => el.scrollBy(0, 300)")
    page.wait_for_function("() => document.querySelector('.coluna').scrollTop > 0")
    depois = _caixa(lado)
    assert all(abs(a - b) <= 0.5 for a, b in zip(depois, [x, topo, direita, base], strict=True))


EM_CIMA = "() => document.querySelector('#detalhe-vaga')?.matches(':popover-open')"
NO_FLUXO = "() => !document.querySelector('#detalhe-vaga')?.matches(':popover-open')"


def test_foco_fica_no_detalhe_ao_alargar_a_janela(page: Page, painel: str) -> None:
    """T305 g: ao passar de sobreposto para coluna o app.js tira o detalhe da camada de cima
    (hidePopover), que devolveria o foco à linha; o detalhe segue à vista e o foco fica nele."""
    page.set_viewport_size({"width": 800, "height": 700})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    expect(page.locator(f"{LADO}:popover-open")).to_have_count(1)
    salvar = page.locator(LADO).get_by_role("button", name="Salvar", exact=True)
    salvar.focus()
    page.set_viewport_size({"width": 1280, "height": 800})
    expect(page.locator(f"{LADO}:popover-open")).to_have_count(0)
    assert page.locator(LADO).evaluate(MODO) == "coluna"
    expect(salvar).to_be_focused()


def test_coluna_sem_a_caixa_do_popover(page: Page, painel: str) -> None:
    """O popover="manual" do sobreposto traz as regras de UA de [popover] (fundo Canvas, largura
    fit-content, borda, inset 0) em todo estado: em coluna o detalhe segue sem fundo, só com o
    separador à esquerda, na largura da trilha da grade."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    lado = page.locator(LADO)
    assert lado.evaluate(MODO) == "coluna"
    page.wait_for_function(NO_FLUXO)
    estilo = lado.evaluate(
        "el => { const s = getComputedStyle(el); return [s.backgroundColor, s.borderTopStyle,"
        " s.borderLeftStyle, s.borderTopLeftRadius, s.boxShadow, s.bottom]; }"
    )
    assert estilo == ["rgba(0, 0, 0, 0)", "none", "solid", "0px", "none", "auto"]
    trilha = page.locator(".vagas-colunas").evaluate(
        "el => parseFloat(getComputedStyle(el).gridTemplateColumns.split(' ').at(-1))"
    )
    caixa = lado.bounding_box()
    assert caixa
    assert abs(caixa["width"] - trilha) <= 1


def test_camada_do_detalhe_depois_de_voltar(page: Page, painel: str) -> None:
    """Voltar troca o body (historyRestore): a troca de camada segue a largura do miolo depois
    disso, sem o observador preso à .coluna velha."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas&ordem=recentes")
    _abrir_ao_lado(page, NOVA)
    page.evaluate("() => { window.__mesmaPagina = true; }")
    # a ordem troca o miolo com hx-push-url (a aba da lateral é página inteira e não serve)
    page.locator("#ordem").select_option("empresa")
    expect(page).to_have_url(re.compile(r"[?&]ordem=empresa"))
    page.go_back()
    expect(page).to_have_url(re.compile(r"[?&]ordem=recentes"))
    expect(page.locator(LADO).get_by_role("heading", level=2, name=NOVA)).to_be_visible()
    assert page.evaluate("() => window.__mesmaPagina") is True  # restaurada pelo htmx, sem recarga
    page.wait_for_function(NO_FLUXO)
    page.set_viewport_size({"width": 800, "height": 700})
    page.wait_for_function(EM_CIMA)
    assert page.locator(LADO).evaluate(MODO) == "sobreposto"
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_function(NO_FLUXO)


def test_camada_desce_mesmo_sem_quadro_na_largura_estreita(page: Page, painel: str) -> None:
    """T314: a camada sobe fora do observador (afterSettle atrasado) com o miolo estreito, e a
    largura volta antes de o navegador desenhar um quadro estreito. O ResizeObserver só avisa
    quando o tamanho difere do último que entregou, então ele precisa se rearmar a cada troca de
    camada; senão o detalhe fica preso em cima com a janela larga."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{painel}/vagas?aba=todas")
    _abrir_ao_lado(page, NOVA)
    page.wait_for_function(NO_FLUXO)
    # numa tarefa só: estreita a .coluna, deixa um afterSettle subir a camada e volta a largura
    subiu = page.evaluate(
        """() => {
          const coluna = document.querySelector('.coluna');
          coluna.style.maxWidth = '780px';
          document.body.dispatchEvent(new CustomEvent('htmx:afterSettle', {bubbles: true}));
          const emCima = document.querySelector('#detalhe-vaga').matches(':popover-open');
          coluna.style.maxWidth = '';
          return emCima;
        }"""
    )
    assert subiu is True
    page.wait_for_function(NO_FLUXO)


def test_titulos_da_lista_alinhados(page: Page, painel: str, banco: Path) -> None:
    """Com encaixe bom, médio, fraco ou nenhum, os títulos começam no mesmo x (a caixa do ícone
    existe vazia)."""
    with closing(abrir(banco)) as con:
        inserir_vaga(con, titulo="Vaga Sem Encaixe")
        con.commit()
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    for icone in ("circle-check", "contrast", "circle"):
        expect(
            page.locator(f'#lista-vagas .icone-encaixe[data-icone="{icone}"]').first
        ).to_be_attached()
    expect(page.locator("#lista-vagas .icone-encaixe:not([data-icone])").first).to_be_attached()
    xs = page.locator("#lista-vagas .linha-titulo").evaluate_all(
        "es => es.map(e => e.getBoundingClientRect().x)"
    )
    assert len(xs) > 4
    assert max(xs) - min(xs) <= 1


def _com_contorno(local: Locator) -> bool:
    return local.evaluate(  # type: ignore[no-any-return]
        "el => { const s = getComputedStyle(el);"
        " return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0; }"
    )


def test_primeira_linha_sem_marca(page: Page, painel: str) -> None:
    """Na carga nenhuma linha vem marcada; a primeira só fica no Tab (T301 item 6)."""
    page.set_viewport_size({"width": 1280, "height": 800})
    # Todas, sem vaga aberta: a seta para baixo precisa de uma segunda linha (Destaques tem uma)
    page.goto(f"{painel}/vagas?aba=todas")
    _aguardar_lista(page)
    marcadas = page.locator('#lista-vagas [aria-selected="true"]')
    expect(marcadas).to_have_count(0)
    primeira = _linhas(page).first
    expect(primeira).to_have_attribute("tabindex", "0")
    # pelo link de pular: o foco, com contorno
    page.get_by_role("link", name="Pular para a lista de vagas").focus()
    page.keyboard.press("Enter")
    expect(primeira).to_be_focused()
    assert _com_contorno(primeira)
    # pelo Tab de verdade: o mesmo
    page.goto(f"{painel}/vagas?aba=todas")
    _aguardar_lista(page)
    for _ in range(150):
        page.keyboard.press("Tab")
        if primeira.evaluate("el => el === document.activeElement"):
            break
    else:
        pytest.fail("o Tab não chegou à lista de vagas")
    assert _com_contorno(primeira)
    # a seta escolhe: uma linha, e só uma, fica marcada
    page.keyboard.press("ArrowDown")
    expect(marcadas).to_have_count(1)
    expect(_linhas(page).nth(1)).to_have_attribute("aria-selected", "true")


VIOLACOES = """
window.__violacoes = [];
document.addEventListener('securitypolicyviolation', (e) => {
  // a diretiva e de onde veio, para a falha dizer o que o CSP barrou
  const onde = `${e.sourceFile}:${e.lineNumber}`;
  window.__violacoes.push(`${e.violatedDirective} ${e.blockedURI} ${onde} ${e.sample}`);
});
"""


def test_troca_da_lista_sem_violacao_de_csp(
    page: Page, painel: str, banco: Path, browser_name: str
) -> None:
    """A captura de tela do Playwright deixa style="" nos campos; o htmx copiava esse style para
    os campos novos na troca e o CSP barrava (style-src-attr). Item 10 da T301."""
    _sql(
        banco,
        "INSERT INTO busca (nome, cargos, modalidades, ativa, criada_em)"
        " VALUES ('Segunda', '[\"cobol\"]', '[]', 1, ?)",
        AGORA.isoformat(),
    )
    page.add_init_script(VIOLACOES)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{painel}/vagas?aba=todas")
    _aguardar_lista(page)
    page.screenshot()  # antes das trocas, como numa conferência visual
    # no WebKit a própria foto põe um <style> na página (o Playwright, para esconder o cursor) e o
    # CSP o barra; lá a conta das violações começa depois dela, quando o aviso já chegou (T352).
    # Nos outros motores a conta vem desde a carga.
    if browser_name == "webkit":
        page.evaluate(
            "() => new Promise(fim => requestAnimationFrame(() => setTimeout(() => {"
            " window.__violacoes = []; fim(); })))"
        )
    # o que a foto faz, sem depender dela: style vazio nos campos, posto pelo CSSOM (o CSP deixa)
    marcados = page.locator('[id^="filtro-"]').evaluate_all(
        "es => es.map(e => { e.style.caretColor = 'transparent'; e.style.caretColor = '';"
        " return e.hasAttribute('style'); })"
    )
    assert marcados and all(marcados)
    _ocultar_pelo_detalhe(page, NOVA)
    page.locator(FAIXA).get_by_role("button", name="Desfazer").click()
    expect(_cartao(page, NOVA)).to_have_count(1)
    seletor = page.locator(".barra-lista #busca-escolhida")
    segunda = seletor.locator("option", has_text="Segunda").get_attribute("value")
    assert segunda
    seletor.select_option(segunda)
    expect(page).to_have_url(re.compile(rf"[?&]busca={segunda}\b"))
    expect(page.locator("#busca-escolhida")).to_have_value(segunda)
    assert page.evaluate("() => window.__violacoes") == []
