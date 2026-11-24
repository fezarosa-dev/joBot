"""Aba IA de Configurações (desenho 5.6, 6 e 10.3 da fase 4; T415; D202).

Os atalhos ("Desligar a IA", "Tudo offline", "Tudo Claude") e a tabela por tarefa gravam
`ia_tarefas`. Só aparecem os backends configurados: os pagos com chave no cofre, o compatível com
endereço e o local com o modelo baixado (`app.state.modelo_local`, que o `serve` põe; sem ele, não
há modelo). Ligar o `encaixe` num serviço pago pede antes a confirmação do custo (desenho 5.6), em
dois passos e sem JavaScript. A chave nunca entra no contexto: só se ela existe. O formulário
(`POST /configuracoes/ia`) fica em `configuracoes.py`, que já tem a página; este módulo não importa
aquele.

Teste ao ligar (desenho 6.1, T416, D203): gravar uma tarefa ligada num par (backend, modelo) novo
põe o par numa fila (`app.state.ia_fila`), testada por uma tarefa de fundo, um par por vez, com um
pedido curto de exemplo fictício. O resultado fica em `app.state.ia_testes[par]`; falhou, a tarefa
desliga. Enquanto o par espera ou roda, ele fica em `app.state.ia_pessoa` e o laço espera.
"""

import asyncio
import functools
import logging
import re
from collections.abc import Callable, Iterable, Mapping
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from starlette.datastructures import FormData

from jobot.agenda.ia import Obter
from jobot.banco.conexao import abrir
from jobot.banco.ia import TarefaIA, chamadas_do_dia, gravar_tarefas_ia, tarefa_ia
from jobot.nucleo.ia.anthropic import MODELOS
from jobot.nucleo.ia.contrato import Falha, Motivo, Pedido, limites
from jobot.nucleo.ia.pedidos import pedido_encaixe, texto_encaixe
from jobot.nucleo.relogio import Relogio
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.rotas.execucao import criar_tarefa
from jobot.painel.rotas.perfil import frase_de_privacidade
from jobot.painel.rotas.servicos import SERVICOS_IA, contexto_chaves_ia
from jobot.painel.seguranca import CAMPO_CSRF, Con, renderizar

log = logging.getLogger(__name__)

router = APIRouter(prefix="/configuracoes/ia")

IA: Final = "/configuracoes/ia"
LOCAL: Final = "local"
BACKENDS: Final = (*SERVICOS_IA, LOCAL)  # a ordem do select
PAGOS: Final = ("anthropic", "openai", "gemini")  # cobrados por uso e ainda não provados (D185.27)
ATALHOS: Final = ("desligada", "offline", "claude")
# o nome vai no corpo JSON do pedido: ASCII visível, sem espaço (`qwen3:4b`, `org/modelo`)
_MODELO: Final = re.compile(r"[!-~]{1,200}")


def tarefas() -> tuple[str, ...]:
    return tuple(limites()["tarefas"])


def modelo_local(request: Request) -> str | None:
    """O nome do modelo local baixado, ou `None`; o `serve` põe o leitor em `app.state`."""
    ler: Callable[[], str | None] | None = getattr(request.app.state, "modelo_local", None)
    return None if ler is None else ler()


async def _configurados(request: Request, con: Con) -> tuple[list[str], bool]:
    """Os backends com onde rodar, na ordem de `BACKENDS`, e se o cofre falhou."""
    cartoes = (await contexto_chaves_ia(request, con))["chaves_ia"]
    prontos = {
        c["servico"]
        for c in cartoes
        if (c["endereco"] if c["servico"] == "compativel" else c["mascara"])
    }
    if modelo_local(request) is not None:
        prontos.add(LOCAL)
    return [b for b in BACKENDS if b in prontos], any(c["falhou"] for c in cartoes)


