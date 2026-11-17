"""Cliente da API da Anthropic (T406, desenho 6 da fase 4; escolhas na D192). Só transporte falso
(`httpx.MockTransport`): o CI não tem chave nem rede."""

import json
import logging
from collections.abc import Callable, Iterator

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field

from jobot.nucleo.ia.anthropic import ClienteAnthropic
from jobot.nucleo.ia.contrato import Falha, Mensagem, Pedido, limites
from jobot.nucleo.ia.esquema import esquema_para

CHAVE = "sk-ant-api-segredo-de-teste-0123456789"
URL = "https://api.anthropic.com/v1/messages"


class Saida(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pede: list[str] = Field(max_length=3)
    resumo: str = Field(max_length=5000)


def _pedido(modelo: str = "claude-haiku-5-5") -> Pedido:
    return Pedido(
        tarefa="encaixe",
        modelo=modelo,
        mensagens=(Mensagem("system", "instruções nossas"), Mensagem("user", "<vaga>texto</vaga>")),
        esquema=Saida,
        max_tokens=1024,
        prazo_s=60.0,
        versao=3,
    )


def _resposta(conteudo: list[object], stop: str = "tool_use") -> httpx.Response:
    return httpx.Response(200, json={"type": "message", "content": conteudo, "stop_reason": stop})


def _uso(entrada: object) -> dict[str, object]:
    return {"type": "tool_use", "id": "toolu_1", "name": "responder", "input": entrada}


BOA = {"pede": ["Python"], "resumo": "ok"}


class _Fluxo(httpx.SyncByteStream):
    """Corpo em blocos que pode estourar no meio; lembra se a conexão foi fechada."""

    def __init__(self, blocos: list[bytes], erro: Exception | None = None) -> None:
        self.blocos = blocos
        self.erro = erro
        self.fechado = False

    def __iter__(self) -> Iterator[bytes]:
        yield from self.blocos
        if self.erro is not None:
            raise self.erro

    def close(self) -> None:
        self.fechado = True


def _cliente(
    responder: Callable[[httpx.Request], httpx.Response], chave: str = CHAVE, **kwargs: object
) -> tuple[ClienteAnthropic, list[httpx.Request]]:
    vistos: list[httpx.Request] = []

    def transporte(pedido: httpx.Request) -> httpx.Response:
        vistos.append(pedido)
        return responder(pedido)

    http = httpx.Client(transport=httpx.MockTransport(transporte), **kwargs)  # type: ignore[arg-type]
    return ClienteAnthropic(chave, http), vistos


def _motivo(cliente: ClienteAnthropic, pedido: Pedido | None = None) -> str:
    with pytest.raises(Falha) as erro:
        cliente.pedir(pedido or _pedido())
    return erro.value.motivo


def test_corpo_com_ferramenta_responder_forcada_no_haiku() -> None:
    cliente, vistos = _cliente(lambda _: _resposta([_uso(BOA)]))
    resposta = cliente.pedir(_pedido())
    assert len(vistos) == 1
    enviado = vistos[0]
    assert (enviado.method, str(enviado.url)) == ("POST", URL)
    assert enviado.headers["authorization"] == f"Bearer {CHAVE}"
    assert enviado.headers["anthropic-version"] == "2026-10-21"
    corpo = json.loads(enviado.content)
    assert corpo["model"] == "claude-haiku-5-5"
    assert corpo["max_tokens"] == 1024
    assert corpo["system"] == "instruções nossas"
    assert corpo["messages"] == [{"role": "user", "content": "<vaga>texto</vaga>"}]
    [ferramenta] = corpo["tools"]
    assert ferramenta["name"] == "responder"
    assert ferramenta["input_schema"] == esquema_para("anthropic", Saida)
    assert ferramenta["input_schema"]["properties"]["resumo"]["maxLength"] == 5000
    assert corpo["tool_choice"] == {"type": "tool", "name": "responder"}
    # sem amostragem: a versão 2026-10-21 recusa `temperature`, `top_p` e `top_k` em todo modelo
    assert set(corpo) == {"model", "max_tokens", "system", "messages", "tools", "tool_choice"}
    assert (resposta.dados, resposta.backend, resposta.modelo, resposta.versao) == (
        BOA,
        "anthropic",
        "claude-haiku-5-5",
        3,
    )


def test_sonnet_usa_auto_sem_pensar_antes() -> None:
    # o Sonnet 5.5 devolve 400 para `tool_choice` forçado (D192.1)
    cliente, vistos = _cliente(lambda _: _resposta([_uso(BOA)]))
    assert cliente.pedir(_pedido("claude-sonnet-5-5")).dados == BOA
    corpo = json.loads(vistos[0].content)
    assert corpo["tool_choice"] == {"type": "auto"}
    assert corpo["thinking"] == {"type": "between_tools"}
    assert [f["name"] for f in corpo["tools"]] == ["responder"]
    keys = {"model", "max_tokens", "system", "messages", "tools", "tool_choice", "thinking"}
    assert set(corpo) == keys


def test_le_o_input_do_tool_use_entre_outros_blocos() -> None:
    blocos = [
        {"type": "thinking", "thinking": "", "signature": "x"},
        {"type": "text", "text": "vou responder"},
        {"type": "tool_use", "id": "toolu_0", "name": "outra", "input": {"pede": []}},
        _uso(BOA),
    ]
    cliente, _ = _cliente(lambda _: _resposta(blocos))
    assert cliente.pedir(_pedido()).dados == BOA


@pytest.mark.parametrize(
    "blocos",
    [
        [{"type": "text", "text": "não vou usar a ferramenta"}],
        [],
        [{"type": "tool_use", "id": "toolu_0", "name": "outra", "input": BOA}],
    ],
)
def test_sem_bloco_responder_e_recusa(blocos: list[object]) -> None:
    cliente, vistos = _cliente(lambda _: _resposta(blocos, stop="refusal"))
    assert _motivo(cliente) == "recusa"
    assert len(vistos) == 1


@pytest.mark.parametrize(
    ("status", "motivo"),
    [
        (400, "esquema_recusado"),
        (401, "chave_recusada"),
        (402, "limite"),
        (403, "chave_recusada"),
        (404, "modelo_ausente"),
        (413, "contexto"),
        (429, "limite"),
        (500, "servico_fora"),
        (529, "servico_fora"),
        (302, "servico_fora"),
    ],
)
def test_codigos_http(status: int, motivo: str) -> None:
    corpo = {"type": "error", "error": {"type": "x", "message": f"eco {CHAVE}"}}
    cliente, _ = _cliente(lambda _: httpx.Response(status, json=corpo))
    with pytest.raises(Falha) as erro:
        cliente.pedir(_pedido())
    assert erro.value.motivo == motivo
    assert erro.value.args == (motivo,)


def test_sem_conexao_e_sem_rede() -> None:
    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota", request=pedido)

    cliente, vistos = _cliente(cai)
    assert _motivo(cliente) == "sem_rede"
    assert len(vistos) == 1


def test_prazo_vira_timeout_e_estouro_fecha_a_conexao() -> None:
    fluxo = _Fluxo([b'{"content": ['], httpx.ReadTimeout("parou"))
    cliente, vistos = _cliente(lambda _: httpx.Response(200, stream=fluxo))
    assert _motivo(cliente) == "tempo_esgotado"
    assert fluxo.fechado
    prazo = vistos[0].extensions["timeout"]
    assert prazo == {"connect": 60.0, "read": 60.0, "write": 60.0, "pool": 60.0}


def test_prazo_antes_da_resposta_e_tempo_esgotado() -> None:
    def demora(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("parou", request=pedido)

    cliente, _ = _cliente(demora)
    assert _motivo(cliente) == "tempo_esgotado"


def test_resposta_acima_do_teto_e_formato_e_fecha() -> None:
    teto = limites()["resposta_max_bytes"]
    assert teto == 1048576
    fluxo = _Fluxo([b" " * teto, b" "])
    cliente, _ = _cliente(lambda _: httpx.Response(200, stream=fluxo))
    assert _motivo(cliente) == "formato"
    assert fluxo.fechado


def test_resposta_no_teto_passa() -> None:
    teto = limites()["resposta_max_bytes"]
    texto = json.dumps({"content": [_uso(BOA)]}).encode()
    fluxo = _Fluxo([texto, b" " * (teto - len(texto))])
    cliente, _ = _cliente(lambda _: httpx.Response(200, stream=fluxo))
    assert cliente.pedir(_pedido()).dados == BOA


@pytest.mark.parametrize(
    "resposta",
    [
        _resposta([_uso({**BOA, "a_mais": 1})]),
        _resposta([_uso({"pede": ["a", "b", "c", "d"], "resumo": "ok"})]),
        _resposta([_uso("texto solto")]),
        httpx.Response(200, content=b"isto nao e json"),
        httpx.Response(200, json=["lista"]),
        httpx.Response(200, json={"content": "texto"}),
    ],
)
def test_fora_do_esquema_e_formato(resposta: httpx.Response) -> None:
    cliente, _ = _cliente(lambda _: resposta)
    assert _motivo(cliente) == "formato"


def test_sem_chave_nao_manda() -> None:
    cliente, vistos = _cliente(lambda _: _resposta([_uso(BOA)]), chave="")
    assert _motivo(cliente) == "sem_chave"
    assert vistos == []


@pytest.mark.parametrize(
    "modelo", ["claude-opus-5-5", "claude-sonnet-5", "claude-haiku-4-5", "claude-haiku-5-5 "]
)
def test_modelo_fora_da_lista_recusado_antes_de_mandar(modelo: str) -> None:
    # (guarda) só `claude-haiku-5-5` e `claude-sonnet-5-5` (ADR 0009); o controle é o Haiku acima
    cliente, vistos = _cliente(lambda _: _resposta([_uso(BOA)]))
    assert _motivo(cliente, _pedido(modelo)) == "modelo_ausente"
    assert vistos == []
    assert cliente.pedir(_pedido("claude-haiku-5-5")).dados == BOA
    assert len(vistos) == 1


def test_salto_nao_e_seguido_mesmo_com_cliente_que_segue() -> None:
    # (guarda) a chave nunca vai a outro host; o controle é o 200 direto dos outros testes
    def salta(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.host == "api.anthropic.com":
            return httpx.Response(307, headers={"location": "https://outro.example/v1/messages"})
        return _resposta([_uso(BOA)])

    cliente, vistos = _cliente(salta, follow_redirects=True)
    assert _motivo(cliente) == "servico_fora"
    assert [p.url.host for p in vistos] == ["api.anthropic.com"]


def test_chave_nunca_no_log_nem_na_falha(caplog: pytest.LogCaptureFixture) -> None:
    # (guarda) controle: o log do httpx aparece (vê o pedido), mas sem a chave
    caplog.set_level(logging.DEBUG)
    cliente, _ = _cliente(lambda _: httpx.Response(401, text=f"chave {CHAVE} recusada"))
    with pytest.raises(Falha) as erro:
        cliente.pedir(_pedido())
    assert "api.anthropic.com" in caplog.text
    assert CHAVE not in caplog.text
    assert CHAVE not in str(erro.value)
    assert CHAVE not in repr(erro.value.__cause__) + repr(erro.value.__context__)


def test_chave_sem_workspace_e_chave_recusada() -> None:
    # 400 de chave sem workspace (manage-claude/authentication): a pessoa troca a chave (D192.3)
    corpo = {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "message": "This API key is not scoped to a workspace, so this request must include "
            "the anthropic-workspace-id header with the ID of the workspace to use.",
        },
    }
    cliente, _ = _cliente(lambda _: httpx.Response(400, json=corpo))
    assert _motivo(cliente) == "chave_recusada"


@pytest.mark.parametrize("chave", ["é" + CHAVE, CHAVE[:5] + " " + CHAVE[5:], "a\nb", "a\x00b"])
def test_chave_invalida_nao_manda(chave: str) -> None:
    # (guarda) chave que não é ASCII visível não vira cabeçalho: nem pedido, nem chave no repr
    cliente, vistos = _cliente(lambda _: _resposta([_uso(BOA)]), chave=chave)
    with pytest.raises(Falha) as erro:
        cliente.pedir(_pedido())
    assert erro.value.motivo == "chave_recusada"
    assert vistos == []
    assert chave not in repr(erro.value.__cause__) + repr(erro.value.__context__)


def test_chave_colada_com_quebra_de_linha_vale_sem_ela() -> None:
    cliente, vistos = _cliente(lambda _: _resposta([_uso(BOA)]), chave=f"  {CHAVE}\n")
    assert cliente.pedir(_pedido()).dados == BOA
    assert vistos[0].headers["authorization"] == f"Bearer {CHAVE}"


def test_close_fecha_so_o_cliente_proprio() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda _: _resposta([])))
    ClienteAnthropic(CHAVE, http).close()
    assert not http.is_closed
    proprio = ClienteAnthropic(CHAVE)
    proprio.close()
    assert proprio._cliente.is_closed
