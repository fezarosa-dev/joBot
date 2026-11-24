"""A faixa de versão nova e o "Atualizar agora" (plano T85 e T332; desenho 5.6 e 6.3; D31, D176).

`GET /aviso-versao` lê só o que `agenda/versao.py` gravou; não faz pedido nenhum. Com o aviso
desligado pela pessoa ou sem versão maior que a instalada, o fragmento sai vazio. A faixa não manda
abrir o terminal (ADR 0023): `POST /atualizar` dispara o `jobot atualizar` destacado, que para e
religa o servidor, e o app.js pergunta ao `/saude-local` até a versão mudar; sem HTMX, a página
"Atualizando…" se recarrega a cada 5 s. Dentro da janela de uma casca antiga (a marca no user
agent só vem da casca até a 0.4.0, que mostrava o painel nela), a faixa diz sempre que a janela é
velha, com ou sem versão nova do Python, e `POST /abrir-release` abre a página da release no
navegador da pessoa pelo Python (D208.4). A casca nova não mostra o painel: o controle avisa ele
mesmo (D207.12).
"""

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from jobot import __version__
from jobot.agenda.versao import versao_da_etiqueta, versao_para_avisar
from jobot.nucleo.quebra import URL_REPOSITORIO
from jobot.painel.ambiente import (
    abrir_endereco_do_painel,
    ambiente_do_painel,
    lancar_atualizacao_do_painel,
)
from jobot.painel.rotas.aviso_candidatura import voltar_da_pagina
from jobot.painel.seguranca import Con, de_volta, renderizar

router = APIRouter()
_LOG = logging.getLogger(__name__)

URL_RELEASE = f"{URL_REPOSITORIO}/releases/latest"
# a marca que a casca até a 0.4.0 acrescentava ao user agent (desenho 5.3); a 0.4.1 não a põe
_MARCA_CASCA = re.compile(
    r" joBot-casca/[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9} \((?:linux|windows|macos)\)"
)
_ERROS = {"nao_comecou": "aviso_versao.nao_comecou"}


class _Disparando:
    """O `jobot atualizar` sendo lançado: conta como rodando."""

    def poll(self) -> None:
        return None


def _janela_velha(request: Request) -> bool:
    """O painel está dentro da janela de uma casca antiga: só ela põe a marca no user agent."""
    return _MARCA_CASCA.search(request.headers.get("user-agent", "")) is not None


def _faixa(request: Request, con: Con, janela: str | None = None) -> HTMLResponse:
    return renderizar(
        request,
        "aviso_versao/aviso.html",
        versao=versao_para_avisar(con),
        janela_nova=_janela_velha(request),
        janela=janela,
        endereco=URL_RELEASE,
        voltar=voltar_da_pagina(request),
    )


@router.get("/aviso-versao")
async def aviso_versao(request: Request, con: Con) -> HTMLResponse:
    return _faixa(request, con)


@router.post("/atualizar")
async def atualizar(request: Request) -> Response:
    """Dispara o `jobot atualizar` uma vez; com ele ainda rodando, só responde a espera."""
    estado = request.app.state
    rodando = getattr(estado, "atualizacao", None)
    falhou = False
    if rodando is None or rodando.poll() is not None:
        # a marca entra antes do await: o segundo POST que chega durante o lançamento já a vê
        estado.atualizacao = _Disparando()
        lancar = lancar_atualizacao_do_painel(request)
        try:
            estado.atualizacao = await run_in_threadpool(
                lancar, estado.banco.parent, ambiente_do_painel(request)
            )
        except OSError:
            estado.atualizacao = None
            _LOG.warning("não deu para começar o jobot atualizar", exc_info=True)
            falhou = True
    if request.headers.get("hx-request") is None:
        destino = "?erro=nao_comecou" if falhou else f"?de={__version__}"
        return RedirectResponse("/atualizando" + destino, status_code=303)
    return renderizar(request, "aviso_versao/_atualizando.html", de=__version__, falhou=falhou)


@router.get("/atualizando")
async def atualizando(request: Request, de: str = "", erro: str = "") -> Response:
    """A espera sem JavaScript: volta ao painel quando a versão no ar não é mais a `de`."""
    antes = de if versao_da_etiqueta(de) is not None else __version__
    if antes != __version__:
        return RedirectResponse("/", status_code=303)
    return renderizar(
        request,
        "aviso_versao/atualizando.html",
        sem_barra=True,
        de=antes,
        erro=_ERROS.get(erro),
    )


@router.post("/abrir-release")
async def abrir_release(
    request: Request, con: Con, voltar: Annotated[str, Form()] = "/"
) -> Response:
    """Abre a página da release no navegador da pessoa; o painel não carrega nada de fora."""
    abrir = abrir_endereco_do_painel(request)
    try:
        aberta = await run_in_threadpool(abrir, URL_RELEASE)
    except OSError:
        _LOG.warning("não deu para abrir a página da release", exc_info=True)
        aberta = False
    if request.headers.get("hx-request") is None:
        return de_volta(voltar)
    return _faixa(request, con, "aberta" if aberta else "falhou")
