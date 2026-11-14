"""Agenda da fase 1 (desenho 12.1 a 12.3).

`o_que_roda` decide, pela hora de parede e pelas últimas execuções completas gravadas,
o que está vencido; `laco` acorda a cada 60 s e dispara cada tipo vencido numa tarefa
asyncio própria, com um `asyncio.Lock` por tipo: descoberta e páginas nunca seguram a
busca, e o mesmo tipo não roda duas vezes ao mesmo tempo no processo.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta
from typing import Protocol

from jobot.banco.execucoes import Tipo
from jobot.nucleo.relogio import Relogio

_LOG = logging.getLogger(__name__)

INTERVALOS: Mapping[Tipo, timedelta] = {
    "busca": timedelta(hours=3),  # do início da última completa (DR-61)
    "descoberta": timedelta(days=7),
    "paginas": timedelta(hours=24),
}
ESPERA_AO_INICIAR = timedelta(seconds=60)  # dá tempo da rede subir (DR-35)
VOLTA_S = 60


class Estado(Protocol):
    """O que o laço lê a cada volta (do banco, na T48)."""

    def ultimas(self) -> Mapping[Tipo, datetime | None]:
        """Início da última execução completa de cada tipo; ausente ou `None` = nunca."""
        ...

    def interruptores(self) -> Mapping[str, bool]:
        """Chave por tipo (`"descoberta"`, `"paginas"`); ausente = ligada."""
        ...

    def pagina_nova(self) -> bool:
        """Há página ativa que nunca foi lida: as páginas não esperam as 24 h (T149)."""
        ...


def _vencida(agora: datetime, ultima: datetime | None, intervalo: timedelta) -> bool:
    # ultima no futuro (relógio voltou) conta como vencida, senão trava para sempre (RF4)
    return ultima is None or ultima > agora or agora - ultima >= intervalo


def o_que_roda(
    agora: datetime,
    ultima_busca: datetime | None,
    ultima_descoberta: datetime | None,
    ultima_paginas: datetime | None,
    iniciou_em: datetime,
    interruptores: Mapping[str, bool],
    *,
    pagina_nova: bool = False,
) -> list[Tipo]:
    """Tipos vencidos e ligados, na ordem busca, descoberta, páginas.

    Nos primeiros 60 s depois de o app iniciar nada roda: a execução perdida sai 60 s
    depois. Se o relógio voltou para antes de `iniciou_em`, essa espera não vale.
    `pagina_nova` torna as páginas devidas na hora, sem esperar as 24 h (T149).
    """
    if timedelta(0) <= agora - iniciou_em < ESPERA_AO_INICIAR:
        return []
    ultimas: dict[Tipo, datetime | None] = {
        "busca": ultima_busca,
        "descoberta": ultima_descoberta,
        "paginas": ultima_paginas,
    }
    return [
        tipo
        for tipo, ultima in ultimas.items()
        if interruptores.get(tipo, True)
        and (_vencida(agora, ultima, INTERVALOS[tipo]) or (tipo == "paginas" and pagina_nova))
    ]


async def rodar(tipo: str, trava: asyncio.Lock, tarefa: Callable[[], Awaitable[None]]) -> None:
    try:
        await tarefa()
    except Exception:
        _LOG.exception("execução %s falhou", tipo)  # o laço segue; a próxima volta tenta de novo
    finally:
        trava.release()


async def laco(
    tarefas: Mapping[str, Callable[[], Awaitable[None]]],
    estado: Estado,
    relogio: Relogio,
    *,
    travas: Mapping[str, asyncio.Lock] | None = None,
) -> None:
    """Acorda a cada 60 s e dispara o que venceu; cancelar o laço cancela o que roda.

    `travas` vem de fora quando outra rota ("buscar agora") precisa da mesma trava por tipo
    (D55); sem ela, o laço cria as suas.
    """
    iniciou_em = relogio.agora()
    if travas is None:
        travas = {tipo: asyncio.Lock() for tipo in tarefas}
    async with asyncio.TaskGroup() as grupo:
        while True:
            try:
                ultimas = estado.ultimas()
                vencidos = o_que_roda(
                    relogio.agora(),
                    ultimas.get("busca"),
                    ultimas.get("descoberta"),
                    ultimas.get("paginas"),
                    iniciou_em,
                    estado.interruptores(),
                    pagina_nova=estado.pagina_nova(),
                )
            except Exception:
                # ex.: banco travado; cair aqui cancelaria as tarefas e pararia a agenda
                _LOG.exception("leitura do estado da agenda falhou")
                vencidos = []
            for tipo in vencidos:
                trava, tarefa = travas.get(tipo), tarefas.get(tipo)
                if trava is None or tarefa is None or trava.locked():
                    continue  # as travas de fora podem trazer tipo ainda sem tarefa
                await trava.acquire()  # livre: não suspende, então a checagem acima vale
                grupo.create_task(rodar(tipo, trava, tarefa))
            await relogio.dormir(VOLTA_S)
