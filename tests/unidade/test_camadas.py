import ast
import tomllib
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
    "playwright",
    "jobot.navegador",
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


def _ruins_fora_de(fonte: Path, proibidos: tuple[str, ...], menos: tuple[str, ...]) -> list[str]:
    """Imports proibidos em `fonte`, menos nas pastas de `menos` (`painel`, `nucleo/ia`)."""
    return [
        f"{arquivo.name}: {modulo}"
        for arquivo, modulo in _importados(fonte)
        if not any(_dentro(arquivo.relative_to(fonte), m) for m in menos)
        and any(_casa(modulo, p) for p in proibidos)
    ]


def _dentro(relativo: Path, pasta: str) -> bool:
    partes = tuple(pasta.split("/"))
    return relativo.parts[: len(partes)] == partes


def _playwright_fora_do_navegador(raiz: Path) -> list[str]:
    """Quem importa `playwright` fora de `src/jobot/navegador` (inclui `scripts/*.py`)."""
    return _ruins_fora_de(raiz / "src" / "jobot", ("playwright",), ("navegador",)) + _ruins(
        raiz / "scripts", ("playwright",)
    )


def test_so_navegador_importa_playwright() -> None:
    assert _playwright_fora_do_navegador(RAIZ) == []


def test_pypdf_so_no_leitor_do_pdf() -> None:
    # desenho 8 da fase 4 (T435): o PDF só se abre no processo filho de `sistema/pdf.py`
    assert _ruins_fora_de(FONTE, ("pypdf",), ("sistema/pdf.py",)) == []
    assert _ruins_fora_de(FONTE, ("pypdf",), ()) == [
        "pdf.py: pypdf",
        "pdf.py: pypdf.PasswordType",
        "pdf.py: pypdf.PdfReader",
    ]


def test_captcha_so_em_navegador_e_painel() -> None:
    # ADR 0022: o 2Captcha só age na navegação com login da fase 2; fonte pública não o importa.
    assert _ruins_fora_de(FONTE, ("jobot.nucleo.captcha",), ("navegador", "painel")) == []


IA_SO_EM = ("agenda", "painel", "cli", "nucleo/ia")


def test_ia_so_em_agenda_painel_e_cli() -> None:
    # desenho 5 da fase 4: o `cli` monta os backends e os injeta no laço da `agenda` e no painel
    assert _ruins_fora_de(FONTE, ("jobot.nucleo.ia",), IA_SO_EM) == []


def test_camadas_de_baixo_nao_importam_navegador() -> None:
    for pasta in ("nucleo", "banco", "agenda", "sistema"):
        assert _ruins(FONTE / pasta, ("jobot.navegador",)) == [], pasta


def test_navegador_nao_importa_painel_agenda_cli() -> None:
    assert _ruins(FONTE / "navegador", ("jobot.painel", "jobot.agenda", "jobot.cli")) == []


def test_detector_acha_playwright_fora_do_navegador(tmp_path: Path) -> None:
    jobot = tmp_path / "src" / "jobot"
    (jobot / "navegador").mkdir(parents=True)
    (jobot / "nucleo").mkdir()
    (tmp_path / "scripts").mkdir()
    (jobot / "navegador" / "ok.py").write_text("import playwright\n")
    (jobot / "nucleo" / "a.py").write_text("from playwright.sync_api import sync_playwright\n")
    (tmp_path / "scripts" / "b.py").write_text("import playwright.sync_api\n")
    assert _playwright_fora_do_navegador(tmp_path) == [
        "a.py: playwright.sync_api",
        "a.py: playwright.sync_api.sync_playwright",
        "b.py: playwright.sync_api",
    ]


def test_detector_acha_captcha_fora_da_lista(tmp_path: Path) -> None:
    jobot = tmp_path / "jobot"
    for pasta in ("agenda", "painel", "navegador"):
        (jobot / pasta).mkdir(parents=True)
        (jobot / pasta / "x.py").write_text("from jobot.nucleo import captcha\n")
    assert _ruins_fora_de(jobot, ("jobot.nucleo.captcha",), ("navegador", "painel")) == [
        "x.py: jobot.nucleo.captcha"
    ]


def test_detector_acha_ia_fora_da_lista(tmp_path: Path) -> None:
    jobot = tmp_path / "jobot"
    for pasta in ("agenda", "painel", "cli", "nucleo/ia", "banco", "nucleo"):
        (jobot / pasta).mkdir(parents=True, exist_ok=True)
    for pasta in ("agenda", "painel", "cli", "banco"):
        (jobot / pasta / "x.py").write_text("from jobot.nucleo.ia import contrato\n")
    (jobot / "nucleo" / "ia" / "falso.py").write_text("from .contrato import Falha\n")
    (jobot / "nucleo" / "encaixe.py").write_text("import jobot.nucleo.ia.esquema\n")
    (jobot / "nucleo" / "iam.py").write_text("import jobot.nucleo.iam\n")  # outro nome
    assert _ruins_fora_de(jobot, ("jobot.nucleo.ia",), IA_SO_EM) == [
        "x.py: jobot.nucleo.ia",
        "x.py: jobot.nucleo.ia.contrato",
        "encaixe.py: jobot.nucleo.ia.esquema",
    ]


def test_detector_acha_navegador_em_banco(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("from jobot import navegador\n")
    assert _ruins(tmp_path, ("jobot.navegador",)) == ["a.py: jobot.navegador"]


def test_detector_acha_painel_no_navegador(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("from jobot.painel import rotas\nimport jobot.cli\n")
    assert _ruins(tmp_path, ("jobot.painel", "jobot.agenda", "jobot.cli")) == [
        "a.py: jobot.painel",
        "a.py: jobot.painel.rotas",
        "a.py: jobot.cli",
    ]


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


def test_playwright_e_dependencia_de_execucao() -> None:
    # D132.1: o navegador com login roda no uso normal, não só nos testes de tela.
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert "playwright==1.65.1" in pyproject["project"]["dependencies"]
    dev = pyproject["dependency-groups"]["dev"]
    assert "playwright==1.65.1" not in dev
    assert "pytest-playwright==0.10.0" in dev
