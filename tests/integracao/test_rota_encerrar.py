"""Encerrar pelo painel (plano T333; desenho 6.4): Configurações › Geral, paleta e alerta."""

import re
from contextlib import closing
from html import unescape
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.i18n import t

PORTA = 47633
BASE = f"http://127.0.0.1:{PORTA}"
ALERTA = re.compile(r'<dialog id="alerta-encerrar".*?</dialog>', re.S)
PALETA = re.compile(r'<dialog\b[^>]*\bid="paleta".*?</dialog>', re.S)
FORM = re.compile(r"<form\b([^>]*)>(.*?)</form>", re.S)


@pytest.fixture
def app(tmp_path: Path) -> SimpleNamespace:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        gravar_config(con, "primeira_execucao_concluida", True)
    painel = criar_app(tmp_path, PORTA)
    painel.state.servidor = SimpleNamespace(should_exit=False)
    http = TestClient(painel, base_url=BASE, follow_redirects=False)
    return SimpleNamespace(app=painel, http=http, token=painel.state.csrf)


def _form_que_abre_o_alerta(html: str) -> tuple[str, str]:
    """O GET para a confirmação cujo botão abre o alerta (sem JavaScript, leva à página)."""
    achados = [
        (attrs, miolo)
        for attrs, miolo in FORM.findall(html)
        if 'data-alerta-abre="alerta-encerrar"' in miolo
    ]
    assert len(achados) == 1, achados
    return achados[0]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_geral_tem_encerrar_que_abre_o_alerta(app: SimpleNamespace, idioma: str) -> None:
    html = app.http.get("/configuracoes/geral", headers={"Accept-Language": idioma}).text
    attrs, miolo = _form_que_abre_o_alerta(PALETA.sub("", html))
    assert 'method="get"' in attrs and 'action="/sair/confirmar"' in attrs
    assert 'name="voltar" value="/configuracoes/geral"' in miolo
    botao = re.search(r"<button\b[^>]*>(.*?)</button>", miolo, re.S)
    assert botao and unescape(botao.group(1)).strip() == t(idioma, "execucao.encerrar")
    assert 'type="submit"' in botao.group(0) and "botao-primario" not in botao.group(0)


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_alerta_pergunta_e_envia_o_post_de_sair(app: SimpleNamespace, idioma: str) -> None:
    html = app.http.get("/configuracoes/geral", headers={"Accept-Language": idioma}).text
    alerta = ALERTA.search(html)
    assert alerta, "falta o alerta de encerrar"
    corpo = unescape(alerta.group(0))
    assert 'role="alertdialog"' in corpo and "data-alerta" in corpo
    assert t(idioma, "execucao.encerrar.pergunta") in corpo
    assert t(idioma, "execucao.encerrar.explicacao") in corpo
    assert 'method="post" action="/sair"' in corpo
    assert f'name="csrf_token" value="{app.token}"' in corpo
    assert re.search(rf'<button type="submit">\s*{t(idioma, "comum.encerrar")}\s*</button>', corpo)
    assert "data-alerta-fecha" in corpo


def test_textos_do_desenho(app: SimpleNamespace) -> None:
    assert t("pt", "execucao.encerrar") == "Encerrar o joBot"
    assert t("pt", "execucao.encerrar.pergunta") == "Encerrar o joBot?"
    assert t("pt", "execucao.encerrar.explicacao") == (
        "As buscas param até você abrir o joBot de novo."
    )
    assert t("pt", "execucao.saiu") == "O joBot foi encerrado. Pode fechar esta janela."


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_paleta_tem_encerrar_que_abre_o_alerta(app: SimpleNamespace, idioma: str) -> None:
    html = app.http.get("/vagas", headers={"Accept-Language": idioma}).text
    paleta = PALETA.search(html)
    assert paleta
    attrs, miolo = _form_que_abre_o_alerta(paleta.group(0))
    assert 'method="get"' in attrs and 'action="/sair/confirmar"' in attrs
    assert 'name="voltar" value="/vagas"' in miolo
    assert 'role="option"' in miolo and 'type="submit"' in miolo
    assert t(idioma, "execucao.encerrar") in unescape(miolo)
    # o POST direto mora só no alerta: a paleta não encerra sem perguntar
    assert 'action="/sair"' not in paleta.group(0)
    assert ALERTA.search(html)  # o alerta vem junto da paleta, em toda página com ela


def test_confirmacao_sem_javascript(app: SimpleNamespace) -> None:
    resposta = app.http.get("/sair/confirmar?voltar=/buscas")
    assert resposta.status_code == 200
    pagina = unescape(resposta.text)
    assert t("pt", "execucao.encerrar.pergunta") in pagina
    assert t("pt", "execucao.encerrar.explicacao") in pagina
    secao = re.search(r'<section class="confirmar".*?</section>', pagina, re.S)
    assert secao
    ((attrs, post),) = FORM.findall(secao.group(0))
    assert 'method="post" action="/sair"' in attrs
    assert f'name="csrf_token" value="{app.token}"' in post
    assert re.search(r'<button[^>]*type="submit"[^>]*>\s*Encerrar\s*</button>', post)
    assert re.search(r'<a\b[^>]*href="/buscas"[^>]*>\s*Cancelar\s*</a>', secao.group(0))
    assert app.app.state.servidor.should_exit is False  # o GET não encerra


def test_confirmacao_nao_volta_para_fora_do_painel(app: SimpleNamespace) -> None:
    pagina = app.http.get("/sair/confirmar?voltar=//exemplo.com/x").text
    cancelar = re.search(r'<a\b[^>]*class="confirmar-cancelar"[^>]*>', pagina)
    assert cancelar and 'href="/"' in cancelar.group(0)


def test_despedida_encerra(app: SimpleNamespace) -> None:
    resposta = app.http.post("/sair", data={"csrf_token": app.token})
    assert resposta.status_code == 200
    assert app.app.state.servidor.should_exit is True
    assert t("pt", "execucao.saiu") in unescape(resposta.text)
    assert 'id="alerta-encerrar"' not in resposta.text  # sem lateral, sem paleta e sem alerta
