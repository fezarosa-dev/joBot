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
from jobot.banco import cadastros
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
        self.token: str = self.app.state.csrf

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def get(self, url: str) -> Any:
        return self.http.get(url)

    def post(self, url: str, dados: dict[str, Any] | None = None, *, csrf: bool = True) -> Any:
        token = {CAMPO_CSRF: self.token} if csrf else {}
        return self.http.post(url, data=token | (dados or {}))

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
    # um botão principal só: o Salvar
    assert len(re.findall(r'class="[^"]*botao-primario', _sem_paleta(resposta.text))) == 1


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
    assert _status(resposta) == (303, PERFIL + "?salvo=1")
    gravadas = ["Python", "PostgreSQL", "Machine Learning", "Docker", "C++", ".NET", "React"]
    assert painel.habilidades() == gravadas
    pagina = painel.get(PERFIL + "?salvo=1").text
    assert _campo(pagina) == "\n".join(gravadas)
    assert "Salvo." in _texto(pagina)


def test_campo_vazio_grava_lista_vazia(painel: Painel) -> None:
    painel.post(PERFIL, {"habilidades": "Go"})
    assert painel.habilidades() == ["Go"]  # controle
    assert _status(painel.post(PERFIL, {"habilidades": " \n \n"})) == (303, PERFIL + "?salvo=1")
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
        assert _status(resposta) == (303, PERFIL + "?salvo=1")
        assert painel.habilidades() == texto.split("\n")
        return
    assert resposta.status_code == 422
    alerta = re.search(r'role="alert"[^>]*>(.*?)</div>', resposta.text, re.S)
    assert alerta is not None
    assert "Até 200 habilidades, cada uma com até 100 caracteres." in _texto(alerta.group(1))
    assert _campo(resposta.text) == texto  # o que foi digitado volta para corrigir
    assert painel.habilidades() == ["Rust"]
    # o campo aponta para a mensagem do erro, não só para a ajuda
    caixa = re.search(r"<textarea[^>]*>", resposta.text)
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
    assert _status(painel.post(PERFIL, {"habilidades": "go\npython\n"})) == (
        303,
        PERFIL + "?salvo=1",
    )
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
            "Suas habilidades ficam no seu computador. A IA está desligada: nada sai dele.",
        ),
        (
            "pt",
            {"ligada": False, "backend": "anthropic", "modelo": "m"},
            "Suas habilidades ficam no seu computador. A IA está desligada: nada sai dele.",
        ),
        (
            "pt",
            {"ligada": True, "backend": "local", "modelo": "qwen"},
            "Suas habilidades ficam no seu computador, e o texto da vaga também: "
            "o encaixe usa o modelo local.",
        ),
        (
            "pt",
            {"ligada": True, "backend": "anthropic", "modelo": "m"},
            "Suas habilidades ficam no seu computador; só o texto da vaga vai para "
            "a API da Anthropic.",
        ),
        (
            "pt",
            {"ligada": True, "backend": "compativel", "modelo": "m"},
            "Suas habilidades ficam no seu computador; só o texto da vaga vai para "
            "o serviço compatível com a OpenAI.",
        ),
        (
            "pt",
            {"ligada": True, "backend": "xyz", "modelo": "m"},
            "Suas habilidades ficam no seu computador; só o texto da vaga vai para "
            "um serviço de fora.",
        ),
        ("en", None, "Your skills stay on your computer. AI is off: nothing leaves it."),
        (
            "en",
            {"ligada": True, "backend": "local", "modelo": "qwen"},
            "Your skills stay on your computer, and so does the job text: "
            "matching uses the local model.",
        ),
        (
            "en",
            {"ligada": True, "backend": "gemini", "modelo": "m"},
            "Your skills stay on your computer; only the job text goes to Google Gemini.",
        ),
    ],
)
def test_frase_de_privacidade(painel: Painel, idioma: str, tarefa: object, frase: str) -> None:
    painel.idioma(idioma)
    if tarefa is not None:
        painel.tarefa(tarefa)
    assert frase in _texto(painel.get(PERFIL).text)


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
