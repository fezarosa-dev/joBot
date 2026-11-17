"""Laço das habilidades (desenho 5.4 da fase 4; D185.12, D198).

Uma tarefa asyncio própria, criada em `vida` (`cli/servir.py`), fora da execução e da trava da
busca. Acorda pelo `asyncio.Event` que a execução da busca marca no fim e que a aba IA marca ao
ligar a tarefa; não roda ao subir. Uma rodada por vez: pedidos durante a rodada viram uma rodada
só, depois dela. Recebe o backend pronto (`obter`), montado em `cli/servir.py`: a `agenda` não
importa `sistema`.

A chamada ao backend roda em `asyncio.to_thread`, fora de transação; a conexão do banco fica na
thread do laço (padrões «Serve»). O log leva só a tarefa, o backend, o modelo e o motivo.
"""

import asyncio
import hashlib
import json
import logging
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from pathlib import Path
from typing import Protocol

from jobot.banco.buscas import recalcular_encaixe
from jobot.banco.cadastros import ler_config
from jobot.banco.conexao import abrir
from jobot.banco.ia import candidatas, chamadas_do_dia, gravar_falha, gravar_pede, tarefa_ia
from jobot.banco.perfil import habilidades
from jobot.nucleo.ia.contrato import Backend, Falha, limites
from jobot.nucleo.ia.pedidos import TextoVaga, pedido_encaixe, texto_encaixe
from jobot.nucleo.ia.tarefas import VERSAO, pede_da_vaga
from jobot.nucleo.relogio import Relogio

log = logging.getLogger(__name__)

ESPERA_PESSOA_S = 2.0  # entre uma olhada e outra, enquanto a pessoa tem um pedido em curso


class BackendDoLaco(Backend, Protocol):
    def fechar(self) -> None:
        """Fecha o cliente HTTP; chamado no fim da rodada e no cancelamento."""
        ...


Obter = Callable[[str, str], BackendDoLaco]


def chave_do_pedido(texto: str, backend: str, modelo: str) -> str:
    """Hash do texto enviado (`TextoVaga.texto`) + `VERSAO` + backend + modelo, sem o perfil:
    mudar as habilidades não reenvia nada (desenho 5.4)."""
    bruto = json.dumps([texto, VERSAO["encaixe"], backend, modelo], ensure_ascii=False)
    return hashlib.sha256(bruto.encode()).hexdigest()


def _fila(
    con: sqlite3.Connection, backend: str, modelo: str, lim: Mapping[str, int]
) -> list[tuple[int, TextoVaga, str]]:
    fila = []
    # ponytail: monta o texto e o hash de toda vaga aberta a cada rodada; guardar a chave na vaga
    # se a base crescer a ponto de pesar
    for c in candidatas(con):
        texto = texto_encaixe(c.titulo, c.descricao)
        chave = chave_do_pedido(texto.texto, backend, modelo)
        if chave == c.chave:
            continue
        if chave == c.falha_chave and c.tentativas >= lim["max_tentativas"]:
            continue  # só volta com chave nova
        fila.append((c.vaga_id, texto, chave))
        if len(fila) >= lim["max_por_rodada"]:
            break
    return fila


async def rodada(
    con: sqlite3.Connection,
    obter: Obter,
    relogio: Relogio,
    *,
    ocupado: Callable[[], bool] = lambda: False,
    limites: Mapping[str, int] | None = None,
) -> None:
    """Uma rodada: pede o `pede` das vagas da fila, grava e recalcula o encaixe de cada uma.

    Falha do backend para a rodada sem marcar a vaga; falha da vaga grava e segue para a próxima.
    """
    lim = limites if limites is not None else _limites_do_laco()
    tarefa = tarefa_ia(con, "encaixe")
    if not tarefa.ligada or not habilidades(con):
        return
    fila = _fila(con, tarefa.backend, tarefa.modelo, lim)
    if not fila:
        return
    try:
        backend = await asyncio.to_thread(obter, tarefa.backend, tarefa.modelo)
    except Falha as falha:
        _parou(tarefa.backend, tarefa.modelo, falha)
        return
    try:
        for vaga_id, texto, chave in fila:
            while ocupado():  # o pedido da pessoa vem primeiro (desenho 5.4, item 6)
                await relogio.dormir(ESPERA_PESSOA_S)
            if tarefa_ia(con, "encaixe") != tarefa:
                return  # desligada ou trocada no meio: a aba IA acorda o laço de novo
            if tarefa.backend != "local" and (
                chamadas_do_dia(con, tarefa.backend, relogio.agora()) >= lim["max_por_dia_fora"]
            ):
                return
            pedido = pedido_encaixe(texto, tarefa.backend, tarefa.modelo)
            try:
                resposta = await asyncio.to_thread(backend.pedir, pedido)
            except Falha as falha:
                if falha.backend_ou_vaga == "backend":
                    _parou(tarefa.backend, tarefa.modelo, falha)
                    return
                gravar_falha(
                    con,
                    vaga_id,
                    chave=chave,
                    motivo=falha.motivo,
                    backend=tarefa.backend,
                    agora=relogio.agora(),
                )
                continue
            agora = relogio.agora()
            gravar_pede(
                con,
                vaga_id,
                chave=chave,
                pede=pede_da_vaga(resposta.dados["pede"], texto.texto),
                backend=tarefa.backend,
                modelo=tarefa.modelo,
                versao=VERSAO["encaixe"],
                agora=agora,
            )
            regras = bool(ler_config(con, "regras_ocultar_ligadas"))
            hoje = agora.astimezone().date()  # DP8: o dia é o local
            recalcular_encaixe(con, None, regras, hoje=hoje, vaga_id=vaga_id)
    finally:
        # ponytail: fechar o cliente `httpx` não corta a leitura já em curso na outra thread (medido
        # na T412); no local, o `Llama.encerrar` do fim de `vida` derruba o servidor e a conexão
        backend.fechar()


def _limites_do_laco() -> Mapping[str, int]:
    lim: Mapping[str, int] = limites()["laco"]
    return lim


def _parou(backend: str, modelo: str, falha: Falha) -> None:
    log.warning("ia encaixe %s %s: rodada parou (%s)", backend, modelo, falha.motivo)


async def laco_ia(
    caminho: Path,
    obter: Obter,
    relogio: Relogio,
    acordar: asyncio.Event,
    *,
    ocupado: Callable[[], bool] = lambda: False,
    depois_da_rodada: Callable[[], None] = lambda: None,
) -> None:
    """Espera `acordar` e roda uma rodada por vez, com conexão própria; `vida` o cancela no fim."""
    while True:
        await acordar.wait()
        acordar.clear()  # antes da rodada: o pedido que chega durante ela vale uma rodada depois
        try:
            with closing(abrir(caminho)) as con:
                await rodada(con, obter, relogio, ocupado=ocupado)
        except Exception:
            log.exception("a rodada das habilidades falhou")
        depois_da_rodada()
