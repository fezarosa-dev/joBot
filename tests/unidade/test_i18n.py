import json
import re
from pathlib import Path

import pytest

from jobot.banco.leitura import PASSOS
from jobot.banco.paginas import MOTIVOS as MOTIVOS_DA_PAGINA
from jobot.nucleo import encaixe
from jobot.nucleo.contas import MOTIVOS as MOTIVOS_DE_SESSAO
from jobot.nucleo.contas import NA_TELA
from jobot.nucleo.modelo import Area, Aviso, Contrato, Modalidade, Nivel
from jobot.painel import i18n

AREAS = [e.value for e in Area]
NIVEIS = [e.value for e in Nivel]
MODALIDADES = [e.value for e in Modalidade]
CONTRATOS = [e.value for e in Contrato]
AVISOS = [e.value for e in Aviso]
FONTES = (
    "github_issues remotive remoteok jobicy himalayas wwr hn_algolia greenhouse lever ashby "
    "smartrecruiters gupy inhire quickin recrutei solides abler ciee iel super_estagios "
    "cia_de_talentos eureca usp workday eightfold oracle_hcm google amazon linkedin_logado"
).split()
ENCAIXE = (
    "cargo_titulo cargo_descricao cargo_ausente local_remoto modalidade_fora modalidade_ok "
    "modalidade_nao_informada local_cidade local_uf local_fora nivel_nao_informado nivel_ok "
    "nivel_fora salario_nao_informado salario_ok salario_abaixo idioma_ok idioma_nao_detectado "
    "idioma_fora"
).split()
MOTIVOS = (
    "formato_mudou zero_inesperado parcial_n sem_detalhe_n empresa_nao_encontrada bloqueio cota "
    "intervalo orcamento parou_429 limite_atingido tempo_esgotado erro_de_rede resposta_grande "
    "excecao listagem_incompleta precisa_login captcha sem_tela sem_navegador"
).split()


def _chaves_fixas() -> list[str]:
    return [
        *[f"area.{v}" for v in AREAS],
        *[f"nivel.{v}" for v in NIVEIS],
        *[f"modalidade.{v}" for v in MODALIDADES],
        *[f"contrato.{v}" for v in CONTRATOS],
        *[f"aviso.{v}" for v in AVISOS],
        *[f"fonte.{v}" for v in FONTES],
        *[f"encaixe.{v}" for v in ENCAIXE],
        *[f"saude.{v}" for v in MOTIVOS],
        "seguranca.recarregue",
    ]


def test_mesmas_chaves_em_pt_e_en() -> None:
    catalogo = i18n.carregar()
    assert set(catalogo) == {"pt", "en"}
    assert set(catalogo["pt"]) == set(catalogo["en"])
    assert catalogo["pt"]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_grupo_aparencia_saiu(idioma: str) -> None:
    catalogo = i18n.carregar()[idioma]
    assert "configuracoes.grupo.aparencia" not in catalogo
    assert catalogo["configuracoes.grupo.geral"]  # o grupo que o substitui
    for opcao in ("padrao", "grande", "maior"):  # `t("...texto." ~ opcao)` percorre o conjunto
        assert catalogo[f"configuracoes.geral.texto.{opcao}"]
    assert catalogo["casca.tema"] == {"pt": "Tema", "en": "Appearance"}[idioma]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_botoes_velhos_do_assistente_sairam(idioma: str) -> None:
    """Continuar, Pular e Voltar passaram ao pé fixo (T263): as chaves de cada passo não voltam."""
    catalogo = i18n.carregar()[idioma]
    for resto in ("p1.continuar", "p1.pular", "sites.continuar", "sites.pular", "sites.voltar"):
        assert f"primeira_execucao.{resto}" not in catalogo
    assert "primeira_execucao.p2.concluir" not in catalogo
    assert catalogo["primeira_execucao.continuar"]  # controle: as do pé existem


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_preferencias_da_barra_saiu(idioma: str) -> None:
    """Tema, idioma e a busca da tela saíram (T251); as chaves de tema e idioma ficam para
    Configurações > Geral, e a busca da barra usa `casca.busca.*`."""
    catalogo = i18n.carregar()[idioma]
    for chave in ("casca.preferencias", "vagas.busca.rotulo", "vagas.busca.dica"):
        assert chave not in catalogo
    assert catalogo["casca.idioma"]


