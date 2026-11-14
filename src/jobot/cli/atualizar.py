"""Comando `atualizar`: puxa a versão nova do joBot (plano T85; o trabalho é de `sistema`)."""

import argparse
import os
import sys

from jobot.sistema.atualizar import atualizar, rodar_atualizacao
from jobot.sistema.pastas import pasta_de_dados


def executar(args: argparse.Namespace) -> int:
    try:
        return atualizar(rodar_atualizacao, pasta_de_dados(os.environ))
    except (ValueError, OSError) as erro:  # pasta de dados ruim, disco, permissão
        print(f"jobot: {erro}", file=sys.stderr)
        return 1
