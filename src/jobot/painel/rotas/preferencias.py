"""Tema, idioma e tamanho do texto (desenho 13.2 e 13.11; visual Mac 5.1).

Grava as chaves `tema`, `idioma` e `tamanho_texto` da configuração. O tema e o tamanho salvos chegam
ao `base.html` pelo contexto do `renderizar` (`seguranca.py`): o servidor já manda
`<html data-tema data-texto>` certos, sem piscar.
"""

import json
import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from jobot.painel.seguranca import Con, TamanhoTexto, Tema, de_volta

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


@router.post("/texto")
async def mudar_texto(
    con: Con, tamanho: Annotated[TamanhoTexto, Form()], voltar: Annotated[str, Form()] = "/"
) -> RedirectResponse:
    _gravar(con, "tamanho_texto", tamanho)
    return de_volta(voltar)
