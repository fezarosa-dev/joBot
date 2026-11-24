"""Comando `serve`: painel e agenda num processo só, escutando só em 127.0.0.1.

Desenho 12.1 (um processo), 12.3 (travas), 12.6 (`jobot serve`) e 14.1 (rede). Ao subir: migra,
semeia, marca as execuções interrompidas e reaplica as regras que mudaram; o laço da agenda
nasce e morre com o app (lifespan) e divide com a rota "buscar agora" as travas por tipo (D55).
A checagem de versão (T85) roda numa tarefa própria no mesmo lifespan, com conexão própria, e
o laço das habilidades (T412, desenho 5.4) também: `FabricaIA` monta os backends de IA (o cliente
do núcleo, a chave do cofre e o `llama-server`) e o laço só recebe o backend pronto.
"""

import argparse
import asyncio
import contextlib
import functools
import logging
import os
import sqlite3
import sys
import threading
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
from jobot.agenda.ia import BackendDoLaco, laco_ia
from jobot.agenda.login import Login
from jobot.agenda.paginas import executar_paginas
from jobot.agenda.versao import laco_versao
from jobot.banco.buscas import recalcular_encaixe
from jobot.banco.cadastros import PADROES, fontes_com_login_ligadas, ler_config, semear
from jobot.banco.conexao import abrir
from jobot.banco.cotacoes import aplicar_cotacoes
from jobot.banco.execucoes import (
    Motivo,
    Tipo,
    inicio_da_ultima_completa,
    inicio_da_ultima_leitura_login,
    marcar_interrompidas,
)
from jobot.banco.gravacao import ValidadoresDoBanco
from jobot.banco.migrar import BancoMaisNovo, migrar
from jobot.banco.paginas import existe_pagina_nova
from jobot.cli import caminho_do_log, mensagem_do_banco
from jobot.cli.ferramentas import caminhos_local
from jobot.navegador.abrir import navegador_instalado
from jobot.navegador.execucao import dependencias_de_producao, executar_login
from jobot.nucleo.horarios import horarios_validos
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.ia.anthropic import ClienteAnthropic
from jobot.nucleo.ia.compativel_openai import ENDERECOS, ClienteCompativel
from jobot.nucleo.ia.contrato import Falha, Pedido, Resposta
from jobot.nucleo.leitores.registro import leitores
from jobot.nucleo.relogio import Relogio, RelogioReal
from jobot.painel.app import criar_app
from jobot.sistema import llama
from jobot.sistema.cofre import Cofre
from jobot.sistema.instancia import AVISO_CAPTURA, Trava, captura_em_andamento, porta
from jobot.sistema.llama import FalhaLlama, Llama
from jobot.sistema.pastas import configurar_log, pasta_de_dados, preparar_pasta
from jobot.sistema.sair import apagar_token, gravar_token

log = logging.getLogger(__name__)

HOST = "127.0.0.1"  # fixo: não aceita outro valor (14.1)
TIPOS: tuple[Tipo, ...] = ("busca", "descoberta", "paginas", "login")
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
        self._torto_avisado: object = None

    def ultimas(self) -> Mapping[Tipo, datetime | None]:
        with closing(abrir(self._caminho)) as con:
            return {tipo: inicio_da_ultima_completa(con, tipo) for tipo in TIPOS}

    def interruptores(self) -> Mapping[str, bool]:
        with closing(abrir(self._caminho)) as con:
            if ler_config(con, "primeira_execucao_concluida", False) is not True:
                # sem as preferências do assistente a busca sairia vazia e ocuparia o "Buscar
                # agora" do fim dele; o painel e `jobot buscar` não passam por aqui (T139)
                return dict.fromkeys(TIPOS, False)
            return {tipo: bool(ler_config(con, chave)) for tipo, chave in _INTERRUPTORES.items()}

    def pagina_nova(self) -> bool:
        with closing(abrir(self._caminho)) as con:
            return existe_pagina_nova(con)

    def login(self) -> Login | None:
        with closing(abrir(self._caminho)) as con:
            registrados = {leitor.chave for leitor in leitores()}
            if not registrados.intersection(fontes_com_login_ligadas(con)):
                return None
            valor = ler_config(con, "login_horarios")
            try:
                horarios = horarios_validos(valor)
            except ValueError as erro:
                # valor torto no banco (edição à mão, versão futura): a agenda segue (RF3);
                # o laço lê a cada 60 s, então avisa uma vez por valor
                if valor != self._torto_avisado:
                    self._torto_avisado = valor
                    log.warning(
                        "login_horarios inválido no banco (%s); vale o padrão", erro.args[0]
                    )
                horarios = horarios_validos(PADROES["login_horarios"])
            return Login(horarios, inicio_da_ultima_leitura_login(con))


