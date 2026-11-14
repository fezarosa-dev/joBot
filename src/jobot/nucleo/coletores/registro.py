"""Registro dos coletores e limites das 28 fontes (desenho 8.1, DR-64)."""

import importlib
import json
import pkgutil
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from jobot.nucleo.coletores.base import Coletor, LimiteEscopo, LimitesDaFonte

_FONTES = Path(__file__).resolve().parents[1] / "dados" / "fontes.json"


def _sem_repeticao(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    """`json.loads` sobrescreve chave repetida em silêncio; aqui ela é erro."""
    achados: dict[str, Any] = {}
    for chave, valor in pares:
        if chave in achados:
            raise ValueError(f"chave repetida: {chave!r}")
        achados[chave] = valor
    return achados


def carregar_fontes(texto: str) -> dict[str, LimitesDaFonte]:
    bruto: dict[str, dict[str, Any]] = json.loads(texto, object_pairs_hook=_sem_repeticao)
    return {
        chave: LimitesDaFonte(
            **(
                dados
                | {"por_escopo": {n: LimiteEscopo(**v) for n, v in dados["por_escopo"].items()}}
            )
        )
        for chave, dados in bruto.items()
    }


@cache
def _fontes() -> dict[str, LimitesDaFonte]:
    return carregar_fontes(_FONTES.read_text(encoding="utf-8"))


def limites(chave: str) -> LimitesDaFonte:
    """Limites da fonte em `fontes.json`; `KeyError` se a chave não existir."""
    return _fontes()[chave]


def descobrir(pacote: str = "jobot.nucleo.coletores") -> Mapping[str, Coletor]:
    """Importa cada módulo do pacote (e dos subpacotes) e junta os `COLETOR` por `chave`."""
    raiz = importlib.import_module(pacote)
    achados: dict[str, Coletor] = {}
    for info in pkgutil.walk_packages(raiz.__path__, prefix=f"{pacote}."):
        coletor: Coletor | None = getattr(importlib.import_module(info.name), "COLETOR", None)
        if coletor is None:
            continue
        if coletor.chave in achados:
            raise ValueError(f"coletor repetido: {coletor.chave!r} (em {info.name})")
        achados[coletor.chave] = coletor
    return achados