def test_chave_repetida_em_dois_arquivos_falha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pt").mkdir()
    (tmp_path / "pt" / "a.json").write_text(json.dumps({"x.y": "um"}), encoding="utf-8")
    (tmp_path / "pt" / "b.json").write_text(json.dumps({"x.y": "dois"}), encoding="utf-8")
    monkeypatch.setattr(i18n, "PASTA", tmp_path)
    with pytest.raises(ValueError, match="x.y"):
        i18n.carregar()


@pytest.mark.parametrize(
    ("cabecalho", "esperado"),
    [
        ("en-US,en;q=0.9", "en"),
        ("pt-BR,pt;q=0.9,en;q=0.8", "pt"),
        ("fr,en;q=0.5", "en"),
        ("en;q=0.2,pt;q=0.9", "pt"),
        (None, "pt"),
        ("", "pt"),
        ("fr", "pt"),
    ],
)
def test_idioma_inicial(cabecalho: str | None, esperado: str) -> None:
    assert i18n.idioma_inicial(cabecalho) == esperado


def test_parametros() -> None:
    assert "3" in i18n.t("pt", "saude.parcial_n", n=3)
    assert "3" in i18n.t("en", "saude.parcial_n", n=3)
    assert "KeyError" in i18n.t("pt", "saude.excecao", tipo="KeyError")


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_motivos_fixos_existem(idioma: str) -> None:
    catalogo = i18n.carregar().get(idioma, {})
    faltam = [c for c in _chaves_fixas() if not catalogo.get(c)]
    assert faltam == []


def test_textos_pt_e_en_diferem_nos_motivos() -> None:
    assert i18n.t("pt", "seguranca.recarregue") != i18n.t("en", "seguranca.recarregue")
    catalogo = i18n.carregar()  # direto, sem `t`: alguns textos pedem parâmetros ({n}, {tipo})
    for motivo in MOTIVOS:
        chave = f"saude.{motivo}"
        assert catalogo["pt"].get(chave) != catalogo["en"].get(chave), motivo


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_chaves_encaixe_existem_em_pt_e_en(idioma: str) -> None:
    """Toda chave `encaixe.*` que o núcleo grava num motivo tem texto no catálogo."""
    usadas = set(re.findall(r'chave="(encaixe\.\w+)"', Path(encaixe.__file__).read_text("utf-8")))
    esperadas = {f"encaixe.{v}" for v in ENCAIXE}
    assert usadas == esperadas, "a lista ENCAIXE saiu de dia com o núcleo"
    arquivo = i18n.PASTA / idioma / "vagas.json"
    textos: dict[str, str] = json.loads(arquivo.read_text("utf-8")) if arquivo.exists() else {}
    assert sorted(c for c in usadas if not textos.get(c)) == []


@pytest.mark.parametrize("lingua", ["pt", "en"])
def test_todo_motivo_tem_texto_nas_duas_linguas(lingua: str) -> None:
    """/sites e a aba Programas traduzem `sites.motivo.<código>`: código sem chave daria 500."""
    catalogo = i18n.carregar()[lingua]
    for codigo in (*sorted(MOTIVOS_DA_PAGINA), "desconhecido"):  # `desconhecido`: motivo nulo
        assert catalogo.get(f"sites.motivo.{codigo}", "").strip(), (lingua, codigo)
    # as frases que recebem o motivo: a de /sites e a da aba Programas (vagas/miolo.html)
    for chave in ("sites.estado.falhou", "vagas.programas.falhou"):
        assert "{motivo}" in catalogo[chave], (lingua, chave)
        assert i18n.t(lingua, chave, motivo="MOTIVO-X").count("MOTIVO-X") == 1


