"""Cola do CAPTCHA com o 2Captcha na navegação com login (desenho A8; ADR 0022).

Acha o widget da página (reCAPTCHA v2, visível ou invisível, e Turnstile), pede o token ao
2Captcha com a chave do cofre e o entrega no campo de resposta do próprio widget, chamando só a
função de retorno que ele declarou. Nada mais é escrito na página: nada de clique, digitação nem
envio. O log nunca leva a chave, o token, cookie nem a query da página.
"""

import asyncio
import contextlib
import logging
import sqlite3
from dataclasses import dataclass
from typing import Final, Literal
from urllib.parse import parse_qs, urldefrag, urlsplit

from playwright.async_api import Error as ErroDoPlaywright
from playwright.async_api import Locator, Page, Request

from jobot.banco.cadastros import ler_config
from jobot.banco.captcha import NOME_NO_COFRE, captcha_pronto, reservar_resolucao
from jobot.navegador import limites
from jobot.navegador.js import agente_do_navegador, entregar_token, nome_de_retorno_valido
from jobot.nucleo.captcha import Desafio, ErroCaptcha, resolver
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.leitores.base import ParadaLogin
from jobot.nucleo.relogio import Relogio
from jobot.sistema.cofre import Cofre

_LOG = logging.getLogger(__name__)

Aceito = Literal["recaptcha_v2", "turnstile"]
_CAMPO: Final[dict[Aceito, str]] = {
    "recaptcha_v2": "g-recaptcha-response",
    "turnstile": "cf-turnstile-response",
}
# reCAPTCHA v3 (e o Enterprise de pontuação) carrega com `render=<sitekey>`; `render=explicit`
# é o v2 desenhado pelo site.
_SCRIPT_V3 = 'script[src*="recaptcha/api.js"][src*="render="]'
# Widget preso a botão envia o formulário pela função de retorno: não é desafio (A8, D132.11).
_NAO_BOTAO = "[data-sitekey]:not(button):not(input)"


@dataclass(frozen=True)
class Widget:
    """O desafio da página; `nao_aceito` (v3, função de retorno torta) não vai ao 2Captcha."""

    tipo: Literal["recaptcha_v2", "turnstile", "nao_aceito"]
    sitekey: str
    invisivel: bool
    retorno: str | None  # `data-callback`
    acao: str | None  # `data-action` do Turnstile


async def _atributo(alvo: Locator, nome: str) -> str | None:
    return await alvo.get_attribute(nome, timeout=limites.ESPERA_ATRIBUTO_MS) or None


async def _do_div(div: Locator, tipo: Aceito, *, invisivel: bool, acao: str | None) -> Widget:
    sitekey = await _atributo(div, "data-sitekey") or ""
    retorno = await _atributo(div, "data-callback")
    if retorno is not None and not nome_de_retorno_valido(retorno):
        return Widget("nao_aceito", sitekey, False, None, None)
    return Widget(tipo, sitekey, invisivel, retorno, acao)


async def achar_widget(page: Page) -> Widget | None:
    """O primeiro widget da página; `None` sem widget ou com a página trocando no meio."""
    try:
        for script in await page.locator(_SCRIPT_V3).all():
            src = await _atributo(script, "src") or ""
            render = parse_qs(urlsplit(src).query).get("render", [""])[0]
            if render and render != "explicit":
                return Widget("nao_aceito", render, False, None, None)
        recaptcha = await page.locator(f".g-recaptcha{_NAO_BOTAO}").all()
        if recaptcha:
            invisivel = await _atributo(recaptcha[0], "data-size") == "invisible"
            return await _do_div(recaptcha[0], "recaptcha_v2", invisivel=invisivel, acao=None)
        turnstile = await page.locator(f".cf-turnstile{_NAO_BOTAO}").all()
        if turnstile:
            acao = await _atributo(turnstile[0], "data-action")
            return await _do_div(turnstile[0], "turnstile", invisivel=False, acao=acao)
    except ErroDoPlaywright:  # o estouro do `get_attribute` também é um `Error`
        return None
    return None


