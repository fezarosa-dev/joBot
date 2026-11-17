"""Comando `jobot ferramentas baixar navegador` (T330; desenho 6.2; D174.2 e D183.24).

O joBot não redistribui o navegador (o Playwright baixa o Google Chrome for Testing, D183.24):
em todo canal, a casca inclusive, é o `playwright install --no-shell chromium` de sempre
(`baixar_chromium`), da versão do Playwright do venv. O stdout leva linhas JSON que a casca lê:
`{"etapa":"navegador","feito":0}` no começo (sem `total`: o Playwright não diz o tamanho) e
`{"fim":"pronto"}` ou `{"fim":"falhou"}` no fim.

O `playwright install` vive em sessão própria (`abrir_instalador`): o sinal de quem chama (a casca
cancelando, o `jobot atualizar` no prazo) não chega a ele. No POSIX o SIGTERM cancela o download e
encerra o grupo dele antes de sair; no Windows quem chama mata a árvore (`taskkill /T`).
"""

import argparse
import asyncio
import json
import os
import signal
import sys

from jobot.navegador.instalador import Resultado, abrir_instalador, baixar_chromium
from jobot.navegador.janela_comum import AbrirJanela
from jobot.sistema.pastas import configurar_log, pasta_de_dados


def _escrever(linha: dict[str, object]) -> None:
    print(json.dumps(linha), flush=True)


async def _baixar(abrir: AbrirJanela) -> Resultado:
    tarefa = asyncio.current_task()
    if tarefa is not None and sys.platform != "win32":
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, tarefa.cancel)
    try:
        return await baixar_chromium(abrir)  # cancelado, encerra o grupo do `playwright install`
    except asyncio.CancelledError:
        return "falhou"


def baixar_navegador(args: argparse.Namespace, *, abrir: AbrirJanela = abrir_instalador) -> int:
    _escrever({"etapa": "navegador", "feito": 0})
    pronto = asyncio.run(_baixar(abrir)) == "pronto"
    _escrever({"fim": "pronto" if pronto else "falhou"})
    return 0 if pronto else 1


def executar(args: argparse.Namespace) -> int:
    configurar_log(pasta_de_dados(os.environ))
    return baixar_navegador(args)
