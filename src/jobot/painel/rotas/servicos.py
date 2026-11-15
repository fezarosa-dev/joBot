"""Aba Serviços: a chave do 2Captcha e o interruptor (plano T184; ADR 0014 e 0022).

A chave mora no cofre (`sistema/cofre.py`) e nunca volta ao HTML, à URL, ao log nem à mensagem de
erro: a tela mostra a máscara. Toda chamada ao cofre passa por `no_cofre`: roda numa thread e tem
prazo, porque o cofre do sistema pode travar (cofre trancado esperando senha).
O formulário da chave (`POST /configuracoes/servicos`) fica em `configuracoes.py`, que já tem a
página; este módulo não importa aquele.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.captcha import TETO_DIA
from jobot.nucleo.captcha import ErroCaptcha, Falha, mascarar, saldo, validar_chave
from jobot.painel.ambiente import cofre_do_painel
from jobot.painel.cliente import cliente_do_painel
from jobot.painel.formatos import decimal_curto
from jobot.painel.i18n import t
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar

router = APIRouter(prefix="/configuracoes/servicos/captcha")
_LOG = logging.getLogger(__name__)

NOME = "2captcha"
PRAZO_COFRE_S = 15.0
PRAZO_TESTE_S = 30.0
_CARTAO = "configuracoes/_cartao_captcha.html"
_RESULTADO = "configuracoes/_resultado_captcha.html"
_VOLTA = "/configuracoes/servicos"


async def no_cofre[T](func: Callable[..., T], *args: object) -> T:
    """Chama o cofre numa thread, com prazo; estourar o prazo levanta `OSError`."""
    try:
        # shortcut: a thread do keyring fica presa até o cofre responder; com o cofre travado,
        # salvar ou apagar espera até 2 prazos (gravar + reler) e a thread do gravar que estourou
        # ainda pode gravar depois; trocar quando houver API assíncrona do cofre
        return await asyncio.wait_for(run_in_threadpool(func, *args), PRAZO_COFRE_S)
    except TimeoutError as erro:
        _LOG.warning("cofre: sem resposta em %s s (%s)", PRAZO_COFRE_S, type(erro).__name__)
        raise OSError("o cofre não respondeu a tempo") from None


async def contexto_captcha(request: Request, con: Con) -> dict[str, Any]:
    """O que o cartão mostra; a chave em si nunca entra no contexto."""
    mascara = local = None
    falhou = request.query_params.get("erro") == "cofre"
    try:
        achado = await no_cofre(cofre_do_painel(request).ler, NOME)
    except OSError as erro:
        _LOG.warning("2captcha: não consegui ler a chave: %s", type(erro).__name__)
        falhou = True
    else:
        if achado is not None:
            mascara, local = mascarar(achado[0]), achado[1]
    return {
        "captcha": {
            "ligado": mascara is not None and ler_config(con, "captcha_ligado") is True,
            "mascara": mascara,
            "local": local,
            "falhou": falhou,
            "teto": TETO_DIA,
        }
    }


def _cartao(
    request: Request,
    ctx: dict[str, Any],
    salvo: bool = True,
    foco: bool = False,
    foco_chave: bool = False,
) -> Response:
    # `foco` marca o interruptor, `foco_chave` o campo da chave (o botão Apagar some com a troca)
    return renderizar(request, _CARTAO, **ctx, cartao_salvo=salvo, foco=foco, foco_chave=foco_chave)


@router.post("/interruptor")
async def interruptor(request: Request, con: Con) -> Response:
    ligar = "captcha_ligado" in await request.form()
    ctx = await contexto_captcha(request, con)
    if ligar and ctx["captcha"]["mascara"] is None:
        raise HTTPException(409)  # a trava não é só do HTML; desligar sempre pode
    gravar_config(con, "captcha_ligado", ligar)
    ctx["captcha"]["ligado"] = ligar
    return _cartao(request, ctx, foco=True)


@router.post("/apagar")
async def apagar(request: Request, con: Con) -> Response:
    gravar_config(con, "captcha_ligado", False)  # antes: sem chave não fica ligado
    falhou = False
    try:
        # shortcut: com o cofre travado espera até 2 prazos (apagar + reler o cartão) e a thread
        # que estourou ainda pode apagar depois; trocar quando o cofre tiver API assíncrona
        await no_cofre(cofre_do_painel(request).apagar, NOME)
    except OSError as erro:
        _LOG.warning("2captcha: não consegui apagar a chave: %s", type(erro).__name__)
        falhou = True
    if request.headers.get("hx-request") != "true":
        return RedirectResponse(_VOLTA + ("?erro=cofre" if falhou else "?salvo=1"), 303)
    ctx = await contexto_captcha(request, con)
    ctx["captcha"]["falhou"] = falhou or ctx["captcha"]["falhou"]
    return _cartao(request, ctx, salvo=not falhou, foco_chave=True)


def _resultado(request: Request, ok: bool, chave: str, **params: object) -> Response:
    """Sempre 200: o resultado do teste é o conteúdo, e o HTMX só troca o corpo de um 2xx."""
    texto = t(idioma_do_pedido(request), chave, **params)
    return renderizar(request, _RESULTADO, ok=ok, texto=texto)


@router.post("/testar")
async def testar(request: Request) -> Response:
    """Consulta o saldo com a chave digitada, ou com a salva se o campo veio vazio; não grava."""
    bruto = (await request.form()).get("chave")
    digitada = bruto.strip() if isinstance(bruto, str) else ""
    if digitada:
        try:
            chave = validar_chave(digitada)
        except ValueError:
            return _resultado(request, False, "configuracoes.servicos.erro.formato")
    else:
        try:
            achado = await no_cofre(cofre_do_painel(request).ler, NOME)
        except OSError as erro:
            _LOG.warning("2captcha: não consegui ler a chave: %s", type(erro).__name__)
            return _resultado(request, False, "configuracoes.servicos.erro.cofre")
        if achado is None:
            return _resultado(request, False, "configuracoes.servicos.erro.sem_chave")
        chave = achado[0]
    try:
        async with cliente_do_painel(request) as cliente, asyncio.timeout(PRAZO_TESTE_S):
            valor = await saldo(cliente, chave)
    except (
        ErroCaptcha
    ) as erro:  # o núcleo nem sempre registra (resposta torta): só o valor da falha
        _LOG.warning("2captcha: o teste da chave falhou: %s", erro.falha.value)
        return _resultado(request, False, "captcha.erro." + erro.falha.value)
    except TimeoutError:
        _LOG.warning("2captcha: o teste da chave passou de %s s", PRAZO_TESTE_S)
        return _resultado(request, False, "captcha.erro." + Falha.TEMPO_ESGOTADO.value)
    saldo_texto = decimal_curto(valor, idioma_do_pedido(request))
    return _resultado(request, True, "configuracoes.servicos.captcha.ok", saldo=saldo_texto)