@pytest.mark.parametrize(
    ("cabecalho", "esperado"),
    [
        ("pt-BR,pt;q=0.9", "BR"),
        ("en-GB", "GB"),
        ("pt-br", "BR"),
        ("en-419", "BR"),
        ("*", "BR"),
        ("en", "BR"),
        (None, "BR"),
        ("fr-CA;q=0.5, de-DE;q=0.9", "DE"),
        ("en-ZZ, pt-PT;q=0.8", "PT"),
    ],
)
def test_pais_do_accept_language(cabecalho: str | None, esperado: str) -> None:
    assert i18n.pais_do_accept_language(cabecalho) == esperado


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_andamento_velho_saiu(idioma: str) -> None:
    """A linha da etapa (T252) substitui o ponto, "consultas prontas" e "ainda rodando"."""
    catalogo = i18n.carregar()[idioma]
    for chave in ("rodando", "prontas", "ainda_rodando", "detalhes"):
        assert f"execucao.{chave}" not in catalogo
    for chave in ("preparando", "coleta", "coleta_um", "detalhes", "detalhes_um", "sites_mais"):
        assert catalogo[f"execucao.etapa.{chave}"]
    assert (
        catalogo["execucao.terminou"]
        == {
            "pt": "Pronto. Vagas novas: {n}.",
            "en": "Done. New jobs: {n}.",
        }[idioma]
    )


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_aviso_contas_tem_texto(idioma: str) -> None:
    """T276: as quatro chaves da faixa de queda, com o parâmetro certo em cada uma."""
    catalogo = i18n.carregar()[idioma]
    for chave in ("um", "varios", "gmail", "entrar"):
        assert catalogo.get(f"casca.aviso_contas.{chave}")
    assert "{site}" in catalogo.get("casca.aviso_contas.um", "")
    assert "{quantos}" in catalogo.get("casca.aviso_contas.varios", "")
    assert "{site}" not in catalogo["casca.aviso_contas.gmail"]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_aviso_candidatura_tem_texto(idioma: str) -> None:
    """T285: as seis chaves da faixa "Você se candidatou?", com os parâmetros do desenho 5.8."""
    catalogo = i18n.carregar()[idioma]
    params = {
        "pergunta": {"titulo", "empresa"},
        "quando": {"quando"},
        "sim": set(),
        "ainda_nao": set(),
        "mais": {"n"},
        "marcada": {"titulo"},
    }
    for chave, esperados in params.items():
        texto = catalogo.get(f"casca.aviso_candidatura.{chave}", "")
        assert texto, chave
        assert set(re.findall(r"\{(\w+)\}", texto)) == esperados, chave


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_abas_do_topo_sairam_e_a_lista_tem_rotulo(idioma: str) -> None:
    """T254: a `nav.abas` sai (a lateral faz o papel dela); o listbox e o estado vazio entram."""
    catalogo = i18n.carregar()[idioma]
    assert "vagas.abas" not in catalogo
    esperado = {
        "pt": ("Vagas", "Nenhuma vaga", "Buscar vagas"),
        "en": ("Jobs", "No Jobs", "Search for Jobs"),
    }[idioma]
    assert (
        catalogo["vagas.lista"],
        catalogo["vagas.vazio.titulo"],
        catalogo["vagas.vazio.buscar"],
    ) == esperado


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_alerta_de_apagar_busca_e_botoes_comuns(idioma: str) -> None:
    """T259: o alerta da busca e os rótulos que a Sites e o Esquecer logins reaproveitam; o
    "Apagar mesmo" em dois cliques saiu. Em inglês, Title Case nos botões e no título."""
    catalogo = i18n.carregar()[idioma]
    for velha in ("buscas.apagar_aviso", "buscas.apagar_confirmar"):
        assert velha not in catalogo
    esperado = {
        "pt": {
            "buscas.apagar_titulo": "Apagar a busca «{nome}»?",
            "buscas.apagar_texto": "As vagas que ela trouxe continuam.",
            "comum.apagar": "Apagar",
            "comum.remover": "Remover",
            "comum.esquecer": "Esquecer",
            "comum.cancelar": "Cancelar",
        },
        "en": {
            "buscas.apagar_titulo": 'Delete the Search "{nome}"?',
            "buscas.apagar_texto": "Jobs it brought in stay.",
            "comum.apagar": "Delete",
            "comum.remover": "Remove",
            "comum.esquecer": "Forget",
            "comum.cancelar": "Cancel",
        },
    }[idioma]
    assert {chave: catalogo.get(chave) for chave in esperado} == esperado
    assert catalogo["buscas.apagar_titulo"].endswith("?")


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_menu_e_interruptor_da_lista_de_buscas(idioma: str) -> None:
    catalogo = i18n.carregar()[idioma]
    for chave in ("buscas.menu.rotulo", "buscas.menu.apagar", "buscas.chave_rotulo"):
        assert catalogo[chave].strip(), chave
    rotulo = catalogo["buscas.chave_rotulo"]
    assert "{nome}" in rotulo
    # nome do interruptor identifica o item; o estado vem do checked (nada de verbo fixo)
    assert not rotulo.startswith(("Ligar", "Turn", "Desligar"))


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_alerta_de_remover_site_e_fontes_em_caixa_de_marcar(idioma: str) -> None:
    """T261: o alerta do site usa o molde da T259 e o rótulo comum; a pergunta em dois cliques e
    o botão solto "Remover" da Sites saíram. A caixa de marcar das Fontes tem rótulo sem verbo
    (o estado vem do `checked`), e em inglês botão, menu e título vão em Title Case."""
    catalogo = i18n.carregar()[idioma]
    for velha in ("sites.remover", "sites.remover_aviso", "sites.remover_confirmar"):
        assert velha not in catalogo
    esperado = {
        "pt": {
            "sites.remover_titulo": "Remover o site «{nome}»?",
            "sites.remover_texto": "O texto guardado e as mudanças dele serão apagados.",
            "sites.menu.remover": "Remover…",
            "fontes.liga_rotulo": "Ligada",
        },
        "en": {
            "sites.remover_titulo": 'Remove the Site "{nome}"?',
            "sites.remover_texto": "Its saved text and changes will be deleted.",
            "sites.menu.remover": "Remove…",
            "fontes.liga_rotulo": "On",
        },
    }[idioma]
    assert {chave: catalogo.get(chave) for chave in esperado} == esperado
    assert catalogo["sites.remover_titulo"].endswith("?")
    assert catalogo["sites.menu.rotulo"].strip()
    assert catalogo["fontes.ligar"] and catalogo["fontes.desligar"]  # o <noscript> ainda usa


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_sem_grupo_sites_com_login(idioma: str) -> None:
    """A aba virou Contas (T275): a chave velha do grupo sai dos dois catálogos."""
    catalogo = i18n.carregar()[idioma]
    assert "configuracoes.grupo.sites_com_login" not in catalogo
    assert catalogo["configuracoes.grupo.contas"] == {"pt": "Contas", "en": "Accounts"}[idioma]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_estados_e_motivos_tem_texto(idioma: str) -> None:
    """Todo selo e todo motivo do cartão tem texto; `esquecido` não aparece (vira Nunca entrou)."""
    catalogo = i18n.carregar()[idioma]
    for estado in NA_TELA:
        assert catalogo[f"configuracoes.contas.estado.{estado}"].strip(), estado
    for motivo in set(MOTIVOS_DE_SESSAO) - {"esquecido"}:
        assert catalogo[f"configuracoes.contas.motivo.{motivo}"].strip(), motivo
    assert "configuracoes.contas.motivo.esquecido" not in catalogo


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_conferir_tem_texto(idioma: str) -> None:
    """T277: as frases do "Conferir agora" nos dois idiomas (desenho 5.8) e o anúncio do fim."""
    catalogo = i18n.carregar()[idioma]
    esperado = {
        "pt": {
            "configuracoes.contas.conferir": "Conferir agora",
            "configuracoes.contas.conferindo": "Conferindo…",
            "configuracoes.contas.ocupado": "Já tem algo usando o navegador; tente daqui a pouco.",
            "configuracoes.contas.conferir_espera": (
                "Conferido há pouco. Dá para conferir de novo em alguns minutos."
            ),
            "configuracoes.contas.conferido_resultado": "{site}: {estado}.",
        },
        "en": {
            "configuracoes.contas.conferir": "Check now",
            "configuracoes.contas.conferindo": "Checking…",
            "configuracoes.contas.ocupado": (
                "Something is already using the browser; try again in a moment."
            ),
            "configuracoes.contas.conferir_espera": (
                "Checked a moment ago. You can check again in a few minutes."
            ),
            "configuracoes.contas.conferido_resultado": "{site}: {estado}.",
        },
    }[idioma]
    assert {chave: catalogo.get(chave) for chave in esperado} == esperado


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_linha_desde_tem_texto(idioma: str) -> None:
    """T287: a frase "{status} desde {data}" da aba Candidatei, nos dois idiomas."""
    esperado = {"pt": "{status} desde {data}", "en": "{status} since {data}"}[idioma]
    assert i18n.carregar()[idioma].get("vagas.linha.desde") == esperado


