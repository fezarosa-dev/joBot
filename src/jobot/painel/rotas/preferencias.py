"""Troca rápida de tema e idioma na casca (desenho 13.2 e 13.11).

Grava as mesmas chaves `tema` e `idioma` da configuração. O tema salvo chega ao `base.html`
pelo contexto do `renderizar` (`seguranca.py`): o servidor já manda `<html data-tema>` certo,
sem piscar.
"""

import json
import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from jobot.painel.seguranca import Con, Tema, de_volta

router = APIRouter(prefix="/preferencias")


def _gravar(con: sqlite3.Connection, chave: str, valor: str) -> None:
    con.execute(
        "INSERT INTO config (chave, valor) VALUES (?, ?)"
        " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, json.dumps(valor)),
    )
    con.commit()


@router.post("/tema")
async def mudar_tema(
    con: Con, tema: Annotated[Tema, Form()], voltar: Annotated[str, Form()] = "/"
) -> RedirectResponse:
    _gravar(con, "tema", tema)
    return de_volta(voltar)


@router.post("/idioma")
async def mudar_idioma(
    con: Con, idioma: Annotated[Literal["pt", "en"], Form()], voltar: Annotated[str, Form()] = "/"
) -> RedirectResponse:
    _gravar(con, "idioma", idioma)
    return de_volta(voltar)
