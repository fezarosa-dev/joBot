"""Cliente da API da Anthropic: `POST /v1/messages` com a ferramenta `responder`, lendo o `input` do
`tool_use` (desenho 6 da fase 4; escolhas na D192).

Conferido em 2026-11-17 na documentação oficial:
- https://platform.claude.com/docs/en/api/messages/create: `max_tokens` obrigatório; `thinking`
  aceita `between_tools`.
- https://platform.claude.com/docs/en/api/versioning: versão `2026-10-21` no `anthropic-version`;
  nela `temperature`, `top_p` e `top_k` dão 400 em todo modelo.
- https://platform.claude.com/docs/en/manage-claude/authentication: chave no `Authorization`
  (`Bearer`); chave sem workspace exige `anthropic-workspace-id`, e sem ele vem 400.
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#forcing-tool-use e
  https://platform.claude.com/docs/en/api/errors#forced-tool-use-not-supported: o Sonnet 5.5 dá 400
  para `tool_choice` `tool`/`any`; o Haiku 5.5 aceita.
- https://platform.claude.com/docs/en/api/errors: 400, 401, 402 (cobrança), 403, 404, 409, 413,
  429, 500, 504 e 529.
- https://platform.claude.com/docs/en/build-with-claude/effort: `between_tools` só com effort
  `high` ou abaixo (o padrão do Sonnet 5.5 é `high`).
"""

import json
import re
from typing import Any

import httpx

from jobot.nucleo.ia.contrato import Falha, Motivo, Pedido, Resposta, conferir, limites
from jobot.nucleo.ia.esquema import esquema_para

URL = "https://api.anthropic.com/v1/messages"
VERSAO_API = "2026-10-21"
FERRAMENTA = "responder"
_DESCRICAO = "Devolve a resposta no formato pedido. Responda sempre chamando esta ferramenta."

# Só estes dois (ADR 0009). O Sonnet 5.5 não aceita ferramenta forçada: vai em `auto`, sem o
# pensamento antes da resposta (que gastaria o `max_tokens` curto das tarefas). `between_tools`
# exige effort `high` ou abaixo (padrão do Sonnet 5.5 é `high`; não mandamos
# `output_config.effort`).
_EXTRAS: dict[str, dict[str, Any]] = {
    "claude-haiku-5-5": {"tool_choice": {"type": "tool", "name": FERRAMENTA}},
    "claude-sonnet-5-5": {"tool_choice": {"type": "auto"}, "thinking": {"type": "between_tools"}},
}
_POR_STATUS: dict[int, Motivo] = {
    400: "esquema_recusado",
    401: "chave_recusada",
    402: "limite",  # cobrança: a pessoa resolve no console, como o limite de gasto
    403: "chave_recusada",
    404: "modelo_ausente",
    413: "contexto",
    429: "limite",
}
_CHAVE_VALIDA = re.compile(r"[\x21-\x7e]+")  # ASCII visível: vira cabeçalho sem erro do h11
_SEM_WORKSPACE = b"anthropic-workspace-id"


class ClienteAnthropic:
    def __init__(self, chave: str, cliente: httpx.Client | None = None) -> None:
        self._chave = chave.strip()  # colagem traz quebra de linha
        self._proprio = cliente is None
        self._cliente = cliente or httpx.Client(follow_redirects=False)

    def close(self) -> None:
        """Fecha só o cliente HTTP criado aqui; o injetado é de quem o injetou."""
        if self._proprio:
            self._cliente.close()

    def pedir(self, pedido: Pedido) -> Resposta:
        extras = _EXTRAS.get(pedido.modelo)
        if extras is None:
            raise Falha("modelo_ausente")
        if not self._chave:
            raise Falha("sem_chave")
        if not _CHAVE_VALIDA.fullmatch(self._chave):
            raise Falha("chave_recusada")
        corpo = {
            "model": pedido.modelo,
            "max_tokens": pedido.max_tokens,
            "system": "\n\n".join(m.texto for m in pedido.mensagens if m.papel == "system"),
            "messages": [
                {"role": "user", "content": m.texto} for m in pedido.mensagens if m.papel == "user"
            ],
            "tools": [
                {
                    "name": FERRAMENTA,
                    "description": _DESCRICAO,
                    "input_schema": esquema_para("anthropic", pedido.esquema),
                }
            ],
            **extras,
        }
        http = self._cliente.build_request(
            "POST",
            URL,
            json=corpo,
            headers={"authorization": f"Bearer {self._chave}", "anthropic-version": VERSAO_API},
            timeout=pedido.prazo_s,
        )
        texto = self._enviar(http)
        try:
            dados = json.loads(texto)
        except ValueError:
            raise Falha("formato") from None
        return conferir(pedido, _entrada(dados), "anthropic")

    def _enviar(self, http: httpx.Request) -> bytes:
        try:
            # salto nunca: a chave não vai a outro host, mesmo que o cliente injetado siga saltos
            resposta = self._cliente.send(http, stream=True, follow_redirects=False)
            try:
                if resposta.status_code == 400 and _sem_workspace(resposta):
                    raise Falha("chave_recusada")
                if resposta.status_code != 200:
                    raise Falha(_POR_STATUS.get(resposta.status_code, "servico_fora"))
                return _ler(resposta, limites()["resposta_max_bytes"])
            finally:
                resposta.close()
        except httpx.TimeoutException:
            raise Falha("tempo_esgotado") from None
        except httpx.HTTPError:
            raise Falha("sem_rede") from None


def _ler(resposta: httpx.Response, teto: int) -> bytes:
    partes: list[bytes] = []
    total = 0
    for bloco in resposta.iter_bytes():
        total += len(bloco)
        if total > teto:
            raise Falha("formato")
        partes.append(bloco)
    return b"".join(partes)


def _sem_workspace(resposta: httpx.Response) -> bool:
    """400 de chave que não está presa a um workspace (D192.3). O texto só é procurado, nunca
    repassado."""
    try:
        return _SEM_WORKSPACE in _ler(resposta, 65536)
    except Falha:
        return False


def _entrada(dados: object) -> object:
    blocos = dados.get("content") if isinstance(dados, dict) else None
    if not isinstance(blocos, list):
        raise Falha("formato")
    for bloco in blocos:
        if isinstance(bloco, dict) and bloco.get("type") == "tool_use":
            if bloco.get("name") == FERRAMENTA:
                return bloco.get("input")
    raise Falha("recusa")  # recusa do modelo ou resposta sem a ferramenta
