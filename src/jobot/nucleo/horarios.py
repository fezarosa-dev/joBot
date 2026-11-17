"""Horários de parede da leitura com login (plano T204; D132.48)."""

import re
from datetime import time

_CHAVE = "configuracoes.sites_com_login.horarios."
_HHMM = re.compile(r"([01][0-9]|2[0-3]):([0-5][0-9])")
_MAXIMO = 4
_MINUTOS_ENTRE = 4 * 60


def horarios_validos(valor: object) -> tuple[time, ...]:
    """De 1 a 4 horários `HH:MM`, sem repetição e a 4 h ou mais um do outro (volta da meia-noite
    inclusa), em ordem. Valor torto levanta `ValueError` com a chave do erro em `args[0]`."""
    if not isinstance(valor, list | tuple) or not valor:
        raise ValueError(_CHAVE + "formato")
    if len(valor) > _MAXIMO:
        raise ValueError(_CHAVE + "muitos")
    minutos: list[int] = []
    for texto in valor:
        achou = _HHMM.fullmatch(texto) if isinstance(texto, str) else None
        if achou is None:
            raise ValueError(_CHAVE + "formato")
        minutos.append(int(achou[1]) * 60 + int(achou[2]))
    if len(set(minutos)) != len(minutos):
        raise ValueError(_CHAVE + "repetido")
    minutos.sort()
    voltas = [*minutos[1:], minutos[0] + 24 * 60]
    if any(b - a < _MINUTOS_ENTRE for a, b in zip(minutos, voltas, strict=True)):
        raise ValueError(_CHAVE + "perto")
    return tuple(time(m // 60, m % 60) for m in minutos)
