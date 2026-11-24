"""Aba Serviços: a chave do 2Captcha e o interruptor (plano T184; ADR 0014 e 0022) e as chaves de
IA (T414; desenho 10.3 da fase 4): Anthropic, OpenAI, Gemini e o compatível com OpenAI (endereço e
chave opcional). Guardar uma chave de IA não liga nada: só a aba IA liga uma tarefa.

A chave mora no cofre (`sistema/cofre.py`) e nunca volta ao HTML, à URL, ao log nem à mensagem de
erro: a tela mostra a máscara. Toda chamada ao cofre passa por `no_cofre`: roda numa thread e tem
prazo, porque o cofre do sistema pode travar (cofre trancado esperando senha).
O formulário da chave (`POST /configuracoes/servicos`) fica em `configuracoes.py`, que já tem a
página; este módulo não importa aquele. Com o campo `servico`, o formulário é de uma chave de IA e
`gravar_chave_ia` faz o trabalho.
"""

import asyncio
import logging
import re
from collections.abc import Callable
from typing import Any, Final

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData

from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.captcha import NOME_NO_COFRE, TETO_DIA
from jobot.navegador import limites
from jobot.nucleo.captcha import ErroCaptcha, Falha, mascarar, saldo, validar_chave
from jobot.nucleo.ia.compativel_openai import conferir_endereco
from jobot.painel.ambiente import cofre_do_painel
from jobot.painel.cliente import cliente_do_painel
from jobot.painel.formatos import decimal_curto
from jobot.painel.i18n import t
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar

router = APIRouter(prefix="/configuracoes/servicos")
_LOG = logging.getLogger(__name__)

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
        return await asyncio.wait_for(run_in_threadpool(func, *args), limites.PRAZO_COFRE_S)
    except TimeoutError as erro:
        _LOG.warning("cofre: sem resposta em %s s (%s)", limites.PRAZO_COFRE_S, type(erro).__name__)
        raise OSError("o cofre não respondeu a tempo") from None


async def contexto_captcha(request: Request, con: Con) -> dict[str, Any]:
    """O que o cartão mostra; a chave em si nunca entra no contexto."""
    mascara = local = None
    falhou = request.query_params.get("erro") == "cofre"
    try:
        achado = await no_cofre(cofre_do_painel(request).ler, NOME_NO_COFRE)
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


@router.post("/captcha/interruptor")
async def interruptor(request: Request, con: Con) -> Response:
    ligar = "captcha_ligado" in await request.form()
    ctx = await contexto_captcha(request, con)
    if ligar and ctx["captcha"]["mascara"] is None:
        raise HTTPException(409)  # a trava não é só do HTML; desligar sempre pode
    gravar_config(con, "captcha_ligado", ligar)
    ctx["captcha"]["ligado"] = ligar
    return _cartao(request, ctx, foco=True)


@router.post("/captcha/apagar")
async def apagar(request: Request, con: Con) -> Response:
    gravar_config(con, "captcha_ligado", False)  # antes: sem chave não fica ligado
    falhou = False
    try:
        # shortcut: com o cofre travado espera até 2 prazos (apagar + reler o cartão) e a thread
        # que estourou ainda pode apagar depois; trocar quando o cofre tiver API assíncrona
        await no_cofre(cofre_do_painel(request).apagar, NOME_NO_COFRE)
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


@router.post("/captcha/testar")
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
            achado = await no_cofre(cofre_do_painel(request).ler, NOME_NO_COFRE)
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


# --- chaves de IA (T414) -------------------------------------------------------------------

# a ordem dos cartões na aba; no cofre, `ia_<servico>`, que a `FabricaIA` do `serve` lê
SERVICOS_IA: Final = ("anthropic", "openai", "gemini", "compativel")
# a chave vai no cabeçalho `Authorization`: só ASCII visível, sem espaço (D201.3)
_CHAVE_IA: Final = re.compile(r"[!-~]{8,512}")
TETO_ENDERECO: Final = 2048
_CARTAO_IA = "configuracoes/_cartao_chave_ia.html"


def _endereco_salvo(con: Con) -> str:
    valor = ler_config(con, "ia_compativel", {})
    endereco = valor.get("endereco") if isinstance(valor, dict) else None
    return endereco if isinstance(endereco, str) else ""


