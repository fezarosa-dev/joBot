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
from jobot.banco import cadastros
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
        "padrao_ligado": r"(?<!des)ligado por padrão",
        "como_desligar": r"Para desligar",
    },
    "en": {
        "pessoal": r"personal use",
        "consentimento": r"prior consent",
        "ligada": r"comes on",
        "onde": r"Settings",
        "padrao_ligado": r"(?<!off )on by default",
        "como_desligar": r"To turn it off",
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


def test_changelog_traz_a_versao_do_pacote() -> None:
    projeto = tomllib.loads(texto("pyproject.toml"))["project"]["version"]
    assert projeto == __version__ == "0.5.0"
    for caminho in CHANGELOG.values():
        conteudo = texto(caminho)
        for versao in (projeto, "0.1.0"):
            assert re.search(
                rf"^## \[{re.escape(versao)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", conteudo, re.M
            )
        # a mais nova vem logo abaixo de "Não lançado", e a fase 1 continua dizendo o que entregou
        assert conteudo.index(f"[{projeto}]") < conteudo.index("[0.1.0]")
        bloco = conteudo.split("[0.1.0]", 1)[1]
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


def test_casca_tem_a_mesma_versao_do_pacote() -> None:
    projeto = tomllib.loads(texto("pyproject.toml"))["project"]["version"]
    cargo = tomllib.loads(texto("desktop/Cargo.toml"))["package"]["version"]
    tauri = json.loads(texto("desktop/tauri.conf.json")).get("version")
    assert (cargo, tauri) == (projeto, projeto), "versão única nos três (desenho 8)"


def test_gitignore_tem_as_pastas_geradas_da_casca() -> None:
    linhas = {linha.strip() for linha in texto(".gitignore").splitlines()}
    pastas = {"desktop/target/", "desktop/ui/painel/", "desktop/binaries/", "desktop/recursos/"}
    assert pastas <= linhas, sorted(pastas - linhas)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_aviso_de_versao_diz_o_que_vai_no_pedido(lingua: str) -> None:
    privacidade = secao(texto(README[lingua]), SECAO_PRIVACIDADE[lingua])
    frases = FRASES[lingua]
    linhas = [linha for linha in privacidade.splitlines() if "api.github.com" in linha]
    assert linhas, f"{README[lingua]}: o aviso de versão não cita o api.github.com"
    aviso = " ".join(linhas)
    assert re.search(frases["padrao_ligado"], aviso)  # D105: o aviso nasce ligado
    assert re.search(frases["como_desligar"], aviso) and re.search(frases["onde"], aviso)
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
    conteudo = texto(CHANGELOG[lingua])
    assert re.search(r"ADRs 0001 \w+ \d{4}", conteudo), f"{CHANGELOG[lingua]}: a 0.1.0 cita as ADRs"
    citadas = [int(n) for n in re.findall(r"ADRs? (?:0001 \w+ )?(\d{4})", conteudo)]
    assert max(citadas) == ultima


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
        "atualização": (
            r"pelo git e pelo uv",
            r"só quando você pede para atualizar",
            r"Atualizar agora",
        ),
        "2captcha": (r"2Captcha", r"testa a chave"),
        "sites com login": (r"sites com login que você liga", r"vêm desligados", r"pelo navegador"),
        "navegador": (
            r"servidores do Playwright",
            r"só quando você",
            r"o marca na instalação",
        ),
        "gmail": (r"Gmail", r"senha de app", r"só quando você"),
        "ia": (
            r"serviços de IA",
            r"API da Anthropic",
            r"OpenAI",
            r"Gemini",
            r"endereço compatível",
            r"só quando você liga",
            r"as tarefas vêm desligadas",
            r"seu perfil",
            r"currículo",
        ),
        "modelo local": (r"GitHub", r"Hugging Face", r"CDNs", r"modelo local", r"só quando você"),
    },
    "en": {
        "fontes": (r"public job sources",),
        "banco central": (r"Central Bank",),
        "common crawl": (r"Common Crawl", r"once a week"),
        "páginas": (r"pages you ask it to follow",),
        "endereço": (r"paste an address", r"only when you"),
        "versão": (r"GitHub",),
        "atualização": (r"through git and uv", r"only when you ask to update", r"Update now"),
        "2captcha": (r"2Captcha", r"test the key"),
        "sites com login": (r"sites with login you turn on", r"come off", r"through the browser"),
        "navegador": (
            r"Playwright's servers",
            r"only when you",
            r"check it during installation",
        ),
        "gmail": (r"Gmail", r"app password", r"only when you"),
        "ia": (
            r"AI services",
            r"Anthropic API",
            r"OpenAI",
            r"Gemini",
            r"compatible address",
            r"only when you turn on",
            r"the tasks come off",
            r"your profile",
            r"résumé",
        ),
        "modelo local": (r"GitHub", r"Hugging Face", r"CDNs", r"local model", r"only when you"),
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
    "versão": "aviso_versao_ligada",
    "2captcha": "captcha_ligado",
}
# o que o texto diz das fontes: todas vêm ligadas (o `fontes.json` não desliga nenhuma)
FONTES_LIGADAS = {"pt": r"vêm todas ligadas", "en": r"all come on"}
# pedidos que só saem quando a pessoa age, sem padrão ligado ou desligado: a frase diz quando
# (os sites com login são vários, cada um com a sua chave, sempre desligada: a frase diz isso)
# (as tarefas de IA também: a frase diz que vêm desligadas, e `_condicoes` confere o `ia_tarefas`)
SO_QUANDO_PEDE = {
    "endereço",
    "atualização",
    "sites com login",
    "navegador",
    "gmail",
    "ia",
    "modelo local",
}


def test_condicao_aceita_os_dois_generos() -> None:
    """A condição em português não prende o gênero: `vem ligado` e `vem ligada` valem."""
    ligar, desligar = CONDICAO["pt"][True], CONDICAO["pt"][False]
    for genero in ("o", "a"):
        assert re.search(desligar, f"vem desligad{genero}")
        assert re.search(ligar, f"vem ligad{genero}")
        assert not re.search(ligar, f"vem desligad{genero}")
        assert not re.search(desligar, f"vem ligad{genero}")


def _ligado_por_padrao(pedido: str) -> bool:
    """O padrão de verdade do pedido, em `PADROES` do banco."""
    return bool(cadastros.PADROES[CHAVE_DO_PADRAO[pedido]])


