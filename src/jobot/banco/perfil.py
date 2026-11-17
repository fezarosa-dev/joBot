"""Perfil da pessoa (desenho 8; plano T403). Na 0.5.0, só as habilidades, numa linha só.

As habilidades ficam no computador: o pedido do `encaixe` nunca leva o perfil (desenho 5.3).
Normalizar e tirar repetidos é da tela (T413); aqui só se lê e grava.
"""

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime


def habilidades(con: sqlite3.Connection) -> list[str]:
    """As habilidades gravadas. Sem perfil, ou com valor estranho, lista vazia; só textos ficam."""
    linha = con.execute("SELECT habilidades FROM perfil WHERE id = 1").fetchone()
    if linha is None:
        return []
    try:
        valor = json.loads(linha[0])
    except ValueError:
        return []
    return [h for h in valor if isinstance(h, str)] if isinstance(valor, list) else []


def gravar_habilidades(con: sqlite3.Connection, lista: Sequence[str], agora: datetime) -> None:
    """Grava as habilidades na linha única (`ON CONFLICT DO UPDATE`)."""
    with con:
        con.execute(
            "INSERT INTO perfil (id, habilidades, atualizado_em) VALUES (1, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET habilidades = excluded.habilidades,"
            " atualizado_em = excluded.atualizado_em",
            (json.dumps(list(lista), ensure_ascii=False), agora.isoformat()),
        )


def apagar_perfil(con: sqlite3.Connection) -> None:
    """Apaga a linha ("Apagar perfil"). `habilidades_vaga` fica: não depende do perfil."""
    with con:
        con.execute("DELETE FROM perfil")
