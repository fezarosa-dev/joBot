"""Troca rápida de tema e idioma na casca (desenho 13.2 e 13.11).

Grava as mesmas chaves `tema` e `idioma` da configuração. O tema salvo chega ao `base.html`
pelo contexto do `renderizar` (`seguranca.py`): o servidor já manda `<html data-tema>` certo,
sem piscar.
"""

import json
import sqlite3
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from jobot.painel.seguranca import Con, Tema

router = APIRouter(prefix="/preferencias")


def _gravar(con: sqlite3.Connection, chave: str, valor: str) -> None:
    con.execute(
        "INSERT INTO config (chave, valor) VALUES (?, ?)"
        " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, json.dumps(valor)),
    )
    con.commit()


def _de_volta(voltar: str) -> RedirectResponse:
    """Volta para a página de onde veio, só se for caminho do próprio painel (sem open redirect).

    O `Referrer-Policy: no-referrer` tira o `Referer`, por isso a página manda `voltar`.
    """
    partes = urlsplit(voltar)  # o urlsplit já tira tab e quebra de linha, como o navegador
    local = not partes.scheme and not partes.netloc and partes.path.startswith("/")
    if not local or partes.path.startswith("//") or "\\" in partes.path:
        return RedirectResponse("/", status_code=303)
    return RedirectResponse(urlunsplit(("", "", partes.path, partes.query, "")), status_code=303)


@router.post("/tema")
async def mudar_tema(
    con: Con, tema: Annotated[Tema, Form()], voltar: Annotated[str, Form()] = "/"
) -> RedirectResponse:
    _gravar(con, "tema", tema)
    return _de_volta(voltar)


@router.post("/idioma")
async def mudar_idioma(
    con: Con, idioma: Annotated[Literal["pt", "en"], Form()], voltar: Annotated[str, Form()] = "/"
) -> RedirectResponse:
    _gravar(con, "idioma", idioma)
    return _de_volta(voltar)
