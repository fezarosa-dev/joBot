"""Guarda da wiki (ADR 0019): pares pt/en, links que não quebram e FAQ com fonte única."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
WIKI = RAIZ / "wiki"
SITE = "https://github.com/fezarosa-dev/joBot"
ESPECIAIS = {"_Sidebar", "_Footer"}
# página em português -> página em inglês; página nova sem par faz o teste falhar
PARES = {
    "Home": "Home-en",
    "A-ideia-e-a-historia": "The-idea-and-the-story",
    "Como-funciona": "How-it-works",
    "Tecnologias": "Technologies",
    "Decisoes": "Decisions",
    "Roteiro": "Roadmap",
    "Apoie": "Support-the-project",
    "Perguntas-frequentes": "Frequently-asked-questions",
    "Tirar-duvida": "Ask-a-question",
}
PAR_DE = PARES | {en: pt for pt, en in PARES.items()}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def paginas() -> dict[str, str]:
    """Nome da página (sem .md) -> texto, sem os arquivos especiais."""
    return {
        p.stem: p.read_text(encoding="utf-8")
        for p in sorted(WIKI.glob("*.md"))
        if p.stem not in ESPECIAIS
    }


def relativos(texto: str) -> list[str]:
    """Alvos de link markdown que não têm esquema e não são só uma âncora."""
    alvos = [m.group(1) for m in LINK.finditer(texto)]
    return [a for a in alvos if not re.match(r"[a-z][a-z0-9+.-]*:", a, re.I) and a[0] != "#"]


def texto(caminho: str) -> str:
    arquivo = RAIZ / caminho
    assert arquivo.is_file(), f"{caminho} não existe"
    return arquivo.read_text(encoding="utf-8")


def test_paginas_sao_exatamente_os_pares() -> None:
    assert WIKI.is_dir()
    assert set(paginas()) == set(PAR_DE)


def test_cada_pagina_linka_a_par() -> None:
    assert paginas()
    for nome, conteudo in paginas().items():
        alvos = {a.split("#")[0] for a in relativos(conteudo)}
        assert PAR_DE[nome] in alvos, f"{nome} não linka {PAR_DE[nome]}"


def test_links_relativos_apontam_para_pagina_da_wiki() -> None:
    fontes = {**paginas(), **{nome: texto(f"wiki/{nome}.md") for nome in sorted(ESPECIAIS)}}
    for nome, conteudo in fontes.items():
        for alvo in relativos(conteudo):
            destino = alvo.split("#")[0]
            assert not destino.endswith(".md") and not destino.startswith(
                ("../", "docs/", ".github/")
            ), f"{nome}: link para arquivo do repositório ({alvo}); use URL absoluta"
            assert (WIKI / f"{destino}.md").is_file(), f"{nome}: {alvo} não existe na wiki"


def test_readmes_apontam_para_a_wiki_e_nao_tem_faq_propria() -> None:
    casos = {
        "README.md": ("perguntas-frequentes", "Perguntas-frequentes"),
        "README.en.md": ("faq", "Frequently-asked-questions"),
    }
    for arquivo, (ancora, pagina) in casos.items():
        conteudo = texto(arquivo)
        assert f'<a id="{ancora}"></a>' in conteudo, arquivo
        assert f"{SITE}/wiki/{pagina}" in conteudo, arquivo
        assert "<details" not in conteudo, f"{arquivo}: FAQ tem fonte única na wiki"
    assert f"{SITE}/wiki/Apoie" in texto("README.md")
    assert f"{SITE}/wiki/Support-the-project" in texto("README.en.md")
    assert f"{SITE}/wiki/Apoie" in texto(".github/FUNDING.yml")


def test_apoio_cita_o_github_sponsors_em_todos_os_lugares() -> None:
    assert "github: fezarosa-dev" in texto(".github/FUNDING.yml")
    for arquivo in ("README.md", "README.en.md", "wiki/Apoie.md", "wiki/Support-the-project.md"):
        assert "https://github.com/sponsors/fezarosa-dev" in texto(arquivo), arquivo


def test_formulario_de_duvida_e_suporte() -> None:
    form = texto(".github/ISSUE_TEMPLATE/duvida.yml")
    assert "labels: [question]" in form
    assert f"{SITE}/wiki/Perguntas-frequentes" in form
    for arquivo in (".github/SUPPORT.md", ".github/SUPPORT.en.md"):
        conteudo = texto(arquivo)
        assert "?template=duvida.yml" in conteudo, arquivo
        assert "?template=sugestao.yml" in conteudo, arquivo


def test_workflow_da_wiki_so_roda_na_main() -> None:
    wf = texto(".github/workflows/wiki.yml")
    assert "pull_request" not in wf  # cobre pull_request e pull_request_target
    assert "contents: write" in wf
    assert re.search(r"push:\s*\n\s*branches: \[main\]", wf)
