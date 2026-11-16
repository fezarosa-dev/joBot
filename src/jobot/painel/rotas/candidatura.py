"""Registro da abertura da candidatura (plano T284, desenho 5.5)."""

from fastapi import APIRouter, HTTPException, Request, Response

from jobot.banco import acoes
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.rotas.vagas import VagaId
from jobot.painel.seguranca import Con

router = APIRouter()


@router.post("/vagas/{vaga_id}/candidatura")
async def abriu(request: Request, con: Con, vaga_id: VagaId) -> Response:
    """Melhor esforço: 204 grave ou não (vaga fora de `nova`/`salva` não grava); sem vaga, 404."""
    try:
        acoes.abriu_candidatura(con, vaga_id, relogio_do_painel(request).agora())
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return Response(status_code=204)
