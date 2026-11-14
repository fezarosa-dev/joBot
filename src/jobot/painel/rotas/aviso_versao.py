"""`GET /aviso-versao`: fragmento HTMX do aviso de versão nova (plano T85; D31).

Lê só o que `agenda/versao.py` gravou; não faz pedido nenhum. Com o aviso desligado (o padrão)
ou sem versão maior que a instalada, o fragmento sai vazio.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from jobot.agenda.versao import versao_para_avisar
from jobot.painel.seguranca import Con, renderizar

router = APIRouter()


@router.get("/aviso-versao")
async def aviso_versao(request: Request, con: Con) -> HTMLResponse:
    return renderizar(request, "aviso_versao/aviso.html", versao=versao_para_avisar(con))
