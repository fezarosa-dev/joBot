"""`GET /aviso-contas`: fragmento HTMX da faixa de queda de sessão no topo (plano T276; E11, E14).

Lê só o que a conferência gravou em `sessao_site` e `sessao_conta`; não faz pedido nenhum. Sem
queda aberta, o fragmento sai vazio. A faixa não tem botão de fechar: some quando a queda fecha.
"""

import sqlite3
from collections.abc import Sequence

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from jobot.banco import cadastros
from jobot.banco.sessoes import ler_sessao, ler_sessoes
from jobot.nucleo import gmail
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.painel.ambiente import leitores_do_painel
from jobot.painel.seguranca import Con, renderizar

router = APIRouter()


def contas_em_queda(
    con: sqlite3.Connection, leitores: Sequence[LeitorComLogin]
) -> list[tuple[str, str]]:
    """Chave e nome das contas em queda: os sites na ordem dos leitores, o Gmail por último."""
    ligadas = {f.chave: f.ligada for f in cadastros.fontes(con)}
    sessoes = ler_sessoes(con, "site")
    quedas = [
        (leitor.chave, leitor.nome)
        for leitor in leitores
        if ligadas.get(leitor.chave, False)
        and (sessao := sessoes.get(leitor.chave)) is not None
        and sessao.queda_aberta
    ]
    do_gmail = ler_sessao(con, "conta", gmail.CONTA)
    if do_gmail is not None and do_gmail.queda_aberta:
        quedas.append((gmail.CONTA, "Gmail"))
    return quedas


@router.get("/aviso-contas")
async def aviso_contas(request: Request, con: Con) -> HTMLResponse:
    # sem leitor só o Gmail pode cair: a faixa vale sem leitor (D167; E11, E13)
    contas = contas_em_queda(con, leitores_do_painel(request))
    so_gmail = [chave for chave, _ in contas] == [gmail.CONTA]
    return renderizar(request, "aviso_contas/aviso.html", contas=contas, so_gmail=so_gmail)
