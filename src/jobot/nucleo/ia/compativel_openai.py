"""Cliente `POST <endereço>/chat/completions` com `response_format` `json_schema` (desenho 5.1 e 6
da fase 4): OpenAI, Gemini, o modelo local (`llama-server`), Ollama, LM Studio e outros
compatíveis.

A chave só vai no `Authorization`; nunca no log nem na `Falha` (que leva só o motivo, sem o erro
do `httpx` encadeado). Saltos nunca são seguidos: um 307/308 reenviaria a chave e o corpo.

Fontes conferidas em 2026-11-17 (T405):
- OpenAI, Chat Completions e Structured Outputs:
  https://developers.openai.com/api/docs/guides/structured-outputs
- Gemini, endpoint compatível (`base_url` e `Authorization: Bearer`):
  https://aistudio.google.com/docs/openai
- llama.cpp, contexto estourado é 400 com `type` `exceed_context_size_error` (PR 15780):
  https://github.com/ggml-org/llama.cpp/pull/15780
- OpenAI, `max_tokens` "deprecated in favor of `max_completion_tokens`" e incompatível com os
  modelos de raciocínio; `max_completion_tokens` conta também os tokens de raciocínio:
  https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
  `temperature` fora do padrão é recusada nos modelos de raciocínio (GPT-5; do 5.1 em diante, só
  com `reasoning_effort` `none`), segundo relatos, não a referência: por isso não vai (D191.12).
"""

import json
import logging
import time
from typing import Any, Final
from urllib.parse import urlsplit

import httpx

from jobot.nucleo.ia.contrato import Falha, Motivo, Pedido, Resposta, conferir, limites
from jobot.nucleo.ia.esquema import esquema_para

_LOG = logging.getLogger(__name__)

ENDERECOS: Final = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}
LOCAIS: Final = frozenset({"127.0.0.1", "localhost", "::1"})
# 400 de contexto estourado: `code` na OpenAI, `type` no llama.cpp
_CONTEXTO: Final = frozenset({"context_length_exceeded", "exceed_context_size_error"})
_POR_CODIGO: Final[dict[int, Motivo]] = {
    400: "esquema_recusado",
    401: "chave_recusada",
    403: "chave_recusada",
    404: "modelo_ausente",
    429: "limite",
}


def conferir_endereco(endereco: str) -> str:
    """`https`, ou `http` só para `127.0.0.1`, `localhost` e `::1`; sem `usuario:senha@`, query
    nem fragmento. Devolve sem a `/` do fim. A mensagem de erro não repete o endereço (ele pode
    trazer uma senha). Espaço e controle nas pontas saem (vêm de copiar e colar); no meio,
    recusa."""
    endereco = endereco.strip()
    if any(c.isspace() or not c.isprintable() for c in endereco):
        raise ValueError("endereço da IA com espaço ou caractere invisível")
    partes = urlsplit(endereco)
    try:
        partes.port  # noqa: B018 (porta que não é número levanta ValueError)
    except ValueError:
        raise ValueError("endereço da IA com porta inválida") from None
    if "@" in partes.netloc or "?" in endereco or "#" in endereco:
        raise ValueError("endereço da IA não pode ter usuário, senha, query nem fragmento")
    host = partes.hostname
    if not host or not (partes.scheme == "https" or (partes.scheme == "http" and host in LOCAIS)):
        raise ValueError("endereço da IA precisa de https (http só em 127.0.0.1, localhost e ::1)")
    return endereco.rstrip("/")


def novo_cliente(endereco: str) -> httpx.Client:
    """Cliente próprio da IA, não o `ClienteEducado` da coleta. Endereço local: `trust_env=False`,
    para um proxy do ambiente não levar para fora o pedido ao `127.0.0.1`."""
    local = urlsplit(endereco).hostname in LOCAIS
    return httpx.Client(follow_redirects=False, trust_env=not local)


