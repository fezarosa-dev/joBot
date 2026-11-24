"""Consultas do painel fora de `rotas/`: a lateral as usa sem import circular (E4; T251)."""

import ast
from pathlib import Path

PAINEL = Path(__file__).resolve().parents[2] / "src/jobot/painel"
DE_CIMA = ("jobot.painel.rotas", "jobot.painel.seguranca", "jobot.painel.globais")
MOVIDOS = {
    "relogio_do_painel",
    "busca_efetiva",
    "utc_do_banco",
    "ids_destaques",
    "_ids_destaques",
    "leitores_do_painel",
}


def _modulos_importados(caminho: Path) -> set[str]:
    """Os módulos que o arquivo importa, `import x` e `from x import y` (com `x.y` também)."""
    nomes: set[str] = set()
    for n in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            nomes |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            nomes |= {n.module, *(f"{n.module}.{a.name}" for a in n.names)}
    return nomes


def _de_cima(caminho: Path) -> set[str]:
    return {m for m in _modulos_importados(caminho) if m.startswith(DE_CIMA)}


def test_detector_pega_os_jeitos_de_importar(tmp_path: Path) -> None:
    """Controle: as três formas caem; `jobot.painel.i18n` passa."""
    arquivo = tmp_path / "x.py"
    for fonte in (
        "from jobot.painel.rotas import vagas",
        "import jobot.painel.seguranca",
        "from jobot.painel import globais",
    ):
        arquivo.write_text(fonte, encoding="utf-8")
        assert _de_cima(arquivo), fonte
    arquivo.write_text("from jobot.painel.i18n import t", encoding="utf-8")
    assert not _de_cima(arquivo)


def test_consultas_nao_importa_o_painel_de_cima() -> None:
    assert _de_cima(PAINEL / "consultas.py") == set()


def test_lateral_nao_importa_rotas() -> None:
    assert _de_cima(PAINEL / "lateral.py") == set()


def test_nomes_movidos_sem_copia() -> None:
    donos: dict[str, list[str]] = {}
    for caminho in PAINEL.rglob("*.py"):
        for n in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name in MOVIDOS:
                donos.setdefault(n.name, []).append(str(caminho.relative_to(PAINEL)))
    assert donos == {
        "relogio_do_painel": ["consultas.py"],
        "busca_efetiva": ["consultas.py"],
        "utc_do_banco": ["consultas.py"],
        "ids_destaques": ["consultas.py"],
        "leitores_do_painel": ["ambiente.py"],
    }
