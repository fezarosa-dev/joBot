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
from pathlib import Path
from typing import Literal

from jobot.banco.buscas import paises_das_buscas, recalcular_encaixe, termos_das_buscas
from jobot.banco.cadastros import empresas_da_coleta, fontes, ler_config
from jobot.banco.conexao import abrir
from jobot.banco.cotacoes import aplicar_cotacoes, falta_cotacao, gravar_cotacao, moedas_em_aberto
from jobot.banco.execucoes import (
    JANELA_DETALHE,
    HistoricoDoBanco,
    abrir_execucao,
    bater,
    fechar_execucao,
    gravar_saude,
    interromper_execucao,
)
from jobot.banco.gravacao import (
    fechar_escopos_extintos,
    gravar_cache_detalhe,
    gravar_escopo,
    reprocessar,
)
from jobot.nucleo.cambio import buscar_cotacao
from jobot.nucleo.coletores.base import Coletor, ContextoColeta
from jobot.nucleo.coletores.executor import SaidaEscopo, rodar
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
BATIMENTO_S = 30.0
_PARA_DETALHES = (Bloqueio, LimiteAtingido, OrcamentoGasto, Parou429)
# Escopo parado por estes (na listagem ou nos detalhes do executor): a fonte fica fora do passo 4.
_PARADAS = frozenset(
    {
        "saude.intervalo",
        "saude.orcamento",
        "saude.parou_429",
        "saude.bloqueio",
        "saude.limite_atingido",
    }
)


def _iso(quando: datetime) -> str:
    return quando.astimezone(UTC).isoformat()


async def executar_busca(
    con: sqlite3.Connection,
    cliente: ClienteEducado,
    relogio: Relogio,
    motivo: Literal["agenda", "agora", "recuperacao"],
    *,
    coletores: Mapping[str, Coletor] | None = None,
) -> int | None:
    """Roda uma busca inteira e devolve o id da execução; `None` se outra já está rodando.

    Um erro no meio marca a execução "interrompida" na hora e sobe (D54).
    """
    inicio = relogio.agora()
    execucao_id = abrir_execucao(con, "busca", motivo, inicio)
    if execucao_id is None:
        return None
    batimento = asyncio.create_task(_bater(con, execucao_id, relogio))
    try:
        todos = descobrir() if coletores is None else coletores
        saidas = await _coletar(con, execucao_id, cliente, relogio, todos)
        if ler_config(con, "enriquecimento_ligado"):
            await _enriquecer(con, cliente, relogio, todos, saidas, inicio)
        reprocessar_se_regras_mudaram(con)
        agora = relogio.agora()
        hoje = agora.astimezone().date()  # DP8: o dia é o local
        await _cotacoes(con, cliente, agora)
        aplicar_cotacoes(
            con, conversao_ligada=bool(ler_config(con, "conversao_moeda_ligada")), hoje=hoje
        )
        # shortcut: recalcula todas as vagas das buscas ativas; trocar pelas mexidas nesta
        # execução se a base crescer a ponto de pesar.
        recalcular_encaixe(con, None, bool(ler_config(con, "regras_ocultar_ligadas")), hoje=hoje)
    except BaseException:
        if con.in_transaction:  # o passo que quebrou pode ter deixado a sua aberta
            con.rollback()
        interromper_execucao(con, execucao_id, relogio.agora())
        raise
    finally:
        batimento.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await batimento
    fechar_execucao(con, execucao_id, relogio.agora())
    return execucao_id


def reprocessar_se_regras_mudaram(con: sqlite3.Connection) -> int:
    """Trata de novo as vagas abertas gravadas com outra versão das regras; devolve quantas."""
    return reprocessar(con, VERSAO_REGRAS)


async def _bater(con: sqlite3.Connection, execucao_id: int, relogio: Relogio) -> None:
    """Batimento numa conexão própria: duas tarefas não dividem uma `sqlite3.Connection`."""
    caminho = con.execute("PRAGMA database_list").fetchone()[2]
    if not caminho:  # banco em memória não tem outra conexão; fica sem batimento
        return
    con2 = abrir(Path(caminho))
    try:
        while True:
            await relogio.dormir(BATIMENTO_S)
            try:
                bater(con2, execucao_id, relogio.agora())
            except sqlite3.Error:
                log.exception("batimento da execução %s falhou", execucao_id)
    finally:
        con2.close()


