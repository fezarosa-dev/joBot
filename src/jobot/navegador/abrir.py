"""Abre o navegador visível com o perfil do joBot (D132.2, D132.3)."""

import logging
import os
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any, Final, Literal

from playwright.async_api import BrowserContext, Playwright, async_playwright

from jobot.navegador.perfil import pasta_do_perfil, preparar_preferencias

_LOG = logging.getLogger(__name__)

# Onde o canal `chrome` do Playwright procura o Chrome no Linux (conferido na 1.65.1, E8).
CAMINHO_CHROME = Path("/opt/google/chrome/chrome")

# Do ambiente do `serve` só o que o Chrome lê (pastas, área de trabalho, usuário, idioma);
# nenhuma carrega segredo. O resto, token e chave de API inclusos, não passa (D135.10).
VARIAVEIS_DO_NAVEGADOR: Final = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "LANGUAGE",
    "TMPDIR",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "XDG_DATA_DIRS",
    "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_TYPE",
    "DBUS_SESSION_BUS_ADDRESS",
)

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
    # sem download e sem service worker: a resposta vem da rede e `response` segue (D135.9)
    base: dict[str, Any] = {
        "user_data_dir": str(perfil),
        "accept_downloads": False,
        "service_workers": "block",
    }
    try:
        return await lancar(**base, channel="chrome")
    except Exception:  # o motivo do Chrome não é o que a pessoa precisa ver; o do Chromium é
        _LOG.debug("Chrome não abriu; tentando o Chromium do Playwright")
    try:
        return await lancar(**base)
    except Exception:
        # a mensagem do Playwright pode trazer caminhos e variáveis: só no log, nunca na exceção
        _LOG.error("nenhum navegador abriu", exc_info=True)
        raise SemNavegador("nenhum navegador abriu") from None


def lancador_de_producao(playwright: Playwright, ambiente: Mapping[str, str]) -> Lancar:
    """Visível, sem argumento extra; o `env` do Playwright troca o ambiente inteiro.

    Vai só `VARIAVEIS_DO_NAVEGADOR` (as que existirem em `os.environ`) mais o `ambiente` da
    tela já validado; o resto do ambiente do `serve` não chega ao navegador.
    """
    base = {n: os.environ[n] for n in VARIAVEIS_DO_NAVEGADOR if n in os.environ}

    async def lancar(**argumentos: Any) -> BrowserContext:
        return await playwright.chromium.launch_persistent_context(
            **argumentos, headless=False, env={**base, **ambiente}
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
