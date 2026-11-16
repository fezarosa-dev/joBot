"""Confere o login do Gmail por IMAP, só para leitura (ADR 0024).

O endereço e a senha de app chegam como texto e nunca saem daqui: não vão a log nem a mensagem
de erro."""

import contextlib
import imaplib
import logging
import ssl
from collections.abc import Callable
from typing import Any, Final, Literal, Protocol

from jobot.nucleo.contas import EstadoSessao, MotivoSessao

_LOG = logging.getLogger(__name__)

HOST: Final = "imap.gmail.com"
PORTA: Final = 993
PRAZO_S: Final = 20.0
NOME_CONTA: Final = "gmail_conta"
NOME_SENHA: Final = "gmail_senha_de_app"
CONTA: Final = "gmail"

ResultadoGmail = Literal["ok", "recusada", "bloqueio", "sem_rede", "erro"]


class Imap(Protocol):
    def login(self, user: str, password: str) -> tuple[str, list[Any]]: ...

    def select(self, mailbox: str = "INBOX", readonly: bool = False) -> tuple[str, list[Any]]: ...

    def logout(self) -> tuple[str, list[Any]]: ...


AbrirImap = Callable[[], Imap]


def abrir_imap_ssl() -> Imap:
    return imaplib.IMAP4_SSL(HOST, PORTA, ssl_context=ssl.create_default_context(), timeout=PRAZO_S)


_PROIBIDOS_NO_ENDERECO: Final = frozenset('"(){}%*\\')  # o imaplib manda o usuário sem aspas


def validar_endereco(texto: str) -> str:
    endereco = texto.strip()
    local, _, dominio = endereco.partition("@")
    if (
        len(endereco) > 254
        or not local
        or "." not in dominio
        or "@" in dominio
        or any(not "!" <= c <= "~" or c in _PROIBIDOS_NO_ENDERECO for c in endereco)
    ):
        raise ValueError("endereço do Gmail inválido")
    return endereco


def limpar_senha(texto: str) -> str:
    senha = "".join(texto.split())
    if len(senha) != 16 or not (senha.isascii() and senha.isalpha()):
        raise ValueError("a senha de app tem 16 letras")
    return senha.lower()


def conferir_gmail(
    endereco: str, senha: str, *, abrir: AbrirImap = abrir_imap_ssl
) -> ResultadoGmail:
    imap: Imap | None = None
    no_login = False
    falha: Exception | None = None
    resultado: ResultadoGmail = "erro"
    try:
        imap = abrir()
        no_login = True
        imap.login(endereco, senha)
        no_login = False
        tipo, _ = imap.select("INBOX", readonly=True)  # o imaplib manda EXAMINE
        resultado = "ok" if tipo == "OK" else "erro"
    except (OSError, imaplib.IMAP4.abort) as erro:
        falha = erro
        resultado = "sem_rede"
    except imaplib.IMAP4.error as erro:
        falha = erro
        if not no_login:
            resultado = "erro"
        elif "AUTHENTICATIONFAILED" in str(erro):
            resultado = "recusada"
        else:
            resultado = "bloqueio"
    except Exception as erro:
        _LOG.warning("Gmail: erro (%s)", type(erro).__name__, exc_info=True)
        return "erro"
    finally:
        if imap is not None:
            with contextlib.suppress(Exception):
                imap.logout()
    _LOG.info("Gmail: %s (%s)", resultado, type(falha).__name__ if falha else "sem exceção")
    return resultado


_ESTADOS: Final[dict[ResultadoGmail, tuple[EstadoSessao, MotivoSessao | None]]] = {
    "ok": ("conectado", None),
    "recusada": ("precisa_entrar", None),
    "bloqueio": ("nao_conferiu", "bloqueio"),
    "sem_rede": ("nao_conferiu", "sem_rede"),
    "erro": ("nao_conferiu", "erro"),
}


def estado_do_gmail(resultado: ResultadoGmail) -> tuple[EstadoSessao, MotivoSessao | None]:
    return _ESTADOS[resultado]