def _modo(atuais: Mapping[str, TarefaIA]) -> str:
    ligadas = [t for t in atuais.values() if t.ligada]
    if not ligadas:
        return "desligada"
    if len(ligadas) == len(atuais) and all(t.backend == LOCAL for t in ligadas):
        return "offline"
    if len(ligadas) == len(atuais) and all(t.backend == "anthropic" for t in ligadas):
        return "claude"
    return "personalizado"


async def contexto_ia(request: Request, con: Con) -> dict[str, Any]:
    configurados, cofre_falhou = await _configurados(request, con)
    agora = relogio_do_painel(request).agora()
    atuais = {nome: tarefa_ia(con, nome) for nome in tarefas()}
    testes = _testes(request)
    linhas = [
        {
            "nome": nome,
            "ligada": t.ligada,
            "backend": t.backend,
            "modelo": t.modelo,
            "privacidade": frase_de_privacidade(t, "configuracoes.ia.privacidade."),
            "parada": t.ligada and t.backend not in configurados,
            # o teto do dia é por backend de fora (D198.10); o local não tem teto
            "hoje": chamadas_do_dia(con, t.backend, agora)
            if t.backend not in ("", LOCAL)
            else None,
            "teste": testes.get((t.backend, t.modelo)),
        }
        for nome, t in atuais.items()
    ]
    return {
        "ia_linhas": linhas,
        "ia_modo": _modo(atuais),
        "ia_backends": configurados,
        "ia_cofre_falhou": cofre_falhou,
        "ia_local": modelo_local(request),
        "ia_teto": limites()["laco"]["max_por_dia_fora"],
        "ia_pagos": PAGOS,
        "ia_modelos_claude": MODELOS,
        "ia_digitado": None,
        "ia_erro_tarefa": None,
        "ia_erro_campo": None,
        "ia_custo": None,
    }


def _do_atalho(
    atalho: str, atuais: Mapping[str, TarefaIA], configurados: list[str], local: str | None
) -> dict[str, TarefaIA] | str:
    """As tarefas que o atalho grava, ou o endereço para onde ele leva quando falta algo."""
    if atalho == "desligada":  # backend e modelo ficam: religar é um clique
        return {n: replace(t, ligada=False) for n, t in atuais.items()}
    if atalho == "offline":
        if local is None:
            return "/configuracoes/ferramentas"
        return {n: TarefaIA(True, LOCAL, local) for n in atuais}
    if "anthropic" not in configurados:
        return "/configuracoes/servicos"
    return {n: TarefaIA(True, "anthropic", limites()["tarefas"][n]["claude"]) for n in atuais}


def _da_tabela(
    form: FormData, atuais: Mapping[str, TarefaIA], configurados: list[str], local: str | None
) -> dict[str, TarefaIA] | tuple[dict[str, dict[str, Any]], str, str, str]:
    """As tarefas da tabela, ou o digitado, a tarefa e o campo errados e a chave do erro."""
    novas: dict[str, TarefaIA] = {}
    digitado: dict[str, dict[str, Any]] = {}
    for nome in tarefas():
        b, m = form.get(f"{nome}_backend"), form.get(f"{nome}_modelo")
        backend = b if isinstance(b, str) else ""
        modelo = m.strip() if isinstance(m, str) else ""
        ligada = f"{nome}_ligada" in form
        if b is None and not ligada:
            # sem backend configurado (ou com o cofre falhando) a tela não mostra o select e a
            # caixa vem desativada: nada ali era editável, então a tarefa gravada fica
            novas[nome] = atuais[nome]
            continue
        if backend and backend not in configurados:
            raise HTTPException(422)  # a tela só mostra os configurados (lista fechada)
        digitado[nome] = {"ligada": ligada, "backend": backend, "modelo": modelo}
        erro: tuple[str, str] | None = None
        if backend == LOCAL:
            modelo = local or ""  # vale o baixado; o digitado não conta
        elif backend == "anthropic":
            modelo = modelo or limites()["tarefas"][nome]["claude"]
            if modelo not in MODELOS:
                erro = ("modelo", "configuracoes.ia.erro.modelo_claude")
        elif backend and (modelo or ligada) and not _MODELO.fullmatch(modelo):
            erro = ("modelo", "configuracoes.ia.erro.modelo")
        if ligada and not backend:
            erro = ("backend", "configuracoes.ia.erro.sem_backend")
        if erro:
            return digitado, nome, *erro
        novas[nome] = TarefaIA(ligada, backend, modelo if backend else "")
    return novas


