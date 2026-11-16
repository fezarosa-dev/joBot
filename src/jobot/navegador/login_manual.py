"""Fazer login agora pela janela comum (D132.52, forma trocada pela T232, D136.1 a D136.8).

Abre o navegador com o perfil do joBot na página de login do site, numa janela comum, sem
automação. Quem digita e envia é a pessoa (Google, e-mail e senha ou outro jeito de entrar); o
joBot nunca preenche campo, clica nem envia nada. Quando a pessoa fecha a janela, ou o prazo
`limites.PRAZO_LOGIN_MANUAL_S` acaba, o joBot abre a janela automática no mesmo perfil, vai ao
`url_entrada` do leitor, confere a sessão com `pagina_logada` e fecha.
"""

import contextlib
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from playwright.async_api import Error as ErroDoPlaywright
from playwright.async_api import TimeoutError as EstouroDoPlaywright

from jobot.navegador import limites
from jobot.navegador.abrir import SemNavegador, SemTela, abrir_contexto, ambiente_do_navegador
from jobot.navegador.execucao import Dependencias
from jobot.navegador.janela_comum import (
    JanelaComum,
    argumentos_da_janela,
    esperar_fechar,
    perfil_em_uso,
)
from jobot.navegador.perfil import pasta_do_perfil, preparar_preferencias
from jobot.nucleo.contas import EstadoSessao, MotivoSessao
from jobot.nucleo.leitores.base import LeitorComLogin

log = logging.getLogger(__name__)

Resultado = Literal["pronto", "nao_entrou", "tempo_esgotado", "sem_tela", "sem_navegador", "em_uso"]
Fim = Literal["fechou", "prazo", "sem_tela", "sem_navegador", "em_uso"]


async def abrir_e_esperar(
    janela: JanelaComum, dados: Path, ambiente: Mapping[str, str], url: str
) -> Fim:
    """Abre a janela comum em `url` e espera ela fechar, ou o prazo acabar."""
    if not ambiente:
        return "sem_tela"
    executavel = await janela.caminho()
    if executavel is None:
        return "sem_navegador"
    perfil = pasta_do_perfil(dados)
    # com o perfil aberto, o navegador repassa o endereço ao processo aberto e sai na hora
    if perfil_em_uso(perfil):
        return "em_uso"
    preparar_preferencias(perfil)
    processo = await janela.abrir(
        argumentos_da_janela(executavel, perfil, url), ambiente_do_navegador(ambiente)
    )
    return "fechou" if await esperar_fechar(processo) else "prazo"


async def _sessao_aberta(
    leitor: LeitorComLogin, deps: Dependencias, ambiente: Mapping[str, str]
) -> bool:
    """A janela automática no mesmo perfil, em `url_entrada`: a página está logada?"""
    contexto = await abrir_contexto(deps.dados, ambiente, deps.lancar)
    try:
        aba = await contexto.new_page()
        await aba.goto(leitor.url_entrada)
        # o site pode pôr a marca da sessão por script depois do `load`; estourar não é erro
        with contextlib.suppress(EstouroDoPlaywright):
            await aba.wait_for_load_state("networkidle", timeout=limites.ESPERA_ASSENTAR_MS)
        return leitor.pagina_logada(await aba.content(), aba.url)
    except ErroDoPlaywright:
        return False  # a página não se leu: não dá para dizer que entrou
    finally:
        with contextlib.suppress(ErroDoPlaywright):
            await contexto.close()


async def fazer_login(leitor: LeitorComLogin, deps: Dependencias, janela: JanelaComum) -> Resultado:
    """Espera a pessoa entrar pela janela comum e confere a sessão (cancelar fecha a janela)."""
    ambiente = deps.ambiente()
    fim = await abrir_e_esperar(janela, deps.dados, ambiente, leitor.url_login)
    resultado: Resultado
    if fim == "sem_tela" or fim == "sem_navegador" or fim == "em_uso":
        resultado = fim
    else:
        try:
            logado = await _sessao_aberta(leitor, deps, ambiente)
        except SemTela:
            resultado = "sem_tela"
        except SemNavegador:
            resultado = "sem_navegador"
        else:
            if logado:
                resultado = "pronto"
            else:
                resultado = "nao_entrou" if fim == "fechou" else "tempo_esgotado"
    log.info("login manual do site %s: %s", leitor.chave, resultado)
    return resultado


def sessao_do_login(resultado: Resultado) -> tuple[EstadoSessao, MotivoSessao | None]:
    """O estado do login que o fim do "Fazer login agora" grava (desenho 5.1)."""
    match resultado:
        case "pronto":
            return ("conectado", None)
        case "nao_entrou" | "tempo_esgotado":
            return ("precisa_entrar", None)
        case "sem_tela" | "sem_navegador" | "em_uso":
            return ("nao_conferiu", resultado)
