"""Conexão por pedido, CSRF e renderização dos templates (desenho 14.3 e 14.4)."""

import hmac
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

from jobot.banco.cadastros import ler_config
from jobot.banco.conexao import abrir
from jobot.painel import globais
from jobot.painel.i18n import idioma_inicial, t
from jobot.sistema.sair import CABECALHO as CABECALHO_SAIR

Tema = Literal["sistema", "claro", "escuro"]
TEMAS: tuple[Tema, ...] = ("sistema", "claro", "escuro")
TamanhoTexto = Literal["padrao", "grande", "maior"]
TAMANHOS_TEXTO: tuple[TamanhoTexto, ...] = ("padrao", "grande", "maior")
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
            salvo = ler_config(con, "idioma", None)  # JSON estragado vale o padrão, sem 500
        if salvo in ("pt", "en"):
            return str(salvo)
    return idioma_inicial(request.headers.get("accept-language"))


def tema_e_texto(request: Request) -> tuple[str, str]:
    """O tema e o tamanho do texto salvos na configuração, lidos numa conexão só.

    Sem a chave, `sistema` (segue o `prefers-color-scheme`) e `padrao`.
    """
    banco: Path = request.app.state.banco
    tema, texto = "sistema", "padrao"
    if banco.exists():  # sem banco ainda, não cria um arquivo vazio só para ler
        with closing(abrir(banco)) as con:
            salvo_tema = ler_config(con, "tema", tema)
            salvo_texto = ler_config(con, "tamanho_texto", texto)
        if salvo_tema in TEMAS:
            tema = str(salvo_tema)
        if salvo_texto in TAMANHOS_TEXTO:
            texto = str(salvo_texto)
    return tema, texto


async def exigir_csrf(request: Request) -> None:
    """Todo método que muda dados: origem do próprio painel e token certo, senão 403.

    Exceção: o `POST /sair` com o cabeçalho `X-Jobot-Sair` decide só pelo segredo local.
    """
    if request.method in METODOS_SEGUROS:
        return
    if request.url.path == "/sair" and (segredo := request.headers.get(CABECALHO_SAIR)) is not None:
        # parada local (desenho 6.1): o segredo do `sair.token` vale no lugar do CSRF, só de
        # 127.0.0.1; presente e errado é 403, mesmo com o CSRF certo
        esperado: str | None = getattr(request.app.state, "sair_token", None)
        cliente = request.client.host if request.client else None
        if (
            esperado
            and cliente == "127.0.0.1"
            and hmac.compare_digest(segredo.encode(), esperado.encode())
        ):
            return
        raise HTTPException(403, detail=t(idioma_do_pedido(request), "seguranca.recarregue"))
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


def caminho_do_painel(voltar: str) -> str:
    """Caminho e consulta de `voltar` se for caminho do próprio painel; senão, `/` (E21).

    Sem esquema, sem host, começa com `/`, não com `//`, e sem `\\` (sem open redirect).
    """
    partes = urlsplit(voltar)  # o urlsplit já tira tab e quebra de linha, como o navegador
    local = not partes.scheme and not partes.netloc and partes.path.startswith("/")
    if not local or partes.path.startswith("//") or "\\" in partes.path:
        return "/"
    return urlunsplit(("", "", partes.path, partes.query, ""))


def de_volta(voltar: str) -> RedirectResponse:
    """Volta para a página de onde veio, só se for caminho do próprio painel (sem open redirect).

    O `Referrer-Policy: no-referrer` tira o `Referer`, por isso a página manda `voltar`.
    """
    return RedirectResponse(caminho_do_painel(voltar), status_code=303)


def renderizar(request: Request, modelo: str, **ctx: Any) -> HTMLResponse:
    """Página do template com `t(chave, **params)`, o idioma, o tema, o tamanho do texto, o CSRF."""
    idioma = idioma_do_pedido(request)
    tema, tamanho_texto = tema_e_texto(request)

    def traduzir(chave: str, **params: object) -> str:
        return t(idioma, chave, **params)

    contexto = {
        "t": traduzir,
        "idioma": idioma,
        "tema": tema,
        "tamanho_texto": tamanho_texto,
        "csrf_token": csrf_token(request),
        **ctx,
    }
    return TEMPLATES.TemplateResponse(request, modelo, contexto)
