"""Cartão do Gmail na aba Contas (plano T278; desenho 5.7.1, ADR 0024, E6 a E13, E21).

O IMAP é sempre o `ImapFalso` em `app.state.abrir_imap` (a rede está bloqueada) e o cofre é o
`CofreFalso`: nenhum teste toca o cofre real. A senha é a falsa dos testes.
"""

import html as html_lib
import imaplib
import logging
import re
import threading
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from keyring.errors import NoKeyringError
from starlette.routing import Match

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.sessoes import gravar_sessao, ler_sessao
from jobot.navegador import limites
from jobot.nucleo import gmail as nucleo_gmail
from jobot.painel.app import criar_app
from jobot.painel.rotas import gmail
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema.cofre import Cofre

PORTA = 47623
SALVAR = "/configuracoes/gmail/salvar"
CONFERIR = "/configuracoes/gmail/conferir"
REMOVER = "/configuracoes/gmail/remover"
CONTAS = "/configuracoes/contas"
AGORA = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
ENDERECO = "pessoa.teste@gmail.com"
SENHA = "abcd efgh ijkl mnop"
LIMPA = "abcdefghijklmnop"
ACESSO = {
    "pt": "A senha de app dá acesso a todo o seu e-mail.",
    "en": "An app password gives access to your whole mailbox.",
}


class ImapFalso:
    """O servidor IMAP de mentira: `modo` diz o que o login dá; `espera` segura o login."""

    def __init__(self) -> None:
        self.modo = "ok"
        self.espera: threading.Event | None = None
        self.logins: list[tuple[str, str]] = []

    def __call__(self) -> ImapFalso:  # o abridor: `app.state.abrir_imap`
        return self

    def login(self, user: str, password: str) -> tuple[str, list[Any]]:
        self.logins.append((user, password))
        if self.espera is not None:
            self.espera.wait(5)
        if self.modo == "recusada":
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")
        if self.modo == "bloqueio":
            raise imaplib.IMAP4.error("[ALERT] Please log in via your web browser")
        if self.modo == "sem_rede":
            raise OSError("rede fora")
        return "OK", [b"logado"]

    def select(self, mailbox: str = "INBOX", readonly: bool = False) -> tuple[str, list[Any]]:
        return "OK", [b"1"]

    def logout(self) -> tuple[str, list[Any]]:
        return "BYE", [b"tchau"]


class Painel:
    """App sobre um banco migrado, sem leitor, com cofre e IMAP falsos e o relógio parado."""

    def __init__(self, tmp_path: Path, backend: CofreFalso | None = None) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            cadastros.semear(con)
        self.backend = backend if backend is not None else CofreFalso()
        self.cofre = Cofre(tmp_path, self.backend)
        self.imap = ImapFalso()
        self.relogio = RelogioFalso(AGORA)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.cofre = self.cofre
        self.app.state.abrir_imap = self.imap
        self.app.state.relogio = self.relogio
        self.app.state.leitores = ()
        self.http = TestClient(
            self.app,
            base_url=f"http://127.0.0.1:{PORTA}",
            follow_redirects=False,
            headers={"Accept-Language": "pt"},
        )
        self.token: str = self.app.state.csrf

    def post(self, url: str, dados: dict[str, str] | None = None) -> Any:
        return self.http.post(
            url, data={CAMPO_CSRF: self.token, **(dados or {})}, headers={"HX-Request": "true"}
        )

    def salvar(self, endereco: str = ENDERECO, senha: str = SENHA) -> Any:
        return self.post(SALVAR, {"endereco": endereco, "senha": senha})

    def sessao(self) -> Any:
        with closing(abrir(self.banco)) as con:
            return ler_sessao(con, "conta", nucleo_gmail.CONTA)

    def gravar_sessao(self, estado: Any, motivo: Any, quando: datetime) -> None:
        with closing(abrir(self.banco)) as con:
            gravar_sessao(con, "conta", nucleo_gmail.CONTA, estado, motivo, quando)
            con.commit()

    def guardar(self) -> None:
        """Credencial já no cofre, como depois de um "Salvar e conferir" que deu certo."""
        self.cofre.gravar(nucleo_gmail.NOME_SENHA, LIMPA)
        self.cofre.gravar(nucleo_gmail.NOME_CONTA, ENDERECO)

    def nomes(self) -> tuple[Any, Any]:
        return (self.cofre.ler(nucleo_gmail.NOME_SENHA), self.cofre.ler(nucleo_gmail.NOME_CONTA))


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _texto(html: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html_lib.unescape(sem_tags))


