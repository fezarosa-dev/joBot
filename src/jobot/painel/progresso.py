"""Progresso da busca como a barra do painel o mostra (desenho 5.9; plano T252)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from jobot.banco.andamento import Etapa, FonteAndamento
from jobot.nucleo.andamento import fracao, pesos_da_execucao, valor_mostrado

# lendo e esperando primeiro, depois na fila, falhou e pronto
_ORDEM = {"lendo": 0, "esperando": 0, "fila": 1, "falhou": 2, "pronto": 3}


@dataclass(frozen=True)
class Progresso:
    indeterminado: bool
    valor: float  # 0 a 100, uma casa
    etapa: str
    feitas: int | None
    total: int | None
    lendo: tuple[str, ...]
    espera: tuple[str, int, str] | None  # fonte, segundos, motivo; só quando nada mais lê
    fontes: tuple[FonteAndamento, ...]  # lendo e esperando, fila, falhou, pronto


def segundos_ate(ate: datetime, agora: datetime) -> int:
    """Segundos inteiros que faltam, arredondados para cima; nunca negativo."""
    return max(0, math.ceil((ate - agora).total_seconds()))


def montar_progresso(
    etapa: Etapa | None, fontes: Sequence[FonteAndamento], agora: datetime, *, fechada: bool
) -> Progresso:
    if fechada:
        return Progresso(False, 100.0, "fim", None, None, (), None, ())
    # E8: a espera que já venceu volta a ser leitura, sem contagem negativa
    vivas = tuple(
        replace(f, estado="lendo", espera_ate=None, espera_motivo=None)
        if f.estado == "esperando" and (f.espera_ate is None or f.espera_ate <= agora)
        else f
        for f in fontes
    )
    ordenadas = tuple(sorted(vivas, key=lambda f: (_ORDEM.get(f.estado, 0), f.fonte)))
    lendo = tuple(f.fonte for f in ordenadas if f.estado == "lendo")
    if etapa is None or etapa.total_planejado is None:
        return Progresso(True, 0.0, "preparando", None, None, lendo, None, ordenadas)
    espera = None
    if etapa.etapa == "coleta" and not lendo:
        esperando = [f for f in ordenadas if f.estado == "esperando" and f.espera_ate]
        if esperando:
            f = min(esperando, key=lambda f: (f.espera_ate, f.fonte))
            assert f.espera_ate is not None
            espera = (f.fonte, segundos_ate(f.espera_ate, agora), f.espera_motivo or "limite")
    p, fim = fracao(pesos_da_execucao(etapa.etapas), etapa.etapa, etapa.feitas, etapa.total)
    parado_s = max(0.0, (agora - etapa.mudou_em).total_seconds())
    valor = round(100 * valor_mostrado(p, fim, etapa.partida, parado_s, fechada=False), 1)
    return Progresso(False, valor, etapa.etapa, etapa.feitas, etapa.total, lendo, espera, ordenadas)
