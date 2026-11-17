"""A tela Panorama (plano T288; desenho 5.1 a 5.3 e 5.10; E11, E16, E19).

Só lê: as contagens das abas e dos chips, as perguntas pendentes, as salvas que fecham, a agenda
da busca, os cartões de Fontes e as contas em queda, sem cópia de nenhuma consulta. A busca segue
a escolhida, como em Vagas (D143.50): a da URL vence, depois a gravada, depois a primeira ativa.
"""

import sqlite3
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import QueryParams

from jobot.banco import leitura
from jobot.banco.cadastros import ler_config
from jobot.banco.execucoes import HistoricoDoBanco, execucao_atual, inicio_da_ultima_completa
from jobot.banco.leitura import Filtros
from jobot.painel.ambiente import leitores_do_painel
from jobot.painel.consultas import (
    MAX_ID,
    contas_em_queda,
    inteiro_da_url,
    relogio_do_painel,
)
from jobot.painel.formatos import data_completa, data_curta
from jobot.painel.lateral import ler_lateral
from jobot.painel.moeda import exibicao_do_painel
from jobot.painel.rotas.vagas import Estado, grupos_dos_chips, ler_estado, seletor_de_buscas
from jobot.painel.saude_das_fontes import cartoes, proxima_busca
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar

router = APIRouter(prefix="/panorama")

ABAS_DE_HOJE = ("novas", "fecham_logo", "salvas", "candidatei", "todas")
PASSOS = ("candidatei", "entrevista", "oferta", "recusada")
BLOCOS = ("encaixe", "modalidade", "area", "fonte")  # os grupos de chips de "O que aparece"
_MAIORES = 5
_PENDENTES = 50
_FECHAM = 5
_VOLTAR = "/panorama"


def pct(n: int, maior: int) -> int:
    """Largura da barra (E11): `n` sobre o maior do bloco, arredondado, com piso de 2 se `n > 0`."""
    if n <= 0 or maior <= 0:
        return 0
    return max(2, round(n * 100 / maior))


def _url_aba(aba: str, busca_id: int | None) -> str:
    pares = [("aba", aba), *([("busca", str(busca_id))] if busca_id is not None else [])]
    return "/vagas?" + urlencode(pares)


def _a_busca(con: sqlite3.Connection, request: Request, agora: datetime) -> dict[str, Any]:
    """Grupo "A busca": última e próxima busca, fontes com problema e contas em queda."""
    idioma = idioma_do_pedido(request)
    inicio = inicio_da_ultima_completa(con, "busca")
    proxima = None
    p = proxima_busca(con, agora)
    if p is not None and p > agora:  # com a busca rodando, o template mostra "Buscando agora."
        # ao minuto, como o cartão de Fontes (`hora` de fontes/pagina.html); o dia só noutro dia
        outro_dia = p.date() != agora.astimezone().date()
        proxima = {
            "hora": p.strftime("%H:%M"),
            "dia": data_curta(p.isoformat(), idioma) if outro_dia else None,
        }
    ligadas = [
        c
        for c in cartoes(con, agora, HistoricoDoBanco(con, relogio_do_painel(request)))
        if c.ligada
    ]
    problema = sum(c.estado in ("falhou", "parcial") for c in ligadas)
    return {
        "ultima": None if inicio is None else data_completa(inicio.isoformat(), idioma),
        "rodando": execucao_atual(con) is not None,
        "proxima": proxima,
        "fontes_problema": problema,
        # `no_limite` e `sem_execucao` não são problema, mas não deixam dizer que todas funcionaram
        "fontes_ok": inicio is not None
        and bool(ligadas)
        and all(c.estado in ("ok", "sem_mudanca") for c in ligadas),
        "contas": len(contas_em_queda(con, leitores_do_painel(request))),
    }


def _o_que_aparece(
    con: sqlite3.Connection, estado: Estado, agora: datetime, idioma: str
) -> list[dict[str, Any]]:
    """Os blocos de chips da aba Todas, com a largura da barra e o mais comum de cada um."""
    grupos = {g["nome"]: g for g in grupos_dos_chips(con, estado, agora, idioma, BLOCOS)}
    blocos = []
    for nome in BLOCOS:
        if nome not in grupos:  # sem busca, o encaixe não tem contagem e o bloco some
            continue
        chips = grupos[nome]["chips"]
        if nome != "encaixe":
            chips = chips[:_MAIORES]  # os outros grupos já vêm do mais contado para o menos
        maior = max(c["n"] for c in chips)
        blocos.append(
            {
                "nome": nome,
                "chips": [c | {"pct": pct(c["n"], maior)} for c in chips],
                "mais_comum": next(c for c in chips if c["n"] == maior),
                "ver": None if nome == "encaixe" else estado.url(),
            }
        )
    return blocos


def _busca(con: sqlite3.Connection, busca_id: int | None) -> dict[str, Any] | None:
    if busca_id is None:
        return None
    nome = con.execute("SELECT nome FROM busca WHERE id = ?", (busca_id,)).fetchone()[0]
    return {"id": busca_id, "nome": nome}


@router.get("")
async def panorama(request: Request, con: Con) -> Response:
    if not ler_config(con, "primeira_execucao_concluida", False):
        return RedirectResponse("/primeira-execucao/1", status_code=303)
    agora = relogio_do_painel(request).agora()
    # a lateral na conexão do pedido: a casca e "Hoje" usam a mesma contagem das abas (T313)
    lado = ler_lateral(con, agora, inteiro_da_url(request.query_params.get("busca"), MAX_ID))
    busca_id = lado.busca_id
    contexto: dict[str, Any] = {
        "vazio": not leitura.tem_vaga(con),
        "voltar": _VOLTAR,
        "lateral_lida": lado,
    }
    contexto |= _a_busca(con, request, agora)
    if not contexto["vazio"]:
        # o Estado de Vagas para a aba Todas da busca escolhida, com a busca nos links
        params = QueryParams({"aba": "todas", **({"busca": str(busca_id)} if busca_id else {})})
        estado = ler_estado(params, con, exibicao_do_painel(con, agora.astimezone().date()))
        abas = lado.contagens
        # só o grupo status: um GROUP BY v.status nas candidaturas (T312)
        status = leitura.contar_chips(con, Filtros(aba="candidatei"), agora, ("status",)).get(
            "status", {}
        )
        contexto |= {
            "busca": _busca(con, busca_id),
            "seletor": seletor_de_buscas(con, estado),
            "hoje": [(aba, abas[aba], _url_aba(aba, busca_id)) for aba in ABAS_DE_HOJE],
            "passos": [(passo, status.get(passo, 0)) for passo in PASSOS],
            "url_candidatei": _url_aba("candidatei", busca_id),
            "url_salvas": _url_aba("salvas", busca_id),
            "pendentes": leitura.perguntas_pendentes(con, _PENDENTES)[0],
            "fecham": leitura.salvas_que_fecham(con, agora, _FECHAM),
            "blocos": _o_que_aparece(con, estado, agora, idioma_do_pedido(request)),
            "total": abas["todas"],
        }
    return renderizar(request, "panorama/pagina.html", **contexto)


@router.get("/para-responder")
async def para_responder(request: Request, con: Con) -> HTMLResponse:
    pendentes = leitura.perguntas_pendentes(con, _PENDENTES)[0]
    return renderizar(request, "panorama/_para_responder.html", pendentes=pendentes, voltar=_VOLTAR)
