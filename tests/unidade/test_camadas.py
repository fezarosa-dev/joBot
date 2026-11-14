import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "jobot"

PROIBIDOS_NO_NUCLEO = (
    "fastapi",
    "starlette",
    "jinja2",
    "jobot.painel",
    "jobot.agenda",
    "jobot.banco",
    "jobot.sistema",
    "jobot.cli",
)


def _importados(pasta: Path) -> list[tuple[Path, str]]:
    """Todo módulo importado por algum .py da pasta (vazio se a pasta não existe)."""
    achados: list[tuple[Path, str]] = []
    for arquivo in sorted(pasta.rglob("*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Import):
                achados += [(arquivo, a.name) for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
                achados.append((arquivo, no.module))
                achados += [(arquivo, f"{no.module}.{a.name}") for a in no.names]
    return achados


def _casa(modulo: str, proibido: str) -> bool:
    return modulo == proibido or modulo.startswith(proibido + ".")


def _ruins(pasta: Path, proibidos: tuple[str, ...]) -> list[str]:
    return [
        f"{arquivo.name}: {modulo}"
        for arquivo, modulo in _importados(pasta)
        if any(_casa(modulo, p) for p in proibidos)
    ]


def test_nucleo_nao_importa_camadas_de_fora() -> None:
    assert _ruins(FONTE / "nucleo", PROIBIDOS_NO_NUCLEO) == []


def test_painel_nao_importa_httpx() -> None:
    assert _ruins(FONTE / "painel", ("httpx",)) == []


def test_detector_acha_import_proibido(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import fastapi\nfrom jobot import painel\nimport os\n")
    assert _ruins(tmp_path, PROIBIDOS_NO_NUCLEO) == ["a.py: fastapi", "a.py: jobot.painel"]