async def gravar_ia(request: Request, con: Con, form: FormData) -> str | tuple[int, dict[str, Any]]:
    """Grava o atalho ou a tabela de `form`; devolve o endereço do 303 ou o status e o contexto
    da página (erro, ou a confirmação do custo). Nada é gravado sem a resposta 303."""
    configurados, _ = await _configurados(request, con)
    local = modelo_local(request)
    atuais = {nome: tarefa_ia(con, nome) for nome in tarefas()}
    atalho = form.get("atalho")
    if atalho is not None:
        if atalho not in ATALHOS:
            raise HTTPException(422)
        feitas = _do_atalho(str(atalho), atuais, configurados, local)
        if isinstance(feitas, str):
            return feitas
        novas = feitas
    else:
        lidas = _da_tabela(form, atuais, configurados, local)
        if isinstance(lidas, tuple):
            digitado, tarefa, campo, erro = lidas
            contexto = {"ia_digitado": digitado, "ia_erro_tarefa": tarefa, "ia_erro_campo": campo}
            return 422, contexto | {"erro": erro}
        novas = lidas
    # ligar o laço num serviço pago (ou trocar de serviço pago) pede a confirmação do custo
    # ponytail: na 0.5.0 toda tarefa é do laço (só o `encaixe`); as sob pedido da 0.6.0 decidem
    caras = [
        t.backend
        for n, t in novas.items()
        if t.ligada
        and t.backend in PAGOS
        and not (atuais[n].ligada and atuais[n].backend == t.backend)
    ]
    if caras and form.get("confirmar") != "1":
        campos = [(k, v) for k, v in form.multi_items() if k not in (CAMPO_CSRF, "confirmar")]
        custo = {"campos": campos, "servico": caras[0]}
        return 200, {"ia_custo": custo, "ia_digitado": None if atalho else _digitado(novas)}
    gravar_tarefas_ia(con, novas)
    # antes de acordar o laço: ele já acorda esperando o teste (desenho 5.4, item 6)
    await _enfileirar(request, _pares_novos(novas, atuais, _testes(request)))
    acordar = getattr(request.app.state, "ia_acordar", None)
    if acordar is not None and any(t.ligada for t in novas.values()):
        acordar.set()  # o laço lê a tarefa nova já (D198.5)
    return IA + "?salvo=1"


def _digitado(novas: Mapping[str, TarefaIA]) -> dict[str, dict[str, Any]]:
    return {
        n: {"ligada": t.ligada, "backend": t.backend, "modelo": t.modelo} for n, t in novas.items()
    }


# --- teste ao ligar (desenho 6.1; T416, D203) -----------------------------------------------

Par = tuple[str, str]
# o exemplo do teste: fictício e fixo, nenhuma vaga do banco sai daqui
_EXEMPLO: Final = ("Pessoa desenvolvedora Python", "Buscamos quem trabalhe com Python e SQL.")


@dataclass(frozen=True)
class Teste:
    estado: Literal["testando", "ok", "falhou"]
    motivo: Motivo | None = None


_OK: Final = Teste("ok")
# por cima do prazo do pedido, o teste inteiro ainda espera a leitura do cofre e a subida do
# `llama-server` (`llama.ESPERA_S`, 120 s); passou disso, `tempo_esgotado` e a fila anda
FOLGA_TESTE_S: Final = 150.0


