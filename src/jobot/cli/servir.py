"""Comando `serve`: painel e agenda num processo só, escutando só em 127.0.0.1.

Desenho 12.1 (um processo), 12.3 (travas), 12.6 (`jobot serve`) e 14.1 (rede). Ao subir: migra,
semeia, marca as execuções interrompidas e reaplica as regras que mudaram; o laço da agenda
nasce e morre com o app (lifespan) e divide com a rota "buscar agora" as travas por tipo (D55).
A checagem de versão (T85) roda numa tarefa própria no mesmo lifespan, com conexão própria.
"""

import argparse
import asyncio
import contextlib
import logging
import os
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import closing
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from jobot import __version__
from jobot.agenda.agendador import INTERVALOS, laco
from jobot.agenda.descoberta import executar_descoberta
from jobot.agenda.execucao import executar_busca, reprocessar_se_regras_mudaram
from jobot.agenda.paginas import executar_paginas
from jobot.agenda.versao import laco_versao
from jobot.banco.buscas import recalcular_encaixe
from jobot.banco.cadastros import ler_config, semear
from jobot.banco.conexao import abrir
from jobot.banco.cotacoes import aplicar_cotacoes
from jobot.banco.execucoes import Motivo, Tipo, inicio_da_ultima_completa, marcar_interrompidas
from jobot.banco.gravacao import ValidadoresDoBanco
from jobot.banco.migrar import BancoMaisNovo, migrar
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.relogio import Relogio, RelogioReal
from jobot.painel.app import criar_app
from jobot.sistema.instancia import Trava, porta
from jobot.sistema.pastas import configurar_log, pasta_de_dados, preparar_pasta

log = logging.getLogger(__name__)

HOST = "127.0.0.1"  # fixo: não aceita outro valor (14.1)
TIPOS: tuple[Tipo, ...] = ("busca", "descoberta", "paginas")
_INTERRUPTORES: Mapping[Tipo, str] = {
    "descoberta": "descoberta_cc_ligada",
    "paginas": "paginas_ligadas",
}
_NOVA_TENTATIVA_S = 0.05  # D23: o servidor anterior pode estar soltando a trava


def preparar_dados(env: Mapping[str, str]) -> Path:
    """Pasta de dados pronta: umask 0o077 (o banco e o WAL nascem 0600), log e permissões (D7)."""
    os.umask(0o077)
    dados = pasta_de_dados(env)
    configurar_log(dados)
    preparar_pasta(dados)
    return dados


def preparar_banco(caminho: Path, relogio: Relogio) -> None:
    """Migra, semeia, marca as interrompidas e reaplica as regras que mudaram (7.2, 7.4, 12.3).

    Levanta `BancoMaisNovo` sem tocar no arquivo quando o banco é de um joBot mais novo.
    """
    with closing(abrir(caminho)) as con:
        migrar(con, caminho)
        semear(con)
        agora = relogio.agora()
        marcar_interrompidas(con, agora)
        if reprocessar_se_regras_mudaram(con):
            # aplica na hora: `reprocessar` não mexe nas `_brl` nem no encaixe (decisões 17, 18)
            hoje = agora.astimezone().date()  # DP8: o dia é o local
            conversao = bool(ler_config(con, "conversao_moeda_ligada"))
            aplicar_cotacoes(con, conversao_ligada=conversao, hoje=hoje)
            regras = bool(ler_config(con, "regras_ocultar_ligadas"))
            recalcular_encaixe(con, None, regras, hoje=hoje)


class _EstadoDoBanco:
    """O que o laço lê a cada volta; uma conexão curta por leitura, aberta na thread do laço."""

    def __init__(self, caminho: Path) -> None:
        self._caminho = caminho

    def ultimas(self) -> Mapping[Tipo, datetime | None]:
        with closing(abrir(self._caminho)) as con:
            return {tipo: inicio_da_ultima_completa(con, tipo) for tipo in TIPOS}

    def interruptores(self) -> Mapping[str, bool]:
        with closing(abrir(self._caminho)) as con:
            if ler_config(con, "primeira_execucao_concluida", False) is not True:
                # sem as preferências do assistente a busca sairia vazia e ocuparia o "Buscar
                # agora" do fim dele; o painel e `jobot buscar` não passam por aqui (T139)
                return {tipo: False for tipo in TIPOS}
            return {tipo: bool(ler_config(con, chave)) for tipo, chave in _INTERRUPTORES.items()}


