"""Cliente compatível com a OpenAI (desenho 5.1 e 6 da fase 4): corpo, motivos de falha, endereço,
saltos, proxy do ambiente e a chave fora do log. Sem rede: `httpx.MockTransport` ou servidor em
thread em `127.0.0.1`."""

import json
import logging
import re
import threading
import traceback
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Annotated, Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field

from jobot.nucleo.ia.compativel_openai import (
    ENDERECOS,
    ClienteCompativel,
    conferir_endereco,
    novo_cliente,
)
from jobot.nucleo.ia.contrato import Falha, Mensagem, Pedido, Resposta, limites
from jobot.nucleo.ia.esquema import esquema_para

OPENAI = "https://api.openai.com/v1"
CHAVE = "sk-SEGREDO-0123456789"


class _Saida(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pede: list[Annotated[str, Field(max_length=60)]] = Field(max_length=3)


def _pedido(**muda: Any) -> Pedido:
    campos: dict[str, Any] = {
        "tarefa": "encaixe",
        "modelo": "m-teste",
        "mensagens": (Mensagem("system", "regras"), Mensagem("user", "vaga")),
        "esquema": _Saida,
        "max_tokens": 1024,
        "prazo_s": 60,
        "versao": 2,
        "temperatura": 0,
        "seed": 7,
    }
    return Pedido(**(campos | muda))


def _corpo(conteudo: str | None, **mensagem: Any) -> dict[str, Any]:
    msg = {"role": "assistant", "content": conteudo} | mensagem
    return {"choices": [{"index": 0, "message": msg, "finish_reason": "stop"}]}


def _ok(dados: object = None) -> httpx.Response:
    return httpx.Response(200, json=_corpo(json.dumps(dados or {"pede": ["Python"]})))


Atende = Callable[[httpx.Request], httpx.Response]


def _responde(resposta: httpx.Response) -> Atende:
    return lambda _: resposta


def _cliente(
    atende: Atende,
    backend: str = "openai",
    endereco: str = OPENAI,
    chave: str | None = CHAVE,
    *,
    segue_saltos: bool = False,
) -> tuple[ClienteCompativel, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []

    def gravar(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return atende(pedido)

    http = httpx.Client(transport=httpx.MockTransport(gravar), follow_redirects=segue_saltos)
    return ClienteCompativel(backend, endereco, chave, cliente=http), pedidos


def _falha(atende: Atende, **kwargs: Any) -> tuple[str, list[httpx.Request]]:
    cliente, pedidos = _cliente(atende, **kwargs)
    with pytest.raises(Falha) as erro:
        cliente.pedir(_pedido())
    return erro.value.motivo, pedidos


@pytest.mark.parametrize(
    ("backend", "endereco"),
    [
        ("openai", ENDERECOS["openai"]),
        ("gemini", ENDERECOS["gemini"]),
        ("compativel", "http://127.0.0.1:11434/v1"),
        ("local", "http://127.0.0.1:8085/v1"),
    ],
)
def test_corpo_leva_modelo_mensagens_esquema_tokens_temperatura_e_seed(
    backend: str, endereco: str
) -> None:
    cliente, pedidos = _cliente(lambda _: _ok(), backend, endereco)
    resposta = cliente.pedir(_pedido())
    assert resposta == Resposta({"pede": ["Python"]}, backend, "m-teste", 2)
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert (pedido.method, str(pedido.url)) == ("POST", f"{endereco}/chat/completions")
    assert json.loads(pedido.content) == {
        "model": "m-teste",
        "messages": [
            {"role": "system", "content": "regras"},
            {"role": "user", "content": "vaga"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "encaixe",
                "strict": True,
                "schema": esquema_para(backend, _Saida),
            },
        },
        "max_tokens": 1024,
        "temperature": 0,
        "seed": 7,
    }
    assert pedido.extensions["timeout"] == dict.fromkeys(("connect", "read", "write", "pool"), 60)


def test_sem_temperatura_e_seed_o_corpo_nao_os_leva() -> None:
    cliente, pedidos = _cliente(lambda _: _ok())
    cliente.pedir(_pedido(temperatura=None, seed=None))
    assert len(pedidos) == 1
    corpo = json.loads(pedidos[0].content)
    assert "temperature" not in corpo and "seed" not in corpo
    assert corpo["max_tokens"] == 1024  # controle


def test_authorization_so_com_chave() -> None:
    com, pedidos_com = _cliente(lambda _: _ok())
    com.pedir(_pedido())
    assert len(pedidos_com) == 1
    assert pedidos_com[0].headers["Authorization"] == f"Bearer {CHAVE}"
    for vazia in (None, ""):
        sem, pedidos_sem = _cliente(lambda _: _ok(), chave=vazia)
        sem.pedir(_pedido())
        assert len(pedidos_sem) == 1
        assert "Authorization" not in pedidos_sem[0].headers


@pytest.mark.parametrize(
    ("codigo", "motivo"),
    [
        (400, "esquema_recusado"),
        (401, "chave_recusada"),
        (403, "chave_recusada"),
        (404, "modelo_ausente"),
        (429, "limite"),
        (500, "servico_fora"),
        (502, "servico_fora"),
        (503, "servico_fora"),
        (418, "servico_fora"),
    ],
)
def test_codigo_http_vira_o_motivo(codigo: int, motivo: str) -> None:
    corpo = {"error": {"message": f"erro {codigo}", "type": "invalid_request_error"}}
    assert _falha(lambda _: httpx.Response(codigo, json=corpo))[0] == motivo


@pytest.mark.parametrize(
    "erro",
    [
        # OpenAI: `code` do erro
        {"message": "too long", "type": "invalid_request_error", "code": "context_length_exceeded"},
        # llama.cpp (PR 15780): `type` do erro
        {"code": 400, "message": "too long", "type": "exceed_context_size_error"},
    ],
)
def test_400_de_contexto_estourado_e_contexto(erro: dict[str, Any]) -> None:
    assert _falha(lambda _: httpx.Response(400, json={"error": erro}))[0] == "contexto"


def test_400_com_corpo_estranho_e_esquema_recusado() -> None:
    for corpo in (b"nao e json", b'["context_length_exceeded"]', b'{"error": "context"}'):
        assert _falha(_responde(httpx.Response(400, content=corpo)))[0] == "esquema_recusado"


def test_conexao_recusada_e_sem_rede() -> None:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("recusada", request=pedido)

    assert _falha(recusa)[0] == "sem_rede"


class _CorpoQueParaNoMeio(httpx.SyncByteStream):
    def __init__(self) -> None:
        self.fechado = False

    def __iter__(self) -> Iterator[bytes]:
        yield b'{"choices": '
        raise httpx.ReadTimeout("prazo")

    def close(self) -> None:
        self.fechado = True


def test_prazo_no_meio_da_resposta_e_tempo_esgotado_com_a_conexao_fechada() -> None:
    corpo = _CorpoQueParaNoMeio()
    assert _falha(lambda _: httpx.Response(200, stream=corpo))[0] == "tempo_esgotado"
    assert corpo.fechado


def test_prazo_antes_da_resposta_e_tempo_esgotado() -> None:
    def demora(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("prazo", request=pedido)

    assert _falha(demora)[0] == "tempo_esgotado"


def test_resposta_acima_do_teto_e_formato() -> None:
    teto = limites()["resposta_max_bytes"]
    base = json.dumps(_corpo(json.dumps({"pede": ["Python"]}))).encode()
    no_teto = base + b" " * (teto - len(base))
    cliente, _ = _cliente(lambda _: httpx.Response(200, content=no_teto))
    assert cliente.pedir(_pedido()).dados == {"pede": ["Python"]}  # controle: no teto passa
    assert _falha(lambda _: httpx.Response(200, content=no_teto + b" "))[0] == "formato"


@pytest.mark.parametrize(
    "corpo",
    [
        _corpo(json.dumps({"pede": ["a"], "extra": 1})),  # campo a mais
        _corpo(json.dumps({"pede": ["a", "b", "c", "d"]})),  # lista longa
        _corpo(json.dumps({"pede": "Python"})),  # tipo errado
        _corpo("{nao e json"),
        _corpo(json.dumps({"pede": ["a"]}))["choices"][0],  # sem `choices`
        {"choices": []},
        [1, 2],
    ],
)
def test_resposta_fora_do_esquema_e_formato(corpo: object) -> None:
    assert _falha(lambda _: httpx.Response(200, json=corpo))[0] == "formato"


def test_corpo_que_nao_e_json_e_formato() -> None:
    assert _falha(lambda _: httpx.Response(200, content=b"<html>"))[0] == "formato"


def test_recusa_do_modelo_e_recusa() -> None:
    recusas = (
        _corpo(None, refusal="não posso"),
        _corpo(json.dumps({"pede": ["a"]}), refusal="não posso"),  # recusa vence o conteúdo
        _corpo(None),
    )
    for corpo in recusas:
        assert _falha(_responde(httpx.Response(200, json=corpo)))[0] == "recusa"


@pytest.mark.parametrize(
    "endereco",
    [
        "https://api.openai.com/v1",
        "https://servico.exemplo/v1/",
        "http://127.0.0.1:8080/v1",
        "http://localhost:11434/v1",
        "http://[::1]:1234/v1",
    ],
)
def test_endereco_aceito(endereco: str) -> None:
    assert conferir_endereco(endereco) == endereco.rstrip("/")


@pytest.mark.parametrize(
    "endereco",
    [
        "http://servico.exemplo/v1",
        "http://192.168.0.2:11434/v1",
        "http://127.0.0.1.exemplo/v1",
        "ftp://127.0.0.1/v1",
        "https:///v1",
        "api.openai.com/v1",
        "https://usuario:s3gr3d0@servico.exemplo/v1",
        "https://usuario@servico.exemplo/v1",
        "https://:s3gr3d0@servico.exemplo/v1",
        "https://servico.exemplo/v1?chave=s3gr3d0",
        "https://servico.exemplo/v1?",
        "https://servico.exemplo/v1#s3gr3d0",
        "http://127.0.0.1:porta/v1",
    ],
)
def test_endereco_recusado_antes_de_mandar(endereco: str) -> None:
    pedidos: list[httpx.Request] = []

    def gravar(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return _ok()

    http = httpx.Client(transport=httpx.MockTransport(gravar))
    with pytest.raises(ValueError, match="endereço") as erro:
        ClienteCompativel("compativel", endereco, CHAVE, cliente=http)
    assert pedidos == []
    assert "s3gr3d0" not in str(erro.value)  # o endereço não volta na mensagem


def test_salto_307_nao_e_seguido() -> None:
    """(guarda) mesmo com um cliente que segue saltos, o pedido com a chave não vai a outro host."""

    def salta(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.host == "api.openai.com":
            return httpx.Response(307, headers={"Location": "https://outro.exemplo/v1"})
        return _ok()

    motivo, pedidos = _falha(salta, segue_saltos=True)
    assert motivo == "servico_fora"
    assert [p.url.host for p in pedidos] == ["api.openai.com"]
    direto, _ = _cliente(lambda _: _ok(), segue_saltos=True)  # controle: o 200 direto passa
    assert direto.pedir(_pedido()).dados == {"pede": ["Python"]}
    assert novo_cliente(OPENAI).follow_redirects is False


class _Servidor:
    def __init__(self, resposta: bytes, codigo: int) -> None:
        self.caminhos: list[str] = []
        servidor = self

        class Atende(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                servidor.caminhos.append(self.path)
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(codigo)
                self.send_header("Content-Length", str(len(resposta)))
                self.end_headers()
                self.wfile.write(resposta)

            def log_message(self, *args: object) -> None:
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Atende)
        self.porta = self.http.server_address[1]
        threading.Thread(target=self.http.serve_forever, daemon=True).start()


@pytest.fixture
def local_e_proxy(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[_Servidor, _Servidor]]:
    local = _Servidor(json.dumps(_corpo(json.dumps({"pede": ["Python"]}))).encode(), 200)
    proxy = _Servidor(b"", 502)
    for nome in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        for variavel in (nome, nome.lower()):
            monkeypatch.setenv(variavel, f"http://127.0.0.1:{proxy.porta}")
    for variavel in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(variavel, raising=False)
    yield local, proxy
    for servidor in (local, proxy):
        servidor.http.shutdown()
        servidor.http.server_close()


def test_cliente_do_local_ignora_o_proxy_do_ambiente(
    local_e_proxy: tuple[_Servidor, _Servidor],
) -> None:
    """(guarda) `trust_env=False` para endereço local: o pedido ao `127.0.0.1` não passa por um
    proxy do ambiente."""
    local, proxy = local_e_proxy
    endereco = f"http://127.0.0.1:{local.porta}/v1"
    with httpx.Client() as confiado:  # controle: um cliente que lê o ambiente vai pelo proxy
        confiado.post(f"{endereco}/chat/completions", json={})
    assert (local.caminhos, len(proxy.caminhos)) == ([], 1)
    cliente = ClienteCompativel("local", endereco, "chave-da-subida")
    try:
        assert cliente.pedir(_pedido()).dados == {"pede": ["Python"]}
    finally:
        cliente.fechar()
    assert (local.caminhos, len(proxy.caminhos)) == (["/v1/chat/completions"], 1)


def test_cliente_de_fora_le_o_ambiente() -> None:
    # o proxy da empresa continua valendo para os serviços de fora
    assert novo_cliente(OPENAI).trust_env is True
    assert novo_cliente("http://localhost:11434/v1").trust_env is False


def _cai_citando_a_chave(pedido: httpx.Request) -> httpx.Response:
    raise httpx.LocalProtocolError(f"valor ilegal no cabeçalho: Bearer {CHAVE}", request=pedido)


def test_chave_nunca_vai_ao_log_nem_a_falha(caplog: pytest.LogCaptureFixture) -> None:
    """(guarda) a chave não aparece no log, em sucesso nem em falha."""
    caplog.set_level(logging.DEBUG)
    ok, _ = _cliente(lambda _: _ok())
    ok.pedir(_pedido())
    recusa, _ = _cliente(lambda _: httpx.Response(401, json={"error": {"message": CHAVE}}))
    with pytest.raises(Falha) as erro:
        recusa.pedir(_pedido())
    rede, _ = _cliente(_cai_citando_a_chave)
    with pytest.raises(Falha) as sem_rede:
        rede.pedir(_pedido())
    assert sem_rede.value.motivo == "sem_rede"
    # o erro do httpx (que pode citar o cabeçalho) não vai junto: nem num log com `exc_info`
    assert CHAVE not in "".join(traceback.format_exception(sem_rede.value))
    assert CHAVE not in caplog.text
    assert CHAVE not in f"{erro.value!s} {erro.value!r}"
    contexto = erro.value.__context__
    assert erro.value.__cause__ is None and (contexto is None or erro.value.__suppress_context__)
    # controle: o log vê o modelo, o resultado e a duração
    assert re.search(r"openai m-teste: ok em \d+\.\d+ s", caplog.text)
    assert re.search(r"openai m-teste: chave_recusada em \d+\.\d+ s", caplog.text)
