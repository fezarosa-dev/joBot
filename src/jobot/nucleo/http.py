"""Coleta educada (desenho 8.2): o único cliente HTTP do joBot."""

import asyncio
import codecs
import ipaddress
import json
import socket
from collections import defaultdict
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Literal, Protocol

import httpx

from jobot.nucleo.relogio import Relogio

TETO_PADRAO = 5 * 1024 * 1024
MAX_RETRY_AFTER_S = 600.0
ESPERAS_LIMITE = (30.0, 60.0, 120.0)  # 429/503 sem Retry-After
ESPERAS_ERRO = (2.0, 4.0)  # erro de rede ou 5xx: duas novas tentativas
MAX_SALTOS = 5  # redirecionamentos por pedido
CABECALHOS_ACEITOS = frozenset({"accept", "accept-language", "content-type", "range", "x-tenant"})
_NUNCA = ("Cookie", "Origin", "Authorization", "Referer")
_SO_NA_ORIGEM = ("X-Tenant", "If-None-Match", "If-Modified-Since")


@dataclass(frozen=True)
class Resposta:
    status: int  # 200, 202, 206 ou 304
    texto: str
    cabecalhos: Mapping[str, str]

    def json(self) -> object:
        return json.loads(self.texto)


@dataclass(frozen=True)
class Validadores:
    etag: str | None
    last_modified: str | None


class LeitorValidadores(Protocol):
    def ler(self, url: str) -> Validadores | None: ...


class HttpEducado(Protocol):
    async def pedir(
        self,
        metodo: Literal["GET", "POST"],
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        cabecalhos: Mapping[str, str] | None = None,
        corpo_json: object | None = None,
        condicional: bool = False,
        teto_bytes: int | None = None,
    ) -> Resposta: ...

    def ler_em_fluxo(
        self, url: str, *, teto_bytes: int, cabecalhos: Mapping[str, str] | None = None
    ) -> AsyncGenerator[bytes]:
        """Gerador assíncrono. Quem sai do laço antes do fim usa `contextlib.aclosing`
        (`async with aclosing(http.ler_em_fluxo(...)) as fluxo:`), para a conexão fechar já;
        o validador da URL só é guardado quando o corpo é lido até o fim."""
        ...


class Bloqueio(Exception):
    """401 ou 403: a fonte falhou e o joBot não tenta contornar."""


class LimiteAtingido(Exception):
    """429/503 que não passou depois das esperas, ou Retry-After acima de 10 min."""


class Parou429(Exception):
    """Escopo com `para_no_429`: o primeiro 429 encerra sem esperar (o 503 segue a regra)."""


class OrcamentoGasto(Exception):
    """O escopo já fez `max_pedidos` pedidos."""


class RespostaGrande(Exception):
    """Corpo acima do teto de bytes."""


class ErroDeRede(Exception):
    """Rede ou 5xx depois das tentativas, redirecionamento ruim ou status inesperado."""

    def __init__(self, mensagem: str, status: int | None = None) -> None:
        super().__init__(mensagem)
        self.status = status  # status HTTP; None em falha de conexão, tempo ou salto ruim


class CabecalhoProibido(ValueError):
    """Cabeçalho fora da lista permitida (DR-51)."""


def _segundos_retry_after(valor: str | None, agora: datetime) -> float | None:
    if valor is None:
        return None
    valor = valor.strip()
    if valor.isdigit():
        return float(valor)
    try:
        data = parsedate_to_datetime(valor)
    except TypeError, ValueError:
        return None
    if data.tzinfo is None:
        data = data.replace(tzinfo=UTC)
    return max((data - agora).total_seconds(), 0.0)


def _texto(corpo: bytes, charset: str | None) -> str:
    try:
        codecs.lookup(charset or "utf-8")
    except LookupError:
        charset = None  # charset que o Python não conhece (ex.: utf8mb4) cai para utf-8
    return corpo.decode(charset or "utf-8", errors="replace")


_COMPATIVEL = ipaddress.IPv6Network("::/96")
_NAT64 = ipaddress.IPv6Network("64:ff9b::/96")


def _local(host: str) -> bool:
    """localhost ou IP não global (loopback, link-local, privado, CGNAT) (DR-19)."""
    host = host.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        return True
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:  # IPv4 curto, decimal ou hexa (127.1, 2130706433, 0x7f000001): o httpx não normaliza
            ip = ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            return False  # nome de host: não resolvemos DNS aqui
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip in _NAT64 or (ip in _COMPATIVEL and int(ip) > 1):  # "::" e "::1" ficam como estão
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)  # IPv4 embutido nos 32 bits de baixo
    return not ip.is_global  # loopback, link-local, privado, não especificado, CGNAT, reservado


