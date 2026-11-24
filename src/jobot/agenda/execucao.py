"""Execução completa da busca: os sete passos da seção 12.4 do desenho (decisões 16, 17, 19, 23).

1. abre a execução (`None` se já há uma rodando) e liga o batimento de 30 s;
2. coleta as fontes ligadas pelo executor (as desligadas ganham saúde "desligada");
3. grava cada escopo ao terminar e marca as ocorrências de escopos que sumiram;
4. enriquece as vagas ainda sem descrição (50 por fonte, 200 por execução, cache de 30 dias);
5. busca as cotações que faltam (só com a conversão ligada) e aplica as `_brl`;
6. recalcula o encaixe;
7. fecha a execução.
"""

import asyncio
import contextlib
import logging
import sqlite3
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal

from jobot.agenda.andamento import Marcas
from jobot.banco import execucoes
from jobot.banco.buscas import paises_das_buscas, recalcular_encaixe, termos_das_buscas
from jobot.banco.cadastros import empresas_da_coleta, fontes, ler_config, moeda_efetiva
from jobot.banco.cotacoes import aplicar_cotacoes, falta_cotacao, gravar_cotacao, moedas_em_aberto
from jobot.banco.execucoes import (
    HistoricoDoBanco,
    abrir_execucao,
    candidatas_a_detalhe,
    fechar_execucao,
    gravar_saude,
    interromper,
    manter_batimento,
)
from jobot.banco.gravacao import (
    fechar_escopos_extintos,
    gravar_cache_detalhe,
    gravar_escopo,
    reprocessar,
    tem_para_reprocessar,
)
from jobot.nucleo.cambio import buscar_cotacao
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, LimiteEscopo
from jobot.nucleo.coletores.executor import SaidaEscopo, estado_da_fonte, rodar
from jobot.nucleo.coletores.registro import descobrir
from jobot.nucleo.http import Bloqueio, ClienteEducado, LimiteAtingido, OrcamentoGasto, Parou429
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.relogio import Relogio
from jobot.nucleo.tratamento.rotulos import VERSAO_REGRAS
from jobot.nucleo.tratamento.tratar import tratar
from jobot.nucleo.url import canonica

log = logging.getLogger(__name__)

MAX_DETALHES_POR_FONTE = 50
MAX_DETALHES_POR_EXECUCAO = 200
_PARA_DETALHES = (Bloqueio, LimiteAtingido, OrcamentoGasto, Parou429)
# Escopo parado por estes (na listagem ou nos detalhes do executor) fica fora do passo 4; os de
# `_PARADAS_DA_FONTE` valem para a fonte toda e tiram todos os escopos dela (A14).
_PARADAS_DA_FONTE = frozenset({"saude.orcamento", "saude.bloqueio", "saude.limite_atingido"})
_PARADAS = _PARADAS_DA_FONTE | {"saude.intervalo", "saude.parou_429"}


