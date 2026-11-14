"""Destaques de hoje (desenho 11.4). Função pura, sem banco."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from jobot.nucleo.texto import normalizar

_JANELA = timedelta(hours=24)


@dataclass(frozen=True, kw_only=True)
class Candidata:
    vaga_id: int
    empresa: str
    nota: int | None
    publicada_em: datetime | None
    primeira_vista_em: datetime


def _ordem(c: Candidata) -> tuple[int, float, int]:
    """Maior primeiro: nota (sem nota por último), publicação mais recente, id menor."""
    publicada = c.publicada_em.timestamp() if c.publicada_em else float("-inf")
    return (-1 if c.nota is None else c.nota, publicada, -c.vaga_id)


def destaques(candidatas: Sequence[Candidata], agora: datetime, n: int = 10) -> list[Candidata]:
    """As `n` melhores, uma por empresa, entre as vistas pela primeira vez nas últimas 24 h.

    Quem chama já entrega só vagas abertas, não ocultas e com status "nova".
    """
    melhor: dict[str, Candidata] = {}
    for c in candidatas:
        if agora - c.primeira_vista_em > _JANELA:
            continue
        chave = normalizar(c.empresa)
        if chave not in melhor or _ordem(c) > _ordem(melhor[chave]):
            melhor[chave] = c
    return sorted(melhor.values(), key=_ordem, reverse=True)[:n]
