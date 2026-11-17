"""Aba Perfil de Configurações: as habilidades e "Apagar perfil" (desenho 8 da fase 4; T413; D200).

As habilidades ficam no computador: o pedido do `encaixe` nunca leva o perfil (desenho 5.3). Elas
vão ao banco limpas e sem repetidos (`habilidades_do_texto`); mudar a lista recalcula o encaixe
**antes** de gravar, com a lista nova (padrões «Config»): se o recálculo falhar, nada muda. O
formulário (`POST /configuracoes/perfil`) fica em `configuracoes.py`, que já tem a página; este
módulo não importa aquele.
"""

import sqlite3
import unicodedata
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from jobot.banco import buscas, perfil
from jobot.banco.cadastros import ler_config
from jobot.banco.ia import tarefa_ia
from jobot.nucleo.texto import normalizar, sem_pontas
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.seguranca import Con, renderizar

router = APIRouter(prefix="/configuracoes/perfil")

PERFIL = "/configuracoes/perfil"
TETO_HABILIDADES = 200
TETO_CARACTERES = 100
# os serviços de fora com nome no catálogo; backend desconhecido vira "outro" (nunca `KeyError`)
SERVICOS = ("anthropic", "openai", "gemini", "compativel")


def habilidades_do_texto(texto: str) -> list[str]:
    """Uma habilidade por linha: controle vira espaço, invisível (Cf) sai, espaços simples e sem
    as pontas (o mesmo corte do encaixe, `sem_pontas`). Repetida pela forma normalizada sai e a
    primeira grafia fica. Mais de `TETO_HABILIDADES` ou uma com mais de `TETO_CARACTERES`:
    `ValueError`."""
    vistas: set[str] = set()
    lista: list[str] = []
    for linha in texto.splitlines():
        limpa = "".join(
            "" if (c := unicodedata.category(ch)) == "Cf" else " " if c == "Cc" else ch
            for ch in linha
        )
        nome = sem_pontas(" ".join(limpa.split()))
        forma = normalizar(nome)
        if forma and forma not in vistas:
            vistas.add(forma)
            lista.append(nome)
    if len(lista) > TETO_HABILIDADES or any(len(h) > TETO_CARACTERES for h in lista):
        raise ValueError("habilidades demais ou longas demais")
    return lista


def _recalcular(request: Request, con: sqlite3.Connection, lista: Sequence[str]) -> None:
    buscas.recalcular_encaixe(
        con,
        None,
        bool(ler_config(con, "regras_ocultar_ligadas")),
        hoje=relogio_do_painel(request).agora().astimezone().date(),  # o dia local (DP8)
        habilidades_perfil=list(lista),
    )


def salvar_habilidades(request: Request, con: sqlite3.Connection, lista: Sequence[str]) -> None:
    """Recalcula só se o conjunto mudou (ordem e grafia não mudam o encaixe) e grava a lista."""
    atuais = perfil.habilidades(con)
    if {normalizar(h) for h in lista} != {normalizar(h) for h in atuais}:
        _recalcular(request, con, lista)
    perfil.gravar_habilidades(con, lista, relogio_do_painel(request).agora())


def _privacidade(con: sqlite3.Connection) -> dict[str, str | None]:
    """A frase de privacidade (desenho 8) pelo estado da tarefa `encaixe`."""
    tarefa = tarefa_ia(con, "encaixe")
    base = "configuracoes.perfil.privacidade."
    if not tarefa.ligada:
        return {"chave": base + "desligada", "servico": None}
    if tarefa.backend == "local":
        return {"chave": base + "local", "servico": None}
    nome = tarefa.backend if tarefa.backend in SERVICOS else "outro"
    return {"chave": base + "fora", "servico": "configuracoes.perfil.servico." + nome}


async def contexto_perfil(request: Request, con: Con) -> dict[str, Any]:
    atuais = perfil.habilidades(con)
    return {
        "habilidades_texto": "\n".join(atuais),
        "tem_perfil": bool(atuais),
        "privacidade": _privacidade(con),
        "apagado": request.query_params.get("apagado") == "1",
    }


@router.get("/apagar/confirmar")
async def apagar_pergunta(request: Request) -> Response:
    """Sem JavaScript: a pergunta do alerta numa página; o GET não apaga nada (T307)."""
    return renderizar(
        request,
        "confirmar.html",
        titulo=("configuracoes.perfil.apagar.pergunta", {}),
        texto="configuracoes.perfil.apagar.explicacao",
        rotulo="comum.apagar",
        acao=PERFIL + "/apagar",
        voltar=PERFIL,
    )


@router.post("/apagar")
async def apagar(request: Request, con: Con) -> Response:
    """Apaga a linha do perfil; `habilidades_vaga` fica (desenho 8). Recalcula antes, sem nada."""
    _recalcular(request, con, [])
    perfil.apagar_perfil(con)
    return RedirectResponse(PERFIL + "?apagado=1", 303)
