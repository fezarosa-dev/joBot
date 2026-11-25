"""Abertura da candidatura e respostas da faixa (planos T284 e T285; desenho 5.5 e 5.6) e o
preparo da candidatura pela IA (plano T438; desenho 9 da fase 4)."""

import asyncio
import functools
import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Annotated, Final, Literal

from fastapi import APIRouter, Form, HTTPException, Request, Response

from jobot.agenda.ia import Obter
from jobot.banco import acoes
from jobot.banco.conexao import abrir
from jobot.banco.ia import TarefaIA, tarefa_ia
from jobot.nucleo.ia import manual
from jobot.nucleo.ia.contrato import Falha, Pedido, Resposta
from jobot.nucleo.relogio import Relogio
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.detalhe_vaga import (
    PedidoDaVaga,
    Preparando,
    Preparos,
    contexto_do_preparo,
    gravar_resposta,
    pedido_da_vaga,
    preparos_de,
)
from jobot.painel.rotas import aviso_candidatura
from jobot.painel.rotas.execucao import criar_tarefa
from jobot.painel.rotas.vagas import VagaId
from jobot.painel.seguranca import Con, de_volta, idioma_do_pedido, renderizar

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/vagas/{vaga_id}/candidatura")
async def abriu(request: Request, con: Con, vaga_id: VagaId) -> Response:
    """Melhor esforço: 204 grave ou não (vaga fora de `nova`/`salva` não grava); sem vaga, 404."""
    try:
        acoes.abriu_candidatura(con, vaga_id, relogio_do_painel(request).agora())
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return Response(status_code=204)


def _depois(
    request: Request,
    con: sqlite3.Connection,
    vaga_id: int,
    voltar: str,
    confirmada: bool = False,
) -> Response:
    """Sem HTMX, volta à página; com ele, a faixa e os eventos (E20), mesmo sem mudança: quem
    escuta só relê o banco. A faixa não escuta o evento (desenho 5.6): a resposta já a troca."""
    if request.headers.get("hx-request") != "true":
        return de_volta(voltar)
    saida = aviso_candidatura.faixa(request, con, voltar, vaga_id if confirmada else None)
    saida.headers["HX-Trigger"] = f"candidatura-mudou, vaga-mudou-{vaga_id}"
    return saida


@router.post("/vagas/{vaga_id}/candidatura/resposta")
async def responder(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    resposta: Annotated[Literal["sim", "ainda_nao"], Form()],
    voltar: Annotated[str, Form()] = "/",
) -> Response:
    """Sim com troca de status mostra a confirmação com Desfazer; o resto, a próxima pendente."""
    agora = relogio_do_painel(request).agora()
    try:
        antes = acoes.responder_candidatura(con, vaga_id, resposta == "sim", agora)
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return _depois(request, con, vaga_id, voltar, confirmada=antes is not None)


@router.post("/vagas/{vaga_id}/candidatura/desfazer")
async def desfazer(
    request: Request, con: Con, vaga_id: VagaId, voltar: Annotated[str, Form()] = "/"
) -> Response:
    """Para onde a vaga volta, o servidor decide (E18); a pergunta não volta."""
    try:
        acoes.desfazer_candidatura(con, vaga_id, relogio_do_painel(request).agora())
    except LookupError as erro:
        raise HTTPException(404, "vaga não existe") from erro
    return _depois(request, con, vaga_id, voltar)


# --- preparar candidatura (desenho 9 da fase 4; T438, D234) ---------------------------------
#
# O `POST` dispara a tarefa e responde na hora com a espera; o HTMX pergunta a cada 2 s (204
# enquanto a IA trabalha). O preparo em curso fica em `app.state.ia_preparos`; a marca da vaga
# em `app.state.ia_pessoa` faz o laço do encaixe esperar (desenho 5.4, item 6). Só o acerto
# grava; a falha fica para a primeira leitura e o preparo anterior segue no banco. A IA manual
# não dispara nada: a página mostra o pedido e `colar` lê a resposta.

