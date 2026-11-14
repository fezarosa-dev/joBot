"""O que as rotas do painel leem do sistema: ambiente, executor de comando e plataforma.

O teste troca os três em `app.state` (`ambiente`, `rodar_comando`, `plataforma`); sem troca, vale
o real.
"""

import os
import sys
from collections.abc import Mapping

from fastapi import Request

from jobot.sistema import segundo_plano_linux
from jobot.sistema.segundo_plano_linux import Rodar


def ambiente_do_painel(request: Request) -> Mapping[str, str]:
    ambiente: Mapping[str, str] | None = getattr(request.app.state, "ambiente", None)
    return os.environ if ambiente is None else ambiente


def rodar_do_painel(request: Request) -> Rodar:
    rodar: Rodar | None = getattr(request.app.state, "rodar_comando", None)
    return segundo_plano_linux.rodar_comando if rodar is None else rodar


def no_linux(request: Request) -> bool:
    return str(getattr(request.app.state, "plataforma", sys.platform)).startswith("linux")
