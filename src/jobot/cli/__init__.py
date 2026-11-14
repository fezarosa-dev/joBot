"""Linha de comando do joBot. Cada comando mora num módulo que expõe `executar(args)`."""

import argparse
import importlib
from collections.abc import Mapping, Sequence

COMANDOS: Mapping[str, str] = {
    "abrir": "jobot.sistema.abrir",
    "sair": "jobot.sistema.abrir",
    "segundo-plano": "jobot.sistema.segundo_plano_linux",
    "serve": "jobot.cli.servir",
    "buscar": "jobot.cli.buscar",
    "avaliar-rotulos": "jobot.cli.avaliar_rotulos",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobot", description="Busca de vagas em fontes públicas.")
    sub = parser.add_subparsers(dest="comando", metavar="comando")
    sub.add_parser("abrir", help="abre o painel no navegador (o padrão)")
    sub.add_parser("sair", help="encerra o servidor")
    sub.add_parser("serve", help="sobe só o servidor, sem abrir nada")
    sub.add_parser("buscar", help="faz uma busca no terminal")
    plano = sub.add_parser("segundo-plano", help="liga ou desliga o serviço de segundo plano")
    plano.add_argument("acao", choices=["ligar", "desligar", "status"])
    rotulos = sub.add_parser("avaliar-rotulos", help="mede as regras contra um gabarito")
    rotulos.add_argument("caminho")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as saida:  # argparse sai com 2 em erro e com 0 em --help
        return saida.code if isinstance(saida.code, int) else 1
    if args.comando is None:
        args.comando = "abrir"
    modulo = importlib.import_module(COMANDOS[args.comando])
    return int(modulo.executar(args))
