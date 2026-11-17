"""Comando `jobot ferramentas baixar navegador` (T330; desenho 6.2; D174.2).

O progresso sai no stdout em linhas JSON (`{"etapa":"navegador","feito":n,"total":m}`, sem
`total` enquanto não souber) e termina com `{"fim":"pronto"}` ou `{"fim":"falhou"}`; a casca lê
essas linhas. Três caminhos: (a) `--arquivo` e `--sha256`, o arquivo da instalação pela casca;
(b) canal `casca` sem `--arquivo`, o mesmo arquivo baixado da release da versão instalada;
(c) fora da casca, o `playwright install` de sempre (`baixar_chromium`).
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx

import jobot
from jobot.navegador import chromium
from jobot.navegador.instalador import abrir_instalador, baixar_chromium
from jobot.navegador.janela_comum import AbrirJanela
from jobot.nucleo.quebra import URL_REPOSITORIO
from jobot.sistema.instalacao import manifesto_da_casca
from jobot.sistema.pastas import configurar_log, pasta_de_dados

_LOG = logging.getLogger(__name__)
_PRAZO_S = 60.0  # por leitura do download; o arquivo inteiro leva o tempo que levar


def _escrever(linha: dict[str, object]) -> None:
    print(json.dumps(linha), flush=True)


def _progresso(feito: int, total: int | None) -> None:
    linha: dict[str, object] = {"etapa": "navegador", "feito": feito}
    if total is not None:
        linha["total"] = total
    _escrever(linha)


def _cliente() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,  # a release salta para o armazenamento do GitHub
        timeout=_PRAZO_S,
        headers={"User-Agent": f"joBot/{jobot.__version__} (+{URL_REPOSITORIO})"},
    )


def _baixar(
    args: argparse.Namespace,
    dados: Path,
    destino: Path,
    abrir_cliente: Callable[[], httpx.Client],
    abrir: AbrirJanela,
) -> bool:
    if args.arquivo is not None or args.sha256 is not None:
        sha256 = (args.sha256 or "").lower()
        if args.arquivo is None or not chromium.HEX.fullmatch(sha256):
            _LOG.error("--arquivo e --sha256 (64 hexadecimais) vão juntos")
            return False
        return chromium.extrair(Path(args.arquivo), sha256, destino, _progresso)
    try:
        manifesto = manifesto_da_casca(dados)
    except ValueError, OSError:
        _LOG.exception("não deu para ler o instalacao.json")
        return False
    if manifesto is not None:
        with abrir_cliente() as cliente:
            return chromium.baixar_e_extrair(
                cliente, manifesto, jobot.__version__, destino, _progresso
            )
    return asyncio.run(baixar_chromium(abrir)) == "pronto"


def baixar_navegador(
    args: argparse.Namespace,
    *,
    dados: Path,
    destino: Path,
    abrir_cliente: Callable[[], httpx.Client] = _cliente,
    abrir: AbrirJanela = abrir_instalador,
) -> int:
    pronto = _baixar(args, dados, destino, abrir_cliente, abrir)
    _escrever({"fim": "pronto" if pronto else "falhou"})
    return 0 if pronto else 1


def executar(args: argparse.Namespace) -> int:
    dados = pasta_de_dados(os.environ)
    configurar_log(dados)
    destino = chromium.pasta_do_playwright(os.environ, sys.platform)
    return baixar_navegador(args, dados=dados, destino=destino)