class _Anthropic(ClienteAnthropic):
    def fechar(self) -> None:
        self.close()


class _Local:
    """`Backend` do modelo local: sobe o `llama-server` na thread do pedido, se ainda não subiu
    (a subida leva de 1 a 25 s; D185.7)."""

    def __init__(self, instancia: Llama) -> None:
        self._llama = instancia
        self._cliente: ClienteCompativel | None = None
        self._de = ("", "")

    def pedir(self, pedido: Pedido) -> Resposta:
        try:
            endereco, chave = self._llama.subir()
        except FalhaLlama as falha:
            raise Falha(falha.motivo) from None  # os motivos do `llama.py` são os do contrato
        if self._cliente is None or self._de != (endereco, chave):  # o servidor subiu de novo
            self.fechar()
            self._cliente, self._de = ClienteCompativel("local", endereco, chave), (endereco, chave)
        return self._cliente.pedir(pedido)

    def fechar(self) -> None:
        if self._cliente is not None:
            self._cliente.fechar()


class FabricaIA:
    """`app.state.ia`: `(backend, modelo) -> Backend` (desenho 5). A chave vem do cofre a cada
    chamada; a `Llama` do modelo local fica aqui e cai no fim de `vida` (D194.4)."""

    def __init__(self, dados: Path, banco: Path, cofre: Cofre | None = None) -> None:
        self._dados = dados
        self._banco = banco
        self._cofre = cofre or Cofre(dados)
        self.llama: Llama | None = None
        self._encerrada = False
        self._caminhos: tuple[Path, Path] | None = None
        self._trava = threading.Lock()  # o laço e as rotas (T416) chamam de threads diferentes

    def __call__(self, backend: str, modelo: str) -> BackendDoLaco:
        if backend == "local":
            return _Local(self._instancia())
        if backend not in ("anthropic", "compativel", *ENDERECOS):
            raise ValueError(f"backend de IA desconhecido: {backend!r}")
        lida = self._cofre.ler(f"ia_{backend}")
        chave = lida[0] if lida else None
        if backend == "compativel":  # a chave é opcional (Ollama, LM Studio)
            with closing(abrir(self._banco)) as con:
                valor = ler_config(con, "ia_compativel")
            endereco = valor.get("endereco") if isinstance(valor, dict) else None
            return ClienteCompativel(backend, endereco if isinstance(endereco, str) else "", chave)
        if chave is None:
            raise Falha("sem_chave")
        if backend == "anthropic":
            return _Anthropic(chave)
        return ClienteCompativel(backend, ENDERECOS[backend], chave)

    def _instancia(self) -> Llama:
        programa, gguf, _ = caminhos_local(self._dados)  # sem modelo baixado: `modelo_ausente`
        with self._trava:
            if self._encerrada:  # depois do fim de `vida`, nenhum `llama-server` novo
                raise Falha("servico_fora")
            if self.llama is None or self._caminhos != (programa, gguf):
                if self.llama is not None:
                    self.llama.encerrar()  # o modelo baixado mudou
                self.llama, self._caminhos = Llama(self._dados, programa, gguf), (programa, gguf)
            return self.llama

    def encerrar(self) -> None:
        with self._trava:
            self._encerrada = True
            if self.llama is not None:
                self.llama.encerrar()


def modelo_local(dados: Path) -> str | None:
    """O nome do modelo local baixado (a aba IA, T415), lido a cada chamada; sem ele, `None`."""
    try:
        return caminhos_local(dados)[2]
    except Falha:
        return None


def _perdida(caminho: Path, agora: datetime) -> bool:
    """A última busca completa passou de 3 h (ou está no futuro): a primeira será a recuperação."""
    with closing(abrir(caminho)) as con:
        ultima = inicio_da_ultima_completa(con, "busca")
    return ultima is not None and (ultima > agora or agora - ultima >= INTERVALOS["busca"])


