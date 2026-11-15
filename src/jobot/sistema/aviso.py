"""Aviso no computador pelo `notify-send` (D132.10).

Dentro do container o aviso passa pelo host (`distrobox-host-exec`). Sem `notify-send` no
sistema (código 127), fica só o aviso do painel; outra falha vai só ao log, sem o texto.
"""

import logging
from collections.abc import Mapping

from jobot.sistema.caso import prefixo_host
from jobot.sistema.segundo_plano_linux import Rodar

_LOG = logging.getLogger(__name__)


def avisar(titulo: str, frase: str, env: Mapping[str, str], rodar: Rodar) -> None:
    resultado = rodar([*prefixo_host(env), "notify-send", titulo, frase])
    if resultado.codigo == 127:
        _LOG.debug("aviso no computador: sem notify-send")
    elif resultado.codigo != 0:
        _LOG.warning("aviso no computador: notify-send saiu com código %s", resultado.codigo)
