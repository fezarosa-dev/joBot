"""Guarda dos documentos de entrada (T79): README e CHANGELOG, em português e em inglês.

Os dois idiomas têm de ter as mesmas seções na mesma ordem; os avisos de uso, de termos, do
distrobox e de versão têm de estar lá; e todo comando `jobot` citado tem de existir no `--help`.
"""

import contextlib
import json
import re
import sqlite3
import tomllib
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from jobot import __version__
from jobot.agenda.versao import URL_VERSOES, aviso_ligado
from jobot.banco import cadastros
from jobot.banco.migrar import migrar
from jobot.cli import COMANDOS, main
from jobot.nucleo.cambio import BASE
from jobot.nucleo.coletores.descoberta_cc import COLLINFO
from jobot.painel import i18n
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
        "consentimento": r"consentimento prévio",
        "ligada": r"vem ligada",
        "onde": r"Configurações",
        "padrao_desligado": r"desligado por padrão",
    },
    "en": {
        "pessoal": r"personal use",
        "consentimento": r"prior consent",
        "ligada": r"comes on",
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


@pytest.mark.parametrize(
    ("lingua", "primeira", "estrelas"),
    [("pt", "o-que-e", "historico-de-estrelas"), ("en", "what-is-jobot", "star-history")],
)
def test_historico_de_estrelas_vem_logo_depois_de_o_que_e(
    lingua: str, primeira: str, estrelas: str
) -> None:
    ordem = ancoras(texto(README[lingua]))
    assert ordem.index(estrelas) == ordem.index(primeira) + 1


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
        re.search(frases["consentimento"], linha)
        and re.search(frases["onde"], linha)
        and re.search(frases["ligada"], linha)
        for linha in eureca
    ), f"{README[lingua]}: diga o consentimento prévio da Eureca e onde desligar"


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


def test_todas_as_fontes_vem_ligadas_por_padrao_como_os_documentos_dizem() -> None:
    """README e CHANGELOG dizem que todas as fontes, a Eureca incluída, vêm ligadas."""
    fontes = json.loads((RAIZ / "src/jobot/nucleo/dados/fontes.json").read_text(encoding="utf-8"))
    assert [c for c, d in fontes.items() if d.get("ligada_padrao", True) is False] == []


# Todo pedido de rede que o joBot faz (A53): cada item diz para quem e em que condição sai.
# (o que o item cita, o que diz da condição), por língua; cada par tem de estar na mesma frase.
# A condição "ligada" ou "desligada" não é escrita aqui: sai do padrão real (`_ligado_por_padrao`).
CITA: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "pt": {
        "fontes": (r"fontes públicas de vagas",),
        "banco central": (r"Banco Central",),
        "common crawl": (r"Common Crawl", r"uma vez por semana"),
        "páginas": (r"páginas que você manda acompanhar",),
        "endereço": (r"cola o endereço", r"só quando você"),
        "versão": (r"GitHub",),
        "atualização": (r"pelo git e pelo uv", r"só quando você pede para atualizar"),
    },
    "en": {
        "fontes": (r"public job sources",),
        "banco central": (r"Central Bank",),
        "common crawl": (r"Common Crawl", r"once a week"),
        "páginas": (r"pages you ask it to follow",),
        "endereço": (r"paste an address", r"only when you"),
        "versão": (r"GitHub",),
        "atualização": (r"through git and uv", r"only when you ask to update"),
    },
}
CONDICAO: Mapping[str, Mapping[bool, str]] = {
    "pt": {True: r"vem ligad[oa]\b", False: r"vem desligad[oa]\b"},
    "en": {True: r"comes on", False: r"comes off"},
}
# pedido -> chave de `PADROES` (cadastros.py) que diz se ele vem ligado
CHAVE_DO_PADRAO = {
    "banco central": "conversao_moeda_ligada",
    "common crawl": "descoberta_cc_ligada",
    "páginas": "paginas_ligadas",
}
# o que o texto diz das fontes: todas vêm ligadas (o `fontes.json` não desliga nenhuma)
FONTES_LIGADAS = {"pt": r"vêm todas ligadas", "en": r"all come on"}
# pedidos que só saem quando a pessoa age, sem padrão ligado ou desligado: a frase diz quando
SO_QUANDO_PEDE = {"endereço", "atualização"}


def test_condicao_aceita_os_dois_generos() -> None:
    """A condição em português não prende o gênero: `vem ligado` e `vem ligada` valem."""
    ligar, desligar = CONDICAO["pt"][True], CONDICAO["pt"][False]
    for genero in ("o", "a"):
        assert re.search(desligar, f"vem desligad{genero}")
        assert re.search(ligar, f"vem ligad{genero}")
        assert not re.search(ligar, f"vem desligad{genero}")
        assert not re.search(desligar, f"vem ligad{genero}")


def _ligado_por_padrao(pedido: str) -> bool:
    """O padrão de verdade do pedido: `PADROES` do banco, ou o padrão de código do aviso."""
    if pedido == "versão":
        with contextlib.closing(sqlite3.connect(":memory:")) as con:
            migrar(con, Path(":memory:"))
            return aviso_ligado(con)
    return bool(cadastros.PADROES[CHAVE_DO_PADRAO[pedido]])


