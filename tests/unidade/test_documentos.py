"""Guarda dos documentos de entrada (T79): README e CHANGELOG, em português e em inglês.

Os dois idiomas têm de ter as mesmas seções na mesma ordem; os avisos de uso, de termos, do
distrobox e de versão têm de estar lá; e todo comando `jobot` citado tem de existir no `--help`.
"""

import json
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from jobot import __version__
from jobot.agenda.versao import URL_VERSOES
from jobot.cli import COMANDOS, main
from jobot.sistema.caso import prefixo_host

RAIZ = Path(__file__).resolve().parents[2]
README = {"pt": "README.md", "en": "README.en.md"}
CHANGELOG = {"pt": "CHANGELOG.md", "en": "CHANGELOG.en.md"}
LINGUAS = ("pt", "en")

BLOCO = re.compile(r"^```[^\n]*\n(.*?)^```", re.M | re.S)
CRASES = re.compile(r"`([^`\n]+)`")
TITULO = re.compile(r"^(#{2,3}) (.+)$")
ANCORA = re.compile(r'^<a id="([a-z0-9-]+)"></a>$')
VERSAO = re.compile(r"\[([^\]]+)\]")
# o que o Keep a Changelog chama cada grupo, nas duas línguas
GRUPOS = {
    "Adicionado": "Added",
    "Alterado": "Changed",
    "Descontinuado": "Deprecated",
    "Removido": "Removed",
    "Corrigido": "Fixed",
    "Segurança": "Security",
}
SECAO_USO = {"pt": "licenca-e-avisos", "en": "license-and-notices"}
SECAO_INSTALACAO = {"pt": "requisitos-e-instalacao", "en": "requirements-and-installation"}
SECAO_PRIVACIDADE = {"pt": "privacidade-e-seguranca", "en": "privacy-and-security"}
# o que cada língua diz para o mesmo aviso
FRASES: Mapping[str, Mapping[str, str]] = {
    "pt": {
        "pessoal": r"uso pessoal",
        "desligada": r"desligada por padrão",
        "onde": r"Configurações",
        "padrao_desligado": r"desligado por padrão",
    },
    "en": {
        "pessoal": r"personal use",
        "desligada": r"off by default",
        "onde": r"Settings",
        "padrao_desligado": r"off by default",
    },
}


def texto(caminho: str) -> str:
    arquivo = RAIZ / caminho
    assert arquivo.is_file(), f"{caminho} não existe"
    return arquivo.read_text(encoding="utf-8")


def sem_blocos(conteudo: str) -> str:
    return BLOCO.sub("", conteudo)


def niveis_readme(conteudo: str) -> list[int]:
    """Nível (`##` ou `###`) de cada título, na ordem; o texto do título muda de língua."""
    linhas = sem_blocos(conteudo).splitlines()
    return [len(m.group(1)) for linha in linhas if (m := TITULO.match(linha)) is not None]


def ancoras(conteudo: str) -> list[str]:
    return [m.group(1) for linha in conteudo.splitlines() if (m := ANCORA.match(linha))]


def titulos_h2(conteudo: str) -> list[str]:
    linhas = sem_blocos(conteudo).splitlines()
    return [m.group(2) for linha in linhas if (m := TITULO.match(linha)) and len(m.group(1)) == 2]


def assinatura_changelog(conteudo: str) -> list[tuple[int, str, int]]:
    """(nível, nome canônico, itens) de cada `##` e `###` do CHANGELOG."""
    achados: list[tuple[int, str, int]] = []
    for linha in sem_blocos(conteudo).splitlines():
        if (m := TITULO.match(linha)) is not None:
            nivel, titulo = len(m.group(1)), m.group(2).strip()
            if nivel == 2:
                versao = VERSAO.search(titulo)
                nome = versao.group(1) if versao else titulo
                nome = "Unreleased" if nome == "Não lançado" else nome
            else:
                nome = GRUPOS.get(titulo, titulo)
            achados.append((nivel, nome, 0))
        elif linha.startswith("- ") and achados:
            nivel, nome, n = achados[-1]
            achados[-1] = (nivel, nome, n + 1)
    return achados


def secao(conteudo: str, ancora: str) -> str:
    """Da âncora dada até a próxima âncora (ou o fim)."""
    inicio = conteudo.index(f'<a id="{ancora}"></a>')
    resto = conteudo[inicio + 1 :]
    proxima = resto.find('<a id="')
    return resto if proxima < 0 else resto[:proxima]


def trechos(conteudo: str) -> list[str]:
    """Linhas dos blocos de código e trechos entre crases, que é onde o texto cita comando."""
    blocos = [linha for b in BLOCO.findall(conteudo) for linha in b.splitlines() if linha.strip()]
    return blocos + CRASES.findall(sem_blocos(conteudo))


def comandos_do_help(saida: str) -> dict[str, list[str]]:
    """Comando -> escolhas do argumento fixo (`ligar`, `desligar`, `status`), lidos do `--help`."""
    nomes = re.findall(r"^    (\S+) {2,}\S", saida, re.M)
    assert nomes, saida
    return {nome: [] for nome in nomes}


