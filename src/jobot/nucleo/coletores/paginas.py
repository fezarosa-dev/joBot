"""Páginas acompanhadas (desenho 8.8, DR-18, DR-19): endereço permitido e conferência.

Não é coletor de vagas (não tem `COLETOR`, o registro passa por cima). O texto da página é dado
de terceiro, nunca instrução: vira texto puro por `para_texto` (14.3) antes de qualquer uso.
"""

import difflib
import hashlib
from dataclasses import dataclass
from datetime import datetime

import httpx

from jobot.nucleo.http import HttpEducado, Resolvedor, conferir_dns, host_local
from jobot.nucleo.texto import para_texto

# Sufixos de rede de casa ou de empresa que nunca são página pública (DR-19).
_SUFIXOS_LOCAIS = (".local", ".localdomain", ".lan", ".home", ".internal", ".intranet", ".arpa")


@dataclass(frozen=True)
class Pagina:
    id: int
    url: str
    nome: str
    ativa: bool
    texto: str | None  # último texto lido; fica quando a leitura seguinte falha
    hash_texto: str | None
    verificada_em: datetime | None  # última leitura que deu certo
    mudou_em: datetime | None
    estado: str | None  # "ok", "falhou"; None antes da primeira leitura


@dataclass(frozen=True)
class Mudanca:
    texto: str
    hash_texto: str
    diferenca: str | None  # None na primeira leitura: não há versão anterior para comparar


def _nome_local(host: str) -> bool:
    host = host.lower().rstrip(".")
    if ":" in host:  # IPv6 literal: quem decide é `host_local`
        return False
    return "." not in host or host.endswith(_SUFIXOS_LOCAIS)


def endereco_permitido(url: str) -> bool:
    """Só http/https, sem usuário e senha, e nunca para host local ou de rede privada (DR-19).

    Lê a URL com o mesmo parser do pedido (`httpx.URL`), para a conferência ver o host que será
    pedido. Nome que resolve para IP local só se pega no DNS: `verificar` confere antes do pedido.
    """
    try:
        partes = httpx.URL(url)
    except httpx.InvalidURL, TypeError:
        return False
    host = partes.host
    if partes.scheme not in ("http", "https") or not host or partes.userinfo:
        return False
    return not (host_local(host) or _nome_local(host))


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


async def verificar(
    http: HttpEducado, pagina: Pagina, *, resolver: Resolvedor | None = None
) -> Mudanca | None:
    """Baixa a página e devolve o texto novo, ou `None` se o texto é o mesmo da última leitura.

    Endereço não permitido levanta `ValueError` sem pedido; falha de rede sobe como a exceção do
    `HttpEducado` (quem chama marca o estado). O salto para host local o cliente recusa.
    """
    if not endereco_permitido(pagina.url):
        raise ValueError(f"endereço não permitido: {pagina.url!r}")
    # nome que resolve para IP local é recusado antes do pedido; IP literal também passa por aqui:
    # o resolvedor o devolve igual, e não há parser próprio de IP neste módulo
    await conferir_dns(httpx.URL(pagina.url).host, resolver)
    resposta = await http.pedir("GET", pagina.url)
    # shortcut: lê tudo como HTML; página em PDF ou outro binário vira texto sem sentido (ainda
    # comparável). Ler o Content-Type se a tela de sites mostrar o texto.
    texto = para_texto(resposta.texto, "html")
    novo = _hash(texto)
    if novo == pagina.hash_texto:
        return None
    if pagina.texto is None:
        return Mudanca(texto, novo, None)
    linhas = difflib.unified_diff(
        pagina.texto.splitlines(), texto.splitlines(), "antes", "depois", lineterm=""
    )
    return Mudanca(texto, novo, "\n".join(linhas))