def _perdida(caminho: Path, agora: datetime) -> bool:
    """A última busca completa passou de 3 h (ou está no futuro): a primeira será a recuperação."""
    with closing(abrir(caminho)) as con:
        ultima = inicio_da_ultima_completa(con, "busca")
    return ultima is not None and (ultima > agora or agora - ultima >= INTERVALOS["busca"])


def montar(
    dados: Path, porta: int, *, relogio: Relogio | None = None
) -> tuple[FastAPI, uvicorn.Config]:
    """App do painel com a agenda no lifespan e a configuração do uvicorn (só 127.0.0.1)."""
    relogio = relogio or RelogioReal()
    caminho = dados / "jobot.db"
    preparar_banco(caminho, relogio)
    app = criar_app(dados, porta)
    # um asyncio.Lock por tipo, o mesmo objeto para o laço e para a rota "buscar agora" (D55)
    travas: dict[str, asyncio.Lock] = {tipo: asyncio.Lock() for tipo in TIPOS}
    app.state.travas = travas
    app.state.relogio = relogio  # o "Buscar agora" usa o mesmo relógio da agenda
    motivos: list[Motivo] = ["recuperacao"] if _perdida(caminho, relogio.agora()) else []

    @contextlib.asynccontextmanager
    async def vida(app: FastAPI) -> AsyncIterator[None]:
        with closing(abrir(caminho)) as leitura:  # só lê os validadores do `cache_http`
            # um cliente para todos os tipos: o ritmo por host vale entre eles (12.3)
            cliente = ClienteEducado(None, relogio, ValidadoresDoBanco(leitura), __version__)
            app.state.cliente = cliente

            async def busca() -> None:
                motivo = motivos.pop() if motivos else "agenda"
                with closing(abrir(caminho)) as con:  # conexão própria: nunca dividida (padrões)
                    await executar_busca(con, cliente, relogio, motivo)

            async def descoberta() -> None:
                with closing(abrir(caminho)) as con:  # conexão própria: nunca dividida (padrões)
                    await executar_descoberta(con, cliente, relogio)

            async def paginas() -> None:
                with closing(abrir(caminho)) as con:  # conexão própria, como a busca
                    await executar_paginas(con, cliente, relogio)

            tarefas: Mapping[str, Callable[[], Awaitable[None]]] = {
                "busca": busca,
                "descoberta": descoberta,
                "paginas": paginas,
            }
            agenda = asyncio.create_task(
                laco(tarefas, _EstadoDoBanco(caminho), relogio, travas=travas)
            )
            # checagem de versão (T85): tarefa própria, abre a sua conexão com o caminho
            versao = asyncio.create_task(laco_versao(caminho, cliente, relogio))
            try:
                yield
            finally:
                # as do "Buscar agora" (painel/rotas/execucao.py) também usam o cliente: Ctrl+C
                # e SIGTERM passam por aqui, então todas param antes de fechá-lo
                todas = [agenda, versao, *getattr(app.state, "tarefas", ())]
                for tarefa in todas:
                    tarefa.cancel()
                await asyncio.gather(*todas, return_exceptions=True)
                await cliente.fechar()

    app.router.lifespan_context = vida
    config = uvicorn.Config(
        app,
        host=HOST,
        port=porta,
        server_header=False,
        proxy_headers=False,
        lifespan="on",
    )
    return app, config


def _pegar(trava: Trava) -> bool:
    if trava.pegar():
        return True
    time.sleep(_NOVA_TENTATIVA_S)
    return trava.pegar()


def executar(args: argparse.Namespace) -> int:
    try:
        dados = preparar_dados(os.environ)
        p = porta(os.environ)
        trava = Trava(dados, p)
        if not _pegar(trava):
            print("O joBot já está aberto.", file=sys.stderr)
            return 1
        try:
            app, config = montar(dados, p)
            servidor = uvicorn.Server(config)
            app.state.servidor = servidor  # o POST /sair pede o encerramento por aqui (T49)
            with contextlib.suppress(SystemExit):  # o uvicorn sai assim se não consegue escutar
                servidor.run()
        finally:
            trava.soltar()
    except (BancoMaisNovo, ValueError, OSError) as erro:
        log.error("o servidor não subiu: %s", erro)
        print(f"jobot: {erro}", file=sys.stderr)
        return 1
    if not servidor.started:
        log.error("o servidor não subiu em %s:%d (porta ocupada?)", HOST, p)
        print(
            f"Não consegui escutar em {HOST}:{p}. A porta pode estar ocupada por outro programa; "
            "feche-o ou defina JOBOT_PORTA com outra porta.",
            file=sys.stderr,
        )
        return 1
    return 0
