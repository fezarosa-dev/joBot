"""Capturas para a conferência visual (T353, D206): quatro telas, dois temas, duas larguras.

O job `capturas` do CI roda este arquivo no Chromium, no Firefox e no WebKit, com
`JOBOT_CAPTURAS` apontando a pasta que vira artefato. Sem a variável, as fotos vão para a pasta
temporária do teste e só se prova que cada tela abre.
"""

import os
from contextlib import closing
from pathlib import Path
from typing import Literal

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela

TELAS = {
    "panorama": "/panorama",
    "vagas": "/vagas",
    "detalhe": "/vagas/1",  # a primeira vaga que o `semear` grava
    "configuracoes": "/configuracoes/geral",
}


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()  # o semeado é datado de `AGORA`
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravar_config(con, "primeira_execucao_concluida", True)  # senão /panorama redireciona
    return app_painel


@pytest.mark.parametrize("largura", [1280, 800])
@pytest.mark.parametrize("tema", ["light", "dark"])
@pytest.mark.parametrize("tela", list(TELAS))
def test_captura(
    page: Page,
    painel: str,
    browser_name: str,
    tmp_path: Path,
    tela: str,
    tema: Literal["light", "dark"],
    largura: int,
) -> None:
    page.set_viewport_size({"width": largura, "height": 900})
    page.emulate_media(color_scheme=tema)  # o tema padrão segue o sistema
    resposta = page.goto(painel + TELAS[tela])
    assert resposta is not None and resposta.ok
    page.wait_for_load_state("networkidle")
    expect(page.locator("main")).to_be_visible()
    pasta = Path(os.environ.get("JOBOT_CAPTURAS") or tmp_path)
    pasta.mkdir(parents=True, exist_ok=True)
    foto = pasta / f"{browser_name}-{tela}-{tema}-{largura}.png"
    page.screenshot(path=foto, animations="disabled")
