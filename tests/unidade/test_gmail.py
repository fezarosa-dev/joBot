"""Núcleo do Gmail: IMAP só para leitura, por um abridor falso (nenhum teste abre rede)."""

import imaplib
import logging
import ssl
from collections.abc import Callable
from typing import Any

import pytest

from jobot.nucleo import gmail

ENDERECO = "pessoa.inventada@exemplo.com.br"
SENHA = "qwertyuiopasdfgh"


class ImapFalso:
    """Guarda as chamadas; `levanta` diz em que passo levantar e `select_tipo` o que o select dá."""

    def __init__(self, levanta: dict[str, BaseException] | None = None, select_tipo: str = "OK"):
        self.chamadas: list[tuple[Any, ...]] = []
        self.levanta = levanta or {}
        self.select_tipo = select_tipo

    def _passo(self, nome: str) -> None:
        if nome in self.levanta:
            raise self.levanta[nome]

    def login(self, user: str, password: str) -> tuple[str, list[Any]]:
        self.chamadas.append(("login", user, password))
        self._passo("login")
        return "OK", [b"logado"]

    def select(self, mailbox: str = "INBOX", readonly: bool = False) -> tuple[str, list[Any]]:
        self.chamadas.append(("select", mailbox, readonly))
        self._passo("select")
        return self.select_tipo, [b"x"]

    def logout(self) -> tuple[str, list[Any]]:
        self.chamadas.append(("logout",))
        self._passo("logout")
        return "BYE", [b"tchau"]


def _abridor(imap: ImapFalso) -> Callable[[], ImapFalso]:
    return lambda: imap


def _recusa(funcao: Callable[[str], str], texto: str) -> bool:
    """True só se recusar com `ValueError` cuja mensagem não traz o texto recebido."""
    try:
        funcao(texto)
    except ValueError as erro:
        return texto.strip() not in str(erro)
    return False


def test_ok_abre_a_caixa_so_para_leitura() -> None:
    imap = ImapFalso()
    assert gmail.conferir_gmail(ENDERECO, SENHA, abrir=_abridor(imap)) == "ok"
    assert imap.chamadas == [("login", ENDERECO, SENHA), ("select", "INBOX", True), ("logout",)]


def test_authenticationfailed_vira_recusada() -> None:
    erro = imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials (Failure)")
    imap = ImapFalso(levanta={"login": erro})
    assert gmail.conferir_gmail(ENDERECO, SENHA, abrir=_abridor(imap)) == "recusada"
    assert imap.chamadas[-1] == ("logout",)


def test_outro_erro_de_login_vira_bloqueio() -> None:
    erro = imaplib.IMAP4.error("[ALERT] Please log in via your web browser")
    imap = ImapFalso(levanta={"login": erro})
    assert gmail.conferir_gmail(ENDERECO, SENHA, abrir=_abridor(imap)) == "bloqueio"
    assert imap.chamadas[-1] == ("logout",)


def _abridor_que_levanta(erro: BaseException) -> Callable[[], ImapFalso]:
    def abrir() -> ImapFalso:
        raise erro

    return abrir


@pytest.mark.parametrize(
    "abrir",
    [
        _abridor_que_levanta(OSError("rede")),
        _abridor_que_levanta(TimeoutError("prazo")),
        _abridor_que_levanta(ssl.SSLError("ssl")),
        _abridor(ImapFalso(levanta={"login": imaplib.IMAP4.abort("caiu")})),
    ],
    ids=["oserror", "timeout", "ssl", "abort_no_login"],
)
def test_rede_vira_sem_rede(abrir: Callable[[], ImapFalso]) -> None:
    assert gmail.conferir_gmail(ENDERECO, SENHA, abrir=abrir) == "sem_rede"


def test_select_que_nao_da_ok_vira_erro() -> None:
    """O logout que levanta é engolido e não muda o resultado."""
    imap = ImapFalso(select_tipo="NO", levanta={"logout": OSError("caiu no logout")})
    assert gmail.conferir_gmail(ENDERECO, SENHA, abrir=_abridor(imap)) == "erro"
    assert imap.chamadas[-1] == ("logout",)