def montar(
    dados: Path,
    porta: int,
    *,
    relogio: Relogio | None = None,
    env: Mapping[str, str] = os.environ,
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
    app.state.modelo_local = functools.partial(modelo_local, dados)  # a aba IA (T415)
    motivos: list[Motivo] = ["recuperacao"] if _perdida(caminho, relogio.agora()) else []

    @contextlib.asynccontextmanager
    async def vida(app: FastAPI) -> AsyncIterator[None]:
        # desenho 7: o `llama-server` de um servidor que morreu sai já na subida (D194.3)
        llama.encerrar_sobra(dados)
        with closing(abrir(caminho)) as leitura:  # só lê os validadores do `cache_http`
            # um cliente para todos os tipos: o ritmo por host vale entre eles (12.3)
            cliente = ClienteEducado(None, relogio, ValidadoresDoBanco(leitura), __version__)
            app.state.cliente = cliente

            # o laço das habilidades acorda no fim de cada busca e quando a aba IA liga a tarefa
            acordar = asyncio.Event()
            app.state.ia_acordar = acordar
            # pedidos da pessoa em curso (o teste ao ligar, T416): o laço espera entre uma vaga e
            # outra enquanto houver algum (desenho 5.4, item 6)
            pessoa: set[object] = set()
            app.state.ia_pessoa = pessoa
            fabrica = FabricaIA(dados, caminho)
            app.state.ia = fabrica

            async def busca() -> None:
                motivo = motivos.pop() if motivos else "agenda"
                with closing(abrir(caminho)) as con:  # conexão própria: nunca dividida (padrões)
                    await executar_busca(con, cliente, relogio, motivo, ao_fim=acordar)

            async def descoberta() -> None:
                with closing(abrir(caminho)) as con:  # conexão própria: nunca dividida (padrões)
                    await executar_descoberta(con, cliente, relogio)

            async def paginas() -> None:
                with closing(abrir(caminho)) as con:  # conexão própria, como a busca
                    await executar_paginas(con, cliente, relogio)

            async def login(motivo: Motivo = "agenda") -> None:
                with closing(abrir(caminho)) as con:  # conexão própria, como a busca
                    async with dependencias_de_producao(dados, env) as deps:
                        await executar_login(
                            con, cliente, relogio, motivo, leitores=leitores(), deps=deps
                        )

            tarefas: Mapping[str, Callable[[], Awaitable[None]]] = {
                "busca": busca,
                "descoberta": descoberta,
                "paginas": paginas,
                "login": login,
            }
            app.state.tarefa_login = login  # o "Buscar agora" dispara a mesma, com motivo "agora"
            if leitores():
                # shortcut: navegador_instalado é calculado ao subir o serve; "Baixar" e
                # "Remover" em Ferramentas atualizam app.state, mas instalar o Chrome com o serve
                # no ar só aparece depois de reiniciar; reler se isso confundir alguém
                app.state.navegador_instalado = await navegador_instalado()
            agenda = asyncio.create_task(
                laco(tarefas, _EstadoDoBanco(caminho), relogio, travas=travas)
            )
            # checagem de versão (T85): tarefa própria, abre a sua conexão com o caminho
            versao = asyncio.create_task(laco_versao(caminho, cliente, relogio))
            habilidades = asyncio.create_task(
                laco_ia(caminho, fabrica, relogio, acordar, ocupado=lambda: bool(pessoa))
            )
            try:
                yield
            finally:
                # as do "Buscar agora" (painel/rotas/execucao.py) também usam o cliente: Ctrl+C
                # e SIGTERM passam por aqui, então todas param antes de fechá-lo
                todas = [agenda, versao, habilidades, *getattr(app.state, "tarefas", ())]
                for tarefa in todas:
                    tarefa.cancel()
                await asyncio.gather(*todas, return_exceptions=True)
                await cliente.fechar()
                try:
                    fabrica.encerrar()  # a instância cai com o servidor (D194.4)
                except Exception:
                    log.exception("não consegui encerrar o llama-server")  # a sobra sai abaixo
                llama.encerrar_sobra(dados)  # e a anotada por um servidor que morreu

    app.router.lifespan_context = vida
    config = uvicorn.Config(
        app,
        host=HOST,
        port=porta,
        server_header=False,
        proxy_headers=False,
        lifespan="on",
        # no pythonw (tarefa do Windows) sys.stdout é None: com cores automáticas o uvicorn
        # chamaria sys.stdout.isatty() e o serve morreria ao subir
        use_colors=False,
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
            if captura_em_andamento(dados):
                print(AVISO_CAPTURA, file=sys.stderr)
                return 1  # a captura acaba logo: o launchd ou o systemd tenta de novo e assume
            # 0 (D175 item 9): com o painel aberto, o KeepAlive do launchd e o
            # Restart=on-failure do systemd não refazem o serve; ele volta no próximo login
            print("O joBot já está aberto.", file=sys.stderr)
            return 0
        try:
            app, config = montar(dados, p, env=os.environ)
            servidor = uvicorn.Server(config)
            app.state.servidor = servidor  # o POST /sair pede o encerramento por aqui (T49)
            # o `jobot sair` do Windows prova ser local por este segredo (desenho 6.1)
            app.state.sair_token = gravar_token(dados)
            with contextlib.suppress(SystemExit):  # o uvicorn sai assim se não consegue escutar
                servidor.run()
        finally:
            apagar_token(dados)  # com a trava presa, um arquivo que sobrou é de subida velha
            trava.soltar()
    except sqlite3.Error as erro:
        log.error("o servidor não subiu: erro do banco", exc_info=erro)
        print(mensagem_do_banco(f" Detalhes em {caminho_do_log()}."), file=sys.stderr)
        return 1
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
