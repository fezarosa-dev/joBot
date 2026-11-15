"""A execução `login` (desenho A7, "Uma execução `login`").

Abre o navegador uma vez e lê os sites com login ligados, um depois do outro, cada um numa aba
nova: a página de entrada confere a sessão, os escopos vão dos lidos há mais tempo aos mais
recentes, e o teto de páginas de lista por site (`limites.MAX_LISTA`) conta a entrada (E16).
Cada escopo grava numa transação só, sem cache HTTP. A aba que para num desafio sem 2Captcha
fica aberta para a pessoa terminar (janela parada, D132.26) enquanto os outros sites seguem.
"""

import asyncio
import contextlib
import logging
import random
import sqlite3
from collections.abc import AsyncIterator, Callable, Coroutine, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import urldefrag

from playwright.async_api import BrowserContext, Page, async_playwright
from playwright.async_api import Error as ErroDoPlaywright

from jobot.banco.buscas import paises_das_buscas, termos_das_buscas
from jobot.banco.cadastros import empresas_da_coleta, fontes, ler_config
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
from jobot.navegador.captcha import ChaveDoCofre, Cola, Widget, achar_widget
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
from jobot.sistema.aviso import avisar
from jobot.sistema.cofre import Cofre
from jobot.sistema.segundo_plano_linux import rodar_comando
from jobot.sistema.tela import ambiente_da_tela

log = logging.getLogger(__name__)

_SEM_DATA = datetime.min.replace(tzinfo=UTC)  # escopo nunca lido vai primeiro no rodízio
_TITULO_AVISO = "joBot"
_FRASES_AVISO: Final = {
    "pt": "Um site com login parou num desafio. Termine na janela do navegador em até {} minutos.",
    "en": "A site with login stopped at a challenge. Finish it in the browser window within {}"
    " minutes.",
}


@dataclass(frozen=True)
class Dependencias:
    dados: Path
    lancar: Lancar
    ambiente: Callable[[], Mapping[str, str]]
    politica: Callable[[LeitorComLogin], Politica]
    sortear: Callable[[], float]
    cofre: Cofre
    avisar: Callable[[str, str], None]  # aviso no computador: título e frase, sem URL


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
            avisar=lambda titulo, frase: avisar(titulo, frase, env, rodar_comando),
        )


def _idioma(con: sqlite3.Connection) -> Literal["pt", "en"]:
    """O idioma salvo na configuração, `pt` para qualquer outro valor (como o painel)."""
    return "en" if ler_config(con, "idioma", "pt") == "en" else "pt"


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
    janela: _Janela | None = None
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
            janela = _Janela(relogio, deps.avisar, fechado, _idioma(con))
            chave = ChaveDoCofre(deps.cofre)  # todas as abas usam a mesma leitura (D135.5)
            for leitor in ligados:
                site = _ler_site(
                    con, execucao_id, leitor, contexto, deps, cliente, relogio, janela, chave
                )
                await janela.ler(site)
            await janela.esperar()
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
        if janela is not None:
            await janela.cancelar()
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
    if isinstance(erro, ErroDoPlaywright):
        return await _fechando(fechado)
    return fechado.is_set()


async def _fechando(fechado: asyncio.Event) -> bool:
    """Espera até `limites.ESPERA_FECHAR_S` pelo `close` do contexto, que pode chegar atrasado."""
    if not fechado.is_set():
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(limites.ESPERA_FECHAR_S):
                await fechado.wait()
    return fechado.is_set()


_Marca = tuple[str, str, Widget | None]


async def _marca(aba: Page) -> _Marca | None:
    """Endereço sem o fragmento, título e widget: mudou, a aba saiu do desafio; `None` com a
    página trocando ou fechada."""
    try:
        return urldefrag(aba.url).url, await aba.title(), await achar_widget(aba)
    except ErroDoPlaywright:
        return None


@dataclass
class _Parada:
    aba: Page
    marca: _Marca | None
    tarefa: asyncio.Task[None]
    saiu: asyncio.Future[bool]
    fechada: asyncio.Event  # a pessoa fechou a aba (T225)


