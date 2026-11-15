"""Os ajudantes de execução moram em `banco.execucoes`, não na agenda (T199, D132.39)."""

import ast
import asyncio
import sqlite3
from pathlib import Path

import pytest

from jobot.banco import execucoes

AGENDA = Path(__file__).parents[2] / "src" / "jobot" / "agenda"
NOMES = ("parada_de", "interromper", "manter_batimento")


@pytest.mark.parametrize("nome", NOMES)
def test_ajudantes_moram_no_banco(nome: str) -> None:
    assert hasattr(execucoes, nome)


def test_parada_de_no_banco() -> None:
    assert execucoes.parada_de(asyncio.CancelledError()) == "fechado"
    assert execucoes.parada_de(sqlite3.OperationalError()) == "banco"
    assert execucoes.parada_de(ValueError()) == "erro"


def test_agenda_nao_tem_copia_dos_ajudantes() -> None:
    proibidos = {*NOMES, "bater"}
    achados = [
        f"{arq.name}:{no.name}"
        for arq in sorted(AGENDA.glob("*.py"))
        for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8")))
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef) and no.name in proibidos
    ]
    assert achados == []