async def executar_busca(
    con: sqlite3.Connection,
    cliente: ClienteEducado,
    relogio: Relogio,
    motivo: Literal["agenda", "agora", "recuperacao"],
    *,
    coletores: Mapping[str, Coletor] | None = None,
    ao_fim: asyncio.Event | None = None,
) -> int | None:
    """Roda uma busca inteira e devolve o id da execução; `None` se outra já está rodando.

    Um erro no meio marca a execução "interrompida" na hora, com o motivo, e sobe (D54, T153).
    `ao_fim` é marcado quando a busca termina bem (o laço das habilidades, `agenda/ia.py`).
    """
    inicio = relogio.agora()
    execucao_id = abrir_execucao(con, "busca", motivo, inicio)
    if execucao_id is None:
        return None
    batimento = asyncio.create_task(manter_batimento(con, execucao_id, relogio))
    marcas = Marcas(con, execucao_id, relogio)
    try:
        # lidos uma vez: as etapas fixadas no começo são as que rodam
        enriquecer = bool(ler_config(con, "enriquecimento_ligado"))
        converter = bool(ler_config(con, "conversao_moeda_ligada"))
        pedidas = {"coleta": True, "detalhes": enriquecer, "cotacoes": converter, "encaixe": True}
        await marcas.comecar([e for e, sim in pedidas.items() if sim])
        todos = descobrir() if coletores is None else coletores
        saidas = await _coletar(con, execucao_id, cliente, relogio, todos, marcas, enriquecer)
        if enriquecer:
            await _enriquecer(con, cliente, relogio, todos, saidas, inicio, marcas)
        if _ha_regras_a_reprocessar(con):
            await marcas.etapa("regras", None, None)
        reprocessar_se_regras_mudaram(con)
        agora = relogio.agora()
        hoje = agora.astimezone().date()  # DP8: o dia é o local
        if converter:
            await _cotacoes(con, cliente, agora, marcas)
        aplicar_cotacoes(con, conversao_ligada=converter, hoje=hoje)
        await marcas.etapa("encaixe", None, None)
        # shortcut: recalcula todas as vagas das buscas ativas; trocar pelas mexidas nesta
        # execução se a base crescer a ponto de pesar.
        recalcular_encaixe(con, None, bool(ler_config(con, "regras_ocultar_ligadas")), hoje=hoje)
        await marcas.etapa("fim", None, None)
    except BaseException as erro:
        interromper(con, execucao_id, erro, relogio.agora())
        raise
    finally:
        batimento.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await batimento
    fechar_execucao(con, execucao_id, relogio.agora())
    if ao_fim is not None:
        ao_fim.set()  # acorda o laço das habilidades (desenho 5.4); a busca não espera por ele
    return execucao_id


def _ha_regras_a_reprocessar(con: sqlite3.Connection) -> bool:
    """Só serve à marca do progresso: de melhor esforço, a falha vai ao log e segue sem a marca."""
    try:
        return tem_para_reprocessar(con, VERSAO_REGRAS)
    except sqlite3.Error:
        log.exception("leitura da marca de regras falhou")
        return False


def reprocessar_se_regras_mudaram(con: sqlite3.Connection) -> int:
    """Trata de novo as vagas abertas gravadas com outra versão das regras; devolve quantas."""
    return reprocessar(con, VERSAO_REGRAS)


async def _coletar(
    con: sqlite3.Connection,
    execucao_id: int,
    cliente: ClienteEducado,
    relogio: Relogio,
    coletores: Mapping[str, Coletor],
    marcas: Marcas,
    enriquecer: bool,
) -> list[SaidaEscopo]:
    """Passos 2 e 3: coleta, grava cada escopo e marca os escopos extintos. Com `enriquecer`
    (lido uma vez em `executar_busca`), o executor já detalha até o teto de cada fonte."""
    cadastradas = {f.chave: f.ligada for f in fontes(con)}
    ligadas = {c for c, ligada in cadastradas.items() if ligada and c in coletores}
    for chave in sorted(c for c, ligada in cadastradas.items() if not ligada and c in coletores):
        gravar_saude(con, execucao_id, chave, "", "desligada")
    ctx = ContextoColeta(
        empresas=empresas_da_coleta(con),
        termos=termos_das_buscas(con),
        paises=paises_das_buscas(con),
    )
    saidas: list[SaidaEscopo] = []

    async def ao_terminar(saida: SaidaEscopo) -> None:
        tratadas = [tratar(v) for v in saida.resultado.vagas if isinstance(v, VagaColetada)]
        gravar_escopo(con, execucao_id, saida, tratadas, relogio.agora())
        saidas.append(saida)
        await marcas.consulta_pronta(saida.fonte)

    # marcas só da tela de andamento: de melhor esforço, como o batimento; banco travado não
    # derruba a busca (nem troca o CancelledError do `finally` do executor por um grupo de erros)
    async def ao_comecar(fonte: str) -> None:
        try:
            execucoes.comecar_fonte(con, execucao_id, fonte, relogio.agora())
        except sqlite3.Error:
            log.exception("marca de começo da fonte %s falhou (execução %s)", fonte, execucao_id)
        await marcas.fonte_comecou(fonte)

    async def ao_terminar_fonte(fonte: str) -> None:
        try:
            execucoes.terminar_fonte(con, execucao_id, fonte, relogio.agora())
        except sqlite3.Error:
            log.exception("marca de fim da fonte %s falhou (execução %s)", fonte, execucao_id)
        estados = [s.resultado.estado for s in saidas if s.fonte == fonte]
        await marcas.fonte_terminou(fonte, estado_da_fonte(estados) == "falhou")

    await rodar(
        coletores,
        ctx,
        cliente,
        HistoricoDoBanco(con, relogio),
        relogio,
        ligadas=ligadas,
        ao_terminar_escopo=ao_terminar,
        ao_comecar_fonte=ao_comecar,
        ao_terminar_fonte=ao_terminar_fonte,
        ao_planejar=marcas.planejado,
        ao_esperar=marcas.esperando,
        max_detalhes_por_fonte=MAX_DETALHES_POR_FONTE if enriquecer else 0,
    )
    agora = relogio.agora()
    for chave in sorted(ligadas):
        da_fonte = [s for s in saidas if s.fonte == chave]
        # `escopos()` que quebrou não diz quais escopos existem: não marca nada
        if any(s.escopo == "" and s.resultado.estado == "falhou" for s in da_fonte):
            continue
        fechar_escopos_extintos(con, chave, {s.escopo for s in da_fonte}, agora)
    return saidas


