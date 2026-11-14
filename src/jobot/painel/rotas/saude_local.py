"""`GET /saude-local`: diz que quem responde na porta é o joBot (desenho 13.2 e 12.6).

O `e_o_jobot` da T43 lê esta resposta antes de abrir o navegador.
"""

from fastapi import APIRouter

from jobot import __version__

router = APIRouter()


@router.get("/saude-local")
async def saude_local() -> dict[str, str]:
    return {"app": "jobot", "versao": __version__}
