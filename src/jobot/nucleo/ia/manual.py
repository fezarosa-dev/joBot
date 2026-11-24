"""IA manual (desenho 6 e 9 da fase 4): o painel mostra o pedido para a pessoa copiar no chat de IA
que ela escolher e lê a resposta que ela cola de volta. A resposta colada é dado, como a de
qualquer backend: passa por `contrato.conferir` (o esquema da tarefa) e depois pelas conferências
de `tarefas`, que quem chama aplica igual para todo backend.

Só nas tarefas sob pedido (`TAREFAS`): o `encaixe` roda sozinho no laço, sem ninguém para colar
(D229)."""

import json
import re

from jobot.nucleo.ia.contrato import Falha, Pedido, Resposta, conferir, limites

BACKEND = "manual"
TAREFAS = frozenset({"curriculo", "perguntas", "candidatura"})

# Em inglês, como o resto do pedido (D190). Vem depois do bloco de dados, fora das marcas.
PEDE_JSON = (
    "Answer with only one JSON object that follows the JSON Schema below, with no text before or "
    "after it."
)
# Sem `\s*` em volta do miolo: com ele, "```" seguido de muito espaço e sem fim fica cúbico. O
# `json.loads` já aceita os espaços das pontas.
_BLOCO = re.compile(r"```(?:json)?(.*?)```", re.DOTALL | re.IGNORECASE)


def _so_sob_pedido(tarefa: str) -> None:
    if tarefa not in TAREFAS:
        raise ValueError(f"a tarefa {tarefa!r} não aceita a IA manual")


def texto_para_copiar(pedido: Pedido) -> str:
    """As mensagens do pedido em ordem (a de sistema primeiro) e o esquema inteiro da tarefa, com os
    tetos: a pessoa cola em qualquer chat, então não há backend para filtrar (`esquema_para`)."""
    _so_sob_pedido(pedido.tarefa)
    esquema = json.dumps(pedido.esquema.model_json_schema(), ensure_ascii=False, indent=1)
    return "\n\n".join([*(m.texto for m in pedido.mensagens), PEDE_JSON, esquema])


def ler_resposta(pedido: Pedido, colado: str) -> Resposta:
    """O texto colado como JSON puro ou num bloco de código só (com texto em volta, como os chats
    respondem). Não é JSON, tem dois blocos, passa do teto de `ia.json` ou não passa no esquema:
    `Falha("formato")`, sem o texto colado."""
    _so_sob_pedido(pedido.tarefa)
    if len(colado.encode()) > limites()["resposta_max_bytes"]:
        raise Falha("formato")
    texto = colado.strip()
    blocos = _BLOCO.findall(texto)
    for candidato in [texto, *blocos] if len(blocos) == 1 else [texto]:
        try:
            dados = json.loads(candidato)
        except ValueError, RecursionError:
            continue
        return conferir(pedido, dados, BACKEND)
    raise Falha("formato")
