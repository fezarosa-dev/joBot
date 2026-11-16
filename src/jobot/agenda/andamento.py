"""Marcas do progresso da busca no banco (desenho 5.9, E1, E8; plano T247).

De melhor esforço, como as marcas de começo e fim de fonte: `sqlite3.Error` vai ao log e a busca
segue. As gravações são chamadas pelo módulo (`andamento.mudar_etapa(...)`).
"""

import logging
import sqlite3
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

from jobot.banco import andamento
from jobot.nucleo.andamento import fracao, partida_nova, pesos_da_execucao, valor_mostrado
from jobot.nucleo.http import MotivoEspera
from jobot.nucleo.relogio import Relogio

log = logging.getLogger(__name__)


class Marcas:
    def __init__(self, con: sqlite3.Connection, execucao_id: int, relogio: Relogio) -> None:
        self.con = con
        self.execucao_id = execucao_id
        self.relogio = relogio
        self._feitas: Counter[str] = Counter()  # consultas prontas por fonte
        self._total = 0

    async def comecar(self, etapas: Sequence[str]) -> None:
        self._tentar(
            "começo",
            lambda: andamento.abrir_andamento(
                self.con, self.execucao_id, etapas, self.relogio.agora()
            ),
        )

    async def planejado(self, totais: Mapping[str, int]) -> None:
        self._total = sum(totais.values())
        self._mudar("coleta", 0, self._total, totais=totais)

    async def fonte_comecou(self, fonte: str) -> None:
        self._fonte(fonte, "lendo")

    async def consulta_pronta(self, fonte: str) -> None:
        self._feitas[fonte] += 1
        self._fonte(fonte, "lendo", feitas=self._feitas[fonte])
        self._mudar("coleta", self._feitas.total(), self._total)

    async def fonte_terminou(self, fonte: str, falhou: bool) -> None:
        self._fonte(fonte, "falhou" if falhou else "pronto")

    async def esperando(self, fonte: str, fim: datetime, motivo: MotivoEspera) -> None:
        self._fonte(fonte, "esperando", espera_ate=fim, espera_motivo=motivo)

    async def etapa(self, etapa: str, feitas: int | None, total: int | None) -> None:
        self._mudar(etapa, feitas, total)

    def _fonte(
        self,
        fonte: str,
        estado: str,
        *,
        feitas: int | None = None,
        espera_ate: datetime | None = None,
        espera_motivo: str | None = None,
    ) -> None:
        self._tentar(
            f"fonte {fonte}",
            lambda: andamento.marcar_fonte(
                self.con,
                self.execucao_id,
                fonte,
                estado,
                feitas=feitas,
                espera_ate=espera_ate,
                espera_motivo=espera_motivo,
            ),
        )

    def _mudar(
        self,
        etapa: str,
        feitas: int | None,
        total: int | None,
        *,
        totais: Mapping[str, int] | None = None,
    ) -> None:
        """Toda mudança de `p` parte do valor que a barra mostrava agora (E1): nunca desce."""

        def gravar() -> None:
            agora = self.relogio.agora()
            antes, _ = andamento.ler_andamento(self.con, self.execucao_id)
            if totais is not None:
                andamento.planejar(self.con, self.execucao_id, totais, agora)
            if antes is None:  # sem andamento aberto, a etapa não teria onde ir
                return
            pesos = pesos_da_execucao(antes.etapas)
            p, fim = fracao(pesos, antes.etapa, antes.feitas, antes.total)
            parado = (agora - antes.mudou_em).total_seconds()
            valor = valor_mostrado(p, fim, antes.partida, parado, fechada=False)
            partida = partida_nova(valor, fracao(pesos, etapa, feitas, total)[0])
            andamento.mudar_etapa(self.con, self.execucao_id, etapa, feitas, total, partida, agora)

        self._tentar(f"etapa {etapa}", gravar)

    def _tentar(self, marca: str, gravar: Callable[[], None]) -> None:
        try:
            gravar()
        except sqlite3.Error:
            log.exception("marca do andamento (%s) falhou (execução %s)", marca, self.execucao_id)
