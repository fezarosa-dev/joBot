"""Guarda da página de arquitetura da wiki (T160): os diagramas Mermaid presos ao código.

A página existe em português e em inglês, com o mesmo conteúdo. O que ela afirma sobre o código
é conferido aqui: as tabelas e as chaves estrangeiras do ER vêm das migrações, os pacotes e as
dependências do diagrama de camadas vêm de `src/jobot`, e as funções da busca existem.
"""

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "jobot"
LINGUAS = ("pt", "en")
PAGINAS = {"pt": "Arquitetura", "en": "Architecture"}
README = {"pt": ("README.md", "Arquitetura"), "en": ("README.en.md", "Architecture")}
COMO_FUNCIONA = {"pt": "Como-funciona", "en": "How-it-works"}
SITE = "https://github.com/fezarosa-dev/joBot"
# `vaga_fts` e os gatilhos dela nascem no migrar.py (só com FTS5), não nos .sql: as duas valem
ESQUEMA = [*sorted((FONTE / "banco" / "migracoes").glob("*.sql")), FONTE / "banco" / "migrar.py"]

BLOCO_MERMAID = re.compile(r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
BLOCO_TEXTO = re.compile(r"^```text[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
RELACAO = re.compile(r"^\s*(\w+)\s+\S+--\S+\s+(\w+)\s*:", re.M)
SETA = re.compile(r"^\s*(\w+)\s*-->\s*(\w+)\s*$", re.M)


def _pagina(lingua: str) -> str:
    arquivo = RAIZ / "wiki" / f"{PAGINAS[lingua]}.md"
    assert arquivo.is_file(), f"wiki/{arquivo.name} não existe"
    return arquivo.read_text(encoding="utf-8")


def _bloco(pagina: str, tipo: str, marca: str | None = None) -> str:
    """O primeiro bloco Mermaid do `tipo` (e com a linha `%% marca`, se houver); "" se não há."""
    for bloco in BLOCO_MERMAID.findall(pagina):
        primeira = bloco.lstrip().splitlines()[0] if bloco.strip() else ""
        if primeira.startswith(tipo) and (marca is None or f"%% {marca}" in bloco):
            return bloco
    return ""


def _sql(texto: str) -> str:
    return re.sub(r"--[^\n]*", "", texto)


def _tabelas_de(textos: list[str]) -> set[str]:
    """Tabelas criadas (comuns e virtuais) menos as apagadas."""
    criadas: set[str] = set()
    apagadas: set[str] = set()
    for texto in map(_sql, textos):
        criadas |= set(
            re.findall(
                r"CREATE\s+(?:VIRTUAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", texto, re.I
            )
        )
        apagadas |= set(re.findall(r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)", texto, re.I))
    return criadas - apagadas


def _chaves_de(textos: list[str]) -> set[frozenset[str]]:
    """Pares {filho, pai} de cada REFERENCES, em CREATE TABLE e ALTER TABLE."""
    pares: set[frozenset[str]] = set()
    for texto in map(_sql, textos):
        for comando in texto.split(";"):
            if dono := re.match(r"\s*(?:CREATE\s+TABLE|ALTER\s+TABLE)\s+(\w+)", comando, re.I):
                pares |= {
                    frozenset((dono[1], pai))
                    for pai in re.findall(r"REFERENCES\s+(\w+)", comando, re.I)
                }
    return pares


def _textos_do_esquema() -> list[str]:
    return [a.read_text(encoding="utf-8") for a in ESQUEMA]


def _entidades(er: str) -> tuple[set[str], set[str]]:
    """(entidades definidas com `{`, entidades que só aparecem nas relações)."""
    definidas = set(re.findall(r"^\s*(\w+)\s*\{", er, re.M))
    nas_relacoes = {nome for par in RELACAO.findall(er) for nome in par}
    return definidas, nas_relacoes


def _pacotes() -> list[str]:
    return sorted(p.name for p in FONTE.iterdir() if (p / "__init__.py").is_file())


def _imports_entre_pacotes() -> set[tuple[str, str]]:
    """(quem importa, quem é importado) entre os pacotes de topo de `src/jobot`."""
    pacotes = set(_pacotes())
    achados: set[tuple[str, str]] = set()
    for arquivo in FONTE.rglob("*.py"):
        de = arquivo.relative_to(FONTE).parts[0]
        if de not in pacotes:
            continue
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Import):
                modulos = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
                modulos = [no.module, *(f"{no.module}.{a.name}" for a in no.names)]
            else:
                continue
            for modulo in modulos:
                partes = modulo.split(".")
                if partes[0] == "jobot" and len(partes) > 1 and partes[1] in pacotes - {de}:
                    achados.add((de, partes[1]))
    return achados


def _nomes_definidos() -> set[str]:
    achados: set[str] = set()
    for arquivo in FONTE.rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                achados.add(no.name)
    return achados


def _subpacotes_de_coletores() -> list[str]:
    pasta = FONTE / "nucleo" / "coletores"
    return sorted(p.name for p in pasta.iterdir() if (p / "__init__.py").is_file())


@pytest.mark.parametrize("lingua", LINGUAS)
def test_er_tem_todas_as_tabelas(lingua: str) -> None:
    er = _bloco(_pagina(lingua), "erDiagram")
    assert er, "a página não tem o erDiagram"
    definidas, _ = _entidades(er)
    assert sorted(_tabelas_de(_textos_do_esquema()) - definidas) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_er_nao_tem_tabela_que_nao_existe(lingua: str) -> None:
    er = _bloco(_pagina(lingua), "erDiagram")
    assert er, "a página não tem o erDiagram"
    definidas, nas_relacoes = _entidades(er)
    assert definidas  # sem entidade definida o teste não prova nada
    assert sorted((definidas | nas_relacoes) - _tabelas_de(_textos_do_esquema())) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_er_tem_as_chaves_estrangeiras(lingua: str) -> None:
    er = _bloco(_pagina(lingua), "erDiagram")
    assert er, "a página não tem o erDiagram"
    no_er = {frozenset(par) for par in RELACAO.findall(er)}
    chaves = _chaves_de(_textos_do_esquema())
    assert chaves  # o leitor de REFERENCES achou alguma
    assert sorted(tuple(sorted(c)) for c in chaves - no_er) == []


def test_leitor_do_esquema_acha_o_que_deve() -> None:
    tabelas = _tabelas_de(_textos_do_esquema())
    assert {"vaga", "evento", "execucao_fonte", "vaga_fts"} <= tabelas
    assert frozenset(("saude", "execucao")) in _chaves_de(_textos_do_esquema())


def test_leitor_do_esquema_tira_tabela_apagada_e_comentario() -> None:
    sql = "CREATE TABLE a (x INTEGER);\nCREATE TABLE b (y INTEGER REFERENCES a(x));\n"
    sql += "-- CREATE TABLE c (z INTEGER);\nDROP TABLE a;\nCREATE VIRTUAL TABLE d USING fts5(t);\n"
    assert _tabelas_de([sql]) == {"b", "d"}
    assert _chaves_de([sql]) == {frozenset(("a", "b"))}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_pagina_cita_os_gatilhos(lingua: str) -> None:
    pagina = _pagina(lingua)
    gatilhos = set(re.findall(r"CREATE\s+TRIGGER\s+(\w+)", "".join(_textos_do_esquema()), re.I))
    assert gatilhos  # o leitor achou algum
    assert sorted(g for g in gatilhos if g not in pagina) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_camadas_tem_todos_os_pacotes(lingua: str) -> None:
    camadas = _bloco(_pagina(lingua), "flowchart", "camadas")
    assert camadas, "a página não tem o diagrama de camadas (flowchart com '%% camadas')"
    assert sorted(set(_pacotes()) - set(re.findall(r"\w+", camadas))) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_camadas_tem_seta_para_todo_import_entre_pacotes(lingua: str) -> None:
    camadas = _bloco(_pagina(lingua), "flowchart", "camadas")
    assert camadas, "a página não tem o diagrama de camadas (flowchart com '%% camadas')"
    # a seta "A --> B" quer dizer "A importa B"
    setas = set(SETA.findall(camadas))
    reais = _imports_entre_pacotes()
    assert ("cli", "painel") in reais  # o leitor de imports achou algo
    assert sorted(reais - setas) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_pastas_cita_todo_subpacote(lingua: str) -> None:
    # só neste sentido: a página pode listar pasta que ainda vai nascer
    arvores = [b for b in BLOCO_TEXTO.findall(_pagina(lingua)) if "src/jobot" in b]
    assert arvores, "a página não tem a árvore de pastas (bloco text com src/jobot)"
    arvore = arvores[0]
    subpacotes = _subpacotes_de_coletores()
    assert subpacotes  # há subpacote real
    assert sorted(n for n in subpacotes if not re.search(rf"\b{n}/", arvore)) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_busca_so_cita_funcoes_que_existem(lingua: str) -> None:
    busca = _bloco(_pagina(lingua), "sequenceDiagram")
    assert busca, "a página não tem o sequenceDiagram"
    citadas = set(re.findall(r"\b([A-Za-z_]\w*)\(", busca))
    assert len(citadas) >= 8  # a busca passa por vários passos com nome real
    assert sorted(citadas - _nomes_definidos()) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_tem_casos_de_uso_e_classes(lingua: str) -> None:
    pagina = _pagina(lingua)
    assert _bloco(pagina, "flowchart", "casos-de-uso"), "falta o flowchart '%% casos-de-uso'"
    classes = _bloco(pagina, "classDiagram")
    assert classes, "falta o classDiagram"
    assert sorted(n for n in ("VagaColetada", "VagaTratada") if n not in classes) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_pagina_linkada_do_readme_da_como_funciona_e_da_barra(lingua: str) -> None:
    pagina = PAGINAS[lingua]
    arquivo, alvo = README[lingua]
    assert f"{SITE}/wiki/{alvo}" in (RAIZ / arquivo).read_text(encoding="utf-8")
    como = (RAIZ / "wiki" / f"{COMO_FUNCIONA[lingua]}.md").read_text(encoding="utf-8")
    assert f"]({pagina})" in como
    barra = (RAIZ / "wiki" / "_Sidebar.md").read_text(encoding="utf-8").splitlines()
    depois = barra.index(next(x for x in barra if f"]({COMO_FUNCIONA[lingua]})" in x)) + 1
    assert f"]({pagina})" in barra[depois]
