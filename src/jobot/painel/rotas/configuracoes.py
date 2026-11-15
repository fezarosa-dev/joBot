"""Configurações e interruptores (desenho 13.2 e 13.7; plano T54; decisão 17 e DP8).

Sete grupos em `/configuracoes/{grupo}`: fontes (uma chave por fonte, por leva), funções (as chaves
da 13.7 e o N dos destaques), segundo plano, aparência (tema e idioma pelas rotas `/preferencias`;
Meu país e moeda de exibição pelo próprio `/configuracoes/aparencia`), privacidade (onde ficam
os dados, a recomendação de disco cifrado e o aviso de versão), serviços (a chave do 2Captcha, que
fica no cofre; o interruptor e o apagar moram em `servicos.py`, T184) e sites com login (T218: só
existe com leitor registrado; o interruptor de cada site grava na hora e os horários são um campo
só). Este módulo não importa `jobot.navegador`: o estado do navegador vem de `app.state`.

Checkbox sem marca é chave desligada: o formulário de cada grupo manda o estado inteiro. Ligar ou
desligar a conversão de moeda chama `aplicar_cotacoes` e, com ela ou com as regras de ocultar
mudadas, `recalcular_encaixe`, as duas com `hoje` = dia local do `Relogio` (nunca o dia UTC).
Todo comando do sistema passa pelo executor de `app.state.rodar_comando`, o ambiente de
`app.state.ambiente` e a plataforma de `app.state.plataforma`: o teste põe os falsos.
"""

import logging
import re
import sqlite3
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from jobot.agenda.versao import aviso_ligado
from jobot.banco import buscas, cadastros, cotacoes
from jobot.banco.cadastros import PADROES, gravar_config, ler_config, ligar_fonte, meu_pais
from jobot.banco.execucoes import LinhaSaude, leitura_login_rodando, ultimas_que_rodaram
from jobot.nucleo.cambio import MOEDAS_EXIBICAO, moeda_do_pais
from jobot.nucleo.captcha import validar_chave
from jobot.nucleo.horarios import horarios_validos
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.leitores.registro import leitores
from jobot.nucleo.tratamento.locais import codigos_de_pais
from jobot.painel.ambiente import ambiente_do_painel, cofre_do_painel, no_linux, rodar_do_painel
from jobot.painel.formatos import opcoes_de_pais
from jobot.painel.rotas.fontes import estado_dos_escopos, motivo_mais_grave
from jobot.painel.rotas.servicos import NOME, contexto_captcha, no_cofre
from jobot.painel.rotas.vagas import relogio_do_painel
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar
from jobot.sistema import caso, segundo_plano_linux
from jobot.sistema.segundo_plano_linux import Recusa

router = APIRouter(prefix="/configuracoes")
_LOG = logging.getLogger(__name__)

GRUPOS = (
    "fontes",
    "funcoes",
    "segundo-plano",
    "aparencia",
    "privacidade",
    "servicos",
    "sites-com-login",
)
_COM_LOGIN = "sites-com-login"
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
    "servicos": "servicos",
    "sites-com-login": "sites_com_login",
}


def grupos_visiveis(leitores: Sequence[LeitorComLogin]) -> tuple[str, ...]:
    """Os grupos da página: "Sites com login" só existe com leitor registrado (D132.23)."""
    return GRUPOS if leitores else tuple(g for g in GRUPOS if g != _COM_LOGIN)


def _leitores(request: Request) -> Sequence[LeitorComLogin]:
    # o teste põe os leitores em `app.state` (E2); sem eles vale o registro
    registrados: Sequence[LeitorComLogin] = getattr(request.app.state, "leitores", leitores())
    return registrados


def _hoje(request: Request) -> date:
    # o dia de calendário é o do fuso local, como no resto do painel (decisão 17, DP8)
    return relogio_do_painel(request).agora().astimezone().date()


# --- o que cada grupo mostra ---------------------------------------------------------------

Contexto = Callable[[Request, Con], Awaitable[dict[str, Any]]]


async def _ctx_fontes(request: Request, con: Con) -> dict[str, Any]:
    todas = [f for f in cadastros.fontes(con) if not f.com_login]  # as com login têm aba própria
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
    pais = meu_pais(con)
    moeda = ler_config(con, "moeda_exibicao")
    return {
        "paises": opcoes_de_pais(idioma_do_pedido(request)),
        "meu_pais": pais,
        "moedas": MOEDAS_EXIBICAO,
        "moeda_exibicao": moeda if isinstance(moeda, str) and moeda in MOEDAS_EXIBICAO else "",
        "moeda_do_pais": moeda_do_pais(pais),
    }


