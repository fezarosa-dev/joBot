"""Atualizar pelo painel (plano T332; desenho 5.6 e 6.3; ADR 0023; D176).

A faixa `#aviso-versao` não manda mais abrir o terminal: traz "Atualizar agora", que dispara o
`jobot atualizar` destacado (`app.state.lancar_atualizacao`, falso aqui), e, na casca com a janela
mais velha que a versão nova, "Baixar a janela nova" (`app.state.abrir_endereco`, falso aqui).
Nada roda de verdade e nada vai à rede.
"""

import html
import logging
import re
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from jobot import __version__
from jobot.banco import cadastros
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47629
BASE = f"http://127.0.0.1:{PORTA}"
HTMX = {"HX-Request": "true", "HX-Current-URL": f"{BASE}/vagas?ordem=nova"}
RELEASE = "https://github.com/fezarosa-dev/joBot/releases/latest"
SEGREDO = "segredo-do-erro-31337"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko)"


def _texto(idioma: str, chave: str, **params: str) -> str:
    """A frase do catálogo, escapada como o Jinja a põe na página."""
    return html.escape(i18n.carregar()[idioma][chave].format(**params))


class Rodando:
    """O `Popen` falso: `poll()` diz se o `jobot atualizar` ainda roda."""

    def __init__(self) -> None:
        self.codigo: int | None = None

    def poll(self) -> int | None:
        return self.codigo


class Painel:
    def __init__(self, tmp_path: Path) -> None:
        self.dados = tmp_path
        banco = tmp_path / "jobot.db"
        with closing(abrir(banco)) as con:
            migrar(con, banco)
            cadastros.semear(con)
            gravar_config(con, "idioma", "pt")
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.ambiente = {"PATH": "/usr/bin", "HOME": "/casa"}
        self.lancados: list[tuple[Path, dict[str, str]]] = []
        self.processos: list[Rodando] = []
        self.falha: Exception | None = None
        self.abertos: list[str] = []
        self.abre = True

        def lancar(dados: Path, ambiente: Mapping[str, str]) -> Rodando:
            if self.falha is not None:
                raise self.falha
            self.lancados.append((dados, dict(ambiente)))
            self.processos.append(Rodando())
            return self.processos[-1]

        def abrir_endereco(endereco: str) -> bool:
            self.abertos.append(endereco)
            return self.abre

        self.app.state.lancar_atualizacao = lancar
        self.app.state.abrir_endereco = abrir_endereco
        self.cliente = TestClient(self.app, base_url=BASE, follow_redirects=False)

    def config(self, chave: str, valor: object) -> None:
        with closing(abrir(self.dados / "jobot.db")) as con:
            gravar_config(con, chave, valor)

    def post(
        self, caminho: str, dados: dict[str, str] | None = None, *, htmx: bool = True
    ) -> httpx.Response:
        cabecalhos = HTMX if htmx else {}
        corpo = {CAMPO_CSRF: str(self.app.state.csrf), **(dados or {})}
        resposta: httpx.Response = self.cliente.post(caminho, data=corpo, headers=cabecalhos)
        return resposta


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    p = Painel(tmp_path)
    p.config("aviso_versao_ligada", True)
    p.config("versao_nova", "v99.0.0")
    return p


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_faixa_tem_atualizar_agora_e_nao_fala_em_terminal(painel: Painel, idioma: str) -> None:
    painel.config("idioma", idioma)
    texto = painel.cliente.get("/aviso-versao").text
    assert _texto(idioma, "aviso_versao.texto", versao="v99.0.0") in texto
    assert 'action="/atualizar"' in texto and 'hx-post="/atualizar"' in texto
    assert _texto(idioma, "aviso_versao.atualizar") in texto
    assert "terminal" not in texto.lower()
    assert "jobot atualizar" not in texto
    # fora da casca, nada da janela nova
    assert "/abrir-release" not in texto


def test_post_atualizar_dispara_o_jobot_atualizar_e_responde_o_progresso(painel: Painel) -> None:
    resposta = painel.post("/atualizar")
    assert resposta.status_code == 200
    assert len(painel.lancados) == 1
    dados, ambiente = painel.lancados[0]
    assert dados == painel.dados
    assert ambiente == {"PATH": "/usr/bin", "HOME": "/casa"}
    assert "<html" not in resposta.text  # fragmento do HTMX
    assert f'data-de="{__version__}"' in resposta.text
    assert "data-atualizando" in resposta.text
    assert 'role="progressbar"' in resposta.text
    assert "aria-valuenow" not in resposta.text  # progresso indeterminado
    assert _texto("pt", "aviso_versao.atualizando") in resposta.text
    # a explicação dos 120 s já vem, escondida, com o "Tentar de novo"
    assert re.search(r"<div data-atualizar-demorou hidden>", resposta.text)
    assert _texto("pt", "aviso_versao.tentar") in resposta.text


