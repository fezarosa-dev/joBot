"""A casca (Rust) acha a pasta de dados com a mesma regra de `pastas.py` (desenho 7.1).

Conferência por texto: `pastas.py` é a fonte; `desktop/src/servidor.rs` repete os caminhos
(um `&[...]` por caminho) e as variáveis de ambiente. Se divergir muito, a casca passa a
perguntar `jobot dados --json`.
"""

import ast
import re
from pathlib import Path

from jobot.sistema import instancia, pastas

RAIZ = Path(__file__).resolve().parents[2]
SERVIDOR = RAIZ / "desktop" / "src" / "servidor.rs"
_ENV = re.compile(r"[A-Z][A-Z_]+")


def _funcao_python() -> ast.FunctionDef:
    arvore = ast.parse(Path(pastas.__file__).read_text(encoding="utf-8"))
    return next(
        n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "pasta_de_dados"
    )


def _partes(no: ast.expr | None) -> list[str]:
    """`base / "a" / "b"` vira `["a", "b"]`."""
    if (
        isinstance(no, ast.BinOp)
        and isinstance(no.op, ast.Div)
        and isinstance(no.right, ast.Constant)
        and isinstance(no.right.value, str)
    ):
        return [*_partes(no.left), no.right.value]
    return []


def _corpo_rust() -> str:
    texto = SERVIDOR.read_text(encoding="utf-8")
    inicio = texto.index("pub fn pasta_de_dados(")
    return texto[inicio : texto.index("\n}\n", inicio)]


def test_mesmos_caminhos_da_pasta_de_dados() -> None:
    python = sorted(
        tuple(p)
        for no in ast.walk(_funcao_python())
        if isinstance(no, ast.Return) and (p := _partes(no.value))
    )
    rust = sorted(
        tuple(re.findall(r'"([^"]*)"', lista))
        for lista in re.findall(r"&\[([^\]]*)\]", _corpo_rust())
    )
    assert len(python) == 5
    assert rust == python


def test_mesmas_variaveis_de_ambiente() -> None:
    python = {
        no.value
        for no in ast.walk(_funcao_python())
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and _ENV.fullmatch(no.value)
    }
    rust = {v for v in re.findall(r'"([^"]*)"', _corpo_rust()) if _ENV.fullmatch(v)}
    assert "JOBOT_DADOS" in python
    assert rust == python


def test_mesma_porta_padrao() -> None:
    texto = SERVIDOR.read_text(encoding="utf-8")
    assert f"pub const PORTA_PADRAO: u16 = {instancia.PORTA_PADRAO};" in texto
