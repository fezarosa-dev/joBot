"""Descoberta semanal de empresas pelo Common Crawl (desenho 8.7, apêndice 5; DR-68).

1. só roda com o interruptor ligado e fora do adiamento de um erro anterior;
2. abre a execução (`None` se já há uma rodando) e liga o batimento;
3. índice igual ao último processado: conclui sem baixar nada;
4. senão, lê os blocos dos quatro ATS, deixa de fora o que já é empresa ou sugestão, testa cada
   quadro ao vivo e grava como sugestão o que tem vaga no Brasil ou remota;
5. guarda o índice processado e fecha a execução.

Um erro no meio marca a execução "interrompida" e sobe (A31, D71 b). Só o 503 e o limite seguram
a próxima tentativa até o dia seguinte; os outros erros tentam de novo no mesmo dia depois de um
recuo de uma hora, porque o laço acorda a cada 60 s e um erro que não some sozinho (403, formato,
bloco grande) viraria uma tentativa por minuto, cada uma baixando de novo o cluster.idx. O
cancelamento (o app fechou) não segura nada.
"""

import asyncio
import contextlib
import logging
import sqlite3
from datetime import UTC, datetime, time, timedelta

from jobot.agenda.execucao import bater
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.execucoes import abrir_execucao, fechar_execucao, interromper_execucao
from jobot.banco.sugeridas import conhecidas, gravar_sugestoes
from jobot.nucleo.coletores.descoberta_cc import indice_mais_novo, sugerir, testar
from jobot.nucleo.http import ClienteEducado, LimiteAtingido, OrcamentoGasto
from jobot.nucleo.relogio import Relogio

log = logging.getLogger(__name__)
CHAVE_INDICE = "descoberta_indice"  # último índice do Common Crawl já processado
CHAVE_ADIADA = "descoberta_adiada_ate"  # instante (ISO, UTC) antes do qual não tenta de novo
RECUO = timedelta(hours=1)  # erro que não é 503 nem limite
# shortcut: o OrcamentoGasto (escopo do Common Crawl com 2 pedidos) vale como 503, mas também
# aparece na nova tentativa de outro 5xx, de falha de rede ou de salto; troque pela checagem do
# status quando o http.py disser qual status esgotou o orçamento.
_ATE_AMANHA = (LimiteAtingido, OrcamentoGasto)


async def executar_descoberta(
    con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio
) -> None:
    if not ler_config(con, "descoberta_cc_ligada"):
        return
    adiada_ate = ler_config(con, CHAVE_ADIADA, None)
    if adiada_ate is not None and relogio.agora() < datetime.fromisoformat(adiada_ate):
        return
    execucao_id = abrir_execucao(con, "descoberta", "agenda", relogio.agora())
    if execucao_id is None:
        return
    batimento = asyncio.create_task(bater(con, execucao_id, relogio))
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
    except BaseException as erro:
        if con.in_transaction:
            con.rollback()
        interromper_execucao(con, execucao_id, relogio.agora())
        if isinstance(erro, Exception):  # o cancelamento (BaseException) não adia
            gravar_config(con, CHAVE_ADIADA, _adiar(erro, relogio.agora()).isoformat())
        raise
    finally:
        batimento.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await batimento
    fechar_execucao(con, execucao_id, relogio.agora())


def _adiar(erro: Exception, agora: datetime) -> datetime:
    if not isinstance(erro, _ATE_AMANHA):
        return (agora + RECUO).astimezone(UTC)
    amanha = agora.astimezone().date() + timedelta(days=1)  # DP8: o dia é o local
    return datetime.combine(amanha, time()).astimezone().astimezone(UTC)
