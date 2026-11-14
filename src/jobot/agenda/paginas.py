"""Execução das páginas acompanhadas (desenho 8.8, 12.2, 12.3; plano T72).

Uma execução do tipo `paginas`, com trava própria: nunca segura a busca. Cada página ativa devida
(nunca lida ou lida há 24 h ou mais, T149) é lida uma vez; a que falha fica "falhou" sem apagar o
texto e sem parar as outras.
"""

import asyncio
import contextlib
import logging
import sqlite3
from datetime import datetime, timedelta

from jobot.agenda.agendador import INTERVALOS
from jobot.agenda.execucao import bater
from jobot.banco.cadastros import ler_config
from jobot.banco.execucoes import abrir_execucao, fechar_execucao, interromper_execucao
from jobot.banco.paginas import gravar_leitura, marcar_falhou, paginas
from jobot.nucleo.coletores.paginas import ConteudoNaoLido, Pagina, verificar
from jobot.nucleo.http import (
    Bloqueio,
    ClienteEducado,
    ErroDeRede,
    LimiteAtingido,
    Parou429,
    Resolvedor,
    RespostaGrande,
)
from jobot.nucleo.relogio import Relogio

log = logging.getLogger(__name__)


# A execução vem a cada 24 h contadas do início dela, mas cada página é gravada um pouco depois:
# sem a folga, a lida no fim da execução de ontem ficaria de fora da de hoje.
_FOLGA = timedelta(hours=1)


def _devida(pagina: Pagina, agora: datetime) -> bool:
    """Ativa e (nunca lida, ou lida há 24 h ou mais, ou com leitura no futuro: relógio voltou)."""
    lida = pagina.verificada_em
    return pagina.ativa and (
        lida is None or lida > agora or agora - lida >= INTERVALOS["paginas"] - _FOLGA
    )


def _motivo(erro: Exception) -> str:
    """O código de `banco.paginas.MOTIVOS` que descreve a falha; o que não se conhece é `erro`."""
    if isinstance(erro, ConteudoNaoLido):
        return "nao_e_texto"
    if isinstance(erro, Bloqueio | LimiteAtingido | Parou429):
        return "bloqueada"
    if isinstance(erro, RespostaGrande):
        return "grande_demais"
    if isinstance(erro, ValueError):  # `verificar` recusa assim o endereço não permitido
        return "endereco_recusado"
    if isinstance(erro, ErroDeRede):
        return "fora_do_ar"
    return "erro"


async def executar_paginas(
    con: sqlite3.Connection,
    cliente: ClienteEducado,
    relogio: Relogio,
    *,
    resolver: Resolvedor | None = None,
) -> int | None:
    """Confere as páginas ativas e devolve o id da execução; `None` se outra já está rodando
    ou se `paginas_ligadas` está desligada (a chave é relida a cada chamada).

    Erro fora da leitura de uma página (banco) marca a execução "interrompida" e sobe (D54).
    `resolver` é o DNS da conferência de host local (padrão: o do sistema; falso nos testes).
    """
    if not ler_config(con, "paginas_ligadas"):
        return None
    execucao_id = abrir_execucao(con, "paginas", "agenda", relogio.agora())
    if execucao_id is None:
        return None
    batimento = asyncio.create_task(bater(con, execucao_id, relogio))
    try:
        for pagina in paginas(con):
            if not _devida(pagina, relogio.agora()):
                continue
            try:
                mudanca = await verificar(
                    cliente.escopo(condicional=False), pagina, resolver=resolver
                )
            # rede, bloqueio, endereço recusado: a página falha, o resto segue
            except Exception as erro:
                log.warning("página acompanhada %s falhou", pagina.id, exc_info=True)
                marcar_falhou(con, pagina.id, _motivo(erro))
                continue
            gravar_leitura(con, pagina.id, mudanca, relogio.agora())
    except BaseException:
        if con.in_transaction:
            con.rollback()
        interromper_execucao(con, execucao_id, relogio.agora())
        raise
    finally:
        batimento.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await batimento
    fechar_execucao(con, execucao_id, relogio.agora())
    return execucao_id