def test_select_que_levanta_vira_erro() -> None:
    """Um IMAP4.error no select (depois do login) é 'erro', não 'bloqueio' (E8)."""
    imap = ImapFalso(levanta={"select": imaplib.IMAP4.error("SELECT recusado")})
    assert gmail.conferir_gmail(ENDERECO, SENHA, abrir=_abridor(imap)) == "erro"
    assert imap.chamadas[-1] == ("logout",)


def test_senha_e_endereco_fora_do_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    imap = ImapFalso(levanta={"login": RuntimeError("falhou")})
    assert gmail.conferir_gmail(ENDERECO, SENHA, abrir=_abridor(imap)) == "erro"
    assert "RuntimeError" in caplog.text
    assert SENHA not in caplog.text
    assert ENDERECO not in caplog.text


def test_limpar_senha_tira_espacos() -> None:
    assert gmail.limpar_senha(" abcd efgh\tijkl\nmnop ") == "abcdefghijklmnop"
    assert gmail.limpar_senha("ABCDEFGHIJKLMNOP") == "abcdefghijklmnop"


@pytest.mark.parametrize(
    "texto",
    ["abcdefghijklmno", "abcdefghijklmnopq", "abcdefghijklmno1", "abcdefghijklmnoé"],
    ids=["15_letras", "17_letras", "com_digito", "com_acento"],
)
def test_limpar_senha_recusa(texto: str) -> None:
    assert _recusa(gmail.limpar_senha, texto) is True


@pytest.mark.parametrize(
    "texto",
    [
        "nomeexemplo.com",
        "nome@outro@exemplo.com",
        "nome@exemplo",
        "no me@exemplo.com",
        "a" * 243 + "@exemplo.com",
        'no"me@exemplo.com',
        "no(me@exemplo.com",
        "no{me@exemplo.com",
        "no*me@exemplo.com",
        "joão@exemplo.com",
        "@exemplo.com",
    ],
    ids=[
        "sem_arroba",
        "dois_arrobas",
        "dominio_sem_ponto",
        "espaco_no_meio",
        "255_caracteres",
        "aspas",
        "parenteses",
        "chaves",
        "asterisco",
        "cedilha_e_til",
        "sem_parte_local",
    ],
)
def test_validar_endereco_recusa(texto: str) -> None:
    assert _recusa(gmail.validar_endereco, texto) is True
    assert gmail.validar_endereco(" nome@exemplo.com.br ") == "nome@exemplo.com.br"
    limite = "a" * 242 + "@exemplo.com"
    assert gmail.validar_endereco(limite) == limite


@pytest.mark.parametrize(
    ("resultado", "esperado"),
    [
        ("ok", ("conectado", None)),
        ("recusada", ("precisa_entrar", None)),
        ("bloqueio", ("nao_conferiu", "bloqueio")),
        ("sem_rede", ("nao_conferiu", "sem_rede")),
        ("erro", ("nao_conferiu", "erro")),
    ],
)
def test_estado_do_gmail_tabela(resultado: gmail.ResultadoGmail, esperado: tuple[str, Any]) -> None:
    assert gmail.estado_do_gmail(resultado) == esperado


def test_abrir_imap_ssl_usa_host_porta_prazo(monkeypatch: pytest.MonkeyPatch) -> None:
    guardado: dict[str, Any] = {}

    def falso(*args: Any, **kwargs: Any) -> ImapFalso:
        guardado["args"], guardado["kwargs"] = args, kwargs
        return ImapFalso()

    monkeypatch.setattr(imaplib, "IMAP4_SSL", falso)
    gmail.abrir_imap_ssl()
    assert guardado["args"] == ("imap.gmail.com", 993)
    assert guardado["kwargs"].get("timeout") == 20.0
    contexto = guardado["kwargs"].get("ssl_context")
    assert isinstance(contexto, ssl.SSLContext)
    assert contexto.check_hostname is True
