"""Configurações e interruptores (desenho 13.2 e 13.7; plano T54; decisão 17 e DP8).

Os grupos em `/configuracoes/{grupo}`: geral (tema, idioma e tamanho do texto pelas rotas
`/preferencias`; Meu país e moeda de exibição pelo próprio `/configuracoes/geral`; o
`/configuracoes/aparencia` de antes só redireciona no GET), fontes (uma chave por fonte, por leva),
funções (as chaves da 13.7 e o N dos destaques), segundo plano, privacidade (onde ficam
os dados, a recomendação de disco cifrado e o aviso de versão), serviços (a chave do 2Captcha, que
fica no cofre; o interruptor e o apagar moram em `servicos.py`, T184) e sites com login (T218: só
existe com leitor registrado; o interruptor de cada site grava na hora e os horários são um campo
só). "Fazer login agora" e "Esquecer logins" (T219) usam o `jobot.navegador` e a trava `login` do
`serve`: nunca abrem o navegador nem apagam o perfil enquanto uma leitura com login roda.

Checkbox sem marca é chave desligada: o formulário de cada grupo manda o estado inteiro. Ligar ou
desligar a conversão de moeda chama `aplicar_cotacoes` e, com ela ou com as regras de ocultar
mudadas, `recalcular_encaixe`, as duas com `hoje` = dia local do `Relogio` (nunca o dia UTC).
Todo comando do sistema passa pelo executor de `app.state.rodar_comando`, o ambiente de
`app.state.ambiente` e a plataforma de `app.state.plataforma`: o teste põe os falsos.
"""

import asyncio
import logging
import re
import sqlite3
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from jobot.agenda.versao import aviso_ligado
from jobot.banco import buscas, cadastros, cotacoes
from jobot.banco.cadastros import PADROES, gravar_config, ler_config, ligar_fonte, meu_pais
from jobot.banco.captcha import NOME_NO_COFRE
from jobot.banco.execucoes import LinhaSaude, leitura_login_rodando, ultimas_que_rodaram
from jobot.navegador import limites
from jobot.navegador.execucao import dependencias_de_producao
from jobot.navegador.instalador import baixar_chromium, remover_chromium
from jobot.navegador.janela_comum import janela_de_producao
from jobot.navegador.login_manual import fazer_login
from jobot.navegador.perfil import apagar_perfil
from jobot.nucleo.cambio import MOEDAS_EXIBICAO, moeda_do_pais
from jobot.nucleo.captcha import validar_chave
from jobot.nucleo.horarios import horarios_validos
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.leitores.registro import leitores
from jobot.nucleo.tratamento.locais import codigos_de_pais
from jobot.painel.ambiente import (
    abrir_instalador_do_painel,
    ambiente_do_painel,
    cofre_do_painel,
    ler_navegador_do_painel,
    no_linux,
    rodar_do_painel,
)
from jobot.painel.consultas import relogio_do_painel
from jobot.painel.formatos import opcoes_de_pais
from jobot.painel.rotas.execucao import criar_tarefa
from jobot.painel.rotas.fontes import estado_dos_escopos, motivo_mais_grave
from jobot.painel.rotas.servicos import contexto_captcha, no_cofre
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar
from jobot.sistema import caso, segundo_plano_linux
from jobot.sistema.segundo_plano_linux import Recusa

router = APIRouter(prefix="/configuracoes")
_LOG = logging.getLogger(__name__)

GRUPOS = (
    "geral",
    "fontes",
    "funcoes",
    "segundo-plano",
    "privacidade",
    "servicos",
    "sites-com-login",
    "ferramentas",
)
# um ícone Lucide por grupo (T262), na ordem de GRUPOS; o desenho é a máscara em configuracoes.css
_ICONES = dict(
    zip(
        GRUPOS,
        (
            "sliders-horizontal",
            "rss",
            "toggle-right",
            "timer",
            "shield",
            "plug",
            "key-round",
            "globe",
        ),
        strict=True,
    )
)
_COM_LOGIN = "sites-com-login"
_FERRAMENTAS = "ferramentas"
_SO_COM_LEITOR = (_COM_LOGIN, _FERRAMENTAS)  # hoje a única ferramenta é o navegador do login
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
    "segundo-plano": "segundo_plano",
    "privacidade": "privacidade",
    "servicos": "servicos",
    "sites-com-login": "sites_com_login",
    "ferramentas": "ferramentas",
}


