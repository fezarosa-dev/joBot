"""Cliente da API do 2Captcha (ADR 0022): só a navegação com login da fase 2 usa.

A chave chega como texto e nunca sai daqui: não vai a log, a mensagem de erro nem a repr."""

import asyncio
import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, NoReturn
from urllib.parse import urlsplit, urlunsplit

from jobot.nucleo.http import (
    Bloqueio,
    CabecalhoProibido,
    ClienteEducado,
    ErroDeRede,
    HttpEducado,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    Resposta,
    RespostaGrande,
)
from jobot.nucleo.relogio import Relogio

_LOG = logging.getLogger(__name__)

API = "https://api.2captcha.com"
ESPERA_S = 5.0
PRAZO_S = 180.0
TETO_BYTES = 64 * 1024
MARGEM_S = 15.0  # folga do teto real, por fora do prazo contado pelo relógio injetado
TETO_ESPERA_S = 30.0
MAX_CONSULTAS = 40
MAX_EXPOENTE_SALDO = 15  # saldo acima de 10**15 é resposta torta e quebraria a formatação

_CHAVE = re.compile(r"[A-Za-z0-9]{16,64}", re.ASCII)
_SITEKEY = re.compile(r"[A-Za-z0-9_-]{1,200}", re.ASCII)
_ACAO = re.compile(r"[A-Za-z0-9_/]{1,100}", re.ASCII)
_CODIGO = re.compile(r"[A-Z_]{1,64}", re.ASCII)
_ERROS_DE_PEDIDO = (
    ErroDeRede,
    Bloqueio,
    LimiteAtingido,
    Parou429,
    OrcamentoGasto,
    RespostaGrande,
    CabecalhoProibido,
)


class Falha(StrEnum):
    CHAVE_INVALIDA = "chave_invalida"
    SEM_SALDO = "sem_saldo"
    SEM_VAGA = "sem_vaga"
    NAO_RESOLVIVEL = "nao_resolvivel"
    IP_BLOQUEADO = "ip_bloqueado"
    CONTA_SUSPENSA = "conta_suspensa"
    TEMPO_ESGOTADO = "tempo_esgotado"
    TETO_DIARIO = "teto_diario"
    OUTRO = "outro"


class ErroCaptcha(Exception):
    """Falha do conjunto fechado; `str(erro)` é o valor da `Falha` (o texto vem do catálogo)."""

    def __init__(self, falha: Falha) -> None:
        super().__init__(falha.value)
        self.falha = falha


TipoDesafio = Literal["recaptcha_v2", "recaptcha_v3", "turnstile"]
_TIPOS = frozenset({"recaptcha_v2", "recaptcha_v3", "turnstile"})


@dataclass(frozen=True)
class Desafio:
    tipo: TipoDesafio
    url: str
    sitekey: str
    user_agent: str
    invisivel: bool = False
    acao: str | None = None
    min_score: float | None = None

    def __post_init__(self) -> None:
        if self.tipo not in _TIPOS:
            raise ValueError("tipo de desafio desconhecido")
        try:
            partes = urlsplit(self.url)
        except ValueError:
            raise ValueError("endereço da página inválido") from None
        if (
            partes.scheme not in ("http", "https")
            or not partes.hostname
            or "@" in partes.netloc  # userinfo (usuário:senha@) não vai ao 2Captcha
            or not self.url.isprintable()
            or " " in self.url
        ):
            raise ValueError("endereço da página inválido")
        # Query e fragmento podem levar e-mail ou token: só o endereço da página vai.
        object.__setattr__(
            self, "url", urlunsplit((partes.scheme, partes.netloc, partes.path, "", ""))
        )
        if not _SITEKEY.fullmatch(self.sitekey):
            raise ValueError("sitekey fora do formato")
        if not self.user_agent or len(self.user_agent) > 512 or not self.user_agent.isprintable():
            raise ValueError("user agent fora do formato")
        if self.acao is not None and not _ACAO.fullmatch(self.acao):
            raise ValueError("ação fora do formato")
        if self.invisivel and self.tipo != "recaptcha_v2":
            raise ValueError("invisível só vale no reCAPTCHA v2")
        if self.tipo == "recaptcha_v3":
            ok = (
                isinstance(self.min_score, int | float)
                and not isinstance(self.min_score, bool)
                and 0.1 <= self.min_score <= 0.9
            )
            if not ok:
                raise ValueError("min_score do reCAPTCHA v3 fora de 0,1 a 0,9")
        elif self.min_score is not None:
            raise ValueError("min_score só vale no reCAPTCHA v3")


