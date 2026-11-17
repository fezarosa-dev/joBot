"""Guarda dos guias para quem contribui: "Como consertar uma fonte que quebrou" (T83, ADR 0018)
e "Como acrescentar um site novo" (T299, M9).

Cada guia só vale se for igual nas duas línguas e se cada comando e cada caminho que ele cita
existir de verdade; o `CONTRIBUTING` de cada língua aponta para o guia dela.
"""

import json
import re
from pathlib import Path

import pytest

from jobot.cli import COMANDOS

RAIZ = Path(__file__).resolve().parents[2]
GUIAS = {
    "consertar-fonte": {"pt": "docs/consertar-fonte.md", "en": "docs/consertar-fonte.en.md"},
    "site-novo": {"pt": "docs/site-novo.md", "en": "docs/site-novo.en.md"},
}
MINIMO_DE_SECOES = {"consertar-fonte": 7, "site-novo": 8}
COM_COMANDO_JOBOT = {"consertar-fonte"}  # o guia de site novo cita `scripts/` e `uv run pytest`
ANCORAS_SITE_NOVO = ["antes", "forma", "copiar", "capturar", "ler", "login", "conferir", "pr"]
MOLDES = (
    "tests/apoio/molde_coletor.py",
    "tests/apoio/molde_leitor.py",
    "tests/unidade/test_site_novo.py",
)
guia = pytest.mark.parametrize("nome", GUIAS)
CONTRIBUTING = {"pt": ".github/CONTRIBUTING.md", "en": ".github/CONTRIBUTING.en.md"}
SECAO = re.compile(r"^(?:<a id=\"([a-z0-9-]+)\"></a>\n)?## (.+)$", re.M)
BLOCO = re.compile(r"^```[^\n]*\n(.*?)^```", re.M | re.S)
CRASES = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
EXTENSOES = (".py", ".md", ".json", ".toml", ".yml", ".html", ".lock")
# `fix/x` e `fonte/<id>` não são caminhos
PASTAS = ("src", "tests", "docs", "scripts", ".github", "wiki")


def texto(caminho: str) -> str:
    arquivo = RAIZ / caminho
    assert arquivo.is_file(), f"{caminho} não existe"
    return arquivo.read_text(encoding="utf-8")


def secoes(conteudo: str) -> list[tuple[str | None, str]]:
    """(âncora, título) de cada `##`; a âncora é a mesma nas duas línguas, o título não."""
    return [(m.group(1), m.group(2).strip()) for m in SECAO.finditer(conteudo)]


def trechos(conteudo: str) -> list[str]:
    """Linhas dos blocos de código e trechos entre crases, que são onde o guia cita comando."""
    blocos = [linha for b in BLOCO.findall(conteudo) for linha in b.splitlines() if linha.strip()]
    return blocos + CRASES.findall(BLOCO.sub("", conteudo))


def existe(caminho: str) -> bool:
    """O caminho existe; com marcador (`test_<fonte>.py`), vale o trecho antes do primeiro `<`."""
    antes, marcador, _ = caminho.partition("<")
    alvo = RAIZ / antes
    if not marcador:
        return alvo.exists()
    if antes.endswith("/"):
        return alvo.is_dir()
    return alvo.parent.is_dir() and any(p.name.startswith(alvo.name) for p in alvo.parent.iterdir())


def problemas(trecho: str) -> list[str]:
    """Comando `jobot` fora de `COMANDOS` e caminho que não existe no repositório.

    Só o primeiro token depois de `jobot` conta. Vale como caminho o que começa numa pasta do
    projeto (`PASTAS`) ou termina em extensão de arquivo; arquivo citado sem pasta (que não dá
    para conferir) é problema, e `.json` solto é só a menção de uma extensão.
    """
    achados: list[str] = []
    tokens = trecho.replace('"', " ").split()
    for atual, proximo in zip(tokens, [*tokens[1:], ""], strict=True):
        if atual == "jobot" and proximo and not proximo.startswith("-"):
            if proximo not in COMANDOS:
                achados.append(f"comando jobot desconhecido: {proximo}")
        elif "/" in atual and (
            atual.split("/")[0] in PASTAS or atual.rstrip(",.;:)").endswith(EXTENSOES)
        ):
            caminho = atual.rstrip(",.;:)")
            if not existe(caminho):
                achados.append(f"caminho não existe: {caminho}")
        elif atual.endswith(EXTENSOES) and not atual.startswith(".") and not existe(atual):
            achados.append(f"arquivo sem pasta: {atual}")
    return achados


@guia
def test_guia_tem_as_mesmas_secoes_em_pt_e_en(nome: str) -> None:
    pt, en = secoes(texto(GUIAS[nome]["pt"])), secoes(texto(GUIAS[nome]["en"]))
    assert len(pt) >= MINIMO_DE_SECOES[nome]
    assert all(ancora for ancora, _ in pt + en), "todo `##` leva a âncora antes do título"
    assert [a for a, _ in pt] == [a for a, _ in en]
    assert all(
        titulo_pt != titulo_en for (_, titulo_pt), (_, titulo_en) in zip(pt, en, strict=True)
    )
    if nome == "site-novo":
        assert [a for a, _ in pt] == ANCORAS_SITE_NOVO


