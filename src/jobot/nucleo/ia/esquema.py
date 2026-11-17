"""O esquema de saída que cada backend aceita (desenho 5.1 da fase 4). Os limites tirados daqui
continuam conferidos pelo pydantic na resposta (`contrato.conferir`)."""

from typing import Any

from pydantic import BaseModel

# Lista da documentação do `strict` da OpenAI, a conferir com data na T405 (D187). O endpoint
# compatível do Gemini e o compatível genérico recebem a mesma, a mais estreita.
_STRICT = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "anyOf",
        "$defs",
        "$ref",
        "description",
        "pattern",
        "format",
        "multipleOf",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minItems",
        "maxItems",
    }
)
_LOCAL = _STRICT | {"title", "default", "const", "minLength", "maxLength"}
# None: o esquema inteiro (o `input_schema` da Anthropic)
PERMITIDAS: dict[str, frozenset[str] | None] = {
    "local": _LOCAL,
    "openai": _STRICT,
    "gemini": _STRICT,
    "compativel": _STRICT,
    "anthropic": None,
}
# llama.cpp b12359: repetição acima disto quebra a gramática (MAX_REPETITION_THRESHOLD)
MAX_REPETICAO_LOCAL = 2000
_REPETICAO = frozenset({"minLength", "maxLength", "minItems", "maxItems"})


def esquema_para(backend: str, modelo: type[BaseModel]) -> dict[str, Any]:
    if backend not in PERMITIDAS:
        raise ValueError(f"backend de IA desconhecido: {backend!r}")
    completo = modelo.model_json_schema()
    permitidas = PERMITIDAS[backend]
    if permitidas is None:
        return completo
    teto = MAX_REPETICAO_LOCAL if backend == "local" else None
    return _filtrar(completo, permitidas, teto)


def _filtrar(no: dict[str, Any], permitidas: frozenset[str], teto: int | None) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for chave, valor in no.items():
        if chave not in permitidas or (teto is not None and chave in _REPETICAO and valor > teto):
            continue
        if chave in ("properties", "$defs"):
            valor = {nome: _filtrar(filho, permitidas, teto) for nome, filho in valor.items()}
        elif chave == "anyOf":
            valor = [_filtrar(filho, permitidas, teto) for filho in valor]
        elif chave in ("items", "additionalProperties") and isinstance(valor, dict):
            valor = _filtrar(valor, permitidas, teto)
        saida[chave] = valor
    return saida
