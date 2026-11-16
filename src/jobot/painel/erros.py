"""Erro do servidor vira página amigável ou, em pedido HTMX, um aviso curto (D106; T150).

O texto sai do status, nunca do `detail` nem da exceção: o `detail` do código não é para a
tela. O fragmento HTMX `<p data-aviso-erro>` é o contrato com o `app.js` (T151).
"""

import logging
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from markupsafe import escape
from starlette.exceptions import HTTPException

from jobot.painel import seguranca
from jobot.painel.i18n import idioma_inicial, t

_LOG = logging.getLogger(__name__)
_TIPO = {
    403: "desatualizada",
    404: "nao_existe",
    422: "invalido",
    500: "interno",
    503: "indisponivel",
}


def _aparencia(request: Request) -> tuple[str, str, str]:
    """O idioma, o tema e o tamanho do texto salvos; com o banco ilegível, o do `Accept-Language`
    e os padrões. Tudo lido no mesmo `try`: um valor torto não derruba a página de erro."""
    try:
        return (seguranca.idioma_do_pedido(request), *seguranca.tema_e_texto(request))
    except Exception:  # o erro pode ser o do próprio banco: a página sai mesmo assim
        return idioma_inicial(request.headers.get("accept-language")), "sistema", "padrao"


def _minima(
    idioma: str, tema: str, tamanho_texto: str, titulo: str, texto: str, inicio: str
) -> str:
    """A página sem a casca, no mesmo visual, para quando montar a casca também falha."""
    return (
        f'<!doctype html><html lang="{escape(idioma)}" data-tema="{escape(tema)}"'
        f' data-texto="{escape(tamanho_texto)}"><head>'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{escape(titulo)} · joBot</title><link rel="icon" href="data:,">'
        '<link rel="stylesheet" href="/static/css/base.css">'
        '<link rel="stylesheet" href="/static/css/vagas.css">'
        '<link rel="stylesheet" href="/static/css/detalhe.css"></head><body>'
        f'<main id="conteudo"><div class="vazio"><h1>{escape(titulo)}</h1>'
        f'<p>{escape(texto)}</p><a class="primario" href="/">{escape(inicio)}</a>'
        "</div></main></body></html>"
    )


def _responder(request: Request, status: int, cabecalhos: Mapping[str, str] | None) -> Response:
    idioma, tema, tamanho_texto = _aparencia(request)
    tipo = _TIPO.get(status, "outro")
    if status == 403:  # o único 403 é o do CSRF: o texto é o do `detail`, sem lê-lo da exceção
        texto = t(idioma, "seguranca.recarregue")
    else:
        log = Path(request.app.state.banco).parent / "logs" / "jobot.log"
        texto = t(idioma, f"erro.{tipo}.texto", log=log)
    if request.headers.get("hx-request") == "true":
        corpo = f"<p data-aviso-erro>{escape(texto)}</p>"
        return HTMLResponse(corpo, status_code=status, headers=cabecalhos)
    titulo = t(idioma, f"erro.{tipo}.titulo")
    contexto = {
        "t": lambda chave, **params: t(idioma, chave, **params),
        "idioma": idioma,
        "tema": tema,
        "tamanho_texto": tamanho_texto,
        "csrf_token": seguranca.csrf_token(request),
        "titulo": titulo,
        "texto": texto,
    }
    try:
        return seguranca.TEMPLATES.TemplateResponse(
            request, "erro/pagina.html", contexto, status_code=status, headers=cabecalhos
        )
    except Exception:
        _LOG.exception("a casca da página de erro falhou em %r", request.url.path)
        inicio = t(idioma, "erro.inicio")
        return HTMLResponse(
            _minima(idioma, tema, tamanho_texto, titulo, texto, inicio),
            status_code=status,
            headers=cabecalhos,
        )


def registrar(app: FastAPI, cabecalhos_de_seguranca: Mapping[str, str]) -> None:
    """Liga os handlers; o do 500 roda fora dos middlewares e põe os cabeçalhos ele mesmo."""

    async def http(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, HTTPException)
        return _responder(request, exc.status_code, exc.headers)

    async def validacao(request: Request, exc: Exception) -> Response:
        return _responder(request, 422, None)

    async def interno(request: Request, exc: Exception) -> Response:
        _LOG.exception("erro em %s %r", request.method, request.url.path, exc_info=exc)
        resposta = _responder(request, 500, None)
        resposta.headers.update(cabecalhos_de_seguranca)
        return resposta

    app.add_exception_handler(HTTPException, http)
    app.add_exception_handler(RequestValidationError, validacao)
    app.add_exception_handler(Exception, interno)
