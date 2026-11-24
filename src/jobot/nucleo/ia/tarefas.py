"""Tarefas da IA (desenho 5.2 da fase 4): esquema de saída, `VERSAO` e a conferência no código."""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from jobot.nucleo.texto import normalizar, sem_pontas

# Sobe quando o texto do pedido (`pedidos.py`) ou o esquema da tarefa mudam: a chave do laço muda e
# a vaga é pedida de novo (desenho 5.1 e 5.4).
VERSAO = {"encaixe": 1}


class SaidaEncaixe(BaseModel):
    """O que o modelo devolve no `encaixe`: só o que a vaga pede. `tem` e `faltam` são do código."""

    model_config = ConfigDict(extra="forbid")
    pede: list[Annotated[str, Field(max_length=60)]] = Field(max_length=30)


def pede_da_vaga(pede: list[str], texto: str) -> list[str]:
    """Anti-invenção: fica só o item que aparece, normalizado e como palavra inteira, no texto
    enviado ao modelo (`TextoVaga.texto`); repetidos e vazios saem, na ordem da resposta."""
    alvo = normalizar(texto)
    vistos: set[str] = set()
    ficam = []
    for item in pede:
        limpo = sem_pontas(item)
        forma = normalizar(limpo)
        if not forma or forma in vistos:
            continue
        if re.search(rf"(?<![\w+#]){re.escape(forma)}(?![\w+#])", alvo):
            vistos.add(forma)
            ficam.append(limpo)
    return ficam


# Esqueleto da T432 (só para o vermelho): campos soltos, sem conferência.
from collections.abc import Mapping, Sequence  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Any  # noqa: E402

VERSAO.update(curriculo=0, perguntas=0, candidatura=0)


class SaidaCurriculo(BaseModel):
    cargo_atual: Any = None
    anos_de_experiencia: Any = None
    formacao_nivel: Any = None
    resumo: Any = None
    habilidades: Any = []
    idiomas_falados: Any = []
    experiencias: Any = []
    cursos: Any = []


class SaidaPerguntas(BaseModel):
    perguntas: Any = []


class SaidaCandidatura(BaseModel):
    idioma: Any = None
    carta: Any = None
    resumo: Any = None
    perguntar: Any = []
    usou: Any = []


def nao_achei(dados: Mapping[str, Any], texto: str) -> frozenset[str]:
    return frozenset()


def perguntas_que_ficam(
    itens: Sequence[Mapping[str, Any]], feitas: Sequence[str]
) -> list[dict[str, str]]:
    return [dict(item) for item in itens]


@dataclass(frozen=True)
class Candidatura:
    idioma: str
    carta: str
    resumo: str
    tem: tuple[str, ...]
    faltam: tuple[str, ...]
    perguntar: tuple[str, ...]
    usou: tuple[str, ...]
    citados: tuple[str, ...]


def conferir_candidatura(
    dados: Mapping[str, Any],
    enviados: Mapping[str, object],
    pede: Sequence[str] | None,
    feitas: Sequence[str],
) -> Candidatura:
    return Candidatura(
        dados["idioma"],
        dados["carta"],
        dados["resumo"],
        (),
        (),
        tuple(dados["perguntar"]),
        tuple(dados["usou"]),
        (),
    )