async def _ler(resposta: httpx.Response, teto_bytes: int) -> AsyncIterator[bytes]:
    total = 0
    try:
        async for parte in resposta.aiter_bytes():
            total += len(parte)
            if total > teto_bytes:
                raise RespostaGrande(f"{resposta.request.url}: mais de {teto_bytes} bytes")
            yield parte
    except httpx.HTTPError as erro:
        raise ErroDeRede(f"{resposta.request.url}: {erro}") from erro


class ClienteEducado:
    def __init__(
        self,
        transporte: httpx.AsyncBaseTransport | None,
        relogio: Relogio,
        leitor: LeitorValidadores,
        versao: str,
    ) -> None:
        self._relogio = relogio
        self._leitor = leitor
        self._ua = f"joBot/{versao} (+https://github.com/fezarosa-dev/joBot)"
        self._ultimo: dict[str, datetime] = {}
        self._travas: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._cliente = httpx.AsyncClient(
            transport=transporte,
            headers={"User-Agent": self._ua},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,  # cada salto passa por _abrir: ritmo e orçamento
            event_hooks={"request": [self._conferir], "response": [self._conferir_salto]},
        )

    def escopo(
        self,
        *,
        espera_s: float = 1.0,
        condicional: bool = True,
        max_pedidos: int | None = None,
        para_no_429: bool = False,
    ) -> HttpDoEscopo:
        return HttpDoEscopo(self, espera_s, condicional, max_pedidos, para_no_429)

    async def fechar(self) -> None:
        await self._cliente.aclose()

    async def _conferir(self, pedido: httpx.Request) -> None:
        # Roda em todo pedido, inclusive em cada salto de redirecionamento.
        if pedido.url.scheme not in ("http", "https"):
            raise ErroDeRede(f"esquema não permitido: {pedido.url}")
        for nome in _NUNCA:  # o httpx guarda cookies e lê .netrc; nada disso sai
            pedido.headers.pop(nome, None)
        pedido.headers["User-Agent"] = self._ua

    async def _conferir_salto(self, resposta: httpx.Response) -> None:
        # Roda antes de o httpx montar o próximo salto: Location ruim não vira erro de rede.
        if not resposta.has_redirect_location:
            return
        try:
            destino = httpx.URL(resposta.headers["Location"])
        except httpx.InvalidURL as erro:
            raise ErroDeRede(f"{resposta.request.url}: Location inválido") from erro
        if not destino.is_relative_url and destino.scheme not in ("http", "https"):
            raise ErroDeRede(f"{resposta.request.url}: redirecionamento para {destino.scheme}")
        origem = resposta.request.url.host
        if destino.host and not _local(origem) and _local(destino.host):
            raise ErroDeRede(f"{resposta.request.url}: redirecionamento para host local")

    async def _enviar(self, pedido: httpx.Request, espera_s: float) -> httpx.Response:
        host = pedido.url.host
        async with self._travas[host]:
            ultimo = self._ultimo.get(host)
            if ultimo is not None:
                passou = max((self._relogio.agora() - ultimo).total_seconds(), 0.0)
                if passou < espera_s:  # relógio que voltou não prende além de espera_s
                    await self._relogio.dormir(espera_s - passou)
            try:
                return await self._cliente.send(pedido, stream=True)
            finally:
                self._ultimo[host] = self._relogio.agora()


