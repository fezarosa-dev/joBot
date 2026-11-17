"""O estado do login visto pelo navegador: o mapa da entrada e o registro com aviso (desenho 5.1
e 5.6; plano T272, E3).

Não importa `execucao.py`: a leitura agendada e o "Conferir agora" usam o mesmo mapa.
"""

import asyncio
import sqlite3
from collections.abc import Callable
from typing import Final, Literal

from playwright.async_api import Error as ErroDoPlaywright

from jobot.banco.sessoes import gravar_sessao
from jobot.navegador.captcha import Widget
from jobot.navegador.pagina import Recusada, Visita
from jobot.nucleo.contas import EstadoSessao, MotivoSessao
from jobot.nucleo.leitores.base import Captura, LeitorComLogin
from jobot.nucleo.relogio import Relogio

TITULO_AVISO: Final = "joBot"
FRASES_QUEDA: Final = {
    "pt": "Sua sessão no {site} caiu. Abra o joBot e entre de novo em Configurações › Contas.",
    "en": "Your {site} session ended. Open joBot and sign in again in Settings › Accounts.",
}


def estado_da_visita(
    visita: Visita, leitor: LeitorComLogin
) -> tuple[EstadoSessao, MotivoSessao | None]:
    """O que a visita à `url_entrada` diz do login (desenho 5.1; 401 e 403 são `bloqueio`)."""
    if isinstance(visita, Captura):
        logada = leitor.pagina_logada(visita.html, visita.url)
        return ("conectado", None) if logada else ("precisa_entrar", None)
    if isinstance(visita, Recusada):
        return ("nao_conferiu", "bloqueio")
    if isinstance(visita, Widget):
        return ("nao_conferiu", "desafio")
    match visita:
        case "precisa_login":
            return ("precisa_entrar", None)
        case "bloqueio":
            return ("nao_conferiu", "bloqueio")
        case "captcha":
            return ("nao_conferiu", "desafio")
        case "no_limite":
            return ("nao_conferiu", "no_limite")


def estado_da_falha(erro: Exception) -> tuple[EstadoSessao, MotivoSessao]:
    """Exceção na entrada; a mensagem do Playwright não é lida (traz a URL e não é contrato)."""
    return ("nao_conferiu", "sem_rede" if isinstance(erro, ErroDoPlaywright) else "erro")


async def registrar_sessao(
    con: sqlite3.Connection,
    leitor: LeitorComLogin,
    estado: EstadoSessao,
    motivo: MotivoSessao | None,
    relogio: Relogio,
    *,
    avisar: Callable[[str, str], None],
    idioma: Literal["pt", "en"],
) -> bool:
    """Grava o estado e avisa no computador quando esta gravação abriu a queda (D139.22)."""
    abriu = gravar_sessao(con, "site", leitor.chave, estado, motivo, relogio.agora())
    if abriu:
        frase = FRASES_QUEDA[idioma].format(site=leitor.nome)
        # o `notify-send` roda fora do laço: o painel não para enquanto ele responde
        await asyncio.to_thread(avisar, TITULO_AVISO, frase)
    return abriu
