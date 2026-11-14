"""Nome com `_` é do módulo que o define: quem importa de fora usa o nome público (T106)."""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTAS = (
    RAIZ / "src" / "jobot" / "painel" / "rotas",
    RAIZ / "src" / "jobot" / "agenda",
    RAIZ / "scripts",
)


def _privados_importados(pasta: Path) -> list[str]:
    achados: list[str] = []
    for arquivo in sorted(pasta.rglob("*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ImportFrom):
                achados += [
                    f"{arquivo.name}:{no.lineno} {no.module or '.'}.{a.name}"
                    for a in no.names
                    if a.name.startswith("_") and not a.name.startswith("__")
                ]
    return achados


def test_nenhuma_rota_importa_nome_privado_de_outro_modulo() -> None:
    assert [achado for pasta in PASTAS for achado in _privados_importados(pasta)] == []


def test_o_detector_acha_import_de_nome_privado(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("from x import _a, b, __c__\nfrom y import d\n")
    assert [a.split(" ", 1)[1] for a in _privados_importados(tmp_path)] == ["x._a"]
