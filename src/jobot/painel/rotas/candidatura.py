"""Abertura da candidatura e respostas da faixa (planos T284 e T285; desenho 5.5 e 5.6)."""

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, Request, Response

from jobot.banco import acoes
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.rotas import aviso_candidatura
from jobot.painel.rotas.vagas import VagaId
from jobot.painel.seguranca import Con, de_volta

router = APIRouter()


@router.post("/vagas/{vaga_id}/candidatura")
async def abriu(request: Request, con: Con, vaga_id: VagaId) -> Response:
    """Melhor esforço: 204 grave ou não (vaga fora de `nova`/`salva` não grava); sem vaga, 404."""
    try:
        acoes.abriu_candidatura(con, vaga_id, relogio_do_painel(request).agora())
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return Response(status_code=204)


def _depois(
    request: Request,
    con: sqlite3.Connection,
    vaga_id: int,
    voltar: str,
    confirmada: bool = False,
) -> Response:
    """Sem HTMX, volta à página; com ele, a faixa e os eventos (E20), mesmo sem mudança: quem
    escuta só relê o banco. A faixa não escuta o evento (desenho 5.6): a resposta já a troca."""
    if request.headers.get("hx-request") != "true":
        return de_volta(voltar)
    saida = aviso_candidatura.faixa(request, con, voltar, vaga_id if confirmada else None)
    saida.headers["HX-Trigger"] = f"candidatura-mudou, vaga-mudou-{vaga_id}"
    return saida


@router.post("/vagas/{vaga_id}/candidatura/resposta")
async def responder(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    resposta: Annotated[Literal["sim", "ainda_nao"], Form()],
    voltar: Annotated[str, Form()] = "/",
) -> Response:
    """Sim com troca de status mostra a confirmação com Desfazer; o resto, a próxima pendente."""
    agora = relogio_do_painel(request).agora()
    try:
        antes = acoes.responder_candidatura(con, vaga_id, resposta == "sim", agora)
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return _depois(request, con, vaga_id, voltar, confirmada=antes is not None)


@router.post("/vagas/{vaga_id}/candidatura/desfazer")
async def desfazer(
    request: Request, con: Con, vaga_id: VagaId, voltar: Annotated[str, Form()] = "/"
) -> Response:
    """Para onde a vaga volta, o servidor decide (E18); a pergunta não volta."""
    try:
        acoes.desfazer_candidatura(con, vaga_id, relogio_do_painel(request).agora())
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return _depois(request, con, vaga_id, voltar)


def espera_maxima(pedido: object) -> float:  # stub do vermelho
    return 0.0