async def _cartao_ia(request: Request, con: Con, servico: str) -> dict[str, Any]:
    """O que um cartão de IA mostra; a chave em si nunca entra no contexto."""
    mascara = local = None
    falhou = request.query_params.get("erro") == f"cofre-ia-{servico}"
    try:
        achado = await no_cofre(cofre_do_painel(request).ler, f"ia_{servico}")
    except OSError as erro:
        _LOG.warning("ia: não consegui ler a chave de %s: %s", servico, type(erro).__name__)
        falhou = True
    else:
        if achado is not None:
            mascara, local = mascarar(achado[0]), achado[1]
    endereco = _endereco_salvo(con) if servico == "compativel" else ""
    return {
        "servico": servico,
        "mascara": mascara,
        "local": local,
        "falhou": falhou,
        "endereco": endereco,
        "apagavel": mascara is not None or bool(endereco),
    }


async def contexto_chaves_ia(request: Request, con: Con) -> dict[str, Any]:
    # as leituras correm juntas: com o cofre travado, a página espera um prazo, não quatro
    cartoes = await asyncio.gather(*(_cartao_ia(request, con, s) for s in SERVICOS_IA))
    return {"chaves_ia": list(cartoes)}


async def contexto_servicos(request: Request, con: Con) -> dict[str, Any]:
    # shortcut: com o cofre travado, cada abertura da aba deixa presas 5 threads (2Captcha + 4 IA)
    # no threadpool do anyio (40); se pesar, uma leitura só do cofre ou um semáforo (D201.7)
    return await contexto_captcha(request, con) | await contexto_chaves_ia(request, con)


async def gravar_chave_ia(
    request: Request, con: Con, form: FormData
) -> tuple[int, dict[str, Any]] | None:
    """Grava a chave (e o endereço do compatível) de `form`; `None` deu certo. Senão, o status e o
    `erro_ia` da página (o cartão, a chave i18n, o campo e o endereço digitado). Nada é gravado
    com erro."""
    servico = form.get("servico")
    if not isinstance(servico, str) or servico not in SERVICOS_IA:
        raise HTTPException(422)
    bruto, digitado = form.get("chave"), form.get("endereco")
    chave = bruto.strip() if isinstance(bruto, str) else ""
    endereco = digitado if isinstance(digitado, str) else ""

    def volta(status: int, erro: str, campo: str | None) -> tuple[int, dict[str, Any]]:
        # o endereço digitado volta para corrigir; a chave nunca volta, nem o endereço com `@`,
        # que pode trazer usuário e senha (desenho 11; D201.2)
        de_volta = "" if "@" in endereco else endereco
        return status, {
            "erro_ia": {"servico": servico, "erro": erro, "campo": campo, "endereco": de_volta}
        }

    if chave and not _CHAVE_IA.fullmatch(chave):
        return volta(422, "configuracoes.servicos.ia.erro.chave", "chave")
    if servico == "compativel":
        try:
            if len(endereco) > TETO_ENDERECO:
                raise ValueError("endereço da IA longo demais")
            endereco = conferir_endereco(endereco)
        except ValueError:  # a mensagem não vai a lugar nenhum: pode trazer uma senha
            return volta(422, "configuracoes.servicos.ia.erro.endereco", "endereco")
    if chave:
        try:
            # shortcut: com o cofre travado espera até 2 prazos, como a chave do 2Captcha
            await no_cofre(cofre_do_painel(request).gravar, f"ia_{servico}", chave)
        except OSError as erro:  # só o tipo vai ao log, nunca a chave
            _LOG.warning("ia: não consegui gravar a chave de %s: %s", servico, type(erro).__name__)
            return volta(200, "configuracoes.servicos.erro.cofre", None)
    if servico == "compativel":  # depois da chave: cofre que falhou não deixa meio gravado
        gravar_config(con, "ia_compativel", {"endereco": endereco})
    return None


@router.post("/ia/{servico}/apagar")
async def apagar_ia(request: Request, con: Con, servico: str) -> Response:
    """Apaga a chave do serviço; no compatível, também o endereço (antes da chave: sem endereço,
    nada sai)."""
    if servico not in SERVICOS_IA:
        raise HTTPException(404)
    if servico == "compativel":
        gravar_config(con, "ia_compativel", {"endereco": ""})
    falhou = False
    try:
        await no_cofre(cofre_do_painel(request).apagar, f"ia_{servico}")
    except OSError as erro:
        _LOG.warning("ia: não consegui apagar a chave de %s: %s", servico, type(erro).__name__)
        falhou = True
    if request.headers.get("hx-request") != "true":
        sufixo = f"?erro=cofre-ia-{servico}" if falhou else "?salvo=1"
        return RedirectResponse(_VOLTA + sufixo, 303)
    cartao = await _cartao_ia(request, con, servico)
    cartao["falhou"] = falhou or cartao["falhou"]
    return renderizar(request, _CARTAO_IA, cartao=cartao, cartao_salvo=not falhou, foco_chave=True)
