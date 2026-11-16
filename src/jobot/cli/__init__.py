"""Linha de comando do joBot. Cada comando mora num módulo que expõe `executar(args)`."""

import argparse
import importlib
import logging
import os
import sqlite3
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from jobot.banco.migrar import BancoMaisNovo
from jobot.sistema.pastas import configurar_log, pasta_de_dados

COMANDOS: Mapping[str, str] = {
    "abrir": "jobot.cli.abrir",
    "sair": "jobot.cli.abrir",
    "segundo-plano": "jobot.sistema.segundo_plano_linux",
    "serve": "jobot.cli.servir",
    "buscar": "jobot.cli.buscar",
    "avaliar-rotulos": "jobot.cli.avaliar_rotulos",
    "atualizar": "jobot.cli.atualizar",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobot", description="Busca de vagas em fontes públicas.")
    sub = parser.add_subparsers(dest="comando", metavar="comando")
    sub.add_parser("abrir", help="abre o painel no navegador (o padrão)")
    sub.add_parser("sair", help="encerra o servidor")
    sub.add_parser("serve", help="sobe só o servidor, sem abrir nada")
    sub.add_parser("buscar", help="faz uma busca no terminal")
    sub.add_parser("atualizar", help="atualiza o joBot para a versão mais nova")
    plano = sub.add_parser("segundo-plano", help="liga ou desliga o serviço de segundo plano")
    plano.add_argument("acao", choices=["ligar", "desligar", "status"])
    rotulos = sub.add_parser("avaliar-rotulos", help="mede as regras contra um gabarito")
    rotulos.add_argument("caminho")
    rotulos.add_argument("--relatorio", metavar="arquivo.md")
    return parser


def caminho_do_log() -> Path:
    return pasta_de_dados(os.environ) / "logs" / "jobot.log"


def mensagem_do_banco(onde: str = "") -> str:
    return (
        "Problema no banco de dados do joBot (pode ser disco cheio ou arquivo danificado)." + onde
    )


def interrompido() -> int:
    """Ctrl+C: a linha curta e o código 130 de quem morre por SIGINT."""
    print("Interrompido.", file=sys.stderr)
    return 130


def _falhou(erro: Exception) -> int:
    """Traceback só no log (D106); no terminal, a frase curta com o caminho do log (T154)."""
    try:
        configurar_log(pasta_de_dados(os.environ))
        logging.getLogger("jobot").error("o comando falhou", exc_info=erro)
        onde = f" Detalhes em {caminho_do_log()}."
    except Exception:  # noqa: BLE001 - se nem o log abre, sobra a mensagem curta
        onde = ""
    if isinstance(erro, sqlite3.Error):
        print(mensagem_do_banco(onde), file=sys.stderr)
    elif isinstance(erro, BancoMaisNovo):  # a frase diz o que fazer; o traceback ficou no log
        print(f"jobot: {erro}", file=sys.stderr)
    else:
        extra = " Se repetir, abra uma issue com esse arquivo." if onde else ""
        print(f"O joBot encontrou um erro e parou.{onde}{extra}", file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as saida:  # argparse sai com 2 em erro e com 0 em --help
        return saida.code if isinstance(saida.code, int) else 1
    if args.comando is None:
        args.comando = "abrir"
    try:
        modulo = importlib.import_module(COMANDOS[args.comando])
        return int(modulo.executar(args))
    except KeyboardInterrupt:
        return interrompido()
    except Exception as erro:  # noqa: BLE001 - nenhum erro trava sem dizer onde está o log
        return _falhou(erro)
