"""Globais do Jinja do painel, registrados num só lugar quando os templates são montados."""

import re
from collections.abc import Sequence

import jinja2
from jinja2 import pass_context
from jinja2.runtime import Context

from jobot.banco.leitura import Item
from jobot.nucleo.modelo import Local, Motivo
from jobot.painel import formatos
from jobot.painel.lateral import grupos_configuracoes, lateral

_MARCA = re.compile(r"(?<!\S)joBot-casca/(\d+(?:\.\d+){0,3}) \((linux|windows|macos)\)")


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


@pass_context
def _aviso(contexto: Context, aviso: str, locais: Sequence[Local]) -> str:
    """O texto do aviso; o de restrição a país nomeia os países da vaga, se houver."""
    if aviso == "restrito_a_pais" and (paises := formatos.paises_texto(locais, contexto["idioma"])):
        return str(contexto["t"]("aviso.restrito_a_pais_lista", paises=paises))
    return _rotulo(contexto, "aviso." + aviso, aviso)


@pass_context
def _salario_texto(contexto: Context, item: Item) -> formatos.SalarioTexto | None:
    """O salário do cartão na moeda de exibição (`exibicao`) e no idioma da pessoa."""
    return formatos.salario_texto(item, contexto["idioma"], contexto.get("exibicao"))


def marca_da_casca(agente: str | None) -> tuple[str, str] | None:
    """A versão e o sistema da marca ` joBot-casca/<versão> (<so>)` que a casca põe no user agent
    (desenho 5.3); sem a marca, ou com sistema desconhecido, `None`."""
    achado = _MARCA.search(agente or "")
    return (achado[1], achado[2]) if achado else None


def registrar(env: jinja2.Environment) -> None:
    env.globals |= {
        "salario_texto": _salario_texto,
        "locais_texto": formatos.locais_texto,
        "data_curta": formatos.data_curta,
        "data_completa": formatos.data_completa,
        "dinheiro": formatos.dinheiro,
        "rotulo": _rotulo,
        "aviso_texto": _aviso,
        "motivo": _motivo,
        "lateral": lateral,
        "grupos_configuracoes": grupos_configuracoes,
        "marca_da_casca": marca_da_casca,
    }
