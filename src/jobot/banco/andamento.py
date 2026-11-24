"""Dados do progresso da busca no banco (desenho 5.9, E2; plano T246).

Datas entram e saem em UTC com fuso (`agora` vem de quem chama; sem fuso levanta `ValueError`).
Transações por `quem_abriu_confirma`: toda gravação só confirma quando não há transação aberta;
havendo, quem abriu confirma. Nada é apagado.
"""

import json
import logging
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from jobot.banco.conexao import quem_abriu_confirma

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Etapa:
    """A etapa em que a busca está, com o que já se sabe dela."""

    etapas: tuple[str, ...]  # as que rodam nesta execução, fixadas no começo
    etapa: str
    feitas: int | None
    total: int | None
    total_planejado: int | None  # o total da coleta, fixado no `planejar`
    partida: float  # de onde a curva do painel parte nesta etapa (0..1)
    mudou_em: datetime


@dataclass(frozen=True)
class FonteAndamento:
    fonte: str
    estado: str  # fila, lendo, pronto, falhou, esperando
    feitas: int
    total: int
    espera_ate: datetime | None
    espera_motivo: str | None  # limite ou erro


def _iso(agora: datetime) -> str:
    if agora.tzinfo is None:
        raise ValueError("agora precisa ter fuso")
    return agora.astimezone(UTC).isoformat()


def _data(texto: str) -> datetime:
    data = datetime.fromisoformat(texto)
    return data if data.tzinfo else data.replace(tzinfo=UTC)


def _data_ou_none(texto: str | None) -> datetime | None:
    return None if texto is None else _data(texto)


def abrir_andamento(
    con: sqlite3.Connection, execucao_id: int, etapas: Sequence[str], agora: datetime
) -> None:
    """Começa o andamento em `preparando`, partida 0; abrir de novo volta ao começo."""
    with quem_abriu_confirma(con):
        con.execute(
            "INSERT INTO andamento (execucao_id, etapas, etapa, partida, mudou_em)"
            " VALUES (?, ?, 'preparando', 0, ?)"
            " ON CONFLICT(execucao_id) DO UPDATE SET etapas=excluded.etapas,"
            " etapa='preparando', feitas=NULL, total=NULL, total_planejado=NULL, partida=0,"
            " mudou_em=excluded.mudou_em",
            (execucao_id, json.dumps(list(etapas)), _iso(agora)),
        )


def planejar(
    con: sqlite3.Connection, execucao_id: int, totais: Mapping[str, int], agora: datetime
) -> None:
    """Fixa o total da coleta (a soma dos `totais`), vai para `coleta` e põe cada fonte na fila.

    Sem `abrir_andamento` antes, não grava nada e escreve no log."""
    planejado = sum(totais.values())
    with quem_abriu_confirma(con):
        cur = con.execute(
            "UPDATE andamento SET etapa='coleta', feitas=0, total=?, total_planejado=?,"
            " mudou_em=? WHERE execucao_id=?",
            (planejado, planejado, _iso(agora), execucao_id),
        )
        if cur.rowcount == 0:
            log.warning("andamento: execução %s sem andamento aberto, nada planejado", execucao_id)
            return
        con.executemany(
            "INSERT INTO andamento_fonte (execucao_id, fonte, estado, feitas, total)"
            " VALUES (?, ?, 'fila', 0, ?)"
            " ON CONFLICT(execucao_id, fonte) DO UPDATE SET estado='fila', feitas=0,"
            " total=excluded.total, espera_ate=NULL, espera_motivo=NULL",
            [(execucao_id, fonte, total) for fonte, total in totais.items()],
        )


def mudar_etapa(
    con: sqlite3.Connection,
    execucao_id: int,
    etapa: str,
    feitas: int | None,
    total: int | None,
    partida: float,
    agora: datetime,
) -> None:
    """Passa para `etapa`; `total_planejado` e as linhas das fontes ficam como estão."""
    with quem_abriu_confirma(con):
        cur = con.execute(
            "UPDATE andamento SET etapa=?, feitas=?, total=?, partida=?, mudou_em=?"
            " WHERE execucao_id=?",
            (etapa, feitas, total, partida, _iso(agora), execucao_id),
        )
        if cur.rowcount == 0:
            log.warning("andamento: execução %s sem andamento aberto, etapa ignorada", execucao_id)


def marcar_fonte(
    con: sqlite3.Connection,
    execucao_id: int,
    fonte: str,
    estado: str,
    *,
    feitas: int | None = None,
    espera_ate: datetime | None = None,
    espera_motivo: str | None = None,
) -> None:
    """Muda a linha que o `planejar` criou (o `total` vem de lá); sem a linha, só escreve no log.

    `feitas=None` mantém o valor. Estado diferente de `esperando` limpa a espera."""
    esperando = estado == "esperando"
    with quem_abriu_confirma(con):
        cur = con.execute(
            "UPDATE andamento_fonte SET estado=?, feitas=COALESCE(?, feitas), espera_ate=?,"
            " espera_motivo=? WHERE execucao_id=? AND fonte=?",
            (
                estado,
                feitas,
                _iso(espera_ate) if esperando and espera_ate else None,
                espera_motivo if esperando else None,
                execucao_id,
                fonte,
            ),
        )
        if cur.rowcount == 0:
            log.warning("andamento: fonte %s da execução %s não foi planejada", fonte, execucao_id)


def ler_andamento(
    con: sqlite3.Connection, execucao_id: int
) -> tuple[Etapa | None, tuple[FonteAndamento, ...]]:
    """A etapa e as fontes (por nome) da execução; sem andamento, `(None, ())`."""
    linha = con.execute(
        "SELECT etapas, etapa, feitas, total, total_planejado, partida, mudou_em"
        " FROM andamento WHERE execucao_id=?",
        (execucao_id,),
    ).fetchone()
    if linha is None:
        return None, ()
    etapa = Etapa(
        tuple(json.loads(linha[0])),
        linha[1],
        linha[2],
        linha[3],
        linha[4],
        linha[5],
        _data(linha[6]),
    )
    fontes = con.execute(
        "SELECT fonte, estado, feitas, total, espera_ate, espera_motivo FROM andamento_fonte"
        " WHERE execucao_id=? ORDER BY fonte",
        (execucao_id,),
    ).fetchall()
    return etapa, tuple(
        FonteAndamento(f[0], f[1], f[2], f[3], _data_ou_none(f[4]), f[5]) for f in fontes
    )
