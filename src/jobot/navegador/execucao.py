"""A execução `login` (desenho A7, "Uma execução `login`").

Abre o navegador uma vez e lê os sites com login ligados, um depois do outro, cada um numa aba
nova: a página de entrada confere a sessão, os escopos vão dos lidos há mais tempo aos mais
recentes, e o teto de páginas de lista por site (`limites.MAX_LISTA`) conta a entrada (E16).
Cada escopo grava numa transação só, sem cache HTTP.
"""

import asyncio
import contextlib
import logging
import random
import sqlite3
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright
from playwright.async_api import Error as ErroDoPlaywright

from jobot.banco.buscas import paises_das_buscas, termos_das_buscas
from jobot.banco.cadastros import empresas_da_coleta, fontes
from jobot.banco.execucoes import (
    HistoricoDoBanco,
    Motivo,
    abrir_execucao,
    candidatas_a_detalhe,
    fechar_execucao,
    gravar_saude,
    interromper,
    interromper_execucao,
    manter_batimento,
)
from jobot.banco.gravacao import fechar_escopos_extintos, gravar_cache_detalhe, gravar_escopo
from jobot.navegador import limites
from jobot.navegador.abrir import (
    Lancar,
    SemNavegador,
    SemTela,
    abrir_contexto,
    lancador_de_producao,
)
from jobot.navegador.captcha import Cola, Widget
from jobot.navegador.pagina import Recusada, visitar
from jobot.navegador.politica import Politica, politica_de_producao
from jobot.nucleo.coletores.base import ContextoColeta, Estado, ResultadoEscopo
from jobot.nucleo.coletores.executor import SaidaEscopo, motivo_do_escopo
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.leitores.base import Captura, EscopoLogado, LeitorComLogin, Leitura, ParadaLogin
from jobot.nucleo.leitores.estado import estado_do_escopo
from jobot.nucleo.relogio import Relogio
from jobot.nucleo.tratamento.tratar import tratar
from jobot.nucleo.url import canonica
from jobot.sistema.cofre import Cofre
from jobot.sistema.segundo_plano_linux import rodar_comando
from jobot.sistema.tela import ambiente_da_tela

log = logging.getLogger(__name__)

_SEM_DATA = datetime.min.replace(tzinfo=UTC)  # escopo nunca lido vai primeiro no rodízio


@dataclass(frozen=True)
class Dependencias:
    dados: Path
    lancar: Lancar
    ambiente: Callable[[], Mapping[str, str]]
    politica: Callable[[LeitorComLogin], Politica]
    sortear: Callable[[], float]
    cofre: Cofre


class NavegadorFechado(Exception):
    """A pessoa fechou o navegador no meio da execução."""


@asynccontextmanager
async def dependencias_de_producao(
    dados: Path, env: Mapping[str, str]
) -> AsyncIterator[Dependencias]:
    """As dependências de verdade (E17); o Playwright fecha na saída do bloco."""
    async with async_playwright() as playwright:
        # o lançador precisa do ambiente da tela, que só se descobre na execução (`ambiente()`)
        tela: list[Mapping[str, str]] = [{}]

        def ambiente() -> Mapping[str, str]:
            tela[0] = ambiente_da_tela(env, rodar_comando)
            return tela[0]

        async def lancar(**argumentos: Any) -> BrowserContext:
            return await lancador_de_producao(playwright, tela[0])(**argumentos)

        yield Dependencias(
            dados=dados,
            lancar=lancar,
            ambiente=ambiente,
            politica=lambda leitor: politica_de_producao(leitor.hosts),
            sortear=lambda: random.uniform(limites.ESPERA_MIN_S, limites.ESPERA_MAX_S),
            cofre=Cofre(dados),
        )


async def executar_login(
    con: sqlite3.Connection,
    cliente: ClienteEducado,
    relogio: Relogio,
    motivo: Motivo,
    *,
    leitores: Sequence[LeitorComLogin],
    deps: Dependencias,
) -> int | None:
    """Lê os sites com login ligados e devolve o id da execução; `None` sem site ligado ou com
    outra execução `login` rodando.

    Fechar o navegador marca a execução "interrompida" (`fechado`) e volta sem subir (E12);
    cancelar fecha o navegador e deixa o `CancelledError` subir (RF5).
    """
    cadastradas = {f.chave: f.ligada for f in fontes(con)}
    ligados = [leitor for leitor in leitores if cadastradas.get(leitor.chave)]
    if not ligados:
        return None
    execucao_id = abrir_execucao(con, "login", motivo, relogio.agora())
    if execucao_id is None:
        return None
    batimento = asyncio.create_task(manter_batimento(con, execucao_id, relogio))
    contexto: BrowserContext | None = None
    try:
        for leitor in leitores:
            if cadastradas.get(leitor.chave) is False:
                gravar_saude(con, execucao_id, leitor.chave, "", "desligada")
        try:
            contexto = await abrir_contexto(deps.dados, deps.ambiente(), deps.lancar)
        except (SemTela, SemNavegador) as erro:
            motivo_saude = "saude.sem_tela" if isinstance(erro, SemTela) else "saude.sem_navegador"
            for leitor in ligados:
                gravar_saude(con, execucao_id, leitor.chave, "", "falhou", motivo=motivo_saude)
        else:
            fechado = asyncio.Event()
            contexto.on("close", lambda _: fechado.set())
            for leitor in ligados:
                await _ler_site(con, execucao_id, leitor, contexto, deps, cliente, relogio, fechado)
    except NavegadorFechado:
        if con.in_transaction:
            con.rollback()
        interromper_execucao(con, execucao_id, relogio.agora(), parada="fechado")
        log.info("navegador fechado no meio da execução %s", execucao_id)
        return execucao_id
    except BaseException as erro:
        interromper(con, execucao_id, erro, relogio.agora())
        raise
    finally:
        if contexto is not None:
            try:
                await contexto.close()
            except ErroDoPlaywright:
                log.debug("o navegador já estava fechado")
        batimento.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await batimento
    fechar_execucao(con, execucao_id, relogio.agora())
    return execucao_id