# ------------------------------------------------------------------ Salvar e conferir


def test_salvar_ok_guarda_e_conecta(painel: Painel) -> None:
    resposta = painel.salvar()
    assert resposta.status_code == 200
    assert painel.cofre.ler(nucleo_gmail.NOME_SENHA) == (LIMPA, "sistema")
    assert painel.cofre.ler(nucleo_gmail.NOME_CONTA) == (ENDERECO, "sistema")
    sessao = painel.sessao()
    assert sessao is not None and sessao.estado == "conectado"
    assert "Conectado" in _texto(resposta.text)
    assert resposta.headers.get("HX-Trigger") == "contas-mudou"
    assert 'id="conta-gmail"' in resposta.text


def test_salvar_recusada_nao_guarda(painel: Painel) -> None:
    painel.imap.modo = "recusada"
    resposta = painel.salvar()
    assert resposta.status_code == 200
    assert painel.imap.logins == [(ENDERECO, LIMPA)]  # o fluxo chegou ao Google
    assert painel.nomes() == (None, None)
    assert painel.backend.guardado == {}
    assert painel.sessao() is None
    texto = _texto(resposta.text)
    assert "Nunca entrou" in texto
    assert "O Google recusou a senha. Confira o endereço ou crie outra senha de app." in texto


def test_salvar_sem_rede_nao_guarda(painel: Painel) -> None:
    painel.imap.modo = "sem_rede"
    resposta = painel.salvar()
    assert resposta.status_code == 200
    texto = _texto(resposta.text)
    assert "Sem internet ou o site não respondeu. A senha não foi guardada." in texto
    assert painel.nomes() == (None, None)
    assert painel.backend.guardado == {}
    assert painel.sessao() is None


def test_salvar_senha_torta_nao_chama_o_google(painel: Painel) -> None:
    resposta = painel.salvar(senha="abcd efgh ijkl")
    assert resposta.status_code == 200
    assert painel.imap.logins == []
    assert "A senha de app tem 16 letras. Copie de novo da página do Google." in _texto(
        resposta.text
    )
    assert 'aria-invalid="true"' in resposta.text
    assert painel.nomes() == (None, None)
    # controle: a mesma montagem com a senha certa chega ao Google
    painel.salvar()
    assert painel.imap.logins == [(ENDERECO, LIMPA)]


def test_salvar_endereco_torto_nao_chama_o_google(painel: Painel) -> None:
    resposta = painel.salvar(endereco="sem arroba")
    assert painel.imap.logins == []
    assert "Digite um endereço de e-mail, como nome@gmail.com." in _texto(resposta.text)
    assert 'aria-invalid="true"' in resposta.text
    assert painel.nomes() == (None, None)


def test_senha_nunca_volta(
    painel: Painel,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.DEBUG)
    respostas = [painel.salvar()]
    painel.relogio._agora += timedelta(seconds=601)  # fora do intervalo: o conferir roda
    respostas.append(painel.post(CONFERIR))
    respostas.append(painel.http.get(CONTAS))
    painel.imap.modo = "recusada"
    respostas.append(painel.salvar())
    # os caminhos que logam: o prazo do Google estourado e o cofre que falha
    monkeypatch.setattr(gmail, "PRAZO_GMAIL_S", 0.01)
    painel.imap.modo = "ok"
    painel.relogio._agora += timedelta(seconds=601)
    painel.imap.espera = threading.Event()
    try:
        respostas.append(painel.post(CONFERIR))
    finally:
        painel.imap.espera.set()  # solta a thread presa do IMAP
    quebrado = tmp_path / "quebrado"
    quebrado.mkdir()
    (quebrado / "gmail_senha_de_app.segredo").symlink_to(tmp_path / "fora.txt")
    outro = Painel(quebrado, CofreFalso(falha=RuntimeError("cofre fora")))
    respostas.append(outro.salvar())
    for resposta in respostas:
        assert resposta.status_code == 200
        assert LIMPA not in resposta.text
        assert SENHA not in resposta.text
    log = caplog.text
    nomes = {registro.name for registro in caplog.records}
    # o fluxo chegou aos loggers que veem a senha: o do núcleo (IMAP) e o da rota (prazo, cofre)
    assert {"jobot.nucleo.gmail", "jobot.painel.rotas.gmail"} <= nomes
    for segredo in (LIMPA, SENHA, ENDERECO):
        assert segredo not in log
    # controle positivo: o fluxo rodou de verdade, com a senha limpa, e os caminhos de falha
    assert "Conectado" in _texto(respostas[0].text)
    assert painel.imap.logins[0] == (ENDERECO, LIMPA)
    assert len(painel.imap.logins) == 4
    assert "Sem internet ou o site não respondeu." in _texto(respostas[4].text)
    # cofre fora de vez: o apagar também falha, e a frase é a do "não apagada" (R1)
    assert "A senha não foi apagada." in _texto(respostas[5].text)
    assert outro.imap.logins == [(ENDERECO, LIMPA)]


