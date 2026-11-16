"""Estado da conta de cada site com login e de cada conta de fora (desenho 5.2; plano T270).

A regra do `entrou_em` e do `avisado_em` é `nucleo.contas.proxima_sessao`; aqui só se lê a linha
e se grava a nova sob o mesmo bloqueio. Quem abriu a transação confirma; quem recebeu uma aberta
deixa o commit para ela.
"""

import sqlite3
from datetime import datetime
from typing import Final, Literal

from jobot.nucleo.contas import EstadoSessao, MotivoSessao, Sessao, proxima_sessao

TipoSessao = Literal["site", "conta"]

# tabela e coluna-chave vêm daqui, nunca do texto de quem chama
_ONDE: Final = {"site": ("sessao_site", "fonte"), "conta": ("sessao_conta", "conta")}
_COLUNAS: Final = "estado, motivo, conferido_em, entrou_em, avisado_em"


def gravar_sessao(
    con: sqlite3.Connection,
    tipo: TipoSessao,
    chave: str,
    estado: EstadoSessao,
    motivo: MotivoSessao | None,
    agora: datetime,
) -> bool:
    """Grava o estado novo e devolve se esta gravação abriu a queda (quem avisa decide o aviso)."""
    tabela, coluna = _ONDE[tipo]
    abri = not con.in_transaction
    try:
        if abri:
            con.execute("BEGIN IMMEDIATE")  # leitura e escrita sob o mesmo bloqueio
        linha = con.execute(
            f"SELECT {_COLUNAS} FROM {tabela} WHERE {coluna} = ?", (chave,)
        ).fetchone()
        antiga = None if linha is None else Sessao(*linha)
        nova, abriu = proxima_sessao(antiga, estado, motivo, agora)
        con.execute(
            f"INSERT INTO {tabela} ({coluna}, {_COLUNAS}) VALUES (?, ?, ?, ?, ?, ?)"
            f" ON CONFLICT({coluna}) DO UPDATE SET estado = excluded.estado,"
            " motivo = excluded.motivo, conferido_em = excluded.conferido_em,"
            " entrou_em = excluded.entrou_em, avisado_em = excluded.avisado_em",
            (
                chave,
                nova.estado,
                nova.motivo,
                nova.conferido_em,
                nova.entrou_em,
                nova.avisado_em,
            ),
        )
        if abri:
            con.commit()
    except BaseException:
        if abri:
            con.rollback()
        raise
    return abriu


def ler_sessao(con: sqlite3.Connection, tipo: TipoSessao, chave: str) -> Sessao | None:
    tabela, coluna = _ONDE[tipo]
    linha = con.execute(f"SELECT {_COLUNAS} FROM {tabela} WHERE {coluna} = ?", (chave,)).fetchone()
    return None if linha is None else Sessao(*linha)


def ler_sessoes(con: sqlite3.Connection, tipo: TipoSessao) -> dict[str, Sessao]:
    tabela, coluna = _ONDE[tipo]
    linhas = con.execute(f"SELECT {coluna}, {_COLUNAS} FROM {tabela}").fetchall()
    return {chave: Sessao(*resto) for chave, *resto in linhas}
