"""Comando `buscar`: uma busca no terminal e o resumo da saúde (desenho 12.2 e 12.6)."""

import argparse
import asyncio
import os
import sqlite3
import sys
from contextlib import closing

from jobot import __version__
from jobot.agenda.execucao import executar_busca
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import saude_recente
from jobot.banco.gravacao import ValidadoresDoBanco
from jobot.banco.migrar import BancoMaisNovo
from jobot.cli.servir import preparar_banco, preparar_dados
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.relogio import RelogioReal


async def _buscar(con: sqlite3.Connection, relogio: RelogioReal) -> int | None:
    cliente = ClienteEducado(None, relogio, ValidadoresDoBanco(con), __version__)
    try:
        return await executar_busca(con, cliente, relogio, "agora")
    finally:
        await cliente.fechar()


def _resumo(con: sqlite3.Connection, execucao_id: int) -> list[str]:
    # shortcut: o motivo sai como a chave de i18n crua; traduzir quando houver catálogo de terminal
    linhas = [f"Busca {execucao_id} concluída."]
    for s in saude_recente(con, n=1):
        if s.execucao_id != execucao_id:
            continue
        nome = f"{s.fonte} {s.escopo}".strip()
        motivo = f"  {s.motivo}" if s.motivo else ""
        linhas.append(f"{nome}: {s.estado} ({s.vagas} vagas){motivo}")
    return linhas


def executar(args: argparse.Namespace) -> int:
    relogio = RelogioReal()
    try:
        dados = preparar_dados(os.environ)
        caminho = dados / "jobot.db"
        preparar_banco(caminho, relogio)
        with closing(abrir(caminho)) as con:
            execucao_id = asyncio.run(_buscar(con, relogio))
            if execucao_id is None:
                print("Uma busca já está rodando; espere ela terminar.", file=sys.stderr)
                return 1
            print("\n".join(_resumo(con, execucao_id)))
    except (BancoMaisNovo, ValueError, OSError) as erro:
        print(f"jobot: {erro}", file=sys.stderr)
        return 1
    return 0
