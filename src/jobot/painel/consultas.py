"""Consultas do painel usadas pelas rotas e pela lateral da casca (E4; T251).

Mora fora de `rotas/` porque a lateral é um global do Jinja: `globais` não pode importar
`rotas/vagas.py`, que importa `seguranca`, que importa `globais`.
"""

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

from starlette.requests import Request

from jobot.banco import cadastros, leitura
from jobot.banco.cadastros import ler_config
from jobot.banco.sessoes import ler_sessao, ler_sessoes
from jobot.nucleo import gmail
from jobot.nucleo.destaques import Candidata, destaques
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.relogio import Relogio, RelogioReal

MAX_ID = 2**31
_DESTAQUES_N = 10
# janela larga para o SQL; a de 24 h é da função pura `destaques`
_ANTES_DESTAQUES = "julianday(v.primeira_vista_em) >= julianday(:agora) - 2"


def relogio_do_painel(request: Request) -> Relogio:
    relogio: Relogio = getattr(request.app.state, "relogio", None) or RelogioReal()
    return relogio


def inteiro_da_url(texto: str | None, maximo: int) -> int | None:
    """Número de 1 a `maximo`; qualquer outra coisa (letra, zero, negativo, enorme) é None."""
    # o tamanho vem antes do `int()`: texto com mais de 4300 dígitos o faz levantar ValueError
    if texto is None or not texto.isascii() or not texto.isdigit() or len(texto) > len(str(maximo)):
        return None
    numero = int(texto)
    return numero if 1 <= numero <= maximo else None


def busca_ativa(con: sqlite3.Connection, id_: object) -> bool:
    """`id_` é o id de uma busca que existe e está ligada."""
    if not isinstance(id_, int) or isinstance(id_, bool):
        return False
    return (
        con.execute("SELECT 1 FROM busca WHERE id = ? AND ativa = 1", (id_,)).fetchone() is not None
    )


def busca_efetiva(con: sqlite3.Connection, pedida: int | None) -> int | None:
    """A busca da URL, se existir (ligada ou não: link velho mostra a busca dele); senão a
    gravada em `busca_escolhida`, se ainda existe e está ligada; senão a primeira ativa (E16)."""
    if pedida is not None and con.execute("SELECT 1 FROM busca WHERE id = ?", (pedida,)).fetchone():
        return pedida
    gravada = ler_config(con, "busca_escolhida", None)
    if busca_ativa(con, gravada):
        return int(gravada)
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
    quantas = ler_config(con, "destaques_n", _DESTAQUES_N)
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


def contas_em_queda(
    con: sqlite3.Connection, leitores: Sequence[LeitorComLogin]
) -> list[tuple[str, str]]:
    """Chave e nome das contas em queda: os sites na ordem dos leitores, o Gmail por último."""
    ligadas = {f.chave: f.ligada for f in cadastros.fontes(con)}
    sessoes = ler_sessoes(con, "site")
    quedas = [
        (leitor.chave, leitor.nome)
        for leitor in leitores
        if ligadas.get(leitor.chave, False)
        and (sessao := sessoes.get(leitor.chave)) is not None
        and sessao.queda_aberta
    ]
    do_gmail = ler_sessao(con, "conta", gmail.CONTA)
    if do_gmail is not None and do_gmail.queda_aberta:
        quedas.append((gmail.CONTA, "Gmail"))
    return quedas
