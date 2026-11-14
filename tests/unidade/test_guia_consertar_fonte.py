"""Guarda do guia "Como consertar uma fonte que quebrou" (T83, ADR 0018).

O guia só vale se for igual nas duas línguas e se cada comando e cada caminho que ele cita
existir de verdade; o `CONTRIBUTING` de cada língua aponta para o guia dela.
"""

import re
from pathlib import Path

from jobot.cli import COMANDOS

RAIZ = Path(__file__).resolve().parents[2]
GUIAS = {"pt": "docs/consertar-fonte.md", "en": "docs/consertar-fonte.en.md"}
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


def test_guia_tem_as_mesmas_secoes_em_pt_e_en() -> None:
    pt, en = secoes(texto(GUIAS["pt"])), secoes(texto(GUIAS["en"]))
    assert len(pt) >= 7
    assert all(ancora for ancora, _ in pt + en), "todo `##` leva a âncora antes do título"
    assert [a for a, _ in pt] == [a for a, _ in en]
    assert all(
        titulo_pt != titulo_en for (_, titulo_pt), (_, titulo_en) in zip(pt, en, strict=True)
    )


def test_comandos_e_caminhos_citados_existem() -> None:
    for lingua, caminho in GUIAS.items():
        citados = trechos(texto(caminho))
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


def test_links_relativos_do_guia_existem() -> None:
    for caminho in GUIAS.values():
        base = (RAIZ / caminho).parent
        alvos = [a for a in LINK.findall(texto(caminho)) if not re.match(r"[a-z][a-z0-9+.-]*:", a)]
        assert alvos, f"{caminho}: nenhum link relativo"
        for alvo in alvos:
            arquivo = alvo.split("#")[0]
            assert not arquivo or (base / arquivo).exists(), f"{caminho}: {alvo} não existe"


def test_contributing_cita_o_guia() -> None:
    for lingua, caminho in CONTRIBUTING.items():
        alvos = {a.split("#")[0] for a in LINK.findall(texto(caminho))}
        proprio = f"../{GUIAS[lingua]}"
        outro = f"../{GUIAS['en' if lingua == 'pt' else 'pt']}"
        assert proprio in alvos, f"{caminho} não aponta para {proprio}"
        assert outro not in alvos, f"{caminho} aponta para o guia da outra língua"
        assert (RAIZ / caminho).parent.joinpath(proprio).resolve().is_file()
