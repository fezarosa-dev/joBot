"""Configurações e interruptores (desenho 13.2 e 13.7; plano T54; decisão 17 e DP8).

Os grupos em `/configuracoes/{grupo}`: geral (tema, idioma e tamanho do texto pelas rotas
`/preferencias`; Meu país e moeda de exibição pelo próprio `/configuracoes/geral`; o
`/configuracoes/aparencia` de antes só redireciona no GET), fontes (uma chave por fonte, por leva),
funções (as chaves da 13.7 e o N dos destaques), perfil (dados, habilidades, experiências e cursos;
o contexto, a gravação e o "Apagar perfil" moram em `perfil.py`, T413 e T434), IA (os atalhos e a
tarefa por tarefa; o contexto e a gravação moram em `ia.py`, T415), segundo plano, privacidade (onde
ficam os dados, a recomendação de disco cifrado e o aviso de versão), serviços (a chave do 2Captcha
e as de IA, que ficam no cofre; o interruptor, os apagar e a gravação das de IA moram em
`servicos.py`, T184 e T414) e contas (T218 e T275: só existe com leitor registrado; o interruptor de
cada site grava na hora, o cartão mostra o estado da sessão e os horários são um campo só). "Fazer
login agora" e "Esquecer logins" (T219) usam o `jobot.navegador` e a trava `login` do `serve`: nunca
abrem o navegador nem apagam o perfil enquanto uma leitura com login roda.

Checkbox sem marca é chave desligada: o formulário de cada grupo manda o estado inteiro. Ligar ou
desligar a conversão de moeda chama `aplicar_cotacoes` e, com ela ou com as regras de ocultar
mudadas, `recalcular_encaixe`, as duas com `hoje` = dia local do `Relogio` (nunca o dia UTC).
Todo comando do sistema passa pelo executor de `app.state.rodar_comando`, o ambiente de
`app.state.ambiente` e a plataforma de `app.state.plataforma`: o teste põe os falsos.
"""

import asyncio
import json
import logging
import re
import sqlite3
from collections.abc import Awaitable, Callable, Mapping
from contextlib import closing, suppress
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from jobot import __version__
from jobot.agenda.versao import aviso_ligado, mais_nova_que_a_instalada, ultima_conhecida
from jobot.banco import buscas, cadastros, cotacoes
from jobot.banco.cadastros import PADROES, gravar_config, ler_config, ligar_fonte, meu_pais
from jobot.banco.captcha import NOME_NO_COFRE
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import LinhaSaude, leitura_login_rodando, ultimas_que_rodaram
from jobot.banco.ia import TarefaIA, gravar_tarefas_ia, tarefa_ia
from jobot.banco.sessoes import gravar_sessao, ler_sessoes
from jobot.navegador import limites
from jobot.navegador.conferir import conferir_sessao
from jobot.navegador.execucao import dependencias_de_producao
from jobot.navegador.instalador import baixar_chromium, remover_chromium
from jobot.navegador.janela_comum import janela_de_producao
from jobot.navegador.login_manual import fazer_login, sessao_do_login
from jobot.navegador.perfil import apagar_perfil
from jobot.nucleo.cambio import MOEDAS_EXIBICAO, moeda_do_pais
from jobot.nucleo.captcha import validar_chave
from jobot.nucleo.contas import estado_na_tela, hora_visivel, pode_conferir
from jobot.nucleo.horarios import horarios_validos
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.tratamento.locais import codigos_de_pais
from jobot.painel.ambiente import (
    COM_LOGIN,
    GRUPOS,
    abrir_ia_local_do_painel,
    abrir_instalador_do_painel,
    ambiente_do_painel,
    cofre_do_painel,
    com_segundo_plano,
    leitores_do_painel,
    ler_navegador_do_painel,
    plataforma_do_painel,
    rodar_do_painel,
)
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.formatos import conferido_texto, gigabytes, opcoes_de_pais
from jobot.painel.rotas.execucao import criar_tarefa
from jobot.painel.rotas.gmail import contexto_gmail
from jobot.painel.rotas.ia import (
    LOCAL,
    contexto_ia,
    gravar_ia,
    refazer_testes,
    servico_trocou,
    tarefas,
)
from jobot.painel.rotas.perfil import (
    PERGUNTAS,
    contexto_perfil,
    contexto_perguntas,
    gravar_perfil,
    gravar_perguntas,
)
from jobot.painel.rotas.servicos import (
    contexto_captcha,
    contexto_servicos,
    gravar_chave_ia,
    no_cofre,
)
from jobot.painel.saude_das_fontes import estado_dos_escopos, motivo_mais_grave
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar
from jobot.sistema import casca, caso, ia_local, segundo_plano
from jobot.sistema.pastas import PASTA_FERRAMENTAS
from jobot.sistema.segundo_plano_linux import Recusa

router = APIRouter(prefix="/configuracoes")
_LOG = logging.getLogger(__name__)

# um ícone Lucide por grupo (T262), na ordem de GRUPOS; o desenho é a máscara em configuracoes.css
_ICONES = dict(
    zip(
        GRUPOS,
        (
            "sliders-horizontal",
            "rss",
            "toggle-right",
            "graduation-cap",
            "sparkles",
            "timer",
            "shield",
            "plug",
            "key-round",
            "globe",
        ),
        strict=True,
    )
)
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
    "geral": "geral",
    "fontes": "fontes",
    "funcoes": "funcoes",
    "perfil": "perfil",
    "ia": "ia",
    "segundo-plano": "segundo_plano",
    "privacidade": "privacidade",
    "servicos": "servicos",
    "contas": "contas",
    "ferramentas": "ferramentas",
}


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
    suportado = com_segundo_plano(request)
    estado = None
    if suportado:
        estado = await run_in_threadpool(
            segundo_plano.status,
            rodar_do_painel(request),
            env=ambiente_do_painel(request),
            plataforma=plataforma_do_painel(request),
        )
    return {
        "suportado": suportado,
        "estado": estado,
        "container": caso.nome_do_container(ambiente_do_painel(request)),
        # D61 (A1): o interruptor segue o instalado (is-enabled, /Query); ativo não entra
        "ligado": estado is not None and estado.habilitado,
    }