@dataclass(frozen=True)
class Solucao:
    token: str
    custo: Decimal | None
    user_agent: str | None
    id_tarefa: int


def validar_chave(texto: str) -> str:
    """Recorta e confere o formato; a mensagem nunca traz o texto recebido."""
    chave = texto.strip()
    if not _CHAVE.fullmatch(chave):
        raise ValueError("chave fora do formato")
    return chave


def mascarar(chave: str) -> str:
    return f"•••• {chave[-4:]}" if len(chave) >= 12 else "••••"


def _falha_do_erro(error_id: int) -> Falha:
    return {
        1: Falha.CHAVE_INVALIDA,
        2: Falha.SEM_VAGA,
        10: Falha.SEM_SALDO,
        11: Falha.IP_BLOQUEADO,
        21: Falha.IP_BLOQUEADO,
        12: Falha.NAO_RESOLVIVEL,
        55: Falha.CONTA_SUSPENSA,
    }.get(error_id, Falha.OUTRO)


def _constante_proibida(nome: str) -> NoReturn:
    raise ValueError(f"constante JSON proibida: {nome}")  # NaN e Infinity


def _ler_resposta(resposta: Resposta) -> Mapping[str, object]:
    """JSON da resposta como dicionário, com `errorId` 0; erro da API vira `ErroCaptcha`."""
    try:
        corpo = json.loads(resposta.texto, parse_float=Decimal, parse_constant=_constante_proibida)
    except ValueError, RecursionError, ArithmeticError:  # ArithmeticError: expoente enorme
        raise ErroCaptcha(Falha.OUTRO) from None
    if not isinstance(corpo, dict):
        raise ErroCaptcha(Falha.OUTRO)
    error_id = corpo.get("errorId")
    if not isinstance(error_id, int) or isinstance(error_id, bool):
        raise ErroCaptcha(Falha.OUTRO)
    if error_id != 0:
        codigo = corpo.get("errorCode")
        if not isinstance(codigo, str) or not _CODIGO.fullmatch(codigo):
            codigo = "?"
        _LOG.warning("2captcha: errorId=%d errorCode=%r", error_id, codigo)
        raise ErroCaptcha(_falha_do_erro(error_id))
    return corpo


async def _post(http: HttpEducado, caminho: str, corpo: object) -> Mapping[str, object]:
    """POST em JSON; falha de rede, bloqueio, 429, orçamento ou corpo grande vira `OUTRO`."""
    try:
        resposta = await http.pedir("POST", API + caminho, corpo_json=corpo, teto_bytes=TETO_BYTES)
    except _ERROS_DE_PEDIDO as erro:
        _LOG.warning("2captcha: %s", type(erro).__name__)
        raise ErroCaptcha(Falha.OUTRO) from None
    return _ler_resposta(resposta)


async def saldo(cliente: ClienteEducado, chave: str) -> Decimal:
    http = cliente.escopo(
        espera_s=ESPERA_S,
        condicional=False,
        para_no_429=True,
        teto_espera_s=TETO_ESPERA_S,
        seguir_saltos=False,  # o corpo leva a chave: 307/308 não a reenvia a outro endereço
    )
    corpo = await _post(http, "/getBalance", {"clientKey": chave})
    valor = corpo.get("balance")
    if not isinstance(valor, Decimal | int) or isinstance(valor, bool):
        raise ErroCaptcha(Falha.OUTRO)
    total = Decimal(valor)  # `math.isfinite` estoura em int enorme; Decimal compara sem converter
    if not total.is_finite() or total < 0 or total.adjusted() > MAX_EXPOENTE_SALDO:
        raise ErroCaptcha(Falha.OUTRO)
    return total or Decimal(0)  # -0.0 vira 0


_CAMPO_DO_TOKEN = {
    "recaptcha_v2": "gRecaptchaResponse",
    "recaptcha_v3": "gRecaptchaResponse",
    "turnstile": "token",
}
_CUSTO = re.compile(r"[0-9]{1,6}(\.[0-9]{1,8})?", re.ASCII)


def _tarefa(desafio: Desafio) -> dict[str, object]:
    base: dict[str, object] = {"websiteURL": desafio.url, "websiteKey": desafio.sitekey}
    if desafio.tipo == "recaptcha_v2":
        return {
            "type": "RecaptchaV2TaskProxyless",
            **base,
            "isInvisible": desafio.invisivel,
            "userAgent": desafio.user_agent,
        }
    if desafio.tipo == "recaptcha_v3":
        extra: dict[str, object] = {"minScore": desafio.min_score}
        if desafio.acao is not None:
            extra["pageAction"] = desafio.acao
        return {"type": "RecaptchaV3TaskProxyless", **base, **extra}
    extra = {} if desafio.acao is None else {"action": desafio.acao}
    return {"type": "TurnstileTaskProxyless", **base, **extra}


