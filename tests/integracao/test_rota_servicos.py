"""Aba Serviços: a chave do 2Captcha e o interruptor (plano T184; ADR 0014 e 0022).

O cofre de senhas é o `CofreFalso`: nenhum teste toca o do sistema.
"""

import html as html_lib
import logging
import re
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from selectolax.lexbor import LexborHTMLParser, LexborNode

from apoio.cofre_falso import CofreFalso
from jobot.banco import cadastros
from jobot.banco.captcha import TETO_DIA
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.i18n import carregar, t
from jobot.painel.rotas import servicos
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema.cofre import SERVICO, Cofre

PORTA = 47619
CHAVE = "AbCd1234EfGh5678IjKl9012MnOp3456"
SEGREDO = "segredo-do-cofre-QWERTY"
SERVICOS = "/configuracoes/servicos"
INTERRUPTOR = SERVICOS + "/captcha/interruptor"
APAGAR = SERVICOS + "/captcha/apagar"
NOME = "2captcha"
HX = {"HX-Request": "true"}
CARTAO = re.compile(r'\s*<[a-z]+[^>]*\bid="cartao-captcha"')


def pt(chave: str, **params: object) -> str:
    return t("pt", chave, **params)


class Painel:
    """Cliente do app sobre um banco migrado, com um cofre falso na pasta de dados."""

    def __init__(self, tmp_path: Path, backend: CofreFalso | None = None) -> None:
        self.dados = tmp_path
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            cadastros.semear(con)
        self.backend = backend if backend is not None else CofreFalso()
        self.cofre = Cofre(tmp_path, self.backend)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.cofre = self.cofre
        self.http = TestClient(
            self.app,
            base_url=f"http://127.0.0.1:{PORTA}",
            follow_redirects=False,
            headers={"Accept-Language": "pt"},
        )
        self.token: str = self.app.state.csrf

    def ligado(self) -> object:
        with closing(abrir(self.banco)) as con:
            return cadastros.ler_config(con, "captcha_ligado")

    def ligar(self, valor: bool) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.gravar_config(con, "captcha_ligado", valor)

    def get(self, url: str) -> Any:
        return self.http.get(url)

    def post(self, url: str, dados: dict[str, Any] | None = None, htmx: bool = False) -> Any:
        if htmx:
            return self.http.post(url, data=dados or {}, headers={**HX, "X-CSRF-Token": self.token})
        return self.http.post(url, data={CAMPO_CSRF: self.token, **(dados or {})})

    def salvar(self, chave: str) -> Any:
        return self.post(SERVICOS, {"chave": chave})


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _texto(resposta: Any) -> str:
    return html_lib.unescape(str(resposta.text))


def _no(html: str, seletor: str) -> LexborNode:
    achado = LexborHTMLParser(html).css_first(seletor)
    assert achado is not None, seletor
    return achado


def _interruptor(html: str) -> dict[str, str | None]:
    return dict(_no(html, 'input[name="captcha_ligado"]').attributes)


# --- a aba e o cartão ----------------------------------------------------------------------


def test_aba_servicos_abre_com_o_cartao_do_2captcha(painel: Painel) -> None:
    resposta = painel.get(SERVICOS)
    assert resposta.status_code == 200
    assert _no(resposta.text, f'nav a[href="{SERVICOS}"]').attributes["aria-current"] == "page"
    texto = _texto(resposta)
    assert pt("configuracoes.servicos.captcha.usar") in texto
    for chave in ("login", "termos", "custo", "dados"):
        esperado = pt("configuracoes.servicos.captcha.aviso." + chave, teto=TETO_DIA)
        assert esperado in texto
    assert "30" in pt("configuracoes.servicos.captcha.aviso.custo", teto=TETO_DIA)
    link = _no(resposta.text, 'a[href="https://2captcha.com"]').attributes
    assert link["target"] == "_blank"
    assert link["rel"] == "noopener noreferrer"
    assert "botao" in str(link["class"]).split()


def test_sem_chave_o_interruptor_vem_desativado_e_explica(painel: Painel) -> None:
    resposta = painel.get(SERVICOS)
    atributos = _interruptor(resposta.text)
    assert "disabled" in atributos
    assert atributos["role"] == "switch"
    assert "checked" not in atributos
    assert "chave" in str(atributos["class"]).split()
    texto = _texto(resposta)
    assert pt("configuracoes.servicos.captcha.sem_chave") in texto
    assert pt("configuracoes.servicos.captcha.apagar") not in texto


def test_interruptor_fica_fora_de_qualquer_form(painel: Painel) -> None:
    no: LexborNode | None = _no(painel.get(SERVICOS).text, 'input[name="captcha_ligado"]')
    while no is not None:
        assert no.tag != "form"
        no = no.parent


