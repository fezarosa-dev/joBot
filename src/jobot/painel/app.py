"""Monta o app do painel: segurança, rotas achadas sozinhas e estáticos (desenho 13 e 14)."""

import importlib
import pkgutil
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from jobot.painel import rotas
from jobot.painel.seguranca import exigir_csrf

ESTATICOS = Path(__file__).parent / "static"
CABECALHOS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def criar_app(dados: Path, porta: int) -> FastAPI:
    # sem /docs nem /openapi.json: a página de documentação puxa script de CDN
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(exigir_csrf)],  # vale para toda rota, inclusive as incluídas depois
    )
    app.state.csrf = secrets.token_urlsafe(32)
    app.state.banco = dados / "jobot.db"

    for modulo in pkgutil.iter_modules(rotas.__path__):
        app.include_router(importlib.import_module(f"{rotas.__name__}.{modulo.name}").router)
    if ESTATICOS.is_dir():
        app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}

    # adicionado por último, roda por fora: o 400 do Host também leva os cabeçalhos
    @app.middleware("http")
    async def cabecalhos(
        request: Request, seguinte: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # o TrustedHostMiddleware do Starlette compara só o nome; a porta é conferida aqui
        if request.headers.get("host") not in hosts:
            resposta: Response = PlainTextResponse("Invalid host header", status_code=400)
        else:
            resposta = await seguinte(request)
        resposta.headers.update(CABECALHOS)
        return resposta

    return app
