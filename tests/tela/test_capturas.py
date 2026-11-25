"""Capturas para a conferência visual (T353, D206): as telas de `TELAS`, dois temas, duas larguras.

O job `capturas` do CI roda este arquivo no Chromium, no Firefox e no WebKit, com
`JOBOT_CAPTURAS` apontando a pasta que vira artefato. Sem a variável, as fotos vão para a pasta
temporária do teste e só se prova que cada tela abre.
As telas da 0.6.0 (T443): as abas Perfil e IA, os passos IA e Perfil da primeira execução e um
detalhe com a candidatura preparada, que o serviço falso deixou gravada (nada sai da máquina).
"""

import os
from contextlib import closing
from pathlib import Path
from typing import Literal

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from apoio.semear import AGORA
from jobot.banco import perfil
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.ia import Preparo, gravar_preparo
from jobot.sistema.cofre import Cofre

pytestmark = pytest.mark.tela

TELAS = {
    "panorama": "/panorama",
    "vagas": "/vagas",
    "detalhe": "/vagas/1",  # a primeira vaga que o `semear` grava
    "configuracoes": "/configuracoes/geral",
    "perfil": "/configuracoes/perfil",
    "ia": "/configuracoes/ia",
    "assistente-ia": "/primeira-execucao/ia",
    "assistente-perfil": "/primeira-execucao/perfil",
    "candidatura": "/vagas/2",  # a segunda semeada, com o preparo do serviço falso
}
CANDIDATURA = Preparo(
    idioma="pt",
    carta="Prezada equipe, trabalho com Python há três anos e quero conversar sobre a vaga.",
    resumo="Analista de sistemas com Python e SQL.",
    tem=("Python", "SQL"),
    faltam=("Kubernetes",),
    perguntar=("Tem disponibilidade para viagens?",),
    usou=("habilidades", "experiencias"),
    backend="gemini",
    modelo="gemini-falso",
    versao=1,
    feito_em=AGORA.isoformat(),
)

# as animações com fim (as sem fim só existem com trabalho em curso, D210.3)
_FIM_DAS_ANIMACOES = """() => Promise.all(document.getAnimations()
  .filter((a) => a.effect && a.effect.getComputedTiming().endTime !== Infinity)
  .map((a) => a.finished.catch(() => null)))"""


@pytest.fixture
def app_painel(app_painel: FastAPI, tmp_path: Path) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()  # o semeado é datado de `AGORA`
    cofre = Cofre(tmp_path, CofreFalso())  # a chave de um serviço pago, só no cofre falso
    cofre.gravar("ia_gemini", "chave-gemini-1234567890")
    app_painel.state.cofre = cofre
    app_painel.state.modelo_local = lambda: None
    app_painel.state.ia_pessoa = set()
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravar_config(con, "primeira_execucao_concluida", True)  # senão /panorama redireciona
        gravar_config(
            con, "ia_tarefas", {"candidatura": {"ligada": True, "backend": "gemini", "modelo": "g"}}
        )
        perfil.gravar_habilidades(con, ["Python", "SQL", "Git"], AGORA)
        perfil.gravar_experiencia(
            con, perfil.Experiencia("Analista de sistemas", "Empresa Exemplo", "2021-03")
        )
        perfil.gravar_curso(con, perfil.Curso("Análise e Desenvolvimento de Sistemas"))
        for pergunta in CANDIDATURA.perguntar:  # o que o preparo sugeriu espera o aceite (D234)
            perfil.gravar_pergunta(con, "ia:viagens", pergunta, "ia", AGORA, sugerida=True)
        gravar_preparo(con, 2, CANDIDATURA)
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
    # sem "networkidle": no Firefox ele às vezes não chega em 30 s (D208.6); basta não haver
    # pedido do htmx no ar depois do load
    page.wait_for_load_state("load")
    expect(page.locator(".htmx-request")).to_have_count(0)
    expect(page.locator("main")).to_be_visible()
    # a entrada do `main` (fundido de opacidade) termina antes da foto: o `animations="disabled"`
    # às vezes pegava o meio dela no Chromium, e a tela saía mais clara (D210.8)
    page.evaluate(_FIM_DAS_ANIMACOES)
    pasta = Path(os.environ.get("JOBOT_CAPTURAS") or tmp_path)
    pasta.mkdir(parents=True, exist_ok=True)
    foto = pasta / f"{browser_name}-{tela}-{tema}-{largura}.png"
    page.screenshot(path=foto, animations="disabled")
