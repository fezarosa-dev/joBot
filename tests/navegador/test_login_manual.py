"""Fazer login agora pela janela comum, contra o site falso (T232; D136.1 a D136.8).

A janela comum aqui é falsa: no `abrir`, ela faz o papel da pessoa, abrindo o mesmo perfil e
visitando o site falso antes de fechar. Depois o joBot confere a sessão pela janela automática
em `url_entrada`.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from playwright.async_api import BrowserContext, Route, async_playwright

from apoio.cofre_falso import CofreFalso
from apoio.site_falso import LOCAIS, LeitorFalso, SiteFalso
from jobot.navegador import limites
from jobot.navegador.abrir import Lancar, abrir_contexto
from jobot.navegador.execucao import Dependencias
from jobot.navegador.janela_comum import Janela, JanelaComum
from jobot.navegador.login_manual import fazer_login
from jobot.navegador.politica import dentro_dos_hosts
from jobot.sistema.cofre import Cofre

pytestmark = [pytest.mark.tela, pytest.mark.anyio]

TELA = {"DISPLAY": ":0"}


@dataclass
class Montagem:
    """O navegador sem tela dos testes, com a rota que recusa tudo fora do loopback."""

    dados: Path
    lancar: Lancar
    contextos: list[BrowserContext] = field(default_factory=list)

    def deps(self) -> Dependencias:
        return Dependencias(
            dados=self.dados,
            lancar=self.lancar,
            ambiente=lambda: TELA,
            politica=lambda leitor: lambda url: dentro_dos_hosts(url, leitor.hosts),
            sortear=lambda: limites.ESPERA_MIN_S,
            cofre=Cofre(self.dados, CofreFalso()),
            avisar=lambda titulo, frase: None,
        )


@pytest.fixture
async def montagem(tmp_path: Path) -> AsyncIterator[Montagem]:
    recusados: list[str] = []

    async def filtrar(route: Route) -> None:
        if urlsplit(route.request.url).hostname in LOCAIS:
            await route.continue_()
        else:
            recusados.append(route.request.url)
            await route.abort()

    async with async_playwright() as playwright:

        async def lancar(**argumentos: Any) -> BrowserContext:
            argumentos.pop("channel", None)  # sempre o Chromium do Playwright, igual no CI
            contexto = await playwright.chromium.launch_persistent_context(
                **argumentos, headless=True
            )
            await contexto.route("**/*", filtrar)
            m.contextos.append(contexto)
            return contexto

        m = Montagem(tmp_path, lancar)
        try:
            yield m
        finally:
            for contexto in m.contextos:
                await contexto.close()
    assert recusados == [], f"pedido para fora do loopback: {recusados}"


class JanelaFalsa:
    """A janela da pessoa: o `wait()` volta na hora, ou só no `terminate()` se ela trava."""

    def __init__(self, trava: bool) -> None:
        self.sinais: list[str] = []
        self.saiu = asyncio.Event()
        if not trava:
            self.saiu.set()

    async def wait(self) -> int:
        await self.saiu.wait()
        return 0

    def terminate(self) -> None:
        self.sinais.append("terminate")
        self.saiu.set()

    def kill(self) -> None:
        self.sinais.append("kill")
        self.saiu.set()


def _janela_da_pessoa(
    montagem: Montagem, site: SiteFalso, caminho: str | None, *, trava: bool = False
) -> tuple[JanelaComum, JanelaFalsa, list[Sequence[str]]]:
    """No `abrir`, visita `caminho` no mesmo perfil e fecha, antes de devolver a janela."""
    falsa = JanelaFalsa(trava)
    abertas: list[Sequence[str]] = []

    async def achar() -> Path | None:
        return Path("/x/chrome")

    async def abrir(argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        abertas.append(argumentos)
        if caminho is not None:
            contexto = await abrir_contexto(montagem.dados, TELA, montagem.lancar)
            aba = await contexto.new_page()
            await aba.goto(site.url(caminho))
            await contexto.close()
        return falsa

    return JanelaComum(caminho=achar, abrir=abrir), falsa, abertas


def _leitor(site: SiteFalso, entrada: str = "/conta") -> LeitorFalso:
    return LeitorFalso.para(site, url_entrada=site.url(entrada))


async def test_login_pela_janela_comum_fica_pronto(montagem: Montagem, site: SiteFalso) -> None:
    janela, falsa, abertas = _janela_da_pessoa(montagem, site, "/entrar-guardado")
    resultado = await fazer_login(_leitor(site), montagem.deps(), janela)
    assert resultado == "pronto"
    assert len(abertas) == 1
    assert falsa.sinais == []  # a janela saiu sozinha: nenhum sinal
    assert site.visitas["/conta"] == 2  # a da pessoa e a conferência do joBot
    assert (site.posts, site.campos_mudados) == (0, 0)


async def test_janela_fechada_sem_login_da_nao_entrou(montagem: Montagem, site: SiteFalso) -> None:
    janela, _, _ = _janela_da_pessoa(montagem, site, "/login")  # abriu o login e não enviou
    assert await fazer_login(_leitor(site), montagem.deps(), janela) == "nao_entrou"
    assert site.visitas["/conta"] == 1  # a conferência
    assert (site.posts, site.campos_mudados) == (0, 0)


async def test_conta_que_aparece_depois_do_load_da_pronto(
    montagem: Montagem, site: SiteFalso
) -> None:
    janela, _, _ = _janela_da_pessoa(montagem, site, "/entrar-guardado")
    leitor = _leitor(site, "/conta-tardia")
    assert await fazer_login(leitor, montagem.deps(), janela) == "pronto"
    assert site.visitas["/conta-tardia/dados"] == 1


async def test_prazo_estourado_sem_login_da_tempo_esgotado(
    montagem: Montagem, site: SiteFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limites, "PRAZO_LOGIN_MANUAL_S", 0)
    monkeypatch.setattr(limites, "ESPERA_SAIR_JANELA_S", 0)
    janela, falsa, _ = _janela_da_pessoa(montagem, site, "/login", trava=True)
    assert await fazer_login(_leitor(site), montagem.deps(), janela) == "tempo_esgotado"
    assert falsa.sinais == ["terminate"]


async def test_prazo_estourado_com_login_da_pronto(
    montagem: Montagem, site: SiteFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limites, "PRAZO_LOGIN_MANUAL_S", 0)
    monkeypatch.setattr(limites, "ESPERA_SAIR_JANELA_S", 0)
    janela, falsa, _ = _janela_da_pessoa(montagem, site, "/entrar-guardado", trava=True)
    assert await fazer_login(_leitor(site), montagem.deps(), janela) == "pronto"
    assert falsa.sinais == ["terminate"]