@guia
def test_comandos_e_caminhos_citados_existem(nome: str) -> None:
    for lingua, caminho in GUIAS[nome].items():
        citados = trechos(texto(caminho))
        if nome in COM_COMANDO_JOBOT:
            assert any("jobot" in t.split() for t in citados), f"{lingua}: nenhum comando jobot"
        assert any("scripts/capturar.py" in t for t in citados), f"{lingua}: sem o capturar.py"
        achados = [p for t in citados for p in problemas(t)]
        assert achados == [], f"{caminho}: {achados}"


def test_conferencia_pega_comando_e_caminho_que_nao_existem() -> None:
    assert problemas("jobot buscar --ajuda") == []
    assert problemas("uv run python scripts/capturar.py <fonte> --caso novo") == []
    assert problemas("tests/fixtures/<fonte>/") == []
    assert problemas("tests/unidade/coletores/test_<fonte>.py") == []
    assert problemas("tests/unidade/nada/test_<fonte>.py") != []
    assert problemas("fix/greenhouse-campos") == [] and problemas(".html") == []
    assert problemas("jobot voar") == ["comando jobot desconhecido: voar"]
    assert problemas("scripts/nao_existe.py") == ["caminho não existe: scripts/nao_existe.py"]
    assert problemas("fontes.json") == ["arquivo sem pasta: fontes.json"]
    # âncora entre crases conta como caminho: só dentro de link
    assert problemas("docs/site-novo.md#copiar") != []


@guia
def test_links_relativos_do_guia_existem(nome: str) -> None:
    for caminho in GUIAS[nome].values():
        base = (RAIZ / caminho).parent
        alvos = [a for a in LINK.findall(texto(caminho)) if not re.match(r"[a-z][a-z0-9+.-]*:", a)]
        assert alvos, f"{caminho}: nenhum link relativo"
        for alvo in alvos:
            arquivo = alvo.split("#")[0]
            assert not arquivo or (base / arquivo).exists(), f"{caminho}: {alvo} não existe"


@guia
def test_contributing_cita_o_guia(nome: str) -> None:
    for lingua, caminho in CONTRIBUTING.items():
        alvos = {a.split("#")[0] for a in LINK.findall(texto(caminho))}
        proprio = f"../{GUIAS[nome][lingua]}"
        outro = f"../{GUIAS[nome]['en' if lingua == 'pt' else 'pt']}"
        assert proprio in alvos, f"{caminho} não aponta para {proprio}"
        assert outro not in alvos, f"{caminho} aponta para o guia da outra língua"
        assert (RAIZ / caminho).parent.joinpath(proprio).resolve().is_file()


def test_guia_de_site_novo_liga_os_moldes() -> None:
    for lingua, caminho in GUIAS["site-novo"].items():
        citados = set(CRASES.findall(texto(caminho)))
        faltam = [m for m in MOLDES if m not in citados]
        assert faltam == [], f"{lingua}: o guia não cita {faltam}"


def test_os_dois_guias_se_citam() -> None:
    for lingua in ("pt", "en"):
        for de, para in (("consertar-fonte", "site-novo"), ("site-novo", "consertar-fonte")):
            base = (RAIZ / GUIAS[de][lingua]).parent
            alvos = {a.split("#")[0] for a in LINK.findall(texto(GUIAS[de][lingua]))}
            ligado = {(base / a).resolve() for a in alvos if a}
            assert (RAIZ / GUIAS[para][lingua]).resolve() in ligado, f"{de} ({lingua}) sem {para}"


def test_guia_de_conserto_e_o_contributing_dizem_a_mesma_fase() -> None:
    """PR de código só depois da publicação: a fase é a mesma no guia e no `CONTRIBUTING`."""
    padrao = {
        "pt": re.compile(r"depois da publicação \(fase (\d+)\)"),
        "en": re.compile(r"after the release \(phase (\d+)\)"),
    }
    for lingua, regra in padrao.items():
        fases = {}
        caminhos = {
            "contributing": CONTRIBUTING[lingua],
            **{nome: GUIAS[nome][lingua] for nome in GUIAS},
        }
        for rotulo, caminho in caminhos.items():
            achadas = regra.findall(texto(caminho))
            assert len(achadas) == 1, f"{caminho}: a fase de PR de código não aparece uma vez"
            fases[rotulo] = achadas[0]
        assert len(set(fases.values())) == 1, f"{lingua}: {fases}"


def test_guia_de_site_novo_cita_todo_campo_da_linha_de_fontes() -> None:
    """O passo da linha em `fontes.json` lista cada campo que `carregar_fontes` exige."""
    linha = json.loads((RAIZ / "src/jobot/nucleo/dados/fontes.json").read_text("utf-8"))
    obrigatorios = set(linha["github_issues"])
    for lingua, caminho in GUIAS["site-novo"].items():
        citados = set(CRASES.findall(texto(caminho)))
        faltam = sorted(obrigatorios - citados)
        assert faltam == [], f"{lingua}: o guia não cita o campo {faltam} de fontes.json"


def test_contributing_sem_promessa_de_comandos() -> None:
    # o guia já traz os comandos (seção 6): o CONTRIBUTING não promete documentá-los depois
    promessa = re.compile(
        r"serão documentados|will be documented|quando o código existir|code exists"
    )
    for caminho in CONTRIBUTING.values():
        assert not promessa.search(texto(caminho)), f"{caminho} ainda promete os comandos"
