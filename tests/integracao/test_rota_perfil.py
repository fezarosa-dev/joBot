"""Aba Perfil de Configurações (desenho 8 da fase 4; plano T413; D200).

As habilidades, uma por linha, vão ao banco sem repetidos; "Apagar perfil" pede confirmação. O
encaixe é recalculado com as habilidades novas antes de gravar (padrões «Config»).
"""

import html as html_lib
import json
import re
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import AGORA, inserir_vaga, semear
from jobot.banco import cadastros, perfil
from jobot.banco.buscas import criar_busca
from jobot.banco.conexao import abrir
from jobot.banco.ia import gravar_pede
from jobot.banco.migrar import migrar
from jobot.nucleo.modelo import Busca
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47619
PERFIL = "/configuracoes/perfil"
APAGAR = PERFIL + "/apagar"
CONFIRMAR = APAGAR + "/confirmar"
HOJE = date(2026, 11, 13)
RECALCULAR = "jobot.painel.rotas.perfil.buscas.recalcular_encaixe"
# o 303 volta à seção que gravou (D230.1): a página não pula para o alto, e o "Salvo." fica dentro
# da seção (D230, decidido pelo dono), para a troca do HTMX trazê-lo
SALVO = {
    secao: (303, f"{PERFIL}?salvo={ancora}#perfil-{ancora}")
    for secao, ancora in (
        (None, "habilidades"),
        ("dados", "sobre"),
        ("experiencia", "experiencias"),
        ("curso", "cursos"),
    )
}


class Painel:
    """Cliente do app sobre um banco semeado, com o relógio parado."""

    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            semear(con)
            cadastros.semear(con)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso()
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        # erro do servidor vira 500 aqui, para a falta de uma conferência reprovar por asserção
        self.http_500 = TestClient(
            self.app,
            base_url=f"http://127.0.0.1:{PORTA}",
            follow_redirects=False,
            raise_server_exceptions=False,
        )
        self.token: str = self.app.state.csrf

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def get(self, url: str) -> Any:
        return self.http.get(url)

    def post(
        self,
        url: str,
        dados: dict[str, Any] | None = None,
        *,
        csrf: bool = True,
        sem_500: bool = False,
    ) -> Any:
        token = {CAMPO_CSRF: self.token} if csrf else {}
        return (self.http_500 if sem_500 else self.http).post(url, data=token | (dados or {}))

    def habilidades(self) -> list[str] | None:
        linhas = self.sql("SELECT habilidades FROM perfil")
        return json.loads(linhas[0][0]) if linhas else None

    def idioma(self, idioma: str) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.gravar_config(con, "idioma", idioma)

    def tarefa(self, valor: object) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.gravar_config(con, "ia_tarefas", {"encaixe": valor})


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", html)))


def _campo(html: str) -> str:
    """O conteúdo do `<textarea name="habilidades">`, sem escape."""
    achado = re.search(r'<textarea\b[^>]*name="habilidades"[^>]*>(.*?)</textarea>', html, re.S)
    assert achado is not None, "sem o campo das habilidades"
    return html_lib.unescape(achado.group(1))


def _status(resposta: Any) -> tuple[int, str | None]:
    return resposta.status_code, resposta.headers.get("location")


def _sem_paleta(html: str) -> str:
    return re.sub(r'<dialog id="paleta".*?</dialog>', "", html, flags=re.S)


# ------------------------------------------------------------------ a aba


def test_perfil_abre_com_a_aba_e_o_campo_com_rotulo(painel: Painel) -> None:
    resposta = painel.get(PERFIL)
    assert resposta.status_code == 200
    nav = re.search(r'<nav class="config-grupos".*?</nav>', resposta.text, re.S)
    assert nav is not None
    marcada = re.findall(r'<a [^>]*href="([^"]+)"[^>]*aria-current="page"', nav.group(0))
    assert marcada == [PERFIL]
    assert 'data-icone="graduation-cap"' in re.findall(r"<a\b[^>]*perfil[^>]*>", nav.group(0))[0]
    campo = re.search(r'<textarea\b[^>]*name="habilidades"[^>]*>', resposta.text)
    assert campo is not None
    id_campo = re.search(r'id="([^"]+)"', campo.group(0))
    assert id_campo is not None
    assert f'<label for="{id_campo.group(1)}"' in resposta.text  # nome acessível
    assert "aria-describedby=" in campo.group(0)
    assert _campo(resposta.text) == ""
    # um botão principal por formulário de gravar: o Salvar de cada seção
    formularios = re.findall(
        r'<form method="post" action="/configuracoes/perfil".*?</form>',
        _sem_paleta(resposta.text),
        re.S,
    )
    assert len(formularios) == 4  # sobre você, habilidades, nova experiência e novo curso
    assert [len(re.findall(r'class="[^"]*botao-primario', f)) for f in formularios] == [1] * 4


def test_perfil_vem_depois_de_funcoes_nas_abas(painel: Painel) -> None:
    nav = painel.get(PERFIL).text.split('class="config-grupos"')[1].split("</nav>")[0]
    abas = re.findall(r'href="/configuracoes/([^"]+)"', nav)
    assert abas[abas.index("funcoes") + 1] == "perfil"


# ------------------------------------------------------------------ gravar


def test_habilidades_gravadas_normalizadas_sem_repetidos(painel: Painel) -> None:
    texto = (
        "  Python  \r\n\npython\nPostgreSQL,\n  Machine \t  Learning \n"
        "PÝTHON.\n(Docker)\nC++\n.NET\nReact\u200b\n\n"
    )
    resposta = painel.post(PERFIL, {"habilidades": texto})
    assert _status(resposta) == SALVO[None]
    gravadas = ["Python", "PostgreSQL", "Machine Learning", "Docker", "C++", ".NET", "React"]
    assert painel.habilidades() == gravadas
    pagina = painel.get(PERFIL + "?salvo=1").text
    assert _campo(pagina) == "\n".join(gravadas)
    assert "Salvo." in _texto(pagina)


def test_campo_vazio_grava_lista_vazia(painel: Painel) -> None:
    painel.post(PERFIL, {"habilidades": "Go"})
    assert painel.habilidades() == ["Go"]  # controle
    assert _status(painel.post(PERFIL, {"habilidades": " \n \n"})) == SALVO[None]
    assert painel.habilidades() == []


