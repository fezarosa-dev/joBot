"""Leitor de validadores vazio: teste, cadastro e resolver não usam pedido condicional."""

from jobot.nucleo.http import Validadores


class SemValidadores:
    """Não há validador guardado: todo pedido vai inteiro."""

    def ler(self, url: str) -> Validadores | None:
        return None
