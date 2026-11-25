"""O esquema de saída que cada backend aceita (desenho 5.1 da fase 4). Os limites tirados daqui
continuam conferidos pelo pydantic na resposta (`contrato.conferir`). Nenhum backend recebe as
descrições: são as docstrings dos modelos, notas de quem constrói (D229)."""

from typing import Any

from pydantic import BaseModel

# Lista do `strict` da OpenAI, conferida em 2026-11-17 (T405) em "Supported schemas" de
# https://developers.openai.com/api/docs/guides/structured-outputs: sem `minLength`/`maxLength`,
# todo campo em `required` e `additionalProperties: false` em todo objeto.
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
# A da saída estruturada do Gemini (https://aistudio.google.com/docs/structured-output, conferida
# em 2026-11-17) não cita `pattern`, `multipleOf` nem os `exclusive*`: o Gemini fica com o que as
# duas citam, e o compatível genérico (Ollama, LM Studio...) com essa, a mais estreita.
_GEMINI = _STRICT - {"pattern", "multipleOf", "exclusiveMinimum", "exclusiveMaximum"}
_LOCAL = _STRICT | {"title", "default", "const", "minLength", "maxLength"}
# None: o esquema inteiro (o `input_schema` da Anthropic)
PERMITIDAS: dict[str, frozenset[str] | None] = {
    "local": _LOCAL,
    "openai": _STRICT,
    "gemini": _GEMINI,
    "compativel": _GEMINI,
    "anthropic": None,
}
# llama.cpp b12359: repetição acima disto quebra a gramática (MAX_REPETITION_THRESHOLD)
MAX_REPETICAO_LOCAL = 2000
_REPETICAO = frozenset({"minLength", "maxLength", "minItems", "maxItems"})


def esquema_para(backend: str, modelo: type[BaseModel]) -> dict[str, Any]:
    if backend not in PERMITIDAS:
        raise ValueError(f"backend de IA desconhecido: {backend!r}")
    completo: dict[str, Any] = sem_descricoes(modelo.model_json_schema())
    permitidas = PERMITIDAS[backend]
    if permitidas is None:
        return completo
    teto = MAX_REPETICAO_LOCAL if backend == "local" else None
    return _filtrar(completo, permitidas, teto, backend == "openai")


def _filtrar(
    no: dict[str, Any], permitidas: frozenset[str], teto: int | None, todos: bool
) -> dict[str, Any]:
    """`todos`: todo campo em `required` (o opcional do pydantic já vai como união com `null`)."""
    saida: dict[str, Any] = {}
    for chave, valor in no.items():
        if chave not in permitidas or (teto is not None and chave in _REPETICAO and valor > teto):
            continue
        if chave in ("properties", "$defs"):
            valor = {nome: _filtrar(f, permitidas, teto, todos) for nome, f in valor.items()}
        elif chave == "anyOf":
            valor = [_filtrar(filho, permitidas, teto, todos) for filho in valor]
        elif chave in ("items", "additionalProperties") and isinstance(valor, dict):
            valor = _filtrar(valor, permitidas, teto, todos)
        saida[chave] = valor
    if todos and "properties" in saida:
        saida["required"] = list(saida["properties"])
    return saida


def sem_descricoes(no: Any) -> Any:
    if isinstance(no, dict):
        # a palavra-chave é texto; um campo chamado "description" em `properties` é um objeto
        return {
            k: sem_descricoes(v)
            for k, v in no.items()
            if not (k == "description" and isinstance(v, str))
        }
    if isinstance(no, list):
        return [sem_descricoes(v) for v in no]
    return no
