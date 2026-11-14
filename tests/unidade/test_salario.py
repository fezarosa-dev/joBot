"""Leitura de salário (desenho 10.3, DR-25, DP4) contra `tests/casos/salario.json`."""

import json
from pathlib import Path
from typing import Any

import pytest

from jobot.nucleo.modelo import SalarioBruto
from jobot.nucleo.tratamento.salario import ler_salario

ARQUIVO = Path(__file__).resolve().parents[1] / "casos" / "salario.json"
CASOS: list[dict[str, Any]] = json.loads(ARQUIVO.read_text(encoding="utf-8"))
PADRAO = {"beneficios": [], "periodo_deduzido": False}


def test_ha_casos_suficientes() -> None:
    assert len(CASOS) >= 60


@pytest.mark.parametrize(
    "caso", CASOS, ids=[f"{i:02d}-{c['idioma']}-{c['texto']}" for i, c in enumerate(CASOS)]
)
def test_casos_do_json(caso: dict[str, Any]) -> None:
    bruto = caso.get("estruturado")
    texto = caso["texto"]
    if "tamanho" in caso:  # texto longo: completa com espaços até o tamanho do caso
        texto = texto.ljust(caso["tamanho"])
    salario = ler_salario(
        texto, SalarioBruto(**bruto) if bruto is not None else None, caso["idioma"]
    )
    if caso["esperado"] is None:
        assert salario is None
        return
    assert salario is not None
    obtido = {
        "moeda": salario.moeda,
        "minimo": salario.minimo,
        "maximo": salario.maximo,
        "periodo": salario.periodo,
        "mensal_minimo": salario.mensal_minimo,
        "plausivel": salario.plausivel,
        "beneficios": list(salario.beneficios),
        "periodo_deduzido": salario.periodo_deduzido,
    }
    assert obtido == PADRAO | caso["esperado"]
    if texto is not None or "texto_obtido" in caso:
        assert salario.texto == caso.get("texto_obtido", texto)
