"""IA no banco (desenho 5.4; plano T403): o que cada vaga pede, a contagem do dia e `ia_tarefas`.

`habilidades_vaga` tem uma linha por vaga, gravada por `ON CONFLICT DO UPDATE`. O acerto troca o
`pede` e não mexe na falha; a falha não apaga o `pede` anterior. `tentativas` conta as falhas
seguidas com a mesma `falha_chave` e recomeça com chave nova.
"""

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from jobot.banco.cadastros import ler_config


@dataclass(frozen=True)
class TarefaIA:
    ligada: bool
    backend: str  # "" = nenhum
    modelo: str


def tarefa_ia(con: sqlite3.Connection, tarefa: str) -> TarefaIA:
    """A configuração da tarefa em `ia_tarefas`. Ausente ou estranha: desligada.

    Só liga com `ligada` igual a `true` e backend e modelo em texto não vazio.
    """
    tarefas = ler_config(con, "ia_tarefas")
    item = tarefas.get(tarefa) if isinstance(tarefas, dict) else None
    if not isinstance(item, dict):
        return TarefaIA(ligada=False, backend="", modelo="")
    backend, modelo = item.get("backend"), item.get("modelo")
    backend = backend if isinstance(backend, str) else ""
    modelo = modelo if isinstance(modelo, str) else ""
    ligada = item.get("ligada") is True and bool(backend) and bool(modelo)
    return TarefaIA(ligada=ligada, backend=backend, modelo=modelo)


def gravar_pede(
    con: sqlite3.Connection,
    vaga_id: int,
    *,
    chave: str,
    pede: Sequence[str],
    backend: str,
    modelo: str,
    versao: int,
    agora: datetime,
) -> None:
    """Grava o que a vaga pede (já conferido) e de onde veio. Não mexe na falha."""
    with con:
        con.execute(
            "INSERT INTO habilidades_vaga (vaga_id, chave, pede, backend, modelo, versao, feito_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(vaga_id) DO UPDATE SET chave = excluded.chave, pede = excluded.pede,"
            " backend = excluded.backend, modelo = excluded.modelo, versao = excluded.versao,"
            " feito_em = excluded.feito_em",
            (
                vaga_id,
                chave,
                json.dumps(list(pede), ensure_ascii=False),
                backend,
                modelo,
                versao,
                agora.isoformat(),
            ),
        )


def gravar_falha(
    con: sqlite3.Connection,
    vaga_id: int,
    *,
    chave: str,
    motivo: str,
    backend: str,
    agora: datetime,
) -> None:
    """Grava a falha da vaga (`recusa`, `formato` ou `contexto`) e soma `tentativas` por chave."""
    with con:
        con.execute(
            "INSERT INTO habilidades_vaga"
            " (vaga_id, falha, falha_em, falha_chave, falha_backend, tentativas)"
            " VALUES (?, ?, ?, ?, ?, 1)"
            " ON CONFLICT(vaga_id) DO UPDATE SET falha = excluded.falha,"
            " falha_em = excluded.falha_em, falha_backend = excluded.falha_backend,"
            " tentativas = CASE WHEN habilidades_vaga.falha_chave IS excluded.falha_chave"
            " THEN habilidades_vaga.tentativas + 1 ELSE 1 END,"
            " falha_chave = excluded.falha_chave",
            (vaga_id, motivo, agora.isoformat(), chave, backend),
        )


def chamadas_do_dia(con: sqlite3.Connection, backend: str, agora: datetime) -> int:
    """Linhas com `feito_em` ou `falha_em` no dia local de `agora` naquele backend (teto do dia)."""
    dia = agora.astimezone().date()
    inicio = datetime(dia.year, dia.month, dia.day).astimezone()
    proximo = dia + timedelta(days=1)
    fim = datetime(proximo.year, proximo.month, proximo.day).astimezone()
    contagem: int = con.execute(
        "SELECT count(*) FROM habilidades_vaga WHERE"
        " (backend = :b AND julianday(feito_em) >= julianday(:ini)"
        "  AND julianday(feito_em) < julianday(:fim))"
        " OR (falha_backend = :b AND julianday(falha_em) >= julianday(:ini)"
        "  AND julianday(falha_em) < julianday(:fim))",
        {"b": backend, "ini": inicio.isoformat(), "fim": fim.isoformat()},
    ).fetchone()[0]
    return contagem