async def _fechou(fechado: asyncio.Event, erro: Exception) -> bool:
    """O erro veio do navegador fechado? Espera um pouco pelo `close`, só com erro do Playwright."""
    if not fechado.is_set() and isinstance(erro, ErroDoPlaywright):
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(limites.ESPERA_FECHAR_S):
                await fechado.wait()
    return fechado.is_set()


@dataclass
class _Site:
    """O que a leitura de um site carrega de página em página."""

    con: sqlite3.Connection
    execucao_id: int
    leitor: LeitorComLogin
    aba: Page  # `page` é nome do Playwright: o test_navegador_ast recusa
    politica: Politica
    deps: Dependencias
    relogio: Relogio
    fechado: asyncio.Event
    cola: Cola  # o 2Captcha desta aba (A8)
    usadas: int = 0  # navegações do site, entrada inclusive (teto `MAX_LISTA`)

    async def ir(self, url: str) -> Captura | ParadaLogin | Recusada:
        """Espera o sorteio antes de toda navegação menos a primeira; recusada não navega."""
        if self.usadas and self.politica(url):
            await self.relogio.dormir(self.deps.sortear())
        visita = await visitar(
            self.aba, url, self.leitor, self.politica, self.relogio, cola=self.cola
        )
        assert not isinstance(visita, Widget)  # com a `cola`, o widget vira parada ou passa
        if self.fechado.is_set():  # a visita pode ter engolido o erro do fechamento (Cloudflare)
            raise NavegadorFechado
        if not isinstance(visita, Recusada):
            self.usadas += 1
        return visita

    def saude(self, estado: Estado, motivo: str | None) -> None:
        gravar_saude(
            self.con,
            self.execucao_id,
            self.leitor.chave,
            "",
            estado,
            pedidos=self.usadas,
            motivo=motivo,
        )


async def _ler_site(
    con: sqlite3.Connection,
    execucao_id: int,
    leitor: LeitorComLogin,
    contexto: BrowserContext,
    deps: Dependencias,
    cliente: ClienteEducado,
    relogio: Relogio,
    fechado: asyncio.Event,
) -> None:
    """Um site inteiro; um erro aqui grava `falhou` no site e não para os outros."""
    page: Page | None = None
    try:
        page = await contexto.new_page()
        cola = Cola(page, con=con, cliente=cliente, relogio=relogio, cofre=deps.cofre)
        politica = deps.politica(leitor)
        site = _Site(con, execucao_id, leitor, page, politica, deps, relogio, fechado, cola)
        await _ler_paginas(site)
    except sqlite3.Error:
        raise  # banco quebrado não é falha do site: a execução para com `banco`
    except Exception as erro:
        if await _fechou(fechado, erro):
            raise NavegadorFechado from erro
        if con.in_transaction:
            con.rollback()
        if isinstance(erro, ErroDoPlaywright):  # a mensagem traz a URL com a query: só o nome
            log.warning("leitura do site %s quebrou: %s", leitor.chave, type(erro).__name__)
        else:
            log.exception("leitura do site %s quebrou", leitor.chave)
        gravar_saude(con, execucao_id, leitor.chave, "", "falhou", motivo=motivo_do_escopo(erro))
    finally:
        if page is not None and not fechado.is_set():
            try:
                await page.close()
            except ErroDoPlaywright:
                log.debug("a aba do site %s já estava fechada", leitor.chave)


