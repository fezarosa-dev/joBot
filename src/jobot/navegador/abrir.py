"""Abre o navegador visível com o perfil do joBot (D132.2, D132.3)."""

import logging
import os
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any, Literal

from playwright.async_api import BrowserContext, Playwright, async_playwright

from jobot.navegador.perfil import pasta_do_perfil, preparar_preferencias

_LOG = logging.getLogger(__name__)

# Onde o canal `chrome` do Playwright procura o Chrome no Linux (conferido na 1.65.1, E8).
CAMINHO_CHROME = Path("/opt/google/chrome/chrome")

# Recebe os mesmos argumentos de nome de `launch_persistent_context`.
Lancar = Callable[..., Awaitable[BrowserContext]]


class SemNavegador(Exception):
    """Nem o Chrome nem o Chromium do Playwright abriram."""


class SemTela(Exception):
    """Sem ambiente de tela gráfica."""


async def abrir_contexto(
    dados: Path, ambiente: Mapping[str, str], lancar: Lancar
) -> BrowserContext:
    """Abre o contexto persistente: Chrome primeiro, depois o Chromium do Playwright."""
    if not ambiente:
        raise SemTela("sem tela gráfica")
    perfil = pasta_do_perfil(dados)
    preparar_preferencias(perfil)
    try:
        return await lancar(user_data_dir=str(perfil), channel="chrome")
    except Exception:  # o motivo do Chrome não é o que a pessoa precisa ver; o do Chromium é
        _LOG.debug("Chrome não abriu; tentando o Chromium do Playwright")
    try:
        return await lancar(user_data_dir=str(perfil))
    except Exception:
        # a mensagem do Playwright pode trazer caminhos e variáveis: só no log, nunca na exceção
        _LOG.error("nenhum navegador abriu", exc_info=True)
        raise SemNavegador("nenhum navegador abriu") from None


def lancador_de_producao(playwright: Playwright, ambiente: Mapping[str, str]) -> Lancar:
    """Visível, sem argumento extra; o `env` do Playwright troca o ambiente inteiro."""

    async def lancar(**argumentos: Any) -> BrowserContext:
        return await playwright.chromium.launch_persistent_context(
            **argumentos, headless=False, env={**os.environ, **ambiente}
        )

    return lancar


async def navegador_instalado() -> Literal["chrome", "chromium"] | None:
    """Chrome pelo caminho; Chromium pelo `executable_path` (sobe o driver do Playwright)."""
    if CAMINHO_CHROME.exists():
        return "chrome"
    async with async_playwright() as playwright:
        if Path(playwright.chromium.executable_path).exists():
            return "chromium"
    return None
