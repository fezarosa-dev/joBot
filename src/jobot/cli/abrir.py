"""Comandos `abrir` e `sair` no terminal (desenho 12.6): monta o abridor da janela do modo app."""

import argparse
import asyncio
import functools
import os
import sys

from jobot.navegador.abrir import chromium_do_jobot
from jobot.sistema.abrir import (
    abrir_janela,
    abrir_painel,
    existe_do_sistema,
    sair_do_servidor,
    subir_servidor,
)
from jobot.sistema.caso import prefixo_host
from jobot.sistema.pastas import pasta_de_dados


def executar(args: argparse.Namespace) -> int:
    env = os.environ
    dados = pasta_de_dados(env)
    try:
        if getattr(args, "comando", "abrir") == "sair":
            return sair_do_servidor(dados)
        janela = functools.partial(
            abrir_janela,
            sistema=sys.platform,
            existe=existe_do_sistema(prefixo_host(env)),
            # o driver do Playwright só sobe se o sistema não tem navegador
            chromium=lambda: asyncio.run(chromium_do_jobot()),
            pasta_dados=dados,
        )
        return abrir_painel(env, dados, subir=subir_servidor, navegador=janela)
    except OSError as erro:  # ex.: o Python que sobe o servidor não existe mais
        print(f"Não consegui concluir o comando: {erro}", file=sys.stderr)
        return 1