GMAIL = {
    "pt": {
        "titulo": "Gmail",
        "explicacao": (
            "Para o joBot conferir o seu Gmail, crie uma senha de app na sua conta Google e cole "
            "aqui."
        ),
        "acesso": (
            "A senha de app dá acesso a todo o seu e-mail. O joBot só abre a caixa de entrada "
            "para leitura."
        ),
        "endereco": "Endereço do Gmail",
        "senha": "Senha de app",
        "senha_guardada": "Há uma senha de app guardada. Para trocar, cole outra.",
        "salvar": "Salvar e conferir",
        "remover": "Remover",
        "remover_pergunta": "Remover a senha de app do Gmail?",
        "remover_explicacao": (
            "O joBot deixa de conferir o Gmail. A senha continua valendo na sua conta Google até "
            "você revogá-la lá."
        ),
        "tutorial": "Como criar uma senha de app",
        "tutorial_url": "https://github.com/fezarosa-dev/joBot/wiki/Gmail-senha-de-app",
        "erro.endereco": "Digite um endereço de e-mail, como nome@gmail.com.",
        "erro.senha": "A senha de app tem 16 letras. Copie de novo da página do Google.",
        "erro.recusada": "O Google recusou a senha. Confira o endereço ou crie outra senha de app.",
        "erro.cofre": "O cofre do sistema não respondeu.",
        "erro.nao_apagou": "A senha não foi apagada. Tente de novo.",
        "nao_guardou": "A senha não foi guardada.",
        "no_arquivo": "Sem cofre do sistema: a senha ficou num arquivo que só o seu usuário lê.",
    },
    "en": {
        "titulo": "Gmail",
        "explicacao": (
            "To let joBot check your Gmail, create an app password in your Google account and "
            "paste it here."
        ),
        "acesso": (
            "An app password gives access to your whole mailbox. joBot only opens the inbox "
            "read-only."
        ),
        "endereco": "Gmail Address",
        "senha": "App Password",
        "senha_guardada": "An app password is saved. To change it, paste a new one.",
        "salvar": "Save and Check",
        "remover": "Remove",
        "remover_pergunta": "Remove the Gmail app password?",
        "remover_explicacao": (
            "joBot stops checking Gmail. The password stays valid in your Google account until "
            "you revoke it there."
        ),
        "tutorial": "How to Create an App Password",
        "tutorial_url": "https://github.com/fezarosa-dev/joBot/wiki/Gmail-app-password",
        "erro.endereco": "Enter an email address, like name@gmail.com.",
        "erro.senha": "An app password has 16 letters. Copy it again from the Google page.",
        "erro.recusada": (
            "Google refused the password. Check the address or create a new app password."
        ),
        "erro.cofre": "The system password vault did not respond.",
        "erro.nao_apagou": "The password was not removed. Try again.",
        "nao_guardou": "The password was not saved.",
        "no_arquivo": (
            "No system password vault: the password is in a file only your user can read."
        ),
    },
}


