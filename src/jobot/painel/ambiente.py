"""O que as rotas do painel leem do sistema: ambiente, executor de comando e plataforma.

O teste troca os sete em `app.state` (`ambiente`, `rodar_comando`, `plataforma`, `cofre`,
`abrir_processo`, `ler_navegador` e `leitores`); sem troca, vale o real. Os grupos de
Configurações moram aqui, abaixo das rotas, porque a lateral também os lê (T265).
"""

import os
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Literal

from fastapi import Request

from jobot.navegador import abrir, instalador
from jobot.navegador.janela_comum import AbrirJanela
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.leitores.registro import leitores
from jobot.sistema import segundo_plano_linux
from jobot.sistema.cofre import Cofre
from jobot.sistema.segundo_plano_linux import Rodar


def ambiente_do_painel(request: Request) -> Mapping[str, str]:
    ambiente: Mapping[str, str] | None = getattr(request.app.state, "ambiente", None)
    return os.environ if ambiente is None else ambiente


def rodar_do_painel(request: Request) -> Rodar:
    rodar: Rodar | None = getattr(request.app.state, "rodar_comando", None)
    return segundo_plano_linux.rodar_comando if rodar is None else rodar


def no_linux(request: Request) -> bool:
    return str(getattr(request.app.state, "plataforma", sys.platform)).startswith("linux")


def cofre_do_painel(request: Request) -> Cofre:
    cofre: Cofre | None = getattr(request.app.state, "cofre", None)
    return Cofre(request.app.state.banco.parent) if cofre is None else cofre


def abrir_instalador_do_painel(request: Request) -> AbrirJanela:
    """Quem abre o processo do instalador do navegador (T240)."""
    abridor: AbrirJanela | None = getattr(request.app.state, "abrir_processo", None)
    return instalador.abrir_instalador if abridor is None else abridor


LerNavegador = Callable[[], Awaitable[Literal["chrome", "chromium"] | None]]


def ler_navegador_do_painel(request: Request) -> LerNavegador:
    """Quem lê do disco qual navegador as janelas usam (sobe o driver do Playwright)."""
    ler: LerNavegador | None = getattr(request.app.state, "ler_navegador", None)
    return abrir.navegador_instalado if ler is None else ler


GRUPOS = (
    "geral",
    "fontes",
    "funcoes",
    "segundo-plano",
    "privacidade",
    "servicos",
    "contas",
    "ferramentas",
)
COM_LOGIN = "contas"
FERRAMENTAS = "ferramentas"
SO_COM_LEITOR = (COM_LOGIN, FERRAMENTAS)  # hoje a única ferramenta é o navegador do login


def grupos_visiveis(leitores: Sequence[LeitorComLogin]) -> tuple[str, ...]:
    """Os grupos da página: "Contas" e "Ferramentas" só existem com leitor registrado
    (D132.23, D137.12)."""
    return GRUPOS if leitores else tuple(g for g in GRUPOS if g not in SO_COM_LEITOR)


def leitores_do_painel(request: Request) -> Sequence[LeitorComLogin]:
    # o teste põe os leitores em `app.state` (E2); sem eles vale o registro
    registrados: Sequence[LeitorComLogin] = getattr(request.app.state, "leitores", leitores())
    return registrados
