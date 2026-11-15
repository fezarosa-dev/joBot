import json
import logging
import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo import captcha as modulo
from jobot.nucleo.captcha import (
    API,
    TETO_BYTES,
    Desafio,
    ErroCaptcha,
    Falha,
    Solucao,
    mascarar,
    resolver,
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


async def _dns_falso(host: str) -> list[str]:
    return ["93.184.215.14"]  # salto para nome: nunca o DNS de verdade


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
    cli = ClienteEducado(
        httpx.MockTransport(gravando), prova, _SemValidadores(), "9.9.9", resolver=_dns_falso
    )
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
        '{"errorId": 0, "balance": 1' + "0" * 400 + "}",
        '{"errorId": 0, "balance": 1e99999999999999999999}',
        '{"errorId": 0, "balance": 1e16}',
        "<html>manutencao</html>",
    ],
)
async def test_saldo_resposta_torta_vira_outro(corpo: str) -> None:
    cli, _, _ = _cliente(_texto(corpo))
    with pytest.raises(ErroCaptcha) as exc:
        await saldo(cli, CHAVE)
    assert exc.value.falha is Falha.OUTRO


async def test_saldo_zero_negativo_vira_zero_e_a_fronteira_de_1e15_passa() -> None:
    cli, _, _ = _cliente(_texto('{"errorId": 0, "balance": -0.0}'))
    zero = await saldo(cli, CHAVE)
    assert (zero, str(zero)) == (Decimal(0), "0")
    cli, _, _ = _cliente(_texto('{"errorId": 0, "balance": 1e15}'))
    assert await saldo(cli, CHAVE) == Decimal("1e15")


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


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [("ERROR_X", "errorCode='ERROR_X'"), ("x\nFORJADO", "errorCode='?'")],
)
async def test_codigo_de_erro_vai_ao_log_como_repr_e_so_se_for_do_formato(
    codigo: str, esperado: str, caplog: pytest.LogCaptureFixture
) -> None:
    cli, _, _ = _cliente(_json({"errorId": 1, "errorCode": codigo}))
    with pytest.raises(ErroCaptcha):
        await saldo(cli, CHAVE)
    assert esperado in caplog.text
    assert "FORJADO" not in caplog.text


# --- resolver ----------------------------------------------------------------------------------

Item = dict[str, Any] | httpx.Response | Responder


class Fila:
    """Transporte falso: uma fila de respostas por caminho (a última se repete)."""

    def __init__(self, criar: list[Item], consulta: list[Item] | None = None) -> None:
        self.filas = {"/createTask": criar, "/getTaskResult": consulta or []}
        self.corpos: dict[str, list[Any]] = {"/createTask": [], "/getTaskResult": []}

    def n(self, caminho: str) -> int:
        return len(self.corpos[caminho])

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        caminho = pedido.url.path
        self.corpos[caminho].append(json.loads(pedido.content))
        fila = self.filas[caminho]
        item = fila.pop(0) if len(fila) > 1 else fila[0]
        if isinstance(item, httpx.Response):
            return item
        if isinstance(item, dict):
            return httpx.Response(200, json=item)
        return item(pedido)


def _tarefa(fila: Fila) -> Any:
    corpos = fila.corpos["/createTask"]
    return corpos[0]["task"] if corpos else None


def _aberta(task_id: Any = 7) -> dict[str, Any]:
    return {"errorId": 0, "taskId": task_id}


def _pronta(solucao: Any = None, custo: Any = "0.00299") -> dict[str, Any]:
    corpo: dict[str, Any] = {"errorId": 0, "status": "ready", "cost": custo}
    corpo["solution"] = {"gRecaptchaResponse": "TOKEN"} if solucao is None else solucao
    return corpo


PROCESSANDO: dict[str, Any] = {"errorId": 0, "status": "processing"}


