"""Guarda dos arquivos de terceiros em `painel/static/`: o sha256 de cada `.meta.json` confere."""

import hashlib
import json
import shutil
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "jobot" / "painel" / "static"


def divergencias(pasta: Path) -> list[str]:
    """Arquivo descrito em `*.meta.json` que falta ou tem sha256 diferente do declarado."""
    metas = sorted(pasta.rglob("*.meta.json"))
    if not metas:
        return [f"{pasta}: nenhum .meta.json"]
    achados: list[str] = []
    for meta in metas:
        arquivos: dict[str, dict[str, str]] = json.loads(meta.read_text(encoding="utf-8"))[
            "arquivos"
        ]
        for nome, dados in arquivos.items():
            alvo = meta.parent / nome
            if not alvo.is_file():
                achados.append(f"{alvo.relative_to(pasta)}: falta")
            elif hashlib.sha256(alvo.read_bytes()).hexdigest() != dados["sha256"]:
                achados.append(f"{alvo.relative_to(pasta)}: sha256 diferente")
    return achados


def test_meta_json_confere_sha256() -> None:
    assert divergencias(STATIC) == []


def test_meta_json_hash_errado_e_detectado(tmp_path: Path) -> None:
    copia = tmp_path / "static"
    shutil.copytree(STATIC, copia)
    assert divergencias(copia) == []  # controle: a cópia fiel passa
    meta = copia / "vendor" / "htmx.meta.json"
    dados = json.loads(meta.read_text(encoding="utf-8"))
    dados["arquivos"]["htmx.min.js"]["sha256"] = "0" * 64
    meta.write_text(json.dumps(dados), encoding="utf-8")
    assert divergencias(copia) == ["vendor/htmx.min.js: sha256 diferente"]
    (copia / "fontes" / "OFL.txt").unlink()
    assert "fontes/OFL.txt: falta" in divergencias(copia)