def test_segundo_post_com_a_atualizacao_rodando_nao_dispara_outra(painel: Painel) -> None:
    painel.post("/atualizar")
    segunda = painel.post("/atualizar")
    assert segunda.status_code == 200
    assert "data-atualizando" in segunda.text
    assert len(painel.lancados) == 1
    painel.processos[0].codigo = 1  # terminou (falhou e religou a de antes): tentar de novo vale
    painel.post("/atualizar")
    assert len(painel.lancados) == 2


def test_atualizar_marca_rodando_antes_de_lancar(painel: Painel) -> None:
    """Revisão da T332: dois POSTs quase juntos (faixa e Geral, clique duplo) não disparam dois
    `jobot atualizar`: a marca de rodando entra antes do lançamento, não depois."""
    vistos: list[int | None] = []
    lancar = painel.app.state.lancar_atualizacao

    def espiar(dados: Path, ambiente: Mapping[str, str]) -> Rodando:
        vistos.append(painel.app.state.atualizacao.poll())
        return lancar(dados, ambiente)

    painel.app.state.lancar_atualizacao = espiar
    painel.post("/atualizar")
    assert vistos == [None]
    # o lançamento que falha tira a marca: "Tentar de novo" dispara outra vez
    painel.processos[0].codigo = 0
    painel.falha = OSError("sem python")
    painel.post("/atualizar")
    assert painel.app.state.atualizacao is None
    painel.falha = None
    painel.post("/atualizar")
    assert len(painel.lancados) == 2


def test_post_atualizar_sem_csrf_recusa_e_nao_dispara(painel: Painel) -> None:
    resposta = painel.cliente.post("/atualizar", headers=HTMX)
    assert resposta.status_code == 403
    assert painel.lancados == []