def _condicoes(lingua: str) -> dict[str, tuple[str, ...]]:
    """Para cada pedido, o que a frase precisa trazer: o que cita e a condição do padrão real."""
    fontes = json.loads((RAIZ / "src/jobot/nucleo/dados/fontes.json").read_text(encoding="utf-8"))
    desligadas = sorted(c for c, d in fontes.items() if d.get("ligada_padrao", True) is False)
    assert not desligadas, f"o texto diz que todas vêm ligadas; o fontes.json desliga {desligadas}"
    exigido = {
        pedido: (*cita, CONDICAO[lingua][_ligado_por_padrao(pedido)])
        for pedido, cita in CITA[lingua].items()
        if pedido not in SO_QUANDO_PEDE and pedido != "fontes"
    }
    exigido["fontes"] = (
        *CITA[lingua]["fontes"],
        FONTES_LIGADAS[lingua],
    )
    exigido.update({p: CITA[lingua][p] for p in SO_QUANDO_PEDE})
    return exigido


def _frases(conteudo: str) -> list[str]:
    return [f.strip() for f in re.split(r"[;.]", conteudo) if f.strip()]


def _conferir_pedidos(lingua: str) -> None:
    privacidade = secao(texto(README[lingua]), SECAO_PRIVACIDADE[lingua])
    bullets = [linha for linha in privacidade.splitlines() if "Common Crawl" in linha]
    assert len(bullets) == 1, f"{README[lingua]}: o Common Crawl não está num item só"
    fontes = {
        README[lingua]: bullets[0],
        f"i18n/{lingua}": i18n.carregar()[lingua]["configuracoes.privacidade.telemetria"],
    }
    for nome, conteudo in fontes.items():
        frases = _frases(conteudo)
        for pedido, regexes in _condicoes(lingua).items():
            assert any(all(re.search(r, f) for r in regexes) for f in frases), (nome, pedido)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_privacidade_cita_todos_os_pedidos(lingua: str) -> None:
    """README e painel listam os mesmos pedidos de rede, com a condição do padrão real."""
    assert urlsplit(COLLINFO).hostname == "index.commoncrawl.org"
    assert urlsplit(BASE).hostname == "olinda.bcb.gov.br"
    _conferir_pedidos(lingua)


@pytest.mark.parametrize("lingua", LINGUAS)
@pytest.mark.parametrize("pedido", sorted(CHAVE_DO_PADRAO))
def test_texto_acompanha_o_padrao_real(
    lingua: str, pedido: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Padrão que muda sem o texto mudar derruba o teste (mutação dirigida de `PADROES`)."""
    chave = CHAVE_DO_PADRAO[pedido]
    invertido = {**cadastros.PADROES, chave: not cadastros.PADROES[chave]}
    monkeypatch.setattr(cadastros, "PADROES", invertido)
    with pytest.raises(AssertionError, match=re.escape(f"'{pedido}'")):
        _conferir_pedidos(lingua)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_nao_cita_duvida_por_numero(lingua: str) -> None:
    """Quem usa o joBot não conhece o `duvidas.md`: o item diz o efeito, não o número (D1, D3)."""
    achados = re.findall(r"\bD\d+\b", sem_blocos(texto(CHANGELOG[lingua])))
    assert achados == []


# o que cada documento diz da fase 1 (T132): concluída, e não mais "em andamento"
FASE_1_CONCLUIDA = {
    ".github/CONTRIBUTING.md": r"fase 1 \(base\) está concluída",
    ".github/CONTRIBUTING.en.md": r"Phase 1 \(foundation\) is complete",
    ".github/SECURITY.md": r"(?i)só a versão mais recente \(hoje a 0\.1\.0\)",
    ".github/SECURITY.en.md": r"(?i)only the latest version \(currently 0\.1\.0\)",
    ".github/SUPPORT.md": r"formulário de bug",
    ".github/SUPPORT.en.md": r"bug form",
    "docs/decisions/0017-fases.md": r"fase 1 está concluída",
    "docs/decisions/README.md": r"fase 1 está concluída",
    "wiki/Home.md": r"fase 1 de 8 \(a base\) está concluída",
    "wiki/Home-en.md": r"Phase 1 of 8 \(the base\) is complete",
    "wiki/A-ideia-e-a-historia.md": r"fase 1 de 8 \(a base\) está concluída",
    "wiki/The-idea-and-the-story.md": r"Phase 1 of 8 \(the base\) is complete",
    "wiki/Roteiro.md": r"\*\*1\. Base\*\*.*Concluída",
    "wiki/Roadmap.md": r"\*\*1\. Base\*\*.*Complete",
}
FASE_1_EM_ANDAMENTO = re.compile(
    r"em andamento|in progress|nada para instalar|nothing to install"
    r"|ainda não tem versão lançada|no released version yet",
    re.IGNORECASE,
)


@pytest.mark.parametrize("caminho", sorted(FASE_1_CONCLUIDA))
def test_status_da_fase_1_igual_nos_documentos(caminho: str) -> None:
    """A fase 1 consta como concluída em todo documento que fala dela, nas duas línguas (T132)."""
    conteudo = texto(caminho)
    assert re.search(FASE_1_CONCLUIDA[caminho], conteudo), f"{caminho} não diz que a fase 1 acabou"
    assert FASE_1_EM_ANDAMENTO.search(conteudo) is None, f"{caminho} ainda diz 'em andamento'"


def test_changelogs_com_a_mesma_data_da_0_1_0() -> None:
    datas = {
        lingua: re.search(r"^## \[0\.1\.0\] - (\S+)$", texto(CHANGELOG[lingua]), re.M)
        for lingua in LINGUAS
    }
    assert all(datas.values()), datas
    assert len({m.group(1) for m in datas.values() if m}) == 1
