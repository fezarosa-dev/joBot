"""Baixa e remove o Chromium do Playwright pelo painel (T240; D137.1 a D137.3 e D137.13).

O instalador é o próprio Playwright, chamado pelo Python do joBot (`-P` não põe a pasta atual no
caminho de importação). Ele roda num grupo de processos próprio: o `install` sobe um Node, e o
sinal tem de chegar a ele também, senão o download segue depois do "cancelar" ou do prazo.
"""

import asyncio
import contextlib
import logging
import os
import sys
from asyncio.subprocess import DEVNULL
from collections.abc import Mapping, Sequence
from typing import Literal

from jobot.navegador import limites
from jobot.navegador.abrir import ambiente_do_navegador
from jobot.navegador.janela_comum import AbrirJanela, Janela, encerrar
from jobot.sistema import processo as _processo

_LOG = logging.getLogger(__name__)

Resultado = Literal["pronto", "falhou"]


def comando_de_baixar() -> list[str]:
    """Só o Chromium, sem o headless shell e sem `--with-deps` (que pede sudo)."""
    return [sys.executable, "-P", "-m", "playwright", "install", "--no-shell", "chromium"]


def comando_de_remover() -> list[str]:
    """Sem `--all`: o Playwright só apaga o que nenhuma outra instalação dele usa."""
    return [sys.executable, "-P", "-m", "playwright", "uninstall"]


def ambiente_de_instalar() -> dict[str, str]:
    """O mesmo ambiente enxuto da janela, mais a pasta dos navegadores se a pessoa mudou."""
    amb = ambiente_do_navegador({})
    pasta = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if pasta is not None:
        amb["PLAYWRIGHT_BROWSERS_PATH"] = pasta
    return amb


class _Grupo:
    """O processo líder visto como `Janela`, com os sinais indo para o grupo inteiro."""

    def __init__(self, processo: asyncio.subprocess.Process) -> None:
        self._processo = processo

    async def wait(self) -> int:
        codigo = await self._processo.wait()
        with contextlib.suppress(ProcessLookupError):  # o líder saiu; um filho pode ter ficado
            _processo.encerrar_grupo(self._processo, forcar=True)
        return codigo

    def terminate(self) -> None:
        _processo.encerrar_grupo(self._processo)

    def kill(self) -> None:
        _processo.encerrar_grupo(self._processo, forcar=True)


async def abrir_instalador(argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
    processo = await asyncio.create_subprocess_exec(
        *argumentos,
        env=dict(ambiente),
        stdin=DEVNULL,
        stdout=DEVNULL,
        stderr=DEVNULL,
        **_processo.destacar(),
    )
    return _Grupo(processo)


async def _rodar(
    abrir: AbrirJanela, argumentos: list[str], prazo: float, *, cancelar_encerra: bool
) -> Resultado:
    try:
        janela = await abrir(argumentos, ambiente_de_instalar())
    except OSError:
        _LOG.exception("não deu para abrir o instalador do navegador")
        return "falhou"
    try:
        async with asyncio.timeout(prazo):
            codigo = await janela.wait()
    except TimeoutError:
        _LOG.warning("o instalador do navegador passou do prazo de %s s", prazo)
        await encerrar(janela)
        return "falhou"
    except asyncio.CancelledError:
        if cancelar_encerra:
            await encerrar(janela)
        raise
    if codigo != 0:
        _LOG.warning("instalador saiu com o código %s", codigo)
        return "falhou"
    return "pronto"


async def baixar_chromium(abrir: AbrirJanela) -> Resultado:
    """Cancelar (o painel fechando) encerra o download: arquivo pela metade não vale nada."""
    return await _rodar(abrir, comando_de_baixar(), limites.PRAZO_BAIXAR_S, cancelar_encerra=True)


async def remover_chromium(abrir: AbrirJanela) -> Resultado:
    """Cancelar não interrompe a remoção: pasta apagada pela metade é pior que inteira (D137.13)."""
    return await _rodar(
        abrir, comando_de_remover(), limites.PRAZO_REMOVER_S, cancelar_encerra=False
    )
