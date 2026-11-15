"""Moeda de exibição do painel e o filtro de salário em reais ou na moeda (desenho 5, parte B)."""

import sqlite3
from dataclasses import dataclass
from datetime import date

from jobot.banco.cadastros import ler_config, moeda_efetiva
from jobot.banco.cotacoes import cotacao_mais_recente
from jobot.nucleo.cambio import Cotacao, em_reais_inteiros

INTEGER_MAX = 2**63 - 1  # maior INTEGER do SQLite
_BRL = "BRL"


@dataclass(frozen=True)
class Exibicao:
    moeda: str
    cotacao: Cotacao | None  # None em BRL, ou sem cotação dos últimos 7 dias
    conversao_ligada: bool


def exibicao_do_painel(con: sqlite3.Connection, hoje: date) -> Exibicao:
    """A moeda de exibição Y, a cotação dela de até 7 dias e se a conversão está ligada."""
    moeda = moeda_efetiva(con)
    cotacao = None if moeda == _BRL else cotacao_mais_recente(con, moeda, hoje=hoje)
    if cotacao is not None and (not cotacao.venda.is_finite() or cotacao.venda <= 0):
        cotacao = None  # linha estragada à mão: vale como sem cotação, nunca como erro
    return Exibicao(moeda, cotacao, bool(ler_config(con, "conversao_moeda_ligada")))


@dataclass(frozen=True)
class FiltroSalario:
    sal_de_brl: int | None
    sal_ate_brl: int | None
    sal_moeda: str | None
    sal_de_centavos: int | None
    sal_ate_centavos: int | None
    aviso: str | None  # "sem_cotacao", "so_moeda" ou None


def _preso(valor: int | None) -> int | None:
    return None if valor is None else min(valor, INTEGER_MAX)


def filtro_salario(de: int | None, ate: int | None, ex: Exibicao) -> FiltroSalario:
    """Os limites digitados (em unidades de Y por mês) no que o `Filtros` entende."""
    if de is not None and ate is not None and de > ate:
        de, ate = ate, de
    if de is None and ate is None:
        return FiltroSalario(None, None, None, None, None, None)
    if ex.moeda == _BRL:
        return FiltroSalario(_preso(de), _preso(ate), None, None, None, None)
    if not ex.conversao_ligada:
        centavos = [None if v is None else v * 100 for v in (de, ate)]
        return FiltroSalario(
            None, None, ex.moeda, _preso(centavos[0]), _preso(centavos[1]), "so_moeda"
        )
    if ex.cotacao is None:
        return FiltroSalario(None, None, None, None, None, "sem_cotacao")
    venda = ex.cotacao.venda  # "de" arredonda para baixo e "até" para cima: a favor da vaga
    reais_de = None if de is None else em_reais_inteiros(de, venda, para_cima=False)
    reais_ate = None if ate is None else em_reais_inteiros(ate, venda, para_cima=True)
    return FiltroSalario(_preso(reais_de), _preso(reais_ate), None, None, None, None)