def test_sem_o_campo_da_422_e_nao_grava(painel: Painel) -> None:
    painel.post(PERFIL, {"habilidades": "Go"})
    assert painel.post(PERFIL, {}).status_code == 422
    assert painel.habilidades() == ["Go"]


@pytest.mark.parametrize(
    ("texto", "aceita"),
    [
        ("\n".join(f"h{n}" for n in range(200)), True),
        ("\n".join(f"h{n}" for n in range(201)), False),
        ("x" * 100, True),
        ("Go\n" + "x" * 101, False),
    ],
)
def test_teto_de_habilidades_volta_com_o_texto(painel: Painel, texto: str, aceita: bool) -> None:
    painel.post(PERFIL, {"habilidades": "Rust"})
    resposta = painel.post(PERFIL, {"habilidades": texto})
    if aceita:
        assert _status(resposta) == SALVO[None]
        assert painel.habilidades() == texto.split("\n")
        return
    assert resposta.status_code == 422
    alerta = re.search(r'role="alert"[^>]*>(.*?)</div>', resposta.text, re.S)
    assert alerta is not None
    assert "Até 200 habilidades, cada uma com até 100 caracteres." in _texto(alerta.group(1))
    assert _campo(resposta.text) == texto  # o que foi digitado volta para corrigir
    assert painel.habilidades() == ["Rust"]
    # o campo aponta para a mensagem do erro, não só para a ajuda
    caixa = re.search(r'<textarea[^>]*name="habilidades"[^>]*>', resposta.text)
    assert caixa is not None
    assert re.search(r'aria-describedby="[^"]*\bconfig-erro\b', caixa.group(0))
    assert 'id="config-erro"' in resposta.text


# ------------------------------------------------------------------ encaixe


def _vaga_que_pede(painel: Painel) -> tuple[int, int]:
    """Uma busca por "python" e uma vaga que pede Python e Docker (desenho 5.5)."""
    with closing(abrir(painel.banco)) as con:
        vaga = inserir_vaga(con, titulo="Dev Python")
        gravar_pede(
            con,
            vaga,
            chave="c1",
            pede=["Python", "Docker"],
            backend="local",
            modelo="qwen",
            versao=1,
            agora=AGORA,
        )
        busca = criar_busca(
            con, Busca(nome="Py", cargos=("python",)), AGORA, regras_ligadas=True, hoje=HOJE
        )
    return busca, vaga


def _nota(painel: Painel, busca: int, vaga: int) -> int:
    linhas = painel.sql("SELECT nota FROM encaixe WHERE busca_id = ? AND vaga_id = ?", busca, vaga)
    return int(linhas[0][0])


def test_salvar_e_apagar_mudam_a_nota_sem_pedir_a_ia(painel: Painel) -> None:
    busca, vaga = _vaga_que_pede(painel)
    pede = painel.sql("SELECT * FROM habilidades_vaga")
    assert _nota(painel, busca, vaga) == 62  # sem perfil: nada casa (40 de 65)
    painel.post(PERFIL, {"habilidades": "python"})
    assert _nota(painel, busca, vaga) == 82
    painel.post(PERFIL, {"habilidades": "Python\nDOCKER"})
    assert _nota(painel, busca, vaga) == 100
    painel.post(APAGAR)
    assert _nota(painel, busca, vaga) == 62
    assert painel.sql("SELECT * FROM habilidades_vaga") == pede  # não depende do perfil


