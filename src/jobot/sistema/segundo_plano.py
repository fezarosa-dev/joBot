"""Segundo plano por sistema (desenho 6.5): uma função só para a tela e o assistente.

Linux usa o systemd (`segundo_plano_linux`); Windows, o Agendador de Tarefas
(`segundo_plano_windows`). Fora deles o segundo plano fica desativado.
"""

import sys
from collections.abc import Mapping

from jobot.sistema import segundo_plano_linux, segundo_plano_windows
from jobot.sistema.segundo_plano_linux import Estado, Rodar

Ambiente = Mapping[str, str] | None


def _qual(plataforma: str | None) -> str:
    p = sys.platform if plataforma is None else plataforma
    if p.startswith("linux"):
        return "linux"
    return "windows" if p == "win32" else p


def suportado(plataforma: str | None = None) -> bool:
    return _qual(plataforma) in ("linux", "windows")


def ligar(rodar: Rodar, *, env: Ambiente = None, plataforma: str | None = None) -> None:
    qual = _qual(plataforma)
    if qual == "linux":
        segundo_plano_linux.ligar(rodar, env=env)
    elif qual == "windows":
        segundo_plano_windows.ligar(rodar)
    else:
        raise ValueError(f"segundo plano não existe em {qual}")


def desligar(rodar: Rodar, *, env: Ambiente = None, plataforma: str | None = None) -> None:
    qual = _qual(plataforma)
    if qual == "linux":
        segundo_plano_linux.desligar(rodar, env=env)
    elif qual == "windows":
        segundo_plano_windows.desligar(rodar)


def status(rodar: Rodar, *, env: Ambiente = None, plataforma: str | None = None) -> Estado:
    qual = _qual(plataforma)
    if qual == "linux":
        return segundo_plano_linux.status(rodar, env=env)
    if qual == "windows":
        return segundo_plano_windows.status(rodar)
    return Estado(habilitado=False, ativo=False)


def criar_atalho(rodar: Rodar, *, env: Ambiente = None, plataforma: str | None = None) -> None:
    """Atalho do menu só no Linux: no Windows o instalador da casca (NSIS) já cria."""
    if _qual(plataforma) == "linux":
        segundo_plano_linux.criar_atalho(rodar, env=env)
