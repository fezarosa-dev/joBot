import json
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.captcha import (
    API,
    TETO_BYTES,
    Desafio,
    ErroCaptcha,
    Falha,
    mascarar,
    saldo,
    validar_chave,
)
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

CHAVE = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
URL = "https://exemplo.com.br/entrar"
SITEKEY = "6Lc_abcdefghij"
UA = "Mozilla/5.0 teste"
Responder = Callable[[httpx.Request], httpx.Response]


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


def _cliente(handler: Responder) -> tuple[ClienteEducado, RelogioFalso, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []

    def gravando(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return handler(pedido)

    relogio = RelogioFalso()
    prova: Relogio = relogio
    cli = ClienteEducado(httpx.MockTransport(gravando), prova, _SemValidadores(), "9.9.9")
    return cli, relogio, pedidos


def _json(corpo: object) -> Responder:
    return lambda _pedido: httpx.Response(200, json=corpo)


def _texto(corpo: str, status: int = 200) -> Responder:
    return lambda _pedido: httpx.Response(status, text=corpo)


def _desafio(**extra: Any) -> Desafio:
    campos: dict[str, Any] = {
        "tipo": "recaptcha_v2",
        "url": URL,
        "sitekey": SITEKEY,
        "user_agent": UA,
    }
    campos.update(extra)
    return Desafio(**campos)


# --- validar_chave e mascarar ------------------------------------------------------------------


def test_validar_chave() -> None:
    assert validar_chave("  " + CHAVE + "\n") == CHAVE
    assert validar_chave("a" * 16) == "a" * 16
    assert validar_chave("a" * 64) == "a" * 64
    for ruim in (
        "a" * 15,
        "a" * 65,
        "abcd efgh ijkl mnop",
        "abcdefghijklmnop!",
        "ãbcdefghijklmnopq",
        "abcdefgh\nijklmnop",
        "",
    ):
        with pytest.raises(ValueError) as exc:
            validar_chave(ruim)
        assert ruim.strip() not in str(exc.value) or ruim.strip() == ""


def test_mascarar() -> None:
    assert mascarar(CHAVE) == "•••• " + CHAVE[-4:]
    assert mascarar("abcdefghijkl") == "•••• ijkl"
    assert mascarar("abcdefghijk") == "••••"


# --- Desafio -----------------------------------------------------------------------------------


def test_desafio_recusa_o_que_esta_fora() -> None:
    recusados: list[dict[str, Any]] = [
        {"tipo": "hcaptcha"},
        {"url": "javascript:x"},
        {"url": "https://u:p@x.com/"},
        {"url": "https://u@x.com/"},
        {"url": "https:///sem-host"},
        {"sitekey": "a b"},
        {"sitekey": ""},
        {"user_agent": ""},
        {"user_agent": "a\nb"},
        {"user_agent": "x" * 513},
        {"acao": "a b"},
        {"acao": "x" * 101},
        {"tipo": "recaptcha_v3"},
        {"tipo": "recaptcha_v3", "min_score": 1.5},
        {"tipo": "recaptcha_v3", "min_score": 0.05},
        {"tipo": "recaptcha_v2", "min_score": 0.5},
        {"tipo": "recaptcha_v3", "min_score": 0.5, "invisivel": True},
        {"tipo": "turnstile", "invisivel": True},
    ]
    for extra in recusados:
        with pytest.raises(ValueError):
            _desafio(**extra)
    assert _desafio().tipo == "recaptcha_v2"
    assert _desafio(invisivel=True, acao="login/ok_1").invisivel is True
    assert _desafio(tipo="recaptcha_v3", min_score=0.7, acao="login").min_score == 0.7
    assert _desafio(tipo="turnstile").tipo == "turnstile"


def test_desafio_tira_query_e_fragmento() -> None:
    assert _desafio(url="https://x.com/entrar?email=a@b#f").url == "https://x.com/entrar"


def test_desafio_nao_mostra_userinfo_na_mensagem() -> None:
    with pytest.raises(ValueError) as exc:
        _desafio(url="https://usuario:senha-secreta@x.com/")
    assert "senha-secreta" not in str(exc.value)


# --- Falha -------------------------------------------------------------------------------------


def test_falha_tem_o_conjunto_fechado() -> None:
    assert {f.value for f in Falha} == {
        "chave_invalida",
        "sem_saldo",
        "sem_vaga",
        "nao_resolvivel",
        "ip_bloqueado",
        "conta_suspensa",
        "tempo_esgotado",
        "teto_diario",
        "outro",
    }
    assert str(ErroCaptcha(Falha.SEM_SALDO)) == "sem_saldo"


# --- saldo -------------------------------------------------------------------------------------


async def test_saldo_devolve_decimal() -> None:
    def handler(pedido: httpx.Request) -> httpx.Response:
        assert pedido.method == "POST"
        assert str(pedido.url) == API + "/getBalance"
        assert json.loads(pedido.content) == {"clientKey": CHAVE}
        assert "authorization" not in pedido.headers
        assert "cookie" not in pedido.headers
        return httpx.Response(200, json={"errorId": 0, "balance": 0.94})

    cli, _, pedidos = _cliente(handler)
    valor = await saldo(cli, CHAVE)
    assert valor == Decimal("0.94")
    assert type(valor) is Decimal
    assert len(pedidos) == 1


@pytest.mark.parametrize(
    ("codigo", "falha"),
    [
        (1, Falha.CHAVE_INVALIDA),
        (11, Falha.IP_BLOQUEADO),
        (21, Falha.IP_BLOQUEADO),
        (55, Falha.CONTA_SUSPENSA),
        (999, Falha.OUTRO),
    ],
)
async def test_saldo_erro_da_api_vira_a_falha(codigo: int, falha: Falha) -> None:
    cli, _, _ = _cliente(_json({"errorId": codigo, "errorCode": "ERROR_X"}))
    with pytest.raises(ErroCaptcha) as exc:
        await saldo(cli, CHAVE)
    assert exc.value.falha is falha


@pytest.mark.parametrize(
    "corpo",
    [
        "nao json",
        "[]",
        '{"balance": 1}',
        '{"errorId": 0}',
        '{"errorId": 0, "balance": "0.94"}',
        '{"errorId": 0, "balance": true}',
        '{"errorId": 0, "balance": NaN}',
        '{"errorId": 0, "balance": Infinity}',
        '{"errorId": 0, "balance": -1}',
        '{"errorId": true, "balance": 1}',
        "<html>manutencao</html>",
    ],
)
async def test_saldo_resposta_torta_vira_outro(corpo: str) -> None:
    cli, _, _ = _cliente(_texto(corpo))
    with pytest.raises(ErroCaptcha) as exc:
        await saldo(cli, CHAVE)
    assert exc.value.falha is Falha.OUTRO


async def test_saldo_429_vira_outro_sem_esperar() -> None:
    cli, relogio, pedidos = _cliente(_texto("devagar", 429))
    with pytest.raises(ErroCaptcha) as exc:
        await saldo(cli, CHAVE)
    assert exc.value.falha is Falha.OUTRO
    assert len(pedidos) == 1
    assert relogio.dormidas == []


async def test_resposta_acima_de_64_kib_vira_outro() -> None:
    cli, _, _ = _cliente(_texto("a" * (TETO_BYTES + 1)))
    with pytest.raises(ErroCaptcha) as exc:
        await saldo(cli, CHAVE)
    assert exc.value.falha is Falha.OUTRO


def _levanta_rede(pedido: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError(CHAVE)


@pytest.mark.parametrize(
    "handler",
    [
        _levanta_rede,
        _json({"errorId": 1, "errorCode": "ERROR_KEY_DOES_NOT_EXIST", "errorDescription": CHAVE}),
    ],
)
async def test_chave_nunca_aparece_nas_falhas(
    handler: Responder, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    cli, _, _ = _cliente(handler)
    with pytest.raises(ErroCaptcha) as exc:
        await saldo(cli, CHAVE)
    erro = exc.value
    assert CHAVE not in str(erro)
    assert CHAVE not in repr(erro)
    assert erro.__cause__ is None
    assert erro.__context__ is None or erro.__suppress_context__ is True
    assert CHAVE not in caplog.text
    assert caplog.records  # o log da falha existe (só sem a chave)
