"""O lugar da marca de instalação do Chromium do Playwright (T240; D137.6).

Roda no CI, com o Chromium baixado: prende que uma troca de versão do Playwright não mude onde
o `caminho_do_navegador` procura a marca.
"""

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

pytestmark = [pytest.mark.tela, pytest.mark.anyio]


async def test_chromium_do_playwright_tem_a_marca() -> None:
    async with async_playwright() as playwright:
        executavel = Path(playwright.chromium.executable_path)
    assert executavel.exists()
    assert (executavel.parents[1] / "INSTALLATION_COMPLETE").exists()
