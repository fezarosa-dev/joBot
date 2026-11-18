"""O filtro de erros de console dos testes de tela (T352): só a fonte cortada pela navegação sai."""

import json
import shutil
import subprocess
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest
from playwright.sync_api import Page

from apoio.console import anotar_erros

CORTADA = (
    'downloadable font: download failed (font-family: "Inter" style:normal weight:100..900'
    " width:100 src index:0): status=2152398850 source: http://127.0.0.1:1/static/x.woff2"
)


class _Pagina:
    def __init__(self) -> None:
        self.ouvintes: dict[str, Callable[[Any], None]] = {}

    def on(self, evento: str, ouvinte: Callable[[Any], None]) -> None:
        self.ouvintes[evento] = ouvinte

    def add_init_script(self, script: str) -> None:
        self.script = script

    def console(self, tipo: str, texto: str) -> None:
        self.ouvintes["console"](SimpleNamespace(type=tipo, text=texto))


def test_guarda_erros_e_tira_so_a_fonte_cortada() -> None:
    pagina = _Pagina()
    erros = anotar_erros(cast(Page, pagina))
    pagina.console("error", CORTADA)
    pagina.console("warning", "aviso qualquer")
    pagina.console("error", CORTADA.replace("2152398850", "2147746065"))  # outra falha da fonte
    pagina.console("error", "Refused to apply inline style (style-src-attr)")
    pagina.ouvintes["pageerror"](ValueError("quebrou"))
    assert erros == [
        CORTADA.replace("2152398850", "2147746065"),
        "Refused to apply inline style (style-src-attr)",
        "quebrou",
    ]


def test_ignorar_tira_so_o_trecho_pedido() -> None:
    pagina = _Pagina()
    erros = anotar_erros(cast(Page, pagina), ignorar="422")
    pagina.console("error", "Failed to load resource: 422")
    pagina.console("error", "Failed to load resource: 500")
    assert erros == ["Failed to load resource: 500"]


_NODE = shutil.which("node")

# `window` e `console` falsos: o script do `anotar_erros` roda como no navegador, e cada chamada
# diz se saiu como erro ou como aviso
_PREPARO = """
const ouvintes = {};
globalThis.window = globalThis;
globalThis.addEventListener = (nome, f) => { ouvintes[nome] = f; };
const saidas = [];
globalThis.console = {
  error: (...p) => saidas.push(['erro', p[0]]),
  warn: (...p) => saidas.push(['aviso', p[0]]),
};
"""
_PASSOS = """
console.error('htmx:sendError');
ouvintes.beforeunload();
console.error('htmx:sendError');
console.error('htmx:afterRequest');
console.error('htmx:responseError');
console.error('outro');
ouvintes.pageshow();
console.error('htmx:sendError');
ouvintes.pagehide();
console.error('htmx:sendError');
process.stdout.write(JSON.stringify(saidas));
"""


@pytest.mark.skipif(_NODE is None, reason="precisa do node")
def test_erro_do_htmx_so_vira_aviso_com_a_pagina_saindo() -> None:
    pagina = _Pagina()
    anotar_erros(cast(Page, pagina))
    codigo = _PREPARO + pagina.script + _PASSOS
    saida = subprocess.run([str(_NODE), "-e", codigo], capture_output=True, text=True, timeout=20)
    assert saida.returncode == 0, saida.stderr
    assert json.loads(saida.stdout) == [
        ["erro", "htmx:sendError"],  # página parada: conta
        ["aviso", "htmx:sendError"],
        ["aviso", "htmx:afterRequest"],
        ["erro", "htmx:responseError"],  # outro erro do htmx conta mesmo saindo
        ["erro", "outro"],
        ["erro", "htmx:sendError"],  # a página voltou (pageshow)
        ["aviso", "htmx:sendError"],
    ]
