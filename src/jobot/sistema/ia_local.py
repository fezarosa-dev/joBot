"""O modelo local no disco: o manifesto dos recursos, a anotação do que baixou e o comando que
baixa (T409; T417; D202.2).

O `jobot ferramentas ... ia-local` (`cli/ferramentas.py`) baixa e anota; a tela Ferramentas do
painel lê a anotação e o manifesto daqui e roda o mesmo comando como processo filho, lendo as
linhas JSON da saída, como a casca (desenho 10.1 e 10.2 da fase 4).
"""

import asyncio
import json
import os
import sys
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from typing import Any

from jobot.sistema import processo
from jobot.sistema.pastas import PASTA_FERRAMENTAS

ANOTACAO = "ia_local.json"


def manifesto_local() -> dict[str, Any]:
    """`nucleo/dados/ia_local.json` (T407; D193)."""
    arquivo = resources.files("jobot.nucleo").joinpath("dados", "ia_local.json")
    dados: dict[str, Any] = json.loads(arquivo.read_text(encoding="utf-8"))
    return dados


def ler_anotacao(dados: Path) -> dict[str, Any]:
    """O que está baixado (`<dados>/ferramentas/ia_local.json`); sem arquivo ou estragado: `{}`."""
    try:
        anotacao = json.loads((dados / PASTA_FERRAMENTAS / ANOTACAO).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return anotacao if isinstance(anotacao, dict) else {}


def comando(argumentos: Sequence[str]) -> list[str]:
    """`jobot ferramentas <argumentos>` pelo Python deste joBot."""
    return [sys.executable, "-m", "jobot", "ferramentas", *argumentos]


async def abrir_comando(argumentos: Sequence[str], dados: Path) -> asyncio.subprocess.Process:
    """O comando com a saída num cano e `JOBOT_DADOS` na pasta do painel que pediu. Cancelado ou
    com erro na leitura, o painel o mata (`kill`). Se o servidor morre de uma vez (SIGKILL, queda),
    o `print` seguinte do andamento levanta `BrokenPipeError`, que o `baixar` não trata como erro
    do disco: o filho sai e o `.parcial` fica para a retomada (D223.1)."""
    return await asyncio.create_subprocess_exec(
        *comando(argumentos),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={**os.environ, "JOBOT_DADOS": str(dados)},
        **processo.SEM_JANELA,
    )
