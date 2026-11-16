"""Conferir agora: a janela automática visita a `url_entrada` e diz o estado do login (desenho
5.4; plano T273, E5).

Não recebe conexão: não grava execução, saúde nem estado; quem chama grava.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from playwright.async_api import BrowserContext
from playwright.async_api import Error as ErroDoPlaywright

from jobot.navegador import limites
from jobot.navegador.abrir import SemNavegador, SemTela, abrir_contexto
from jobot.navegador.execucao import Dependencias, fechou
from jobot.navegador.janela_comum import perfil_em_uso
from jobot.navegador.pagina import visitar
from jobot.navegador.perfil import pasta_do_perfil
from jobot.navegador.sessao import estado_da_visita
from jobot.nucleo.contas import EstadoSessao, MotivoSessao
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.relogio import Relogio

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Conferencia:
    estado: EstadoSessao
    motivo: MotivoSessao | None


async def conferir_sessao(
    leitor: LeitorComLogin, deps: Dependencias, relogio: Relogio
) -> Conferencia | None:
    """O estado do login agora; `None` quando a pessoa fecha a janela no meio (E5)."""
    if perfil_em_uso(pasta_do_perfil(deps.dados)):
        return Conferencia("nao_conferiu", "em_uso")
    fechado = asyncio.Event()
    contexto: BrowserContext | None = None
    try:
        # fora do prazo: o launch tem prazo próprio e cancelá-lo deixa um Chromium órfão
        contexto = await abrir_contexto(deps.dados, deps.ambiente(), deps.lancar)
        contexto.on("close", lambda _: fechado.set())
        async with asyncio.timeout(limites.PRAZO_CONFERIR_S):
            aba = await contexto.new_page()
            # sem `cola`: o "Conferir agora" não resolve CAPTCHA, o desafio vira `desafio`
            visita = await visitar(aba, leitor.url_entrada, leitor, deps.politica(leitor), relogio)
        return Conferencia(*estado_da_visita(visita, leitor))
    except SemTela:
        return Conferencia("nao_conferiu", "sem_tela")
    except SemNavegador:
        return Conferencia("nao_conferiu", "sem_navegador")
    except TimeoutError:
        return Conferencia("nao_conferiu", "sem_rede")
    except ErroDoPlaywright as erro:
        if await fechou(fechado, erro):
            return None
        return Conferencia("nao_conferiu", "sem_rede")
    except Exception:
        log.warning("conferir a sessão do site %s falhou", leitor.chave, exc_info=True)
        return Conferencia("nao_conferiu", "erro")
    finally:
        if contexto is not None:
            with contextlib.suppress(ErroDoPlaywright):
                await contexto.close()
