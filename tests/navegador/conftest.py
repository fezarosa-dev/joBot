"""Fixtures dos testes de navegador: site falso e contexto sem tela (`apoio/site_falso.py`), e o
Playwright da sessão."""

from collections.abc import AsyncIterator

import pytest
from playwright.async_api import Playwright, async_playwright

from apoio.site_falso import contexto_de_teste, politica_local, site

__all__ = ["contexto_de_teste", "politica_local", "site"]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    # de sessão: o Playwright abaixo vive no laço do anyio, que fica o mesmo enquanto ele viver
    return "asyncio"


@pytest.fixture(scope="session")
async def playwright_da_sessao() -> AsyncIterator[Playwright]:
    """Um Playwright por processo (por parte no CI): subir e descer o driver custa 0,5 a 0,9 s
    por teste (T295). Cada teste segue com o seu navegador e o seu contexto."""
    async with async_playwright() as playwright:
        yield playwright
