"""O filtro de erros de console dos testes de tela (T352): só a fonte cortada pela navegação sai."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

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
