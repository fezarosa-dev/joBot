"""Saúde das fontes: estado, motivo, últimas execuções, ligar e desligar (desenho 13.8; plano T50).

O estado da fonte vem da última execução que gravou linha dela (`saude`), com a regra do
executor (`estado_da_fonte`). O escopo aparece como texto, como vem do coletor, sem separar nem
traduzir (D50). O link "reportar problema" só existe em "falhou" e "parcial" com motivo do
conjunto fechado de `nucleo/quebra.py`; em fonte com vários escopos ele fica em cada escopo,
com `<fonte>/<escopo>`. A tela nunca faz pedido para fora: o link só abre no clique (ADR 0014).
"""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from jobot.agenda.agendador import INTERVALOS
from jobot.banco.cadastros import empresas, fontes, ligar_fonte
from jobot.banco.execucoes import (
    HistoricoDoBanco,
    LinhaSaude,
    inicio_da_ultima_completa,
    saude_recente,
)
from jobot.nucleo.coletores.executor import estado_da_fonte
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.quebra import link_reportar
from jobot.painel.rotas.vagas import _relogio
from jobot.painel.seguranca import Con, renderizar

router = APIRouter(prefix="/fontes")

Chave = Annotated[str, Path(min_length=1, max_length=100)]
EXECUCOES = 8
_NAO_RODOU = ("no_limite", "desligada")
_GRAVIDADE = {"falhou": 0, "parcial": 1, "no_limite": 2}


@dataclass(frozen=True)
class Reporte:
    url: str
    fonte: str  # o que vai no campo `fonte` do modelo
    motivo: str  # só a chave, como vai na URL


@dataclass(frozen=True)
class Escopo:
    nome: str  # texto como veio do coletor
    estado: str
    motivo: str | None
    vagas: int
    pode_rodar_em: datetime | None
    reporte: Reporte | None


@dataclass(frozen=True)
class Cartao:
    chave: str
    ligada: bool
    estado: str
    motivo: str | None
    quando: datetime | None
    vagas: int
    duracao_ms: int
    pontos: tuple[str, ...]  # do mais antigo para o mais novo
    proxima: datetime | None  # `None` ou já passada: roda na próxima busca
    pode_rodar_em: datetime | None
    escopos: tuple[Escopo, ...]
    reporte: Reporte | None


def _estado(estados: Sequence[str]) -> str:
    """Estado da fonte por escopos: `estado_da_fonte` mais "sem mudança" e "desligada"."""
    rodaram = [e for e in estados if e not in _NAO_RODOU]
    if not rodaram:
        return "desligada" if "desligada" in estados else "no_limite"
    if set(rodaram) == {"sem_mudanca"}:
        return "sem_mudanca"
    return estado_da_fonte(rodaram)


def _motivo(linhas: Sequence[LinhaSaude]) -> str | None:
    """O motivo do escopo mais grave que tiver um."""
    for linha in sorted(linhas, key=lambda ln: _GRAVIDADE.get(ln.estado, 3)):
        if linha.motivo:
            return linha.motivo
    return None


def _reporte(fonte: str, estado: str, motivo: str | None) -> Reporte | None:
    if estado not in ("falhou", "parcial") or motivo is None:
        return None
    url = link_reportar(fonte, motivo)
    return None if url is None else Reporte(url, fonte, motivo.partition(":")[0])


def _liberacao(
    historico: HistoricoDoBanco, chave: str, escopo: str, da_fonte: int | None, agora: datetime
) -> datetime | None:
    """Hora em que o escopo pode rodar de novo, com a mesma regra do executor (DR-64)."""
    minutos, onde = da_fonte, None
    try:
        proprio = limites(chave).por_escopo.get(escopo)
    except KeyError:
        proprio = None
    if proprio is not None and proprio.intervalo_min is not None:
        minutos, onde = proprio.intervalo_min, escopo  # o do escopo substitui o da fonte
    ultimo = historico.ultimo_inicio_com_pedido(chave, onde)
    if minutos is None or ultimo is None or ultimo > agora:  # relógio voltou: vencido (RF4)
        return None
    livre = ultimo + timedelta(minutes=minutos)
    return livre if livre > agora else None


def _local(data: datetime | None) -> datetime | None:
    return None if data is None else data.astimezone()


