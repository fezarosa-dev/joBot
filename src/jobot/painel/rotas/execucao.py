"""Buscar agora, andamento da busca e sair (desenho 12.3, 12.6, 13.2 e 13.12; plano T49).

A rota usa a trava e o cliente que o lifespan de `cli/servir.py` põe em `app.state` (D55, D58):
com a trava `busca` presa (pela agenda ou por outro clique), não dispara outra e mostra o
andamento da que roda. A busca roda numa tarefa asyncio, com conexão própria, como a da agenda,
e o pedido volta na hora. O dia local (DP8) é calculado por `executar_busca`, com o `Relogio`
do app.
"""

import asyncio
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from jobot.agenda.agendador import _rodar
from jobot.agenda.execucao import executar_busca
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import execucao_atual
from jobot.nucleo.http import ClienteEducado
from jobot.painel.rotas.vagas import _relogio
from jobot.painel.seguranca import Con, _de_volta, renderizar

router = APIRouter()
_AVISO = "jobot_ja_roda"  # cookie do aviso "já roda" no clique sem HTMX (lido em barra.html)


@dataclass(frozen=True)
class Resultado:
    """A última busca encerrada e quantas vagas ela viu pela primeira vez."""

    estado: str  # concluida ou interrompida
    novas: int


def _ultima(con: sqlite3.Connection) -> Resultado | None:
    # nova = vista pela primeira vez entre o início e o fim da busca; julianday compara instantes
    # mesmo com fusos diferentes no texto
    linha = con.execute(
        "SELECT e.estado, (SELECT count(*) FROM vaga v"
        "   WHERE julianday(v.primeira_vista_em)"
        "   BETWEEN julianday(e.iniciada_em) AND julianday(e.terminada_em))"
        " FROM execucao e WHERE e.tipo = 'busca' AND e.estado <> 'rodando'"
        " ORDER BY julianday(e.iniciada_em) DESC, e.id DESC LIMIT 1"
    ).fetchone()
    return None if linha is None else Resultado(linha[0], linha[1])


def _tarefas(request: Request) -> set[asyncio.Task[None]]:
    # o laço de eventos só guarda referência fraca às tarefas: sem isto a busca pode sumir no
    # meio. Fica em app.state (uma por app), para o `sair` e o lifespan acharem e cancelarem
    estado = request.app.state
    if not hasattr(estado, "tarefas"):
        estado.tarefas = set()
    tarefas: set[asyncio.Task[None]] = estado.tarefas
    return tarefas


def _andamento(
    request: Request,
    con: sqlite3.Connection,
    *,
    ja_rodava: bool,
    visto: int | None = None,
    so_rodando: bool = False,
) -> Response:
    # a casca pergunta em toda página: app sem o lifespan (sem travas) não pode dar 500
    trava: asyncio.Lock | None = getattr(request.app.state, "travas", {}).get("busca")
    atual = execucao_atual(con)
    if atual is not None and atual.tipo != "busca":
        atual = None  # descoberta e páginas não seguram a busca nem aparecem aqui (12.3)
    # trava presa sem execução no banco: a tarefa acabou de nascer e ainda não abriu a sua
    rodando = (trava is not None and trava.locked()) or atual is not None
    marca = atual.escopos_prontos if atual is not None else -1
    # 204: o HTMX não troca nada. A pergunta de 2 s que já mostra este andamento não reinsere
    # nós na região viva (o leitor de tela não repete o anúncio), e a carga da casca não
    # repete em toda página o fim de uma busca velha
    # quem veio do redirect com o aviso vê o fim da busca, mesmo que ela já tenha acabado
    if (rodando and visto == marca) or (so_rodando and not rodando and not ja_rodava):
        return Response(status_code=204)
    return renderizar(
        request,
        "execucao/andamento.html",
        rodando=rodando,
        ja_rodava=ja_rodava,
        atual=atual,
        marca=marca,
        ultima=None if rodando else _ultima(con),
    )


def _disparar(request: Request, trava: asyncio.Lock) -> None:
    banco: Path = request.app.state.banco
    cliente: ClienteEducado = request.app.state.cliente
    relogio = _relogio(request)  # o `montar` do serve põe em app.state o relógio da agenda

    async def busca() -> None:
        with closing(abrir(banco)) as con:  # conexão própria: nunca dividida entre tarefas
            await executar_busca(con, cliente, relogio, "agora")

    # o `_rodar` da agenda: registra o erro e solta a trava no fim, como na busca da agenda
    tarefa = asyncio.create_task(_rodar("busca", trava, busca))
    tarefas = _tarefas(request)
    tarefas.add(tarefa)
    tarefa.add_done_callback(tarefas.discard)


@router.post("/buscar-agora")
async def buscar_agora(
    request: Request, con: Con, voltar: Annotated[str, Form()] = "/"
) -> Response:
    htmx = request.headers.get("hx-request") == "true"
    if getattr(request.app.state, "saindo", False):
        # o Sair já cancelou as buscas: uma nova usaria o cliente que o lifespan vai fechar
        if not htmx:
            return _de_volta(voltar)
        return renderizar(request, "execucao/andamento.html", saindo=True)
    trava: asyncio.Lock = request.app.state.travas["busca"]
    ja_rodava = trava.locked()
    if not ja_rodava:
        await trava.acquire()  # livre: não suspende, então a checagem acima vale (como no laço)
        _disparar(request, trava)
    if not htmx:
        resposta = _de_volta(voltar)  # sem HTMX: volta para a página de onde veio
        if ja_rodava:
            # o aviso atravessa o redirect (e o de "/") num cookie que a casca lê e a carga
            # do andamento apaga
            resposta.set_cookie(_AVISO, "1", max_age=60, httponly=True, samesite="strict")
        return resposta
    return _andamento(request, con, ja_rodava=ja_rodava)


@router.get("/execucao/atual")
async def atual(
    request: Request,
    con: Con,
    visto: int | None = None,
    so_rodando: bool = False,
    ja_roda: bool = False,
) -> Response:
    resposta = _andamento(request, con, ja_rodava=ja_roda, visto=visto, so_rodando=so_rodando)
    if ja_roda:
        resposta.delete_cookie(_AVISO, httponly=True, samesite="strict")
    return resposta


@router.post("/sair")
async def sair(request: Request) -> HTMLResponse:
    # o `executar` do `serve` guarda o uvicorn.Server aqui; o teste troca por um falso
    servidor = getattr(request.app.state, "servidor", None)
    if servidor is None:
        raise HTTPException(503, "o servidor não foi aberto pelo jobot serve")
    # daqui em diante o "Buscar agora" não cria tarefa; as que rodam param antes do fim do
    # lifespan fechar o cliente (ele também as cancela, para Ctrl+C e SIGTERM)
    request.app.state.saindo = True
    tarefas = list(_tarefas(request))
    for tarefa in tarefas:
        tarefa.cancel()
    await asyncio.gather(*tarefas, return_exceptions=True)
    servidor.should_exit = True  # o uvicorn termina os pedidos e roda o fim do lifespan
    return renderizar(request, "execucao/saiu.html", sem_barra=True)
