"""Backend de IA para os testes: grava os pedidos e devolve, em ordem, as respostas prontas."""

from jobot.nucleo.ia.contrato import Falha, Pedido, Resposta, conferir


class BackendFalso:
    def __init__(self, prontas: list[dict[str, object] | Falha]) -> None:
        self.prontas = list(prontas)
        self.pedidos: list[Pedido] = []

    def pedir(self, pedido: Pedido) -> Resposta:
        self.pedidos.append(pedido)
        pronta = self.prontas.pop(0)
        if isinstance(pronta, Falha):
            raise pronta
        return conferir(pedido, pronta, "falso")  # a mesma conferência dos clientes de verdade
