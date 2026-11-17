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
from pathlib import Path
from typing import Literal

from jobot.navegador import limites
from jobot.navegador.abrir import ambiente_do_navegador
from jobot.navegador.janela_comum import AbrirJanela, Janela, encerrar
from jobot.sistema import processo as _processo

_LOG = logging.getLogger(__name__)

Resultado = Literal["pronto", "falhou"]

# O subcomando da casca baixa e grava em Python: no Windows, sem estas o `Path.home()` levanta e
# o socket não abre (WinError 10106). Nenhuma leva segredo; fora do Windows não existem.
_DO_WINDOWS = ("LOCALAPPDATA", "USERPROFILE", "SYSTEMROOT", "TEMP", "TMP")


def comando_de_baixar() -> list[str]:
    """Só o Chromium, sem o headless shell e sem `--with-deps` (que pede sudo)."""
    return [sys.executable, "-P", "-m", "playwright", "install", "--no-shell", "chromium"]


def comando_de_baixar_pela_casca() -> list[str]:
    """Canal `casca`: o subcomando baixa o Chromium da release do joBot (T330; D174.2)."""
    return [sys.executable, "-P", "-m", "jobot", "ferramentas", "baixar", "navegador"]


def comando_de_remover() -> list[str]:
    """Sem `--all`: o Playwright só apaga o que nenhuma outra instalação dele usa."""
    return [sys.executable, "-P", "-m", "playwright", "uninstall"]


def ambiente_de_instalar(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """O mesmo ambiente enxuto da janela, mais a pasta dos navegadores se a pessoa mudou."""
    amb = ambiente_do_navegador(extra or {})
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
        with contextlib.suppress(ProcessLookupError):  # líder saiu; no POSIX um filho pode ficar
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
    abrir: AbrirJanela,
    argumentos: list[str],
    prazo: float,
    *,
    cancelar_encerra: bool,
    ambiente: Mapping[str, str] | None = None,
) -> Resultado:
    try:
        janela = await abrir(argumentos, ambiente_de_instalar(ambiente))
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


async def baixar_chromium(abrir: AbrirJanela, dados_da_casca: Path | None = None) -> Resultado:
    """Cancelar (o painel fechando) encerra o download: arquivo pela metade não vale nada.
    Com a pasta de dados do canal `casca`, roda o subcomando que baixa da release, com o
    `JOBOT_DADOS` para ele achar o mesmo `instalacao.json` e as `_DO_WINDOWS`."""
    if dados_da_casca is None:
        comando, ambiente = comando_de_baixar(), None
    else:
        comando = comando_de_baixar_pela_casca()
        ambiente = {n: os.environ[n] for n in _DO_WINDOWS if n in os.environ}
        ambiente["JOBOT_DADOS"] = str(dados_da_casca)
    return await _rodar(
        abrir, comando, limites.PRAZO_BAIXAR_S, cancelar_encerra=True, ambiente=ambiente
    )


async def remover_chromium(abrir: AbrirJanela) -> Resultado:
    """Cancelar não interrompe a remoção: pasta apagada pela metade é pior que inteira (D137.13)."""
    return await _rodar(
        abrir, comando_de_remover(), limites.PRAZO_REMOVER_S, cancelar_encerra=False
    )
