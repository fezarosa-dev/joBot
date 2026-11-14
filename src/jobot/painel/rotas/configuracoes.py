"""Configurações e interruptores (desenho 13.2 e 13.7; plano T54; decisão 17 e DP8).

Cinco grupos em `/configuracoes/{grupo}`: fontes (uma chave por fonte, por leva), funções (as chaves
da 13.7 e o N dos destaques), segundo plano, aparência (tema e idioma, pelas rotas `/preferencias`)
e privacidade (onde ficam os dados, a recomendação de disco cifrado e o aviso de versão).

Checkbox sem marca é chave desligada: o formulário de cada grupo manda o estado inteiro. Ligar ou
desligar a conversão de moeda chama `aplicar_cotacoes` e, com ela ou com as regras de ocultar
mudadas, `recalcular_encaixe`, as duas com `hoje` = dia local do `Relogio` (nunca o dia UTC).
Todo comando do sistema passa pelo executor de `app.state.rodar_comando`, o ambiente de
`app.state.ambiente` e a plataforma de `app.state.plataforma`: o teste põe os falsos.
"""

import re
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from jobot.banco import buscas, cadastros, cotacoes
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.painel.ambiente import ambiente_do_painel, no_linux, rodar_do_painel
from jobot.painel.rotas.vagas import relogio_do_painel
from jobot.painel.seguranca import Con, renderizar
from jobot.sistema import caso, segundo_plano_linux
from jobot.sistema.segundo_plano_linux import Recusa

router = APIRouter(prefix="/configuracoes")

GRUPOS = ("fontes", "funcoes", "segundo-plano", "aparencia", "privacidade")
FUNCOES = (
    "descoberta_cc_ligada",
    "paginas_ligadas",
    "enriquecimento_ligado",
    "destaques_ligados",
    "conversao_moeda_ligada",
    "regras_ocultar_ligadas",
)
_N_MAX = 100
_N = re.compile(r"[0-9]{1,3}", re.ASCII)
_PARCIAIS = {
    "fontes": "fontes",
    "funcoes": "funcoes",
    "segundo-plano": "segundo_plano",
    "aparencia": "aparencia",
    "privacidade": "privacidade",
}


def _hoje(request: Request) -> date:
    # o dia de calendário é o do fuso local, como no resto do painel (decisão 17, DP8)
    return relogio_do_painel(request).agora().astimezone().date()


# --- o que cada grupo mostra ---------------------------------------------------------------

Contexto = Callable[[Request, Con], Awaitable[dict[str, Any]]]


async def _ctx_fontes(request: Request, con: Con) -> dict[str, Any]:
    todas = cadastros.fontes(con)
    return {"levas": [(leva, [f for f in todas if f.leva == leva]) for leva in ("A", "B")]}


async def _ctx_funcoes(request: Request, con: Con) -> dict[str, Any]:
    valores = {c: bool(ler_config(con, c)) for c in FUNCOES}
    return {"funcoes": FUNCOES, "valores": valores, "destaques_n": ler_config(con, "destaques_n")}


async def _ctx_segundo_plano(request: Request, con: Con) -> dict[str, Any]:
    linux = no_linux(request)
    estado = None
    if linux:
        estado = await run_in_threadpool(
            segundo_plano_linux.status, rodar_do_painel(request), env=ambiente_do_painel(request)
        )
    return {
        "linux": linux,
        "estado": estado,
        "container": caso.nome_do_container(ambiente_do_painel(request)),
        # D61 (A1): no Linux o interruptor segue o is-enabled do systemd; ativo não entra
        "ligado": estado is not None and estado.habilitado,
    }


async def _ctx_aparencia(request: Request, con: Con) -> dict[str, Any]:
    return {}


async def _ctx_privacidade(request: Request, con: Con) -> dict[str, Any]:
    return {
        "pasta": str(request.app.state.banco.parent),
        "aviso_versao": ler_config(con, "aviso_versao_ligada", False) is True,
    }


_CONTEXTOS: dict[str, Contexto] = {
    "fontes": _ctx_fontes,
    "funcoes": _ctx_funcoes,
    "segundo-plano": _ctx_segundo_plano,
    "aparencia": _ctx_aparencia,
    "privacidade": _ctx_privacidade,
}


async def _pagina(
    request: Request, con: Con, grupo: str, status: int = 200, **ctx: Any
) -> Response:
    contexto: dict[str, Any] = {
        "grupo": grupo,
        "abas": [(g, "configuracoes.grupo." + g.replace("-", "_")) for g in GRUPOS],
        "parcial": f"configuracoes/{_PARCIAIS[grupo]}.html",
        "erro": None,
        "motivo": None,
    }
    contexto |= await _CONTEXTOS[grupo](request, con)
    resposta = renderizar(request, "configuracoes/pagina.html", **(contexto | ctx))
    resposta.status_code = status
    return resposta


