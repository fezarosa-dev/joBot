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

# Na língua da pessoa, que lê o que copia (D229, decidido pelo dono); o resto do pedido segue em
# inglês (D190). Vem depois do bloco de dados, fora das marcas.
PEDE_JSON = {
    "pt": (
        "Responda só com um objeto JSON que siga o esquema JSON abaixo, sem texto antes nem "
        "depois dele."
    ),
    "en": (
        "Answer with only one JSON object that follows the JSON Schema below, with no text before "
        "or after it."
    ),
}
# Sem `\s*` em volta do miolo: com ele, "```" seguido de muito espaço e sem fim fica cúbico. O
# `json.loads` já aceita os espaços das pontas.
_BLOCO = re.compile(r"```(?:json)?(.*?)```", re.DOTALL | re.IGNORECASE)


def _so_sob_pedido(tarefa: str) -> None:
    if tarefa not in TAREFAS:
        raise ValueError(f"a tarefa {tarefa!r} não aceita a IA manual")


def texto_para_copiar(pedido: Pedido, idioma: str) -> str:
    """As mensagens do pedido em ordem (a de sistema primeiro), a frase que pede o JSON no `idioma`
    do painel (`pt` ou `en`) e o esquema inteiro da tarefa, com os tetos: a pessoa cola em qualquer
    chat, então não há backend para filtrar (`esquema_para`). O esquema sai sem as descrições,
    que são as docstrings dos modelos, notas de quem constrói (D229)."""
    _so_sob_pedido(pedido.tarefa)
    esquema = json.dumps(
        _sem_descricoes(pedido.esquema.model_json_schema()), ensure_ascii=False, indent=1
    )
    return "\n\n".join([*(m.texto for m in pedido.mensagens), PEDE_JSON[idioma], esquema])


def _sem_descricoes(no: object) -> object:
    if isinstance(no, dict):
        # a palavra-chave é texto; um campo chamado "description" em `properties` é um objeto
        return {
            k: _sem_descricoes(v)
            for k, v in no.items()
            if not (k == "description" and isinstance(v, str))
        }
    if isinstance(no, list):
        return [_sem_descricoes(v) for v in no]
    return no


def ler_resposta(pedido: Pedido, colado: str) -> Resposta:
    """O texto colado como JSON puro ou num bloco de código só (com texto em volta, como os chats
    respondem). Não é JSON, tem dois blocos, passa do teto de `ia.json` ou não passa no esquema:
    `Falha("formato")`, sem o texto colado."""
    _so_sob_pedido(pedido.tarefa)
    # `surrogatepass`: substituto solto conta os seus bytes e cai no `json.loads` como formato.
    if len(colado.encode(errors="surrogatepass")) > limites()["resposta_max_bytes"]:
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