def test_salvar_chave_grava_no_cofre_e_mostra_so_o_final(painel: Painel) -> None:
    resposta = painel.salvar(CHAVE)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == SERVICOS + "?salvo=1"
    assert CHAVE not in resposta.headers["location"]
    assert painel.cofre.ler(NOME) == (CHAVE, "sistema")
    seguinte = painel.get(SERVICOS)
    assert "•••• " + CHAVE[-4:] in _texto(seguinte)
    assert CHAVE not in seguinte.text
    assert "value" not in _no(seguinte.text, 'input[name="chave"]').attributes
    assert pt("configuracoes.servicos.captcha.apagar") in _texto(seguinte)


def test_chave_de_menos_de_12_mostra_so_pontos(painel: Painel) -> None:
    painel.backend.guardado[(SERVICO, NOME)] = "abcdefghij"
    texto = _texto(painel.get(SERVICOS))
    assert "••••" in texto
    assert "•••• " not in texto
    assert "ghij" not in texto


def test_salvar_vazio_mantem_a_chave(painel: Painel) -> None:
    painel.salvar(CHAVE)
    resposta = painel.salvar("")
    assert resposta.status_code == 303
    assert painel.cofre.ler(NOME) == (CHAVE, "sistema")


def test_chave_recortada_antes_de_salvar(painel: Painel) -> None:
    assert painel.salvar("  " + CHAVE + "\n").status_code == 303
    assert painel.cofre.ler(NOME) == (CHAVE, "sistema")


@pytest.mark.parametrize(
    "ruim",
    [
        "a" * 15,
        "a" * 65,
        "abcd efgh ijkl mnop",
        "abcdefghijklmnop!",
        "ãbcdefghijklmnopq",
        "abcdefgh\nijklmnop",
    ],
)
def test_chave_torta_volta_com_mensagem_e_nao_grava(painel: Painel, ruim: str) -> None:
    resposta = painel.salvar(ruim)
    assert resposta.status_code == 422
    assert pt("configuracoes.servicos.erro.formato") in _texto(resposta)
    assert painel.cofre.ler(NOME) is None
    assert ruim.strip() not in _texto(resposta)


# --- o interruptor -------------------------------------------------------------------------


def test_ligar_sem_chave_da_409_e_nao_grava(painel: Painel) -> None:
    resposta = painel.post(INTERRUPTOR, {"captcha_ligado": "on"}, htmx=True)
    assert resposta.status_code == 409
    assert painel.ligado() is False


def test_ligar_com_chave_grava_e_devolve_o_cartao(painel: Painel) -> None:
    painel.salvar(CHAVE)
    resposta = painel.post(INTERRUPTOR, {"captcha_ligado": "on"}, htmx=True)
    assert resposta.status_code == 200
    assert CARTAO.match(resposta.text)
    atributos = _interruptor(resposta.text)
    assert "checked" in atributos
    assert "data-foco" in atributos
    oob = _no(resposta.text, "[hx-swap-oob]")
    assert str(oob.attributes["hx-swap-oob"]).endswith("#status-servicos")
    assert oob.text(strip=True) == pt("configuracoes.salvo")
    assert painel.ligado() is True
    assert CHAVE not in resposta.text


def test_ajuda_do_interruptor_segue_a_chave(painel: Painel) -> None:
    def ajuda(html: str) -> str:
        alvo = str(_interruptor(html)["aria-describedby"])
        return _no(html, "#" + alvo).text(strip=True)

    assert ajuda(painel.get(SERVICOS).text) == pt("configuracoes.servicos.captcha.sem_chave")
    painel.salvar(CHAVE)
    assert ajuda(painel.get(SERVICOS).text) == pt("configuracoes.servicos.captcha.usar.ajuda")


def test_status_fica_fora_do_cartao(painel: Painel) -> None:
    html = painel.get(SERVICOS).text
    status = _no(html, "#status-servicos")
    assert status.attributes["role"] == "status"
    assert status.text(strip=True) == ""
    ancestral: LexborNode | None = status
    while ancestral is not None:
        assert ancestral.attributes.get("id") != "cartao-captcha"
        ancestral = ancestral.parent
    assert _no(html, "#cartao-captcha") is not None


def test_desligar_sempre_pode(painel: Painel) -> None:
    painel.ligar(True)
    resposta = painel.post(INTERRUPTOR, htmx=True)
    assert resposta.status_code == 200
    assert painel.ligado() is False


# --- apagar --------------------------------------------------------------------------------