def test_cofre_que_falha_nao_deixa_meia_credencial(tmp_path: Path) -> None:
    dados = tmp_path / "dados"
    dados.mkdir()
    fora = tmp_path / "fora.txt"
    fora.write_text("não mexa", encoding="utf-8")
    (dados / "gmail_conta.segredo").symlink_to(fora)
    painel = Painel(dados, CofreFalso(falha=NoKeyringError()))
    resposta = painel.salvar()
    assert resposta.status_code == 200
    assert painel.imap.logins == [(ENDERECO, LIMPA)]  # o login foi aceito
    assert painel.nomes() == (None, None)
    assert not (dados / "gmail_senha_de_app.segredo").exists()
    assert fora.read_text(encoding="utf-8") == "não mexa"
    assert painel.sessao() is None
    assert "O cofre do sistema não respondeu. A senha não foi guardada." in _texto(resposta.text)


def _gravar_endereco_falha(painel: Painel, monkeypatch: pytest.MonkeyPatch) -> None:
    """A gravação do endereço (a segunda da troca) levanta; a da senha passa."""
    original = painel.cofre.gravar

    def gravar(nome: str, valor: str) -> Any:
        if nome == nucleo_gmail.NOME_CONTA:
            raise OSError("sem cofre")
        return original(nome, valor)

    monkeypatch.setattr(painel.cofre, "gravar", gravar)


def test_troca_que_falha_e_nao_apaga_nao_diz_conectado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path, CofreFalso(recusa_apagar=True))
    painel.guardar()
    painel.gravar_sessao("conectado", None, AGORA - timedelta(hours=1))
    _gravar_endereco_falha(painel, monkeypatch)
    resposta = painel.salvar("outra.pessoa@gmail.com", "zzzz yyyy xxxx wwww")
    assert resposta.status_code == 200
    assert painel.imap.logins == [("outra.pessoa@gmail.com", "zzzzyyyyxxxxwwww")]  # controle
    sessao = painel.sessao()
    assert sessao is not None
    assert sessao.estado != "conectado"
    texto = _texto(resposta.text)
    assert "Conectado" not in texto
    assert "não foi guardada" not in texto
    assert "O cofre do sistema não respondeu. A senha não foi apagada. Tente de novo." in texto
    assert 'data-alerta-abre="alerta-gmail-remover"' in resposta.text