@pytest.fixture
def help_do_jobot(capsys: pytest.CaptureFixture[str]) -> dict[str, list[str]]:
    assert main(["--help"]) == 0
    comandos = comandos_do_help(capsys.readouterr().out)
    assert main(["segundo-plano", "--help"]) == 0
    escolhas = re.search(r"\{([a-z,-]+)\}", capsys.readouterr().out)
    assert escolhas is not None
    comandos["segundo-plano"] = escolhas.group(1).split(",")
    return comandos


def problemas(trecho: str, comandos: Mapping[str, list[str]]) -> list[str]:
    """Comando `jobot` que não está no `--help` e ação de `segundo-plano` que não existe."""
    achados: list[str] = []
    tokens = trecho.replace("`", " ").split()
    for i, atual in enumerate(tokens):
        if atual != "jobot" or i + 1 >= len(tokens) or tokens[i + 1].startswith("-"):
            continue
        comando = tokens[i + 1]
        if comando not in comandos:
            achados.append(f"comando jobot desconhecido: {comando}")
            continue
        escolhas = comandos[comando]
        acao = tokens[i + 2] if i + 2 < len(tokens) else ""
        if escolhas and acao and not acao.startswith(("-", "<", "[")) and acao not in escolhas:
            achados.append(f"ação desconhecida em jobot {comando}: {acao}")
    return achados


def test_readme_tem_as_mesmas_secoes_nas_duas_linguas() -> None:
    pt, en = texto(README["pt"]), texto(README["en"])
    assert len(titulos_h2(pt)) >= 15
    assert niveis_readme(pt) == niveis_readme(en)
    assert len(ancoras(pt)) == len(titulos_h2(pt)) - 1  # o Sumário é o único `##` sem âncora
    assert set(ancoras(pt)).isdisjoint(ancoras(en)), "a âncora de cada língua é da língua"
    assert all(a != b for a, b in zip(titulos_h2(pt), titulos_h2(en), strict=True))


def test_changelog_tem_as_mesmas_secoes_nas_duas_linguas() -> None:
    pt, en = texto(CHANGELOG["pt"]), texto(CHANGELOG["en"])
    assinatura = assinatura_changelog(pt)
    assert [nome for nivel, nome, _ in assinatura if nivel == 2][0] == "Unreleased"
    assert assinatura == assinatura_changelog(en)
    assert all(nome in GRUPOS.values() for nivel, nome, _ in assinatura if nivel == 3)


def test_changelog_traz_a_versao_0_1_0_do_pacote() -> None:
    projeto = tomllib.loads(texto("pyproject.toml"))["project"]["version"]
    assert projeto == __version__ == "0.1.0"
    for caminho in CHANGELOG.values():
        conteudo = texto(caminho)
        assert re.search(
            rf"^## \[{re.escape(projeto)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", conteudo, re.M
        )
        bloco = conteudo.split(f"[{projeto}]", 1)[1]
        assert bloco.count("\n- ") >= 8, f"{caminho}: a 0.1.0 precisa dizer o que a fase 1 entrega"


@pytest.mark.parametrize("lingua", LINGUAS)
def test_aviso_de_uso_pessoal_e_de_termos_cita_eureca_abler_e_gupy(lingua: str) -> None:
    avisos = secao(texto(README[lingua]), SECAO_USO[lingua])
    frases = FRASES[lingua]
    assert re.search(frases["pessoal"], avisos, re.I)
    for portal in ("Eureca", "Abler", "Gupy"):
        assert portal in avisos, f"{README[lingua]}: o aviso de termos não cita {portal}"
    eureca = [linha for linha in avisos.splitlines() if "Eureca" in linha]
    assert any(
        re.search(frases["desligada"], linha) and re.search(frases["onde"], linha)
        for linha in eureca
    ), f"{README[lingua]}: diga que a Eureca vem desligada e como ligar em Configurações"


@pytest.mark.parametrize("lingua", LINGUAS)
def test_instalacao_traz_o_caso_distrobox(lingua: str) -> None:
    instalacao = secao(texto(README[lingua]), SECAO_INSTALACAO[lingua])
    assert "distrobox" in instalacao
    assert "distrobox-host-exec" in instalacao  # é o que o joBot chama de dentro do container
    assert prefixo_host({"CONTAINER_ID": "x"}) == ("distrobox-host-exec",)
    assert prefixo_host({}) == ()


@pytest.mark.parametrize("lingua", LINGUAS)
def test_aviso_de_versao_diz_o_que_vai_no_pedido(lingua: str) -> None:
    privacidade = secao(texto(README[lingua]), SECAO_PRIVACIDADE[lingua])
    frases = FRASES[lingua]
    linhas = [linha for linha in privacidade.splitlines() if "api.github.com" in linha]
    assert linhas, f"{README[lingua]}: o aviso de versão não cita o api.github.com"
    aviso = " ".join(linhas)
    assert re.search(frases["padrao_desligado"], aviso)
    assert "user agent" in aviso.lower() and "IP" in aviso
    assert urlsplit(URL_VERSOES).hostname == "api.github.com"


