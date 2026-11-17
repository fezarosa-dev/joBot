"""Guarda de site completo: todo coletor e leitor registrado tem teste, exemplo e nome (M5)."""

import hashlib
import importlib.util
import json
import re
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

from apoio.molde_leitor import MoldeLogado
from jobot.navegador.politica import casa_login
from jobot.nucleo.coletores.registro import descobrir
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.leitores.linkedin import LinkedIn
from jobot.nucleo.leitores.registro import leitores

RAIZ = Path(__file__).resolve().parents[2]
GUIA = "docs/site-novo.md"
_ANCORA = re.compile(r"\.md#([a-z0-9-]+)")


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


def prefixos_fora_do_host(leitores: Iterable[LeitorComLogin]) -> list[str]:
    """Uma linha por prefixo de login torto: o navegador casa `host + caminho` (`casa_login`)."""
    achadas: list[str] = []
    for leitor in leitores:
        if not leitor.prefixos_login:
            achadas.append(f"{leitor.chave}: sem prefixos_login ({GUIA}#login)")
        hosts = {h.lower() for h in leitor.hosts}
        for prefixo in leitor.prefixos_login:
            host, barra, _ = prefixo.partition("/")
            torto = (
                "://" in prefixo
                or not barra
                or host != host.lower()
                or host not in hosts
                or not casa_login(f"https://{prefixo}?x=1", leitor.prefixos_login)
            )
            if torto:
                achadas.append(
                    f"{leitor.chave}: prefixos_login {prefixo!r} deve ser host + caminho,"
                    f" com o host em minúsculas e igual a um dos hosts ({GUIA}#login)"
                )
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


def test_ancoras_citadas_pelas_faltas_existem_no_guia(tmp_path: Path) -> None:
    """A falta manda o leitor para uma seção do guia: a seção tem de existir, nas duas línguas."""
    _arvore(tmp_path)
    (tmp_path / "tests/unidade/coletores/test_site_x.py").unlink()
    (tmp_path / "tests/unidade/test_leitor_site_y.py").unlink()
    for lingua in ("pt", "en"):
        (tmp_path / f"src/jobot/painel/i18n/{lingua}/comum.json").write_text("{}", "utf-8")
    citadas = {
        a
        for falta in faltas(tmp_path, ["site_x"], ["site_y_logado"])
        for a in _ANCORA.findall(falta)
    }
    assert citadas == {"copiar", "login"}, citadas
    for caminho in (GUIA, GUIA.replace(".md", ".en.md")):
        arquivo = RAIZ / caminho
        assert arquivo.is_file(), f"{caminho} não existe"
        ancoras = set(re.findall(r'<a id="([a-z0-9-]+)"></a>', arquivo.read_text("utf-8")))
        assert citadas <= ancoras, f"{caminho}: faltam as âncoras {sorted(citadas - ancoras)}"


def test_todo_prefixo_de_login_comeca_pelo_host() -> None:
    assert prefixos_fora_do_host(leitores()) == []
    assert prefixos_fora_do_host([MoldeLogado()]) == []


def test_prefixo_so_de_caminho_reprova() -> None:
    class SoCaminho(LinkedIn):
        prefixos_login: tuple[str, ...] = ("/login", "/checkpoint/")

    achados = prefixos_fora_do_host([SoCaminho()])
    assert len(achados) == 2, achados
    assert all("linkedin_logado" in a and f"{GUIA}#login" in a for a in achados), achados
    assert "/login" in achados[0] and "/checkpoint/" in achados[1], achados


def test_prefixo_com_esquema_host_de_outro_site_ou_query_reprova() -> None:
    for prefixo in (
        "https://www.linkedin.com/login",
        "www.outro.invalid/login",
        "WWW.linkedin.com/login",
        "www.linkedin.com/login?next=1",  # a query não entra em `casa_login`: nunca casa
    ):

        class Torto(LinkedIn):
            prefixos_login: tuple[str, ...] = (prefixo,)

        achados = prefixos_fora_do_host([Torto()])
        assert len(achados) == 1, (prefixo, achados)
        assert prefixo in achados[0] and "linkedin_logado" in achados[0], achados


def test_prefixo_sem_caminho_ou_leitor_sem_prefixo_reprova() -> None:
    class SemCaminho(LinkedIn):
        prefixos_login: tuple[str, ...] = ("www.linkedin.com",)

    class SemNenhum(LinkedIn):
        prefixos_login: tuple[str, ...] = ()

    assert len(prefixos_fora_do_host([SemCaminho()])) == 1
    assert len(prefixos_fora_do_host([SemNenhum()])) == 1


def test_ancora_da_guarda_de_prefixo_existe_no_guia() -> None:
    for caminho in (GUIA, GUIA.replace(".md", ".en.md")):
        texto = (RAIZ / caminho).read_text("utf-8")
        assert '<a id="login"></a>' in texto, f"{caminho}: falta a seção #login"
        secao = texto.split('<a id="login"></a>', 1)[1].split("<a id=", 1)[0]
        assert "prefixos_login" in secao, f"{caminho}: #login não cita `prefixos_login`"


def test_moldes_ficam_fora_do_registro() -> None:
    # só vale com os moldes no lote; sem eles passa à toa (prova por mutação na junção)
    assert "molde_coletor" not in descobrir()
    assert "molde_logado" not in [leitor.chave for leitor in leitores()]
