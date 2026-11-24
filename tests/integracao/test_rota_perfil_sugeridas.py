"""Perguntas sugeridas na aba Perfil (D234, decidido pelo dono em 2026-11-24).

A pergunta que a IA sugere ao preparar uma candidatura fica "sugerida" até a pessoa aceitar ou
descartar na aba Perfil (formulário comum, com CSRF, sem JavaScript). Só a aceita entra no
questionário, e só a aceita e respondida vai nos pedidos à IA.
"""

import html as html_lib
import re
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from selectolax.lexbor import LexborHTMLParser

from apoio.relogio import RelogioFalso
from jobot.banco import cadastros, perfil
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.rotas.perfil import TETO_PERGUNTAS
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47619
PERFIL = "/configuracoes/perfil"
PERGUNTAS = PERFIL + "/perguntas"
SALVO = (303, f"{PERFIL}?salvo=sugeridas#perfil-sugeridas")
K8S = "Há quanto tempo você usa Kubernetes?"


class Painel:
    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            cadastros.semear(con)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso()
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

    def con(self) -> Any:
        return closing(abrir(self.banco))

    def pergunta(self, chave: str, texto: str, *, sugerida: bool) -> None:
        with self.con() as con:
            agora = RelogioFalso().agora()
            perfil.gravar_pergunta(con, chave, texto, "ia", agora, sugerida=sugerida)

    def decidir(self, chave: str, acao: str, *, csrf: bool = True) -> Any:
        dados = {"secao": "sugerida", "chave": chave, "acao": acao}
        token = {CAMPO_CSRF: self.token} if csrf else {}
        return self.http.post(PERFIL, data=token | dados)

    def chaves(self, sugeridas: bool = False) -> list[str]:
        with self.con() as con:
            return [p.chave for p in perfil.perguntas(con, sugeridas=sugeridas)]


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", html)))


def _secao(html: str) -> Any:
    return LexborHTMLParser(html).css_first("#bloco-sugeridas")


def pt(chave: str) -> str:
    return i18n.carregar()["pt"][chave]


def test_sugerida_aparece_com_aceitar_e_descartar(painel: Painel) -> None:
    painel.pergunta("ia:k8s", K8S, sugerida=True)
    secao = _secao(painel.http.get(PERFIL).text)
    assert secao is not None
    assert secao.css_first("h2").text().strip() == pt("configuracoes.perfil.sugeridas.titulo")
    form = secao.css_first("form")
    assert (form.attributes["method"], form.attributes["action"]) == ("post", PERFIL)
    ocultos = {i.attributes["name"]: i.attributes["value"] for i in form.css("input[type=hidden]")}
    assert ocultos == {CAMPO_CSRF: painel.token, "secao": "sugerida", "chave": "ia:k8s"}
    botoes = {b.attributes["value"]: b.attributes["aria-label"] for b in form.css("button")}
    # o nome acessível começa pelo texto visível e diz qual pergunta (D230.2)
    assert botoes == {
        "aceitar": f"{pt('configuracoes.perfil.sugeridas.aceitar')}: {K8S}",
        "descartar": f"{pt('configuracoes.perfil.sugeridas.descartar')}: {K8S}",
    }
    assert K8S in _texto(secao.html)


def test_sem_sugerida_a_secao_nao_aparece(painel: Painel) -> None:
    assert _secao(painel.http.get(PERFIL).text) is None
    painel.pergunta("ia:bi", "Usa BI?", sugerida=False)  # a aceita mora no questionário
    assert _secao(painel.http.get(PERFIL).text) is None


