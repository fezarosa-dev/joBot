"""Guarda de site completo: todo coletor e leitor registrado tem teste, exemplo e nome (M5)."""

import hashlib
import importlib.util
import json
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

from jobot.nucleo.coletores.registro import descobrir
from jobot.nucleo.leitores.registro import leitores

RAIZ = Path(__file__).resolve().parents[2]
GUIA = "docs/site-novo.md"


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capturar_guarda", RAIZ / "scripts/capturar.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


capturar = _carregar()


def faltas(raiz: Path, coletores: Iterable[str], leitores: Iterable[str]) -> list[str]:
    """Uma linha por falta, com a chave e a seção do guia que ensina a resolvê-la."""
    coletores, leitores = list(coletores), list(leitores)
    achadas: list[str] = []
    for chave in coletores:
        teste = f"tests/unidade/coletores/test_{chave}.py"
        if not (raiz / teste).is_file():
            achadas.append(f"{chave}: falta {teste} ({GUIA}#copiar)")
    for chave in leitores:
        teste = f"tests/unidade/test_leitor_{chave.removesuffix('_logado')}.py"
        if not (raiz / teste).is_file():
            achadas.append(f"{chave}: falta {teste} ({GUIA}#login)")
        pasta = f"tests/fixtures/{chave}"
        achadas += [
            f"{chave}: {pasta}: {p} ({GUIA}#login)" for p in capturar.problemas(raiz / pasta)
        ]
    for lingua in ("pt", "en"):
        catalogo = f"src/jobot/painel/i18n/{lingua}/comum.json"
        nomes = json.loads((raiz / catalogo).read_text(encoding="utf-8"))
        achadas += [
            f"{chave}: falta fonte.{chave} em {catalogo} ({GUIA}#copiar)"
            for chave in coletores + leitores
            if f"fonte.{chave}" not in nomes
        ]
    return achadas


def _arvore(raiz: Path, coletor: str = "site_x", leitor: str = "site_y_logado") -> None:
    """Árvore mínima completa: teste do coletor, teste e exemplo do leitor, os dois catálogos."""
    (raiz / "tests/unidade/coletores").mkdir(parents=True)
    (raiz / f"tests/unidade/coletores/test_{coletor}.py").write_text("", encoding="utf-8")
    teste_leitor = leitor.removesuffix("_logado")
    (raiz / f"tests/unidade/test_leitor_{teste_leitor}.py").write_text("", encoding="utf-8")
    pasta = raiz / "tests/fixtures" / leitor
    pasta.mkdir(parents=True)
    caso = pasta / "busca.html"
    caso.write_text("<html><body>vaga</body></html>", encoding="utf-8")
    meta = {
        "url": "https://vagas.exemplo.invalid/busca",
        "data": "2026-11-16T12:00:00+00:00",
        "codigo": 200,
        "cabecalhos": {"Content-Type": "text/html"},
        "sha256": hashlib.sha256(caso.read_bytes()).hexdigest(),
        "versao": "0.1.0",
        "montado_a_mao": True,
    }
    (pasta / "busca.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    for lingua in ("pt", "en"):
        catalogo = raiz / f"src/jobot/painel/i18n/{lingua}/comum.json"
        catalogo.parent.mkdir(parents=True)
        nomes = {f"fonte.{coletor}": "Site X", f"fonte.{leitor}": "Site Y"}
        catalogo.write_text(json.dumps(nomes), encoding="utf-8")


def test_todo_site_registrado_esta_completo() -> None:
    assert faltas(RAIZ, descobrir(), [leitor.chave for leitor in leitores()]) == []


def test_faltas_acha_coletor_sem_teste(tmp_path: Path) -> None:
    _arvore(tmp_path)
    (tmp_path / "tests/unidade/coletores/test_site_x.py").unlink()
    achadas = faltas(tmp_path, ["site_x"], ["site_y_logado"])
    assert len(achadas) == 1, achadas
    assert "site_x" in achadas[0] and f"{GUIA}#copiar" in achadas[0], achadas


def test_faltas_acha_leitor_sem_teste(tmp_path: Path) -> None:
    _arvore(tmp_path)
    (tmp_path / "tests/unidade/test_leitor_site_y.py").unlink()
    achadas = faltas(tmp_path, ["site_x"], ["site_y_logado"])
    assert len(achadas) == 1, achadas
    assert "site_y_logado" in achadas[0] and f"{GUIA}#login" in achadas[0], achadas


def test_faltas_acha_leitor_com_exemplo_ruim(tmp_path: Path) -> None:
    _arvore(tmp_path)
    pasta = tmp_path / "tests/fixtures/site_y_logado"
    meta = json.loads((pasta / "busca.meta.json").read_text(encoding="utf-8"))
    (pasta / "busca.meta.json").write_text(json.dumps(meta | {"sha256": "0" * 64}), "utf-8")
    achadas = faltas(tmp_path, ["site_x"], ["site_y_logado"])
    assert len(achadas) == 1, achadas
    assert "tests/fixtures/site_y_logado" in achadas[0] and "sha256" in achadas[0], achadas
    assert f"{GUIA}#login" in achadas[0], achadas
    for arquivo in pasta.iterdir():  # pasta sem nenhum caso: também é falta
        arquivo.unlink()
    assert any("tests/fixtures/site_y_logado" in a for a in faltas(tmp_path, [], ["site_y_logado"]))


def test_faltas_acha_site_sem_nome_no_catalogo(tmp_path: Path) -> None:
    _arvore(tmp_path)
    for lingua, chave in (("en", "site_x"), ("pt", "site_y_logado")):
        catalogo = tmp_path / f"src/jobot/painel/i18n/{lingua}/comum.json"
        nomes = json.loads(catalogo.read_text(encoding="utf-8"))
        del nomes[f"fonte.{chave}"]
        catalogo.write_text(json.dumps(nomes), encoding="utf-8")
    achadas = faltas(tmp_path, ["site_x"], ["site_y_logado"])
    assert len(achadas) == 2, achadas
    sem_en, sem_pt = sorted(achadas, key=lambda a: "site_y_logado" in a)
    assert "fonte.site_x" in sem_en and "en/comum.json" in sem_en, achadas
    assert "fonte.site_y_logado" in sem_pt and "pt/comum.json" in sem_pt, achadas
    assert all(f"{GUIA}#copiar" in a for a in achadas), achadas


def test_moldes_ficam_fora_do_registro() -> None:
    # só vale com os moldes no lote; sem eles passa à toa (prova por mutação na junção)
    assert "molde_coletor" not in descobrir()
    assert "molde_logado" not in [leitor.chave for leitor in leitores()]