def _no_estado(request: Request, nome: str, novo: Callable[[], Any]) -> Any:
    estado = request.app.state
    if getattr(estado, nome, None) is None:
        setattr(estado, nome, novo())
    return getattr(estado, nome)


def _testes(request: Request) -> dict[Par, Teste]:
    testes: dict[Par, Teste] = _no_estado(request, "ia_testes", dict)
    return testes


def pedido_de_teste(backend: str, modelo: str) -> Pedido:
    """Um pedido curto da tarefa, com o prazo do teste (30 s fora, 180 s local; `ia.json`)."""
    lim = limites()
    lugar = "local" if backend == LOCAL else "fora"
    pedido = pedido_encaixe(texto_encaixe(*_EXEMPLO), backend, modelo)
    return replace(pedido, prazo_s=lim["prazo_teste_s"][lugar], max_tokens=lim["max_tokens_teste"])


def _pares_novos(
    novas: Mapping[str, TarefaIA], atuais: Mapping[str, TarefaIA], testes: Mapping[Par, Teste]
) -> list[Par]:
    """Os pares das tarefas que ligaram agora ou trocaram de par, sem os que já passaram."""
    pares: list[Par] = []
    for nome, t in novas.items():
        par, antes = (t.backend, t.modelo), atuais[nome]
        mudou = not antes.ligada or (antes.backend, antes.modelo) != par
        if t.ligada and mudou and testes.get(par) != _OK and par not in pares:
            pares.append(par)
    return pares


async def _enfileirar(request: Request, pares: Iterable[Par], *, de_novo: bool = False) -> None:
    """Põe os pares na fila (o que já espera fica onde está; `de_novo` refaz o que roda agora,
    porque a chave mudou no meio) e sobe a tarefa de fundo, se ela não roda. Sem a fábrica do
    `serve` (`app.state.ia`), não há como testar."""
    obter: Obter | None = getattr(request.app.state, "ia", None)
    if obter is None:
        return
    fila: list[Par] = _no_estado(request, "ia_fila", list)
    testes = _testes(request)
    pessoa: set[object] = _no_estado(request, "ia_pessoa", set)
    for par in pares:
        if par in fila[1:] or (par in fila[:1] and not de_novo):
            continue
        fila.append(par)
        testes[par] = Teste("testando")
        pessoa.add(par)
    trava: asyncio.Lock = _no_estado(request, "ia_trava_teste", asyncio.Lock)
    if fila and not trava.locked():
        await trava.acquire()  # livre: não suspende, então a checagem acima vale (como no laço)
        banco: Path = request.app.state.banco
        tarefa = functools.partial(
            _testar_fila, fila, testes, pessoa, obter, banco, relogio_do_painel(request)
        )
        criar_tarefa(request, "teste da IA", trava, tarefa)


async def _testar_fila(
    fila: list[Par],
    testes: dict[Par, Teste],
    pessoa: set[object],
    obter: Obter,
    banco: Path,
    relogio: Relogio,
) -> None:
    """Um par por vez, na ordem da fila. Erro de qualquer tipo vai ao log e a fila anda: o par
    nunca fica em "testando" com o laço esperando para sempre."""
    while fila:
        par = fila[0]
        resultado = Teste("falhou", "servico_fora")  # começa em falha (padrões «Serve»)
        try:
            try:
                resultado = await _um_teste(obter, par, relogio)
            except Exception:
                log.exception("ia teste %s %s: erro fora do contrato", *par)
            # pedido de novo no meio (a chave mudou): vale o resultado do seguinte
            if resultado != _OK and par not in fila[1:]:
                _desligar(banco, par)
        finally:
            # o cancelamento (fim do servidor) passa só por aqui: a tarefa gravada fica
            fila.pop(0)
            if par not in fila:
                testes[par] = resultado
                pessoa.discard(par)