def _condicoes(lingua: str) -> dict[str, tuple[str, ...]]:
    """Para cada pedido, o que a frase precisa trazer: o que cita e a condição do padrão real."""
    fontes = json.loads((RAIZ / "src/jobot/nucleo/dados/fontes.json").read_text(encoding="utf-8"))
    desligadas = sorted(c for c, d in fontes.items() if d.get("ligada_padrao", True) is False)
    assert not desligadas, f"o texto diz que todas vêm ligadas; o fontes.json desliga {desligadas}"
    tarefas = cadastros.PADROES["ia_tarefas"]
    assert isinstance(tarefas, dict) and tarefas, "sem tarefa de IA no padrão"  # controle
    ligadas = sorted(t for t, c in tarefas.items() if c["ligada"])
    assert not ligadas, f"o texto diz que as tarefas de IA vêm desligadas; {ligadas} vem ligada"
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


TAMANHO_DO_CHROMIUM = {
    "pt": "| Navegador controlado pelo Playwright",
    "en": "| Browser controlled by Playwright",
}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_readme_diz_o_tamanho_do_chromium(lingua: str) -> None:
    """A tabela de tamanhos diz quanto o Chromium baixa (T240; D137.8), no lugar de "A definir"."""
    linhas = [
        linha
        for linha in texto(README[lingua]).splitlines()
        if linha.startswith(TAMANHO_DO_CHROMIUM[lingua])
    ]
    assert len(linhas) == 1
    assert "210 MB" in linhas[0]


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_nao_cita_duvida_por_numero(lingua: str) -> None:
    """Quem usa o joBot não conhece o `duvidas.md`: o item diz o efeito, não o número (D1, D3)."""
    achados = re.findall(r"\bD\d+\b", sem_blocos(texto(CHANGELOG[lingua])))
    assert achados == []


NAO_LANCADO = {"pt": "## [Não lançado]", "en": "## [Unreleased]"}
ADICIONADO = {"pt": "### Adicionado", "en": "### Added"}
# termos que só o item do LinkedIn e do login pela janela comum têm
CITA_LOGIN_JANELA = {
    "pt": ("LinkedIn", "janela comum", "nunca digita"),
    "en": ("LinkedIn", "regular browser window", "never types"),
}
V0_2_0 = "## [0.2.0] - 2026-11-15"
# o que a 0.2.0 diz dos filtros, do país e da moeda
CITA_0_2_0 = {
    "pt": ("Meu país", "moeda dos valores convertidos"),
    "en": ("My country", "currency of converted values"),
}


V0_2_1 = "## [0.2.1] - 2026-11-15"
# termos que só os três itens da 0.2.1 têm: os chips, o índice 0006 e o "Salvo." em 5 s
CITA_0_2_1 = {"pt": ("chips", "0006", "5 segundos"), "en": ("chips", "0006", "5 seconds")}


# o resumo da 0.3.0 cobre tudo o que estava em "Não lançado", não só o último lote
V0_3_0 = "## [0.3.0] - 2026-11-16"
RESUMO_0_3_0 = {"pt": ("Panorama", "LinkedIn"), "en": ("Overview", "LinkedIn")}
# a 0.4.0 fecha a fase 3: o resumo cita a janela e o instalador
V0_4_0 = "## [0.4.0] - 2026-11-17"
RESUMO_0_4_0 = {"pt": ("fase 3", "janela", "instalador"), "en": ("Phase 3", "window", "installer")}


# a 0.4.1 corrige o Linux; no topo, o aviso a quem tem a janela 0.4.0 (D214.3)
V0_4_1 = "## [0.4.1] - 2026-11-24"
RESUMO_0_4_1 = {"pt": ("Linux", "controle", "navegador"), "en": ("Linux", "control", "browser")}
AVISO_0_4_1 = {
    "pt": "**Quem tem a janela 0.4.0:** instale a janela 0.4.1 antes de usar o Atualizar agora",
    "en": "**If you have the 0.4.0 window:** install the 0.4.1 window before using Update now",
}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_fecha_a_0_4_1(lingua: str) -> None:
    """A 0.4.1 vem logo depois da 0.5.0 e abre com o aviso a quem tem a janela 0.4.0, antes do
    resumo."""
    conteudo = texto(CHANGELOG[lingua])
    inicio = conteudo.index(V0_5_0)
    fim = conteudo.index("\n## [", inicio + 1)
    assert conteudo[fim + 1 :].startswith(V0_4_1), CHANGELOG[lingua]
    secao = conteudo[fim + 1 :]
    resumo = secao[: secao.index("###")]
    assert resumo.split("\n\n")[1].startswith(AVISO_0_4_1[lingua]), CHANGELOG[lingua]
    for termo in RESUMO_0_4_1[lingua]:
        assert termo in resumo, (CHANGELOG[lingua], termo)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_fecha_a_0_4_0(lingua: str) -> None:
    """A 0.4.0 vem logo depois da 0.4.1, e o resumo dela cobre a fase 3."""
    conteudo = texto(CHANGELOG[lingua])
    inicio = conteudo.index(V0_4_1)
    fim = conteudo.index("\n## [", inicio + 1)
    assert conteudo[fim + 1 :].startswith(V0_4_0), CHANGELOG[lingua]
    secao = conteudo[fim + 1 :]
    resumo = secao[: secao.index("###")]
    for termo in RESUMO_0_4_0[lingua]:
        assert termo in resumo, (CHANGELOG[lingua], termo)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_mantem_o_resumo_da_0_3_0(lingua: str) -> None:
    """A 0.3.0 vem logo depois da 0.4.0, e a linha de resumo dela cobre o lote inteiro."""
    conteudo = texto(CHANGELOG[lingua])
    inicio = conteudo.index(V0_4_0)
    fim = conteudo.index("\n## [", inicio + 1)
    assert conteudo[fim + 1 :].startswith(V0_3_0), CHANGELOG[lingua]
    # só o resumo: os itens movidos já trazem "LinkedIn" e deixariam passar um resumo do último lote
    secao = conteudo[fim + 1 :]
    resumo = secao[: secao.index("###")]
    for termo in RESUMO_0_3_0[lingua]:
        assert termo in resumo, (CHANGELOG[lingua], termo)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_traz_os_tres_itens_da_0_2_1(lingua: str) -> None:
    """A seção da 0.2.1 diz o que mudou: os chips, o índice da fonte e o aviso."""
    conteudo = texto(CHANGELOG[lingua])
    assert V0_2_1 in conteudo, CHANGELOG[lingua]
    inicio = conteudo.index(V0_2_1)
    secao_0_2_1 = conteudo[inicio : conteudo.index("\n## [", inicio + 1)]
    for termo in CITA_0_2_1[lingua]:
        assert termo in secao_0_2_1, (CHANGELOG[lingua], termo)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_traz_os_filtros_da_0_2_0(lingua: str) -> None:
    """A seção da 0.2.0 cita o país e a moeda; o resto do arquivo não vale."""
    conteudo = texto(CHANGELOG[lingua])
    assert V0_2_0 in conteudo, CHANGELOG[lingua]
    inicio = conteudo.index(V0_2_0)
    fim = conteudo.index("\n## [", inicio + 1)
    secao_0_2_0 = conteudo[inicio:fim]
    for termo in CITA_0_2_0[lingua]:
        assert termo in secao_0_2_0, (CHANGELOG[lingua], termo)
    assert re.findall(r"\bD\d+\b", secao_0_2_0) == []


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_cita_o_login_pela_janela_comum(lingua: str) -> None:
    """Na 0.3.0, "Adicionado" diz do LinkedIn e do login pela janela comum."""
    conteudo = texto(CHANGELOG[lingua])
    assert V0_3_0 in conteudo, CHANGELOG[lingua]
    inicio = conteudo.index(V0_3_0)
    secao_nova = conteudo[inicio : conteudo.index("\n## [", inicio + 1)]
    assert ADICIONADO[lingua] in secao_nova, CHANGELOG[lingua]
    adicionado = secao_nova[secao_nova.index(ADICIONADO[lingua]) :]
    for termo in CITA_LOGIN_JANELA[lingua]:
        assert termo in adicionado, (CHANGELOG[lingua], termo)


