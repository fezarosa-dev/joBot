"""Pedido, Resposta, Falha e o `Protocol` dos backends de IA (desenho 5.1 da fase 4)."""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal, Protocol, get_args

from pydantic import BaseModel, ValidationError

Motivo = Literal[
    # do backend: a rodada para e a vaga não é marcada (desenho 5.4)
    "sem_chave",
    "chave_recusada",
    "sem_rede",
    "programa_ausente",
    "modelo_ausente",
    "tempo_esgotado",
    "limite",
    "esquema_recusado",
    "servico_fora",
    # do pedido: só a vaga leva a falha
    "recusa",
    "formato",
    "contexto",
]
_DA_VAGA = frozenset({"recusa", "formato", "contexto"})


class Falha(Exception):
    """Falha de uma chamada à IA, com um dos motivos fechados de `Motivo`. Não leva o texto do
    pedido nem o da resposta (o log só vê o motivo)."""

    def __init__(self, motivo: Motivo) -> None:
        if motivo not in get_args(Motivo):
            raise ValueError(f"motivo de falha desconhecido: {motivo!r}")
        super().__init__(motivo)
        self.motivo: Motivo = motivo

    @property
    def backend_ou_vaga(self) -> Literal["backend", "vaga"]:
        return "vaga" if self.motivo in _DA_VAGA else "backend"


@dataclass(frozen=True)
class Mensagem:
    papel: Literal["system", "user"]
    texto: str


@dataclass(frozen=True)
class Pedido:
    tarefa: str
    modelo: str
    mensagens: tuple[Mensagem, ...]
    esquema: type[BaseModel]  # o cliente o envia por `esquema_para` e confere com `conferir`
    max_tokens: int
    prazo_s: float
    versao: int  # `VERSAO` da tarefa, que volta na `Resposta`


@dataclass(frozen=True)
class Resposta:
    dados: dict[str, Any]
    backend: str
    modelo: str
    versao: int


class Backend(Protocol):
    def pedir(self, pedido: Pedido) -> Resposta:
        """Devolve a resposta conferida ou levanta `Falha`."""
        ...


def conferir(pedido: Pedido, dados: object, backend: str) -> Resposta:
    """Passa a saída do modelo pelo esquema pydantic da tarefa; não passou: `Falha("formato")`,
    sem repetir. Confere também os limites que `esquema_para` tirou do esquema enviado."""
    try:
        valido = pedido.esquema.model_validate(dados)
    except ValidationError:
        raise Falha("formato") from None  # o erro do pydantic cita o texto da resposta
    return Resposta(valido.model_dump(mode="json"), backend, pedido.modelo, pedido.versao)


@cache
def limites() -> dict[str, Any]:
    """Prazos, `max_tokens`, cortes e tetos de `nucleo/dados/ia.json` (propostas da D185)."""
    texto = (Path(__file__).parent.parent / "dados" / "ia.json").read_text(encoding="utf-8")
    dados: dict[str, Any] = json.loads(texto)
    return dados
