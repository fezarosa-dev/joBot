"""Descoberta semanal de empresas pelo Common Crawl (desenho 8.7, apêndice 5; DR-68).

1. só roda com o interruptor ligado e se a última descoberta não parou hoje (503: dia seguinte);
2. abre a execução (`None` se já há uma rodando) e liga o batimento;
3. índice igual ao último processado: conclui sem baixar nada;
4. senão, lê os blocos dos quatro ATS, deixa de fora o que já é empresa ou sugestão, testa cada
   quadro ao vivo e grava como sugestão o que tem vaga no Brasil ou remota;
5. guarda o índice processado e fecha a execução.

Um erro no meio marca a execução "interrompida" e sobe; o laço registra e tenta de novo, e
`parou_hoje` segura a próxima tentativa até o dia seguinte.
"""

import asyncio
import contextlib
import logging
import sqlite3

from jobot.agenda.execucao import _bater
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.execucoes import abrir_execucao, fechar_execucao, interromper_execucao
from jobot.banco.sugeridas import conhecidas, gravar_sugestoes, parou_hoje
from jobot.nucleo.coletores.descoberta_cc import indice_mais_novo, sugerir, testar
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.relogio import Relogio

log = logging.getLogger(__name__)
CHAVE_INDICE = "descoberta_indice"  # último índice do Common Crawl já processado


async def executar_descoberta(
    con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio
) -> None:
    if not ler_config(con, "descoberta_cc_ligada"):
        return
    if parou_hoje(con, relogio.agora().astimezone().date()):  # DP8: o dia é o local
        return
    execucao_id = abrir_execucao(con, "descoberta", "agenda", relogio.agora())
    if execucao_id is None:
        return
    batimento = asyncio.create_task(_bater(con, execucao_id, relogio))
    try:
        indice = await indice_mais_novo(cliente)
        if indice != ler_config(con, CHAVE_INDICE, None):
            ja = conhecidas(con)
            for s in await sugerir(cliente, indice):
                if (s.fonte, s.identificador.lower()) in ja:
                    continue
                if await testar(s, cliente):
                    gravar_sugestoes(con, [s], relogio.agora())
            gravar_config(con, CHAVE_INDICE, indice)
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