FAQ = {"pt": "wiki/Perguntas-frequentes.md", "en": "wiki/Frequently-asked-questions.md"}
# o que a pergunta sobre a vaga "fechada" no LinkedIn diz: só o texto novo tem estes termos
FAQ_FECHADA = {
    "pt": ("não vista há 30 dias", "última semana", "reabre"),
    "en": ("not seen for 30 days", "last week", "reopens"),
}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_faq_diz_o_que_fechada_quer_dizer_no_linkedin(lingua: str) -> None:
    """Na wiki, a resposta do LinkedIn (relevância, última semana, 30 dias, reabre) é uma só."""
    conteudo = texto(FAQ[lingua])
    marcador = FAQ_FECHADA[lingua][0]
    assert marcador in conteudo, FAQ[lingua]
    resposta = conteudo[: conteudo.index("</details>", conteudo.index(marcador))]
    resposta = resposta[resposta.rindex("<details>") :]
    assert "LinkedIn" in resposta, FAQ[lingua]
    for termo in FAQ_FECHADA[lingua]:
        assert termo in resposta, (FAQ[lingua], termo)


# a cotação que o pedido ao Banco Central traz, e o que sai dos textos de rede
COTACAO_TRAZ = {
    "pt": ("cotação das moedas das vagas", "moeda de exibição"),
    "en": ("exchange rates of the currencies", "display currency"),
}
COTACAO_VELHO = {"pt": "do dólar", "en": "dollar rate"}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_rede_fala_da_cotacao_das_moedas(lingua: str) -> None:
    """README e painel falam da cotação das moedas das vagas e da moeda de exibição."""
    privacidade = secao(texto(README[lingua]), SECAO_PRIVACIDADE[lingua])
    bullet = next(linha for linha in privacidade.splitlines() if "Common Crawl" in linha)
    fontes = {
        README[lingua]: bullet,
        f"i18n/{lingua}": i18n.carregar()[lingua]["configuracoes.privacidade.telemetria"],
    }
    for nome, conteudo in fontes.items():
        assert COTACAO_VELHO[lingua] not in conteudo, nome
        for termo in COTACAO_TRAZ[lingua]:
            assert termo in conteudo, (nome, termo)


