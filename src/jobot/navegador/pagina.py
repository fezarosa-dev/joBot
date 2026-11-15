"""Uma navegação com as checagens do desenho A7 (D132.30, D132.37, D132.42, D132.54).

Ordem: política → `goto` → host e política de `page.url` → login → Cloudflare → CAPTCHA (A8) →
401/403/bloqueio → 429 → assentar → rolar → `Captura`. Nada aqui clica, digita nem envia: só lê
a página; a única escrita é a da `cola` do CAPTCHA (`navegador/captcha.py`).
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urldefrag, urlsplit

from playwright.async_api import Error as ErroDoPlaywright
from playwright.async_api import Page, Response
from playwright.async_api import TimeoutError as EstouroDoPlaywright

from jobot.navegador import limites
from jobot.navegador.captcha import Widget, achar_widget
from jobot.navegador.js import rolar
from jobot.navegador.politica import Politica, casa_login, dentro_dos_hosts
from jobot.nucleo.http import MAX_RETRY_AFTER_S, segundos_retry_after
from jobot.nucleo.leitores.base import Captura, LeitorComLogin, ParadaLogin, RespostaCapturada
from jobot.nucleo.relogio import Relogio

_LOG = logging.getLogger(__name__)

TIPOS_CAPTURADOS = frozenset({"application/json", "text/html"})


@dataclass(frozen=True)
class Recusada:
    url_host: str


Visita = Captura | ParadaLogin | Recusada | Widget
Desafiar = Callable[[Widget], Awaitable[ParadaLogin | None]]


class Ouvidas(list[RespostaCapturada]):
    """A lista que `ouvir_respostas` vai enchendo, mais o que a navegação precisa saber dela."""

    def __init__(self) -> None:
        super().__init__()
        self.ativa = True  # desligada, o ouvinte não faz nada (o Playwright não sai da página)
        self.ultimas: dict[str, Response] = {}  # última resposta por URL, de qualquer host
        # shortcut: não separa documento de XHR; um fetch à mesma URL depois do documento troca o
        # status lido. Separar por `request.resource_type` se um site real fizer isso (o
        # test_navegador_ast recusa `request` e `resource_type` hoje).
        self.pedidos = 0
        self.respondidos = 0
        self._lendo: set[asyncio.Task[None]] = set()

    async def prontas(self) -> None:
        """Espera os corpos que ainda estão sendo lidos, no máximo `PRAZO_CORPOS_S`.

        Resposta em fluxo nunca entrega o corpo: o que sobrar no prazo é cancelado e não entra."""
        laco = asyncio.get_running_loop()
        fim = laco.time() + limites.PRAZO_CORPOS_S
        while self._lendo and (resto := fim - laco.time()) > 0:
            await asyncio.wait(self._lendo, timeout=resto)
        presas = list(self._lendo)
        for tarefa in presas:
            tarefa.cancel()
        await asyncio.gather(*presas, return_exceptions=True)


def _host(url: str) -> str:
    """Host da URL, ou "" quando ela é torta (colchete sem par)."""
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def _onde(url: str) -> str:
    """Host e caminho, para o log: nunca query, cookie, cabeçalho ou corpo."""
    partes = urlsplit(url)
    return f"{partes.hostname or ''}{partes.path}"


def _casa(url: str, padroes: Sequence[str] | None) -> bool:
    """E3: `re.fullmatch` com `host + caminho`, sem query; `None` aceita tudo."""
    return padroes is None or any(re.fullmatch(p, _onde(url)) for p in padroes)


def ouvir_respostas(page: Page, hosts: Sequence[str], padroes: Sequence[str] | None) -> Ouvidas:
    """Liga o evento `response` da página e devolve a lista que vai enchendo (D132.54).

    Entra só resposta dos `hosts`, JSON ou HTML, até `MAX_RESPOSTA_BYTES` e `MAX_RESPOSTAS`."""
    ouvidas = Ouvidas()

    async def guardar(resposta: Response, tipo: str) -> None:
        try:
            corpo = await resposta.body()
        except ErroDoPlaywright:  # salto, página que já saiu: sem corpo
            return
        if (
            not ouvidas.ativa
            or len(corpo) > limites.MAX_RESPOSTA_BYTES
            or len(ouvidas) >= limites.MAX_RESPOSTAS
        ):
            return
        texto = corpo.decode("utf-8", errors="replace")
        ouvidas.append(RespostaCapturada(resposta.url, resposta.status, tipo, texto))

    def ao_responder(resposta: Response) -> None:
        if not ouvidas.ativa:
            return
        ouvidas.respondidos += 1
        ouvidas.ultimas[resposta.url] = resposta
        cabecalhos = resposta.headers
        tipo = cabecalhos.get("content-type", "").split(";")[0].strip().lower()
        if (
            not dentro_dos_hosts(resposta.url, hosts)
            or tipo not in TIPOS_CAPTURADOS
            or not _casa(resposta.url, padroes)
            or len(ouvidas) >= limites.MAX_RESPOSTAS
        ):
            return
        tamanho = cabecalhos.get("content-length", "")
        if tamanho.isdigit() and int(tamanho) > limites.MAX_RESPOSTA_BYTES:
            return
        tarefa = asyncio.get_running_loop().create_task(guardar(resposta, tipo))
        ouvidas._lendo.add(tarefa)
        tarefa.add_done_callback(ouvidas._lendo.discard)

    def ao_pedir(_: object) -> None:
        if ouvidas.ativa:
            ouvidas.pedidos += 1

    # shortcut: o ouvinte fica na page (a lista permitida não tem remove_listener) e só se cala;
    # rever se uma page passar de dezenas de navegações
    page.on("response", ao_responder)
    page.on("request", ao_pedir)
    return ouvidas


async def _e_cloudflare(page: Page) -> bool:
    """E9: título "Just a moment" ou o script do desafio. Página trocando no meio: ainda nele."""
    try:
        if (await page.title()).startswith("Just a moment"):
            return True
        return await page.locator('script[src*="/cdn-cgi/challenge-platform/"]').count() > 0
    except ErroDoPlaywright:
        return True


async def _assentar(page: Page) -> None:
    """E11: `load` e depois `networkidle`, sem esperar além do prazo por este último."""
    await page.wait_for_load_state("load")
    try:
        await page.wait_for_load_state("networkidle", timeout=limites.ESPERA_ASSENTAR_MS)
    except EstouroDoPlaywright:
        pass


async def _depois_de_rolar(ouvidas: Ouvidas, relogio: Relogio, inicio: int) -> None:
    """Dá tempo à página de pedir o resto: para quando ela pediu algo depois de rolar e todo
    pedido teve resposta por dois passos seguidos; sem pedido novo, espera todos os passos."""
    antes = -1
    for _ in range(limites.PASSOS_DEPOIS_DE_ROLAR):
        await relogio.dormir(1)
        if ouvidas.pedidos == ouvidas.respondidos == antes:
            break
        quieta = ouvidas.pedidos == ouvidas.respondidos and ouvidas.pedidos > inicio
        antes = ouvidas.pedidos if quieta else -1


def _parou(parada: ParadaLogin, url: str) -> ParadaLogin:
    _LOG.info("navegação parou (%s) em %r", parada, _onde(url))
    return parada


async def visitar(
    page: Page,
    url: str,
    leitor: LeitorComLogin,
    politica: Politica,
    relogio: Relogio,
    *,
    cola: Desafiar | None = None,
) -> Visita:
    """Navega a `url` e devolve a `Captura`, a parada do site ou a `Recusada` pela política.

    Página com CAPTCHA vai à `cola`; sem ela, a visita devolve o `Widget` achado."""
    if not politica(url):
        host = _host(url)
        _LOG.info("navegação recusada pela política: %r", host)
        return Recusada(host)
    for tentativa in range(2):
        ouvidas = ouvir_respostas(page, leitor.hosts, leitor.respostas)
        try:
            visita = await _uma_vez(
                page, url, leitor, politica, ouvidas, relogio, cola=cola, ultima=tentativa == 1
            )
        finally:
            ouvidas.ativa = False  # o ouvinte fica na page: solta o que ele juntou
            del ouvidas[:]  # `clear` é nome do Playwright: o test_navegador_ast recusa
            ouvidas.ultimas = {}
        if visita is not None:
            return visita
    raise AssertionError("inalcançável: a segunda tentativa sempre decide")


def _recusada(url: str, leitor: LeitorComLogin, politica: Politica) -> ParadaLogin | None:
    """Host e política da página atual, sem ler o conteúdo: a política vale também para a página
    a que um salto, a função de retorno do widget ou a própria página levaram."""
    if dentro_dos_hosts(url, leitor.hosts):
        if politica(url):
            return None
        _LOG.info("página final recusada pela política: %r", _host(url))
    return "precisa_login" if casa_login(url, leitor.prefixos_login) else "bloqueio"


async def _fora_ou_login(
    page: Page, leitor: LeitorComLogin, politica: Politica, status: int
) -> ParadaLogin | None:
    """Host, política e login; refeitas quando a página troca sozinha (Cloudflare)."""
    if parada := _recusada(page.url, leitor, politica):
        return parada
    if (
        await page.locator("input[type=password]").count() > 0
        or leitor.e_login(Captura(page.url, status, await page.content(), ()))
        or casa_login(page.url, leitor.prefixos_login)
    ):
        return "precisa_login"
    return None


async def _desafio(page: Page, leitor: LeitorComLogin, status: int) -> Widget | None:
    """O widget que barra a página; numa página logada com 200 ele é de formulário, não se toca."""
    if status not in (401, 403, 429) and leitor.pagina_logada(await page.content(), page.url):
        return None
    return await achar_widget(page)


async def _uma_vez(
    page: Page,
    url: str,
    leitor: LeitorComLogin,
    politica: Politica,
    ouvidas: Ouvidas,
    relogio: Relogio,
    *,
    cola: Desafiar | None,
    ultima: bool,
) -> Visita | None:
    """Uma navegação; `None` quando o 429 pede outra tentativa depois da espera."""
    resposta = await page.goto(url)
    status = resposta.status if resposta is not None else 0
    if parada := await _fora_ou_login(page, leitor, politica, status):
        return _parou(parada, page.url)
    if await _e_cloudflare(page):
        for _ in range(limites.ESPERA_CLOUDFLARE_S):
            await relogio.dormir(1)
            if not await _e_cloudflare(page):
                break
        else:
            return _parou("captcha", page.url)  # não saiu sozinho: sem 2Captcha (A8)
        await page.wait_for_load_state("load")
        # o status e o Retry-After da nova; page.url traz o #, a resposta não
        resposta = ouvidas.ultimas.get(urldefrag(page.url).url, resposta)
        status = resposta.status if resposta is not None else 0
        if parada := await _fora_ou_login(page, leitor, politica, status):
            return _parou(parada, page.url)
    # o widget vem antes do 401/403 e do 429: o site que desafia responde com eles
    while (widget := await _desafio(page, leitor, status)) is not None:
        if cola is None:
            return widget
        if parada := _recusada(page.url, leitor, politica):  # trocou depois da checagem
            return _parou(parada, page.url)
        if parada := await cola(widget):
            return _parou(parada, page.url)
        await page.wait_for_load_state("load")
        # saiu do desafio: o status e o Retry-After são os do documento novo; sem documento novo
        # (o desafio saiu no lugar), o 403/429 era do desafio e não vale mais
        nova = ouvidas.ultimas.get(urldefrag(page.url).url)
        resposta = None if nova is resposta else nova
        status = resposta.status if resposta is not None else 200
        if parada := await _fora_ou_login(page, leitor, politica, status):
            return _parou(parada, page.url)
    html = await page.content()
    if status in (401, 403) or leitor.pagina_bloqueada(html, page.url):
        return _parou("bloqueio", page.url)
    if status == 429:
        pedida = segundos_retry_after(
            resposta.headers.get("retry-after") if resposta is not None else None,
            relogio.agora(),
        )
        if ultima or (pedida is not None and pedida > MAX_RETRY_AFTER_S):
            return _parou("no_limite", page.url)
        await relogio.dormir(limites.ESPERA_429_S if pedida is None else pedida)
        return None
    await _assentar(page)
    if leitor.rolar:
        inicio = ouvidas.pedidos
        await rolar(page)
        await _depois_de_rolar(ouvidas, relogio, inicio)
    await ouvidas.prontas()
    html = await page.content()
    # a página pode ter saído sozinha depois das checagens (refresh, JS, rolar); a URL é lida
    # depois do HTML, para um salto no meio nunca passar com o HTML da página nova
    final = page.url
    if parada := _recusada(final, leitor, politica):
        return _parou(parada, final)
    return Captura(final, status, html, tuple(ouvidas))