def grupos_visiveis(leitores: Sequence[LeitorComLogin]) -> tuple[str, ...]:
    """Os grupos da página: "Sites com login" e "Ferramentas" só existem com leitor registrado
    (D132.23, D137.12)."""
    return GRUPOS if leitores else tuple(g for g in GRUPOS if g not in _SO_COM_LEITOR)


def leitores_do_painel(request: Request) -> Sequence[LeitorComLogin]:
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


async def _ctx_geral(request: Request, con: Con) -> dict[str, Any]:
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
    for leitor in leitores_do_painel(request):
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
                "login": _estados_de_login(request).get(leitor.chave),
                "minutos": _minutos_de_login(),
            }
        )
    return cartoes


async def contexto_sites_com_login(request: Request, con: Con) -> dict[str, Any]:
    achado = getattr(request.app.state, "navegador_instalado", None)  # nunca sobe o driver (E8)
    return {
        "navegador": achado if achado in ("chrome", "chromium") else "nenhum",
        "cartoes": _cartoes_de_sites(request, con),
        "horarios_texto": _horarios_em_texto(con),
    }


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
    return {"navegador": navegador, "resultado": resultado, "estado": estado}


async def _contexto_ferramentas(request: Request, con: Con) -> dict[str, Any]:
    return contexto_ferramenta_navegador(request)


_CONTEXTOS: dict[str, Contexto] = {
    "geral": _ctx_geral,
    "fontes": _ctx_fontes,
    "funcoes": _ctx_funcoes,
    "segundo-plano": _ctx_segundo_plano,
    "privacidade": _ctx_privacidade,
    "servicos": contexto_captcha,
    "sites-com-login": contexto_sites_com_login,
    "ferramentas": _contexto_ferramentas,
}


