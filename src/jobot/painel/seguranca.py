"""Conexão por pedido, CSRF e renderização dos templates (desenho 14.3 e 14.4)."""

import hmac
import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import closing
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit, urlunsplit

import jinja2
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from jobot.banco.conexao import abrir
from jobot.painel import globais
from jobot.painel.i18n import idioma_inicial, t

Tema = Literal["sistema", "claro", "escuro"]
TEMAS: tuple[Tema, ...] = ("sistema", "claro", "escuro")
CAMPO_CSRF = "csrf_token"
CABECALHO_CSRF = "X-CSRF-Token"
METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
# autoescape=True (e não select_autoescape): escapa em qualquer extensão de template
TEMPLATES = Jinja2Templates(
    env=jinja2.Environment(
        loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True
    )
)
globais.registrar(TEMPLATES.env)


async def conexao(request: Request) -> AsyncIterator[sqlite3.Connection]:
    """Uma conexão por pedido, fechada no fim.

    É `async`: abre na thread do laço, então a rota que usa `Con` também é `async def`
    (o `abrir` não passa `check_same_thread=False`; rota síncrona roda noutra thread).
    """
    con = abrir(request.app.state.banco)
    try:
        yield con
    finally:
        con.close()


Con = Annotated[sqlite3.Connection, Depends(conexao)]


def csrf_token(request: Request) -> str:
    """Token do processo: nasce no `criar_app` e só vive na memória."""
    token: str = request.app.state.csrf
    return token


def idioma_do_pedido(request: Request) -> str:
    """O idioma salvo na configuração; sem ele, o do `Accept-Language` (desenho 13.10).

    Abre uma conexão curta, criada e fechada na thread de quem chama: vale também para a rota
    sem `Con` (inclusive síncrona) e para o 403 do CSRF, que roda antes do `Con`.
    """
    banco: Path = request.app.state.banco
    if banco.exists():  # sem banco ainda, não cria um arquivo vazio só para ler
        with closing(abrir(banco)) as con:
            linha = con.execute("SELECT valor FROM config WHERE chave = 'idioma'").fetchone()
        if linha is not None:
            salvo = json.loads(linha[0])
            if salvo in ("pt", "en"):
                return str(salvo)
    return idioma_inicial(request.headers.get("accept-language"))


def _tema(request: Request) -> str:
    """O tema salvo na configuração; sem ele, `sistema` (segue o `prefers-color-scheme`)."""
    banco: Path = request.app.state.banco
    if banco.exists():  # sem banco ainda, não cria um arquivo vazio só para ler
        with closing(abrir(banco)) as con:
            linha = con.execute("SELECT valor FROM config WHERE chave = 'tema'").fetchone()
        if linha is not None and (salvo := json.loads(linha[0])) in TEMAS:
            return str(salvo)
    return "sistema"


async def exigir_csrf(request: Request) -> None:
    """Todo método que muda dados: origem do próprio painel e token certo, senão 403."""
    if request.method in METODOS_SEGUROS:
        return
    origem = request.headers.get("origin")
    enviado = request.headers.get(CABECALHO_CSRF)
    if enviado is None:
        campo = (await request.form()).get(CAMPO_CSRF)
        enviado = campo if isinstance(campo, str) else ""
    if (
        request.headers.get("sec-fetch-site") == "cross-site"
        or (origem is not None and origem != f"http://{request.headers.get('host')}")
        or not hmac.compare_digest(enviado.encode(), csrf_token(request).encode())
    ):
        raise HTTPException(403, detail=t(idioma_do_pedido(request), "seguranca.recarregue"))


def _de_volta(voltar: str) -> RedirectResponse:
    """Volta para a página de onde veio, só se for caminho do próprio painel (sem open redirect).

    O `Referrer-Policy: no-referrer` tira o `Referer`, por isso a página manda `voltar`.
    """
    partes = urlsplit(voltar)  # o urlsplit já tira tab e quebra de linha, como o navegador
    local = not partes.scheme and not partes.netloc and partes.path.startswith("/")
    if not local or partes.path.startswith("//") or "\\" in partes.path:
        return RedirectResponse("/", status_code=303)
    return RedirectResponse(urlunsplit(("", "", partes.path, partes.query, "")), status_code=303)


def renderizar(request: Request, modelo: str, **ctx: Any) -> HTMLResponse:
    """Página do template com `t(chave, **params)`, o idioma, o tema salvo e o token CSRF."""
    idioma = idioma_do_pedido(request)

    def traduzir(chave: str, **params: object) -> str:
        return t(idioma, chave, **params)

    contexto = {
        "t": traduzir,
        "idioma": idioma,
        "tema": _tema(request),
        "csrf_token": csrf_token(request),
        **ctx,
    }
    return TEMPLATES.TemplateResponse(request, modelo, contexto)