# o que cada documento diz da fase 1 (T132): concluída, e não mais "em andamento"
FASE_1_CONCLUIDA = {
    ".github/CONTRIBUTING.md": (
        r"fases 1, 2 e 3 \(base, navegador com login e instalador\) estão concluídas"
    ),
    ".github/CONTRIBUTING.en.md": (
        r"Phases 1, 2 and 3 \(foundation, browser with login and installer\) are complete"
    ),
    ".github/SECURITY.md": r"(?i)só a versão mais recente \(hoje a 0\.5\.0\)",
    ".github/SECURITY.en.md": r"(?i)only the latest version \(currently 0\.5\.0\)",
    ".github/SUPPORT.md": r"formulário de bug",
    ".github/SUPPORT.en.md": r"bug form",
    "docs/decisions/0017-fases.md": r"fases 1, 2 e 3 estão concluídas",
    "docs/decisions/README.md": r"fases 1, 2 e 3 estão concluídas",
    "wiki/Home.md": (
        r"fases 1, 2 e 3 de 9 \(a base, o navegador com login e o instalador\) estão concluídas"
    ),
    "wiki/Home-en.md": (
        r"Phases 1, 2 and 3 of 9 \(the base, the browser with login and the installer\)"
        r" are complete"
    ),
    "wiki/A-ideia-e-a-historia.md": (
        r"fases 1, 2 e 3 de 9 \(a base, o navegador com login e o instalador\) estão concluídas"
    ),
    "wiki/The-idea-and-the-story.md": (
        r"Phases 1, 2 and 3 of 9 \(the base, the browser with login and the installer\)"
        r" are complete"
    ),
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


# a aba de Configurações com o estado de cada login: nome de hoje e nome velho, por língua
ABA_CONTAS = {"pt": "Configurações, Contas", "en": "Settings, Accounts"}
ABA_VELHA = {"pt": r"Configurações\W+Sites com login", "en": r"Settings\W+Sites with login"}
CITA_CONTAS = {"pt": "Cartão do Gmail na aba Contas", "en": "Gmail card in the Accounts tab"}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_cita_a_aba_contas(lingua: str) -> None:
    """Na 0.3.0 a aba é "Contas" e traz o cartão do Gmail; o nome velho não aparece."""
    conteudo = texto(CHANGELOG[lingua])
    assert V0_3_0 in conteudo, CHANGELOG[lingua]
    inicio = conteudo.index(V0_3_0)
    secao_nova = conteudo[inicio : conteudo.index("\n## [", inicio + 1)]
    assert ABA_CONTAS[lingua] in secao_nova, CHANGELOG[lingua]
    assert CITA_CONTAS[lingua] in secao_nova, CHANGELOG[lingua]
    assert not re.search(ABA_VELHA[lingua], conteudo), CHANGELOG[lingua]


# o Panorama e a fila de candidaturas em "Não lançado": o nome da tela e a pergunta, por língua
CITA_PANORAMA = {"pt": ("Panorama", "Você se candidatou?"), "en": ("Overview", "Did you apply")}
# a linha de privacidade sobre a abertura da candidatura, por língua
CITA_ABERTURA = {"pt": "quando você abriu a candidatura", "en": "when you opened the application"}
PRIVACIDADE = {"pt": "## 🔒 Privacidade e segurança", "en": "## 🔒 Privacy and security"}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_cita_o_panorama(lingua: str) -> None:
    """Na 0.3.0 o CHANGELOG traz o Panorama e a pergunta da fila de candidaturas."""
    conteudo = texto(CHANGELOG[lingua])
    assert V0_3_0 in conteudo, CHANGELOG[lingua]
    inicio = conteudo.index(V0_3_0)
    secao_nova = conteudo[inicio : conteudo.index("\n## [", inicio + 1)]
    for marcador in CITA_PANORAMA[lingua]:
        assert marcador in secao_nova, (CHANGELOG[lingua], marcador)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_privacidade_cita_a_abertura(lingua: str) -> None:
    """Na seção de privacidade do README: o registro local de quando a candidatura foi aberta."""
    conteudo = texto(README[lingua])
    assert PRIVACIDADE[lingua] in conteudo, README[lingua]
    inicio = conteudo.index(PRIVACIDADE[lingua])
    fim = conteudo.find("\n## ", inicio + 1)
    secao = conteudo[inicio : fim if fim != -1 else len(conteudo)]
    assert CITA_ABERTURA[lingua] in secao, README[lingua]


# o que cada documento de estado vivo diz da fase 3 (T342): concluída na 0.4.0
FASE_3_CONCLUIDA = {
    "docs/decisions/0017-fases.md": r"Fase 3, Instalador:.*concluída na 0\.4\.0",
    "docs/decisions/README.md": r"fases 1, 2 e 3 estão concluídas \(versão 0\.4\.0\)",
    "wiki/Roteiro.md": r"✅ \| \*\*3\. Instalador\*\*.*Concluída na 0\.4\.0",
    "wiki/Roadmap.md": r"✅ \| \*\*3\. Installer\*\*.*Complete in 0\.4\.0",
    "README.md": r"\*\*3\. Instalador\*\*.*🟢 Pronta \(versão 0\.4\.0\)",
    "README.en.md": r"\*\*3\. Installer\*\*.*🟢 Done \(version 0\.4\.0\)",
    ".github/CONTRIBUTING.md": (
        r"fases 1, 2 e 3 .*estão concluídas: o joBot 0\.4\.0.*a versão 0\.5\.0 já dá para instalar"
    ),
    ".github/CONTRIBUTING.en.md": (
        r"Phases 1, 2 and 3 .*are complete: joBot 0\.4\.0.*version 0\.5\.0 can already be installed"
    ),
}
# sobra do tempo em que a fase 3 estava em obras
FASE_3_EM_OBRAS = re.compile(
    r"fase 3[^.\n]*sendo construída|phase 3[^.\n]*being built|🟡 Fase 3|🟡 Phase 3"
    r"|instalador ainda vai chegar|installer is not here yet",
    re.IGNORECASE,
)


@pytest.mark.parametrize("caminho", sorted(FASE_3_CONCLUIDA))
def test_status_da_fase_3_igual_nos_documentos(caminho: str) -> None:
    """A fase 3 consta como concluída na 0.4.0 em todo documento de estado vivo (T342)."""
    conteudo = texto(caminho)
    assert re.search(FASE_3_CONCLUIDA[caminho], conteudo), caminho
    assert FASE_3_EM_OBRAS.search(conteudo) is None, caminho


# o que cada documento de estado vivo diz da fase 4 (T400, D185.26): sendo construída; desde a
# T421, com a 0.5.0 como a primeira parte e rumo à 0.6.0
PARTE_PT = r"a 0\.5\.0 trouxe a primeira parte; rumo à 0\.6\.0"
PARTE_EN = r"0\.5\.0 brought the first part; toward 0\.6\.0"
FASE_4_EM_OBRAS = {
    "docs/decisions/0017-fases.md": (
        r"Fase 4, IA local:.*Status: sendo construída; a 0\.5\.0 trouxe a primeira parte, rumo à"
        r" 0\.6\.0"
    ),
    "docs/decisions/README.md": rf"a fase 4 está sendo construída \({PARTE_PT}\)",
    "wiki/Roteiro.md": rf"🟡 \| \*\*4\. IA local\*\*.*\| Sendo construída \({PARTE_PT}\) \|",
    "wiki/Roadmap.md": rf"🟡 \| \*\*4\. Local AI\*\*.*\| Being built \({PARTE_EN}\) \|",
    "README.md": rf"\*\*4\. IA local\*\*.*\| 🟡 Sendo construída \({PARTE_PT}\) \|",
    "README.en.md": rf"\*\*4\. Local AI\*\*.*\| 🟡 Being built \({PARTE_EN}\) \|",
    ".github/CONTRIBUTING.md": (
        r"A fase 4 \(IA local\) está sendo construída: a 0\.5\.0 trouxe a primeira parte"
    ),
    ".github/CONTRIBUTING.en.md": (
        r"Phase 4 \(local AI\) is being built: 0\.5\.0 brought the first part"
    ),
    "wiki/Home.md": (
        r"A fase 4 \(IA local\) está sendo construída: a 0\.5\.0 trouxe a primeira parte"
    ),
    "wiki/Home-en.md": r"Phase 4 \(local AI\) is being built: 0\.5\.0 brought the first part",
}
# sobra do tempo em que a fase 4 estava só planejada
FASE_4_PLANEJADA = re.compile(
    r"4\. IA local\*\*[^\n]*Planejada|4\. Local AI\*\*[^\n]*Planned"
    r"|Fase 4, IA local:[^\n]*planejada|⚪ Fase 4|⚪ Phase 4"
    r"|fases 4 a 9 estão planejadas|Phases 4 to 9 are planned",
    re.IGNORECASE,
)


@pytest.mark.parametrize("caminho", sorted(FASE_4_EM_OBRAS))
def test_status_da_fase_4_igual_nos_documentos(caminho: str) -> None:
    """A fase 4 consta como sendo construída em todo documento de estado vivo, e nenhum deles
    ainda a chama de planejada (T400)."""
    conteudo = texto(caminho)
    assert re.search(FASE_4_EM_OBRAS[caminho], conteudo), caminho
    assert FASE_4_PLANEJADA.search(conteudo) is None, caminho


def test_fase_4_planejada_pega_as_frases_antigas() -> None:
    """Controle positivo: o regex reconhece cada frase de "planejada" que a T400 trocou."""
    antigas = (
        "| ⚪ | **4. IA local** | Pacote offline (llama-server + Qwen) | Planejada |",
        "| ⚪ | **4. Local AI** | Offline package (llama-server + Qwen) | Planned |",
        "- Fase 4, IA local: pacote offline (llama-server + Qwen). Status: planejada.",
        'F3 --> F4["⚪ Fase 4 · IA local"]',
        "<summary><strong>⚪ Phase 4, Local AI</strong></summary>",
        "As fases 4 a 9 estão planejadas.",
        "Phases 4 to 9 are planned.",
    )
    assert [a for a in antigas if FASE_4_PLANEJADA.search(a) is None] == []


# o ajuste do Laya antes da fase 4 (D141): adiado em 2026-11-17 (D185.8), autorizado pelo dono em
# 2026-11-24 (D219)
LAYA_AUTORIZADO = ("docs/decisions/0015-treino.md", "docs/decisions/0017-fases.md")


@pytest.mark.parametrize("caminho", LAYA_AUTORIZADO)
def test_laya_antes_da_fase_4_diz_autorizado(caminho: str) -> None:
    linhas = [
        linha
        for linha in texto(caminho).splitlines()
        if linha.startswith("- ")
        and not linha.startswith(("- [", "- **"))
        and "Laya" in linha
        and "antes da fase 4" in linha
    ]
    assert linhas, caminho  # controle: achou a linha do Laya
    assert [linha for linha in linhas if "autorizou o treino" not in linha] == [], caminho
    assert [linha for linha in linhas if "2026-11-24 (D219" not in linha] == [], caminho


def test_indice_das_adrs_lista_todas() -> None:
    numeros = sorted(
        p.name[:4] for p in (RAIZ / "docs/decisions").glob("[0-9][0-9][0-9][0-9]-*.md")
    )
    assert "0026" in numeros  # controle: a ADR da fase 4 existe
    conteudo = texto("docs/decisions/README.md")
    assert [n for n in numeros if f"| {n} | [" not in conteudo] == []


def test_adr_0026_marca_para_confirmar_cada_escolha() -> None:
    """Toda frase da decisão vem da D185, que o dono ainda não confirmou (padrões «Dúvidas»)."""
    conteudo = texto("docs/decisions/0026-ia-da-fase-4.md")
    assert "## Decisão" in conteudo
    decisao = conteudo[conteudo.index("## Decisão") : conteudo.index("## Consequências")]
    itens = [linha for linha in decisao.splitlines() if linha.startswith("- ")]
    assert len(itens) >= 5  # controle: achou os itens
    assert [i for i in itens if "para confirmar" not in i] == []


# T341: a instalação pelo instalador da fase 3, por língua; cada termo só o texto novo tem
INSTALADOR_CITA = {
    "pt": (
        "-setup.exe",
        "_aarch64.dmg",
        "_x64.dmg",
        ".AppImage",
        ".deb",
        ".rpm",
        "100 a 200 MB",
        "Mais informações",
        "Executar assim mesmo",
        "Abrir Mesmo Assim",
        "nada mais é baixado na instalação além do navegador e do Modelo local",
        "https://developer.microsoft.com/microsoft-edge/webview2/",
        "%LOCALAPPDATA%\\joBot",
        "~/Library/Application Support/joBot",
        "~/.local/share/jobot-app",
        "Desinstalar",
        "Configurações › Ferramentas",
        "https://github.com/fezarosa-dev/joBot/wiki/Instalar",
    ),
    "en": (
        "-setup.exe",
        "_aarch64.dmg",
        "_x64.dmg",
        ".AppImage",
        ".deb",
        ".rpm",
        "100 to 200 MB",
        "More info",
        "Run anyway",
        "Open Anyway",
        "nothing else is downloaded during the installation besides the browser",
        "https://developer.microsoft.com/microsoft-edge/webview2/",
        "%LOCALAPPDATA%\\joBot",
        "~/Library/Application Support/joBot",
        "~/.local/share/jobot-app",
        "Uninstall",
        "Settings › Tools",
        "https://github.com/fezarosa-dev/joBot/wiki/Install",
    ),
}
# o subtítulo de atualizar e o botão do painel que substitui o terminal (D176.9)
ATUALIZAR = {"pt": ("### Atualizar", "Atualizar agora"), "en": ("### Updating", "Update now")}
# a linha que ainda manda rodar `jobot atualizar` tem de dizer que é para quem instalou pelo código
PELO_CODIGO = {"pt": "pelo código", "en": "from the code"}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_readme_instala_pelo_instalador(lingua: str) -> None:
    """O que baixar por sistema, tamanho, avisos sem selo, dados, desinstalar e sem rede (T341)."""
    instalacao = secao(texto(README[lingua]), SECAO_INSTALACAO[lingua])
    faltam = [termo for termo in INSTALADOR_CITA[lingua] if termo not in instalacao]
    assert faltam == [], (README[lingua], faltam)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_readme_atualiza_pelo_painel_quem_usa_o_instalador(lingua: str) -> None:
    """Quem usa o instalador atualiza pelo botão; o terminal fica para quem instalou pelo código."""
    instalacao = secao(texto(README[lingua]), SECAO_INSTALACAO[lingua])
    titulo, botao = ATUALIZAR[lingua]
    assert titulo in instalacao, README[lingua]
    inicio = instalacao.index(titulo)
    atualizar = instalacao[inicio : instalacao.find("\n### ", inicio + 1)]
    assert botao in atualizar, README[lingua]
    com_terminal = [linha for linha in atualizar.splitlines() if "jobot atualizar" in linha]
    assert com_terminal, README[lingua]  # controle: quem instalou pelo código ainda acha o comando
    for linha in com_terminal:
        assert PELO_CODIGO[lingua] in linha.lower(), (README[lingua], linha)


# o que a fase 3 entrega, na 0.4.0; e a frase velha do `uv` embutido, que a D174 superou
FASE_3_NO_CHANGELOG = {
    "pt": ("instalador", "Windows", "Atualizar agora", "Encerrar o joBot", "sem internet"),
    "en": ("installer", "Windows", "Update now", "Quit joBot", "without internet"),
}
UV_EMBUTIDO = {"pt": "com o `uv` embutido", "en": "with `uv` bundled"}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_traz_a_fase_3_na_0_4_0(lingua: str) -> None:
    conteudo = texto(CHANGELOG[lingua])
    assert V0_4_0 in conteudo, CHANGELOG[lingua]
    inicio = conteudo.index(V0_4_0)
    secao_0_4_0 = conteudo[inicio : conteudo.index("\n## [", inicio + 1)]
    faltam = [termo for termo in FASE_3_NO_CHANGELOG[lingua] if termo not in secao_0_4_0]
    assert faltam == [], (CHANGELOG[lingua], faltam)
    assert UV_EMBUTIDO[lingua] not in conteudo, CHANGELOG[lingua]


DECISOES_DA_WIKI = {"pt": "wiki/Decisoes.md", "en": "wiki/Decisions.md"}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_wiki_de_decisoes_sem_o_uv_embutido(lingua: str) -> None:
    """O resumo da ADR 0025 na wiki fala do instalador completo, não do `uv` embutido (D174)."""
    conteudo = texto(DECISOES_DA_WIKI[lingua])
    assert UV_EMBUTIDO[lingua] not in conteudo, DECISOES_DA_WIKI[lingua]


CONTRIBUTING = {"pt": ".github/CONTRIBUTING.md", "en": ".github/CONTRIBUTING.en.md"}
# como compilar a casca: a toolchain fixada, o modo de desenvolvimento e os recursos do instalador
COMPILAR_A_CASCA = (
    "desktop/rust-toolchain.toml",
    "cargo install tauri-cli --version =2.12.4 --locked",
    "cargo tauri dev",
    "desktop/recursos/",
    "scripts/montar_recursos.py",
    "JOBOT_MANIFESTO_SHA256",
)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_contributing_ensina_a_compilar_a_casca(lingua: str) -> None:
    citados = trechos(texto(CONTRIBUTING[lingua]))
    faltam = [t for t in COMPILAR_A_CASCA if not any(t in trecho for trecho in citados)]
    assert faltam == [], (CONTRIBUTING[lingua], faltam)


def test_contributing_usa_o_tauri_cli_do_workflow() -> None:
    """A versão do `tauri-cli` citada no guia é a que o build da release instala."""
    workflow = texto(".github/workflows/pacotes.yml")
    assert "cargo install tauri-cli --version =2.12.4 --locked" in workflow


@pytest.mark.parametrize("lingua", LINGUAS)
def test_readme_lista_todas_as_adrs(lingua: str) -> None:
    numeros = sorted(
        p.name[:4] for p in (RAIZ / "docs/decisions").glob("[0-9][0-9][0-9][0-9]-*.md")
    )
    assert numeros  # controle: achou as ADRs
    conteudo = texto(README[lingua])
    faltam = [n for n in numeros if f"| {n} | [" not in conteudo]
    assert faltam == [], (README[lingua], faltam)


# T420: o que os documentos da 0.5.0 dizem da IA; cada termo só o texto novo tem
SECAO_IA = {"pt": "inteligencia-artificial", "en": "artificial-intelligence"}
IA_0_5_0 = {
    "pt": ("O que a 0.5.0 traz", "O que funciona sem internet", "Hugging Face", "provado no CI"),
    "en": ("What 0.5.0 brings", "What works without internet", "Hugging Face", "proven in CI"),
}
SOBRA_DO_MODELO = {
    "pt": ("pasta `ferramentas`", "2,7 GB"),
    "en": ("`ferramentas` folder", "2.7 GB"),
}
V0_5_0 = "## [0.5.0] - 2026-11-24"
NA_0_5_0 = {
    "pt": ("Configurações › IA", "Hugging Face", "Laya"),
    "en": ("Settings › AI", "Hugging Face", "Laya"),
}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_readme_traz_a_ia_da_0_5_0(lingua: str) -> None:
    """A seção de IA diz o que a 0.5.0 traz, a tabela do que funciona sem internet, a marca dos
    serviços pagos não provados (a mesma frase da aba IA) e o que só o CI provou; o pacote offline
    perdeu o áudio (D185.10 e D185.27)."""
    ia = secao(texto(README[lingua]), SECAO_IA[lingua])
    assert "Qwen3.5-4B" in ia, README[lingua]  # controle: a tabela do pacote offline está aqui
    for termo in IA_0_5_0[lingua]:
        assert termo in ia, (README[lingua], termo)
    marca = i18n.carregar()[lingua]["configuracoes.ia.experimental"].split(":")[0]
    assert f"**{marca}:**" in ia, README[lingua]
    assert "whisper" not in ia.lower(), README[lingua]


@pytest.mark.parametrize("lingua", LINGUAS)
def test_desinstalar_diz_a_sobra_do_modelo_local(lingua: str) -> None:
    """Desinstalar deixa o modelo local na pasta de dados: o README diz onde e quanto (D185.18)."""
    instalacao = secao(texto(README[lingua]), SECAO_INSTALACAO[lingua])
    for termo in SOBRA_DO_MODELO[lingua]:
        assert termo in instalacao, (README[lingua], termo)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_fecha_a_0_5_0(lingua: str) -> None:
    """A 0.5.0 é a primeira seção de versão, logo depois de "Não lançado", com a data do dia da
    tag (T421, padrões «Troca de versão»), e traz a IA."""
    conteudo = texto(CHANGELOG[lingua])
    assert NAO_LANCADO[lingua] in conteudo, CHANGELOG[lingua]
    inicio = conteudo.index(NAO_LANCADO[lingua])
    fim = conteudo.index("\n## [", inicio + 1)
    assert conteudo[fim + 1 :].startswith(V0_5_0), CHANGELOG[lingua]
    nova = conteudo[fim + 1 : conteudo.index("\n## [", fim + 1)]
    for termo in NA_0_5_0[lingua]:
        assert termo in nova, (CHANGELOG[lingua], termo)


# o Laya é o padrão em todo computador e a memória só decide o aviso (D219.20)
LAYA_NO_README = {
    "pt": ("Laya-2B", "`--modelo laya`", "`2b`", "`4b`", "versões do joBot no GitHub"),
    "en": ("Laya-2B", "`--modelo laya`", "`2b`", "`4b`", "joBot's releases on GitHub"),
}
ESCOLHA_PELA_MEMORIA = {
    "pt": ("escolhe o modelo pela memória", "escolhe pela memória", "conforme a memória"),
    "en": ("picks the model by the computer", "picks by the computer", "depending on the computer"),
}
# as quatro fontes que entraram no treino do Laya (D219.14); nenhuma foi "liberada" pelos termos
FONTES_DO_LAYA = ("Greenhouse", "Lever", "We Work Remotely", "Jobicy")
LIBERADA = {"pt": "liberad", "en": "cleared"}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_readme_diz_o_laya_como_modelo_padrao(lingua: str) -> None:
    """O pacote offline, o passo do instalador e o comando dizem o Laya como padrão e as três
    opções; a escolha pela memória da 0.5.0 não sobra (D219.20)."""
    conteudo = texto(README[lingua])
    for termo in LAYA_NO_README[lingua]:
        assert termo in conteudo, (README[lingua], termo)
    for termo in ESCOLHA_PELA_MEMORIA[lingua]:
        assert termo not in conteudo, (README[lingua], termo)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_diz_de_onde_vem_o_treino_do_laya(lingua: str) -> None:
    """O "Não lançado" diz as quatro fontes do treino e não chama nenhuma de liberada: os termos
    delas não falam de treino de modelo (D219.14)."""
    conteudo = texto(CHANGELOG[lingua])
    inicio = conteudo.index(NAO_LANCADO[lingua])
    nao_lancado = conteudo[inicio : conteudo.index("\n## [", inicio + 1)]
    laya = next(x for x in nao_lancado.splitlines() if "Laya 2B" in x)
    for fonte in FONTES_DO_LAYA:
        assert fonte in laya, (CHANGELOG[lingua], fonte)
    assert LIBERADA[lingua] not in laya.lower(), CHANGELOG[lingua]


LAYA_AUTORIZADO_NA_IA = (
    "docs/decisions/0014-seguranca-e-privacidade.md",
    "docs/decisions/0026-ia-da-fase-4.md",
)
# o que essas ADRs diziam do Laya antes da autorização (D185.8); fora do riscado, não pode sobrar
LAYA_ESPERANDO = re.compile(r"primeira pergunta ao dono|só roda se o dono autorizar")


@pytest.mark.parametrize("caminho", LAYA_AUTORIZADO_NA_IA)
def test_adr_da_ia_diz_o_laya_autorizado(caminho: str) -> None:
    """D219.12: a 0014 e a 0026 riscam o Laya à espera do dono e citam a autorização (D219)."""
    linhas = [linha for linha in texto(caminho).splitlines() if linha.startswith("- ")]
    vivas = [re.sub(r"~~.*?~~", "", linha) for linha in linhas if "Laya" in linha]
    assert vivas, caminho  # controle: achou as linhas do Laya
    assert any(LAYA_ESPERANDO.search(linha) for linha in linhas), caminho  # o riscado ficou
    assert [linha for linha in vivas if LAYA_ESPERANDO.search(linha)] == [], caminho
    assert any("D219" in linha for linha in vivas), caminho


TELA_DE_INSTALACAO = {
    "pt": ("README.md", "wiki/Instalar.md"),
    "en": ("README.en.md", "wiki/Install.md"),
}
SO_O_NAVEGADOR = re.compile(
    r"único que vem da internet|exceto o navegador, se marcado"
    r"|only thing that comes from the internet|except the browser, if ticked"
)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_tela_de_instalacao_cita_o_modelo_local(lingua: str) -> None:
    """O passo Ferramentas do instalador tem a caixa Modelo local (desenho 10.1, T418), que baixa
    do GitHub e do Hugging Face: o passo a passo não pode dizer que só o navegador vem da
    internet."""
    rotulo = json.loads(texto(f"desktop/ui/i18n/{lingua}.json"))["ferramentas.ia_local"]
    for arquivo in TELA_DE_INSTALACAO[lingua]:
        conteudo = texto(arquivo)
        assert f"**{rotulo}**" in conteudo, (arquivo, rotulo)
        assert "Hugging Face" in conteudo, arquivo
        assert not SO_O_NAVEGADOR.search(conteudo), arquivo


# T440: a 0.6.0 nos documentos. Os rótulos vêm do catálogo do painel (o documento copia a tela);
# os outros termos só o texto novo tem.
IA_0_6_0 = {"pt": ("O que a 0.6.0 traz", "IA manual"), "en": ("What 0.6.0 brings", "Manual AI")}
ROTULOS_0_6_0 = (
    "configuracoes.perfil.curriculo.aprovar",
    "configuracoes.perfil.sugeridas.titulo",
    "detalhe.candidatura.preparar",
    "detalhe.candidatura.aviso",
)
# o que a 0.5.0 dizia da 0.6.0 e do Laya no futuro; com a 0.6.0 construída, não pode sobrar
VELHO_0_6_0 = re.compile(
    r"chegam na 0\.6\.0|arrive in 0\.6\.0|vai ajudar a preparar|will help prepare"
    r"|Modelo local \(Qwen\)|Local model \(Qwen\)|versão seguinte|later version|next version"
)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_readme_traz_a_ia_da_0_6_0(lingua: str) -> None:
    """A seção de IA diz o que a 0.6.0 traz, com os rótulos da tela; o README não fala mais da
    0.6.0 e do Laya no futuro (desenho 14 da fase 4)."""
    conteudo = texto(README[lingua])
    ia = secao(conteudo, SECAO_IA[lingua])
    assert "Qwen3.5-4B" in ia, README[lingua]  # controle: achou a seção
    catalogo = i18n.carregar()[lingua]
    for termo in (*IA_0_6_0[lingua], *(catalogo[c] for c in ROTULOS_0_6_0)):
        assert termo in ia, (README[lingua], termo)
    assert VELHO_0_6_0.findall(conteudo) == [], README[lingua]


def test_velho_0_6_0_pega_as_frases_antigas() -> None:
    """Controle das regex: as frases que a 0.5.0 deixou no README e na wiki casam."""
    assert VELHO_0_6_0.search("ele entra numa versão seguinte, depois do treino")
    assert VELHO_0_6_0.search("| **Local model (Qwen)** | Free |")
    assert VELHO_NA_WIKI.search("| **IA manual** (copiar e colar), na 0.6.0 | Grátis |")
    assert SO_A_VAGA.search("vai só o texto da vaga, nunca o seu perfil")
    assert NUNCA_ENTRAM.search("e nome, e-mail, telefone e cidade nunca entram nos pedidos.")
    assert NUNCA_ENTRAM.search("Name, email, phone and city never go into the requests.")
    assert CPF_PREENCHIDO.search(
        "O e-mail, o telefone e o CPF são tirados do texto antes de ir à IA e preenchidos"
    )
    assert CPF_PREENCHIDO.search(
        "Email, phone and CPF are taken out of the text before it goes to the AI and filled in"
    )
    assert VELHO_NA_0014.search("- CPF e data de nascimento ficam no SQLite (banco)")
    assert VELHO_NA_0014.search("- Exportar o perfil não leva documentos pessoais (como o CPF)")
    assert VELHO_NA_0014.search("Nome, e-mail, telefone e cidade nunca vão; e-mail")


# cada tarefa diz o que manda (a lista permitida da T431 e as frases das abas IA e Perfil)
CADA_TAREFA = {
    "pt": ("sem nome, e-mail, telefone e cidade", "sem e-mail, telefone e CPF", "IA manual"),
    "en": ("without name, email, phone and city", "without email, phone and CPF", "manual AI"),
}
# o que a 0.5.0 dizia (só o texto da vaga sai) e o CPF guardado, que a 0.6.0 não guarda
SO_A_VAGA = re.compile(
    r"A IA só recebe o texto da vaga|The AI only gets the job text|nunca o seu perfil"
    r"|never your profile|CPF e data de nascimento ficam"
    r"|CPF \(Brazilian tax ID\) and date of birth stay"
)


@pytest.mark.parametrize("lingua", LINGUAS)
def test_privacidade_diz_o_que_cada_tarefa_manda(lingua: str) -> None:
    """Com a 0.6.0 o perfil e o texto do currículo saem para o serviço escolhido: a privacidade
    do README diz o que vai em cada tarefa, e nem ela nem o FAQ dizem que só a vaga sai."""
    privacidade = secao(texto(README[lingua]), SECAO_PRIVACIDADE[lingua])
    assert "Common Crawl" in privacidade, README[lingua]  # controle: achou a seção
    for termo in CADA_TAREFA[lingua]:
        assert termo in privacidade, (README[lingua], termo)
    for nome, conteudo in ((README[lingua], privacidade), (FAQ[lingua], texto(FAQ[lingua]))):
        assert SO_A_VAGA.findall(conteudo) == [], nome


NA_0_6_0 = {
    "pt": ("Configurações › Perfil", "IA manual", "pypdf"),
    "en": ("Settings › Profile", "Manual AI", "pypdf"),
}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_changelog_traz_a_0_6_0_em_nao_lancado(lingua: str) -> None:
    """O "Não lançado" traz o perfil completo, o currículo, a IA manual e Preparar candidatura,
    com o rótulo do botão (padrões «ADR e CHANGELOG»)."""
    conteudo = texto(CHANGELOG[lingua])
    assert NAO_LANCADO[lingua] in conteudo, CHANGELOG[lingua]
    inicio = conteudo.index(NAO_LANCADO[lingua])
    nao_lancado = conteudo[inicio : conteudo.index("\n## [", inicio + 1)]
    preparar = i18n.carregar()[lingua]["detalhe.candidatura.preparar"]
    for termo in (*NA_0_6_0[lingua], preparar):
        assert termo in nao_lancado, (CHANGELOG[lingua], termo)


# wiki: o que cada página precisa dizer da 0.6.0, e o que ela dizia no futuro
WIKI_0_6_0 = {
    "wiki/Tecnologias.md": (
        "Laya",
        "IA manual",
        "o nome e a cidade escritos nele vão junto",
        "das versões do llama.cpp",
    ),
    "wiki/Technologies.md": (
        "Laya",
        "Manual AI",
        "the name and city written in it go along",
        "from llama.cpp's releases",
    ),
    "wiki/Como-funciona.md": (
        "Preparar candidatura",
        "IA manual",
        "o nome e a cidade escritos nele vão junto",
    ),
    "wiki/How-it-works.md": (
        "Prepare Application",
        "manual AI",
        "the name and city written in it go along",
    ),
    "wiki/Perguntas-frequentes.md": ("sem nome, e-mail, telefone e cidade",),
    "wiki/Frequently-asked-questions.md": ("without name, email, phone and city",),
    "wiki/Roteiro.md": ("Laya",),
    "wiki/Roadmap.md": ("Laya",),
}
VELHO_NA_WIKI = re.compile(
    r"versão seguinte|later version|na 0\.6\.0 \||in 0\.6\.0 \||vai ajudar a preparar"
    r"|will help prepare|chega na 0\.6\.0|comes in 0\.6\.0|\(Qwen, grátis|\(Qwen, free"
)
# o absoluto que a tarefa curriculo não cumpre: o nome e a cidade escritos no PDF vão (D230.5)
NUNCA_ENTRAM = re.compile(r"nunca entram nos pedidos|never go into the requests")


@pytest.mark.parametrize("caminho", sorted(WIKI_0_6_0))
def test_wiki_traz_a_0_6_0(caminho: str) -> None:
    conteudo = texto(caminho)
    for termo in WIKI_0_6_0[caminho]:
        assert termo in conteudo, (caminho, termo)
    assert VELHO_NA_WIKI.findall(conteudo) == [], caminho
    assert NUNCA_ENTRAM.findall(conteudo) == [], caminho


# o CPF sai do texto do currículo, mas não é preenchido nem guardado (D185.13, D236.3)
CPF_PREENCHIDO = re.compile(
    r"CPF são tirados do texto antes de ir à IA e preenchidos"
    r"|CPF are taken out of the text before it goes to the AI and filled in"
)
CPF_NAO_GUARDADO = {"pt": "o CPF não é guardado", "en": "the CPF is not kept"}


@pytest.mark.parametrize("lingua", LINGUAS)
def test_cpf_do_curriculo_nao_e_preenchido(lingua: str) -> None:
    """O README e o CHANGELOG dizem que o e-mail e o telefone são preenchidos no computador e
    que o CPF, tirado do texto, não é guardado: o perfil não tem CPF."""
    for caminho in (README[lingua], CHANGELOG[lingua]):
        conteudo = texto(caminho)
        assert CPF_NAO_GUARDADO[lingua] in conteudo, caminho
        assert CPF_PREENCHIDO.findall(conteudo) == [], caminho


# ADR 0014: o que ela dizia do CPF guardado e o absoluto do contato, fora do riscado
VELHO_NA_0014 = re.compile(
    r"CPF e data de nascimento ficam no SQLite|não leva documentos pessoais \(como o CPF\)"
    r"|cidade nunca vão"
)


def test_adr_0014_sem_cpf_guardado_e_com_a_regra_por_tarefa() -> None:
    """D236.3: o perfil não guarda CPF nem data de nascimento, e o texto do currículo leva o
    nome e a cidade escritos nele; fora do riscado, a ADR 0014 não diz o contrário."""
    vivo = re.sub(r"~~.*?~~", "", texto("docs/decisions/0014-seguranca-e-privacidade.md"))
    assert "keyring" in vivo  # controle: achou a ADR
    assert VELHO_NA_0014.findall(vivo) == []
    assert "o nome e a cidade escritos nele vão junto" in vivo


LAYA_NA_0_6_0 = (
    "docs/decisions/0015-treino.md",
    "docs/decisions/0017-fases.md",
    "docs/decisions/0026-ia-da-fase-4.md",
)


@pytest.mark.parametrize("caminho", LAYA_NA_0_6_0)
def test_adr_diz_o_laya_padrao_na_0_6_0(caminho: str) -> None:
    """D219.20: o Laya é o modelo local padrão da 0.6.0; fora do riscado, nenhuma linha diz que
    ele entra numa versão seguinte."""
    linhas = [linha for linha in texto(caminho).splitlines() if linha.startswith("- ")]
    vivas = [re.sub(r"~~.*?~~", "", linha) for linha in linhas if "Laya" in linha]
    assert vivas, caminho  # controle: achou as linhas do Laya
    assert [linha for linha in vivas if "versão seguinte" in linha] == [], caminho
    assert any("0.6.0" in linha for linha in vivas), caminho
