"""Pergunta depois da candidatura: o clique registra a abertura (T284) e a faixa pergunta (T285)."""

import re
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, Response, expect

from apoio.relogio import RelogioFalso
from apoio.site_falso import SiteFalso
from jobot.banco import acoes
from jobot.banco.conexao import abrir
from jobot.banco.leitura import abertura_da_candidatura

pytestmark = pytest.mark.tela

HIMALAYAS = 3  # id na ordem em que o `semear` grava; tem link de candidatura


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()  # o semeado é datado de `AGORA`
    return app_painel


def test_tela_clique_registra(page: Page, painel: str, tmp_path: Path) -> None:
    banco = tmp_path / "jobot.db"
    with SiteFalso() as site:
        # a vaga aponta para o servidor local de teste: nunca para a rede
        with closing(abrir(banco)) as con:
            con.execute(
                "UPDATE ocorrencia SET coletada = json_set(coletada, '$.url_candidatura', ?)"
                " WHERE vaga_id = ?",
                (site.url("/logado"), HIMALAYAS),
            )
            con.commit()
            assert abertura_da_candidatura(con, HIMALAYAS) is None
        page.goto(f"{painel}/vagas/{HIMALAYAS}")
        with (
            page.context.expect_page() as nova,
            page.expect_response(f"**/vagas/{HIMALAYAS}/candidatura") as resposta,
        ):
            page.get_by_role("link", name="Candidatar-se").click()
        assert resposta.value.status == 204
        assert nova.value.url.startswith(site.url("/"))
        expect(page).to_have_url(f"{painel}/vagas/{HIMALAYAS}")  # esta aba não saiu da vaga
        with closing(abrir(banco)) as con:
            assert abertura_da_candidatura(con, HIMALAYAS) is not None


# ---- a faixa "Você se candidatou?" (T285; desenho 5.6) ----
USD = 1  # "Desenvolvedor Python", Zeta Corp
FAIXA = "#aviso-candidatura"
PERGUNTA_HIMALAYAS = "Você se candidatou a Backend Engineer (beta labs)?"


def _abrir_candidatura(banco: Path, *vagas: int) -> None:
    """Abre a candidatura de cada vaga, um minuto depois da anterior (a última fica no topo)."""
    hora = RelogioFalso().agora()
    with closing(abrir(banco)) as con:
        for n, vaga in enumerate(vagas):
            assert acoes.abriu_candidatura(con, vaga, hora + timedelta(minutes=n))


def _status(banco: Path, vaga: int) -> str:
    with closing(abrir(banco)) as con:
        return str(con.execute("SELECT status FROM vaga WHERE id = ?", (vaga,)).fetchone()[0])


def _abrir_pagina(page: Page, url: str) -> None:
    """Abre a página e espera o GET da faixa que vem com ela (`load`)."""
    with page.expect_response("**/aviso-candidatura*"):
        page.goto(url)


def _assentada(faixa: Locator) -> None:
    """O nó trocado só ganha os `hx-*` no fim do settle: antes disso o clique ou a tecla mandam o
    formulário sem o htmx («Tela com HTMX»). Chame depois de esperar o texto novo."""
    expect(faixa).not_to_have_class(re.compile(r"htmx-(request|swapping|settling)"))


def _voltar_a_janela(page: Page) -> None:
    """A pessoa volta à aba do painel. O Chromium sem tela pode não disparar `focus` no
    `bring_to_front`: o `focus` da janela, que o `hx-trigger` escuta, vai também à mão."""
    page.bring_to_front()
    page.evaluate("() => window.dispatchEvent(new Event('focus'))")


def test_tela_volta_a_janela_mostra_a_faixa(page: Page, painel: str, tmp_path: Path) -> None:
    banco = tmp_path / "jobot.db"
    with SiteFalso() as site:
        with closing(abrir(banco)) as con:
            con.execute(
                "UPDATE ocorrencia SET coletada = json_set(coletada, '$.url_candidatura', ?)"
                " WHERE vaga_id = ?",
                (site.url("/logado"), HIMALAYAS),
            )
            con.commit()
        _abrir_pagina(page, f"{painel}/vagas/{HIMALAYAS}")
        faixa = page.locator(FAIXA)
        expect(faixa.get_by_role("group")).to_have_count(0)
        with (
            page.context.expect_page() as nova,
            page.expect_response(f"**/vagas/{HIMALAYAS}/candidatura"),
        ):
            page.get_by_role("link", name="Candidatar-se").click()
        # fechar a aba nova já pode devolver o foco: o primeiro 200 vale, venha de onde vier
        with page.expect_response(
            lambda r: "/aviso-candidatura" in r.url and r.status == 200
        ) as resposta:
            nova.value.close()
            _voltar_a_janela(page)
        assert resposta.value.ok
        expect(faixa).to_contain_text(PERGUNTA_HIMALAYAS)
        expect(faixa.get_by_role("button", name="Sim, me candidatei", exact=True)).to_be_visible()
        expect(faixa.get_by_role("button", name="Ainda não", exact=True)).to_be_visible()