async def _resolver(
    fila: Responder,
    desafio: Desafio | None = None,
    relogio: RelogioFalso | None = None,
    dias: list[date] | None = None,
    liberado: bool = True,
) -> tuple[Solucao, RelogioFalso]:
    rel = relogio or RelogioFalso()
    prova: Relogio = rel
    cli = ClienteEducado(
        httpx.MockTransport(fila), prova, _SemValidadores(), "9.9.9", resolver=_dns_falso
    )
    visto = dias if dias is not None else []

    def reservar(dia: date) -> bool:
        visto.append(dia)
        return liberado

    solucao = await resolver(cli, CHAVE, desafio or _desafio(), rel, reservar=reservar)
    return solucao, rel


async def _falha(fila: Responder, **extra: Any) -> tuple[Falha, RelogioFalso]:
    rel = RelogioFalso()
    with pytest.raises(ErroCaptcha) as exc:
        await _resolver(fila, relogio=rel, **extra)
    return exc.value.falha, rel


@pytest.mark.parametrize("invisivel", [False, True])
async def test_resolver_recaptcha_v2(invisivel: bool) -> None:
    fila = Fila([_aberta()], [_pronta()])
    solucao, _ = await _resolver(fila, _desafio(invisivel=invisivel))
    assert fila.corpos["/createTask"] == [
        {
            "clientKey": CHAVE,
            "task": {
                "type": "RecaptchaV2TaskProxyless",
                "websiteURL": URL,
                "websiteKey": SITEKEY,
                "isInvisible": invisivel,
                "userAgent": UA,
            },
        }
    ]
    assert fila.corpos["/getTaskResult"] == [{"clientKey": CHAVE, "taskId": 7}]
    assert solucao == Solucao("TOKEN", Decimal("0.00299"), None, 7)


async def test_resolver_recaptcha_v3() -> None:
    fila = Fila([_aberta()], [_pronta()])
    desafio = _desafio(tipo="recaptcha_v3", min_score=0.7, acao="login")
    solucao, _ = await _resolver(fila, desafio)
    assert _tarefa(fila) == {
        "type": "RecaptchaV3TaskProxyless",
        "websiteURL": URL,
        "websiteKey": SITEKEY,
        "minScore": 0.7,
        "pageAction": "login",
    }
    assert solucao.token == "TOKEN"
    sem_acao = Fila([_aberta()], [_pronta()])
    await _resolver(sem_acao, _desafio(tipo="recaptcha_v3", min_score=0.7))
    assert "pageAction" not in (_tarefa(sem_acao) or {"pageAction": 1})


async def test_resolver_turnstile() -> None:
    fila = Fila([_aberta()], [_pronta({"token": "T", "userAgent": "UA2"})])
    solucao, _ = await _resolver(fila, _desafio(tipo="turnstile"))
    assert _tarefa(fila) == {
        "type": "TurnstileTaskProxyless",
        "websiteURL": URL,
        "websiteKey": SITEKEY,
    }
    assert (solucao.token, solucao.user_agent) == ("T", "UA2")
    com_acao = Fila([_aberta()], [_pronta({"token": "T"})])
    solucao, _ = await _resolver(com_acao, _desafio(tipo="turnstile", acao="entrar"))
    assert (_tarefa(com_acao) or {}).get("action") == "entrar"
    assert solucao.user_agent is None


async def test_consulta_espera_5_s_entre_pedidos() -> None:
    fila = Fila([_aberta()], [PROCESSANDO, PROCESSANDO, _pronta()])
    _, rel = await _resolver(fila)
    assert rel.dormidas == [5.0, 5.0, 5.0]
    assert (fila.n("/createTask"), fila.n("/getTaskResult")) == (1, 3)


async def test_passou_de_180_s_e_tempo_esgotado() -> None:
    fila = Fila([_aberta()], [PROCESSANDO])
    rel = RelogioFalso()
    inicio = rel.agora()
    with pytest.raises(ErroCaptcha) as exc:
        await _resolver(fila, relogio=rel)
    assert exc.value.falha is Falha.TEMPO_ESGOTADO
    assert fila.n("/getTaskResult") == 36
    assert rel.agora() - inicio == timedelta(seconds=180)