class _Janela:
    """As abas paradas num desafio sem 2Captcha (D132.26, D132.44).

    Cada site lê numa tarefa, um por vez: a conexão nunca é usada por duas ao mesmo tempo. A
    parada suspende a tarefa do site com a aba aberta, e a execução segue com o próximo. Depois do
    último, `esperar` olha as abas paradas até `limites.JANELA_PARADA_S` no total; a que saiu do
    desafio segue o seu site no mesmo prazo, e no fim as restantes gravam a parada `captcha`.
    """

    def __init__(
        self,
        relogio: Relogio,
        avisar: Callable[[str, str], None],
        fechado: asyncio.Event,
        idioma: Literal["pt", "en"],
    ) -> None:
        self._relogio = relogio
        self._idioma = idioma
        self._avisar = avisar
        self.fechado = fechado
        self._paradas: list[_Parada] = []
        self._tarefas: list[asyncio.Task[None]] = []
        self._parou = asyncio.Event()
        self._avisou = False
        self._acabou = False

    async def parar(self, aba: Page) -> bool:
        """Chamada pelo site parado: True quando a pessoa tirou a aba do desafio no prazo."""
        if self._acabou:
            return False
        # antes do aviso: a pessoa pode fechar a aba logo ao vê-lo, e o `close` não se perde
        fechada = asyncio.Event()
        aba.on("close", lambda _: fechada.set())
        marca = await _marca(aba)
        if not self._avisou:  # uma vez por execução, sem endereço
            self._avisou = True
            frase = _FRASES_AVISO[self._idioma].format(limites.JANELA_PARADA_S // 60)
            # o `notify-send` roda fora do laço: o painel não para enquanto ele responde
            await asyncio.to_thread(self._avisar, _TITULO_AVISO, frase)
        tarefa = asyncio.current_task()
        assert tarefa is not None
        saiu: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._paradas.append(_Parada(aba, marca, tarefa, saiu, fechada))
        self._parou.set()
        return await saiu

    async def ler(self, site: Coroutine[Any, Any, None]) -> None:
        """Lê um site até ele acabar ou parar num desafio."""
        tarefa = asyncio.create_task(site)
        self._tarefas.append(tarefa)
        await self._ate_parar(tarefa)

    async def _ate_parar(self, tarefa: asyncio.Task[None]) -> None:
        self._parou = asyncio.Event()  # `clear` é nome do Playwright: o test_navegador_ast recusa
        parou = asyncio.create_task(self._parou.wait())
        try:
            await asyncio.wait((tarefa, parou), return_when=asyncio.FIRST_COMPLETED)
        finally:
            parou.cancel()
        if tarefa.done():
            tarefa.result()  # sobe o navegador fechado e o banco quebrado

    async def _seguir(self, parada: _Parada, saiu: bool) -> None:
        parada.saiu.set_result(saiu)
        await self._ate_parar(parada.tarefa)

    async def esperar(self) -> None:
        fim = self._relogio.agora() + timedelta(seconds=limites.JANELA_PARADA_S)
        while self._paradas and (resta := (fim - self._relogio.agora()).total_seconds()) > 0:
            await self._relogio.dormir(min(limites.OLHAR_S, resta))
            if self.fechado.is_set():
                raise NavegadorFechado
            for parada in list(self._paradas):
                if parada.fechada.is_set():
                    # o `close` da aba pode chegar antes do do contexto: o navegador inteiro
                    # fechando não passa por fechamento só desta aba
                    if await _fechando(self.fechado):
                        raise NavegadorFechado
                    self._paradas.remove(parada)
                    await self._seguir(parada, False)
                    continue
                marca = await _marca(parada.aba)
                if marca is None or marca == parada.marca:
                    continue
                self._paradas.remove(parada)
                await self._seguir(parada, True)
        self._acabou = True
        while self._paradas:
            await self._seguir(self._paradas.pop(0), False)

    async def cancelar(self) -> None:
        """Cancela os sites que sobraram (parados, ou o que lia quando a execução parou)."""
        for tarefa in self._tarefas:
            tarefa.cancel()
        await asyncio.gather(*self._tarefas, return_exceptions=True)


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
    janela: _Janela
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
        if visita == "captcha" and await self.janela.parar(self.aba):
            self.usadas -= 1  # a mesma página de novo, agora fora do desafio
            return await self.ir(url)
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
    janela: _Janela,
    chave: ChaveDoCofre,
) -> None:
    """Um site inteiro; um erro aqui grava `falhou` no site e não para os outros."""
    fechado = janela.fechado
    page: Page | None = None
    try:
        page = await contexto.new_page()
        cola = Cola(page, con=con, cliente=cliente, relogio=relogio, chave=chave)
        politica = deps.politica(leitor)
        site = _Site(con, execucao_id, leitor, page, politica, deps, relogio, fechado, cola, janela)
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
            desfecho = estado_do_escopo((), parada=visita, cortada=False, tres_ok_com_vagas=False)
            site.saude(desfecho.estado, desfecho.motivo)  # a página de saúde não mostra "ok"
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
