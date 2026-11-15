"""Dados que o navegador entrega ao leitor e o protocolo `LeitorComLogin` (desenho A4)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.modelo import VagaColetada

ParadaLogin = Literal["precisa_login", "bloqueio", "captcha", "no_limite"]


@dataclass(frozen=True)
class RespostaCapturada:
    url: str
    status: int
    tipo: str
    texto: str


@dataclass(frozen=True)
class Captura:
    url: str
    status: int
    html: str
    respostas: tuple[RespostaCapturada, ...]


@dataclass(frozen=True)
class EscopoLogado:
    id: str  # vai para `escopo` da saúde e de `VagaColetada`
    url: str


@dataclass(frozen=True)
class Leitura:
    vagas: tuple[VagaColetada, ...]
    pulados: int
    formato_mudou: bool


class LeitorComLogin(Protocol):
    chave: str  # termina em `_logado`
    nome: str
    hosts: tuple[str, ...]
    url_login: str
    url_entrada: str
    prefixos_login: tuple[str, ...]
    respostas: tuple[str, ...]
    campos_conta: tuple[str, ...]
    rolar: bool
    lista_tem_descricao: bool
    lista_exaustiva: bool  # falso: a vaga ausente só fecha depois de `JANELA_PARCIAL`

    def escopos(self, ctx: ContextoColeta) -> Sequence[EscopoLogado]: ...

    def e_login(self, captura: Captura) -> bool: ...

    def pagina_logada(self, html: str, url: str) -> bool: ...

    def pagina_bloqueada(self, html: str, url: str) -> bool: ...

    def proxima(self, captura: Captura) -> str | None: ...

    def ler(self, captura: Captura, escopo: EscopoLogado) -> Leitura: ...

    def detalhar(self, captura: Captura, vaga: VagaColetada) -> VagaColetada | None: ...
