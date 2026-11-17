"""Cartão do Gmail na aba Contas (plano T278; desenho 5.7.1, ADR 0024, E6 a E13, E21).

A senha de app mora no cofre (`sistema/cofre.py`) e nunca volta ao HTML, à resposta, ao log nem à
mensagem de erro; o endereço também não vai ao log. Só o "ok" do Google grava: fora dele, nada vai
ao cofre nem ao banco (E10). As rotas moram em `/configuracoes/gmail/...`, fora do espaço
`/configuracoes/contas/{chave}/...` dos sites (E21). Com o HTMX, todas respondem 200 com o
cartão, como o `_resultado` de Serviços: o HTMX só troca o corpo de um 2xx. Sem JavaScript, 303 para
a aba Contas com `?salvo=1` ou `?erro=<código>` de `_ERROS_DO_GMAIL` (lista fechada, D165).
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
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
_CONTAS = "/configuracoes/contas"

# o que cada falha põe no cartão: com HTMX direto na resposta, sem JavaScript pelo `?erro=` da
# volta. Lista fechada: nada da URL vai à página. `falhou_cofre` diz de onde veio a falha do cofre,
# para a frase não prometer o que não aconteceu (C2, D169)
_ERROS_DO_GMAIL: dict[str, dict[str, Any]] = {
    "gmail_endereco": {"erro_endereco": True},
    "gmail_senha": {"erro_senha": "erro.senha"},
    "gmail_recusada": {"erro_senha": "erro.recusada"},
    "gmail_bloqueio": {"aviso": "bloqueio"},
    "gmail_sem_rede": {"aviso": "sem_rede"},
    "gmail_erro": {"aviso": "erro"},
    "gmail_cofre_ler": {"falhou_cofre": "ler"},
    "gmail_cofre_salvar": {"falhou_cofre": "salvar"},
    "gmail_cofre_remover": {"falhou_cofre": "remover"},
    "gmail_cofre_troca": {"falhou_cofre": "remover"},  # a troca falhou e a antiga não saiu (R1)
}


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
    falhou = None
    try:
        senha = await no_cofre(cofre.ler, NOME_SENHA)
        endereco = await no_cofre(cofre.ler, NOME_CONTA)
    except OSError as erro:
        _LOG.warning("Gmail: não consegui ler o cofre: %s", type(erro).__name__)
        falhou = "ler"
    tem_credencial = senha is not None and endereco is not None
    sessao = ler_sessao(con, "conta", CONTA)
    na_tela = estado_na_tela(tem_credencial, sessao)
    if na_tela == "desligado":  # o Gmail não tem interruptor: sem credencial é "nunca entrou"
        na_tela = "nunca_entrou"
    agora = relogio_do_painel(request).agora()
    return {
        "gmail": {
            "tem_credencial": tem_credencial,
            # meia credencial (um `apagar` que falhou pela metade) ainda se remove (C1)
            "tem_algo": senha is not None or endereco is not None,
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
        # a volta sem JavaScript (C4): só código conhecido
        | _ERROS_DO_GMAIL.get(request.query_params.get("erro", ""), {})
    }


async def _responder(
    request: Request,
    con: Con,
    erro: str | None = None,
    mudou: bool = False,
    salvo: bool = False,
    **extra: Any,
) -> Response:
    """Com HTMX, o cartão, com o foco e o anúncio (C3); sem JavaScript, 303 para a aba (C4)."""
    if request.headers.get("hx-request") != "true":
        sufixo = f"?erro={erro}" if erro else "?salvo=1" if salvo else ""
        return RedirectResponse(_CONTAS + sufixo, 303)
    ctx = await contexto_gmail(request, con)
    ctx["gmail"] |= _ERROS_DO_GMAIL.get(erro or "", {}) | extra
    # o botão focado some na troca: o foco vai ao campo com erro ou, se estava solto, ao cartão
    resposta = renderizar(request, _CARTAO, foco=True, anunciar=mudou, **ctx)
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
        return await _responder(request, con, "gmail_endereco", endereco=digitado)
    try:
        senha = limpar_senha(str(formulario.get("senha", "")))
    except ValueError:
        return await _responder(request, con, "gmail_senha", endereco=endereco)
    resultado = await _testar(request, endereco, senha)
    if resultado != "ok":
        return await _responder(request, con, f"gmail_{resultado}", endereco=endereco)
    cofre = cofre_do_painel(request)
    try:
        await no_cofre(cofre.gravar, NOME_SENHA, senha)
        await no_cofre(cofre.gravar, NOME_CONTA, endereco)
    except OSError as erro:
        _LOG.warning("Gmail: não consegui guardar no cofre: %s", type(erro).__name__)
        # melhor esforço: nunca meia credencial. Apaga também a antiga, que valia (E10; C5, D169)
        agora = relogio_do_painel(request).agora()
        sessao = ler_sessao(con, "conta", CONTA)
        if await _apagar(request):
            if sessao is not None:  # sem credencial, a sessão antiga some junto, como no Remover
                gravar_sessao(con, "conta", CONTA, "precisa_entrar", "esquecido", agora)
            return await _responder(
                request, con, "gmail_cofre_salvar", mudou=sessao is not None, endereco=endereco
            )
        if sessao is not None and sessao.estado == "conectado":  # a senha antiga sobrou, torta
            gravar_sessao(con, "conta", CONTA, "nao_conferiu", "erro", agora)
        return await _responder(request, con, "gmail_cofre_troca", endereco=endereco)
    gravar_sessao(con, "conta", CONTA, "conectado", None, relogio_do_painel(request).agora())
    return await _responder(request, con, mudou=True, salvo=True)


@router.post("/conferir")
async def conferir(request: Request, con: Con) -> Response:
    agora = relogio_do_painel(request).agora()
    if not pode_conferir(ler_sessao(con, "conta", CONTA), agora, limites.INTERVALO_CONFERIR_S):
        return await _responder(request, con)
    cofre = cofre_do_painel(request)
    try:
        senha = await no_cofre(cofre.ler, NOME_SENHA)
        endereco = await no_cofre(cofre.ler, NOME_CONTA)
    except OSError as erro:
        _LOG.warning("Gmail: não consegui ler o cofre: %s", type(erro).__name__)
        return await _responder(request, con, "gmail_cofre_ler")
    if senha is None or endereco is None:
        return await _responder(request, con)
    resultado = await _testar(request, endereco[0], senha[0])
    gravar_sessao(con, "conta", CONTA, *estado_do_gmail(resultado), agora)
    return await _responder(request, con, mudou=True)


@router.get("/remover/confirmar")
async def remover_pergunta(request: Request) -> Response:
    """Sem JavaScript: a pergunta do alerta numa página; o GET não apaga nada (C4, T307). Vale sem
    leitor de site, como o cartão (E13)."""
    return renderizar(
        request,
        "confirmar.html",
        titulo=("configuracoes.contas.gmail.remover_pergunta", {}),
        texto="configuracoes.contas.gmail.remover_explicacao",
        rotulo="configuracoes.contas.gmail.remover",
        acao="/configuracoes/gmail/remover",
        voltar=_CONTAS,
    )


@router.post("/remover")
async def remover(request: Request, con: Con) -> Response:
    if not await _apagar(request):
        return await _responder(request, con, "gmail_cofre_remover")
    agora = relogio_do_painel(request).agora()
    gravar_sessao(con, "conta", CONTA, "precisa_entrar", "esquecido", agora)
    return await _responder(request, con, mudou=True, salvo=True)