def _grupo_valido(grupo: str) -> str:
    if grupo not in GRUPOS:
        raise HTTPException(404)
    return grupo


def _volta(grupo: str) -> RedirectResponse:
    return RedirectResponse(f"/configuracoes/{grupo}", status_code=303)


# --- gravações -----------------------------------------------------------------------------


async def _gravar_fontes(request: Request, con: Con) -> Response:
    form = await request.form()
    marcadas = {str(v) for v in form.getlist("fonte")}
    conhecidas = {f.chave for f in cadastros.fontes(con)}
    if not marcadas <= conhecidas:
        raise HTTPException(422)
    for chave in sorted(conhecidas):
        cadastros.ligar_fonte(con, chave, chave in marcadas)
    return _volta("fontes")


async def _gravar_funcoes(request: Request, con: Con) -> Response:
    form = await request.form()
    novos = {c: c in form for c in FUNCOES}
    destaques_n = ler_config(con, "destaques_n")
    digitado = form.get("destaques_n")
    if digitado is not None:
        achado = _N.fullmatch(str(digitado).strip())
        if achado is None or not 1 <= int(achado[0]) <= _N_MAX:
            # a página volta com o que foi marcado, e nada do formulário é gravado
            return await _pagina(
                request,
                con,
                "funcoes",
                422,
                valores=novos,
                destaques_n=str(digitado),
                erro="configuracoes.erro.destaques_n",
            )
        destaques_n = int(achado[0])
    antes = {c: bool(ler_config(con, c)) for c in FUNCOES}
    conversao, regras = novos["conversao_moeda_ligada"], novos["regras_ocultar_ligadas"]
    mudou_conversao = conversao != antes["conversao_moeda_ligada"]
    hoje = _hoje(request)
    # recalcula antes de gravar: se falhar, a chave segue como estava e salvar de novo refaz tudo
    if mudou_conversao:
        cotacoes.aplicar_cotacoes(con, conversao_ligada=conversao, hoje=hoje)
    if mudou_conversao or regras != antes["regras_ocultar_ligadas"]:
        buscas.recalcular_encaixe(con, None, regras, hoje=hoje)
    for chave, valor in novos.items():
        gravar_config(con, chave, valor)
    gravar_config(con, "destaques_n", destaques_n)
    return _volta("funcoes")


async def _gravar_segundo_plano(request: Request, con: Con) -> Response:
    form = await request.form()
    linux = no_linux(request)
    ligar = "segundo_plano" in form and linux  # fora do Linux o segundo plano é desativado
    rodar, env = rodar_do_painel(request), ambiente_do_painel(request)
    try:
        if ligar:
            await run_in_threadpool(segundo_plano_linux.ligar, rodar, env=env)
        elif linux:
            await run_in_threadpool(segundo_plano_linux.desligar, rodar, env=env)
    except Recusa as recusa:
        return await _pagina(request, con, "segundo-plano", motivo=recusa.motivo)
    except (ValueError, OSError) as falha:  # caractere de controle no caminho, disco, permissão
        return await _pagina(request, con, "segundo-plano", erro=str(falha))
    gravar_config(con, "segundo_plano", ligar)
    return _volta("segundo-plano")


async def _gravar_privacidade(request: Request, con: Con) -> Response:
    form = await request.form()
    gravar_config(con, "aviso_versao_ligada", "aviso_versao_ligada" in form)
    return _volta("privacidade")


_GRAVADORES: dict[str, Callable[[Request, Con], Awaitable[Response]]] = {
    "fontes": _gravar_fontes,
    "funcoes": _gravar_funcoes,
    "segundo-plano": _gravar_segundo_plano,
    "privacidade": _gravar_privacidade,
}


# --- rotas ---------------------------------------------------------------------------------


@router.get("")
async def raiz() -> RedirectResponse:
    return _volta(GRUPOS[0])


@router.get("/{grupo}")
async def mostrar(request: Request, con: Con, grupo: str) -> Response:
    return await _pagina(request, con, _grupo_valido(grupo))


@router.post("/{grupo}")
async def gravar(request: Request, con: Con, grupo: str) -> Response:
    gravador = _GRAVADORES.get(_grupo_valido(grupo))
    if gravador is None:  # aparência grava pelas rotas /preferencias
        raise HTTPException(404)
    return await gravador(request, con)
