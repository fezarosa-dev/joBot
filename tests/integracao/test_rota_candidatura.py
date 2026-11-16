"""Registro da abertura da candidatura: `POST /vagas/{id}/candidatura` (plano T284, desenho 5.5)."""

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match

from apoio.relogio import RelogioFalso
from apoio.semear import semear
from jobot.banco.conexao import abrir
from jobot.banco.leitura import abertura_da_candidatura
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.rotas import candidatura
from jobot.painel.seguranca import CABECALHO_CSRF

PORTA = 47617
HORA = datetime(2026, 11, 16, 15, 30, tzinfo=UTC)


class Painel:
    """Cliente do app sobre um banco semeado, com o relógio parado em `HORA`."""

    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            self.ids = semear(con)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso(HORA)
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

    def aberta_em(self, vaga_id: int) -> str | None:
        with closing(abrir(self.banco)) as con:
            return abertura_da_candidatura(con, vaga_id)

    def linhas(self) -> int:
        with closing(abrir(self.banco)) as con:
            n: int = con.execute("SELECT COUNT(*) FROM candidatura").fetchone()[0]
        return n

    def post(self, vaga: int | str, **cabecalhos: str) -> Any:
        return self.http.post(f"/vagas/{vaga}/candidatura", headers=cabecalhos)

    def post_com_token(self, vaga: int | str) -> Any:
        return self.post(vaga, **{CABECALHO_CSRF: self.token})


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def test_post_204(painel: Painel) -> None:
    vaga = painel.ids["usd"]
    resposta = painel.post_com_token(vaga)
    assert resposta.status_code == 204
    assert resposta.content == b""
    assert painel.aberta_em(vaga) == HORA.isoformat()


def test_post_com_candidatei_204_sem_gravar(painel: Painel) -> None:
    vaga = painel.ids["usd"]
    with closing(abrir(painel.banco)) as con:
        con.execute("UPDATE vaga SET status = 'candidatei' WHERE id = ?", (vaga,))
        con.commit()
    resposta = painel.post_com_token(vaga)
    assert resposta.status_code == 204
    assert painel.linhas() == 0
    # controle: a mesma rota grava com a vaga `salva`
    salva = painel.ids["fechada_salva"]
    assert painel.post_com_token(salva).status_code == 204
    assert painel.linhas() == 1


def test_post_vaga_inexistente_404(painel: Painel) -> None:
    assert painel.post_com_token(999999).status_code == 404
    assert painel.linhas() == 0


def test_post_sem_csrf_recusado(painel: Painel) -> None:
    vaga = painel.ids["usd"]
    resposta = painel.post(vaga)
    assert resposta.status_code == 403
    assert painel.linhas() == 0
    # controle: com o cabeçalho, grava
    assert painel.post_com_token(vaga).status_code == 204
    assert painel.linhas() == 1


def test_rotas_de_candidatura_casam_antes_do_detalhe(painel: Painel) -> None:
    """E7: `/vagas/{id}/candidatura` não pode cair numa rota de `/vagas/{id}/...` que vem antes."""
    propria = [r for r in candidatura.router.routes if hasattr(r, "methods")]
    assert propria
    for rota in propria:
        caminho = rota.path.replace("{vaga_id}", "1")  # type: ignore[attr-defined]
        for metodo in rota.methods:
            escopo = {"type": "http", "path": caminho, "method": metodo}
            # o FastAPI novo agrupa cada `include_router` num `_IncludedRouter`: quem casa primeiro
            # é o roteador, e o `matches` já confere caminho e método (FULL)
            primeira = next(r for r in painel.app.routes if r.matches(escopo)[0] == Match.FULL)
            assert primeira.original_router is candidatura.router  # type: ignore[attr-defined]
