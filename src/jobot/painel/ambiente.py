"""O que as rotas do painel leem do sistema: ambiente, executor de comando e plataforma.

O teste troca os onze em `app.state` (`ambiente`, `rodar_comando`, `plataforma`, `cofre`,
`abrir_processo`, `ler_navegador`, `leitores`, `abrir_imap`, `lancar_atualizacao`,
`abrir_endereco` e `abrir_ia_local`); sem troca, vale o real. Os grupos de
Configurações moram aqui, abaixo das rotas, porque a lateral também os lê (T265).
"""

import os
import sys
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal, Protocol

from fastapi import Request

from jobot.navegador import abrir, instalador
from jobot.navegador.janela_comum import AbrirJanela
from jobot.nucleo import gmail
from jobot.nucleo.gmail import AbrirImap
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.leitores.registro import leitores
from jobot.sistema import ia_local, segundo_plano, segundo_plano_linux
from jobot.sistema.abrir import abrir_navegador
from jobot.sistema.atualizar import lancar_atualizacao
from jobot.sistema.cofre import Cofre
from jobot.sistema.segundo_plano_linux import Rodar


def ambiente_do_painel(request: Request) -> Mapping[str, str]:
    ambiente: Mapping[str, str] | None = getattr(request.app.state, "ambiente", None)
    return os.environ if ambiente is None else ambiente


def rodar_do_painel(request: Request) -> Rodar:
    rodar: Rodar | None = getattr(request.app.state, "rodar_comando", None)
    return segundo_plano_linux.rodar_comando if rodar is None else rodar


def plataforma_do_painel(request: Request) -> str:
    return str(getattr(request.app.state, "plataforma", sys.platform))


def com_segundo_plano(request: Request) -> bool:
    """O sistema tem segundo plano (desenho 6.5); fora dele a tela e o passo 2 vêm desativados."""
    return segundo_plano.suportado(plataforma_do_painel(request))


def cofre_do_painel(request: Request) -> Cofre:
    cofre: Cofre | None = getattr(request.app.state, "cofre", None)
    return Cofre(request.app.state.banco.parent) if cofre is None else cofre


def imap_do_painel(request: Request) -> AbrirImap:
    """Quem abre a conexão IMAP do Gmail (T278); o teste põe um falso, a rede está fechada."""
    abrir_imap: AbrirImap | None = getattr(request.app.state, "abrir_imap", None)
    return gmail.abrir_imap_ssl if abrir_imap is None else abrir_imap


class ComandoIA(Protocol):
    """O `jobot ferramentas ... ia-local` rodando: as linhas JSON da saída e o fim."""

    @property
    def stdout(self) -> AsyncIterable[bytes] | None: ...
    async def wait(self) -> int: ...
    def kill(self) -> None: ...


AbrirComandoIA = Callable[[Sequence[str], Path], Awaitable[ComandoIA]]


def abrir_ia_local_do_painel(request: Request) -> AbrirComandoIA:
    """Quem roda o `jobot ferramentas ... ia-local` da tela Ferramentas (T417)."""
    abrir_ia: AbrirComandoIA | None = getattr(request.app.state, "abrir_ia_local", None)
    return ia_local.abrir_comando if abrir_ia is None else abrir_ia


def abrir_instalador_do_painel(request: Request) -> AbrirJanela:
    """Quem abre o processo do instalador do navegador (T240)."""
    abridor: AbrirJanela | None = getattr(request.app.state, "abrir_processo", None)
    return instalador.abrir_instalador if abridor is None else abridor


LerNavegador = Callable[[], Awaitable[Literal["chrome", "chromium"] | None]]


def ler_navegador_do_painel(request: Request) -> LerNavegador:
    """Quem lê do disco qual navegador as janelas usam (sobe o driver do Playwright)."""
    ler: LerNavegador | None = getattr(request.app.state, "ler_navegador", None)
    return abrir.navegador_instalado if ler is None else ler


class Rodando(Protocol):
    def poll(self) -> int | None: ...


LancarAtualizacao = Callable[[Path, Mapping[str, str]], Rodando]


def lancar_atualizacao_do_painel(request: Request) -> LancarAtualizacao:
    """Quem dispara o `jobot atualizar` destacado (T332)."""
    lancar: LancarAtualizacao | None = getattr(request.app.state, "lancar_atualizacao", None)
    return lancar_atualizacao if lancar is None else lancar


def abrir_endereco_do_painel(request: Request) -> Callable[[str], bool]:
    """Quem abre um endereço no navegador da pessoa, pelo Python (T332: a página da release)."""
    abrir: Callable[[str], bool] | None = getattr(request.app.state, "abrir_endereco", None)
    if abrir is not None:
        return abrir
    ambiente = ambiente_do_painel(request)
    return lambda endereco: abrir_navegador(endereco, ambiente)


# todos sempre na página: Ferramentas tem o modelo local mesmo sem leitor (D185.20); o cartão do
# navegador e as ações de "Contas" é que pedem leitor registrado
GRUPOS = (
    "geral",
    "fontes",
    "funcoes",
    "perfil",
    "ia",
    "segundo-plano",
    "privacidade",
    "servicos",
    "contas",
    "ferramentas",
)
COM_LOGIN = "contas"


def leitores_do_painel(request: Request) -> Sequence[LeitorComLogin]:
    # o teste põe os leitores em `app.state` (E2); sem eles vale o registro
    registrados: Sequence[LeitorComLogin] = getattr(request.app.state, "leitores", leitores())
    return registrados