def test_recalculo_que_falha_nao_grava_as_habilidades(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    busca, vaga = _vaga_que_pede(painel)
    painel.post(PERFIL, {"habilidades": "python"})

    def quebra(*_: object, **__: object) -> None:
        raise sqlite3.OperationalError("banco travado")

    with monkeypatch.context() as m:
        m.setattr(RECALCULAR, quebra)
        with pytest.raises(sqlite3.OperationalError):
            painel.post(PERFIL, {"habilidades": "Python\nDocker"})
        with pytest.raises(sqlite3.OperationalError):
            painel.post(APAGAR)
    assert painel.habilidades() == ["python"]
    assert _nota(painel, busca, vaga) == 82  # o encaixe segue como estava
    painel.post(PERFIL, {"habilidades": "Python\nDocker"})  # sem falha: grava e recalcula
    assert painel.habilidades() == ["Python", "Docker"]
    assert _nota(painel, busca, vaga) == 100


def test_mesmo_conjunto_grava_sem_recalcular(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel.post(PERFIL, {"habilidades": "Python\nGo"})
    chamadas: list[dict[str, object]] = []

    def conta(*args: object, **kw: object) -> int:
        chamadas.append(kw)
        return 0

    monkeypatch.setattr(RECALCULAR, conta)
    assert _status(painel.post(PERFIL, {"habilidades": "go\npython\n"})) == SALVO[None]
    assert chamadas == []
    assert painel.habilidades() == ["go", "python"]  # ordem e grafia novas gravadas
    painel.post(PERFIL, {"habilidades": "Python"})  # controle: a lista mudou
    assert len(chamadas) == 1
    assert chamadas[0]["habilidades_perfil"] == ["Python"]


# ------------------------------------------------------------------ apagar


def test_apagar_perfil_pede_confirmacao_e_apaga_a_linha(painel: Painel) -> None:
    painel.post(PERFIL, {"habilidades": "Python"})
    pagina = painel.get(PERFIL).text
    # sem JavaScript, o botão leva à pergunta (GET, sem mudar nada)
    assert f'<form method="get" action="{CONFIRMAR}">' in pagina
    assert f'action="{APAGAR}"' in pagina  # o POST mora no alerta
    pergunta = painel.get(CONFIRMAR)
    assert pergunta.status_code == 200
    assert painel.habilidades() == ["Python"]
    assert "Apagar o perfil?" in _texto(pergunta.text)
    assert f'action="{APAGAR}"' in pergunta.text
    assert f'name="csrf_token" value="{painel.token}"' in pergunta.text
    assert _status(painel.post(APAGAR)) == (303, PERFIL + "?apagado=1")
    assert painel.sql("SELECT count(*) FROM perfil") == [(0,)]
    depois = painel.get(PERFIL + "?apagado=1").text
    assert "Perfil apagado." in _texto(depois)
    assert _campo(depois) == ""
    assert CONFIRMAR not in depois  # sem perfil, nada a apagar


def test_sem_habilidades_nao_mostra_apagar(painel: Painel) -> None:
    assert CONFIRMAR not in painel.get(PERFIL).text
    painel.post(PERFIL, {"habilidades": "Go"})
    assert CONFIRMAR in painel.get(PERFIL).text  # controle


def test_aviso_de_apagado_so_com_o_codigo(painel: Painel) -> None:
    assert "Perfil apagado." not in _texto(painel.get(PERFIL + "?apagado=x").text)
    assert "Perfil apagado." in _texto(painel.get(PERFIL + "?apagado=1").text)


# ------------------------------------------------------------------ CSRF


@pytest.mark.parametrize("url", [PERFIL, APAGAR])
def test_post_sem_csrf_e_recusado(painel: Painel, url: str) -> None:
    painel.post(PERFIL, {"habilidades": "Go"})
    assert painel.post(url, {"habilidades": "Rust"}, csrf=False).status_code == 403
    assert painel.habilidades() == ["Go"]
    resposta = painel.post(url, {"habilidades": "Rust"})  # controle: com o token passa
    assert resposta.status_code == 303
    assert painel.habilidades() == (["Rust"] if url == PERFIL else None)


# ------------------------------------------------------------------ privacidade e idiomas


@pytest.mark.parametrize(
    ("idioma", "tarefa", "frase"),
    [
        (
            "pt",
            None,
            "No encaixe, suas habilidades ficam no seu computador: a IA do encaixe está desligada.",
        ),
        (
            "pt",
            {"ligada": False, "backend": "anthropic", "modelo": "m"},
            "No encaixe, suas habilidades ficam no seu computador: a IA do encaixe está desligada.",
        ),
        (
            "pt",
            {"ligada": True, "backend": "local", "modelo": "qwen"},
            "No encaixe, suas habilidades ficam no seu computador, e o texto da vaga também: "
            "o encaixe usa o modelo local.",
        ),
        (
            "pt",
            {"ligada": True, "backend": "anthropic", "modelo": "m"},
            "No encaixe, suas habilidades ficam no seu computador; só o texto da vaga vai para "
            "a API da Anthropic.",
        ),
        (
            "pt",
            {"ligada": True, "backend": "compativel", "modelo": "m"},
            "No encaixe, suas habilidades ficam no seu computador; só o texto da vaga vai para "
            "o serviço compatível com a OpenAI.",
        ),
        (
            "pt",
            {"ligada": True, "backend": "xyz", "modelo": "m"},
            "No encaixe, suas habilidades ficam no seu computador; só o texto da vaga vai para "
            "um serviço de fora.",
        ),
        ("en", None, "In matching, your skills stay on your computer: matching AI is off."),
        (
            "en",
            {"ligada": True, "backend": "local", "modelo": "qwen"},
            "In matching, your skills stay on your computer, and so does the job text: "
            "matching uses the local model.",
        ),
        (
            "en",
            {"ligada": True, "backend": "gemini", "modelo": "m"},
            "In matching, your skills stay on your computer; only the job text goes to "
            "Google Gemini.",
        ),
    ],
)
def test_frase_de_privacidade(painel: Painel, idioma: str, tarefa: object, frase: str) -> None:
    painel.idioma(idioma)
    if tarefa is not None:
        painel.tarefa(tarefa)
    assert frase in _texto(painel.get(PERFIL).text)


@pytest.mark.parametrize(
    ("encaixe", "perguntas", "frase"),
    [
        (
            None,
            {"ligada": True, "backend": "openai", "modelo": "m"},
            "Ao pedir perguntas, o seu perfil, sem nome, contato e cidade, vai para a OpenAI; o que"
            " você escreveu nos campos de texto vai como você escreveu, menos e-mail, telefone,"
            " CPF e o seu nome, quando escrito como está no perfil.",
        ),
        (
            {"ligada": True, "backend": "local", "modelo": "m"},
            {"ligada": True, "backend": "local", "modelo": "m"},
            "O seu perfil fica no seu computador: as perguntas usam o modelo local.",
        ),
    ],
)
def test_frase_de_privacidade_conta_a_tarefa_perguntas(
    painel: Painel, encaixe: object, perguntas: object, frase: str
) -> None:
    """As habilidades vão no pedido das perguntas (D233): com `perguntas` ligada, a aba diz para
    onde o perfil vai, e nada diz que nada sai. Controle: com `perguntas` desligada, a frase das
    perguntas não aparece."""
    tarefas: dict[str, object] = {"perguntas": perguntas}
    if encaixe is not None:
        tarefas["encaixe"] = encaixe
    with closing(abrir(painel.banco)) as con:
        cadastros.gravar_config(con, "ia_tarefas", tarefas)
    texto = _texto(painel.get(PERFIL).text)
    assert frase in texto
    assert "nada sai" not in texto
    with closing(abrir(painel.banco)) as con:
        cadastros.gravar_config(
            con, "ia_tarefas", tarefas | {"perguntas": {"ligada": False, "backend": "openai"}}
        )
    texto = _texto(painel.get(PERFIL).text)
    assert frase not in texto
    assert "nada sai" not in texto  # a frase da tarefa desligada é da página do questionário


@pytest.mark.parametrize("backend", ["anthropic", "openai", "gemini", "compativel", "outro"])
def test_todo_servico_tem_nome_nos_dois_catalogos(backend: str) -> None:
    catalogos = i18n.carregar()
    for idioma in ("pt", "en"):
        assert f"configuracoes.perfil.servico.{backend}" in catalogos[idioma]


def test_textos_do_perfil_nos_dois_catalogos(painel: Painel) -> None:
    catalogos = i18n.carregar()
    chaves = {c for idioma in ("pt", "en") for c in catalogos[idioma] if ".perfil" in c}
    assert "configuracoes.grupo.perfil" in chaves
    for idioma in ("pt", "en"):
        assert sorted(c for c in chaves if c not in catalogos[idioma]) == []
    painel.idioma("en")
    painel.post(PERFIL, {"habilidades": "Go"})
    pagina = _texto(painel.get(PERFIL).text)
    for frase in ("Profile", "Your skills", "Delete profile", "Save"):
        assert frase in pagina
    assert "Suas habilidades" not in pagina
    assert "Delete the profile?" in _texto(painel.get(CONFIRMAR).text)


# ------------------------------------------------------------------ perfil completo (T434)

DADOS: dict[str, Any] = {
    "secao": "dados",
    "nome": "Maria Exemplo",
    "email": "maria@exemplo.test",
    "telefone": "+55 11 0000-0000",
    "cidade_moradia": "Campinas",
    "links": "https://exemplo.test/maria\n\n http://portfolio.exemplo.test \n",
    "cargo_atual": "Analista de dados",
    "anos_de_experiencia": "7",
    "formacao_nivel": "pos_graduacao",
    "resumo": "Trabalho com dados.\nGosto de SQL.",
    "idioma_pt": "fluente",
    "idioma_en": "avancado",
    "idioma_es": "",
    "outro_nome": ["Alemão", ""],
    "outro_nivel": ["basico", ""],
}
EXPERIENCIA: dict[str, Any] = {
    "secao": "experiencia",
    "id": "",
    "cargo": "Analista",
    "empresa": "Empresa Exemplo",
    "inicio": "2019-03",
    "fim": "",
    "descricao": "Painéis e relatórios.",
}
CURSO: dict[str, Any] = {
    "secao": "curso",
    "id": "",
    "nome": "Estatística",
    "instituicao": "Universidade Exemplo",
    "situacao": "concluido",
    "previsao": "2018-12",
}


def _dados(painel: Painel) -> perfil.Dados:
    with closing(abrir(painel.banco)) as con:
        return perfil.dados(con)


def _experiencias(painel: Painel) -> list[perfil.Experiencia]:
    with closing(abrir(painel.banco)) as con:
        return perfil.experiencias(con)


def _cursos(painel: Painel) -> list[perfil.Curso]:
    with closing(abrir(painel.banco)) as con:
        return perfil.cursos(con)


def _valor(html: str, campo_id: str) -> str:
    """O `value` do `<input id=...>` (sem escape), ou o texto do `<textarea>`."""
    entrada = re.search(rf'<input\b[^>]*\bid="{campo_id}"[^>]*>', html)
    if entrada is not None:
        valor = re.search(r'\bvalue="([^"]*)"', entrada.group(0))
        return html_lib.unescape(valor.group(1)) if valor else ""
    caixa = re.search(rf'<textarea\b[^>]*\bid="{campo_id}"[^>]*>(.*?)</textarea>', html, re.S)
    assert caixa is not None, f"sem o campo {campo_id}"
    return html_lib.unescape(caixa.group(1))


def _escolhido(html: str, campo_id: str) -> str:
    """O `value` da opção marcada do `<select id=...>`."""
    caixa = re.search(rf'<select\b[^>]*\bid="{campo_id}"[^>]*>(.*?)</select>', html, re.S)
    assert caixa is not None, f"sem a lista {campo_id}"
    marcadas = re.findall(r'<option value="([^"]*)"[^>]*\bselected', caixa.group(1))
    return marcadas[0] if marcadas else ""


def _alerta(html: str) -> str:
    achado = re.search(r'role="alert"[^>]*>(.*?)</div>', html, re.S)
    assert achado is not None, "sem o alerta do erro"
    return _texto(achado.group(1)).strip()


def test_secoes_com_titulo_e_campos_com_rotulo(painel: Painel) -> None:
    pagina = painel.get(PERFIL).text
    secoes = re.findall(r'<section class="config-bloco" aria-labelledby="([^"]+)"', pagina)
    titulos = [
        _texto(re.search(rf'<h2 id="{s}"[^>]*>(.*?)</h2>', pagina, re.S).group(1)).strip()  # type: ignore[union-attr]
        for s in secoes
    ]
    assert titulos == ["Currículo em PDF", "Sobre você", "Habilidades", "Experiências", "Cursos"]
    conteudo = _sem_paleta(pagina).split('class="config-conteudo"')[1]
    ids = re.findall(
        r'<(?:input|select|textarea)\b(?![^>]*type="hidden")[^>]*\bid="([^"]+)"', conteudo
    )
    assert len(ids) > 20
    sem_rotulo = [i for i in ids if f'<label for="{i}"' not in conteudo]
    assert sem_rotulo == []
    for formulario in re.findall(r'<form method="post".*?</form>', _sem_paleta(pagina), re.S):
        assert f'name="csrf_token" value="{painel.token}"' in formulario


def test_dados_gravados_e_mostrados_de_volta(painel: Painel) -> None:
    assert _status(painel.post(PERFIL, DADOS)) == SALVO["dados"]
    assert _dados(painel) == perfil.Dados(
        nome="Maria Exemplo",
        email="maria@exemplo.test",
        telefone="+55 11 0000-0000",
        cidade_moradia="Campinas",
        cargo_atual="Analista de dados",
        anos_de_experiencia=7,
        formacao_nivel="pos_graduacao",
        resumo="Trabalho com dados.\nGosto de SQL.",
        idiomas_falados=(("pt", "fluente"), ("en", "avancado"), ("Alemão", "basico")),
        links=("https://exemplo.test/maria", "http://portfolio.exemplo.test"),
    )
    pagina = painel.get(PERFIL).text
    assert _valor(pagina, "perfil-nome") == "Maria Exemplo"
    assert _valor(pagina, "perfil-email") == "maria@exemplo.test"
    assert _valor(pagina, "perfil-telefone") == "+55 11 0000-0000"
    assert _valor(pagina, "perfil-cidade") == "Campinas"
    assert _valor(pagina, "perfil-links") == (
        "https://exemplo.test/maria\nhttp://portfolio.exemplo.test"
    )
    assert _valor(pagina, "perfil-cargo") == "Analista de dados"
    assert _valor(pagina, "perfil-anos") == "7"
    assert _escolhido(pagina, "perfil-formacao") == "pos_graduacao"
    assert _valor(pagina, "perfil-resumo") == "Trabalho com dados.\nGosto de SQL."
    assert _escolhido(pagina, "perfil-idioma-pt") == "fluente"
    assert _escolhido(pagina, "perfil-idioma-en") == "avancado"
    assert _escolhido(pagina, "perfil-idioma-es") == ""
    # o idioma de fora da lista volta na sua linha, e sobra uma linha vazia para mais um
    assert _valor(pagina, "perfil-outro-1") == "Alemão"
    assert _escolhido(pagina, "perfil-outro-1-nivel") == "basico"
    assert _valor(pagina, "perfil-outro-2") == ""


def test_dados_e_habilidades_nao_se_apagam(painel: Painel) -> None:
    painel.post(PERFIL, {"habilidades": "Python"})
    painel.post(PERFIL, DADOS)
    assert painel.habilidades() == ["Python"]
    painel.post(PERFIL, {"habilidades": "Go"})
    assert _dados(painel).nome == "Maria Exemplo"


def test_campo_limpo_apaga_o_valor(painel: Painel) -> None:
    painel.post(PERFIL, DADOS)
    vazio = {c: "" for c in DADOS} | {"secao": "dados", "outro_nome": "", "outro_nivel": ""}
    assert _status(painel.post(PERFIL, vazio)) == SALVO["dados"]
    assert _dados(painel) == perfil.Dados()


@pytest.mark.parametrize(
    ("campo", "valor", "mensagem", "campo_id"),
    [
        ("anos_de_experiencia", "61", "Anos de experiência: um número de 0 a 60.", "perfil-anos"),
        ("anos_de_experiencia", "-1", "Anos de experiência: um número de 0 a 60.", "perfil-anos"),
        ("anos_de_experiencia", "sete", "Anos de experiência: um número de 0 a 60.", "perfil-anos"),
        ("anos_de_experiencia", "７", "Anos de experiência: um número de 0 a 60.", "perfil-anos"),
        (
            "email",
            "maria.exemplo.test",
            "Confira o e-mail: falta o @ ou o domínio.",
            "perfil-email",
        ),
        (
            "links",
            "javascript:alert(1)",
            "Um link por linha, começando com http:// ou https://, até 10.",
            "perfil-links",
        ),
        (
            "links",
            "https://",
            "Um link por linha, começando com http:// ou https://, até 10.",
            "perfil-links",
        ),
        (
            "links",
            "https://exemplo.test/" + "x" * 480,
            "Um link por linha, começando com http:// ou https://, até 10.",
            "perfil-links",
        ),
        (  # `urlsplit` levanta `ValueError` com estes dois: 422, nunca 500
            "links",
            "http://[abc",
            "Um link por linha, começando com http:// ou https://, até 10.",
            "perfil-links",
        ),
        (
            "links",
            "https://exemplo.test\u2100/x",
            "Um link por linha, começando com http:// ou https://, até 10.",
            "perfil-links",
        ),
        (
            "links",
            "ftp://exemplo.test",
            "Um link por linha, começando com http:// ou https://, até 10.",
            "perfil-links",
        ),
        (
            "links",
            "\n".join(f"https://exemplo.test/{n}" for n in range(11)),
            "Um link por linha, começando com http:// ou https://, até 10.",
            "perfil-links",
        ),
        ("nome", "x" * 201, "Um dos campos passou do tamanho máximo.", "perfil-nome"),
        ("resumo", "x" * 2001, "Um dos campos passou do tamanho máximo.", "perfil-resumo"),
    ],
)
def test_dado_errado_volta_com_o_texto_e_nao_grava(
    painel: Painel, campo: str, valor: str, mensagem: str, campo_id: str
) -> None:
    painel.post(PERFIL, DADOS | {"nome": "Antes"})
    resposta = painel.post(PERFIL, DADOS | {"nome": "Depois", campo: valor}, sem_500=True)
    assert resposta.status_code == 422
    assert _alerta(resposta.text) == mensagem
    assert _valor(resposta.text, campo_id) == valor.strip()  # o digitado volta para corrigir
    entrada = re.search(rf'<(?:input|textarea)\b[^>]*\bid="{campo_id}"[^>]*>', resposta.text)
    assert entrada is not None
    assert 'aria-invalid="true"' in entrada.group(0)
    assert re.search(r'aria-describedby="[^"]*\bconfig-erro\b', entrada.group(0))
    # o foco abre no campo errado, sem JavaScript (o `autofocus` de um `<dialog>` só vale aberto)
    focados = re.findall(r"<(?!dialog\b)[^>]*\bautofocus\b[^>]*>", resposta.text)
    assert focados == [entrada.group(0)]
    assert _dados(painel).nome == "Antes"


def test_repetidos_e_linhas_vazias_das_pontas_saem(painel: Painel) -> None:
    links = "https://a.test\nhttps://b.test\nhttps://a.test\n" + "\n".join(
        f"https://c.test/{n}" for n in range(8)
    )
    troca = {
        "links": links,  # 11 linhas, 10 links diferentes: cabe
        "outro_nome": ["Alemão", "ALEMÃO", "Russo"],
        "outro_nivel": ["basico", "fluente", "avancado"],
        "resumo": "\n\n  Primeira  \n\nSegunda\n\n",
    }
    assert _status(painel.post(PERFIL, DADOS | troca)) == SALVO["dados"]
    gravados = _dados(painel)
    assert gravados.links[:2] == ("https://a.test", "https://b.test")
    assert len(gravados.links) == 10
    assert gravados.idiomas_falados[2:] == (("Alemão", "basico"), ("Russo", "avancado"))
    assert gravados.resumo == "Primeira\n\nSegunda"


def test_outro_idioma_sem_nivel_volta_com_o_texto(painel: Painel) -> None:
    resposta = painel.post(PERFIL, DADOS | {"outro_nome": ["Alemão", ""], "outro_nivel": ["", ""]})
    assert resposta.status_code == 422
    assert _alerta(resposta.text) == "Escolha o nível de cada idioma que você escreveu."
    assert _valor(resposta.text, "perfil-outro-1") == "Alemão"
    # o controle errado é a lista do nível, não o nome
    nivel = re.search(r'<select\b[^>]*\bid="perfil-outro-1-nivel"[^>]*>', resposta.text)
    assert nivel is not None
    assert 'aria-invalid="true"' in nivel.group(0)
    assert "autofocus" in nivel.group(0)
    nome = re.search(r'<input\b[^>]*\bid="perfil-outro-1"[^>]*>', resposta.text)
    assert nome is not None
    assert "aria-invalid" not in nome.group(0)
    assert _dados(painel) == perfil.Dados()


def _outros(quantos: int) -> dict[str, list[str]]:
    return {
        "outro_nome": [f"Idioma {n}" for n in range(quantos)],
        "outro_nivel": ["basico"] * quantos,
    }


def test_teto_de_dez_outros_idiomas(painel: Painel) -> None:
    assert _status(painel.post(PERFIL, DADOS | _outros(10))) == SALVO["dados"]
    pagina = painel.get(PERFIL).text
    assert 'id="perfil-outro-10"' in pagina
    assert 'id="perfil-outro-11"' not in pagina  # com dez, sem a linha vazia de mais um
    resposta = painel.post(PERFIL, DADOS | _outros(11))
    assert resposta.status_code == 422
    assert _alerta(resposta.text) == "Até 10 outros idiomas."
    assert len(_dados(painel).idiomas_falados) == 12  # os dois fixos e os dez de antes
    # a tela nunca manda mais de 11 linhas: mais que isso é 422 seco
    linhas = {"outro_nome": ["Russo"] + [""] * 11, "outro_nivel": ["basico"] + [""] * 11}
    assert painel.post(PERFIL, DADOS | linhas, sem_500=True).status_code == 422
    assert len(_dados(painel).idiomas_falados) == 12


def test_outro_idioma_com_o_codigo_de_um_fixo_nao_o_troca(painel: Painel) -> None:
    troca = {"outro_nome": ["pt", "EN", "Russo"], "outro_nivel": ["basico", "basico", "basico"]}
    assert _status(painel.post(PERFIL, DADOS | troca)) == SALVO["dados"]
    assert _dados(painel).idiomas_falados == (
        ("pt", "fluente"),
        ("en", "avancado"),
        ("Russo", "basico"),
    )


@pytest.mark.parametrize(
    "troca",
    [
        {"formacao_nivel": "phd"},
        {"idioma_pt": "otimo"},
        {"outro_nome": ["Alemão"], "outro_nivel": ["otimo"]},
        {"outro_nome": ["Alemão", "Russo"], "outro_nivel": ["basico"]},
        {"secao": "outra"},
    ],
)
def test_valor_fora_da_lista_da_422_seco(painel: Painel, troca: dict[str, Any]) -> None:
    assert painel.post(PERFIL, DADOS | troca, sem_500=True).status_code == 422
    assert _dados(painel) == perfil.Dados()
    assert _status(painel.post(PERFIL, DADOS)) == SALVO["dados"]  # controle


def test_texto_da_pessoa_sai_escapado(painel: Painel) -> None:
    painel.post(PERFIL, DADOS | {"nome": "<script>x</script>"})
    painel.post(PERFIL, EXPERIENCIA | {"cargo": "<b>dev</b>"})
    pagina = painel.get(PERFIL).text
    assert "<script>x" not in pagina
    assert "<b>dev" not in pagina
    assert "&lt;script&gt;x" in pagina
    assert "&lt;b&gt;dev" in pagina


# ------------------------------------------------------------------ experiências e cursos


def test_experiencia_entra_edita_e_tirar_apaga_a_linha(painel: Painel) -> None:
    assert _status(painel.post(PERFIL, EXPERIENCIA)) == SALVO["experiencia"]
    painel.post(PERFIL, EXPERIENCIA | {"cargo": "Estagiário", "fim": "2019-02", "inicio": ""})
    primeira, segunda = _experiencias(painel)
    assert primeira == perfil.Experiencia(
        "Analista", "Empresa Exemplo", "2019-03", None, "Painéis e relatórios.", primeira.id
    )
    assert (segunda.cargo, segunda.inicio, segunda.fim) == ("Estagiário", None, "2019-02")
    pagina = painel.get(PERFIL).text
    assert _valor(pagina, f"exp-{primeira.id}-cargo") == "Analista"
    assert _valor(pagina, f"exp-{primeira.id}-inicio") == "2019-03"
    assert _valor(pagina, f"exp-{segunda.id}-cargo") == "Estagiário"
    assert _valor(pagina, "exp-nova-cargo") == ""

    editada = EXPERIENCIA | {"id": str(primeira.id), "cargo": "Analista sênior", "empresa": ""}
    assert _status(painel.post(PERFIL, editada)) == SALVO["experiencia"]
    assert [(e.id, e.cargo, e.empresa) for e in _experiencias(painel)] == [
        (primeira.id, "Analista sênior", None),
        (segunda.id, "Estagiário", "Empresa Exemplo"),
    ]
    assert _status(painel.post(PERFIL, editada | {"tirar": "1"})) == SALVO["experiencia"]
    assert painel.sql("SELECT id, cargo FROM experiencia") == [(segunda.id, "Estagiário")]
    assert f'id="exp-{primeira.id}-cargo"' not in painel.get(PERFIL).text


def test_curso_entra_edita_e_tirar_apaga_a_linha(painel: Painel) -> None:
    assert _status(painel.post(PERFIL, CURSO)) == SALVO["curso"]
    (curso,) = _cursos(painel)
    assert curso == perfil.Curso(
        "Estatística", "Universidade Exemplo", "concluido", "2018-12", curso.id
    )
    pagina = painel.get(PERFIL).text
    assert _valor(pagina, f"curso-{curso.id}-nome") == "Estatística"
    assert _escolhido(pagina, f"curso-{curso.id}-situacao") == "concluido"
    editado = CURSO | {"id": str(curso.id), "situacao": "cursando", "previsao": "2027-06"}
    assert _status(painel.post(PERFIL, editado)) == SALVO["curso"]
    assert _cursos(painel) == [
        perfil.Curso("Estatística", "Universidade Exemplo", "cursando", "2027-06", curso.id)
    ]
    assert _status(painel.post(PERFIL, editado | {"tirar": "1"})) == SALVO["curso"]
    assert painel.sql("SELECT count(*) FROM curso") == [(0,)]


def test_botoes_de_cada_item_dizem_qual_item(painel: Painel) -> None:
    painel.post(PERFIL, EXPERIENCIA)
    painel.post(PERFIL, EXPERIENCIA | {"cargo": "Estagiário"})
    painel.post(PERFIL, CURSO)
    pagina = _sem_paleta(painel.get(PERFIL).text).split('class="config-conteudo"')[1]
    rotulos = re.findall(r'<button\b[^>]*\baria-label="([^"]+)"', pagina)
    esperados = ["Salvar", "Tirar"]
    assert [html_lib.unescape(r) for r in rotulos] == [
        *(f"{b} Analista" for b in esperados),
        *(f"{b} Estagiário" for b in esperados),
        *(f"{b} Estatística" for b in esperados),
    ]
    painel.idioma("en")
    pagina = painel.get(PERFIL).text.split('class="config-conteudo"')[1]
    rotulos = re.findall(r'<button\b[^>]*\baria-label="([^"]+)"', pagina)
    assert rotulos[:2] == ["Save Analista", "Remove Analista"]


@pytest.mark.parametrize(
    ("dados", "mensagem", "campo"),
    [
        (EXPERIENCIA | {"cargo": "  "}, "Escreva o cargo da experiência.", "cargo"),
        (
            EXPERIENCIA | {"inicio": "2019-13"},
            "Datas no formato AAAA-MM, com o início antes do fim.",
            "inicio",
        ),
        (
            EXPERIENCIA | {"fim": "março"},
            "Datas no formato AAAA-MM, com o início antes do fim.",
            "fim",
        ),
        (
            EXPERIENCIA | {"inicio": "2020-01", "fim": "2019-12"},
            "Datas no formato AAAA-MM, com o início antes do fim.",
            "fim",
        ),
        (
            EXPERIENCIA | {"descricao": "x" * 2001},
            "Um dos campos passou do tamanho máximo.",
            "descricao",
        ),
        (CURSO | {"nome": ""}, "Escreva o nome do curso.", "nome"),
        (
            CURSO | {"previsao": "12/2018"},
            "Datas no formato AAAA-MM, com o início antes do fim.",
            "previsao",
        ),
    ],
)
def test_item_errado_volta_com_o_texto_e_nao_grava(
    painel: Painel, dados: dict[str, Any], mensagem: str, campo: str
) -> None:
    resposta = painel.post(PERFIL, dados, sem_500=True)
    assert resposta.status_code == 422
    assert _alerta(resposta.text) == mensagem
    prefixo = "exp" if dados["secao"] == "experiencia" else "curso"
    campo_id = f"{prefixo}-nova-{campo}"
    assert _valor(resposta.text, campo_id) == dados[campo].strip()
    entrada = re.search(rf'<(?:input|textarea)\b[^>]*\bid="{campo_id}"[^>]*>', resposta.text)
    assert entrada is not None
    assert 'aria-invalid="true"' in entrada.group(0)
    assert "autofocus" in entrada.group(0)
    assert painel.sql("SELECT count(*) FROM experiencia") == [(0,)]
    assert painel.sql("SELECT count(*) FROM curso") == [(0,)]


def test_erro_ao_editar_volta_no_proprio_item(painel: Painel) -> None:
    assert _status(painel.post(PERFIL, EXPERIENCIA)) == SALVO["experiencia"]
    (exp,) = _experiencias(painel)
    resposta = painel.post(
        PERFIL, EXPERIENCIA | {"id": str(exp.id), "cargo": "", "empresa": "Nova"}
    )
    assert resposta.status_code == 422
    assert _valor(resposta.text, f"exp-{exp.id}-empresa") == "Nova"
    assert _valor(resposta.text, "exp-nova-empresa") == ""  # o formulário novo segue vazio
    assert _experiencias(painel) == [exp]


@pytest.mark.parametrize(("base", "tabela"), [(EXPERIENCIA, "experiencia"), (CURSO, "curso")])
def test_teto_de_dez_itens(painel: Painel, base: dict[str, Any], tabela: str) -> None:
    for _ in range(10):
        assert _status(painel.post(PERFIL, base)) == SALVO[base["secao"]]
    pagina = painel.get(PERFIL).text
    novo = "exp-nova-cargo" if tabela == "experiencia" else "curso-nova-nome"
    assert f'id="{novo}"' not in pagina  # sem o formulário de mais um
    resposta = painel.post(PERFIL, base)
    assert resposta.status_code == 422
    assert _alerta(resposta.text) == "Até 10 experiências e 10 cursos."
    # de outra aba, com um campo errado: o teto vem antes da conferência dos campos
    obrigatorio = "cargo" if tabela == "experiencia" else "nome"
    resposta = painel.post(PERFIL, base | {obrigatorio: ""})
    assert _alerta(resposta.text) == "Até 10 experiências e 10 cursos."
    assert painel.sql(f"SELECT count(*) FROM {tabela}") == [(10,)]


@pytest.mark.parametrize("base", [EXPERIENCIA, CURSO])
def test_editar_item_ja_tirado_da_404(painel: Painel, base: dict[str, Any]) -> None:
    assert _status(painel.post(PERFIL, base)) == SALVO[base["secao"]]
    tabela = "experiencia" if base is EXPERIENCIA else "curso"
    (id_,) = painel.sql(f"SELECT id FROM {tabela}")[0]
    painel.post(PERFIL, base | {"id": str(id_), "tirar": "1"})
    assert painel.post(PERFIL, base | {"id": str(id_)}).status_code == 404
    # com um campo errado também: o item que saiu vem antes da conferência dos campos
    obrigatorio = "cargo" if tabela == "experiencia" else "nome"
    assert painel.post(PERFIL, base | {"id": str(id_), obrigatorio: ""}).status_code == 404
    assert painel.sql(f"SELECT count(*) FROM {tabela}") == [(0,)]  # não volta
    # tirar de novo não quebra nada
    assert (
        _status(painel.post(PERFIL, base | {"id": str(id_), "tirar": "1"})) == SALVO[base["secao"]]
    )


@pytest.mark.parametrize(
    "troca",
    [
        {"id": "abc"},
        {"id": "0"},
        {"id": "9" * 19},
        {"id": " 1"},
        {"id": "", "tirar": "1"},
        {"situacao": "formado"},
    ],
)
def test_id_ou_lista_errados_dao_422(painel: Painel, troca: dict[str, Any]) -> None:
    base = CURSO if "situacao" in troca else EXPERIENCIA
    assert painel.post(PERFIL, base | troca, sem_500=True).status_code == 422
    assert painel.sql("SELECT count(*) FROM experiencia") == [(0,)]
    assert painel.sql("SELECT count(*) FROM curso") == [(0,)]


# ------------------------------------------------------------------ apagar tudo e CSRF


def _encher(painel: Painel) -> None:
    painel.post(PERFIL, {"habilidades": "Python"})
    painel.post(PERFIL, DADOS)
    painel.post(PERFIL, EXPERIENCIA)
    painel.post(PERFIL, CURSO)
    with closing(abrir(painel.banco)) as con:
        perfil.gravar_pergunta(con, "base:a3", "Qual o seu cargo?", "base", AGORA)
        vaga = inserir_vaga(con, titulo="Dev")
        con.execute(
            "INSERT INTO preparo_candidatura VALUES (?, 'pt', 'c', 'r', '[]', '[]', '[]', '[]',"
            " 'local', 'm', 1, ?)",
            (vaga, AGORA.isoformat()),
        )
        con.commit()


_PESSOAIS = ("perfil", "experiencia", "curso", "pergunta_perfil", "preparo_candidatura")


def test_apagar_perfil_apaga_tudo_e_a_tela_volta_vazia(painel: Painel) -> None:
    _encher(painel)
    contagens = [painel.sql(f"SELECT count(*) FROM {t}")[0][0] for t in _PESSOAIS]
    assert contagens == [1, 1, 1, 1, 1]  # controle: tudo estava lá
    assert _status(painel.post(APAGAR)) == (303, PERFIL + "?apagado=1")
    assert [painel.sql(f"SELECT count(*) FROM {t}")[0][0] for t in _PESSOAIS] == [0] * 5
    pagina = painel.get(PERFIL).text
    assert _valor(pagina, "perfil-nome") == ""
    assert "exp-1-cargo" not in pagina
    assert CONFIRMAR not in pagina


def test_confirmacao_de_apagar_diz_o_que_sai(painel: Painel) -> None:
    painel.post(PERFIL, {"habilidades": "Go"})
    texto = _texto(painel.get(CONFIRMAR).text)
    assert (
        "Seus dados, idiomas, habilidades, experiências, cursos, respostas e candidaturas"
        " preparadas saem do joBot. O que a IA já leu das vagas continua."
    ) in texto


def test_salvar_tudo_em_branco_nao_mostra_apagar(painel: Painel) -> None:
    vazio = {c: "" for c in DADOS} | {"secao": "dados", "outro_nome": "", "outro_nivel": ""}
    assert _status(painel.post(PERFIL, vazio)) == SALVO["dados"]
    assert _status(painel.post(PERFIL, {"habilidades": ""})) == SALVO[None]
    assert CONFIRMAR not in painel.get(PERFIL).text  # nada para apagar
    painel.post(PERFIL, {"habilidades": "Go"})
    assert CONFIRMAR in painel.get(PERFIL).text  # controle


def test_pagina_do_perfil_nao_fica_no_cache(painel: Painel) -> None:
    painel.post(PERFIL, DADOS)
    assert painel.get(PERFIL).headers.get("cache-control") == "no-store"
    resposta = painel.post(PERFIL, DADOS | {"anos_de_experiencia": "99"})
    assert resposta.status_code == 422
    assert resposta.headers.get("cache-control") == "no-store"
    assert "no-store" not in painel.get("/configuracoes/geral").headers.get("cache-control", "")


def test_explicacao_diz_que_cada_parte_salva_e_o_que_nao_vai_a_ia(painel: Painel) -> None:
    pagina = _texto(painel.get(PERFIL).text)
    assert "Cada parte tem o seu Salvar." in pagina
    assert "O joBot não põe estes campos nos pedidos à IA." in pagina
    assert "nunca vai para a IA" not in pagina
    painel.idioma("en")
    pagina = _texto(painel.get(PERFIL).text)
    assert "Each part has its own Save." in pagina
    assert "joBot does not put these fields in requests to AI." in pagina


@pytest.mark.parametrize("base", [DADOS, EXPERIENCIA, CURSO])
def test_apagar_aparece_com_qualquer_parte_do_perfil(painel: Painel, base: dict[str, Any]) -> None:
    assert CONFIRMAR not in painel.get(PERFIL).text
    painel.post(PERFIL, base)
    assert CONFIRMAR in painel.get(PERFIL).text


@pytest.mark.parametrize(
    ("dados", "tabela"),
    [(DADOS, "perfil"), (EXPERIENCIA, "experiencia"), (CURSO, "curso")],
)
def test_secao_sem_csrf_e_recusada(painel: Painel, dados: dict[str, Any], tabela: str) -> None:
    assert painel.post(PERFIL, dados, csrf=False).status_code == 403
    assert painel.sql(f"SELECT count(*) FROM {tabela}") == [(0,)]
    assert _status(painel.post(PERFIL, dados)) == SALVO[dados["secao"]]  # controle
    assert painel.sql(f"SELECT count(*) FROM {tabela}") == [(1,)]
    if tabela != "perfil":
        (id_,) = painel.sql(f"SELECT id FROM {tabela}")[0]
        tirar = dados | {"id": str(id_), "tirar": "1"}
        assert painel.post(PERFIL, tirar, csrf=False).status_code == 403
        assert painel.sql(f"SELECT count(*) FROM {tabela}") == [(1,)]


def test_perfil_completo_em_ingles(painel: Painel) -> None:
    painel.idioma("en")
    painel.post(PERFIL, EXPERIENCIA)
    pagina = _texto(painel.get(PERFIL).text)
    for frase in ("About you", "Contact", "Languages", "Experience", "Courses", "Job title"):
        assert frase in pagina
    assert "Sobre você" not in pagina
    resposta = painel.post(PERFIL, DADOS | {"anos_de_experiencia": "99"})
    assert _alerta(resposta.text) == "Years of experience: a number from 0 to 60."
