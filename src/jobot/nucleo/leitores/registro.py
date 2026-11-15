"""Registro explícito dos leitores com login (E2). Vazio na Parte A; a Parte B acrescenta."""

from jobot.nucleo.leitores.base import LeitorComLogin

LEITORES: tuple[LeitorComLogin, ...] = ()


def leitores() -> tuple[LeitorComLogin, ...]:
    """Os leitores registrados; chave repetida ou sem o sufixo `_logado` é `ValueError`."""
    vistas: set[str] = set()
    for leitor in LEITORES:
        if not leitor.chave.endswith("_logado"):
            raise ValueError(f"chave de leitor sem o sufixo _logado: {leitor.chave!r}")
        if leitor.chave in vistas:
            raise ValueError(f"chave de leitor repetida: {leitor.chave!r}")
        vistas.add(leitor.chave)
    return LEITORES
