"""Janela comum do navegador para o login (D136.1 a D136.8).

É o processo do navegador aberto direto, sem Playwright e sem automação: só o perfil do joBot e
o endereço de login. Quem digita é a pessoa; nada é injetado na página. O joBot só espera a
janela fechar (ou o prazo acabar) e depois confere a sessão pela janela automática.
"""

import asyncio
import contextlib
import logging
import os
import re
import socket
from asyncio.subprocess import DEVNULL
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from jobot.navegador import limites
from jobot.navegador.abrir import caminho_do_navegador
from jobot.nucleo.modelo import confere_http

_LOG = logging.getLogger(__name__)


class Janela(Protocol):
    """O que o joBot usa do processo da janela (o `Process` do `asyncio` serve)."""

    async def wait(self) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


AbrirJanela = Callable[[Sequence[str], Mapping[str, str]], Awaitable[Janela]]


@dataclass(frozen=True)
class JanelaComum:
    caminho: Callable[[], Awaitable[Path | None]]
    abrir: AbrirJanela


def argumentos_da_janela(executavel: Path, perfil: Path, url: str) -> list[str]:
    """Só o perfil, os cookies legíveis pela janela automática e o endereço (D136.1)."""
    confere_http(url, "url_login")  # posicional: um endereço com "-" na frente viraria opção
    return [
        str(executavel),
        f"--user-data-dir={perfil}",
        "--password-store=basic",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]


def perfil_em_uso(perfil: Path) -> bool:
    """Lê o `SingletonLock` ("máquina-pid") do perfil; na dúvida, em uso (D136.5)."""
    try:
        alvo = os.readlink(perfil / "SingletonLock")
    except FileNotFoundError:
        return False
    except OSError as erro:
        _LOG.warning("trava do perfil não se lê como link (%s): perfil em uso", erro.strerror)
        return True
    maquina, _, pid = alvo.rpartition("-")
    if not maquina or not re.fullmatch("[0-9]{1,9}", pid):
        _LOG.warning("trava do perfil com alvo torto: perfil em uso")
        return True
    if maquina != socket.gethostname():
        _LOG.warning("trava do perfil de outra máquina: perfil em uso")
        return True
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # o processo existe, só não é nosso
        pass
    return True


def janela_de_producao() -> JanelaComum:
    async def abrir(argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        return await asyncio.create_subprocess_exec(
            *argumentos, env=dict(ambiente), stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL
        )

    return JanelaComum(caminho=caminho_do_navegador, abrir=abrir)


async def encerrar(janela: Janela) -> None:
    """SIGTERM, espera `limites.ESPERA_SAIR_JANELA_S` e só então SIGKILL (D136.3)."""
    with contextlib.suppress(ProcessLookupError):  # saiu entre o prazo e o sinal
        janela.terminate()
    try:
        async with asyncio.timeout(limites.ESPERA_SAIR_JANELA_S):
            await janela.wait()
        return
    except TimeoutError:
        pass
    with contextlib.suppress(ProcessLookupError):
        janela.kill()
    await janela.wait()


async def esperar_fechar(janela: Janela) -> bool:
    """`True` se saiu no prazo; senão a fecha e devolve `False`. Cancelar ou erro também fecham."""
    try:
        async with asyncio.timeout(limites.PRAZO_LOGIN_MANUAL_S):
            codigo = await janela.wait()
    except TimeoutError:
        await encerrar(janela)
        return False
    except BaseException:  # cancelamento ou erro na espera: a janela não fica aberta sozinha
        await encerrar(janela)
        raise
    if codigo != 0:
        _LOG.warning("janela comum saiu com o código %s", codigo)
    return True
