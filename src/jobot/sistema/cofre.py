"""Cofre de segredos: o cofre de senhas do sistema (keyring, ADR 0014), com reserva em arquivo 0600.

Lê do sistema e depois do arquivo. Grava no sistema e confere lendo de volta; deu certo, apaga o
arquivo antigo; não deu, grava em `<pasta>/<nome>.segredo` (0600, nunca segue symlink) e tira a
cópia velha do sistema. O segredo nunca vai ao log nem a mensagem de erro: o log leva só o tipo
da exceção do cofre, sem `exc_info`.
"""

import logging
import os
import re
from pathlib import Path
from typing import Literal, Protocol

import keyring
from keyring.errors import NoKeyringError, PasswordDeleteError

SERVICO = "jobot"

OndeGuardou = Literal["sistema", "arquivo"]

_LOG = logging.getLogger(__name__)
_NOME = re.compile(r"[a-z0-9_]{1,32}", re.ASCII)
_MODO = 0o600
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class Backend(Protocol):
    def get_password(self, service: str, username: str, /) -> str | None: ...
    def set_password(self, service: str, username: str, password: str, /) -> None: ...
    def delete_password(self, service: str, username: str, /) -> None: ...


def _avisar(erro: Exception) -> None:
    # só o tipo: a mensagem da exceção pode carregar o segredo. Sem cofre (distrobox, Linux sem
    # ambiente gráfico) é o caminho normal: só DEBUG
    nivel = logging.DEBUG if isinstance(erro, NoKeyringError) else logging.WARNING
    _LOG.log(nivel, "cofre do sistema indisponível: %s", type(erro).__name__)


class Cofre:
    def __init__(self, pasta: Path, backend: Backend | None = None) -> None:
        self._pasta = pasta
        if backend is None:
            backend = keyring  # o módulo cumpre o protocolo
        self._backend = backend

    def _arquivo(self, nome: str) -> Path:
        if not _NOME.fullmatch(nome):
            raise ValueError("nome de segredo fora do padrão [a-z0-9_]{1,32}")
        return self._pasta / f"{nome}.segredo"

    def _do_sistema(self, nome: str) -> str | None:
        try:
            return self._backend.get_password(SERVICO, nome)
        except Exception as erro:
            _avisar(erro)
            return None

    def _tirar_do_sistema(self, nome: str) -> None:
        try:
            self._backend.delete_password(SERVICO, nome)
        except PasswordDeleteError:
            pass  # não existia
        except Exception as erro:
            _avisar(erro)

    def ler(self, nome: str) -> tuple[str, OndeGuardou] | None:
        caminho = self._arquivo(nome)
        valor = self._do_sistema(nome)
        if valor:
            return valor, "sistema"
        try:
            if caminho.is_symlink():
                return None
            fd = os.open(caminho, os.O_RDONLY | _O_NOFOLLOW | os.O_CLOEXEC)
            with os.fdopen(fd, encoding="utf-8") as arquivo:
                texto = arquivo.read().strip()
        except OSError, ValueError:  # ausente, ilegível ou fora de UTF-8
            return None
        return (texto, "arquivo") if texto else None

    def gravar(self, nome: str, valor: str) -> OndeGuardou:
        """Devolve onde guardou; levanta `OSError` quando nem o arquivo dá."""
        caminho = self._arquivo(nome)
        try:
            self._backend.set_password(SERVICO, nome, valor)
            conferido = self._backend.get_password(SERVICO, nome) == valor
        except Exception as erro:
            _avisar(erro)
            conferido = False
        if conferido:
            caminho.unlink(missing_ok=True)
            return "sistema"
        if caminho.is_symlink():
            raise OSError("o arquivo do segredo é um link simbólico")
        # nasce 0600 (o umask só tira bits); o fchmod acerta o arquivo antigo frouxo
        fd = os.open(
            caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _O_NOFOLLOW | os.O_CLOEXEC, _MODO
        )
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            os.fchmod(fd, _MODO)
            arquivo.write(valor)
        # shortcut: com o cofre trancado, a chave velha do sistema volta a valer depois do
        # desbloqueio; trocar se aparecer caso real.
        self._tirar_do_sistema(nome)  # não deixa chave velha no sistema
        return "arquivo"

    def apagar(self, nome: str) -> None:
        """Levanta `OSError` se o arquivo não sai ou se o segredo segue no sistema."""
        caminho = self._arquivo(nome)
        caminho.unlink(missing_ok=True)  # um symlink sai ele mesmo, sem tocar o alvo
        self._tirar_do_sistema(nome)
        confirmou = True
        resta: str | None = None
        try:
            resta = self._backend.get_password(SERVICO, nome)
        except NoKeyringError:
            pass  # sem cofre: não há o que apagar lá
        except Exception as erro:
            _avisar(erro)
            confirmou = False
        if not confirmou:  # fora do except: a exceção nova não carrega a do cofre
            raise OSError("o cofre não confirmou que apagou")
        if resta is not None:
            raise OSError("o cofre não apagou")
