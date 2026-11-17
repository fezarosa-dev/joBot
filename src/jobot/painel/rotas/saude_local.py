"""`GET /saude-local`: diz que quem responde na porta é o joBot (desenho 13.2 e 12.6).

O `e_o_jobot` da T43 lê esta resposta antes de abrir o navegador. A casca lê `segundo_plano`
para saber se fecha o servidor junto com a janela (fase 3, desenho 5.5).
"""

from fastapi import APIRouter

from jobot import __version__
from jobot.banco.cadastros import ler_config
from jobot.painel.seguranca import Con

router = APIRouter()


@router.get("/saude-local")
async def saude_local(con: Con) -> dict[str, str | bool]:
    # `is True`: a config guarda qualquer JSON; só o booleano gravado liga (sem linha = desligado).
    ligado = ler_config(con, "segundo_plano", False) is True
    return {"app": "jobot", "versao": __version__, "segundo_plano": ligado}
