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
    "Atalhos-de-teclado": "Keyboard-shortcuts",
    "Arquitetura": "Architecture",
    "Tecnologias": "Technologies",
    "Decisoes": "Decisions",
    "Roteiro": "Roadmap",
    "Apoie": "Support-the-project",
    "Perguntas-frequentes": "Frequently-asked-questions",
    "Gmail-senha-de-app": "Gmail-app-password",
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


DOCS_GMAIL = ("README.md", "README.en.md")
# a nota "o cartão chega depois" que o lote Contas tira: a aba já existe
SEM_VERSAO_PROXIMA = (
    "versão próxima",
    "upcoming version",
    "chega com a aba",
    "arrives with the Accounts tab",
)
PAGINAS_COM_GMAIL = (
    "wiki/Gmail-senha-de-app.md",
    "wiki/Gmail-app-password.md",
    "wiki/Perguntas-frequentes.md",
    "wiki/Frequently-asked-questions.md",
)


def linhas_com_gmail() -> list[tuple[str, str]]:
    """(arquivo, linha) de toda linha que cita Gmail nas páginas da wiki e nos dois README."""
    arquivos = [f"wiki/{nome}.md" for nome in paginas()] + list(DOCS_GMAIL)
    return [
        (arquivo, linha)
        for arquivo in arquivos
        for linha in texto(arquivo).splitlines()
        if "Gmail" in linha
    ]


def test_gmail_sem_versao_proxima() -> None:
    linhas = linhas_com_gmail()
    # controle positivo: o conjunto não é vazio e pega as quatro páginas e os dois README
    assert {arquivo for arquivo, _ in linhas} >= set(PAGINAS_COM_GMAIL) | set(DOCS_GMAIL)
    for arquivo, linha in linhas:
        for frase in SEM_VERSAO_PROXIMA:
            assert frase not in linha, (arquivo, frase)


def nota_de_privacidade(arquivo: str) -> str:
    """A linha `>` logo depois do título da seção de privacidade."""
    linhas = texto(arquivo).splitlines()
    titulo = next(i for i, linha in enumerate(linhas) if linha.startswith("## 🔒"))
    nota = next((linha for linha in linhas[titulo + 1 : titulo + 4] if linha.startswith(">")), "")
    return nota


def test_nota_de_privacidade_sem_gmail_futuro() -> None:
    esperado = {
        "README.md": ("Configurações, Contas", "fase 6", "IA, Gmail"),
        "README.en.md": ("Settings, Accounts", "phase 6", "AI, Gmail"),
    }
    for arquivo, (aba, fase, velho) in esperado.items():
        nota = nota_de_privacidade(arquivo)
        assert aba in nota, arquivo  # controle positivo: a nota existe e cita a aba
        assert fase in nota, arquivo
        assert velho not in nota, arquivo