async def _ctx_geral(request: Request, con: Con) -> dict[str, Any]:
    pais = meu_pais(con)
    moeda = ler_config(con, "moeda_exibicao")
    ultima = ultima_conhecida(con)
    return {
        "paises": opcoes_de_pais(idioma_do_pedido(request)),
        "meu_pais": pais,
        "moedas": MOEDAS_EXIBICAO,
        "moeda_exibicao": moeda if isinstance(moeda, str) and moeda in MOEDAS_EXIBICAO else "",
        "moeda_do_pais": moeda_do_pais(pais),
        "versao_atual": __version__,
        "versao_ultima": ultima,
        "tem_versao_nova": ultima is not None and mais_nova_que_a_instalada(ultima),
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
    sessoes = ler_sessoes(con, "site")
    agora, idioma = relogio_do_painel(request).agora(), idioma_do_pedido(request)
    navegador = _navegador(request)
    cartoes: list[dict[str, Any]] = []
    for leitor in leitores_do_painel(request):
        ligada = ligadas.get(leitor.chave, False)
        ultima = _ultima_leitura(saude.get(leitor.chave, {}))
        sessao = sessoes.get(leitor.chave)
        na_tela = estado_na_tela(ligada, sessao)
        cartoes.append(
            {
                "chave": leitor.chave,
                "nome": leitor.nome,
                "ligada": ligada,
                "leitura": ultima[0] if ultima else None,
                "leitura_motivo": ultima[1] if ultima else None,
                "na_tela": na_tela,  # o selo (E15)
                "hora": (
                    conferido_texto(sessao.conferido_em, agora, idioma)
                    if sessao is not None and hora_visivel(na_tela, sessao)
                    else None
                ),
                "motivo": sessao.motivo
                if sessao is not None and na_tela == "nao_conferiu"
                else None,
                "rodando": lendo and ligada,  # a leitura com login lê só os sites ligados
                "login": _estados_de_login(request).get(leitor.chave),
                "minutos": _minutos_de_login(),
                "navegador": navegador,  # sem navegador, o login sai desabilitado (desenho 5.7)
                # intervalo do "Conferir agora" (5.4), lido na hora (monkeypatch em limites)
                "pode_conferir": pode_conferir(sessao, agora, limites.INTERVALO_CONFERIR_S),
                "conferindo": _conferencias(request).get(leitor.chave) == "rodando",
            }
        )
    return cartoes


def _navegador(request: Request) -> str:
    achado = getattr(request.app.state, "navegador_instalado", None)  # nunca sobe o driver (E8)
    return achado if achado in ("chrome", "chromium") else "nenhum"


async def contexto_sites_com_login(request: Request, con: Con) -> dict[str, Any]:
    return {
        "navegador": _navegador(request),
        "cartoes": _cartoes_de_sites(request, con),
        "horarios_texto": _horarios_em_texto(con),
    }


async def _ctx_contas(request: Request, con: Con) -> dict[str, Any]:
    # a linha do 2Captcha no fim da aba (D139.26): só a máscara entra no contexto, nunca a chave;
    # o cartão do Gmail (T278) nunca recebe a senha
    return (
        await contexto_sites_com_login(request, con)
        | await contexto_captcha(request, con)
        | await contexto_gmail(request, con)
    )


def _ferramentas(request: Request) -> dict[str, str]:
    """O estado do que roda ou do último resultado de cada ferramenta (D137.4)."""
    estado = request.app.state
    if getattr(estado, "ferramentas", None) is None:  # sem o lifespan do `serve`
        estado.ferramentas = {}
    ferramentas: dict[str, str] = estado.ferramentas
    return ferramentas


_RODANDO = ("baixando", "removendo")
_TERMINAIS = ("pronto", "removido", "continua", "falhou_baixar", "falhou_remover")


def contexto_ferramenta_navegador(request: Request) -> dict[str, Any]:
    """O navegador, o resultado e o rótulo do estado; resultado terminal aparece uma vez só
    (D137.4): a leitura que o devolve também o apaga."""
    achado = getattr(request.app.state, "navegador_instalado", None)
    navegador = achado if achado in ("chrome", "chromium") else None
    ferramentas = _ferramentas(request)
    resultado = ferramentas.get("navegador")
    if resultado in _TERMINAIS:
        ferramentas.pop("navegador")
    if resultado in _RODANDO:
        estado = resultado
    elif resultado in ("falhou_baixar", "falhou_remover"):
        estado = "falhou"
    elif navegador == "chrome":
        estado = "chrome"
    else:
        estado = "instalado" if navegador == "chromium" else "nao_instalado"
    # a atualização da casca não conseguiu trazer o Chromium novo (D174.13): Baixar de novo
    desatualizado = navegador == "chromium" and casca.navegador_desatualizado(_dados(request))
    return {
        "navegador": navegador,
        "resultado": resultado,
        "estado": estado,
        "desatualizado": desatualizado,
    }


def _dados(request: Request) -> Path:
    pasta: Path = request.app.state.banco.parent
    return pasta


async def _contexto_ferramentas(request: Request, con: Con) -> dict[str, Any]:
    # o cartão do navegador só com leitor com login, como antes (desenho 10.2 da fase 4)
    navegador = contexto_ferramenta_navegador(request) if leitores_do_painel(request) else {}
    return {"com_navegador": bool(navegador)} | navegador | contexto_ferramenta_ia_local(request)


_CONTEXTOS: dict[str, Contexto] = {
    "geral": _ctx_geral,
    "fontes": _ctx_fontes,
    "funcoes": _ctx_funcoes,
    "perfil": contexto_perfil,
    "ia": contexto_ia,
    "segundo-plano": _ctx_segundo_plano,
    "privacidade": _ctx_privacidade,
    "servicos": contexto_servicos,
    COM_LOGIN: _ctx_contas,
    "ferramentas": _contexto_ferramentas,
}


async def _pagina(
    request: Request, con: Con, grupo: str, status: int = 200, **ctx: Any
) -> Response:
    contexto: dict[str, Any] = {
        "grupo": grupo,
        "abas": [(g, "configuracoes.grupo." + g.replace("-", "_"), _ICONES[g]) for g in GRUPOS],
        "parcial": f"configuracoes/{_PARCIAIS[grupo]}.html",
        "erro": None,
        "motivo": None,
        "salvo": False,
    }
    contexto |= await _CONTEXTOS[grupo](request, con)
    resposta = renderizar(request, "configuracoes/pagina.html", **(contexto | ctx))
    resposta.status_code = status
    if grupo == "perfil":  # nome, contato e resumo: o navegador não guarda cópia em disco (D230.7)
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


def _grupo_valido(request: Request, grupo: str) -> str:
    if grupo not in GRUPOS:
        raise HTTPException(404)
    return grupo


def _exige_leitor(request: Request) -> None:
    """A aba "Contas" aparece sem leitor (o Gmail mora lá, E13), mas mostrar não libera ação:
    login, interruptor, conferir, horários e "Esquecer logins" pedem um leitor registrado."""
    if not leitores_do_painel(request):
        raise HTTPException(404)


def _volta(grupo: str, salvo: bool = False, erro: str | None = None) -> RedirectResponse:
    # `?salvo=1` só faz a página seguinte dizer "Salvo."; nada fica guardado no servidor
    sufixo = "?salvo=1" if salvo else f"?erro={erro}" if erro else ""
    return RedirectResponse(f"/configuracoes/{grupo}{sufixo}", 303)


# `?erro=` de "Esquecer logins" sem JavaScript (T310): lista fechada, nada da URL vai à página
_ERROS_DE_ESQUECER = {
    "em_andamento": "configuracoes.sites_com_login.em_andamento",
    "esquecer": "configuracoes.sites_com_login.esquecer.erro",
}


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
    suportado = com_segundo_plano(request)
    ligar = "segundo_plano" in form and suportado  # sem suporte o segundo plano é desativado
    rodar, env = rodar_do_painel(request), ambiente_do_painel(request)
    plataforma = plataforma_do_painel(request)
    try:
        if ligar:
            await run_in_threadpool(segundo_plano.ligar, rodar, env=env, plataforma=plataforma)
        elif suportado:
            await run_in_threadpool(segundo_plano.desligar, rodar, env=env, plataforma=plataforma)
    except Recusa as recusa:
        return await _pagina(request, con, "segundo-plano", motivo=recusa.motivo)
    except ValueError, OSError:  # caractere de controle no caminho, disco, permissão
        _LOG.warning("segundo plano: não consegui mudar", exc_info=True)
        return await _pagina(
            request, con, "segundo-plano", erro="configuracoes.erro.segundo_plano_arquivos"
        )
    gravar_config(con, "segundo_plano", ligar)
    return _volta("segundo-plano", salvo=True)


async def _gravar_geral(request: Request, con: Con) -> Response:
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
    return _volta("geral", salvo=True)


async def _gravar_privacidade(request: Request, con: Con) -> Response:
    form = await request.form()
    gravar_config(con, "aviso_versao_ligada", "aviso_versao_ligada" in form)
    return _volta("privacidade", salvo=True)


async def _gravar_servicos(request: Request, con: Con) -> Response:
    form = await request.form()
    if "servico" in form:  # o cartão de uma chave de IA (T414)
        antes = ler_config(con, "ia_compativel")
        falhou = await gravar_chave_ia(request, con, form)
        if falhou is None:
            # chave digitada ou endereço novo: o teste ao ligar dos pares do serviço vale de novo
            servico = str(form.get("servico"))
            if str(form.get("chave") or "").strip() or ler_config(con, "ia_compativel") != antes:
                await servico_trocou(request, con, servico)
            return _volta("servicos", salvo=True)
        status, ctx = falhou
        return await _pagina(request, con, "servicos", status, **ctx)
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
        await no_cofre(cofre_do_painel(request).gravar, NOME_NO_COFRE, chave)
    except OSError as erro:  # nem o cofre nem o arquivo: só o tipo vai ao log, nunca a chave
        _LOG.warning("2captcha: não consegui gravar a chave: %s", type(erro).__name__)
        return await _pagina(request, con, "servicos", erro="configuracoes.servicos.erro.cofre")
    return _volta("servicos", salvo=True)


async def _gravar_perfil(request: Request, con: Con) -> Response:
    feito = await gravar_perfil(request, con, await request.form())
    if isinstance(feito, str):
        return RedirectResponse(feito, 303)
    status, ctx = feito
    return await _pagina(request, con, "perfil", status, **ctx)


async def _gravar_ia(request: Request, con: Con) -> Response:
    feito = await gravar_ia(request, con, await request.form())
    if isinstance(feito, str):
        return RedirectResponse(feito, 303)
    status, ctx = feito
    return await _pagina(request, con, "ia", status, **ctx)


async def _gravar_sites_com_login(request: Request, con: Con) -> Response:
    form = await request.form()
    bruto = form.get("horarios")
    texto = bruto if isinstance(bruto, str) else ""
    try:
        horarios = horarios_validos([parte.strip() for parte in texto.split(",")])
    except ValueError as erro:  # a chave do erro vem de `horarios_validos`; nada é gravado
        return await _pagina(
            request, con, COM_LOGIN, 422, horarios_texto=texto, erro=str(erro.args[0])
        )
    gravar_config(con, "login_horarios", [h.strftime("%H:%M") for h in horarios])
    return _volta(COM_LOGIN, salvo=True)


_GRAVADORES: dict[str, Callable[[Request, Con], Awaitable[Response]]] = {
    "geral": _gravar_geral,
    "fontes": _gravar_fontes,
    "funcoes": _gravar_funcoes,
    "perfil": _gravar_perfil,
    "ia": _gravar_ia,
    "segundo-plano": _gravar_segundo_plano,
    "privacidade": _gravar_privacidade,
    "servicos": _gravar_servicos,
    COM_LOGIN: _gravar_sites_com_login,
}


# --- rotas ---------------------------------------------------------------------------------


@router.get("")
async def raiz() -> RedirectResponse:
    return _volta(GRUPOS[0])


@router.get("/aparencia")
async def aparencia_de_antes() -> RedirectResponse:
    """O endereço velho do grupo que virou Geral (só o GET; o POST não tem cópia, D139.25)."""
    return _volta("geral")


@router.get("/sites-com-login")
async def sites_com_login_de_antes() -> RedirectResponse:
    """O endereço velho da aba que virou Contas (T275; só o GET, as ações não têm cópia)."""
    return _volta(COM_LOGIN)


# O questionário do perfil (T437): uma página da aba Perfil, com o contexto e a gravação de
# `perfil.py`. Fica antes de `/{grupo}` só por clareza: tem dois segmentos.
_QUESTIONARIO = "configuracoes/perguntas.html"


@router.get(PERGUNTAS.removeprefix("/configuracoes"))
async def questionario(request: Request, con: Con) -> Response:
    ctx = await contexto_perguntas(request, con)
    salvo = request.query_params.get("salvo") == "1"
    return await _pagina(request, con, "perfil", parcial=_QUESTIONARIO, salvo=salvo, **ctx)


@router.post(PERGUNTAS.removeprefix("/configuracoes"))
async def gravar_questionario(request: Request, con: Con) -> Response:
    feito = await gravar_perguntas(request, con, await request.form())
    if isinstance(feito, str):
        return RedirectResponse(feito, 303)
    status, extra = feito
    ctx = await contexto_perguntas(request, con) | extra
    return await _pagina(request, con, "perfil", status, parcial=_QUESTIONARIO, **ctx)


@router.get("/{grupo}")
async def mostrar(request: Request, con: Con, grupo: str) -> Response:
    salvo = request.query_params.get("salvo") == "1"
    ctx: dict[str, Any] = {"salvo": salvo}
    if grupo == COM_LOGIN and (
        chave := _ERROS_DE_ESQUECER.get(request.query_params.get("erro", ""))
    ):
        ctx["erro"] = chave
    return await _pagina(request, con, _grupo_valido(request, grupo), **ctx)


@router.post("/{grupo}")
async def gravar(request: Request, con: Con, grupo: str) -> Response:
    gravador = _GRAVADORES.get(_grupo_valido(request, grupo))
    if grupo == COM_LOGIN:
        _exige_leitor(request)  # os horários são da leitura dos sites
    if gravador is None:  # "Ferramentas" não tem formulário: cada ação tem a sua rota
        raise HTTPException(405)
    return await gravador(request, con)


@router.post(f"/{COM_LOGIN}/{{chave}}/interruptor")
async def interruptor_do_site(request: Request, con: Con, chave: str) -> Response:
    """Liga ou desliga um site na hora (D132.8); só chave de leitor, nunca de fonte pública."""
    _exige_leitor(request)
    if chave not in {leitor.chave for leitor in leitores_do_painel(request)}:
        raise HTTPException(404)
    ligar = "ligada" in await request.form()
    try:
        ligar_fonte(con, chave, ligar)
    except LookupError:
        raise HTTPException(404) from None
    resposta = _cartao_do_site(request, con, chave, foco=True, cartao_salvo=True)
    resposta.headers["HX-Trigger"] = _MUDOU
    return resposta


# o evento que a faixa do topo e outras partes da tela ouvem quando o estado de uma conta muda (E17)
_MUDOU = "contas-mudou"


def _dados_do_cartao(request: Request, con: sqlite3.Connection, chave: str) -> dict[str, Any]:
    return next(c for c in _cartoes_de_sites(request, con) if c["chave"] == chave)


def _cartao_do_site(request: Request, con: sqlite3.Connection, chave: str, **ctx: Any) -> Response:
    cartao = _dados_do_cartao(request, con, chave)
    return renderizar(request, "configuracoes/_cartao_site_login.html", c=cartao, **ctx)


# --- fazer login agora e esquecer logins (T219; D132.18, D132.21, D132.22, D132.52) ----------


def _minutos_de_login() -> int:
    return int(limites.PRAZO_LOGIN_MANUAL_S // 60)  # lido na hora: o monkeypatch vai em limites


def _leitor(request: Request, chave: str) -> LeitorComLogin:
    """Só chave de leitor registrado; sem leitor, 404."""
    _exige_leitor(request)
    for leitor in leitores_do_painel(request):
        if leitor.chave == chave:
            return leitor
    raise HTTPException(404)


def _trava(request: Request, nome: str) -> asyncio.Lock:
    # as travas do `serve` (a de login é a mesma da leitura); app sem o lifespan cria as suas
    estado = request.app.state
    if not hasattr(estado, "travas"):
        estado.travas = {}
    trava: asyncio.Lock = estado.travas.setdefault(nome, asyncio.Lock())
    return trava


def _trava_de_login(request: Request) -> asyncio.Lock:
    return _trava(request, "login")


def _estados_de_login(request: Request) -> dict[str, str]:
    estado = request.app.state
    if not hasattr(estado, "login_manual"):
        estado.login_manual = {}
    estados: dict[str, str] = estado.login_manual
    return estados


def _fragmento_de_login(request: Request, chave: str, estado: str) -> Response:
    return renderizar(
        request,
        "configuracoes/_login_site.html",
        chave=chave,
        estado=estado,
        minutos=_minutos_de_login(),
    )


@router.post(f"/{COM_LOGIN}/{{chave}}/login")
async def fazer_login_agora(request: Request, chave: str) -> Response:
    """Abre a janela comum na página de login do site e espera a pessoa entrar (D136.1)."""
    leitor = _leitor(request, chave)
    trava = _trava_de_login(request)
    estados = _estados_de_login(request)
    if trava.locked():
        # o mesmo site já espera a pessoa: devolve a espera, que mantém o polling na tela
        estado = "aguardando" if estados.get(chave) == "aguardando" else "em_andamento"
        return _fragmento_de_login(request, chave, estado)
    # tudo que pode falhar vem antes do acquire: depois dele, só o que não solta exceção
    banco: Path = request.app.state.banco
    env = ambiente_do_painel(request)
    relogio = relogio_do_painel(request)
    await trava.acquire()  # livre: não suspende, então a checagem acima vale (como no laço)
    estados[chave] = "aguardando"

    async def login() -> None:
        try:
            async with dependencias_de_producao(banco.parent, env) as deps:
                resultado = await fazer_login(leitor, deps, janela_de_producao())
            # conexão própria: a do pedido já fechou (E20: só resultado grava, exceção não)
            with closing(abrir(banco)) as con:
                estado, motivo = sessao_do_login(resultado)
                gravar_sessao(con, "site", chave, estado, motivo, relogio.agora())
            estados[chave] = resultado
        except Exception:
            estados[chave] = "erro"
            raise  # o `rodar` registra no log e solta a trava

    criar_tarefa(request, "login manual", trava, login)
    return _fragmento_de_login(request, chave, "aguardando")


@router.get(f"/{COM_LOGIN}/{{chave}}/login")
async def estado_do_login(request: Request, con: Con, chave: str) -> Response:
    """O HTMX pergunta a cada 5 s; enquanto espera, 204 (nada troca na tela). Depois, o cartão
    inteiro, com o selo novo e o resultado do login (E17); sem estado (os logins foram
    esquecidos no meio), o cartão como está, para o `outerHTML` nunca apagá-lo."""
    _leitor(request, chave)
    if _estados_de_login(request).get(chave) == "aguardando":
        return Response(status_code=204)
    # o `outerHTML` troca a região viva do cartão: o resultado é anunciado em `#status-sites`
    # e o foco vai ao cartão novo
    resposta = _cartao_do_site(request, con, chave, foco_cartao=True, anunciar_login=True)
    resposta.headers["HX-Trigger"] = _MUDOU
    return resposta


# --- conferir agora (T277; desenho 5.4, E17, D166) --------------------------------------------


def _conferencias(request: Request) -> dict[str, str]:
    """ "rodando" enquanto a tarefa roda; "erro" até o GET final anunciá-lo. O resultado fica no
    banco."""
    estado = request.app.state
    if not hasattr(estado, "conferencias"):
        estado.conferencias = {}
    conferencias: dict[str, str] = estado.conferencias
    return conferencias


@router.post(f"/{COM_LOGIN}/{{chave}}/conferir")
async def conferir_agora(request: Request, con: Con, chave: str) -> Response:
    """Confere o login do site na hora, nesta ordem: chave (404), site desligado, intervalo e
    trava. Recusado, o cartão como está; aceito, o cartão em espera, que pergunta a cada 2 s."""
    leitor = _leitor(request, chave)
    cartao = _dados_do_cartao(request, con, chave)

    def responder(**ctx: Any) -> Response:  # o foco segue para o cartão novo: o botão sumiu
        return renderizar(
            request, "configuracoes/_cartao_site_login.html", c=cartao, foco_cartao=True, **ctx
        )

    if not cartao["ligada"] or not cartao["pode_conferir"]:
        return responder()
    conferencias = _conferencias(request)
    if conferencias.get(chave) == "rodando":
        # segundo clique no mesmo site: o cartão já vem em espera (conferindo)
        return responder()
    trava = _trava(request, "login")
    if trava.locked():
        return responder(ocupado=True)
    # tudo que pode falhar vem antes do acquire: depois dele, só o que não solta exceção
    banco: Path = request.app.state.banco
    env = ambiente_do_painel(request)
    relogio = relogio_do_painel(request)
    resposta = responder(espera=True)
    await trava.acquire()  # livre: não suspende, então a checagem acima vale (como no laço)
    conferencias[chave] = "rodando"

    async def conferir() -> None:
        terminou = False
        try:
            async with dependencias_de_producao(banco.parent, env) as deps:
                conferencia = await conferir_sessao(leitor, deps, relogio)
            if conferencia is not None:  # None: a pessoa fechou a janela (E5), nada se sabe
                # conexão própria: a do pedido já fechou. Sem aviso no computador: só a leitura
                # agendada avisa (D139.22)
                with closing(abrir(banco)) as con_da_tarefa:
                    gravar_sessao(
                        con_da_tarefa,
                        "site",
                        chave,
                        conferencia.estado,
                        conferencia.motivo,
                        relogio.agora(),
                    )
            terminou = True
        finally:
            # exceção sobe ao `rodar`, que registra e solta a trava; o erro fica até o GET final
            # anunciá-lo uma vez (molde do `login_manual`)
            if terminou:
                conferencias.pop(chave, None)
            else:
                conferencias[chave] = "erro"

    criar_tarefa(request, "conferir conta", trava, conferir)
    return resposta


@router.get(f"/{COM_LOGIN}/{{chave}}/conferir")
async def estado_da_conferencia(request: Request, con: Con, chave: str) -> Response:
    """O HTMX pergunta a cada 2 s; enquanto a conferência roda, 204. Depois, o cartão inteiro com o
    estado novo (E17), o resultado anunciado em `#status-sites` e o foco no cartão, se livre."""
    _leitor(request, chave)
    conferencias = _conferencias(request)
    if conferencias.get(chave) == "rodando":
        return Response(status_code=204)
    erro = conferencias.pop(chave, None) == "erro"
    resposta = _cartao_do_site(
        request, con, chave, foco_cartao=True, anunciar_conferencia=True, erro_conferencia=erro
    )
    resposta.headers["HX-Trigger"] = _MUDOU
    return resposta


@router.get(f"/{COM_LOGIN}/esquecer/confirmar")
async def esquecer_logins_pergunta(request: Request) -> Response:
    """Sem JavaScript: a pergunta do alerta numa página; o GET não apaga nada (T307)."""
    _exige_leitor(request)
    return renderizar(
        request,
        "confirmar.html",
        titulo=("configuracoes.sites_com_login.esquecer.pergunta", {}),
        texto="configuracoes.sites_com_login.esquecer.explicacao",
        rotulo="comum.esquecer",
        acao=f"/configuracoes/{COM_LOGIN}/esquecer/confirmar",
        voltar=f"/configuracoes/{COM_LOGIN}",
    )


@router.post(f"/{COM_LOGIN}/esquecer/confirmar")
async def esquecer_logins_confirmado(request: Request, con: Con) -> Response:
    """Confirma o alerta: apaga a pasta do perfil (D132.21), nunca com leitura ou login rodando
    (trava `login`, D132.18)."""
    _exige_leitor(request)
    trava = _trava_de_login(request)
    sem_js = request.headers.get("hx-request") != "true"  # T310, D165: volta à página do grupo
    if trava.locked():
        if sem_js:
            return _volta(COM_LOGIN, erro="em_andamento")
        return renderizar(request, "configuracoes/_esquecer.html", fase="em_andamento")
    await trava.acquire()  # livre: não suspende; segura enquanto apaga
    try:
        await run_in_threadpool(apagar_perfil, request.app.state.banco.parent)
        # ainda com a trava: cada site volta a "Nunca entrou"; o Gmail não é sessão do navegador
        # (E12). Só leitor com fonte semeada: a linha da sessão pede a fonte (chave estrangeira)
        agora = relogio_do_painel(request).agora()
        com_fonte = {f.chave for f in cadastros.fontes(con) if f.com_login}
        for leitor in leitores_do_painel(request):
            if leitor.chave in com_fonte:
                gravar_sessao(con, "site", leitor.chave, "precisa_entrar", "esquecido", agora)
    except OSError as erro:  # symlink recusado ou disco: o caminho fica só no log
        _LOG.warning("esquecer logins: não consegui apagar o perfil: %s", type(erro).__name__)
        if sem_js:
            return _volta(COM_LOGIN, erro="esquecer")
        return renderizar(request, "configuracoes/_esquecer.html", fase="erro")
    finally:
        trava.release()
    _estados_de_login(request).clear()  # o "Login feito" de antes não vale mais
    if sem_js:
        return _volta(COM_LOGIN, salvo=True)
    resposta = renderizar(
        request,
        "configuracoes/_esquecer.html",
        fase="apagados",
        cartoes=_cartoes_de_sites(request, con),  # os cartões vão juntos, fora do alvo (OOB)
    )
    resposta.headers["HX-Trigger"] = _MUDOU
    return resposta


# --- ferramentas: o navegador dos sites com login (T240; D137.1 a D137.8, D137.12 a D137.14) ---

_NAVEGADOR = "/ferramentas/navegador"


def _fragmento_do_navegador(request: Request, **ctx: Any) -> Response:
    return renderizar(
        request,
        "configuracoes/_ferramenta_navegador.html",
        **(contexto_ferramenta_navegador(request) | ctx),
    )


_PASSO_SITES = "/primeira-execucao/sites"  # o passo do assistente que mostra este fragmento


@router.get(_NAVEGADOR)
async def estado_do_navegador(request: Request, con: Con) -> Response:
    """O HTMX pergunta a cada 5 s; enquanto baixa ou remove, 204 (nada troca na tela)."""
    _exige_leitor(request)  # Ferramentas existe sem leitor (D185.20); o navegador, não
    if _ferramentas(request).get("navegador") in _RODANDO:
        return Response(status_code=204)
    if urlsplit(request.headers.get("HX-Current-URL", "")).path == _PASSO_SITES:
        # no assistente os cartões e a frase dependem do navegador (D166): trocam junto, em OOB
        return _fragmento_do_navegador(request, cartoes_oob=_cartoes_de_sites(request, con))
    return _fragmento_do_navegador(request)


@router.post(_NAVEGADOR + "/baixar")
async def baixar_navegador(request: Request) -> Response:
    """Baixa o Chromium do Playwright em segundo plano; um download por vez (D137.4)."""
    _exige_leitor(request)  # Ferramentas existe sem leitor (D185.20); o navegador, não
    trava = _trava(request, "navegador")
    instalado = getattr(request.app.state, "navegador_instalado", None)
    desatualizado = instalado == "chromium" and casca.navegador_desatualizado(_dados(request))
    if (instalado and not desatualizado) or trava.locked():
        return _fragmento_do_navegador(request)
    # tudo que pode falhar vem antes do acquire: depois dele, só o que não solta exceção
    abrir = abrir_instalador_do_painel(request)
    ler = ler_navegador_do_painel(request)
    ferramentas = _ferramentas(request)
    await trava.acquire()  # livre: não suspende, então a checagem acima vale
    ferramentas["navegador"] = "baixando"

    async def baixar() -> None:
        resultado = "falhou_baixar"  # erro inesperado sai assim; o `rodar` registra e solta
        try:
            if await baixar_chromium(abrir) == "pronto":
                request.app.state.navegador_instalado = await ler()
                if request.app.state.navegador_instalado:
                    resultado = "pronto"
                    await run_in_threadpool(casca.tirar_marca_do_navegador, _dados(request))
                else:
                    _LOG.warning("o instalador terminou, mas o navegador não apareceu no disco")
        finally:
            ferramentas["navegador"] = resultado

    criar_tarefa(request, "baixar navegador", trava, baixar)
    return _fragmento_do_navegador(request)


@router.post(_NAVEGADOR + "/remover")
async def remover_navegador(request: Request) -> Response:
    """Remove o Chromium do Playwright, nunca com o navegador aberto num site (D137.13)."""
    _exige_leitor(request)  # Ferramentas existe sem leitor (D185.20); o navegador, não
    trava = _trava(request, "navegador")
    login = _trava_de_login(request)
    if getattr(request.app.state, "navegador_instalado", None) != "chromium" or trava.locked():
        return _fragmento_do_navegador(request)
    if login.locked():  # leitura ou login com o navegador aberto: só nesta resposta
        return _fragmento_do_navegador(request, resultado="em_uso")
    abrir = abrir_instalador_do_painel(request)
    ler = ler_navegador_do_painel(request)
    ferramentas = _ferramentas(request)
    await trava.acquire()  # as duas livres: nenhum acquire suspende
    await login.acquire()
    ferramentas["navegador"] = "removendo"

    async def remover() -> None:
        resultado = "falhou_remover"
        try:
            if await remover_chromium(abrir) == "pronto":
                request.app.state.navegador_instalado = await ler()
                # outra instalação do Playwright pode usar a mesma pasta: o uninstall a mantém
                ficou = request.app.state.navegador_instalado == "chromium"
                resultado = "continua" if ficou else "removido"
        finally:
            ferramentas["navegador"] = resultado
            login.release()

    criar_tarefa(request, "remover navegador", trava, remover)
    return _fragmento_do_navegador(request)


# --- ferramentas: o modelo local (T417; desenho 10.2 da fase 4; D185.20) ---

_IA_LOCAL = "/ferramentas/ia-local"
_CARTAO_IA_LOCAL = "configuracoes/_ferramenta_ia_local.html"
_RODANDO_IA = ("baixando", "removendo")
_TERMINAIS_IA = ("pronto", "removido", "falhou_baixar", "falhou_remover")
# os motivos da linha `fim` do `jobot ferramentas`: os de `baixar.Motivo` mais os do contrato
MOTIVOS_IA = (
    "sem_rede",
    "espaco",
    "arquivo",
    "cancelado",
    "ocupado",
    "programa_ausente",
    "modelo_ausente",
)


def _andamento_ia(request: Request) -> dict[str, Any]:
    """O comando do modelo local que roda (`estado`, `feito`, `total`) ou o último resultado
    (`estado` terminal e `motivo`)."""
    estado = request.app.state
    if getattr(estado, "ia_local", None) is None:
        estado.ia_local = {}
    andamento: dict[str, Any] = estado.ia_local
    return andamento


def _no_disco(request: Request) -> tuple[dict[str, Any], dict[str, Any], str | None, bool]:
    """O manifesto, a anotação, a chave do modelo baixado (`laya`, `2b`, `4b`) e se há o que
    atualizar: o manifesto mudou desde o download (programa ou modelo, D195) ou um dos arquivos
    anotados sumiu. Anotação torta (valor que não é texto) é "não baixado", como na aba IA
    (D202.13)."""
    manifesto = ia_local.manifesto_local()
    dados = _dados(request)
    anotacao = ia_local.ler_anotacao(dados)
    chave, alvo, arquivo = anotacao.get("modelo"), anotacao.get("alvo"), anotacao.get("arquivo")
    if not (isinstance(chave, str) and isinstance(alvo, str) and isinstance(arquivo, str)):
        return manifesto, anotacao, None, False
    if chave not in manifesto["modelos"]:
        return manifesto, anotacao, None, False
    servidor = manifesto["llama_server"]
    item = servidor["alvos"].get(alvo) or {}
    ferramentas = dados / PASTA_FERRAMENTAS
    programa = anotacao.get("programa")
    mudou = (
        anotacao.get("build") != servidor["build"]
        or anotacao.get("servidor_sha256") != item.get("sha256")
        or anotacao.get("modelo_sha256") != manifesto["modelos"][chave]["sha256"]
        or not isinstance(programa, str)
        or not (ferramentas / programa).is_file()
        or not (ferramentas / "modelos" / arquivo).is_file()
    )
    return manifesto, anotacao, chave, mudou


def contexto_ferramenta_ia_local(request: Request, *, foco: bool = False) -> dict[str, Any]:
    """O cartão do modelo local; resultado terminal aparece uma vez só, como no navegador.
    `foco`: a resposta do botão, que some na troca; o foco vai ao estado (o aviso do fim o puxa
    sozinho, o polling não)."""
    idioma = idioma_do_pedido(request)
    manifesto, anotacao, chave, mudou = _no_disco(request)
    modelos = manifesto["modelos"]
    andamento = _andamento_ia(request)
    resultado, motivo = andamento.get("estado"), andamento.get("motivo")
    if resultado in _TERMINAIS_IA:
        andamento.clear()
    rodando = resultado in _RODANDO_IA
    feito, total = (andamento.get("feito", 0), andamento.get("total", 0)) if rodando else (0, 0)
    modelo = programa = None
    outros = []
    if chave is not None:
        m = modelos[chave]
        modelo = m | {"tamanho": gigabytes(m["tamanho"], idioma)}
        # um "Trocar para" por modelo do manifesto, na ordem dele (o padrão primeiro, D219.20)
        outros = [
            {"chave": c, "nome": o["nome"], "tamanho": gigabytes(o["tamanho"], idioma)}
            for c, o in modelos.items()
            if c != chave
        ]
        servidor = manifesto["llama_server"]
        if alvo := servidor["alvos"].get(anotacao.get("alvo")):
            programa = alvo | {"build": anotacao.get("build")}
    padrao = modelos[manifesto["padrao"]]
    return {
        "ia_estado": resultado if rodando else "baixado" if chave else "nao_baixado",
        "ia_foco": foco,
        "ia_resultado": resultado if resultado in _TERMINAIS_IA else None,
        "ia_motivo": motivo if motivo in MOTIVOS_IA else "outro",
        "ia_feito": feito,
        "ia_total": total,
        "ia_pct": feito * 100 // total if total else 0,
        "ia_modelo": modelo,
        "ia_programa": programa,
        "ia_outros": outros,
        "ia_desatualizado": mudou and not rodando,
        "ia_padrao": {"nome": padrao["nome"], "tamanho": gigabytes(padrao["tamanho"], idioma)},
    }


def _cartao_ia_local(request: Request, *, foco: bool = False) -> Response:
    if request.headers.get("hx-request") != "true":  # sem JavaScript: a página inteira de novo
        return _volta("ferramentas")
    contexto = contexto_ferramenta_ia_local(request, foco=foco)
    return renderizar(request, _CARTAO_IA_LOCAL, **contexto)


@router.get(_IA_LOCAL)
async def estado_do_modelo_local(request: Request) -> Response:
    """O HTMX pergunta a cada 5 s enquanto o comando roda: a barra anda pelos bytes."""
    return _cartao_ia_local(request)


def argumentos_ia_local(
    chave: str | None, mudou: bool, alvo: str | None = None
) -> dict[str, list[str] | None]:
    """O `jobot ferramentas ...` de cada botão; `None`: o botão não vale agora. `alvo`: o modelo
    do "Trocar para", já conferido no manifesto."""
    return {
        "baixar": ["baixar", "ia-local"] if chave is None else None,
        "trocar": ["baixar", "ia-local", "--modelo", alvo]
        if chave and alvo and alvo != chave
        else None,
        "atualizar": ["atualizar", "ia-local"] if chave and mudou else None,
        "remover": ["remover", "ia-local"] if chave else None,
    }


@router.post(_IA_LOCAL + "/{acao}")
async def comando_do_modelo_local(request: Request, con: Con, acao: str) -> Response:
    """Baixar (o padrão do manifesto), Trocar (para o modelo do campo `modelo`), Atualizar e
    Remover rodam o `jobot ferramentas ... ia-local` em segundo plano, um por vez (D195.12)."""
    manifesto, _, chave, mudou = _no_disco(request)
    alvo = None
    if acao == "trocar":
        pedido_modelo = (await request.form()).get("modelo")
        # só um modelo do manifesto: o valor vai para a linha de comando
        if isinstance(pedido_modelo, str) and pedido_modelo in manifesto["modelos"]:
            alvo = pedido_modelo
    argumentos = argumentos_ia_local(chave, mudou, alvo)
    if acao not in argumentos:
        raise HTTPException(404)
    trava = _trava(request, "ia_local")
    pedido = argumentos[acao]
    if pedido is None or trava.locked():  # nada a fazer, ou outro comando já roda
        return _cartao_ia_local(request, foco=True)
    abrir_ia = abrir_ia_local_do_painel(request)
    dados = _dados(request)
    if acao == "remover":
        # as tarefas no local desligam já, sem esperar o comando (que também desliga, D195)
        _desligar_local(con)
    andamento = _andamento_ia(request)
    novo = manifesto["modelos"][alvo]["nome"] if acao == "trocar" and alvo else None
    banco: Path = request.app.state.banco
    await trava.acquire()  # livre: não suspende; tudo que pode falhar vem antes
    andamento.clear()
    andamento["estado"] = "removendo" if acao == "remover" else "baixando"

    async def rodar_comando() -> None:
        fim: object = None
        motivo: object = None
        try:
            comando = await abrir_ia(pedido, dados)
            try:
                linhas = comando.stdout
                if linhas is not None:
                    async for linha in linhas:
                        lida = _linha_json(linha)
                        feito, total = lida.get("feito"), lida.get("total")
                        if isinstance(feito, int) and isinstance(total, int):
                            andamento["feito"], andamento["total"] = feito, total
                        fim, motivo = lida.get("fim", fim), lida.get("motivo", motivo)
                if await comando.wait() != 0:
                    fim = "falhou"
            except BaseException:  # cancelado (`/sair`, fim do servidor) ou erro na leitura
                with suppress(ProcessLookupError):
                    comando.kill()  # o `.parcial` fica para a retomada
                raise
            if fim == "pronto" and novo is not None:
                trocadas = await run_in_threadpool(_renomear_local, banco, novo)
                await refazer_testes(request, LOCAL, trocadas)  # o par mudou: testa (T416)
        finally:
            ok = fim == "pronto"
            removeu = acao == "remover"
            falha = "falhou_remover" if removeu else "falhou_baixar"
            andamento.clear()
            andamento["estado"] = ("removido" if removeu else "pronto") if ok else falha
            andamento["motivo"] = None if ok else motivo

    criar_tarefa(request, "modelo local", trava, rodar_comando)
    return _cartao_ia_local(request, foco=True)


def _linha_json(linha: bytes) -> dict[str, Any]:
    try:
        lida = json.loads(linha)
    except ValueError:
        return {}
    return lida if isinstance(lida, dict) else {}


def _desligar_local(con: sqlite3.Connection) -> None:
    locais = {n: tarefa_ia(con, n) for n in tarefas()}
    desligar = {n: replace(t, ligada=False) for n, t in locais.items() if t.backend == LOCAL}
    if desligar:
        gravar_tarefas_ia(con, desligar)


def _renomear_local(banco: Path, nome: str) -> list[TarefaIA]:
    """Depois do "Trocar modelo", as tarefas no local levam o nome do modelo novo (devolvidas)."""
    with closing(abrir(banco)) as con:
        locais = {n: tarefa_ia(con, n) for n in tarefas()}
        trocar = {n: replace(t, modelo=nome) for n, t in locais.items() if t.backend == LOCAL}
        if trocar:
            gravar_tarefas_ia(con, trocar)
        return list(trocar.values())
