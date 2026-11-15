"""Fazer login agora (D132.18, D132.21, D132.52).

Abre o navegador com o perfil do joBot na página de login do site e só olha: a cada
`limites.INTERVALO_LOGIN_MANUAL_S` lê `content()` e `url`, até a página ficar logada ou o prazo
`limites.PRAZO_LOGIN_MANUAL_S` acabar. Quem digita e envia é a pessoa; o joBot nunca preenche
campo, clica nem envia nada.
"""

import asyncio
import contextlib
import logging
from typing import Literal

from playwright.async_api import Error as ErroDoPlaywright

from jobot.navegador import limites
from jobot.navegador.abrir import SemNavegador, SemTela, abrir_contexto
from jobot.navegador.execucao import Dependencias
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.relogio import Relogio

log = logging.getLogger(__name__)

Resultado = Literal["pronto", "tempo_esgotado", "sem_tela", "sem_navegador", "fechado"]


async def fazer_login(leitor: LeitorComLogin, deps: Dependencias, relogio: Relogio) -> Resultado:
    """Espera a pessoa entrar no site; fecha o navegador ao sair (cancelado inclusive)."""
    try:
        contexto = await abrir_contexto(deps.dados, deps.ambiente(), deps.lancar)
    except SemTela:
        return "sem_tela"
    except SemNavegador:
        return "sem_navegador"
    fechado = asyncio.Event()  # a pessoa desistiu: fechou a aba de login ou o navegador
    contexto_fechado = asyncio.Event()  # só o `close` do contexto: aí não há o que fechar
    contexto.on("close", lambda _: contexto_fechado.set())
    contexto.on("close", lambda _: fechado.set())
    try:
        # o perfil persistente já abre com uma aba: usa ela, sem deixar uma em branco ao lado
        aba = contexto.pages[0] if contexto.pages else await contexto.new_page()
        aba.on("close", lambda _: fechado.set())  # fechar a aba de login também desiste
        await aba.goto(leitor.url_login)
        inicio = relogio.agora()
        while True:
            try:
                html, url = await aba.content(), aba.url
            except ErroDoPlaywright:
                if fechado.is_set():
                    return "fechado"
                # a página está trocando (a pessoa enviou): olha na próxima, sem perguntar ao
                # leitor com texto vazio (o contrato não promete False para vazio)
            else:
                if leitor.pagina_logada(html, url):
                    return "pronto"
            if (relogio.agora() - inicio).total_seconds() >= limites.PRAZO_LOGIN_MANUAL_S:
                return "tempo_esgotado"
            await relogio.dormir(limites.INTERVALO_LOGIN_MANUAL_S)
            if fechado.is_set():
                return "fechado"
    except ErroDoPlaywright:
        if fechado.is_set():
            return "fechado"
        raise
    finally:
        if not contexto_fechado.is_set():
            with contextlib.suppress(ErroDoPlaywright):
                await contexto.close()
        log.info("login manual do site %s encerrado", leitor.chave)
