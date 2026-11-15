"""Variáveis da tela gráfica, lidas do ambiente ou do systemd do usuário."""

import logging
import os
import re
from collections.abc import Mapping

from jobot.sistema.caso import prefixo_host
from jobot.sistema.segundo_plano_linux import Rodar

_LOG = logging.getLogger(__name__)

VARIAVEIS = ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR")


_DISPLAY = re.compile(r"[A-Za-z0-9.-]*:[0-9]+(\.[0-9]+)?")
_NOME_WAYLAND = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")


def _absoluto(valor: str) -> bool:
    return valor.startswith("/") and "\0" not in valor and "\n" not in valor


def _valida(nome: str, valor: str) -> bool:
    if nome == "DISPLAY":
        return _DISPLAY.fullmatch(valor) is not None
    if nome == "WAYLAND_DISPLAY":
        return _NOME_WAYLAND.fullmatch(valor) is not None or _absoluto(valor)
    return _absoluto(valor) and os.path.exists(valor)  # XAUTHORITY, XDG_RUNTIME_DIR


def _validas(origem: Mapping[str, str]) -> dict[str, str]:
    return {n: origem[n] for n in VARIAVEIS if n in origem and _valida(n, origem[n])}


def ambiente_da_tela(env: Mapping[str, str], rodar: Rodar) -> dict[str, str]:
    """Vazio quer dizer sem tela. Só os nomes aceitos vão ao log, nunca os valores.

    Sem DISPLAY nem WAYLAND_DISPLAY válido o retorno é vazio, mesmo com XAUTHORITY ou
    XDG_RUNTIME_DIR: sem um dos dois não há tela.
    """
    achadas = _validas(env)
    if "DISPLAY" not in achadas and "WAYLAND_DISPLAY" not in achadas:
        resultado = rodar([*prefixo_host(env), "systemctl", "--user", "show-environment"])
        achadas = {}
        if resultado.codigo != 0:
            _LOG.warning("tela: systemctl show-environment saiu com código %s", resultado.codigo)
        else:
            linhas = (linha.partition("=") for linha in resultado.saida.splitlines())
            achadas = _validas({n: v for n, _, v in linhas if n in VARIAVEIS})
        if "DISPLAY" not in achadas and "WAYLAND_DISPLAY" not in achadas:
            achadas = {}
    _LOG.info("tela: variáveis aceitas: %s", ", ".join(achadas) or "nenhuma")
    return achadas
