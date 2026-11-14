"""Leitura de campo de formulário compartilhada pelas rotas do painel."""

from starlette.datastructures import FormData


def campo_unico(form: FormData, campo: str) -> str:
    """O texto do campo; ausente ou arquivo enviado vira vazio."""
    valor = form.get(campo)
    return valor if isinstance(valor, str) else ""
