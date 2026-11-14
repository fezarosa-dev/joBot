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


@pytest.mark.parametrize(
    ("texto", "minimo", "periodo"),
    [
        ("R$ 25 por hora e R$ 4.000", 2_500, "hora"),
        ("R$ 3.000 e R$ 30 por hora", 3_000, "hora"),
        ("R$ 3.000 mensais e R$ 3", 300_000, "mes"),
        # controles: faixa até 10 vezes (inclusive) e período dos dois lados seguem faixa
        ("R$ 4.000 por mês a R$ 6.000", None, "mes"),
        ("R$ 1.000 por mês a R$ 10.000", None, "mes"),
    ],
)
def test_faixa_com_periodo_de_um_lado_desproporcional_nao_forma_faixa(
    texto: str, minimo: int | None, periodo: str
) -> None:
    salario = ler_salario(texto, None, "pt")
    assert salario is not None
    assert salario.periodo == periodo
    if minimo is None:  # controle: continua faixa
        assert salario.minimo is not None
        assert salario.maximo is not None
        assert salario.minimo < salario.maximo
    else:
        assert salario.minimo == salario.maximo == minimo


def test_faixa_um_lado_com_periodo_acima_de_10_vezes_por_um_centavo() -> None:
    dentro = ler_salario("R$ 1.000 por mês e R$ 10.000", None, "pt")
    fora = ler_salario("R$ 1.000 por mês e R$ 10.001", None, "pt")
    assert dentro is not None
    assert fora is not None
    assert dentro.minimo == 100_000
    assert dentro.maximo == 1_000_000
    assert fora.minimo == fora.maximo == 100_000


def test_salario_estruturado_int_grande_nao_levanta() -> None:
    # json.loads aceita int de qualquer tamanho; Decimal(str(int)) estoura acima de 4.300 dígitos
    for bruto in (
        SalarioBruto(moeda="USD", minimo_unidades=10**4500, periodo="ano"),
        SalarioBruto(moeda="USD", minimo_unidades=1, maximo_unidades=10**4500, periodo="ano"),
    ):
        salario = ler_salario(None, bruto, "en")
        assert salario is not None
        assert salario.plausivel is False