def _id_da_tarefa(corpo: Mapping[str, object]) -> int:
    valor = corpo.get("taskId")
    if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
        raise ErroCaptcha(Falha.OUTRO)
    return valor


def _solucao(corpo: Mapping[str, object], desafio: Desafio, id_tarefa: int) -> Solucao:
    pronta = corpo.get("solution")
    if not isinstance(pronta, dict):
        raise ErroCaptcha(Falha.OUTRO)
    token = pronta.get(_CAMPO_DO_TOKEN[desafio.tipo])
    if not isinstance(token, str) or not token:
        raise ErroCaptcha(Falha.OUTRO)
    custo_txt = corpo.get("cost")
    custo = (
        Decimal(custo_txt)
        if isinstance(custo_txt, str) and _CUSTO.fullmatch(custo_txt)
        else None  # custo fora do formato não derruba uma resolução que deu certo
    )
    agente = pronta.get("userAgent") if desafio.tipo == "turnstile" else None
    return Solucao(token, custo, agente if isinstance(agente, str) else None, id_tarefa)


async def _abrir_tarefa(
    cliente: ClienteEducado, chave: str, desafio: Desafio, relogio: Relogio, inicio: datetime
) -> int:
    """`createTask` uma vez só por tarefa: `max_pedidos=1` impede a repetição automática de rede
    ou 5xx de abrir uma segunda tarefa (e cobrar duas vezes). Sem vaga tenta de novo até o prazo."""
    pedido = {"clientKey": chave, "task": _tarefa(desafio)}
    while True:
        http = cliente.escopo(
            espera_s=ESPERA_S,
            condicional=False,
            max_pedidos=1,
            para_no_429=True,
            teto_espera_s=TETO_ESPERA_S,
            seguir_saltos=False,
        )
        try:
            return _id_da_tarefa(await _post(http, "/createTask", pedido))
        except ErroCaptcha as erro:
            if (
                erro.falha is not Falha.SEM_VAGA
                or (relogio.agora() - inicio).total_seconds() >= PRAZO_S
            ):
                raise


async def _consultar(
    cliente: ClienteEducado,
    chave: str,
    desafio: Desafio,
    relogio: Relogio,
    inicio: datetime,
    id_tarefa: int,
) -> Solucao:
    http = cliente.escopo(
        espera_s=ESPERA_S,
        condicional=False,
        max_pedidos=MAX_CONSULTAS,
        para_no_429=True,
        teto_espera_s=TETO_ESPERA_S,
        seguir_saltos=False,
    )
    while True:
        if (relogio.agora() - inicio).total_seconds() >= PRAZO_S:
            raise ErroCaptcha(Falha.TEMPO_ESGOTADO)
        corpo = await _post(http, "/getTaskResult", {"clientKey": chave, "taskId": id_tarefa})
        estado = corpo.get("status")
        if estado == "ready":
            return _solucao(corpo, desafio, id_tarefa)
        if estado != "processing":
            raise ErroCaptcha(Falha.OUTRO)


async def resolver(
    cliente: ClienteEducado,
    chave: str,
    desafio: Desafio,
    relogio: Relogio,
    *,
    reservar: Callable[[date], bool],
) -> Solucao:
    """Abre a tarefa e consulta até `ready`; falha do conjunto fechado vira `ErroCaptcha`.

    `reservar` conta a resolução no teto do dia (dia local) antes de qualquer pedido. O prazo de
    180 s conta pelo relógio injetado; o `asyncio.timeout` por fora só corta um pedido preso."""
    inicio = relogio.agora()
    if not reservar(inicio.astimezone().date()):
        raise ErroCaptcha(Falha.TETO_DIARIO)
    try:
        async with asyncio.timeout(PRAZO_S + MARGEM_S):
            id_tarefa = await _abrir_tarefa(cliente, chave, desafio, relogio, inicio)
            solucao = await _consultar(cliente, chave, desafio, relogio, inicio, id_tarefa)
    except TimeoutError:
        raise ErroCaptcha(Falha.TEMPO_ESGOTADO) from None
    _LOG.info(
        "2captcha: %s resolvido em %.0f s, custo %s",
        desafio.tipo,
        (relogio.agora() - inicio).total_seconds(),
        solucao.custo,
    )
    return solucao