async def _ctx_privacidade(request: Request, con: Con) -> dict[str, Any]:
    return {
        "pasta": str(request.app.state.banco.parent),
        "aviso_versao": aviso_ligado(con),
    }


def _horarios_em_texto(con: sqlite3.Connection) -> str:
    try:
        horarios = horarios_validos(ler_config(con, "login_horarios"))
    except ValueError:  # valor torto no banco: a tela mostra o padrão, como a agenda
        horarios = horarios_validos(PADROES["login_horarios"])
    return ", ".join(h.strftime("%H:%M") for h in horarios)


def _ultima_leitura(linhas: Mapping[str, LinhaSaude]) -> tuple[str, str | None] | None:
    """Estado e motivo da última execução que rodou a fonte, pela regra da página de saúde."""
    if not linhas:
        return None
    ultima = max(linha.execucao_id for linha in linhas.values())
    da_ultima = [linha for linha in linhas.values() if linha.execucao_id == ultima]
    estado = estado_dos_escopos([linha.estado for linha in da_ultima])
    return estado, motivo_mais_grave(da_ultima)


def _cartoes_de_sites(request: Request, con: sqlite3.Connection) -> list[dict[str, Any]]:
    ligadas = {f.chave: f.ligada for f in cadastros.fontes(con) if f.com_login}
    saude = ultimas_que_rodaram(con)
    lendo = leitura_login_rodando(con)
    cartoes: list[dict[str, Any]] = []
    for leitor in _leitores(request):
        ligada = ligadas.get(leitor.chave, False)
        ultima = _ultima_leitura(saude.get(leitor.chave, {}))
        cartoes.append(
            {
                "chave": leitor.chave,
                "nome": leitor.nome,
                "ligada": ligada,
                "estado": ultima[0] if ultima else None,
                "motivo": ultima[1] if ultima else None,
                "rodando": lendo and ligada,  # a leitura com login lê só os sites ligados
            }
        )
    return cartoes


async def _ctx_sites_com_login(request: Request, con: Con) -> dict[str, Any]:
    achado = getattr(request.app.state, "navegador_instalado", None)  # nunca sobe o driver (E8)
    return {
        "navegador": achado if achado in ("chrome", "chromium") else "nenhum",
        "cartoes": _cartoes_de_sites(request, con),
        "horarios_texto": _horarios_em_texto(con),
    }


_CONTEXTOS: dict[str, Contexto] = {
    "fontes": _ctx_fontes,
    "funcoes": _ctx_funcoes,
    "segundo-plano": _ctx_segundo_plano,
    "aparencia": _ctx_aparencia,
    "privacidade": _ctx_privacidade,
    "servicos": contexto_captcha,
    "sites-com-login": _ctx_sites_com_login,
}


async def _pagina(
    request: Request, con: Con, grupo: str, status: int = 200, **ctx: Any
) -> Response:
    contexto: dict[str, Any] = {
        "grupo": grupo,
        "abas": [
            (g, "configuracoes.grupo." + g.replace("-", "_"))
            for g in grupos_visiveis(_leitores(request))
        ],
        "parcial": f"configuracoes/{_PARCIAIS[grupo]}.html",
        "erro": None,
        "motivo": None,
        "salvo": False,
    }
    contexto |= await _CONTEXTOS[grupo](request, con)
    resposta = renderizar(request, "configuracoes/pagina.html", **(contexto | ctx))
    resposta.status_code = status
    return resposta


def _grupo_valido(request: Request, grupo: str) -> str:
    if grupo not in grupos_visiveis(_leitores(request)):
        raise HTTPException(404)
    return grupo


def _volta(grupo: str, salvo: bool = False) -> RedirectResponse:
    # `?salvo=1` só faz a página seguinte dizer "Salvo."; nada fica guardado no servidor
    return RedirectResponse(f"/configuracoes/{grupo}" + ("?salvo=1" if salvo else ""), 303)


# --- gravações -----------------------------------------------------------------------------


async def _gravar_fontes(request: Request, con: Con) -> Response:
    form = await request.form()
    marcadas = {str(v) for v in form.getlist("fonte")}
    conhecidas = {f.chave for f in cadastros.fontes(con) if not f.com_login}
    if not marcadas <= conhecidas:
        raise HTTPException(422)
    for chave in sorted(conhecidas):
        cadastros.ligar_fonte(con, chave, chave in marcadas)
    return _volta("fontes", salvo=True)


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
    return _volta("funcoes", salvo=True)


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
    except ValueError, OSError:  # caractere de controle no caminho, disco, permissão
        _LOG.warning("segundo plano: não consegui mudar", exc_info=True)
        return await _pagina(
            request, con, "segundo-plano", erro="configuracoes.erro.segundo_plano_arquivos"
        )
    gravar_config(con, "segundo_plano", ligar)
    return _volta("segundo-plano", salvo=True)


