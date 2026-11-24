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

# Do ambiente do `serve` só o que o Chrome lê (pastas, área de trabalho, usuário, idioma; no
# Windows, as pastas do sistema: sem SYSTEMROOT o Winsock não carrega); nenhuma carrega segredo.
# O resto, token e chave de API inclusos, não passa (D135.10).
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
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "USERNAME",
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


def ambiente_do_navegador(ambiente: Mapping[str, str]) -> dict[str, str]:
    """O ambiente das duas janelas: só `VARIAVEIS_DO_NAVEGADOR` (as que existirem em
    `os.environ`) mais o `ambiente` da tela já validado; o resto do `serve` não passa."""
    return {**{n: os.environ[n] for n in VARIAVEIS_DO_NAVEGADOR if n in os.environ}, **ambiente}


def lancador_de_producao(playwright: Playwright, ambiente: Mapping[str, str]) -> Lancar:
    """Visível, sem argumento extra; o `env` do Playwright troca o ambiente inteiro."""
    env: dict[str, str | float | bool] = {**ambiente_do_navegador(ambiente)}

    async def lancar(**argumentos: Any) -> BrowserContext:
        return await playwright.chromium.launch_persistent_context(
            **argumentos, headless=False, env=env
        )

    return lancar


async def caminho_do_navegador() -> Path | None:
    """O Chrome se existe; senão o Chromium do Playwright (sobe o driver); senão `None`."""
    # shortcut: escolhe o Chrome só porque o arquivo existe; se o canal chrome do Playwright
    # falhar, o abrir_contexto cai no Chromium com o mesmo perfil, e os cookies v10 com
    # --password-store=basic foram conferidos só no Chromium; mudar se aparecer sessão perdida
    # nessa troca
    if CAMINHO_CHROME.exists():
        return CAMINHO_CHROME
    return await chromium_do_jobot()


async def chromium_do_jobot() -> Path | None:
    """Só o Chromium do Playwright (sobe o driver), se o arquivo existe; não olha o Chrome."""
    async with async_playwright() as playwright:
        chromium = Path(playwright.chromium.executable_path)
    # o Playwright grava a marca no fim do download: sem ela o Chromium está pela metade
    # shortcut: marca conferida só em Linux e Windows; revisar quando o Mac entrar
    pronto = chromium.exists() and (chromium.parents[1] / "INSTALLATION_COMPLETE").exists()
    return chromium if pronto else None


async def navegador_instalado() -> Literal["chrome", "chromium"] | None:
    """Qual navegador as duas janelas usam, pelo `caminho_do_navegador`."""
    caminho = await caminho_do_navegador()
    if caminho is None:
        return None
    return "chrome" if caminho == CAMINHO_CHROME else "chromium"