async def resolver_na_pagina(
    page: Page,
    widget: Widget,
    *,
    con: sqlite3.Connection,
    cliente: ClienteEducado,
    relogio: Relogio,
    cofre: Cofre,
    user_agent: str,
) -> bool:
    """Uma resolução: True quando a página saiu do desafio em até `limites.ESPERA_TOKEN_S`."""
    tipo = widget.tipo
    if tipo == "nao_aceito":
        return False
    if ler_config(con, "captcha_ligado") is not True:  # desligado nem abre o cofre (pede senha)
        _LOG.info("2captcha desligado: o desafio fica sem resolver")
        return False
    try:
        async with asyncio.timeout(limites.PRAZO_COFRE_S):
            # shortcut: a thread do keyring fica presa até o cofre responder; trocar quando o
            # cofre tiver API assíncrona
            achado = await asyncio.to_thread(cofre.ler, NOME_NO_COFRE)
    except TimeoutError:
        _LOG.warning("2captcha: o cofre não respondeu em %s s", limites.PRAZO_COFRE_S)
        return False
    if achado is None or not captcha_pronto(con, achado[0]):
        _LOG.info("2captcha sem chave: o desafio fica sem resolver")
        return False
    try:
        desafio = Desafio(tipo, page.url, widget.sitekey, user_agent, widget.invisivel, widget.acao)
    except ValueError as erro:  # mensagens fixas, sem dado da página
        _LOG.info("2captcha: desafio fora do formato (%s)", erro)
        return False
    try:
        solucao = await resolver(
            cliente, achado[0], desafio, relogio, reservar=lambda dia: reservar_resolucao(con, dia)
        )
    except ErroCaptcha as erro:
        _LOG.info("2captcha não resolveu: %s", erro.falha.value)
        return False
    if solucao.user_agent is not None and solucao.user_agent != user_agent:
        # D132.56: o navegador segue com o seu; trocar no meio da sessão denuncia o robô
        _LOG.info("2captcha devolveu outro user agent; o navegador fica com o seu")
    pagina = urldefrag(page.url).url
    with contextlib.suppress(ErroDoPlaywright):  # a função de retorno pode trocar de página já
        await entregar_token(page, _CAMPO[tipo], solucao.token, widget.retorno)
    for _ in range(limites.ESPERA_TOKEN_S):
        await relogio.dormir(1)
        if urldefrag(page.url).url != pagina or await achar_widget(page) != widget:
            return True
    _LOG.info("a página não saiu do desafio em %s s depois do token", limites.ESPERA_TOKEN_S)
    return False


class Cola:
    """O 2Captcha de uma aba numa execução: uma tentativa por página (URL sem o fragmento), e o
    widget já aceito que volta é bloqueio (E10). O user agent é o que o navegador manda."""

    def __init__(
        self,
        page: Page,
        *,
        con: sqlite3.Connection,
        cliente: ClienteEducado,
        relogio: Relogio,
        cofre: Cofre,
    ) -> None:
        self._aba = page  # `page` é nome do Playwright: o test_navegador_ast recusa
        self._con = con
        self._cliente = cliente
        self._relogio = relogio
        self._cofre = cofre
        self._agente = ""
        self._aceitos: set[tuple[str, str]] = set()
        self._tentadas: set[str] = set()
        page.on("request", self._ouvir)

    def _ouvir(self, pedido: Request) -> None:
        self._agente = pedido.headers.get("user-agent") or self._agente

    async def __call__(self, widget: Widget) -> ParadaLogin | None:
        """A parada da página, ou `None` quando ela saiu do desafio."""
        if (widget.tipo, widget.sitekey) in self._aceitos:
            return "bloqueio"  # E10: o desafio voltou depois de aceito
        pagina = urldefrag(self._aba.url).url
        if widget.tipo == "nao_aceito" or pagina in self._tentadas:
            return "captcha"
        self._tentadas.add(pagina)
        resolveu = await resolver_na_pagina(
            self._aba,
            widget,
            con=self._con,
            cliente=self._cliente,
            relogio=self._relogio,
            cofre=self._cofre,
            user_agent=self._agente or await agente_do_navegador(self._aba),
        )
        if not resolveu:
            return "captcha"
        self._aceitos.add((widget.tipo, widget.sitekey))
        return None
