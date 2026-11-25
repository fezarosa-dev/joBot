"""Esqueleto (T445): o vermelho dos testes por asserção."""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

CURRICULO: tuple[str, ...] = ()
VAGA = ("", "")
PERFIL: dict[str, object] = {}
PERFIL_LONGO: dict[str, object] = {}


@dataclass(frozen=True)
class Caso:
    nome: str
    pedido: Any


def casos(modelo: str) -> list[Caso]:
    return []


def provar(*args: Any, **kwargs: Any) -> list[Any]:
    return []


def main(
    argv: Sequence[str] | None = None, *, env: Mapping[str, str] = os.environ, montar: Any = None
) -> int:
    return 3
