"""Cotações PTAX no banco e colunas `_brl` das vagas (desenho 7.3 e 10.3; plano T25).

`aplicar_cotacoes` é o dono de `sal_mensal_min_brl`, `sal_mensal_max_brl` e `sal_cotacao_data`:
reais inteiros, também na vaga em BRL. Quem grava chama `commit` aqui dentro.
"""

import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from jobot.nucleo.cambio import MOEDAS, Cotacao, em_reais
from jobot.nucleo.tratamento.salario import PARA_MENSAL, mensal

_BRL = "BRL"
_VALIDADE = timedelta(days=7)  # desenho 10.3: cotação guardada vale por 7 dias
_Valores = tuple[int | None, int | None, str | None]  # min_brl, max_brl, sal_cotacao_data


def moedas_em_aberto(con: sqlite3.Connection) -> list[str]:
    """Moedas do PTAX que aparecem em vaga aberta, em ordem alfabética."""
    linhas = con.execute(
        "SELECT DISTINCT sal_moeda FROM vaga WHERE fechada_em IS NULL AND sal_moeda IS NOT NULL"
    ).fetchall()
    return sorted(m for (m,) in linhas if m in MOEDAS)


def falta_cotacao(con: sqlite3.Connection, moeda: str, dia: date) -> bool:
    """Verdadeiro se ainda não houve pedido desta moeda em `dia` (o dia UTC do `buscada_em`).

    Conta o dia do pedido, não o do boletim: no fim de semana o boletim é o de sexta e o pedido
    do sábado já foi feito.
    Quem chama passa `relogio.agora().astimezone(UTC).date()`, nunca a data local de Brasília.
    """
    achou = con.execute(
        "SELECT 1 FROM cotacao WHERE moeda = ? AND date(buscada_em) = ?", (moeda, dia.isoformat())
    ).fetchone()
    return achou is None


def gravar_cotacao(con: sqlite3.Connection, cotacao: Cotacao, buscada_em: datetime) -> None:
    if buscada_em.utcoffset() is None:
        raise ValueError("buscada_em precisa ter fuso")
    if not cotacao.venda.is_finite() or cotacao.venda <= 0:
        raise ValueError(f"venda inválida: {cotacao.venda!r}")
    con.execute(
        "INSERT INTO cotacao (moeda, data, venda, buscada_em) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(moeda, data) DO UPDATE SET venda = excluded.venda,"
        " buscada_em = excluded.buscada_em",
        (
            cotacao.moeda,
            cotacao.data.isoformat(),
            format(cotacao.venda, "f"),
            buscada_em.astimezone(UTC).isoformat(),
        ),
    )
    con.commit()


def cotacao_mais_recente(
    con: sqlite3.Connection, moeda: str, *, hoje: date | None = None
) -> Cotacao | None:
    """Cotação guardada mais recente; com `hoje`, só a dos últimos 7 dias (`data` >= hoje - 7)."""
    desde = "0001-01-01" if hoje is None else (hoje - _VALIDADE).isoformat()
    linha = con.execute(
        "SELECT data, venda FROM cotacao WHERE moeda = ? AND data >= ? ORDER BY data DESC LIMIT 1",
        (moeda, desde),
    ).fetchone()
    if linha is None:
        return None
    try:
        return Cotacao(moeda=moeda, data=date.fromisoformat(linha[0]), venda=Decimal(linha[1]))
    except ValueError, InvalidOperation:
        return None


_INTEGER_MAX = 2**63 - 1  # maior INTEGER do SQLite


def _reais(centavos: int | None, cotacao: Decimal) -> int | None:
    if centavos is None:
        return None
    reais = em_reais(centavos, cotacao)
    # Mensal por hora (x 160) ou cotação alta estouram mesmo com o original cabendo (decisão 17)
    return reais if -_INTEGER_MAX - 1 <= reais <= _INTEGER_MAX else None


def _calcula(
    moeda: str,
    mensal_min: int | None,
    sal_max: int | None,
    periodo: str | None,
    cotacao: Cotacao | None,
) -> _Valores:
    if moeda == _BRL:
        venda, data = Decimal(1), None
    elif cotacao is not None:
        venda, data = cotacao.venda, cotacao.data.isoformat()
    else:
        return (None, None, None)
    mensal_max = None
    if sal_max is not None and periodo in PARA_MENSAL:
        mensal_max = mensal(sal_max, periodo)
    return (_reais(mensal_min, venda), _reais(mensal_max, venda), data)


def aplicar_cotacoes(
    con: sqlite3.Connection,
    *,
    conversao_ligada: bool = True,
    hoje: date | None = None,
    vaga_id: int | None = None,
) -> int:
    """Grava as colunas `_brl` e `sal_cotacao_data`; devolve quantas vagas mudaram.

    Vaga aberta em BRL: centavos ÷ 100, sem cotação, com a conversão ligada ou desligada.
    Vaga aberta em moeda estrangeira: pela cotação mais recente guardada; sem cotação, `NULL`
    (a vaga continua na lista). Conversão desligada: `NULL` em toda vaga em moeda estrangeira.
    Com `hoje`, cotação de mais de 7 dias não vale (vaga fica sem valor em reais); sem `hoje`,
    vale a mais recente guardada. Quem chama passa o dia pelo `Relogio`.
    Com `vaga_id`, só aquela vaga. Valor em reais que não cabe no INTEGER do SQLite fica `NULL`.
    """
    filtro, params = ("", ()) if vaga_id is None else (" AND id = ?", (vaga_id,))
    cotacoes: dict[str, Cotacao | None] = {}
    mudou = 0
    try:
        if not con.in_transaction:
            con.execute("BEGIN IMMEDIATE")  # leitura e escrita sob o mesmo bloqueio
        linhas = con.execute(
            "SELECT id, sal_moeda, sal_mensal_min, sal_max, sal_periodo, fechada_em,"
            " sal_mensal_min_brl, sal_mensal_max_brl, sal_cotacao_data"
            " FROM vaga WHERE sal_moeda IS NOT NULL" + filtro,
            params,
        ).fetchall()
        for id_, moeda, mensal_min, sal_max, periodo, fechada, *atual in linhas:
            moeda = moeda.upper()
            if moeda != _BRL and not conversao_ligada:
                novo: _Valores = (None, None, None)
            elif fechada is not None:
                continue
            else:
                if moeda not in cotacoes:
                    cotacoes[moeda] = cotacao_mais_recente(con, moeda, hoje=hoje)
                novo = _calcula(moeda, mensal_min, sal_max, periodo, cotacoes[moeda])
            if tuple(atual) != novo:
                con.execute(
                    "UPDATE vaga SET sal_mensal_min_brl = ?, sal_mensal_max_brl = ?,"
                    " sal_cotacao_data = ? WHERE id = ?",
                    (*novo, id_),
                )
                mudou += 1
        con.commit()
    except BaseException:
        con.rollback()
        raise
    return mudou