# por cima do prazo do pedido, a leitura do cofre e a subida do `llama-server` (como o teste ao
# ligar, `ia.FOLGA_TESTE_S`); passou disso, `tempo_esgotado`
FOLGA_S: Final = 150.0


def espera_maxima(pedido: Pedido) -> float:
    """Quanto a tarefa espera o backend: a thread presa segue até o próprio prazo do cliente."""
    return pedido.prazo_s + FOLGA_S


def _existe(con: sqlite3.Connection, vaga_id: int) -> None:
    if con.execute("SELECT 1 FROM vaga WHERE id = ?", (vaga_id,)).fetchone() is None:
        raise HTTPException(404, "vaga não existe")


def _secao(request: Request, con: sqlite3.Connection, vaga_id: int, lado: bool) -> Response:
    """A seção do preparo sozinha (`detalhe/_preparo.html`), como no detalhe: a página da vaga ou,
    com `lado`, o detalhe ao lado da lista (os ids levam o prefixo)."""
    contexto = contexto_do_preparo(con, vaga_id, preparos_de(request), idioma_do_pedido(request))
    return renderizar(
        request,
        "detalhe/_preparo.html",
        preparo=contexto,
        vaga_id=vaga_id,
        retorno=f"/vagas/{vaga_id}",
        prefixo="lado-" if lado else "",
        n=2 if lado else 1,
        foco=True,
    )


def _depois_do_preparo(
    request: Request, con: sqlite3.Connection, vaga_id: int, voltar: str, lado: str
) -> Response:
    if request.headers.get("hx-request") != "true":
        return de_volta(voltar)  # sem JavaScript, a página da vaga mostra a espera ou o resultado
    return _secao(request, con, vaga_id, lado == "1")


@router.get("/vagas/{vaga_id}/candidatura/preparo")
async def preparo_da_vaga(request: Request, con: Con, vaga_id: VagaId, lado: str = "") -> Response:
    """A pergunta do HTMX: 204 enquanto a IA trabalha (nada troca); depois, a seção."""
    _existe(con, vaga_id)
    atual = preparos_de(request).get(vaga_id)
    if atual is not None and atual.estado == "preparando":
        return Response(status_code=204)
    return _secao(request, con, vaga_id, lado == "1")


@router.post("/vagas/{vaga_id}/candidatura/preparar")
async def preparar(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    voltar: Annotated[str, Form()] = "/",
    lado: Annotated[str, Form()] = "",
) -> Response:
    """Dispara o preparo; com um em curso (clique duplo), só devolve a espera. Sem a tarefa
    ligada, na IA manual ou sem perfil, nada sai: a seção diz por quê."""
    _existe(con, vaga_id)
    preparos = preparos_de(request)
    tarefa = tarefa_ia(con, "candidatura")
    atual = preparos.get(vaga_id)
    em_curso = atual is not None and atual.estado == "preparando"
    if tarefa.ligada and tarefa.backend != manual.BACKEND and not em_curso:
        idioma = idioma_do_pedido(request)
        feito = pedido_da_vaga(con, vaga_id, tarefa.backend, tarefa.modelo, idioma)
        if feito is not None:
            await _disparar(request, vaga_id, tarefa, feito)
    return _depois_do_preparo(request, con, vaga_id, voltar, lado)


async def _disparar(request: Request, vaga_id: int, tarefa: TarefaIA, feito: PedidoDaVaga) -> None:
    preparos = preparos_de(request)
    obter: Obter | None = getattr(request.app.state, "ia", None)
    if obter is None:  # o app sem o `serve` não tem a fábrica
        preparos[vaga_id] = Preparando("falhou", tarefa.backend, "servico_fora")
        return
    preparos[vaga_id] = Preparando("preparando", tarefa.backend)
    estado = request.app.state
    if getattr(estado, "ia_pessoa", None) is None:
        estado.ia_pessoa = set()
    marca = ("candidatura", vaga_id)
    estado.ia_pessoa.add(marca)
    trava = asyncio.Lock()  # a de `criar_tarefa`, que a solta no fim; uma por preparo
    await trava.acquire()  # nova: não suspende
    tarefa_de_fundo = functools.partial(
        _preparar,
        preparos,
        estado.ia_pessoa,
        marca,
        obter,
        request.app.state.banco,
        relogio_do_painel(request),
        vaga_id,
        tarefa,
        feito,
    )
    criar_tarefa(request, "preparar candidatura", trava, tarefa_de_fundo)


