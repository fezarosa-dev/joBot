"""Saúde das fontes: rotas de listar, ligar e desligar (desenho 13.8; plano T50).

Os cartões e o estado vêm de `painel/saude_das_fontes.py` (T283). A tela nunca faz pedido para
fora: o link "reportar problema" só abre no clique (ADR 0014).
"""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from jobot.banco.cadastros import fontes, ligar_fonte
from jobot.banco.execucoes import HistoricoDoBanco
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.saude_das_fontes import cartoes
from jobot.painel.seguranca import Con, renderizar

router = APIRouter(prefix="/fontes")

Chave = Annotated[str, Path(min_length=1, max_length=100)]


@router.get("")
async def listar(request: Request, con: Con) -> HTMLResponse:
    relogio = relogio_do_painel(request)
    agora = relogio.agora()
    historico = HistoricoDoBanco(con, relogio)
    return renderizar(request, "fontes/pagina.html", cartoes=cartoes(con, agora, historico))


def _ligar(con: sqlite3.Connection, chave: str, ligada: bool) -> RedirectResponse:
    if any(f.chave == chave and f.com_login for f in fontes(con)):
        raise HTTPException(422, "site com login liga em Configurações > Contas")
    try:
        ligar_fonte(con, chave, ligada)
    except LookupError as erro:
        raise HTTPException(404, "fonte não existe") from erro
    return RedirectResponse("/fontes", status_code=303)


@router.post("/{chave}/ligar")
async def ligar(con: Con, chave: Chave) -> RedirectResponse:
    return _ligar(con, chave, True)


@router.post("/{chave}/desligar")
async def desligar(con: Con, chave: Chave) -> RedirectResponse:
    return _ligar(con, chave, False)