PANORAMA = {
    "titulo": set(),
    "busca_contada": {"busca"},
    "sem_busca": set(),
    "vazio": set(),
    "hoje.titulo": set(),
    "candidaturas.titulo": set(),
    "candidaturas.ver": set(),
    "responder.titulo": set(),
    "responder.vazio": set(),
    "fecham.titulo": set(),
    "fecham.prazo": {"data"},
    "fecham.vazio": set(),
    "fecham.ver": set(),
    "busca.titulo": set(),
    "busca.ultima": {"quando"},
    "busca.nunca": set(),
    "busca.proxima": {"hora"},
    "busca.proxima_dia": {"dia", "hora"},
    "busca.rodando": set(),
    "busca.fontes_ok": set(),
    "busca.fontes_problema": {"n"},
    "busca.ver_fontes": set(),
    "busca.contas": {"n"},
    "busca.ver_contas": set(),
    "aparece.titulo": set(),
    "aparece.descricao": set(),
    "aparece.mais_comum": {"valor", "n", "total"},
    "aparece.ver": set(),
}


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_gmail_tem_texto(idioma: str) -> None:
    """T278: as frases do cartão do Gmail nos dois idiomas, frase por frase, com o tutorial na
    página do idioma; nenhuma chave do Gmail fora desta lista."""
    catalogo = i18n.carregar()[idioma]
    prefixo = "configuracoes.contas.gmail."
    achadas = {
        chave[len(prefixo) :]: v for chave, v in catalogo.items() if chave.startswith(prefixo)
    }
    assert achadas == GMAIL[idioma]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_detalhe_passos_e_email_tem_texto(idioma: str) -> None:
    """T286: a Linha do tempo (um texto por passo de `PASSOS`, mais vista e abriu) e o e-mail de
    candidatura, com o texto e os parâmetros do desenho 5.8."""
    esperado = {
        "pt": {
            "detalhe.passos.titulo": "Linha do tempo",
            "detalhe.passos.vista": "Vista em {data}",
            "detalhe.passos.abriu": "Abriu a candidatura em {data}",
            "detalhe.passos.salva": "Salva em {data}",
            "detalhe.passos.candidatei": "Candidatei em {data}",
            "detalhe.passos.entrevista": "Entrevista em {data}",
            "detalhe.passos.oferta": "Oferta em {data}",
            "detalhe.passos.recusada": "Recusada em {data}",
            "detalhe.candidatar_email": "Candidatar-se por e-mail",
            "detalhe.candidatar_email_rotulo": (
                "Candidatar-se por e-mail (abre o seu programa de e-mail)"
            ),
            "detalhe.email.endereco": "Endereço para candidatura: {email}",
            "detalhe.email.copiar": "Copiar endereço",
            "detalhe.email.copiado": "Endereço copiado.",
            "detalhe.email.nao_copiou": "Não deu para copiar. Selecione o endereço e copie.",
            "detalhe.email.aviso": (
                "O joBot não envia nada: o e-mail sai do seu programa de e-mail."
            ),
        },
        "en": {
            "detalhe.passos.titulo": "Timeline",
            "detalhe.passos.vista": "Found {data}",
            "detalhe.passos.abriu": "Opened the application {data}",
            "detalhe.passos.salva": "Saved {data}",
            "detalhe.passos.candidatei": "Applied {data}",
            "detalhe.passos.entrevista": "Interview {data}",
            "detalhe.passos.oferta": "Offer {data}",
            "detalhe.passos.recusada": "Rejected {data}",
            "detalhe.candidatar_email": "Apply by Email",
            "detalhe.candidatar_email_rotulo": "Apply by email (opens your email app)",
            "detalhe.email.endereco": "Application address: {email}",
            "detalhe.email.copiar": "Copy Address",
            "detalhe.email.copiado": "Address copied.",
            "detalhe.email.nao_copiou": "Couldn't copy. Select the address and copy it.",
            "detalhe.email.aviso": (
                "joBot doesn't send anything: the email goes out from your email app."
            ),
        },
    }[idioma]
    catalogo = i18n.carregar()[idioma]
    assert {chave: catalogo.get(chave) for chave in esperado} == esperado
    # o template monta a chave por `t("detalhe.passos." ~ chave)`: todo passo tem texto
    for passo in ("vista", "abriu", *PASSOS):
        assert "{data}" in catalogo.get(f"detalhe.passos.{passo}", ""), passo


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_panorama_tem_texto(idioma: str) -> None:
    """T288: as chaves `panorama.*` do desenho 5.8 mais a `proxima_dia` (E19), com os mesmos
    parâmetros nos dois idiomas. A frase do estado vazio cita o botão pelo texto da chave dele."""
    catalogo = i18n.carregar()[idioma]
    achadas = {c.removeprefix("panorama.") for c in catalogo if c.startswith("panorama.")}
    assert achadas == set(PANORAMA)
    for chave, esperados in PANORAMA.items():
        texto = catalogo[f"panorama.{chave}"]
        assert texto, chave
        assert set(re.findall(r"\{(\w+)\}", texto)) == esperados, chave
    assert f'"{catalogo["execucao.buscar_agora"]}"' in catalogo["panorama.vazio"]
    esperado = {
        "pt": ("Panorama", "Próxima busca automática em {dia}, por volta das {hora}."),
        "en": ("Overview", "Next automatic search on {dia}, around {hora}."),
    }[idioma]
    assert (catalogo["panorama.titulo"], catalogo["panorama.busca.proxima_dia"]) == esperado