class ClienteCompativel:
    """`Backend` (contrato) de `openai`, `gemini`, `compativel` ou `local`; o nome escolhe a lista
    de `esquema_para` e volta na `Resposta`."""

    def __init__(
        self,
        backend: str,
        endereco: str,
        chave: str | None,
        *,
        cliente: httpx.Client | None = None,
    ) -> None:
        self.backend = backend
        limpo = conferir_endereco(endereco)
        self._url = limpo + "/chat/completions"
        self._chave = chave.strip() if chave else None  # espaço e quebra de copiar e colar
        self._http = cliente if cliente is not None else novo_cliente(limpo)

    def fechar(self) -> None:
        self._http.close()

    def pedir(self, pedido: Pedido) -> Resposta:
        comeco = time.monotonic()
        resultado = "erro"  # só vira "ok" depois do sucesso
        tamanho = 0
        try:
            codigo, corpo = self._chamar(pedido)
            tamanho = len(corpo)
            if codigo != 200:
                raise Falha(_motivo_do_erro(codigo, corpo))
            resposta = conferir(pedido, _conteudo(corpo), self.backend)
            resultado = "ok"
            return resposta
        except Falha as falha:
            resultado = falha.motivo
            raise
        finally:
            _LOG.info(
                "ia %s %s %s: %s em %.2f s, %d bytes",
                pedido.tarefa,
                self.backend,
                pedido.modelo,
                resultado,
                time.monotonic() - comeco,
                tamanho,
            )

    def _chamar(self, pedido: Pedido) -> tuple[int, bytes]:
        """O código e o corpo lido. Chave que não é ASCII imprimível (um NBSP ou zero-width colado)
        é recusada antes: o `httpx` levantaria `UnicodeEncodeError`, que guarda a chave inteira."""
        if self._chave and not (self._chave.isascii() and self._chave.isprintable()):
            raise Falha("chave_recusada")
        cabecalhos = {"Authorization": f"Bearer {self._chave}"} if self._chave else {}
        requisicao = self._http.build_request(
            "POST",
            self._url,
            json=self._corpo(pedido),
            headers=cabecalhos,
            timeout=pedido.prazo_s,
        )
        try:
            resposta = self._http.send(requisicao, stream=True, follow_redirects=False)
        except httpx.TimeoutException:
            raise Falha("tempo_esgotado") from None
        except httpx.HTTPError:
            raise Falha("sem_rede") from None
        try:
            corpo = _ler(resposta)
        finally:
            resposta.close()  # no prazo, fecha a conexão: o llama-server cancela o pedido
        return resposta.status_code, corpo

    def _corpo(self, pedido: Pedido) -> dict[str, Any]:
        corpo: dict[str, Any] = {
            "model": pedido.modelo,
            "messages": [{"role": m.papel, "content": m.texto} for m in pedido.mensagens],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": pedido.tarefa,
                    "strict": True,
                    "schema": esquema_para(self.backend, pedido.esquema),
                },
            },
        }
        if self.backend == "openai":
            # `max_tokens` é recusado nos modelos de raciocínio, e `temperature` fora do padrão
            # também (fontes no topo; D191.12). `seed` fica: a referência não o restringe.
            corpo["max_completion_tokens"] = pedido.max_tokens
        else:
            corpo["max_tokens"] = pedido.max_tokens
        if pedido.temperatura is not None and self.backend != "openai":
            corpo["temperature"] = pedido.temperatura
        if pedido.seed is not None:
            corpo["seed"] = pedido.seed
        return corpo


def _ler(resposta: httpx.Response) -> bytes:
    """O corpo até o teto de `ia.json`, lido em fluxo; acima dele, `formato`."""
    teto: int = limites()["resposta_max_bytes"]
    partes: list[bytes] = []
    lidos = 0
    try:
        for bloco in resposta.iter_bytes():
            lidos += len(bloco)
            if lidos > teto:
                raise Falha("formato")
            partes.append(bloco)
    except httpx.TimeoutException:
        raise Falha("tempo_esgotado") from None
    except httpx.HTTPError:
        raise Falha("sem_rede") from None
    return b"".join(partes)


def _json(corpo: bytes) -> object:
    try:
        return json.loads(corpo)
    except ValueError:
        return None


def _motivo_do_erro(codigo: int, corpo: bytes) -> Motivo:
    if codigo == 400:
        dados = _json(corpo)
        erro = dados.get("error") if isinstance(dados, dict) else None
        if isinstance(erro, dict) and {erro.get("code"), erro.get("type")} & _CONTEXTO:
            return "contexto"
    return _POR_CODIGO.get(codigo, "servico_fora")  # 3xx (salto não seguido), 5xx e o resto


def _conteudo(corpo: bytes) -> object:
    """A saída do modelo: o JSON de `choices[0].message.content`. Sem conteúdo (ou com `refusal`):
    `recusa`. Fora desse formato: `formato`."""
    dados = _json(corpo)
    escolhas = dados.get("choices") if isinstance(dados, dict) else None
    if not isinstance(escolhas, list) or not escolhas or not isinstance(escolhas[0], dict):
        raise Falha("formato")
    mensagem = escolhas[0].get("message")
    if not isinstance(mensagem, dict):
        raise Falha("formato")
    conteudo = mensagem.get("content")
    if mensagem.get("refusal") or conteudo is None:
        raise Falha("recusa")
    if not isinstance(conteudo, str):
        raise Falha("formato")
    saida = _json(conteudo.encode())
    if saida is None:
        raise Falha("formato")
    return saida
