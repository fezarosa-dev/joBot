"""Consultas do painel usadas pelas rotas e pela lateral da casca (E4; T251).

Mora fora de `rotas/` porque a lateral é um global do Jinja: `globais` não pode importar
`rotas/vagas.py`, que importa `seguranca`, que importa `globais`.
"""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from starlette.requests import Request

from jobot.banco import leitura
from jobot.nucleo.destaques import Candidata, destaques
from jobot.nucleo.relogio import Relogio, RelogioReal

_DESTAQUES_N = 10
# janela larga para o SQL; a de 24 h é da função pura `destaques`
_ANTES_DESTAQUES = "julianday(v.primeira_vista_em) >= julianday(:agora) - 2"


def relogio_do_painel(request: Request) -> Relogio:
    relogio: Relogio = getattr(request.app.state, "relogio", None) or RelogioReal()
    return relogio


def config_ou_padrao(con: sqlite3.Connection, chave: str, padrao: Any) -> Any:
    linha = con.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return padrao if linha is None else json.loads(linha[0])


def busca_efetiva(con: sqlite3.Connection, pedida: int | None) -> int | None:
    """A busca da URL, se existir; senão a primeira ativa; sem nenhuma, None."""
    if pedida is not None and con.execute("SELECT 1 FROM busca WHERE id = ?", (pedida,)).fetchone():
        return pedida
    linha = con.execute("SELECT id FROM busca WHERE ativa = 1 ORDER BY id LIMIT 1").fetchone()
    return None if linha is None else int(linha[0])


def utc_do_banco(texto: str) -> datetime | None:
    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return data if data.tzinfo else data.replace(tzinfo=UTC)


def ids_destaques(con: sqlite3.Connection, busca_id: int | None, agora: datetime) -> list[int]:
    """As vagas da aba Destaques: só abertas, não ocultas e novas (a função pura faz o resto)."""
    quantas = config_ou_padrao(con, "destaques_n", _DESTAQUES_N)
    if not isinstance(quantas, int) or isinstance(quantas, bool) or quantas < 1:
        quantas = _DESTAQUES_N
    linhas = con.execute(
        "SELECT v.id, v.empresa, e.nota, v.publicada_em, v.primeira_vista_em"
        " FROM vaga v LEFT JOIN encaixe e ON e.vaga_id = v.id AND e.busca_id = :busca"
        f" WHERE {leitura.ABAS['novas']} AND {_ANTES_DESTAQUES}",
        # o dia de calendário é o do fuso local (mesma regra do `leitura`)
        {
            "agora": agora.isoformat(),
            "hoje": agora.astimezone().date().isoformat(),
            "busca": busca_id,
        },
    ).fetchall()
    candidatas = []
    for vaga_id, empresa, nota, publicada, primeira in linhas:
        vista = utc_do_banco(primeira)
        if vista is not None:
            candidata = Candidata(
                vaga_id=vaga_id,
                empresa=empresa,
                nota=nota,
                publicada_em=utc_do_banco(publicada) if publicada else None,
                primeira_vista_em=vista,
            )
            candidatas.append(candidata)
    return [c.vaga_id for c in destaques(candidatas, agora, quantas)]