async def _coletar(
    con: sqlite3.Connection,
    execucao_id: int,
    cliente: ClienteEducado,
    relogio: Relogio,
    coletores: Mapping[str, Coletor],
) -> list[SaidaEscopo]:
    """Passos 2 e 3: coleta, grava cada escopo e marca os escopos extintos."""
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

    enriquecer = bool(ler_config(con, "enriquecimento_ligado"))
    await rodar(
        coletores,
        ctx,
        cliente,
        HistoricoDoBanco(con, relogio),
        relogio,
        ligadas=ligadas,
        ao_terminar_escopo=ao_terminar,
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
) -> None:
    """Passo 4: `detalhar` das vagas ainda sem detalhe, dentro dos limites (DR-70).

    Candidata: ocorrência aberta, sem descrição, vista pela primeira vez nos últimos 30 dias e
    sem tentativa no cache de 30 dias; as mais recentes primeiro. O que não coube no limite,
    ou falhou sem gravar o cache, volta na próxima execução.

    Só as fontes que rodaram nesta execução sem parar: a desligada (não está em `saidas`), a
    que ficou no intervalo ou sem orçamento e a que levou 429, bloqueio ou limite não recebem
    pedido de detalhe (ADR 0004). Fonte com todos os escopos em "falhou" também fica de fora.
    """
    rodaram = {s.fonte for s in saidas if s.resultado.estado not in ("no_limite", "falhou")} - {
        s.fonte for s in saidas if s.resultado.motivo in _PARADAS
    }
    if not rodaram:
        return
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
    candidatas: defaultdict[str, list[tuple[int, VagaColetada]]] = defaultdict(list)
    marcas = ",".join("?" * len(rodaram))
    # o SQL já descarta a maioria (as que têm descrição); o `strip()` abaixo fecha o resto
    for oid, fonte, coletada in con.execute(
        "SELECT o.id, o.fonte, o.coletada FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id"
        f" WHERE v.primeira_vista_em >= ? AND o.sumiu_em IS NULL AND o.fonte IN ({marcas})"
        " AND trim(coalesce(json_extract(o.coletada, '$.descricao'), ''), char(32, 9, 10, 13))"
        " = ''"
        " ORDER BY v.primeira_vista_em DESC, o.id",
        (_iso(inicio - JANELA_DETALHE), *sorted(rodaram)),
    ).fetchall():
        v = VagaColetada.de_json(coletada)
        if not v.descricao.strip() and canonica(v.url) not in ja_detalhadas:
            candidatas[fonte].append((oid, v))
    historico = HistoricoDoBanco(con, relogio)
    for fonte, da_fonte in candidatas.items():
        recentes = historico.detalhe_recente(fonte, [v.url for _, v in da_fonte])
        livres = min(MAX_DETALHES_POR_FONTE - usados[fonte], livres_total)
        fila = [(oid, v) for oid, v in da_fonte if v.url not in recentes][: max(livres, 0)]
        if not fila:
            continue
        coletor = coletores[fonte]
        max_pedidos = None if coletor.max_pedidos is None else coletor.max_pedidos - pedidos[fonte]
        http = cliente.escopo(espera_s=coletor.espera_s, condicional=False, max_pedidos=max_pedidos)
        for oid, v in fila:
            livres_total -= 1
            try:
                detalhe = await coletor.detalhar(v, http)
            except _PARA_DETALHES as erro:
                log.warning("detalhes de %s parados: %s", fonte, type(erro).__name__)
                break
            except Exception:  # só esta URL; sem cache, volta na próxima execução
                # shortcut: sem recuo; a URL que sempre quebra é pedida em toda execução por
                # até 30 dias (JANELA_DETALHE). Contar as falhas pede schema (D54, opção c).
                log.exception("detalhe de %s falhou", v.url)
                continue
            gravar_cache_detalhe(con, oid, v.url, detalhe, relogio.agora())


async def _cotacoes(con: sqlite3.Connection, cliente: ClienteEducado, agora: datetime) -> None:
    """Passo 5, primeira metade: PTAX das moedas sem cotação do dia, só com a conversão ligada."""
    if not ler_config(con, "conversao_moeda_ligada"):
        return
    hoje = agora.astimezone().date()
    http = cliente.escopo(condicional=False)
    for moeda in moedas_em_aberto(con):
        if not falta_cotacao(con, moeda, agora.astimezone(UTC).date()):
            continue
        try:
            cotacao = await buscar_cotacao(http, moeda, hoje)
            if cotacao is not None:
                gravar_cotacao(con, cotacao, agora)
        except Exception:  # a vaga fica sem valor em reais, não some
            log.exception("cotação de %s falhou", moeda)
            if con.in_transaction:
                con.rollback()
