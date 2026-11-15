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
            elif isinstance(no, ast.ImportFrom):
                base = _base_do_import(arquivo, no)
                if base:
                    if no.module or no.level:
                        achados.append((arquivo, base))
                    achados += [(arquivo, f"{base}.{a.name}") for a in no.names]
    return achados


def _base_do_import(arquivo: Path, no: ast.ImportFrom) -> str:
    """Nome absoluto de onde o `from` importa; relativo resolve pelo caminho (jobot.…)."""
    if no.level == 0:
        return no.module or ""
    partes = list(arquivo.with_suffix("").parts)
    if "jobot" not in partes:
        return ""
    partes = partes[len(partes) - 1 - partes[::-1].index("jobot") :]
    if partes[-1] == "__init__":
        partes.pop()
    else:
        partes = partes[:-1]
    partes = partes[: max(len(partes) - (no.level - 1), 0)]
    if not partes:
        return ""
    return ".".join([*partes, *([no.module] if no.module else [])])


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


def test_captcha_so_fora_das_fontes_publicas() -> None:
    # ADR 0022: o 2Captcha só age na navegação com login da fase 2; fonte pública não o importa.
    for pasta in ("nucleo/coletores", "agenda", "cli"):
        assert _ruins(FONTE / pasta, ("jobot.nucleo.captcha",)) == [], pasta
    assert _ruins(FONTE / "nucleo", PROIBIDOS_NO_NUCLEO) == []


def test_detector_acha_import_do_captcha(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("from jobot.nucleo import captcha\n")
    assert _ruins(tmp_path, ("jobot.nucleo.captcha",)) == ["a.py: jobot.nucleo.captcha"]


def test_detector_resolve_import_relativo(tmp_path: Path) -> None:
    nucleo = tmp_path / "src" / "jobot" / "nucleo"
    (nucleo / "coletores").mkdir(parents=True)
    (nucleo / "coletores" / "x.py").write_text("from ...banco import gravacao\n")
    (nucleo / "y.py").write_text("from .. import painel\n")
    (nucleo / "coletores" / "z.py").write_text("from . import base\n")
    (nucleo / "coletores" / "__init__.py").write_text("from ...banco import gravacao\n")
    (nucleo / "coletores" / "w.py").write_text("from ......banco import gravacao\n")  # além do topo
    assert _ruins(nucleo, PROIBIDOS_NO_NUCLEO) == [
        "__init__.py: jobot.banco",
        "__init__.py: jobot.banco.gravacao",
        "x.py: jobot.banco",
        "x.py: jobot.banco.gravacao",
        "y.py: jobot.painel",
    ]