@pytest.mark.parametrize(
    ("codigo", "falha"),
    [
        (1, Falha.CHAVE_INVALIDA),
        (10, Falha.SEM_SALDO),
        (11, Falha.IP_BLOQUEADO),
        (12, Falha.NAO_RESOLVIVEL),
        (21, Falha.IP_BLOQUEADO),
        (55, Falha.CONTA_SUSPENSA),
        (31, Falha.OUTRO),
        (110, Falha.OUTRO),
        (999, Falha.OUTRO),
    ],
)
async def test_cada_codigo_vira_a_falha(codigo: int, falha: Falha) -> None:
    fila = Fila([{"errorId": codigo, "errorCode": "ERROR_X"}])
    obtida, _ = await _falha(fila)
    assert obtida is falha
    assert fila.n("/createTask") == 1


async def test_sem_vaga_tenta_de_novo() -> None:
    fila = Fila([{"errorId": 2, "errorCode": "ERROR_NO_SLOT_AVAILABLE"}, _aberta()], [_pronta()])
    dias: list[date] = []
    solucao, _ = await _resolver(fila, dias=dias)
    assert solucao.token == "TOKEN"
    assert fila.n("/createTask") == 2
    assert len(dias) == 1


async def test_sem_vaga_ate_o_fim_e_sem_vaga() -> None:
    fila = Fila([{"errorId": 2, "errorCode": "ERROR_NO_SLOT_AVAILABLE"}])
    obtida, rel = await _falha(fila)
    assert obtida is Falha.SEM_VAGA
    assert fila.n("/createTask") > 1
    assert sum(rel.dormidas) <= 185


async def test_nao_resolvivel_na_consulta() -> None:
    fila = Fila([_aberta()], [{"errorId": 12, "errorCode": "ERROR_CAPTCHA_UNSOLVABLE"}])
    obtida, _ = await _falha(fila)
    assert obtida is Falha.NAO_RESOLVIVEL


@pytest.mark.parametrize(
    "consulta",
    [
        {"errorId": 0, "status": "esquisito"},
        {"errorId": 0, "status": "ready"},
        _pronta({"gRecaptchaResponse": ""}),
        _pronta({"gRecaptchaResponse": 123}),
        _pronta({"token": "no-campo-errado"}),
        _pronta("texto"),
        httpx.Response(200, text="nao json"),
    ],
)
async def test_resposta_torta_nao_e_sucesso_na_consulta(consulta: Item) -> None:
    obtida, _ = await _falha(Fila([_aberta()], [consulta]))
    assert obtida is Falha.OUTRO


@pytest.mark.parametrize("task_id", [True, 0, "7", None, -3, 7.5])
async def test_task_id_torto_no_createtask_e_outro(task_id: Any) -> None:
    fila = Fila([{"errorId": 0, "taskId": task_id}], [_pronta()])
    obtida, _ = await _falha(fila)
    assert obtida is Falha.OUTRO
    assert fila.n("/getTaskResult") == 0


@pytest.mark.parametrize("item", [_levanta_rede, httpx.Response(500, text="erro")])
async def test_erro_de_rede_no_createtask_nao_abre_segunda_tarefa(item: Item) -> None:
    fila = Fila([item])
    obtida, _ = await _falha(fila)
    assert obtida is Falha.OUTRO
    assert fila.n("/createTask") == 1


async def test_teto_recusa_antes_do_pedido() -> None:
    fila = Fila([_aberta()], [_pronta()])
    obtida, _ = await _falha(fila, liberado=False)
    assert obtida is Falha.TETO_DIARIO
    assert (fila.n("/createTask"), fila.n("/getTaskResult")) == (0, 0)


@pytest.fixture
def fuso_sao_paulo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


async def test_reserva_usa_o_dia_local(fuso_sao_paulo: None) -> None:
    dias: list[date] = []
    relogio = RelogioFalso(datetime(2026, 11, 16, 2, 30, tzinfo=UTC))  # 23h30 do dia 15 em Brasília
    await _resolver(Fila([_aberta()], [_pronta()]), relogio=relogio, dias=dias)
    assert dias == [date(2026, 11, 15)]