def test_sem_htmx_vai_para_atualizando_com_refresh_de_5_s(painel: Painel) -> None:
    resposta = painel.post("/atualizar", htmx=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/atualizando?de={__version__}"
    assert len(painel.lancados) == 1
    pagina = painel.cliente.get(resposta.headers["location"])
    assert pagina.status_code == 200
    refresh = f'<meta http-equiv="refresh" content="5;url=/atualizando?de={__version__}">'
    assert refresh in pagina.text
    assert _texto("pt", "aviso_versao.atualizando_titulo") in pagina.text
    assert _texto("pt", "aviso_versao.sem_js") in pagina.text


def test_atualizando_com_a_versao_nova_no_ar_volta_ao_painel(painel: Painel) -> None:
    resposta = painel.cliente.get("/atualizando", params={"de": "0.0.1"})
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"
    # versão de antes igual à de agora: segue esperando
    igual = painel.cliente.get("/atualizando", params={"de": __version__})
    assert igual.status_code == 200
    assert 'http-equiv="refresh"' in igual.text
    # `de` que não é versão não vira redirect nem vai para a página
    lixo = painel.cliente.get("/atualizando", params={"de": "<b>x</b>"})
    assert lixo.status_code == 200
    assert "<b>x</b>" not in lixo.text
    assert f"/atualizando?de={__version__}" in lixo.text


def test_atualizacao_que_nao_comeca_avisa_sem_vazar_o_erro(
    painel: Painel, caplog: pytest.LogCaptureFixture
) -> None:
    painel.falha = OSError(SEGREDO)
    with caplog.at_level(logging.WARNING, logger="jobot"):
        resposta = painel.post("/atualizar")
    assert resposta.status_code == 200
    assert _texto("pt", "aviso_versao.nao_comecou") in resposta.text
    assert "data-atualizando" not in resposta.text
    assert 'action="/atualizar"' in resposta.text  # tentar de novo
    assert SEGREDO not in resposta.text
    assert sum(SEGREDO in (r.exc_text or "") for r in caplog.records) == 1
    # sem HTMX: a página diz o mesmo e não fica recarregando
    sem_js = painel.post("/atualizar", htmx=False)
    assert sem_js.status_code == 303
    assert sem_js.headers["location"] == "/atualizando?erro=nao_comecou"
    assert SEGREDO not in sem_js.headers["location"]
    pagina = painel.cliente.get(sem_js.headers["location"])
    assert _texto("pt", "aviso_versao.nao_comecou") in pagina.text
    assert 'http-equiv="refresh"' not in pagina.text


def test_geral_mostra_a_versao_atual_e_a_ultima_conhecida(painel: Painel) -> None:
    pagina = painel.cliente.get("/configuracoes/geral").text
    assert _texto("pt", "configuracoes.geral.versao.titulo") in pagina
    assert _texto("pt", "configuracoes.geral.versao.atual", versao=__version__) in pagina
    assert _texto("pt", "configuracoes.geral.versao.ultima", versao="v99.0.0") in pagina
    corpo = pagina.split('id="conteudo"', 1)[1]  # fora da faixa, que é da casca
    assert 'action="/atualizar"' in corpo


def test_geral_sem_versao_nova_nao_oferece_atualizar(painel: Painel) -> None:
    painel.config("versao_nova", "v0.0.1")
    pagina = painel.cliente.get("/configuracoes/geral").text
    assert _texto("pt", "configuracoes.geral.versao.ultima", versao="v0.0.1") in pagina
    assert _texto("pt", "configuracoes.geral.versao.em_dia") in pagina
    assert 'action="/atualizar"' not in pagina


def test_geral_sem_checagem_diz_que_nao_conferiu(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    painel.config("idioma", "en")
    pagina = painel.cliente.get("/configuracoes/geral").text
    assert _texto("en", "configuracoes.geral.versao.atual", versao=__version__) in pagina
    assert _texto("en", "configuracoes.geral.versao.nao_conferida") in pagina
    assert 'action="/atualizar"' not in pagina


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_casca_mais_velha_traz_baixar_a_janela_nova(painel: Painel, idioma: str) -> None:
    painel.config("idioma", idioma)
    velha = painel.cliente.get(
        "/aviso-versao", headers={"User-Agent": f"{UA} joBot-casca/0.4.0 (linux)"}
    )
    assert _texto(idioma, "aviso_versao.janela") in velha.text
    assert _texto(idioma, "aviso_versao.baixar_janela") in velha.text
    assert 'action="/abrir-release"' in velha.text
    # o `voltar` sem HTMX é a página aberta (HX-Current-URL não veio: a raiz)
    assert 'name="voltar" value="/"' in velha.text


@pytest.mark.parametrize(
    "agente",
    [
        UA,
        f"{UA} joBot-casca/99.0.0 (macos)",
        f"{UA} joBot-casca/0.4 (linux)",
        f"{UA} joBot-casca/0.4.0 (bsd)",
    ],
)
def test_sem_casca_velha_nao_oferece_a_janela_nova(painel: Painel, agente: str) -> None:
    texto = painel.cliente.get("/aviso-versao", headers={"User-Agent": agente}).text
    assert 'action="/atualizar"' in texto  # controle: a faixa está lá
    assert _texto("pt", "aviso_versao.baixar_janela") not in texto
    assert "/abrir-release" not in texto


def test_abrir_release_abre_a_pagina_pelo_python(painel: Painel) -> None:
    agente = {"User-Agent": f"{UA} joBot-casca/0.4.0 (windows)"}
    corpo = {CAMPO_CSRF: painel.app.state.csrf}
    resposta = painel.cliente.post("/abrir-release", data=corpo, headers=HTMX | agente)
    assert resposta.status_code == 200
    assert painel.abertos == [RELEASE]
    assert _texto("pt", "aviso_versao.janela_aberta") in resposta.text
    assert _texto("pt", "aviso_versao.baixar_janela") in resposta.text  # a faixa segue inteira
    assert 'name="voltar" value="/vagas?ordem=nova"' in resposta.text


def test_abrir_release_que_falha_mostra_o_endereco(painel: Painel) -> None:
    painel.abre = False
    resposta = painel.post("/abrir-release")
    assert painel.abertos == [RELEASE]
    assert _texto("pt", "aviso_versao.janela_falhou", endereco=RELEASE) in resposta.text


def test_abrir_release_sem_htmx_volta_para_a_pagina(painel: Painel) -> None:
    resposta = painel.post("/abrir-release", {"voltar": "/buscas"}, htmx=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/buscas"
    assert painel.abertos == [RELEASE]
    fora = painel.post("/abrir-release", {"voltar": "https://exemplo.invalid/"}, htmx=False)
    assert fora.headers["location"] == "/"


def test_abrir_release_sem_csrf_recusa_e_nao_abre(painel: Painel) -> None:
    resposta = painel.cliente.post("/abrir-release", headers=HTMX)
    assert resposta.status_code == 403
    assert painel.abertos == []