async def _pagina(
    request: Request, con: Con, grupo: str, status: int = 200, **ctx: Any
) -> Response:
    contexto: dict[str, Any] = {
        "grupo": grupo,
        "abas": [
            (g, "configuracoes.grupo." + g.replace("-", "_"), _ICONES[g])
            for g in grupos_visiveis(leitores_do_painel(request))
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
    if grupo not in grupos_visiveis(leitores_do_painel(request)):
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
    "geral": _gravar_geral,
    "fontes": _gravar_fontes,
    "funcoes": _gravar_funcoes,
    "segundo-plano": _gravar_segundo_plano,
    "privacidade": _gravar_privacidade,
    "servicos": _gravar_servicos,
    "sites-com-login": _gravar_sites_com_login,
}


# --- rotas ---------------------------------------------------------------------------------


@router.get("")
async def raiz() -> RedirectResponse:
    return _volta(GRUPOS[0])


@router.get("/aparencia")
async def aparencia_de_antes() -> RedirectResponse:
    """O endereço velho do grupo que virou Geral (só o GET; o POST não tem cópia, D139.25)."""
    return _volta("geral")


@router.get("/{grupo}")
async def mostrar(request: Request, con: Con, grupo: str) -> Response:
    if grupo in _SO_COM_LEITOR and grupo not in grupos_visiveis(leitores_do_painel(request)):
        # o navegador guarda o último grupo (T262): sem leitor ele sumiu, e a pessoa cai em Geral
        return _volta(GRUPOS[0])
    salvo = request.query_params.get("salvo") == "1"
    return await _pagina(request, con, _grupo_valido(request, grupo), salvo=salvo)


@router.post("/{grupo}")
async def gravar(request: Request, con: Con, grupo: str) -> Response:
    gravador = _GRAVADORES.get(_grupo_valido(request, grupo))
    if gravador is None:  # "Ferramentas" não tem formulário: cada ação tem a sua rota
        raise HTTPException(405)
    return await gravador(request, con)


@router.post(f"/{_COM_LOGIN}/{{chave}}/interruptor")
async def interruptor_do_site(request: Request, con: Con, chave: str) -> Response:
    """Liga ou desliga um site na hora (D132.8); só chave de leitor, nunca de fonte pública."""
    _grupo_valido(request, _COM_LOGIN)
    if chave not in {leitor.chave for leitor in leitores_do_painel(request)}:
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


# --- fazer login agora e esquecer logins (T219; D132.18, D132.21, D132.22, D132.52) ----------


def _minutos_de_login() -> int:
    return int(limites.PRAZO_LOGIN_MANUAL_S // 60)  # lido na hora: o monkeypatch vai em limites


def _leitor(request: Request, chave: str) -> LeitorComLogin:
    """Só chave de leitor registrado; sem leitor o grupo nem existe (404)."""
    _grupo_valido(request, _COM_LOGIN)
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


@router.post(f"/{_COM_LOGIN}/{{chave}}/login")
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
    dados: Path = request.app.state.banco.parent
    env = ambiente_do_painel(request)
    await trava.acquire()  # livre: não suspende, então a checagem acima vale (como no laço)
    estados[chave] = "aguardando"

    async def login() -> None:
        try:
            async with dependencias_de_producao(dados, env) as deps:
                estados[chave] = await fazer_login(leitor, deps, janela_de_producao())
        except Exception:
            estados[chave] = "erro"
            raise  # o `rodar` registra no log e solta a trava

    criar_tarefa(request, "login manual", trava, login)
    return _fragmento_de_login(request, chave, "aguardando")


@router.get(f"/{_COM_LOGIN}/{{chave}}/login")
async def estado_do_login(request: Request, chave: str) -> Response:
    """O HTMX pergunta a cada 5 s; enquanto espera, 204 (nada troca na tela)."""
    _leitor(request, chave)
    estado = _estados_de_login(request).get(chave)
    if estado == "aguardando":
        return Response(status_code=204)
    if estado is None:
        return Response()  # nunca pediu login: nada a mostrar
    return _fragmento_de_login(request, chave, estado)


@router.post(f"/{_COM_LOGIN}/esquecer/confirmar")
async def esquecer_logins_confirmado(request: Request) -> Response:
    """Confirma o alerta: apaga a pasta do perfil, nunca com leitura ou login rodando (D132.22)."""
    _grupo_valido(request, _COM_LOGIN)
    trava = _trava_de_login(request)
    if trava.locked():
        return renderizar(request, "configuracoes/_esquecer.html", fase="em_andamento")
    await trava.acquire()  # livre: não suspende; segura enquanto apaga
    try:
        await run_in_threadpool(apagar_perfil, request.app.state.banco.parent)
    except OSError as erro:  # symlink recusado ou disco: o caminho fica só no log
        _LOG.warning("esquecer logins: não consegui apagar o perfil: %s", type(erro).__name__)
        return renderizar(request, "configuracoes/_esquecer.html", fase="erro")
    finally:
        trava.release()
    _estados_de_login(request).clear()  # o "Login feito" de antes não vale mais
    return renderizar(request, "configuracoes/_esquecer.html", fase="apagados")


# --- ferramentas: o navegador dos sites com login (T240; D137.1 a D137.8, D137.12 a D137.14) ---

_NAVEGADOR = "/ferramentas/navegador"


def _fragmento_do_navegador(request: Request, **ctx: Any) -> Response:
    return renderizar(
        request,
        "configuracoes/_ferramenta_navegador.html",
        **(contexto_ferramenta_navegador(request) | ctx),
    )


@router.get(_NAVEGADOR)
async def estado_do_navegador(request: Request) -> Response:
    """O HTMX pergunta a cada 5 s; enquanto baixa ou remove, 204 (nada troca na tela)."""
    _grupo_valido(request, _FERRAMENTAS)
    if _ferramentas(request).get("navegador") in _RODANDO:
        return Response(status_code=204)
    return _fragmento_do_navegador(request)


@router.post(_NAVEGADOR + "/baixar")
async def baixar_navegador(request: Request) -> Response:
    """Baixa o Chromium do Playwright em segundo plano; um download por vez (D137.4)."""
    _grupo_valido(request, _FERRAMENTAS)
    trava = _trava(request, "navegador")
    if getattr(request.app.state, "navegador_instalado", None) or trava.locked():
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
                else:
                    _LOG.warning("o instalador terminou, mas o navegador não apareceu no disco")
        finally:
            ferramentas["navegador"] = resultado

    criar_tarefa(request, "baixar navegador", trava, baixar)
    return _fragmento_do_navegador(request)


@router.post(_NAVEGADOR + "/remover")
async def remover_navegador(request: Request) -> Response:
    """Remove o Chromium do Playwright, nunca com o navegador aberto num site (D137.13)."""
    _grupo_valido(request, _FERRAMENTAS)
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