async def _ler_paginas(site: _Site) -> None:
    """Entrada, escopos em rodízio, o fechamento dos escopos que o site não tem mais e, quando a
    lista não traz a descrição, o detalhe das vagas."""
    leitor = site.leitor
    inicio = site.relogio.agora()
    entrada = await site.ir(leitor.url_entrada)
    parada: ParadaLogin | None = None
    if isinstance(entrada, Captura):
        if not leitor.pagina_logada(entrada.html, entrada.url):
            parada = "precisa_login"
    elif not isinstance(entrada, Recusada):
        parada = entrada
    if parada is not None or isinstance(entrada, Recusada):
        desfecho = estado_do_escopo(
            (), parada=parada, cortada=parada is None, tres_ok_com_vagas=False
        )
        site.saude(desfecho.estado, desfecho.motivo)
        return
    ctx = ContextoColeta(
        empresas=empresas_da_coleta(site.con),
        termos=termos_das_buscas(site.con),
        paises=paises_das_buscas(site.con),
    )
    escopos = list(leitor.escopos(ctx))  # quebrou: `_ler_site` grava `falhou` e nada fecha
    historico = HistoricoDoBanco(site.con, site.relogio)
    em_rodizio = sorted(
        escopos, key=lambda e: historico.ultima_coleta(leitor.chave, e.id) or _SEM_DATA
    )
    visitados: set[str] = set()
    parou = False
    for escopo in em_rodizio:
        if site.usadas >= limites.MAX_LISTA:
            break
        visitados.add(escopo.id)  # mesmo com a 1ª URL recusada; a política filtra a vaga também
        if parou := await _ler_escopo(site, escopo, historico):
            break  # parada encerra o site
    fechar_escopos_extintos(site.con, leitor.chave, {e.id for e in escopos}, site.relogio.agora())
    if not parou and not leitor.lista_tem_descricao:
        await _detalhar_site(site, inicio, visitados)


async def _detalhar_site(site: _Site, inicio: datetime, escopos: set[str]) -> None:
    """Abre a página de cada vaga aberta, sem descrição e sem detalhe tentado há 30 dias (a mais
    nova primeiro), só dos escopos lidos agora, até `limites.MAX_VAGA` páginas (D132.32).

    Cada página aberta grava o detalhe e a tentativa no cache de 30 dias; `detalhar` que devolve
    `None` grava a tentativa com o conteúdo vazio. Parada do site encerra o detalhe: os escopos já
    estão gravados, e as vagas que sobram voltam na próxima execução.
    """
    leitor = site.leitor
    candidatas = candidatas_a_detalhe(site.con, [leitor.chave], inicio, site.relogio)
    vistas: set[str] = set()  # a mesma vaga em dois escopos abre uma página só
    abertas = 0
    for c in candidatas:
        url = canonica(c.vaga.url)
        if c.escopo not in escopos or url in vistas:
            continue
        if abertas >= limites.MAX_VAGA:
            break
        vistas.add(url)
        visita = await site.ir(c.vaga.url)
        if isinstance(visita, Recusada):
            continue
        if not isinstance(visita, Captura):
            log.info("detalhes do site %s parados: %s", leitor.chave, visita)
            return
        abertas += 1
        try:
            detalhe = leitor.detalhar(visita, c.vaga)
        except Exception:  # só esta vaga; sem cache, volta na próxima execução
            # shortcut: sem recuo; a vaga que sempre quebra ocupa o teto e é pedida em toda
            # execução por até 30 dias. Contar as falhas pede schema (D54, opção c).
            log.exception("detalhe de uma vaga do site %s quebrou", leitor.chave)
            continue
        gravar_cache_detalhe(site.con, c.ocorrencia_id, c.vaga.url, detalhe, site.relogio.agora())


async def _ler_escopo(site: _Site, escopo: EscopoLogado, historico: HistoricoDoBanco) -> bool:
    """Lê as páginas do escopo, grava o desfecho e diz se o site parou."""
    inicio = site.relogio.agora()
    antes = site.usadas
    leituras: list[Leitura] = []
    lidas: list[str] = []
    parada: ParadaLogin | None = None
    cortada = False
    url: str | None = escopo.url
    while url is not None:
        if site.usadas >= limites.MAX_LISTA:  # o teto chegou no meio do escopo
            cortada = True
            break
        visita = await site.ir(url)
        if isinstance(visita, Recusada):
            cortada = True
            break
        if not isinstance(visita, Captura):
            parada = visita
            break
        lidas.append(visita.url)
        leituras.append(site.leitor.ler(visita, escopo))
        url = site.leitor.proxima(visita)
    chave = site.leitor.chave
    desfecho = estado_do_escopo(
        leituras,
        parada=parada,
        cortada=cortada,
        tres_ok_com_vagas=historico.tres_ultimas_ok_trouxeram_vagas(chave, escopo.id),
    )
    agora = site.relogio.agora()
    saida = SaidaEscopo(
        fonte=chave,
        escopo=escopo.id,
        resultado=ResultadoEscopo(
            desfecho.vagas, desfecho.estado, desfecho.motivo, site.usadas - antes
        ),
        duracao_ms=int((agora - inicio).total_seconds() * 1000),
        validadores={},
        urls_vistas=tuple(lidas),
        urls_sem_detalhe=(),
    )
    gravar_escopo(site.con, site.execucao_id, saida, [tratar(v) for v in desfecho.vagas], agora)
    return parada is not None
