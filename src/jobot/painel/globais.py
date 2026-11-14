"""Globais do Jinja do painel, registrados num só lugar quando os templates são montados."""

import jinja2
from jinja2 import pass_context
from jinja2.runtime import Context

from jobot.nucleo.modelo import Motivo
from jobot.painel import formatos


@pass_context
def _rotulo(contexto: Context, chave: str, padrao: str) -> str:
    """O texto da chave; sem texto no catálogo, o `padrao` (valor que o sistema não conhece)."""
    texto: str = contexto["t"](chave)
    return padrao if texto == chave else texto


@pass_context
def _motivo(contexto: Context, motivo: Motivo) -> str:
    """O motivo do encaixe em texto; chave desconhecida ou parâmetro faltando fica sem texto."""
    try:
        texto: str = contexto["t"](motivo.chave, **motivo.params)
    except KeyError, IndexError, ValueError:
        return ""
    return "" if texto == motivo.chave else texto


def registrar(env: jinja2.Environment) -> None:
    env.globals |= {
        "salario_texto": formatos.salario_texto,
        "locais_texto": formatos.locais_texto,
        "data_curta": formatos.data_curta,
        "data_completa": formatos.data_completa,
        "dinheiro": formatos.dinheiro,
        "rotulo": _rotulo,
        "motivo": _motivo,
    }
