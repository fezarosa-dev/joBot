"""O caminho da D173 na prova do `uv` (T322, T338): instalação offline com hash de tudo."""

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]


def _provar() -> ModuleType:
    caminho = RAIZ / "scripts" / "provar_uv.py"
    spec = importlib.util.spec_from_file_location("provar_uv", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_linha_do_jobot_tem_a_versao_e_o_hash_da_wheel(tmp_path: Path) -> None:
    roda = tmp_path / "jobot-1.2.3-py3-none-any.whl"
    roda.write_bytes(b"wheel")
    esperado = hashlib.sha256(b"wheel").hexdigest()
    assert _provar().linha_do_jobot(roda) == f"jobot==1.2.3 --hash=sha256:{esperado}\n"


def test_instalar_offline_exige_hash_e_nao_usa_indice(tmp_path: Path) -> None:
    venv, rodas, restricoes = tmp_path / "venv", tmp_path / "wheels", tmp_path / "r.txt"
    assert _provar().comando_offline(venv, rodas, restricoes) == [
        "uv",
        "pip",
        "install",
        "--python",
        str(venv),
        "--offline",
        "--no-index",
        "--find-links",
        str(rodas),
        "--require-hashes",
        "-r",
        str(restricoes),
    ]