def test_troca_que_falha_e_apaga_fecha_a_queda(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel.guardar()
    painel.gravar_sessao("conectado", None, AGORA - timedelta(hours=1))
    painel.imap.modo = "recusada"
    painel.relogio._agora += timedelta(seconds=601)
    painel.post(CONFERIR)  # abre a queda, com aviso
    assert "Gmail" in _texto(painel.http.get("/aviso-contas").text)  # controle
    painel.imap.modo = "ok"
    _gravar_endereco_falha(painel, monkeypatch)
    resposta = painel.salvar()
    assert resposta.status_code == 200
    assert painel.nomes() == (None, None)
    sessao = painel.sessao()
    assert sessao is not None
    assert (sessao.estado, sessao.motivo) == ("precisa_entrar", "esquecido")
    assert "Gmail" not in _texto(painel.http.get("/aviso-contas").text)
    assert "Nunca entrou" in _texto(resposta.text)


# ------------------------------------------------------------------ Conferir agora


def test_conferir_no_intervalo_nao_chama(painel: Painel) -> None:
    painel.guardar()
    painel.gravar_sessao("conectado", None, AGORA - timedelta(seconds=599))
    resposta = painel.post(CONFERIR)
    assert resposta.status_code == 200
    assert painel.imap.logins == []
    sessao = painel.sessao()
    assert (
        sessao is not None and sessao.conferido_em == (AGORA - timedelta(seconds=599)).isoformat()
    )
    # controle: 1 s depois o mesmo pedido confere e grava
    painel.relogio._agora += timedelta(seconds=1)
    resposta = painel.post(CONFERIR)
    assert painel.imap.logins == [(ENDERECO, LIMPA)]
    depois = painel.sessao()
    assert depois is not None and depois.conferido_em == painel.relogio.agora().isoformat()
    assert resposta.headers.get("HX-Trigger") == "contas-mudou"


def test_conferir_recusada_abre_queda_sem_aviso(painel: Painel) -> None:
    painel.guardar()
    painel.gravar_sessao("conectado", None, AGORA - timedelta(hours=1))
    assert painel.http.get("/aviso-contas").text.strip() == ""  # controle: sem queda
    painel.imap.modo = "recusada"
    resposta = painel.post(CONFERIR)
    assert resposta.status_code == 200
    sessao = painel.sessao()
    assert sessao is not None
    assert (sessao.estado, sessao.motivo) == ("precisa_entrar", None)
    assert sessao.avisado_em == AGORA.isoformat()
    assert "Sua sessão no Gmail caiu." in _texto(painel.http.get("/aviso-contas").text)
    assert "Precisa entrar de novo" in _texto(resposta.text)


def test_conferir_sem_rede_mantem_a_faixa(painel: Painel) -> None:
    painel.guardar()
    painel.gravar_sessao("conectado", None, AGORA - timedelta(hours=2))
    painel.gravar_sessao("precisa_entrar", None, AGORA - timedelta(hours=1))
    antes = painel.sessao()
    assert antes is not None
    aberta = antes.avisado_em
    assert aberta is not None
    painel.imap.modo = "sem_rede"
    resposta = painel.post(CONFERIR)
    assert painel.imap.logins == [(ENDERECO, LIMPA)]
    sessao = painel.sessao()
    assert sessao is not None
    assert (sessao.estado, sessao.motivo, sessao.avisado_em) == ("nao_conferiu", "sem_rede", aberta)
    assert "Sua sessão no Gmail caiu." in _texto(painel.http.get("/aviso-contas").text)
    assert "Sem internet ou o site não respondeu." in _texto(resposta.text)


def test_prazo_estourado_vira_sem_rede(painel: Painel, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gmail, "PRAZO_GMAIL_S", 0.01)
    painel.guardar()
    painel.imap.espera = threading.Event()
    try:
        resposta = painel.post(CONFERIR)
    finally:
        painel.imap.espera.set()  # solta a thread presa do IMAP
    assert resposta.status_code == 200
    sessao = painel.sessao()
    assert sessao is not None and (sessao.estado, sessao.motivo) == ("nao_conferiu", "sem_rede")


def test_conferir_sem_credencial_nao_chama(painel: Painel) -> None:
    resposta = painel.post(CONFERIR)
    assert resposta.status_code == 200
    assert painel.imap.logins == []
    assert painel.sessao() is None


# ------------------------------------------------------------------ Remover


def test_remover_apaga_e_volta_a_nunca_entrou(painel: Painel) -> None:
    painel.salvar()
    painel.imap.modo = "recusada"
    painel.relogio._agora += timedelta(seconds=601)
    painel.post(CONFERIR)  # abre a queda: a faixa aparece
    assert "Gmail" in _texto(painel.http.get("/aviso-contas").text)
    resposta = painel.post(REMOVER)
    assert resposta.status_code == 200
    assert painel.nomes() == (None, None)
    assert painel.backend.guardado == {}
    sessao = painel.sessao()
    assert sessao is not None
    assert (sessao.estado, sessao.motivo) == ("precisa_entrar", "esquecido")
    assert "Nunca entrou" in _texto(resposta.text)
    assert resposta.headers.get("HX-Trigger") == "contas-mudou"
    assert painel.http.get("/aviso-contas").text.strip() == ""


def test_remover_tem_alerta(painel: Painel) -> None:
    painel.guardar()
    html = painel.http.get(CONTAS).text
    assert 'data-alerta-abre="alerta-gmail-remover"' in html
    dialogo = re.search(r'<dialog id="alerta-gmail-remover".*?</dialog>', html, re.S)
    assert dialogo is not None
    assert 'hx-post="/configuracoes/gmail/remover"' in dialogo.group(0)
    assert 'hx-swap="outerHTML"' in dialogo.group(0)
    assert "Remover a senha de app do Gmail?" in _texto(dialogo.group(0))
    # o "Remover" não confere nada: sem o indicador do "Conferindo…" (C6)
    assert "hx-indicator" not in dialogo.group(0)


def test_remover_pela_metade_mantem_o_remover(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(recusa_apagar=True))
    painel.cofre.gravar(nucleo_gmail.NOME_SENHA, LIMPA)  # no sistema, que não apaga
    (tmp_path / "gmail_conta.segredo").write_text(ENDERECO, encoding="utf-8")  # no arquivo: sai
    assert painel.nomes() == ((LIMPA, "sistema"), (ENDERECO, "arquivo"))
    resposta = painel.post(REMOVER)
    assert resposta.status_code == 200
    assert painel.nomes() == ((LIMPA, "sistema"), None)  # a senha ficou
    assert 'data-alerta-abre="alerta-gmail-remover"' in resposta.text
    assert "Conferir agora" not in _texto(resposta.text)  # a credencial não está inteira
    assert "A senha não foi apagada. Tente de novo." in _texto(resposta.text)
    # recarregada, sem falha a mostrar, a página ainda deixa remover o que sobrou
    recarregada = painel.http.get(CONTAS).text
    assert 'data-alerta-abre="alerta-gmail-remover"' in recarregada
    assert "Conferir agora" not in _texto(recarregada)


def test_so_o_endereco_guardado_nao_e_credencial(painel: Painel) -> None:
    painel.cofre.gravar(nucleo_gmail.NOME_CONTA, ENDERECO)
    painel.gravar_sessao("conectado", None, AGORA - timedelta(hours=1))
    html = painel.http.get(CONTAS).text
    assert "Há uma senha de app guardada" not in _texto(html)
    assert "Conferir agora" not in _texto(html)
    assert 'data-alerta-abre="alerta-gmail-remover"' in html  # sobra algo a remover
    painel.guardar()  # controle: inteira, a frase e o botão aparecem
    inteira = _texto(painel.http.get(CONTAS).text)
    assert "Há uma senha de app guardada" in inteira
    assert "Conferir agora" in inteira


def test_remover_cofre_falha_nao_grava(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(recusa_apagar=True))
    painel.guardar()
    resposta = painel.post(REMOVER)
    assert resposta.status_code == 200
    assert painel.sessao() is None
    assert painel.nomes() == ((LIMPA, "sistema"), (ENDERECO, "sistema"))
    assert "HX-Trigger" not in resposta.headers
    texto = _texto(resposta.text)
    assert "O cofre do sistema não respondeu. A senha não foi apagada. Tente de novo." in texto
    assert "não foi guardada" not in texto


def test_leitura_do_cofre_falhando_no_get(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limites, "PRAZO_COFRE_S", 0.05)
    trava = threading.Event()
    painel = Painel(tmp_path, CofreFalso(trava=trava))
    try:
        html = painel.http.get(CONTAS).text
    finally:
        trava.set()  # solta as threads presas no cofre
    cartao = re.search(r'<section id="conta-gmail".*?</section>', html, re.S)
    assert cartao is not None
    texto = _texto(cartao.group(0))
    assert "O cofre do sistema não respondeu." in texto
    assert "não foi guardada" not in texto
    assert "não foi apagada" not in texto
    # sem saber o que há no cofre, o "Remover" fica à mão
    assert 'data-alerta-abre="alerta-gmail-remover"' in cartao.group(0)


# ------------------------------------------------------------------ sem JavaScript (C4)


def _sem_js(painel: Painel, url: str, dados: dict[str, str] | None = None) -> Any:
    return painel.http.post(url, data={CAMPO_CSRF: painel.token, **(dados or {})})


def test_sem_js_as_tres_rotas_voltam_a_contas(painel: Painel) -> None:
    salvar = _sem_js(painel, SALVAR, {"endereco": ENDERECO, "senha": SENHA})
    assert salvar.status_code == 303
    assert salvar.headers["location"] == "/configuracoes/contas?salvo=1"
    assert painel.nomes() == ((LIMPA, "sistema"), (ENDERECO, "sistema"))
    painel.relogio._agora += timedelta(seconds=601)
    conferir = _sem_js(painel, CONFERIR)
    assert conferir.status_code == 303
    assert conferir.headers["location"] == "/configuracoes/contas"
    assert len(painel.imap.logins) == 2
    remover = _sem_js(painel, REMOVER)
    assert remover.status_code == 303
    assert remover.headers["location"] == "/configuracoes/contas?salvo=1"
    assert painel.nomes() == (None, None)
    assert "Salvo." in _texto(painel.http.get(remover.headers["location"]).text)
    # controle: com o HTMX, o cartão
    assert painel.salvar().status_code == 200


@pytest.mark.parametrize(
    ("dados", "modo", "codigo", "frase"),
    [
        ({"endereco": "sem arroba"}, "ok", "gmail_endereco", "Digite um endereço de e-mail"),
        ({"senha": "abcd"}, "ok", "gmail_senha", "A senha de app tem 16 letras."),
        ({}, "recusada", "gmail_recusada", "O Google recusou a senha."),
        (
            {},
            "sem_rede",
            "gmail_sem_rede",
            "Sem internet ou o site não respondeu. A senha não foi guardada.",
        ),
    ],
)
def test_sem_js_salvar_mostra_o_erro(
    painel: Painel, dados: dict[str, str], modo: str, codigo: str, frase: str
) -> None:
    painel.imap.modo = modo
    resposta = _sem_js(painel, SALVAR, {"endereco": ENDERECO, "senha": SENHA} | dados)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/configuracoes/contas?erro={codigo}"
    assert frase in _texto(painel.http.get(resposta.headers["location"]).text)
    assert painel.nomes() == (None, None)


def test_sem_js_cofre_que_falha_no_remover(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(recusa_apagar=True))
    painel.guardar()
    resposta = _sem_js(painel, REMOVER)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/configuracoes/contas?erro=gmail_cofre_remover"
    texto = _texto(painel.http.get(resposta.headers["location"]).text)
    assert "O cofre do sistema não respondeu. A senha não foi apagada. Tente de novo." in texto


def test_erro_do_gmail_na_url_e_lista_fechada(painel: Painel) -> None:
    frase = "A senha de app tem 16 letras."
    assert frase in _texto(painel.http.get(CONTAS + "?erro=gmail_senha").text)  # controle
    lixo = painel.http.get(CONTAS + "?erro=%3Cb%3Elixo%3C%2Fb%3E")
    assert lixo.status_code == 200
    assert frase not in _texto(lixo.text)
    assert "<b>lixo" not in lixo.text  # nada da URL vira HTML (ela só volta codificada)
    assert frase not in _texto(painel.http.get("/configuracoes/geral?erro=gmail_senha").text)


def test_sem_js_conferir_recusada_nao_diz_salvo(painel: Painel) -> None:
    painel.guardar()
    painel.gravar_sessao("conectado", None, AGORA - timedelta(hours=1))
    painel.imap.modo = "recusada"
    resposta = _sem_js(painel, CONFERIR)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == CONTAS
    assert len(painel.imap.logins) == 1  # controle: o Google foi chamado
    texto = _texto(painel.http.get(CONTAS).text)
    assert "Precisa entrar de novo" in texto
    assert "Salvo." not in texto


def test_remover_sem_js_pergunta_numa_pagina(painel: Painel) -> None:
    # sem leitor de site (o `Painel` não tem): o Gmail vale sem leitor (E13)
    painel.guardar()
    resposta = painel.http.get(REMOVER + "/confirmar")
    assert resposta.status_code == 200
    assert painel.nomes() == ((LIMPA, "sistema"), (ENDERECO, "sistema"))  # o GET não apaga
    assert '<form method="post" action="/configuracoes/gmail/remover">' in resposta.text
    assert 'href="/configuracoes/contas"' in resposta.text
    assert "Remover a senha de app do Gmail?" in _texto(resposta.text)
    # na aba, o botão é um GET para a confirmação; o POST mora só no <dialog>
    html = re.sub(r"<dialog.*?</dialog>", "", painel.http.get(CONTAS).text, flags=re.S)
    assert '<form method="get" action="/configuracoes/gmail/remover/confirmar">' in html
    assert 'action="/configuracoes/gmail/remover"' not in html


# ------------------------------------------------------------------ foco e anúncio (C3)


def _abre(padrao: str, html: str) -> str:
    achado = re.search(padrao, html, re.S)
    assert achado is not None, padrao
    return achado.group(0)


def test_resposta_leva_o_foco_e_anuncia(painel: Painel) -> None:
    senha = r'<input [^>]*name="senha"[^>]*>'
    endereco = r'<input [^>]*name="endereco"[^>]*>'
    secao = r'<section id="conta-gmail"[^>]*>'
    torta = painel.salvar(senha="abcd").text
    assert "data-foco" in _abre(senha, torta) and 'aria-invalid="true"' in _abre(senha, torta)
    assert "data-foco" not in _abre(secao, torta)
    assert "data-foco" in _abre(endereco, painel.salvar(endereco="sem arroba").text)
    certa = painel.salvar().text
    assert "data-foco-se-livre" in _abre(secao, certa)
    assert 'tabindex="-1"' in _abre(secao, certa)
    assert "data-foco" not in _abre(senha, certa)
    anuncio = _abre(r'<p hx-swap-oob="innerHTML:#status-gmail">.*?</p>', certa)
    assert "Gmail: Conectado." in _texto(anuncio)
    pagina = painel.http.get(CONTAS).text
    assert re.search(r'<p id="status-gmail" role="status" aria-live="polite"', pagina)
    assert "data-foco" not in _abre(r'<section id="conta-gmail".*?</section>', pagina)


# ------------------------------------------------------------------ rotas e cartão


def test_rotas_do_gmail_casam_primeiro(painel: Painel) -> None:
    # o FastAPI embrulha cada `include_router` num roteador próprio, na ordem de inclusão: o
    # primeiro que casa por inteiro é o que atende, e tem de ser o do Gmail
    rotas = criar_app(painel.banco.parent, PORTA).routes
    for minha in gmail.router.routes:
        assert isinstance(minha, APIRoute)
        for metodo in minha.methods or ():
            escopo = {"type": "http", "path": minha.path, "method": metodo}
            primeira = next(r for r in rotas if r.matches(escopo)[0] == Match.FULL)
            dono = getattr(primeira, "original_router", primeira)
            assert dono is gmail.router or getattr(dono, "endpoint", None) is minha.endpoint, (
                minha.path
            )
    painel.guardar()
    resposta = painel.post(CONFERIR)
    assert resposta.status_code == 200
    assert painel.imap.logins == [(ENDERECO, LIMPA)]


@pytest.mark.parametrize(
    ("idioma", "pagina"), [("pt", "Gmail-senha-de-app"), ("en", "Gmail-app-password")]
)
def test_tutorial_no_idioma(painel: Painel, idioma: str, pagina: str) -> None:
    html = painel.http.get(CONTAS, headers={"Accept-Language": idioma}).text
    link = re.search(rf'<a [^>]*href="[^"]*/wiki/{pagina}"[^>]*>', html)
    assert link is not None
    assert 'target="_blank"' in link.group(0)
    assert 'rel="noopener noreferrer"' in link.group(0)


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize("credencial", [False, True])
def test_cartao_avisa_acesso_total(painel: Painel, idioma: str, credencial: bool) -> None:
    if credencial:
        painel.guardar()
    html = painel.http.get(CONTAS, headers={"Accept-Language": idioma}).text
    cartao = re.search(r'<section id="conta-gmail".*?</section>', html, re.S)
    assert cartao is not None
    assert ACESSO[idioma] in _texto(cartao.group(0))


def test_aviso_no_arquivo(tmp_path: Path) -> None:
    painel = Painel(tmp_path, CofreFalso(falha=NoKeyringError()))
    sem = _texto(painel.http.get(CONTAS).text)
    assert "a senha ficou num arquivo" not in sem  # controle: sem credencial, sem aviso
    painel.guardar()
    assert painel.nomes()[0] == (LIMPA, "arquivo")
    texto = _texto(painel.http.get(CONTAS).text)
    assert "Sem cofre do sistema: a senha ficou num arquivo que só o seu usuário lê." in texto


def test_campo_da_senha_sempre_vazio(painel: Painel) -> None:
    painel.guardar()
    html = painel.http.get(CONTAS).text
    campo = re.search(r'<input [^>]*name="senha"[^>]*>', html)
    assert campo is not None
    assert "value=" not in campo.group(0)
    assert 'type="password"' in campo.group(0)
    assert 'autocomplete="off"' in campo.group(0)
    endereco = re.search(r'<input [^>]*name="endereco"[^>]*>', html)
    assert endereco is not None and f'value="{ENDERECO}"' in endereco.group(0)
    assert "Há uma senha de app guardada. Para trocar, cole outra." in _texto(html)