async def _um_teste(obter: Obter, par: Par, relogio: Relogio) -> Teste:
    """O teste de um par, com o prazo contado do próprio começo."""
    inicio = relogio.agora()
    pedido = pedido_de_teste(*par)
    passo = asyncio.ensure_future(_testar(obter, par, pedido))
    try:
        feitas, _ = await asyncio.wait({passo}, timeout=pedido.prazo_s + FOLGA_TESTE_S)
        if not feitas:  # a thread presa segue até o próprio prazo; a fila não espera
            raise Falha("tempo_esgotado")
        passo.result()
        resultado = _OK
    except Falha as falha:
        resultado = Teste("falhou", falha.motivo)
    finally:
        passo.cancel()  # terminado, não faz nada; senão fecha o cliente (o `finally` dele)
    segundos = (relogio.agora() - inicio).total_seconds()
    log.info("ia teste %s %s: %s em %.1f s", *par, resultado.motivo or "ok", segundos)
    return resultado


async def _testar(obter: Obter, par: Par, pedido: Pedido) -> None:
    backend = await asyncio.to_thread(obter, *par)
    try:
        await asyncio.to_thread(backend.pedir, pedido)
    finally:
        backend.fechar()


def _desligar(banco: Path, par: Par) -> None:
    """Desliga as tarefas ligadas no par que falhou; backend e modelo ficam (desenho 6.1). Erro
    (banco, disco) vai ao log: a fila segue com os outros pares."""
    try:
        with closing(abrir(banco)) as con:  # conexão própria: a do pedido já fechou
            atuais = {nome: tarefa_ia(con, nome) for nome in tarefas()}
            caidas = {
                n: replace(t, ligada=False)
                for n, t in atuais.items()
                if t.ligada and (t.backend, t.modelo) == par
            }
            if caidas:
                gravar_tarefas_ia(con, caidas)
    except Exception:
        log.exception("ia teste %s %s: não consegui desligar a tarefa", *par)


async def servico_trocou(request: Request, con: Con, servico: str) -> None:
    """A chave ou o endereço do serviço mudou (aba Serviços): os pares ligados nele testam de
    novo."""
    await refazer_testes(request, servico, [tarefa_ia(con, nome) for nome in tarefas()])


async def refazer_testes(request: Request, servico: str, atuais: Iterable[TarefaIA]) -> None:
    """O serviço mudou (chave, endereço, ou o modelo local trocado em Ferramentas): os testes dele
    valem de novo, os pares ligados nele voltam à fila e o laço acorda, porque a rodada em curso
    montou o cliente com o que era antes (ela para sozinha na falha)."""
    testes = _testes(request)
    for par in [p for p, t in testes.items() if p[0] == servico and t.estado != "testando"]:
        del testes[par]
    pares = dict.fromkeys(
        (t.backend, t.modelo) for t in atuais if t.ligada and t.backend == servico
    )
    await _enfileirar(request, pares, de_novo=True)
    acordar = getattr(request.app.state, "ia_acordar", None)
    if acordar is not None and pares:
        acordar.set()


@router.get("/teste/{tarefa}")
async def estado_do_teste(request: Request, con: Con, tarefa: str) -> Response:
    """O HTMX pergunta a cada 2 s; enquanto o par da tarefa testa, 204 (nada troca). Depois, a
    tarefa inteira com o resultado, que puxa o foco se ele estava solto."""
    if tarefa not in tarefas():
        raise HTTPException(404)
    atual = tarefa_ia(con, tarefa)
    teste = _testes(request).get((atual.backend, atual.modelo))
    if teste is not None and teste.estado == "testando":
        return Response(status_code=204)
    contexto = await contexto_ia(request, con)
    (linha,) = [linha for linha in contexto["ia_linhas"] if linha["nome"] == tarefa]
    return renderizar(
        request, "configuracoes/_ia_tarefa.html", linha=linha, ia_foco_teste=True, **contexto
    )