@pytest.mark.parametrize("lingua", LINGUAS)
def test_todo_comando_citado_existe_no_help(
    lingua: str, help_do_jobot: dict[str, list[str]]
) -> None:
    assert set(help_do_jobot) == set(COMANDOS)
    citados = trechos(texto(README[lingua])) + trechos(texto(CHANGELOG[lingua]))
    assert any("jobot" in t.split() for t in citados)
    assert [p for t in citados for p in problemas(t, help_do_jobot)] == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_readme_cita_todos_os_comandos(lingua: str, help_do_jobot: dict[str, list[str]]) -> None:
    instalacao = secao(texto(README[lingua]), SECAO_INSTALACAO[lingua])
    citados = trechos(instalacao)
    for comando in help_do_jobot:
        assert any(re.search(rf"\bjobot {comando}\b", t) for t in citados), (
            f"{README[lingua]}: a seção de instalação não cita `jobot {comando}`"
        )


def test_conferencia_pega_comando_que_nao_existe(help_do_jobot: dict[str, list[str]]) -> None:
    assert problemas("uv run jobot buscar", help_do_jobot) == []
    assert problemas("jobot --help", help_do_jobot) == []
    assert problemas("jobot segundo-plano ligar", help_do_jobot) == []
    assert problemas("jobot voar", help_do_jobot) == ["comando jobot desconhecido: voar"]
    assert problemas("jobot segundo-plano pular", help_do_jobot) == [
        "ação desconhecida em jobot segundo-plano: pular"
    ]


@pytest.mark.parametrize("arquivo", [*README.values(), *CHANGELOG.values()])
def test_documento_ja_nao_promete_o_que_a_fase_1_entregou(arquivo: str) -> None:
    conteudo = texto(arquivo).lower()
    for velho in (
        "nada para instalar",
        "nothing to install",
        "(planejada)",
        "(planned)",
        "ainda vai ser feito",
        "is still to be designed",
    ):
        assert velho not in conteudo, f"{arquivo}: sobrou '{velho}'"


@pytest.mark.parametrize("arquivo", [*README.values(), *CHANGELOG.values()])
def test_sem_caminho_de_gabarito_nem_dado_pessoal_nem_autoria_de_ia(arquivo: str) -> None:
    conteudo = texto(arquivo)
    for proibido in ("dados_locais", "gabarito", "/home/", "/var/home", "Co-Authored"):
        assert proibido not in conteudo, f"{arquivo}: tem '{proibido}'"
    autoria = re.compile(
        r"generated with|(written|made|built|created|authored) (by|with) claude"
        r"|(escrit|feit|criad|gerad)[oa]s? (pel[oa]|com|por) (o )?claude",
        re.I,
    )
    assert autoria.search(conteudo) is None


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_cita_as_adrs_que_existem(lingua: str) -> None:
    adrs = (RAIZ / "docs/decisions").glob("[0-9][0-9][0-9][0-9]-*.md")
    ultima = max(int(p.name[:4]) for p in adrs)
    citada = re.search(r"ADRs 0001 \w+ (\d{4})", texto(CHANGELOG[lingua]))
    assert citada is not None, f"{CHANGELOG[lingua]}: a 0.1.0 cita as ADRs"
    assert int(citada.group(1)) == ultima


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_nao_perde_o_que_ja_estava_certo(lingua: str) -> None:
    conteudo = texto(CHANGELOG[lingua])
    assert "previa-social.png" in conteudo
    assert re.search(r"estrelas|star", conteudo, re.I)
    assert (RAIZ / "docs/imagens/previa-social.png").is_file()


@pytest.mark.parametrize("lingua", LINGUAS)
def test_selo_de_plataforma_nao_promete_o_que_nao_foi_testado(lingua: str) -> None:
    selo = [
        linha
        for linha in texto(README[lingua]).splitlines()
        if re.search(r"img\.shields\.io/badge/(plataformas|platforms)", linha)
    ]
    assert len(selo) == 1
    assert "Linux" in selo[0] and not re.search(r"Windows|macOS", selo[0])


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_leva_jobot_em_todo_comando_da_lista(lingua: str) -> None:
    """Lista de comandos numa linha: sem `jobot` em cada um, só o primeiro era conferido."""
    for linha in texto(CHANGELOG[lingua]).splitlines():
        crases = CRASES.findall(linha)
        if any(c.startswith("jobot ") for c in crases):
            assert all(c.startswith("jobot ") for c in crases), linha


def test_eureca_vem_desligada_por_padrao_como_os_documentos_dizem() -> None:
    """README e CHANGELOG prometem a Eureca desligada (D80 opção b); o padrão real é do T130."""
    fontes = json.loads((RAIZ / "src/jobot/nucleo/dados/fontes.json").read_text(encoding="utf-8"))
    if not any("ligada_padrao" in dados for dados in fontes.values()):
        pytest.skip("campo ligada_padrao ainda não existe (T130 não integrada)")
    assert fontes["eureca"].get("ligada_padrao", True) is False
