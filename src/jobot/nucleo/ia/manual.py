"""IA manual (esqueleto do vermelho da T433)."""

from jobot.nucleo.ia.contrato import Pedido, Resposta

BACKEND = "manual"
TAREFAS = frozenset({"curriculo", "perguntas", "candidatura"})


def texto_para_copiar(pedido: Pedido) -> str:
    return "{}"


def ler_resposta(pedido: Pedido, colado: str) -> Resposta:
    return Resposta({}, BACKEND, pedido.modelo, pedido.versao)
