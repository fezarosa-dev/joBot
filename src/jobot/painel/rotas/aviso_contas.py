"""`GET /aviso-contas`: fragmento HTMX da faixa de queda de sessão no topo (plano T276; E11, E14).

Lê só o que a conferência gravou em `sessao_site` e `sessao_conta`; não faz pedido nenhum. Sem
queda aberta, o fragmento sai vazio. A faixa não tem botão de fechar: some quando a queda fecha.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from jobot.nucleo import gmail
from jobot.painel.ambiente import leitores_do_painel
from jobot.painel.consultas import contas_em_queda
from jobot.painel.seguranca import Con, renderizar

router = APIRouter()


@router.get("/aviso-contas")
async def aviso_contas(request: Request, con: Con) -> HTMLResponse:
    # sem leitor só o Gmail pode cair: a faixa vale sem leitor (D167; E11, E13)
    contas = contas_em_queda(con, leitores_do_painel(request))
    so_gmail = [chave for chave, _ in contas] == [gmail.CONTA]
    return renderizar(request, "aviso_contas/aviso.html", contas=contas, so_gmail=so_gmail)