def test_apagar_chave_desliga_e_tira_do_cofre(painel: Painel) -> None:
    painel.salvar(CHAVE)
    painel.ligar(True)
    resposta = painel.post(APAGAR, htmx=True)
    assert resposta.status_code == 200
    assert CARTAO.match(resposta.text)
    assert "Chave salva" not in _texto(resposta)
    assert "hx-swap-oob" in resposta.text
    # o botão some com a troca: o foco vai para o campo da chave
    assert "data-foco" in _no(resposta.text, "#campo-chave-captcha").attributes
    assert painel.cofre.ler(NOME) is None
    assert painel.ligado() is False


def test_apagar_sem_htmx_redireciona(painel: Painel) -> None:
    painel.salvar(CHAVE)
    painel.ligar(True)
    resposta = painel.post(APAGAR)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == SERVICOS + "?salvo=1"
    assert painel.cofre.ler(NOME) is None
    assert painel.ligado() is False


def test_apagar_que_o_cofre_recusa_mostra_erro(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(recusa_apagar=True))
    painel.salvar(CHAVE)
    painel.ligar(True)
    resposta = painel.post(APAGAR, htmx=True)
    assert resposta.status_code == 200
    assert 'id="cartao-captcha"' in resposta.text
    assert pt("configuracoes.servicos.erro.cofre") in _texto(resposta)
    assert painel.ligado() is False


def test_apagar_que_o_cofre_recusa_sem_htmx_volta_com_o_erro(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(recusa_apagar=True))
    painel.salvar(CHAVE)
    resposta = painel.post(APAGAR)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == SERVICOS + "?erro=cofre"
    seguinte = painel.get(resposta.headers["location"])
    assert pt("configuracoes.servicos.erro.cofre") in _texto(seguinte)


# --- cofre ruim ----------------------------------------------------------------------------


def test_sem_cofre_a_chave_vai_ao_arquivo_e_o_cartao_avisa(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(falha=RuntimeError("x")))
    assert painel.salvar(CHAVE).status_code == 303
    assert (tmp_path / "2captcha.segredo").read_text() == CHAVE
    assert pt("configuracoes.servicos.captcha.no_arquivo") in _texto(painel.get(SERVICOS))


def test_cofre_que_falha_vira_aviso_sem_vazar_a_chave(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    painel = Painel(tmp_path, CofreFalso(falha=RuntimeError(SEGREDO)))
    (tmp_path / "2captcha.segredo").mkdir()  # o arquivo não abre
    with caplog.at_level(logging.DEBUG):
        resposta = painel.salvar(CHAVE)
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.erro.cofre") in _texto(resposta)
    for proibido in (SEGREDO, CHAVE):
        assert proibido not in caplog.text
        assert proibido not in resposta.text


class _CofreContado(CofreFalso):
    """Conta as chamadas que entraram no cofre (a thread nasceu e ficou presa na `trava`)."""

    chamadas = 0

    def _antes(self) -> None:
        self.chamadas += 1
        super()._antes()


def test_cofre_que_trava_vira_erro_em_15_s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    trava = threading.Event()
    backend = _CofreContado(trava=trava)
    painel = Painel(tmp_path, backend)
    monkeypatch.setattr(servicos, "PRAZO_COFRE_S", 0.05)
    try:
        with caplog.at_level(logging.DEBUG):
            resposta = painel.salvar(CHAVE)
        assert backend.chamadas >= 1  # a chamada presa entrou no cofre e foi abandonada
    finally:
        trava.set()  # solta as threads presas
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.erro.cofre") in _texto(resposta)
    assert "TimeoutError" in caplog.text
    assert CHAVE not in caplog.text


# --- CSRF e catálogo -----------------------------------------------------------------------


@pytest.mark.parametrize("url", [SERVICOS, INTERRUPTOR, APAGAR])
def test_post_servicos_sem_token_da_403(painel: Painel, url: str) -> None:
    painel.ligar(True)
    resposta = painel.http.post(url, data={"chave": CHAVE, "captcha_ligado": "on"})
    assert resposta.status_code == 403
    assert painel.cofre.ler(NOME) is None
    assert painel.ligado() is True  # nada mudou: nem o apagar desligou


def test_chaves_novas_em_pt_e_en() -> None:
    catalogo = carregar()
    chaves = {
        c
        for c in catalogo["pt"]
        if c.startswith("configuracoes.servicos.") or c == "configuracoes.grupo.servicos"
    }
    assert len(chaves) >= 19
    for chave in chaves:
        assert chave in catalogo["en"], chave
        assert set(re.findall(r"\{(\w+)\}", catalogo["pt"][chave])) == set(
            re.findall(r"\{(\w+)\}", catalogo["en"][chave])
        ), chave