def test_aceitar_leva_ao_questionario(painel: Painel) -> None:
    painel.pergunta("ia:k8s", K8S, sugerida=True)
    assert K8S not in painel.http.get(PERGUNTAS).text  # controle: antes do aceite, fora
    resposta = painel.decidir("ia:k8s", "aceitar")
    assert (resposta.status_code, resposta.headers.get("location")) == SALVO
    assert painel.chaves() == ["ia:k8s"] and painel.chaves(sugeridas=True) == []
    assert K8S in painel.http.get(PERGUNTAS).text
    # a seção fica, com o "Salvo." dentro dela, para a troca do HTMX mostrar (D230)
    secao = _secao(painel.http.get(SALVO[1].split("#")[0]).text)
    assert secao is not None and pt("configuracoes.salvo") in _texto(secao.html)


def test_descartar_apaga(painel: Painel) -> None:
    painel.pergunta("ia:k8s", K8S, sugerida=True)
    resposta = painel.decidir("ia:k8s", "descartar")
    assert (resposta.status_code, resposta.headers.get("location")) == SALVO
    assert painel.chaves() == [] and painel.chaves(sugeridas=True) == []


def test_descartar_nao_tira_a_aceita(painel: Painel) -> None:
    painel.pergunta("ia:bi", "Usa BI?", sugerida=False)
    assert painel.decidir("ia:bi", "descartar").status_code == 303
    assert painel.chaves() == ["ia:bi"]


def test_acao_desconhecida_e_422_e_nada_muda(painel: Painel) -> None:
    painel.pergunta("ia:k8s", K8S, sugerida=True)
    assert painel.decidir("ia:k8s", "responder").status_code == 422
    assert painel.chaves(sugeridas=True) == ["ia:k8s"]


def test_sem_csrf_nada_muda(painel: Painel) -> None:
    painel.pergunta("ia:k8s", K8S, sugerida=True)
    assert painel.decidir("ia:k8s", "aceitar", csrf=False).status_code == 403
    assert painel.chaves(sugeridas=True) == ["ia:k8s"]
    assert painel.decidir("ia:k8s", "aceitar").status_code == 303  # controle


def test_responder_a_sugerida_pelo_questionario_nao_grava(painel: Painel) -> None:
    """Um formulário montado à mão não responde a pergunta que ninguém aceitou."""
    painel.pergunta("ia:k8s", K8S, sugerida=True)
    painel.pergunta("ia:bi", "Usa BI?", sugerida=False)
    campos = ("nome", "email", "telefone", "links", "cidade_moradia", "cargo_atual")
    vazios = dict.fromkeys(
        (*campos, "anos_de_experiencia", "formacao_nivel", "idioma_pt", "idioma_en", "idioma_es"),
        "",
    )
    dados = vazios | {
        CAMPO_CSRF: painel.token,
        "habilidades": "",
        "pergunta_chave": ["ia:k8s", "ia:bi"],
        "pergunta_resposta": ["Cinco anos", "Sim"],
    }
    assert painel.http.post(PERGUNTAS, data=dados).status_code == 303
    with painel.con() as con:
        respostas = dict(con.execute("SELECT chave, resposta FROM pergunta_perfil"))
    assert respostas == {"ia:k8s": None, "ia:bi": "Sim"}


def test_aceitar_no_teto_recusa_na_secao(painel: Painel) -> None:
    """Com o questionário no teto (D233.5), a aceita não caberia na tela e não seria respondida."""
    for n in range(TETO_PERGUNTAS):
        painel.pergunta(f"ia:{n}", f"Pergunta {n}?", sugerida=False)
    painel.pergunta("ia:k8s", K8S, sugerida=True)
    resposta = painel.decidir("ia:k8s", "aceitar")
    assert resposta.status_code == 422
    secao = _secao(resposta.text)
    assert secao is not None
    alerta = secao.css_first("#config-erro")
    assert alerta is not None and alerta.attributes.get("role") == "alert"
    assert pt("configuracoes.perfil.sugeridas.cheio") in _texto(alerta.html or "")
    assert painel.chaves(sugeridas=True) == ["ia:k8s"]
    assert len(painel.chaves()) == TETO_PERGUNTAS
    assert painel.decidir("ia:k8s", "descartar").status_code == 303  # descartar segue livre
    assert painel.chaves(sugeridas=True) == []
