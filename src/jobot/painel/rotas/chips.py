"""`GET /vagas/chips`: os chips de filtro com contagem, que a lista não espera (T191, D129).

Fica neste arquivo porque o app inclui as rotas em ordem alfabética e `detalhe.py` tem
`/vagas/{vaga_id}`: sem vir antes dele, `/vagas/chips` cairia ali e daria 422.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from jobot.painel.moeda import exibicao_do_painel
from jobot.painel.rotas.vagas import _grupos, _ler_estado, _vary, relogio_do_painel
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar

router = APIRouter()


@router.get("/vagas/chips")
async def chips(request: Request, con: Con) -> HTMLResponse:
    agora = relogio_do_painel(request).agora()
    ex = exibicao_do_painel(con, agora.astimezone().date())
    estado = _ler_estado(request.query_params, con, ex)
    grupos = [] if estado.e_destaques else _grupos(con, estado, agora, idioma_do_pedido(request))
    return _vary(renderizar(request, "vagas/chips.html", grupos=grupos))