def test_tela_sim_e_desfazer(page: Page, painel: str, tmp_path: Path) -> None:
    banco = tmp_path / "jobot.db"
    _abrir_candidatura(banco, HIMALAYAS)
    _abrir_pagina(page, f"{painel}/vagas/{HIMALAYAS}")
    faixa = page.locator(FAIXA)
    expect(faixa).to_contain_text(PERGUNTA_HIMALAYAS)
    _assentada(faixa)
    with page.expect_response("**/candidatura/resposta"):
        faixa.get_by_role("button", name="Sim, me candidatei", exact=True).click()
    expect(faixa).to_contain_text("Backend Engineer marcada como Candidatei.")
    _assentada(faixa)
    assert _status(banco, HIMALAYAS) == "candidatei"
    with page.expect_response("**/candidatura/desfazer"):
        faixa.get_by_role("button", name="Desfazer", exact=True).click()
    expect(faixa.get_by_role("button")).to_have_count(0)
    assert _status(banco, HIMALAYAS) == "nova"


def test_tela_desfazer_fica_com_a_rede_parada(page: Page, painel: str, tmp_path: Path) -> None:
    banco = tmp_path / "jobot.db"
    _abrir_candidatura(banco, HIMALAYAS)
    _abrir_pagina(page, f"{painel}/vagas")
    faixa = page.locator(FAIXA)
    expect(faixa).to_contain_text(PERGUNTA_HIMALAYAS)
    _assentada(faixa)
    with page.expect_response("**/candidatura/resposta"):
        faixa.get_by_role("button", name="Sim, me candidatei", exact=True).click()
    desfazer = faixa.get_by_role("button", name="Desfazer", exact=True)
    expect(desfazer).to_be_visible()
    page.route("**/aviso-candidatura*", lambda rota: rota.abort())
    with page.expect_event("requestfailed", lambda r: "/aviso-candidatura" in r.url):
        _voltar_a_janela(page)
    expect(desfazer).to_be_visible()
    desfazer.focus()
    expect(desfazer).to_be_focused()


def test_tela_pelo_teclado(page: Page, painel: str, tmp_path: Path) -> None:
    banco = tmp_path / "jobot.db"
    _abrir_candidatura(banco, USD, HIMALAYAS)
    _abrir_pagina(page, f"{painel}/vagas")
    faixa = page.locator(FAIXA)
    expect(faixa).to_contain_text(PERGUNTA_HIMALAYAS)
    expect(faixa.get_by_role("link", name="e mais 1 para responder")).to_be_visible()
    _assentada(faixa)
    faixa.get_by_role("button", name="Sim, me candidatei", exact=True).focus()
    page.keyboard.press("Tab")
    ainda_nao = faixa.get_by_role("button", name="Ainda não", exact=True)
    expect(ainda_nao).to_be_focused()
    with page.expect_response("**/candidatura/resposta"):
        page.keyboard.press("Enter")
    expect(faixa).to_contain_text("Você se candidatou a Desenvolvedor Python (Zeta Corp)?")
    _assentada(faixa)
    assert _status(banco, HIMALAYAS) == "nova"
    faixa.get_by_role("button", name="Sim, me candidatei", exact=True).focus()
    with page.expect_response("**/candidatura/resposta"):
        page.keyboard.press("Space")
    expect(faixa).to_contain_text("Desenvolvedor Python marcada como Candidatei.")
    _assentada(faixa)
    assert _status(banco, USD) == "candidatei"
    faixa.get_by_role("button", name="Desfazer", exact=True).focus()
    with page.expect_response("**/candidatura/desfazer"):
        page.keyboard.press("Enter")
    expect(faixa.get_by_role("button")).to_have_count(0)
    assert _status(banco, USD) == "nova"


def test_tela_detalhe_atualiza_depois_da_faixa(page: Page, painel: str, tmp_path: Path) -> None:
    """E20 (T286): depois de "Sim" e de "Desfazer" na faixa, o #estado-da-vaga do detalhe pede de
    novo o próprio `GET /vagas/{id}` e mostra o status, os botões e a Linha do tempo de agora."""
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        acoes.mudar_status(con, HIMALAYAS, "salva", RelogioFalso().agora())
    _abrir_candidatura(banco, HIMALAYAS)
    _abrir_pagina(page, f"{painel}/vagas/{HIMALAYAS}")
    faixa = page.locator(FAIXA)
    estado = page.locator("#estado-da-vaga")
    expect(estado.locator(".situacao")).to_have_text("Situação: Salva")
    expect(estado.locator('button[value="nova"]')).to_have_count(1)
    expect(faixa).to_contain_text(PERGUNTA_HIMALAYAS)
    _assentada(faixa)

    def detalhe_de_novo(resposta: Response) -> bool:
        pedido = resposta.request
        return pedido.method == "GET" and resposta.url == f"{painel}/vagas/{HIMALAYAS}"

    with page.expect_response(detalhe_de_novo):
        faixa.get_by_role("button", name="Sim, me candidatei", exact=True).click()
    expect(estado.locator(".situacao")).to_have_text("Situação: Candidatei")
    expect(estado.locator('button[value="nova"]')).to_have_count(0)
    expect(estado.locator('button[value="entrevista"]')).to_have_count(1)
    expect(estado.locator(".passos")).to_contain_text("Candidatei em")
    expect(faixa).to_contain_text("Backend Engineer marcada como Candidatei.")
    _assentada(faixa)
    with page.expect_response(detalhe_de_novo):
        faixa.get_by_role("button", name="Desfazer", exact=True).click()
    expect(estado.locator(".situacao")).to_have_text("Situação: Salva")
    expect(estado.locator('button[value="nova"]')).to_have_count(1)
    expect(estado.locator(".passos")).not_to_contain_text("Candidatei em")