def _cartoes(con: sqlite3.Connection, agora: datetime, historico: HistoricoDoBanco) -> list[Cartao]:
    linhas = saude_recente(con, EXECUCOES)
    # só o identificador cadastrado de uma empresa pode ir no link; o resto do escopo é texto
    # opaco (D50) e pode trazer termo ou país da busca (Himalayas, Gupy, SmartRecruiters)
    cadastradas = {(e.fonte, e.identificador) for e in empresas(con)}
    execucoes = list(dict.fromkeys(ln.execucao_id for ln in linhas))  # da mais nova
    por_fonte: dict[str, dict[int, list[LinhaSaude]]] = {}
    for ln in linhas:
        por_fonte.setdefault(ln.fonte, {}).setdefault(ln.execucao_id, []).append(ln)
    ultima_busca = inicio_da_ultima_completa(con, "busca")
    agenda = (
        None
        if ultima_busca is None or ultima_busca > agora  # relógio voltou: vencida (RF4)
        else ultima_busca + INTERVALOS["busca"]
    )

    cartoes: list[Cartao] = []
    for fonte in fontes(con):
        chave = fonte.chave
        por_exec = por_fonte.get(chave, {})
        pontos = tuple(
            _estado([ln.estado for ln in por_exec[e]]) if e in por_exec else "vazio"
            for e in reversed(execucoes)
        )
        ultima = next((por_exec[e] for e in execucoes if e in por_exec), [])
        estado = _estado([ln.estado for ln in ultima]) if ultima else "sem_execucao"
        if not fonte.ligada:
            estado = "desligada"
        elif estado == "desligada":  # sobra de antes de a pessoa ligar de novo
            estado = "sem_execucao"

        livres = {
            ln.escopo: _liberacao(historico, chave, ln.escopo, fonte.intervalo_min, agora)
            for ln in ultima
            if ln.estado == "no_limite" and ln.motivo == "saude.intervalo"
        }
        com_escopos = len(ultima) > 1 or any(ln.escopo != "" for ln in ultima)
        escopos = tuple(
            Escopo(
                ln.escopo,
                ln.estado,
                ln.motivo,
                ln.vagas,
                _local(livres.get(ln.escopo)),
                _reporte(f"{chave}/{ln.escopo}", ln.estado, ln.motivo)
                if fonte.ligada and (chave, ln.escopo) in cadastradas
                else None,
            )
            for ln in ultima
            if com_escopos
        )

        proxima: datetime | None = None
        if fonte.ligada:
            candidatas = [agenda] if agenda else []
            ultimo = historico.ultimo_inicio_com_pedido(chave, None)
            if fonte.intervalo_min is not None and ultimo is not None and ultimo <= agora:
                candidatas.append(ultimo + timedelta(minutes=fonte.intervalo_min))
            proxima = max(candidatas, default=None)
            if proxima is not None and proxima <= agora:
                proxima = None

        # o motivo de um escopo parado por limite não explica um cartão que rodou
        motivo = _motivo(
            [ln for ln in ultima if estado in _NAO_RODOU or ln.estado not in _NAO_RODOU]
        )
        # escopo que não é empresa cadastrada não tem link próprio: o do cartão leva só a chave
        sem_link = [ln for ln in ultima if (chave, ln.escopo) not in cadastradas]
        motivo_reporte = _motivo(sem_link) if com_escopos else motivo
        livre = min((d for d in livres.values() if d is not None), default=None)
        cartoes.append(
            Cartao(
                chave=chave,
                ligada=fonte.ligada,
                estado=estado,
                motivo=motivo,
                quando=_local(ultima[0].iniciada_em) if ultima else None,
                vagas=sum(ln.vagas for ln in ultima),
                duracao_ms=sum(ln.duracao_ms for ln in ultima),
                pontos=pontos,
                proxima=_local(proxima),
                pode_rodar_em=_local(livre) if estado == "no_limite" else None,
                escopos=escopos,
                reporte=_reporte(chave, estado, motivo_reporte),
            )
        )
    return cartoes


@router.get("")
async def listar(request: Request, con: Con) -> HTMLResponse:
    relogio = _relogio(request)
    agora = relogio.agora()
    historico = HistoricoDoBanco(con, relogio)
    return renderizar(request, "fontes/pagina.html", cartoes=_cartoes(con, agora, historico))


def _ligar(con: sqlite3.Connection, chave: str, ligada: bool) -> RedirectResponse:
    try:
        ligar_fonte(con, chave, ligada)
    except LookupError as erro:
        raise HTTPException(404, "fonte não existe") from erro
    return RedirectResponse("/fontes", status_code=303)


@router.post("/{chave}/ligar")
async def ligar(con: Con, chave: Chave) -> RedirectResponse:
    return _ligar(con, chave, True)


@router.post("/{chave}/desligar")
async def desligar(con: Con, chave: Chave) -> RedirectResponse:
    return _ligar(con, chave, False)