async def _gravar_aparencia(request: Request, con: Con) -> Response:
    form = await request.form()
    pais, moeda = form.get("meu_pais"), form.get("moeda_exibicao")
    if not isinstance(pais, str) or pais not in codigos_de_pais():
        raise HTTPException(422)
    if not isinstance(moeda, str) or (moeda and moeda not in MOEDAS_EXIBICAO):
        raise HTTPException(422)
    # recalcula antes de gravar, como nas funções: se falhar, o país segue como estava
    if pais != meu_pais(con):
        buscas.recalcular_encaixe(
            con,
            None,
            bool(ler_config(con, "regras_ocultar_ligadas")),
            hoje=_hoje(request),
            pais_padrao=pais,
        )
    gravar_config(con, "meu_pais", pais)
    gravar_config(con, "moeda_exibicao", moeda)
    return _volta("aparencia", salvo=True)


async def _gravar_privacidade(request: Request, con: Con) -> Response:
    form = await request.form()
    gravar_config(con, "aviso_versao_ligada", "aviso_versao_ligada" in form)
    return _volta("privacidade", salvo=True)


async def _gravar_servicos(request: Request, con: Con) -> Response:
    form = await request.form()
    bruto = form.get("chave")
    if not isinstance(bruto, str) or not bruto.strip():
        return _volta("servicos", salvo=True)  # campo vazio mantém a chave salva
    try:
        chave = validar_chave(bruto)
    except ValueError:
        return await _pagina(
            request, con, "servicos", 422, erro="configuracoes.servicos.erro.formato"
        )
    try:
        # shortcut: com o cofre travado espera até 2 prazos (gravar + reler a página) e a thread
        # que estourou ainda pode gravar depois; trocar quando o cofre tiver API assíncrona
        await no_cofre(cofre_do_painel(request).gravar, NOME, chave)
    except OSError as erro:  # nem o cofre nem o arquivo: só o tipo vai ao log, nunca a chave
        _LOG.warning("2captcha: não consegui gravar a chave: %s", type(erro).__name__)
        return await _pagina(request, con, "servicos", erro="configuracoes.servicos.erro.cofre")
    return _volta("servicos", salvo=True)


async def _gravar_sites_com_login(request: Request, con: Con) -> Response:
    form = await request.form()
    bruto = form.get("horarios")
    texto = bruto if isinstance(bruto, str) else ""
    try:
        horarios = horarios_validos([parte.strip() for parte in texto.split(",")])
    except ValueError as erro:  # a chave do erro vem de `horarios_validos`; nada é gravado
        return await _pagina(
            request, con, _COM_LOGIN, 422, horarios_texto=texto, erro=str(erro.args[0])
        )
    gravar_config(con, "login_horarios", [h.strftime("%H:%M") for h in horarios])
    return _volta(_COM_LOGIN, salvo=True)


_GRAVADORES: dict[str, Callable[[Request, Con], Awaitable[Response]]] = {
    "fontes": _gravar_fontes,
    "funcoes": _gravar_funcoes,
    "segundo-plano": _gravar_segundo_plano,
    "aparencia": _gravar_aparencia,
    "privacidade": _gravar_privacidade,
    "servicos": _gravar_servicos,
    "sites-com-login": _gravar_sites_com_login,
}


# --- rotas ---------------------------------------------------------------------------------


@router.get("")
async def raiz() -> RedirectResponse:
    return _volta(GRUPOS[0])


@router.get("/{grupo}")
async def mostrar(request: Request, con: Con, grupo: str) -> Response:
    salvo = request.query_params.get("salvo") == "1"
    return await _pagina(request, con, _grupo_valido(request, grupo), salvo=salvo)


@router.post("/{grupo}")
async def gravar(request: Request, con: Con, grupo: str) -> Response:
    return await _GRAVADORES[_grupo_valido(request, grupo)](request, con)


@router.post(f"/{_COM_LOGIN}/{{chave}}/interruptor")
async def interruptor_do_site(request: Request, con: Con, chave: str) -> Response:
    """Liga ou desliga um site na hora (D132.8); só chave de leitor, nunca de fonte pública."""
    _grupo_valido(request, _COM_LOGIN)
    if chave not in {leitor.chave for leitor in _leitores(request)}:
        raise HTTPException(404)
    ligar = "ligada" in await request.form()
    try:
        ligar_fonte(con, chave, ligar)
    except LookupError:
        raise HTTPException(404) from None
    cartao = next(c for c in _cartoes_de_sites(request, con) if c["chave"] == chave)
    return renderizar(
        request, "configuracoes/_cartao_site_login.html", c=cartao, foco=True, cartao_salvo=True
    )
