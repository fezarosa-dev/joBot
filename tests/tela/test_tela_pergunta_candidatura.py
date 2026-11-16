"""Pergunta depois da candidatura: o clique em "Candidatar-se" registra a abertura (T284, T285)."""

from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.relogio import RelogioFalso
from apoio.site_falso import SiteFalso
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
