"""A rota de sugeridas usa o nome público do painel, sem cópia local (T127)."""

import ast
from pathlib import Path

ROTA = Path(__file__).resolve().parents[2] / "src/jobot/painel/rotas/sugeridas.py"
COPIAS = {"_relogio", "relogio_do_painel", "de_volta", "_de_volta", "rodar", "_rodar"}


def test_sugeridas_nao_copia_nome_publico() -> None:
    arvore = ast.parse(ROTA.read_text(encoding="utf-8"))
    definidos = {
        n.name for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    assert definidos & COPIAS == set()
    importados = {
        (n.module, a.name)
        for n in ast.walk(arvore)
        if isinstance(n, ast.ImportFrom)
        for a in n.names
    }
    assert ("jobot.painel.rotas.vagas", "relogio_do_painel") in importados
