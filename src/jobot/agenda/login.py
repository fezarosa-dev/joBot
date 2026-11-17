"""Hora da leitura com login (desenho A6; D132.6, D132.25)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta

JANELA_HORARIO = timedelta(minutes=15)
INTERVALO_MINIMO = timedelta(hours=4)


@dataclass(frozen=True)
class Login:
    horarios: tuple[time, ...]
    ultima: datetime | None


def login_vencido(agora: datetime, horarios: Sequence[time], ultima: datetime | None) -> bool:
    """O horário mais recente que já chegou (hoje ou ontem, no dia local) pede leitura agora.

    Vence dentro de `JANELA_HORARIO` depois dele, se nenhuma leitura começou desde então e a
    anterior começou `INTERVALO_MINIMO` antes dele. Horário perdido é pulado. `ultima` no futuro
    (relógio que voltou) conta como nula, senão trava para sempre.
    """
    hoje = agora.astimezone().date()
    # naive + astimezone(): cada dia ganha o deslocamento local dele (horário de verão)
    passados = [
        candidato
        for dia in (hoje - timedelta(days=1), hoje)
        for h in horarios
        if (candidato := datetime.combine(dia, h).astimezone()) <= agora
    ]
    if not passados:
        return False
    marco = max(passados)
    if agora - marco >= JANELA_HORARIO:
        return False
    if ultima is None or ultima > agora:
        return True
    return ultima < marco and marco - ultima >= INTERVALO_MINIMO


def pode_ler_agora(agora: datetime, ultima: datetime | None) -> bool:
    """ "Buscar agora" lê os sites com login: nunca leu, relógio voltou ou já passou o intervalo."""
    return ultima is None or ultima > agora or agora - ultima >= INTERVALO_MINIMO
