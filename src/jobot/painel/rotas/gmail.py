"""Cartão do Gmail na aba Contas (plano T278; desenho 5.7.1, ADR 0024, E6 a E13, E21).

A senha de app mora no cofre (`sistema/cofre.py`) e nunca volta ao HTML, à resposta, ao log nem à
mensagem de erro; o endereço também não vai ao log. Só o "ok" do Google grava: fora dele, nada vai
ao cofre nem ao banco (E10). As rotas moram em `/configuracoes/gmail/...`, fora do espaço
`/configuracoes/contas/{chave}/...` dos sites (E21). Todas respondem 200 com o cartão, como o
`_resultado` de Serviços: o HTMX só troca o corpo de um 2xx.
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from jobot.banco.sessoes import gravar_sessao, ler_sessao
from jobot.navegador import limites
from jobot.nucleo.contas import estado_na_tela, hora_visivel, pode_conferir
from jobot.nucleo.gmail import (
    CONTA,
    NOME_CONTA,
    NOME_SENHA,
    ResultadoGmail,
    conferir_gmail,
    estado_do_gmail,
    limpar_senha,
    validar_endereco,
)
from jobot.painel.ambiente import cofre_do_painel, imap_do_painel
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.formatos import conferido_texto
from jobot.painel.rotas.servicos import no_cofre
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar

router = APIRouter(prefix="/configuracoes/gmail")
_LOG = logging.getLogger(__name__)

PRAZO_GMAIL_S = 30.0
_CARTAO = "configuracoes/_cartao_gmail.html"
_MUDOU = "contas-mudou"  # o mesmo evento dos sites: a faixa do topo relê a queda (E17)


async def _testar(request: Request, endereco: str, senha: str) -> ResultadoGmail:
    try:
        # shortcut: a thread do IMAP fica presa até o prazo do socket; trocar se houver IMAP
        # assíncrono
        return await asyncio.wait_for(
            run_in_threadpool(conferir_gmail, endereco, senha, abrir=imap_do_painel(request)),
            PRAZO_GMAIL_S,
        )
    except TimeoutError:
        _LOG.warning("Gmail: sem resposta em %s s", PRAZO_GMAIL_S)
        return "sem_rede"


async def contexto_gmail(request: Request, con: Con) -> dict[str, Any]:
    """O que o cartão mostra; a senha nunca entra no contexto, o endereço só vai ao campo."""
    cofre = cofre_do_painel(request)
    senha = endereco = None
    falhou = False
    try:
        senha = await no_cofre(cofre.ler, NOME_SENHA)
        endereco = await no_cofre(cofre.ler, NOME_CONTA)
    except OSError as erro:
        _LOG.warning("Gmail: não consegui ler o cofre: %s", type(erro).__name__)
        falhou = True
    tem_credencial = senha is not None and endereco is not None
    sessao = ler_sessao(con, "conta", CONTA)
    na_tela = estado_na_tela(tem_credencial, sessao)
    if na_tela == "desligado":  # o Gmail não tem interruptor: sem credencial é "nunca entrou"
        na_tela = "nunca_entrou"
    agora = relogio_do_painel(request).agora()
    return {
        "gmail": {
            "tem_credencial": tem_credencial,
            "endereco": endereco[0] if endereco else None,
            "local": any(
                achado is not None and achado[1] == "arquivo" for achado in (senha, endereco)
            ),
            "falhou_cofre": falhou,
            "na_tela": na_tela,
            "hora": (
                conferido_texto(sessao.conferido_em, agora, idioma_do_pedido(request))
                if sessao is not None and hora_visivel(na_tela, sessao)
                else None
            ),
            "motivo": sessao.motivo if sessao is not None and na_tela == "nao_conferiu" else None,
            "pode_conferir": pode_conferir(sessao, agora, limites.INTERVALO_CONFERIR_S),
        }
    }


async def _cartao(request: Request, con: Con, mudou: bool = False, **extra: Any) -> Response:
    ctx = await contexto_gmail(request, con)
    ctx["gmail"] |= extra
    resposta = renderizar(request, _CARTAO, **ctx)
    if mudou:
        resposta.headers["HX-Trigger"] = _MUDOU
    return resposta


async def _apagar(request: Request) -> bool:
    """Apaga senha e endereço, cada um no seu `try`; devolve se os dois saíram."""
    cofre = cofre_do_painel(request)
    saiu = True
    for nome in (NOME_SENHA, NOME_CONTA):
        try:
            await no_cofre(cofre.apagar, nome)
        except OSError as erro:
            _LOG.warning("Gmail: não consegui apagar do cofre: %s", type(erro).__name__)
            saiu = False
    return saiu


@router.post("/salvar")
async def salvar(request: Request, con: Con) -> Response:
    formulario = await request.form()
    digitado = str(formulario.get("endereco", "")).strip()
    try:
        endereco = validar_endereco(digitado)
    except ValueError:
        return await _cartao(request, con, endereco=digitado, erro_endereco=True)
    try:
        senha = limpar_senha(str(formulario.get("senha", "")))
    except ValueError:
        return await _cartao(request, con, endereco=endereco, erro_senha="erro.senha")
    resultado = await _testar(request, endereco, senha)
    if resultado == "recusada":
        return await _cartao(request, con, endereco=endereco, erro_senha="erro.recusada")
    if resultado != "ok":
        return await _cartao(request, con, endereco=endereco, aviso=resultado)
    cofre = cofre_do_painel(request)
    try:
        await no_cofre(cofre.gravar, NOME_SENHA, senha)
        await no_cofre(cofre.gravar, NOME_CONTA, endereco)
    except OSError as erro:
        _LOG.warning("Gmail: não consegui guardar no cofre: %s", type(erro).__name__)
        await _apagar(request)  # melhor esforço: nunca meia credencial
        return await _cartao(request, con, endereco=endereco, falhou_cofre=True)
    gravar_sessao(con, "conta", CONTA, "conectado", None, relogio_do_painel(request).agora())
    return await _cartao(request, con, mudou=True)


@router.post("/conferir")
async def conferir(request: Request, con: Con) -> Response:
    agora = relogio_do_painel(request).agora()
    if not pode_conferir(ler_sessao(con, "conta", CONTA), agora, limites.INTERVALO_CONFERIR_S):
        return await _cartao(request, con)
    cofre = cofre_do_painel(request)
    try:
        senha = await no_cofre(cofre.ler, NOME_SENHA)
        endereco = await no_cofre(cofre.ler, NOME_CONTA)
    except OSError as erro:
        _LOG.warning("Gmail: não consegui ler o cofre: %s", type(erro).__name__)
        return await _cartao(request, con, falhou_cofre=True)
    if senha is None or endereco is None:
        return await _cartao(request, con)
    resultado = await _testar(request, endereco[0], senha[0])
    gravar_sessao(con, "conta", CONTA, *estado_do_gmail(resultado), agora)
    return await _cartao(request, con, mudou=True)


@router.post("/remover")
async def remover(request: Request, con: Con) -> Response:
    if not await _apagar(request):
        return await _cartao(request, con, falhou_cofre=True)
    agora = relogio_do_painel(request).agora()
    gravar_sessao(con, "conta", CONTA, "precisa_entrar", "esquecido", agora)
    return await _cartao(request, con, mudou=True)
