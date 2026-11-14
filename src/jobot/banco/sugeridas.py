"""Empresas sugeridas pela descoberta (desenho 7.3, 8.7; DR-17, DR-68).

Nada entra sozinho na busca: a sugestão espera a pessoa aprovar ou descartar. Empresa já
cadastrada, inclusive a removida, nunca vira sugestão; a comparação do identificador ignora a
caixa. `aprovar` e `descartar` levantam `LookupError` para sugestão inexistente ou que não
está mais pendente (a rota traduz em 404).
"""

import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from jobot.nucleo.coletores.descoberta_cc import Sugestao


@dataclass(frozen=True)
class Sugerida:
    id: int
    fonte: str
    identificador: str
    url_exemplo: str
    descoberta_em: datetime


def gravar_sugestoes(
    con: sqlite3.Connection, sugestoes: Iterable[Sugestao], agora: datetime
) -> int:
    """Grava como pendentes as que ainda não são empresa nem sugestão; devolve quantas entraram.

    Sugestão já descartada ou aprovada fica como está (não volta a pendente).
    """
    if agora.utcoffset() is None:
        raise ValueError("agora precisa ter fuso")
    instante = agora.astimezone(UTC).isoformat()
    novas = 0
    with con:
        for s in sugestoes:
            cur = con.execute(
                "INSERT INTO empresa_sugerida (fonte, identificador, url_exemplo, descoberta_em)"
                " SELECT ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM empresa"
                " WHERE fonte = ?1 AND lower(identificador) = lower(?2))"
                " AND NOT EXISTS (SELECT 1 FROM empresa_sugerida"
                " WHERE fonte = ?1 AND lower(identificador) = lower(?2))",
                (s.fonte, s.identificador, s.url_exemplo, instante),
            )
            novas += cur.rowcount
    return novas


def conhecidas(con: sqlite3.Connection) -> set[tuple[str, str]]:
    """(fonte, identificador em minúsculas) de toda empresa (removidas incluídas) e sugestão."""
    linhas = con.execute(
        "SELECT fonte, lower(identificador) FROM empresa"
        " UNION SELECT fonte, lower(identificador) FROM empresa_sugerida"
    ).fetchall()
    return {(fonte, identificador) for fonte, identificador in linhas}


def sugeridas(con: sqlite3.Connection) -> list[Sugerida]:
    """As sugestões pendentes, na ordem em que foram achadas."""
    linhas = con.execute(
        "SELECT id, fonte, identificador, url_exemplo, descoberta_em FROM empresa_sugerida"
        " WHERE estado = 'pendente' ORDER BY id"
    ).fetchall()
    return [Sugerida(i, f, ide, url, datetime.fromisoformat(em)) for i, f, ide, url, em in linhas]


def aprovar(
    con: sqlite3.Connection,
    id: int,
    *,
    nome: str | None = None,
    parametros: Mapping[str, str] | None = None,
    identificador_novo: str | None = None,
) -> int:
    """Cria a empresa com origem `descoberta` e marca a sugestão aprovada; devolve o id da empresa.

    Sem `nome`, a empresa leva o identificador. Quem testou ao vivo passa o que o resolver leu
    (o `careerPageName` da Gupy vai em `parametros`, decisão 29). Empresa cadastrada depois da
    sugestão (qualquer caixa, removida inclusive) fica como está: só marca a sugestão aprovada
    e devolve o id dela, sem trocar nome nem `parametros` e sem reativar.
    `identificador_novo`, se vier, é o que a empresa nova grava no lugar do da
    sugestão (o do resolver, na caixa dele, D45).
    """
    if con.in_transaction:
        raise RuntimeError("conexão já está numa transação: commit ou rollback antes de aprovar")
    # Não usa adicionar_empresa: ela abre `with con` (encerraria esta transação) e sobrescreve.
    con.execute("BEGIN IMMEDIATE")  # lê sugestão e empresa com a escrita já travada
    try:
        linha = con.execute(
            "SELECT fonte, identificador FROM empresa_sugerida"
            " WHERE id = ? AND estado = 'pendente'",
            (id,),
        ).fetchone()
        if linha is None:
            raise LookupError(f"sugestão pendente inexistente: {id}")
        fonte, identificador = linha
        existente = con.execute(
            "SELECT id FROM empresa WHERE fonte = ? AND lower(identificador) = lower(?)"
            " ORDER BY id LIMIT 1",
            (fonte, identificador),
        ).fetchone()
        if existente is None:
            existente = con.execute(
                "INSERT INTO empresa (nome, fonte, identificador, parametros, origem)"
                " VALUES (?, ?, ?, ?, 'descoberta') RETURNING id",
                (
                    (nome or "").strip() or identificador,
                    fonte,
                    identificador_novo or identificador,
                    json.dumps(dict(parametros or {}), ensure_ascii=False, sort_keys=True),
                ),
            ).fetchone()
        con.execute("UPDATE empresa_sugerida SET estado = 'aprovada' WHERE id = ?", (id,))
    except BaseException:
        con.rollback()
        raise
    con.commit()
    return int(existente[0])


def descartar(con: sqlite3.Connection, id: int) -> None:
    with con:
        cur = con.execute(
            "UPDATE empresa_sugerida SET estado = 'descartada'"
            " WHERE id = ? AND estado = 'pendente'",
            (id,),
        )
        if cur.rowcount == 0:
            raise LookupError(f"sugestão pendente inexistente: {id}")
