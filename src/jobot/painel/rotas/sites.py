"""Sites: as páginas que a pessoa acompanha, adicionar, desativar e remover (plano T75, T112).

O endereço digitado passa pela mesma barreira da leitura (`conferir_endereco`,
DR-19): endereço interno, nome que resolve para rede local ou que não resolve é recusado com uma
mensagem e o texto de volta (422), nunca 500. A rota não baixa a página; quem lê é a execução
`paginas`. Página que não existe é 404. `app.state.resolvedor` troca o DNS nos testes.
O texto e o nome vêm de terceiro e da pessoa: o Jinja os escapa, nada é HTML.
"""

import asyncio
import sqlite3
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from jobot.banco.paginas import (
    MudancaPagina,
    adicionar_pagina,
    desativar_pagina,
    mudancas,
    paginas,
    remover_pagina,
)
from jobot.nucleo.coletores.paginas import Pagina, conferir_endereco
from jobot.nucleo.http import ErroDeRede
from jobot.painel.seguranca import Con, renderizar

router = APIRouter(prefix="/sites")

PaginaId = Annotated[int, Path(ge=1, le=2**63 - 1)]  # o INTEGER do SQLite tem 64 bits com sinal
_MAX_NOME = 100
_MAX_ENDERECO = 500
_PRAZO_DNS_S = 15.0
_MUDANCAS_POR_PAGINA = 5


@dataclass(frozen=True)
class Formulario:
    """O que a pessoa digitou: volta igual ao formulário num erro."""

    url: str = ""
    nome: str = ""


@dataclass(frozen=True)
class Linha:
    p: Pagina
    mudancas: list[MudancaPagina]  # as mais novas primeiro, no máximo `_MUDANCAS_POR_PAGINA`


def _texto(valor: object) -> str:
    return "".join(c for c in valor if c.isprintable()).strip() if isinstance(valor, str) else ""


def _linhas(con: sqlite3.Connection) -> list[Linha]:
    por_pagina: dict[int, list[MudancaPagina]] = {}
    for m in mudancas(con):
        por_pagina.setdefault(m.pagina_id, []).append(m)
    return [Linha(p, por_pagina.get(p.id, [])[:_MUDANCAS_POR_PAGINA]) for p in paginas(con)]


def _pagina(
    request: Request, con: sqlite3.Connection, f: Formulario = Formulario(), erro: str | None = None
) -> HTMLResponse:
    resposta = renderizar(request, "sites/lista.html", linhas=_linhas(con), f=f, erro=erro)
    resposta.status_code = 422 if erro else 200
    return resposta


async def _conferir(request: Request, f: Formulario) -> str | None:
    """A chave de i18n do erro, ou `None` se a pessoa pode acompanhar esse endereço."""
    if not f.nome or len(f.nome) > _MAX_NOME:
        return "sites.erro.nome"
    if not f.url or len(f.url) > _MAX_ENDERECO:
        return "sites.erro.endereco"
    try:
        async with asyncio.timeout(_PRAZO_DNS_S):
            await conferir_endereco(f.url, getattr(request.app.state, "resolvedor", None))
    except ValueError, ErroDeRede, TimeoutError:
        return "sites.erro.endereco"
    return None


@router.get("")
async def lista(request: Request, con: Con) -> HTMLResponse:
    return _pagina(request, con)


@router.post("")
async def adicionar(request: Request, con: Con) -> Response:
    form = await request.form()
    f = Formulario(url=_texto(form.get("url")), nome=_texto(form.get("nome")))
    erro = await _conferir(request, f)
    if erro is None:
        try:
            adicionar_pagina(con, f.url, f.nome)
        except ValueError:  # a mesma regra, vista de novo pelo banco
            erro = "sites.erro.endereco"
    if erro:
        return _pagina(request, con, f, erro)
    return RedirectResponse("/sites", status_code=303)


@router.post("/{pagina_id}/desativar")
async def desativar(con: Con, pagina_id: PaginaId) -> Response:
    try:
        desativar_pagina(con, pagina_id)
    except LookupError as erro:
        raise HTTPException(404) from erro
    return RedirectResponse("/sites", status_code=303)


@router.post("/{pagina_id}/remover")
async def remover(con: Con, pagina_id: PaginaId) -> Response:
    try:
        remover_pagina(con, pagina_id)
    except LookupError as erro:
        raise HTTPException(404) from erro
    return RedirectResponse("/sites", status_code=303)
