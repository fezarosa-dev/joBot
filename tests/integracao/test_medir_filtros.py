"""O script que mede os filtros com muitas vagas (T170)."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).parents[2] / "scripts" / "medir_filtros.py"
_FILTROS = (
    "sem filtro novo",
    "país",
    "UF",
    "cidade",
    "empresa",
    "publicada há 7 dias",
    "não pode ter",
    "salário: só de",
    "salário: só até",
    "salário: de e até",
    "salário: com sem salário",
    "todos juntos",
)


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("medir_filtros", _SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_medir_filtros_roda_com_poucas_vagas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    banco = tmp_path / "m.db"
    codigo = _carregar().main(["--vagas", "200", "--banco", str(banco)])
    saida = capsys.readouterr().out
    assert codigo == 0
    linhas = saida.splitlines()
    for filtro in _FILTROS:
        assert sum(1 for linha in linhas if linha.startswith(filtro)) == 1, filtro
    assert banco.exists()


def test_medir_filtros_recusa_banco_que_ja_existe(tmp_path: Path) -> None:
    banco = tmp_path / "meu.db"
    banco.write_text("conteudo", encoding="utf-8")
    assert _carregar().main(["--vagas", "1", "--banco", str(banco)]) == 2
    assert banco.read_text(encoding="utf-8") == "conteudo"


def test_medir_filtros_recusa_zero_vagas(tmp_path: Path) -> None:
    banco = tmp_path / "m.db"
    assert _carregar().main(["--vagas", "0", "--banco", str(banco)]) == 2
    assert not banco.exists()