async def test_custo_vai_ao_log_sem_a_chave(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    await _resolver(Fila([_aberta()], [_pronta({"token": "TOKEN"})]), _desafio(tipo="turnstile"))
    avisos = [r.getMessage() for r in caplog.records if r.name == "jobot.nucleo.captcha"]
    assert any("0.00299" in a and "turnstile" in a for a in avisos)
    assert CHAVE not in caplog.text
    assert "TOKEN" not in caplog.text


async def test_custo_torto_fica_none() -> None:
    solucao, _ = await _resolver(Fila([_aberta()], [_pronta(custo="abc")]))
    assert solucao.custo is None
    assert solucao.token == "TOKEN"


@pytest.mark.parametrize("etapa", ["createTask", "getTaskResult"])
async def test_chave_nunca_nas_falhas_do_resolver(
    etapa: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    if etapa == "createTask":
        fila = Fila([_levanta_rede])
    else:
        fila = Fila([_aberta()], [_levanta_rede])
    with pytest.raises(ErroCaptcha) as exc:
        await _resolver(fila)
    erro = exc.value
    assert CHAVE not in str(erro)
    assert CHAVE not in repr(erro)
    assert erro.__cause__ is None
    assert erro.__suppress_context__ is True
    assert CHAVE not in caplog.text


async def test_503_com_retry_after_longo_nao_passa_do_prazo() -> None:
    resposta = httpx.Response(503, headers={"Retry-After": "600"})
    obtida, rel = await _falha(Fila([_aberta()], [resposta]))
    assert obtida in {Falha.TEMPO_ESGOTADO, Falha.OUTRO}
    assert max(rel.dormidas, default=0.0) < 180


async def test_consulta_tem_teto_de_pedidos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo, "MAX_CONSULTAS", 3)
    fila = Fila([_aberta()], [PROCESSANDO])
    obtida, _ = await _falha(fila)
    assert obtida is Falha.OUTRO
    assert fila.n("/getTaskResult") == 3


async def test_saldo_503_com_retry_after_longo_vira_outro_sem_dormir() -> None:
    cli, rel, _ = _cliente(lambda _p: httpx.Response(503, headers={"Retry-After": "600"}))
    with pytest.raises(ErroCaptcha) as exc:
        await saldo(cli, CHAVE)
    assert exc.value.falha is Falha.OUTRO
    assert rel.dormidas == []


# O caso createTask já é barrado pelo max_pedidos=1 (o salto estoura o orçamento); quem prova o
# seguir_saltos=False são os casos saldo e getTaskResult.
@pytest.mark.parametrize("etapa", ["saldo", "createTask", "getTaskResult"])
async def test_redirecionamento_nao_reenvia_o_corpo_com_a_chave(etapa: str) -> None:
    pedidos: list[httpx.Request] = []

    def handler(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        if pedido.url.host != "api.2captcha.com":  # quem recebeu o corpo com a chave
            return httpx.Response(200, json=_pronta() | {"taskId": 7, "balance": 1})
        if pedido.url.path != {"saldo": "/getBalance"}.get(etapa, "/" + etapa):
            return httpx.Response(200, json=_aberta())
        return httpx.Response(307, headers={"Location": "https://outro.example/x"})

    cli, _, _ = _cliente(handler)
    with pytest.raises(ErroCaptcha) as exc:
        if etapa == "saldo":
            await saldo(cli, CHAVE)
        else:
            await resolver(cli, CHAVE, _desafio(), RelogioFalso(), reservar=lambda _d: True)
    assert exc.value.falha is Falha.OUTRO
    assert all(p.url.host == "api.2captcha.com" for p in pedidos)
    assert CHAVE not in str(exc.value)


async def test_createtask_com_retry_after_longo_nao_dorme_nem_repete() -> None:
    fila = Fila([httpx.Response(503, headers={"Retry-After": "600"})])
    obtida, rel = await _falha(fila)
    assert obtida is Falha.OUTRO
    assert rel.dormidas == []
    assert fila.n("/createTask") == 1