async def _enriquecer(
    con: sqlite3.Connection,
    cliente: ClienteEducado,
    relogio: Relogio,
    coletores: Mapping[str, Coletor],
    saidas: list[SaidaEscopo],
    inicio: datetime,
    marcas: Marcas,
) -> None:
    """Passo 4: `detalhar` das vagas ainda sem detalhe, dentro dos limites (DR-70).

    Candidata: ocorrência aberta, sem descrição, vista pela primeira vez nos últimos 30 dias e
    sem tentativa no cache de 30 dias; as mais recentes primeiro. O que não coube no limite,
    ou falhou sem gravar o cache, volta na próxima execução.

    Só as ocorrências dos escopos que rodaram nesta execução sem parar (A14): o escopo no
    intervalo, em "falhou" ou que levou 429 fica de fora; orçamento, bloqueio e limite param a
    fonte toda, e a fonte desligada não está em `saidas` (ADR 0004). Cada escopo detalha no ritmo
    dele (`por_escopo`, como o executor); o `max_pedidos` da fonte é um orçamento só, somado
    entre os escopos. 429 no detalhe para só aquele escopo; bloqueio, limite e orçamento param a
    fonte.
    """
    await marcas.etapa("detalhes", None, None)
    fontes_paradas = {s.fonte for s in saidas if s.resultado.motivo in _PARADAS_DA_FONTE}
    rodaram = {
        (s.fonte, s.escopo)
        for s in saidas
        if s.resultado.estado not in ("no_limite", "falhou")
        and s.resultado.motivo not in _PARADAS
        and s.fonte not in fontes_paradas
    }
    if not rodaram:
        return
    nomes = sorted({f for f, _ in rodaram})
    usados: defaultdict[str, int] = defaultdict(int)
    pedidos: defaultdict[str, int] = defaultdict(int)
    for s in saidas:
        usados[s.fonte] += s.detalhes
        pedidos[s.fonte] += s.resultado.pedidos
    # o executor acabou de detalhar estas (sitemap): não repete o mesmo pedido agora
    ja_detalhadas = {
        canonica(v.url)
        for s in saidas
        if s.detalhes
        for v in s.resultado.vagas
        if isinstance(v, VagaColetada)
    }
    # shortcut: os 200 por execução não limitam os detalhes de sitemap dentro do executor
    # (fontes juntas); só o que sobra para este passo. Passar um orçamento comum ao `rodar`
    # se houver mais de quatro fontes de sitemap.
    livres_total = MAX_DETALHES_POR_EXECUCAO - sum(usados.values())
    candidatas: defaultdict[str, list[tuple[int, str, VagaColetada]]] = defaultdict(list)
    for c in candidatas_a_detalhe(con, nomes, inicio, relogio):
        if (c.fonte, c.escopo) in rodaram and canonica(c.vaga.url) not in ja_detalhadas:
            candidatas[c.fonte].append((c.ocorrencia_id, c.escopo, c.vaga))
    # o total é o teto de tentativas: escopo parado ou fonte parada terminam antes dele
    total = max(
        0,
        min(
            livres_total,
            sum(min(MAX_DETALHES_POR_FONTE - usados[f], len(c)) for f, c in candidatas.items()),
        ),
    )
    feitas = 0
    await marcas.etapa("detalhes", feitas, total)
    for fonte, da_fonte in candidatas.items():
        livres = min(MAX_DETALHES_POR_FONTE - usados[fonte], livres_total)
        fila = da_fonte[: max(livres, 0)]
        coletor = coletores[fonte]
        gastos = pedidos[fonte]
        parados: set[str] = set()
        for oid, escopo, v in fila:
            if escopo in parados:
                continue
            limite = coletor.por_escopo.get(escopo, LimiteEscopo())
            # um `HttpDoEscopo` por detalhe: o orçamento da fonte fica um só entre os escopos
            http = cliente.escopo(
                espera_s=coletor.espera_s if limite.espera_s is None else limite.espera_s,
                condicional=False,
                max_pedidos=None if coletor.max_pedidos is None else coletor.max_pedidos - gastos,
                para_no_429=limite.para_no_429,
            )
            livres_total -= 1
            try:
                detalhe = await coletor.detalhar(v, http)
            except Parou429 as erro:
                log.warning("detalhes de %s/%s parados: Parou429: %s", fonte, escopo, erro)
                parados.add(escopo)
                continue
            except _PARA_DETALHES as erro:
                log.warning("detalhes de %s parados: %s: %s", fonte, type(erro).__name__, erro)
                break
            except Exception:  # só esta URL; sem cache, volta na próxima execução
                # shortcut: sem recuo; a URL que sempre quebra é pedida em toda execução por
                # até 30 dias (`JANELA_DETALHE`). Contar as falhas pede schema (D54, opção c).
                log.exception("detalhe de %s falhou", v.url)
                continue
            finally:
                gastos += http.pedidos
                feitas += 1
                await marcas.etapa("detalhes", feitas, total)
            gravar_cache_detalhe(con, oid, v.url, detalhe, relogio.agora())


async def _cotacoes(
    con: sqlite3.Connection, cliente: ClienteEducado, agora: datetime, marcas: Marcas
) -> None:
    """Passo 5, primeira metade: PTAX das moedas sem cotação do dia (quem chama confere se a
    conversão está ligada)."""
    hoje = agora.astimezone().date()
    http = cliente.escopo(condicional=False)
    moedas = moedas_em_aberto(con)
    exibicao = moeda_efetiva(con)
    if exibicao != "BRL" and exibicao not in moedas:
        moedas = sorted([*moedas, exibicao])
    await marcas.etapa("cotacoes", 0, len(moedas))
    for feitas, moeda in enumerate(moedas, 1):
        if not falta_cotacao(con, moeda, agora.astimezone(UTC).date()):
            await marcas.etapa("cotacoes", feitas, len(moedas))
            continue
        try:
            cotacao = await buscar_cotacao(http, moeda, hoje)
            if cotacao is not None:
                gravar_cotacao(con, cotacao, agora)
        except Exception:  # a vaga fica sem valor em reais, não some
            log.exception("cotação de %s falhou", moeda)
            if con.in_transaction:
                con.rollback()
        finally:
            await marcas.etapa("cotacoes", feitas, len(moedas))
