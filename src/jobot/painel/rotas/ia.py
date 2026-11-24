"""Aba IA de Configurações (desenho 5.6, 6 e 10.3 da fase 4; T415; D202).

Os atalhos ("Desligar a IA", "Tudo offline", "Tudo Claude") e a tabela por tarefa gravam
`ia_tarefas`. Só aparecem os backends configurados: os pagos com chave no cofre, o compatível com
endereço e o local com o modelo baixado (`app.state.modelo_local`, que o `serve` põe; sem ele, não
há modelo). Ligar o `encaixe` num serviço pago pede antes a confirmação do custo (desenho 5.6), em
dois passos e sem JavaScript. A chave nunca entra no contexto: só se ela existe. O formulário
(`POST /configuracoes/ia`) fica em `configuracoes.py`, que já tem a página; este módulo não importa
aquele. O teste ao ligar (T416) vem morar aqui.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any, Final

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import FormData

from jobot.banco.ia import TarefaIA, chamadas_do_dia, gravar_tarefas_ia, tarefa_ia
from jobot.nucleo.ia.anthropic import MODELOS
from jobot.nucleo.ia.contrato import limites
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.rotas.perfil import frase_de_privacidade
from jobot.painel.rotas.servicos import SERVICOS_IA, contexto_chaves_ia
from jobot.painel.seguranca import CAMPO_CSRF, Con

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
    form: FormData, configurados: list[str], local: str | None
) -> dict[str, TarefaIA] | tuple[dict[str, dict[str, Any]], str, str]:
    """As tarefas da tabela, ou o digitado, o campo errado e a chave do erro."""
    novas: dict[str, TarefaIA] = {}
    digitado: dict[str, dict[str, Any]] = {}
    for nome in tarefas():
        b, m = form.get(f"{nome}_backend"), form.get(f"{nome}_modelo")
        backend = b if isinstance(b, str) else ""
        modelo = m.strip() if isinstance(m, str) else ""
        ligada = f"{nome}_ligada" in form
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
            return digitado, *erro
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
        lidas = _da_tabela(form, configurados, local)
        if isinstance(lidas, tuple):
            digitado, campo, erro = lidas
            return 422, {"ia_digitado": digitado, "ia_erro_campo": campo, "erro": erro}
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
    acordar = getattr(request.app.state, "ia_acordar", None)
    if acordar is not None and any(t.ligada for t in novas.values()):
        acordar.set()  # o laço lê a tarefa nova já (D198.5)
    return IA + "?salvo=1"


def _digitado(novas: Mapping[str, TarefaIA]) -> dict[str, dict[str, Any]]:
    return {
        n: {"ligada": t.ligada, "backend": t.backend, "modelo": t.modelo} for n, t in novas.items()
    }
