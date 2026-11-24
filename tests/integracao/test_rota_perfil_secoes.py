"""Cada seção da aba Perfil salva sozinha (D230, decidido pelo dono em 2026-11-24).

Com HTMX, o Salvar de uma seção troca só a própria seção (`hx-select` dela), e o que foi digitado
nas outras fica na tela; o "Salvo." e o alerta do erro moram dentro da seção, para a troca os
trazer. Sem JavaScript, o formulário comum recarrega a página, e a aba avisa antes disso.
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
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47619
PERFIL = "/configuracoes/perfil"
SECOES = ("sobre", "habilidades", "experiencias", "cursos")
DADOS = {
    "secao": "dados",
    "nome": "",
    "email": "",
    "telefone": "",
    "cidade_moradia": "",
    "cargo_atual": "",
    "anos_de_experiencia": "",
    "formacao_nivel": "",
    "resumo": "",
    "links": "",
    "idioma_pt": "",
    "idioma_en": "",
    "idioma_es": "",
}


class Http(TestClient):
    """O cliente do app com o token CSRF e o banco à mão."""

    token: str
    banco: Path

    def gravar(self, dados: dict[str, Any]) -> Any:
        return self.post(PERFIL, data={CAMPO_CSRF: self.token} | dados)

    def idioma(self, idioma: str) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.gravar_config(con, "idioma", idioma)


@pytest.fixture
def http(tmp_path: Path) -> Http:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        cadastros.semear(con)
    app = criar_app(tmp_path, PORTA)
    app.state.relogio = RelogioFalso()
    cliente = Http(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)
    cliente.token, cliente.banco = app.state.csrf, banco
    return cliente


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", html)))


def pt(chave: str) -> str:
    return i18n.carregar()["pt"][chave]


def _fora_das_secoes(html: str) -> str:
    """A página sem as seções que trocam sozinhas: o que sobra é o alto da aba."""
    arvore = LexborHTMLParser(html)
    for secao in arvore.css("section[id^='bloco-']"):
        secao.decompose()
    conteudo = arvore.css_first(".config-conteudo")
    assert conteudo is not None
    return _texto(conteudo.html or "")


def test_cada_secao_troca_so_a_si_mesma(http: Http) -> None:
    arvore = LexborHTMLParser(http.get(PERFIL).text)
    for nome in SECOES:
        secao = arvore.css_first(f"section#bloco-{nome}")
        assert secao is not None, nome
        atributos = secao.attributes
        assert atributos.get("hx-select") == f"#bloco-{nome}", nome
        assert (atributos.get("hx-target"), atributos.get("hx-swap")) == ("this", "outerHTML")
        assert "data-troca-422" in atributos, nome
        formularios = secao.css("form")
        assert formularios, nome
        for form in formularios:  # sem JavaScript, o mesmo formulário posta igual
            assert form.attributes.get("hx-post") == form.attributes.get("action") == PERFIL


@pytest.mark.parametrize(
    ("secao", "dados", "ancora"),
    [
        (None, {"habilidades": "Python"}, "habilidades"),
        ("dados", DADOS | {"nome": "Ana"}, "sobre"),
        (
            "experiencia",
            {
                "secao": "experiencia",
                "id": "",
                "cargo": "Analista",
                "empresa": "",
                "inicio": "",
                "fim": "",
                "descricao": "",
            },
            "experiencias",
        ),
        (
            "curso",
            {
                "secao": "curso",
                "id": "",
                "nome": "ADS",
                "instituicao": "",
                "situacao": "",
                "previsao": "",
            },
            "cursos",
        ),
    ],
)
def test_salvo_aparece_dentro_da_secao_que_gravou(
    http: Http, secao: str | None, dados: dict[str, str], ancora: str
) -> None:
    resposta = http.gravar(dados)
    destino = f"{PERFIL}?salvo={ancora}#perfil-{ancora}"
    assert (resposta.status_code, resposta.headers.get("location")) == (303, destino)
    html = http.get(destino.split("#")[0]).text
    gravou = LexborHTMLParser(html).css_first(f"#bloco-{ancora}")
    assert gravou is not None
    salvo = gravou.css_first("[role=status]")
    assert salvo is not None and _texto(salvo.html or "").strip() == pt("configuracoes.salvo")
    assert pt("configuracoes.salvo") not in _fora_das_secoes(html)
    for outra in set(SECOES) - {ancora}:  # só na que gravou
        no = LexborHTMLParser(html).css_first(f"#bloco-{outra}")
        assert no is not None and no.css_first("[role=status]") is None, outra


@pytest.mark.parametrize(
    ("dados", "ancora", "campo"),
    [
        (DADOS | {"email": "sem-arroba"}, "sobre", "perfil-email"),
        ({"habilidades": "x" * 101}, "habilidades", "campo-habilidades"),
        (
            {
                "secao": "experiencia",
                "id": "",
                "cargo": "Analista",
                "empresa": "",
                "inicio": "2020-13",
                "fim": "",
                "descricao": "",
            },
            "experiencias",
            "exp-nova-inicio",
        ),
    ],
)
def test_erro_aparece_dentro_da_secao_com_o_campo_marcado(
    http: Http, dados: dict[str, str], ancora: str, campo: str
) -> None:
    resposta = http.gravar(dados)
    assert resposta.status_code == 422
    secao = LexborHTMLParser(resposta.text).css_first(f"#bloco-{ancora}")
    assert secao is not None
    alerta = secao.css_first("#config-erro")
    assert alerta is not None and alerta.attributes.get("role") == "alert"
    marcado = secao.css_first(f"#{campo}")
    assert marcado is not None and marcado.attributes.get("aria-invalid") == "true"
    assert "config-erro" in (marcado.attributes.get("aria-describedby") or "").split()
    assert len(LexborHTMLParser(resposta.text).css("#config-erro")) == 1  # nada no alto


def test_curriculo_segue_com_o_salvo_no_alto(http: Http) -> None:
    """A revisão do currículo grava várias seções e recarrega a página: o aviso fica no alto."""
    html = http.get(PERFIL + "?salvo=1").text
    assert pt("configuracoes.salvo") in _fora_das_secoes(html)


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_sem_javascript_a_aba_avisa_que_salvar_recarrega(http: Http, idioma: str) -> None:
    http.idioma(idioma)
    html = http.get(PERFIL).text
    aviso = LexborHTMLParser(html).css_first("noscript#perfil-sem-js")
    assert aviso is not None
    assert i18n.carregar()[idioma]["configuracoes.perfil.sem_js"] in _texto(aviso.html or "")
