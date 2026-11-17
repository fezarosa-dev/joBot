"""Aba Serviços: a chave do 2Captcha e o interruptor (plano T184; ADR 0014 e 0022).

O cofre de senhas é o `CofreFalso`: nenhum teste toca o do sistema.
"""

import asyncio
import html as html_lib
import json
import logging
import re
import threading
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from selectolax.lexbor import LexborHTMLParser, LexborNode

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from jobot.banco import cadastros
from jobot.banco.captcha import TETO_DIA
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.navegador import limites
from jobot.nucleo.captcha import Falha
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
TESTAR = SERVICOS + "/captcha/testar"
DIGITADA = "ZyXw9876VuTs5432RqPo1098NmLk7654"
API_SALDO = "https://api.2captcha.com/getBalance"
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
        self.app.state.relogio = RelogioFalso()
        self.pedidos: list[httpx.Request] = []
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

    def api(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        """Troca a rede do painel por `handler`; cada pedido que chega fica em `pedidos`."""

        def gravando(pedido: httpx.Request) -> httpx.Response:
            self.pedidos.append(pedido)
            return handler(pedido)

        self.app.state.transporte = httpx.MockTransport(gravando)

    def testar(self, chave: str) -> Any:
        return self.post(TESTAR, {"chave": chave}, htmx=True)

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
    monkeypatch.setattr(limites, "PRAZO_COFRE_S", 0.05)
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


# --- testar a chave ------------------------------------------------------------------------


def _so_se_chamado(pedido: httpx.Request) -> httpx.Response:
    raise AssertionError("o teste não devia falar com o 2Captcha")


def _saldo(corpo: dict[str, object]) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _pedido: httpx.Response(200, json=corpo)


def test_testar_com_a_chave_digitada_mostra_o_saldo(painel: Painel) -> None:
    def handler(pedido: httpx.Request) -> httpx.Response:
        assert str(pedido.url) == API_SALDO
        assert json.loads(pedido.content) == {"clientKey": DIGITADA}
        return httpx.Response(200, json={"errorId": 0, "balance": 1234.567})

    painel.api(handler)
    resposta = painel.testar(DIGITADA)
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.captcha.ok", saldo="1.234,56").endswith("Saldo: 1.234,56")
    assert pt("configuracoes.servicos.captcha.ok", saldo="1.234,56") in _texto(resposta)
    assert len(painel.pedidos) == 1
    assert painel.cofre.ler(NOME) is None  # testar não grava
    assert DIGITADA not in resposta.text


def test_testar_sem_digitar_usa_a_salva(painel: Painel) -> None:
    painel.salvar(CHAVE)

    def handler(pedido: httpx.Request) -> httpx.Response:
        assert json.loads(pedido.content) == {"clientKey": CHAVE}
        return httpx.Response(200, json={"errorId": 0, "balance": 0.9})

    painel.api(handler)
    resposta = painel.testar("")
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.captcha.ok", saldo="0,90") in _texto(resposta)
    assert CHAVE not in resposta.text
    assert len(painel.pedidos) == 1


def test_testar_sem_chave_nenhuma_explica_sem_pedido(painel: Painel) -> None:
    painel.api(_so_se_chamado)
    resposta = painel.testar("")
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.erro.sem_chave") in _texto(resposta)
    assert painel.pedidos == []


def test_testar_chave_torta_nao_faz_pedido(painel: Painel) -> None:
    painel.salvar(CHAVE)  # com chave salva: a torta digitada não cai na salva
    painel.api(_so_se_chamado)
    resposta = painel.testar("curta")
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.erro.formato") in _texto(resposta)
    assert painel.pedidos == []
    achado = painel.cofre.ler(NOME)
    assert achado is not None
    assert achado[0] == CHAVE  # a chave salva segue intacta


def test_testar_com_o_cofre_travado_mostra_erro_do_cofre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trava = threading.Event()
    painel = Painel(tmp_path, CofreFalso(trava=trava))
    painel.api(_so_se_chamado)
    monkeypatch.setattr(limites, "PRAZO_COFRE_S", 0.05)
    try:
        resposta = painel.testar("")
    finally:
        trava.set()  # solta a thread presa
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.erro.cofre") in _texto(resposta)
    assert painel.pedidos == []


def _levanta(erro: BaseException) -> Callable[[httpx.Request], httpx.Response]:
    def handler(_pedido: httpx.Request) -> httpx.Response:
        raise erro

    return handler


@pytest.mark.parametrize(
    ("handler", "falha"),
    [
        (_saldo({"errorId": 1, "errorCode": "ERROR_KEY_DOES_NOT_EXIST"}), Falha.CHAVE_INVALIDA),
        (_saldo({"errorId": 10, "errorCode": "ERROR_ZERO_BALANCE"}), Falha.SEM_SALDO),
        (_saldo({"errorId": 11, "errorCode": "ERROR_IP_NOT_ALLOWED"}), Falha.IP_BLOQUEADO),
        (_saldo({"errorId": 55, "errorCode": "ERROR_ACCOUNT_SUSPENDED"}), Falha.CONTA_SUSPENSA),
        (_levanta(httpx.ConnectError("x")), Falha.OUTRO),
        (_levanta(TimeoutError()), Falha.TEMPO_ESGOTADO),
    ],
)
def test_cada_falha_da_api_vira_o_texto_dela(
    painel: Painel, handler: Callable[[httpx.Request], httpx.Response], falha: Falha
) -> None:
    painel.api(handler)
    resposta = painel.testar(DIGITADA)
    assert resposta.status_code == 200
    esperado = pt("captcha.erro." + falha.value)
    assert esperado != "captcha.erro." + falha.value
    assert esperado in _texto(resposta)
    assert pt("configuracoes.servicos.captcha.ok", saldo="") not in _texto(resposta)


def test_testar_que_passa_do_prazo_vira_tempo_esgotado(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel.api(_so_se_chamado)

    async def lento(*_: object, **__: object) -> None:
        await asyncio.sleep(5)

    monkeypatch.setattr(servicos, "PRAZO_TESTE_S", 0.05)
    monkeypatch.setattr(servicos, "saldo", lento)
    resposta = painel.testar(DIGITADA)
    assert resposta.status_code == 200
    assert pt("captcha.erro.tempo_esgotado") in _texto(resposta)


def _testar_com(painel: Painel, salva: bool) -> tuple[Any, str]:
    """Testa com a chave digitada ou, se `salva`, com a do cofre; devolve a resposta e a chave."""
    if not salva:
        return painel.testar(DIGITADA), DIGITADA
    painel.salvar(CHAVE)
    return painel.testar(""), CHAVE


@pytest.mark.parametrize("salva", [False, True])
def test_segredo_nunca_no_log_nem_na_resposta(
    painel: Painel, caplog: pytest.LogCaptureFixture, salva: bool
) -> None:
    painel.api(_levanta(httpx.ConnectError(DIGITADA + CHAVE)))  # o erro de rede leva as duas
    with caplog.at_level(logging.DEBUG):
        resposta, _ = _testar_com(painel, salva)
    assert resposta.status_code == 200
    assert painel.pedidos  # o pedido saiu de verdade (o cliente tenta mais de uma vez)
    for segredo in (DIGITADA, CHAVE):
        assert segredo not in caplog.text
        assert segredo not in resposta.text
        assert segredo not in "".join(f"{k}={v}" for k, v in resposta.headers.items())


@pytest.mark.parametrize("salva", [False, True])
@pytest.mark.parametrize("balance", ["abc", -1])
def test_saldo_torto_loga_a_falha_sem_a_chave(
    painel: Painel, caplog: pytest.LogCaptureFixture, balance: object, salva: bool
) -> None:
    """O núcleo não registra a resposta torta: a rota loga `falha.value`, e só ele."""
    painel.api(_saldo({"errorId": 0, "balance": balance}))
    with caplog.at_level(logging.DEBUG):
        resposta, _ = _testar_com(painel, salva)
    assert resposta.status_code == 200
    assert pt("captcha.erro.outro") in _texto(resposta)
    da_rota = [r.getMessage() for r in caplog.records if r.name == servicos.__name__]
    assert any(Falha.OUTRO.value in m for m in da_rota), da_rota
    for segredo in (DIGITADA, CHAVE):
        assert segredo not in caplog.text
        assert segredo not in resposta.text


def test_o_botao_testar_leva_a_chave_digitada_e_mostra_onde_cai(painel: Painel) -> None:
    html = painel.get(SERVICOS).text
    botao = _no(html, f'button[hx-post="{TESTAR}"]')
    assert botao.attributes["hx-include"] == "#campo-chave-captcha"
    assert botao.attributes["hx-target"] == "#resultado-captcha"
    assert botao.attributes["hx-disabled-elt"] == "this"
    assert "botao" in str(botao.attributes["class"]).split()
    assert "form" not in {p.tag for p in _pais(botao)}  # fora do form: não envia a chave ao salvar
    assert pt("configuracoes.servicos.captcha.testar") in botao.text()
    regiao = _no(html, "#resultado-captcha")
    assert regiao.attributes["aria-live"] == "polite"
    assert regiao.text(strip=True) == ""


def test_botao_testar_tem_rotulo_e_texto_de_espera_para_leitor_de_tela(painel: Painel) -> None:
    html = painel.get(SERVICOS).text
    botao = _no(html, f'button[hx-post="{TESTAR}"]')
    assert "botao-secundario" in str(botao.attributes["class"]).split()
    rotulo = _no(html, f'button[hx-post="{TESTAR}"] .botao-rotulo')
    assert rotulo.text(strip=True) == pt("configuracoes.servicos.captcha.testar")
    espera = _no(html, f'button[hx-post="{TESTAR}"] .botao-espera')
    assert espera.text(strip=True) == pt("configuracoes.servicos.captcha.testando")
    assert "data-testando" not in botao.attributes


def test_olho_mostra_o_que_foi_digitado_pelo_aria_controls(painel: Painel) -> None:
    html = painel.get(SERVICOS).text
    olho = _no(html, "button[data-olho]").attributes
    assert olho["type"] == "button"
    assert olho["aria-controls"] == "campo-chave-captcha"
    assert olho["aria-pressed"] == "false"
    assert {"botao", "botao-secundario"} <= set(str(olho["class"]).split())
    assert _no(html, "button[data-olho]").text(strip=True) == pt(
        "configuracoes.servicos.captcha.mostrar"
    )
    campo = _no(html, "#campo-chave-captcha").attributes
    assert campo["type"] == "password"
    assert "campo-texto" in str(campo["class"]).split()


def test_salvo_some_sozinho_so_a_mensagem_e_nao_o_no_do_status(painel: Painel) -> None:
    painel.salvar(CHAVE)
    resposta = painel.post(INTERRUPTOR, {"captcha_ligado": "on"}, htmx=True)
    oob = _no(resposta.text, "[hx-swap-oob]")
    assert "data-some-sozinho" not in oob.attributes  # o innerHTML OOB descarta o <p>
    filho = _no(resposta.text, "[hx-swap-oob] > [data-some-sozinho]")
    assert filho.text(strip=True) == pt("configuracoes.salvo")
    # a página não traz a mensagem pronta: só aparece depois de salvar
    assert "data-some-sozinho" not in painel.get(SERVICOS).text


def _pais(no: LexborNode) -> list[LexborNode]:
    achados: list[LexborNode] = []
    atual = no.parent
    while atual is not None:
        achados.append(atual)
        atual = atual.parent
    return achados


def test_todo_codigo_de_falha_tem_texto_em_pt_e_en() -> None:
    for falha in Falha:
        chave = "captcha.erro." + falha.value
        for idioma in ("pt", "en"):
            assert t(idioma, chave) != chave, (idioma, chave)


# --- CSRF e catálogo -----------------------------------------------------------------------


@pytest.mark.parametrize("url", [SERVICOS, INTERRUPTOR, APAGAR, TESTAR])
def test_post_servicos_sem_token_da_403(painel: Painel, url: str) -> None:
    painel.ligar(True)
    painel.api(_so_se_chamado)
    resposta = painel.http.post(url, data={"chave": CHAVE, "captcha_ligado": "on"})
    assert resposta.status_code == 403
    assert painel.cofre.ler(NOME) is None
    assert painel.ligado() is True  # nada mudou: nem o apagar desligou
    assert painel.pedidos == []  # o 403 vem antes de qualquer pedido ao 2Captcha


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


# --- chaves de IA (T414; desenho 10.3 da fase 4) -------------------------------------------

IA_COM_CHAVE = ("anthropic", "openai", "gemini")
IA = (*IA_COM_CHAVE, "compativel")
CHAVE_IA = "sk-ant-api03-AbCd_1234-EfGh5678IjKl9012MnOpQrSt"
OUTRA_IA = "AIzaSyZ-9876_VuTs5432RqPo1098NmLk7654"
ENDERECO = "http://127.0.0.1:11434/v1"
APAGAR_IA = SERVICOS + "/ia/{}/apagar"


def _salvar_ia(painel: Painel, servico: str, **campos: str) -> Any:
    return painel.post(SERVICOS, {"servico": servico, **campos})


def _compativel(painel: Painel) -> object:
    with closing(abrir(painel.banco)) as con:
        return cadastros.ler_config(con, "ia_compativel")


def _cartao_ia(html: str, servico: str) -> LexborNode:
    return _no(html, f"#cartao-ia-{servico}")


def test_servicos_mostra_os_quatro_cartoes_de_ia_depois_do_2captcha(painel: Painel) -> None:
    html = painel.get(SERVICOS).text
    ids = [str(n.attributes["id"]) for n in LexborHTMLParser(html).css('[id^="cartao-"]')]
    assert ids == ["cartao-captcha", *(f"cartao-ia-{s}" for s in IA)]
    for servico in IA:
        cartao = _cartao_ia(html, servico)
        titulo = pt(f"configuracoes.servicos.ia.{servico}.titulo")
        assert _no(cartao.html or "", "h2").text(strip=True) == titulo
        assert pt("configuracoes.servicos.ia.nada_sai") in html_lib.unescape(cartao.html or "")
    # um botão principal por tela: o do 2Captcha; os das chaves de IA são secundários
    assert len(LexborHTMLParser(html).css(".config-conteudo .botao-primario")) == 1


def test_cartao_da_anthropic_avisa_do_workspace_e_da_cobranca(painel: Painel) -> None:
    frase = pt("configuracoes.servicos.ia.anthropic.frase")
    assert "workspace" in frase
    assert "402" in frase
    en = t("en", "configuracoes.servicos.ia.anthropic.frase")
    assert "workspace" in en
    assert "402" in en
    assert frase in _texto(painel.get(SERVICOS))


@pytest.mark.parametrize("servico", IA)
def test_todo_texto_dos_cartoes_de_ia_existe_em_pt_e_en(servico: str) -> None:
    catalogo = carregar()
    for sufixo in ("titulo", "de", "frase"):
        chave = f"configuracoes.servicos.ia.{servico}.{sufixo}"
        for idioma in ("pt", "en"):
            assert catalogo[idioma].get(chave), (idioma, chave)


@pytest.mark.parametrize("servico", IA_COM_CHAVE)
def test_salvar_chave_de_ia_grava_no_cofre_e_mostra_so_a_mascara(
    painel: Painel, servico: str
) -> None:
    resposta = _salvar_ia(painel, servico, chave=CHAVE_IA)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == SERVICOS + "?salvo=1"
    assert painel.cofre.ler(f"ia_{servico}") == (CHAVE_IA, "sistema")
    assert painel.cofre.ler(NOME) is None  # o 2Captcha não muda
    seguinte = painel.get(SERVICOS)
    cartao = html_lib.unescape(_cartao_ia(seguinte.text, servico).html or "")
    assert pt("configuracoes.servicos.captcha.salva", mascara="•••• " + CHAVE_IA[-4:]) in cartao
    assert CHAVE_IA not in seguinte.text  # (guarda) nunca no `value` nem em lugar nenhum
    campo = _no(seguinte.text, f"#campo-chave-ia-{servico}").attributes
    assert campo["type"] == "password"
    assert "value" not in campo
    assert campo["name"] == "chave"


def test_cada_cartao_de_ia_mostra_so_a_propria_chave(painel: Painel) -> None:
    _salvar_ia(painel, "openai", chave=CHAVE_IA)
    html = painel.get(SERVICOS).text
    salva = pt("configuracoes.servicos.captcha.salva", mascara="•••• " + CHAVE_IA[-4:])
    for servico in IA:
        com = salva in html_lib.unescape(_cartao_ia(html, servico).html or "")
        assert com is (servico == "openai"), servico
    assert salva not in html_lib.unescape(_no(html, "#cartao-captcha").html or "")


def test_salvar_chave_de_ia_vazia_mantem_a_salva(painel: Painel) -> None:
    _salvar_ia(painel, "gemini", chave=CHAVE_IA)
    resposta = _salvar_ia(painel, "gemini", chave="   ")
    assert resposta.status_code == 303
    assert painel.cofre.ler("ia_gemini") == (CHAVE_IA, "sistema")


def test_chave_de_ia_recortada_antes_de_salvar(painel: Painel) -> None:
    assert _salvar_ia(painel, "openai", chave="  " + CHAVE_IA + "\n").status_code == 303
    assert painel.cofre.ler("ia_openai") == (CHAVE_IA, "sistema")


@pytest.mark.parametrize(
    "ruim",
    [
        "sk-curt",  # 8 é o mínimo: 7 não
        "a" * 513,
        "sk-ant abc defghijkl",
        "sk-ãbcdefghijkl",
        "sk-abcd\nefghijkl",
        "sk-abcd​efghijkl",
    ],
)
def test_chave_de_ia_torta_volta_no_cartao_e_nao_grava(painel: Painel, ruim: str) -> None:
    resposta = _salvar_ia(painel, "anthropic", chave=ruim)
    assert resposta.status_code == 422
    cartao = _cartao_ia(resposta.text, "anthropic")
    alerta = _no(cartao.html or "", '[role="alert"]')
    assert alerta.text(strip=True) == pt("configuracoes.servicos.ia.erro.chave")
    assert _no(cartao.html or "", "#campo-chave-ia-anthropic").attributes["aria-invalid"] == "true"
    assert painel.cofre.ler("ia_anthropic") is None
    assert ruim.strip() not in _texto(resposta)


def test_chave_de_ia_de_8_caracteres_vale(painel: Painel) -> None:
    assert _salvar_ia(painel, "openai", chave="sk-12345").status_code == 303
    assert painel.cofre.ler("ia_openai") == ("sk-12345", "sistema")


@pytest.mark.parametrize("servico", ["", "local", "2captcha", "OPENAI", "ia_openai"])
def test_servico_fora_da_lista_e_422_seco(painel: Painel, servico: str) -> None:
    resposta = _salvar_ia(painel, servico, chave=CHAVE_IA)
    assert resposta.status_code == 422
    assert painel.backend.guardado == {}


def test_salvar_chave_de_ia_sem_csrf_e_recusado(painel: Painel) -> None:
    resposta = painel.http.post(SERVICOS, data={"servico": "openai", "chave": CHAVE_IA})
    assert resposta.status_code == 403
    assert painel.backend.guardado == {}


# --- o compatível --------------------------------------------------------------------------


def test_compativel_grava_o_endereco_sem_chave(painel: Painel) -> None:
    resposta = _salvar_ia(painel, "compativel", endereco=ENDERECO, chave="")
    assert resposta.status_code == 303
    assert _compativel(painel) == {"endereco": ENDERECO}
    assert painel.cofre.ler("ia_compativel") is None
    html = painel.get(SERVICOS).text
    assert _no(html, "#campo-endereco-ia").attributes["value"] == ENDERECO
    rotulo = _no(html, 'label[for="campo-chave-ia-compativel"]').text(strip=True)
    assert rotulo == pt(
        "configuracoes.servicos.ia.chave_opcional", de=pt("configuracoes.servicos.ia.compativel.de")
    )


def test_compativel_com_chave_grava_os_dois(painel: Painel) -> None:
    resposta = _salvar_ia(painel, "compativel", endereco=ENDERECO + "/", chave=OUTRA_IA)
    assert resposta.status_code == 303
    assert _compativel(painel) == {"endereco": ENDERECO}  # sem a `/` do fim
    assert painel.cofre.ler("ia_compativel") == (OUTRA_IA, "sistema")
    assert OUTRA_IA not in painel.get(SERVICOS).text


@pytest.mark.parametrize(
    ("digitado", "gravado"),
    [
        ("  https://api.exemplo.com/v1  ", "https://api.exemplo.com/v1"),
        ("http://localhost:1234/v1", "http://localhost:1234/v1"),
        ("http://[::1]:8080/v1", "http://[::1]:8080/v1"),
    ],
)
def test_endereco_do_compativel_que_vale(painel: Painel, digitado: str, gravado: str) -> None:
    assert _salvar_ia(painel, "compativel", endereco=digitado).status_code == 303
    assert _compativel(painel) == {"endereco": gravado}


@pytest.mark.parametrize(
    "ruim",
    [
        "",
        "http://exemplo.com/v1",  # http só no próprio computador
        "ftp://exemplo.com/v1",
        "https://eu:senha@exemplo.com/v1",
        "https://exemplo.com/v1?x=1",
        "https://exemplo.com/v1#x",
        "https://exem plo.com/v1",
        "https://exemplo.com:porta/v1",
        "https://exemplo.com/" + "a" * 2048,
    ],
)
def test_endereco_do_compativel_torto_volta_no_cartao_e_nada_e_gravado(
    painel: Painel, ruim: str
) -> None:
    _salvar_ia(painel, "compativel", endereco=ENDERECO)
    resposta = _salvar_ia(painel, "compativel", endereco=ruim, chave=OUTRA_IA)
    assert resposta.status_code == 422
    cartao = _cartao_ia(resposta.text, "compativel")
    alerta = _no(cartao.html or "", '[role="alert"]')
    assert alerta.text(strip=True) == pt("configuracoes.servicos.ia.erro.endereco")
    assert _no(cartao.html or "", "#campo-endereco-ia").attributes["aria-invalid"] == "true"
    assert _compativel(painel) == {"endereco": ENDERECO}
    assert painel.cofre.ler("ia_compativel") is None  # a chave digitada também não
    assert OUTRA_IA not in resposta.text


def test_endereco_torto_volta_no_campo_para_corrigir(painel: Painel) -> None:
    resposta = _salvar_ia(painel, "compativel", endereco="http://exemplo.com/v1")
    assert _no(resposta.text, "#campo-endereco-ia").attributes["value"] == "http://exemplo.com/v1"


# --- apagar a chave de IA ------------------------------------------------------------------


def test_sem_chave_de_ia_nao_ha_botao_apagar(painel: Painel) -> None:
    html = painel.get(SERVICOS).text
    for servico in IA:
        assert f'action="{APAGAR_IA.format(servico)}"' not in html


@pytest.mark.parametrize("servico", IA_COM_CHAVE)
def test_apagar_chave_de_ia_tira_do_cofre_e_devolve_o_cartao(painel: Painel, servico: str) -> None:
    _salvar_ia(painel, servico, chave=CHAVE_IA)
    _salvar_ia(painel, "openai" if servico != "openai" else "gemini", chave=OUTRA_IA)
    assert f'action="{APAGAR_IA.format(servico)}"' in painel.get(SERVICOS).text
    resposta = painel.post(APAGAR_IA.format(servico), htmx=True)
    assert resposta.status_code == 200
    assert re.match(rf'\s*<section[^>]*\bid="cartao-ia-{servico}"', resposta.text)
    assert "data-foco" in _no(resposta.text, f"#campo-chave-ia-{servico}").attributes
    oob = _no(resposta.text, "[hx-swap-oob]")
    assert str(oob.attributes["hx-swap-oob"]).endswith("#status-servicos")
    assert painel.cofre.ler(f"ia_{servico}") is None
    assert f'action="{APAGAR_IA.format(servico)}"' not in resposta.text
    outro = "openai" if servico != "openai" else "gemini"
    assert painel.cofre.ler(f"ia_{outro}") == (OUTRA_IA, "sistema")  # só a dele


def test_apagar_o_compativel_tira_o_endereco_e_a_chave(painel: Painel) -> None:
    _salvar_ia(painel, "compativel", endereco=ENDERECO, chave=OUTRA_IA)
    resposta = painel.post(APAGAR_IA.format("compativel"))
    assert resposta.status_code == 303
    assert resposta.headers["location"] == SERVICOS + "?salvo=1"
    assert _compativel(painel) == {"endereco": ""}
    assert painel.cofre.ler("ia_compativel") is None


def test_compativel_so_com_endereco_tem_botao_apagar(painel: Painel) -> None:
    _salvar_ia(painel, "compativel", endereco=ENDERECO)
    assert f'action="{APAGAR_IA.format("compativel")}"' in painel.get(SERVICOS).text
    assert painel.post(APAGAR_IA.format("compativel"), htmx=True).status_code == 200
    assert _compativel(painel) == {"endereco": ""}


@pytest.mark.parametrize("servico", ["local", "2captcha", "captcha", "x"])
def test_apagar_servico_fora_da_lista_e_404(painel: Painel, servico: str) -> None:
    painel.backend.guardado[(SERVICO, NOME)] = CHAVE
    assert painel.post(APAGAR_IA.format(servico), htmx=True).status_code == 404
    assert painel.cofre.ler(NOME) == (CHAVE, "sistema")


def test_apagar_chave_de_ia_sem_csrf_e_recusado(painel: Painel) -> None:
    _salvar_ia(painel, "openai", chave=CHAVE_IA)
    assert painel.http.post(APAGAR_IA.format("openai")).status_code == 403
    assert painel.cofre.ler("ia_openai") == (CHAVE_IA, "sistema")


def test_apagar_chave_de_ia_que_o_cofre_recusa_avisa_so_no_cartao_dela(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(recusa_apagar=True))
    _salvar_ia(painel, "openai", chave=CHAVE_IA)
    resposta = painel.post(APAGAR_IA.format("openai"), htmx=True)
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.erro.cofre") in _texto(resposta)
    sem_htmx = painel.post(APAGAR_IA.format("openai"))
    assert sem_htmx.headers["location"] == SERVICOS + "?erro=cofre-ia-openai"
    html = painel.get(sem_htmx.headers["location"]).text
    erro = pt("configuracoes.servicos.erro.cofre")
    assert erro in html_lib.unescape(_cartao_ia(html, "openai").html or "")
    assert erro not in html_lib.unescape(_no(html, "#cartao-captcha").html or "")
    assert erro not in html_lib.unescape(_cartao_ia(html, "gemini").html or "")


# --- cofre ruim e segredo ------------------------------------------------------------------


def test_sem_cofre_a_chave_de_ia_vai_ao_arquivo_e_o_cartao_avisa(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(falha=RuntimeError("x")))
    assert _salvar_ia(painel, "anthropic", chave=CHAVE_IA).status_code == 303
    assert (tmp_path / "ia_anthropic.segredo").read_text() == CHAVE_IA
    html = painel.get(SERVICOS).text
    aviso = pt("configuracoes.servicos.captcha.no_arquivo")
    assert aviso in html_lib.unescape(_cartao_ia(html, "anthropic").html or "")
    assert aviso not in html_lib.unescape(_cartao_ia(html, "openai").html or "")


def test_cofre_que_falha_ao_gravar_a_chave_de_ia_avisa_sem_vazar(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    painel = Painel(tmp_path, CofreFalso(falha=RuntimeError(SEGREDO)))
    (tmp_path / "ia_compativel.segredo").mkdir()  # o arquivo não abre
    with caplog.at_level(logging.DEBUG):
        resposta = _salvar_ia(painel, "compativel", endereco=ENDERECO, chave=CHAVE_IA)
    assert resposta.status_code == 200
    cartao = html_lib.unescape(_cartao_ia(resposta.text, "compativel").html or "")
    assert pt("configuracoes.servicos.erro.cofre") in cartao
    assert _compativel(painel) == {"endereco": ""}  # sem a chave, o endereço também não
    for proibido in (SEGREDO, CHAVE_IA):
        assert proibido not in caplog.text
        assert proibido not in resposta.text


def test_cofre_que_trava_ao_ler_as_chaves_de_ia_avisa_em_cada_cartao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trava = threading.Event()
    painel = Painel(tmp_path, CofreFalso(trava=trava))
    monkeypatch.setattr(limites, "PRAZO_COFRE_S", 0.05)
    try:
        html = painel.get(SERVICOS).text
    finally:
        trava.set()
    for servico in IA:
        cartao = html_lib.unescape(_cartao_ia(html, servico).html or "")
        assert pt("configuracoes.servicos.erro.cofre") in cartao, servico


@pytest.mark.parametrize("servico", IA)
def test_chave_de_ia_nunca_no_log(
    painel: Painel, caplog: pytest.LogCaptureFixture, servico: str
) -> None:
    campos = {"endereco": ENDERECO} if servico == "compativel" else {}
    with caplog.at_level(logging.DEBUG):
        _salvar_ia(painel, servico, chave=CHAVE_IA, **campos)
        _salvar_ia(painel, servico, chave=CHAVE_IA + " torta", **campos)
        painel.get(SERVICOS)
        painel.post(APAGAR_IA.format(servico), htmx=True)
    assert CHAVE_IA not in caplog.text