class HttpDoEscopo:
    """Um escopo de coleta: ritmo, orçamento e validadores novos (só em memória)."""

    def __init__(
        self,
        dono: ClienteEducado,
        espera_s: float,
        condicional: bool,
        max_pedidos: int | None,
        para_no_429: bool,
    ) -> None:
        self._dono = dono
        self._espera_s = espera_s
        self._condicional = condicional
        self._max_pedidos = max_pedidos
        self._para_no_429 = para_no_429
        self.pedidos = 0
        self.validadores_novos: dict[str, Validadores] = {}

    async def pedir(
        self,
        metodo: Literal["GET", "POST"],
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        cabecalhos: Mapping[str, str] | None = None,
        corpo_json: object | None = None,
        condicional: bool = False,
        teto_bytes: int | None = None,
    ) -> Resposta:
        pedido = self._montar(metodo, url, params, cabecalhos, corpo_json)
        if metodo == "GET" and condicional and self._condicional:
            guardados = self._dono._leitor.ler(str(pedido.url))
            if guardados is not None and guardados.etag:
                pedido.headers["If-None-Match"] = guardados.etag
            if guardados is not None and guardados.last_modified:
                pedido.headers["If-Modified-Since"] = guardados.last_modified
        resposta = await self._abrir(pedido)
        try:
            corpo = b"".join([p async for p in _ler(resposta, teto_bytes or TETO_PADRAO)])
        finally:
            await resposta.aclose()
        if metodo == "GET":  # POST paginado pelo corpo colide na chave da URL
            self._guardar_validadores(str(pedido.url), resposta)
        return Resposta(
            resposta.status_code, _texto(corpo, resposta.charset_encoding), resposta.headers
        )

    async def ler_em_fluxo(
        self, url: str, *, teto_bytes: int, cabecalhos: Mapping[str, str] | None = None
    ) -> AsyncGenerator[bytes]:
        pedido = self._montar("GET", url, None, cabecalhos, None)
        resposta = await self._abrir(pedido)
        try:
            async for parte in _ler(resposta, teto_bytes):
                yield parte
        finally:
            await resposta.aclose()
        self._guardar_validadores(str(pedido.url), resposta)  # só com o corpo inteiro lido

    def _montar(
        self,
        metodo: str,
        url: str,
        params: Mapping[str, str] | None,
        cabecalhos: Mapping[str, str] | None,
        corpo_json: object | None,
    ) -> httpx.Request:
        extras = dict(cabecalhos or {})
        proibidos = [n for n in extras if n.lower() not in CABECALHOS_ACEITOS]
        if proibidos:
            raise CabecalhoProibido(f"cabeçalho não permitido: {', '.join(proibidos)}")
        try:
            return self._dono._cliente.build_request(
                metodo, url, params=params, headers=extras, json=corpo_json
            )
        except httpx.InvalidURL as erro:
            raise ErroDeRede(f"{url}: URL inválida") from erro

    async def _abrir(self, pedido: httpx.Request) -> httpx.Response:
        """Envia com ritmo, orçamento, tentativas e até 5 saltos; devolve 2xx ou 304 aberta."""
        relogio = self._dono._relogio
        original = pedido
        saltos = 0
        esperas_limite = iter(ESPERAS_LIMITE)
        esperas_erro = iter(ESPERAS_ERRO)
        while True:
            if self._max_pedidos is not None and self.pedidos >= self._max_pedidos:
                raise OrcamentoGasto(f"{self._max_pedidos} pedidos já feitos")
            self.pedidos += 1
            try:
                resposta = await self._dono._enviar(pedido, self._espera_s)
            except httpx.InvalidURL as erro:
                raise ErroDeRede(f"{pedido.url}: redirecionamento recusado: {erro}") from erro
            except httpx.TransportError as erro:
                espera = next(esperas_erro, None)
                if espera is None:
                    raise ErroDeRede(f"{pedido.url}: {erro}") from erro
                await relogio.dormir(espera)
                continue

            status = resposta.status_code
            if resposta.next_request is not None:
                await resposta.aclose()
                saltos += 1
                if saltos > MAX_SALTOS:
                    raise ErroDeRede(f"{original.url}: mais de {MAX_SALTOS} redirecionamentos")
                proximo = resposta.next_request
                if (proximo.url.scheme, proximo.url.netloc) != (
                    pedido.url.scheme,
                    pedido.url.netloc,
                ):
                    for nome in _SO_NA_ORIGEM:  # o httpx repassa; outra origem não recebe
                        proximo.headers.pop(nome, None)
                pedido = proximo
                continue
            if 200 <= status < 300 or status == 304:
                return resposta
            await resposta.aclose()
            if status in (401, 403):
                raise Bloqueio(f"{pedido.url}: HTTP {status}")
            if status in (429, 503):
                if self._para_no_429 and status == 429:
                    raise Parou429(f"{pedido.url}: HTTP {status}")
                pedida = _segundos_retry_after(resposta.headers.get("Retry-After"), relogio.agora())
                padrao = next(esperas_limite, None)
                if padrao is None:
                    raise LimiteAtingido(f"{pedido.url}: HTTP {status} depois das esperas")
                espera = padrao if pedida is None else pedida
                if espera > MAX_RETRY_AFTER_S:
                    raise LimiteAtingido(f"{pedido.url}: Retry-After de {espera:.0f} s")
                await relogio.dormir(espera)
                continue
            if status >= 500:
                espera = next(esperas_erro, None)
                if espera is None:
                    raise ErroDeRede(f"{pedido.url}: HTTP {status} depois das tentativas", status)
                await relogio.dormir(espera)
                continue
            raise ErroDeRede(f"{pedido.url}: HTTP {status}", status)

    def _guardar_validadores(self, url: str, resposta: httpx.Response) -> None:
        if resposta.status_code != 200:
            return
        etag = resposta.headers.get("ETag")
        last_modified = resposta.headers.get("Last-Modified")
        if etag or last_modified:
            self.validadores_novos[url] = Validadores(etag, last_modified)