async def _preparar(
    preparos: Preparos,
    pessoa: set[object],
    marca: object,
    obter: Obter,
    banco: Path,
    relogio: Relogio,
    vaga_id: int,
    tarefa: TarefaIA,
    feito: PedidoDaVaga,
) -> None:
    """Pede, confere e grava. Começa em falha (padrões «Serve»): erro fora do contrato vai ao log
    e vira `servico_fora`; o cancelamento (fim do servidor) também passa pelo `finally`. O log só
    leva backend, modelo, duração e motivo (desenho 5.3)."""
    inicio = relogio.agora()
    resultado: Preparando | None = Preparando("falhou", tarefa.backend, "servico_fora")
    try:
        try:
            resposta = await _pedir(obter, tarefa, feito.pedido)
            with closing(abrir(banco)) as con:  # conexão própria: a do pedido já fechou
                gravar_resposta(con, vaga_id, feito, resposta, relogio.agora())
            resultado = None
        except Falha as falha:
            resultado = Preparando("falhou", tarefa.backend, falha.motivo)
        except Exception:
            log.exception("ia candidatura %s: erro fora do contrato", tarefa.backend)
    finally:
        pessoa.discard(marca)
        if resultado is None:
            preparos.pop(vaga_id, None)
        else:
            preparos[vaga_id] = resultado
        segundos = (relogio.agora() - inicio).total_seconds()
        motivo = "ok" if resultado is None else resultado.motivo
        log.info(
            "ia candidatura %s %s: %s em %.1f s", tarefa.backend, tarefa.modelo, motivo, segundos
        )


async def _pedir(obter: Obter, tarefa: TarefaIA, pedido: Pedido) -> Resposta:
    passo = asyncio.ensure_future(_chamar(obter, tarefa, pedido))
    try:
        feitas, _ = await asyncio.wait({passo}, timeout=espera_maxima(pedido))
        if not feitas:  # a thread presa segue até o próprio prazo; a tela não espera
            raise Falha("tempo_esgotado")
        return passo.result()
    finally:
        passo.cancel()  # terminado, não faz nada; senão fecha o cliente (o `finally` dele)


async def _chamar(obter: Obter, tarefa: TarefaIA, pedido: Pedido) -> Resposta:
    backend = await asyncio.to_thread(obter, tarefa.backend, tarefa.modelo)
    try:
        return await asyncio.to_thread(backend.pedir, pedido)
    finally:
        backend.fechar()


@router.post("/vagas/{vaga_id}/candidatura/colar")
async def colar(
    request: Request,
    con: Con,
    vaga_id: VagaId,
    resposta: Annotated[str, Form()] = "",
    voltar: Annotated[str, Form()] = "/",
    lado: Annotated[str, Form()] = "",
) -> Response:
    """A resposta colada da IA manual: o mesmo esquema e as mesmas conferências de todo backend.
    Fora do formato, o motivo aparece e o preparo anterior fica. Só com a tarefa no manual."""
    _existe(con, vaga_id)
    tarefa = tarefa_ia(con, "candidatura")
    preparos = preparos_de(request)
    if tarefa.ligada and tarefa.backend == manual.BACKEND:
        idioma = idioma_do_pedido(request)
        feito = pedido_da_vaga(con, vaga_id, tarefa.backend, tarefa.modelo, idioma)
        if feito is not None:
            try:
                lida = manual.ler_resposta(feito.pedido, resposta)
            except Falha as falha:
                preparos[vaga_id] = Preparando("falhou", manual.BACKEND, falha.motivo)
            else:
                gravar_resposta(con, vaga_id, feito, lida, relogio_do_painel(request).agora())
                preparos.pop(vaga_id, None)
    return _depois_do_preparo(request, con, vaga_id, voltar, lado)
