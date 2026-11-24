"""Contrato da IA (desenho 5.1 da fase 4): Falha, esquema por backend, BackendFalso e ia.json."""

import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal, get_args

import pytest
from pydantic import BaseModel, ConfigDict, Field

from jobot.nucleo.ia.contrato import (
    Backend,
    Falha,
    Mensagem,
    Motivo,
    Pedido,
    Resposta,
    conferir,
    limites,
)
from jobot.nucleo.ia.esquema import esquema_para
from jobot.nucleo.ia.falso import BackendFalso

DO_BACKEND = {
    "sem_chave",
    "chave_recusada",
    "sem_rede",
    "programa_ausente",
    "modelo_ausente",
    "tempo_esgotado",
    "limite",
    "esquema_recusado",
    "servico_fora",
}
DO_PEDIDO = {"recusa", "formato", "contexto"}

# Lista permitida de cada backend, escrita aqui à parte do código (desenho 5.1), conferida na
# documentação em 2026-11-17 (T405): a do `strict` da OpenAI e a da saída estruturada do Gemini,
# que não cita `pattern`, `multipleOf` nem os `exclusive*`. O compatível leva a do Gemini, a mais
# estreita; o llama.cpp aceita mais, mas repetição acima de 2000 quebra a gramática.
_STRICT = {
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
_GEMINI = _STRICT - {"pattern", "multipleOf", "exclusiveMinimum", "exclusiveMaximum"}
_LOCAL = _STRICT | {"title", "default", "const", "minLength", "maxLength"}
PERMITIDAS = {"openai": _STRICT, "gemini": _GEMINI, "compativel": _GEMINI, "local": _LOCAL}
REPETICAO = ("minLength", "maxLength", "minItems", "maxItems")


class _Sub(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(max_length=60)


class _Exemplo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(max_length=5000)
    itens: list[Annotated[str, Field(max_length=70)]] = Field(max_length=3000)
    nota: int | None = Field(default=None, ge=0, le=100)
    apelido: str | None = Field(default=None, max_length=10)  # limite dentro de `anyOf`
    rotulos: dict[str, Annotated[str, Field(max_length=80)]] = {}  # `additionalProperties`
    marcas: set[str] = set()  # `uniqueItems`: nenhum backend além da Anthropic o recebe
    tipo: Literal["a", "b"]
    sub: _Sub


def _pedido() -> Pedido:
    return Pedido(
        tarefa="encaixe",
        modelo="m1",
        mensagens=(Mensagem("system", "regras"), Mensagem("user", "dado")),
        esquema=_Exemplo,
        max_tokens=100,
        prazo_s=60,
        versao=3,
    )


def _valido(**muda: Any) -> dict[str, Any]:
    return {"texto": "t", "itens": ["a"], "tipo": "a", "sub": {"nome": "n"}} | muda


def _nos(esquema: dict[str, Any]) -> list[dict[str, Any]]:
    """Todo nó de esquema (não os nomes de campo em `properties` nem os de `$defs`)."""
    nos = [esquema]
    for chave, valor in esquema.items():
        if chave in ("properties", "$defs"):
            for filho in valor.values():
                nos += _nos(filho)
        elif chave == "anyOf":
            for filho in valor:
                nos += _nos(filho)
        elif chave in ("items", "additionalProperties") and isinstance(valor, dict):
            nos += _nos(valor)
    return nos


def _palavras(esquema: dict[str, Any]) -> set[str]:
    return {chave for no in _nos(esquema) for chave in no}


def test_falha_so_tem_os_motivos_do_desenho() -> None:
    assert set(get_args(Motivo)) == DO_BACKEND | DO_PEDIDO
    assert [Falha(m).motivo for m in get_args(Motivo)] == list(get_args(Motivo))


def test_falha_recusa_motivo_fora_da_lista() -> None:
    with pytest.raises(ValueError, match="motivo"):
        Falha("outro")  # type: ignore[arg-type]
    assert Falha("formato").motivo == "formato"  # controle


def test_cada_motivo_e_do_backend_ou_da_vaga() -> None:
    lados = {m: Falha(m).backend_ou_vaga for m in get_args(Motivo)}
    assert lados == {m: "backend" for m in DO_BACKEND} | {m: "vaga" for m in DO_PEDIDO}


@pytest.mark.parametrize("backend", sorted(PERMITIDAS))
def test_esquema_enviado_so_leva_palavras_permitidas(backend: str) -> None:
    completo = _Exemplo.model_json_schema()
    assert _palavras(completo) - _STRICT  # controle: o completo leva palavra de fora do strict
    enviado = esquema_para(backend, _Exemplo)
    assert sorted(_palavras(enviado) - PERMITIDAS[backend]) == []
    assert enviado["properties"].keys() == completo["properties"].keys()
    # o `strict` da OpenAI pede todo campo em `required` (o opcional vai como união com `null`)
    obrigatorios = list(completo["properties"]) if backend == "openai" else completo["required"]
    assert enviado["required"] == obrigatorios
    assert enviado["additionalProperties"] is False


class _Folha(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str
    apelido: str = ""


class _Restrito(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str = Field(pattern="^[a-z]+$")
    peso: float = Field(gt=0, lt=10, multiple_of=0.5)
    folha: _Folha | None = None


@pytest.mark.parametrize("backend", ["compativel", "gemini", "openai"])
def test_esquema_do_gemini_e_do_compativel_sem_as_palavras_que_o_gemini_nao_cita(
    backend: str,
) -> None:
    sem_no_gemini = {"pattern", "multipleOf", "exclusiveMinimum", "exclusiveMaximum"}
    assert _palavras(_Restrito.model_json_schema()) >= sem_no_gemini  # controle
    enviado = esquema_para(backend, _Restrito)
    assert _palavras(enviado) & sem_no_gemini == (sem_no_gemini if backend == "openai" else set())


def test_esquema_da_openai_poe_todo_campo_em_required_tambem_nos_defs() -> None:
    completo = _Restrito.model_json_schema()
    # controle: `folha` e `apelido` têm padrão
    assert completo["required"] == ["codigo", "peso"]
    assert completo["$defs"]["_Folha"]["required"] == ["nome"]
    enviado = esquema_para("openai", _Restrito)
    assert enviado["required"] == ["codigo", "peso", "folha"]
    assert enviado["$defs"]["_Folha"]["required"] == ["nome", "apelido"]
    assert esquema_para("gemini", _Restrito)["required"] == ["codigo", "peso"]


def _repeticoes(esquema: dict[str, Any]) -> list[int]:
    return sorted(no[p] for no in _nos(esquema) for p in REPETICAO if p in no)


def test_esquema_local_nao_passa_de_2000_repeticoes() -> None:
    assert _repeticoes(_Exemplo.model_json_schema()) == [10, 60, 70, 80, 3000, 5000]  # controle
    assert _repeticoes(esquema_para("local", _Exemplo)) == [10, 60, 70, 80]


@pytest.mark.parametrize("backend", ["compativel", "gemini", "openai"])
def test_esquema_strict_guarda_so_o_max_items(backend: str) -> None:
    # o teto de 2000 é do llama.cpp; o `strict` não aceita `maxLength` (desenho 5.1)
    assert _repeticoes(esquema_para(backend, _Exemplo)) == [3000]


def test_esquema_da_anthropic_e_o_inteiro() -> None:
    assert esquema_para("anthropic", _Exemplo) == _Exemplo.model_json_schema()


def test_esquema_para_recusa_backend_desconhecido() -> None:
    with pytest.raises(ValueError, match="backend"):
        esquema_para("outro", _Exemplo)


def test_pydantic_recusa_o_texto_longo_que_o_esquema_enviado_deixou_passar() -> None:
    enviado = esquema_para("openai", _Exemplo)
    assert "maxLength" not in enviado["properties"]["texto"]  # o serviço não barra o texto longo
    assert conferir(_pedido(), _valido(texto="x" * 5000), "openai").dados["texto"] == "x" * 5000
    for longo in (_valido(texto="x" * 5001), _valido(itens=["a"] * 3001)):
        with pytest.raises(Falha) as erro:
            conferir(_pedido(), longo, "openai")
        assert erro.value.motivo == "formato"
        # o texto da resposta não vai junto da falha (nunca ao log)
        assert erro.value.__suppress_context__ and erro.value.__cause__ is None


def test_conferir_recusa_campo_a_mais_e_monta_a_resposta() -> None:
    with pytest.raises(Falha) as erro:
        conferir(_pedido(), _valido(extra=1), "local")
    assert erro.value.motivo == "formato"
    assert conferir(_pedido(), _valido(), "local") == Resposta(
        dados=_valido(nota=None, apelido=None, rotulos={}, marcas=[]),
        backend="local",
        modelo="m1",
        versao=3,
    )


def test_backend_falso_grava_os_pedidos_e_devolve_o_que_esta_pronto() -> None:
    falso = BackendFalso([_valido(), Falha("limite"), _valido(extra=1)])
    backend: Backend = falso
    primeiro, segundo, terceiro = _pedido(), _pedido(), _pedido()
    assert backend.pedir(primeiro).dados == _valido(nota=None, apelido=None, rotulos={}, marcas=[])
    with pytest.raises(Falha) as limite:
        backend.pedir(segundo)
    assert limite.value.motivo == "limite"
    with pytest.raises(Falha) as formato:  # resposta pronta passa pela mesma conferência
        backend.pedir(terceiro)
    assert formato.value.motivo == "formato"
    assert len(falso.pedidos) == 3
    assert all(p is q for p, q in zip(falso.pedidos, (primeiro, segundo, terceiro), strict=True))


def test_ia_json_traz_prazos_limites_e_cortes() -> None:
    assert limites() == {
        "prazo_s": {"fora": 60, "local": 180},
        "prazo_teste_s": {"fora": 30, "local": 180},
        "max_tokens_teste": 256,  # o pedido curto do teste ao ligar (T416; desenho 5.6)
        "resposta_max_bytes": 1048576,
        "tarefas": {
            "encaixe": {
                "max_tokens": {"fora": 1024, "local": 448},
                "corte": {"inicio": 4000, "fim": 2000},
                "claude": "claude-haiku-5-5",  # o modelo do "Tudo Claude" (T415; desenho 5.2)
            },
            # sob pedido, no questionário do perfil (T437; D233)
            "perguntas": {"max_tokens": {"fora": 1024, "local": 512}, "claude": "claude-sonnet-5-5"},
        },
        "laco": {"max_por_rodada": 20, "max_tentativas": 2, "max_por_dia_fora": 200},
        "memoria_gib": {"modelo_4b_desde": 11, "aviso_lento_abaixo": 7},
    }


def test_pydantic_e_dependencia_direta() -> None:
    # D185.3: o núcleo importa o pydantic; antes ele só vinha pelo FastAPI
    raiz = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    assert "pydantic==2.14.3" in pyproject["project"]["dependencies"]
