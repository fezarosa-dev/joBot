"""Fazer login agora contra o site falso (T219; D132.18, D132.21, D132.52).

O joBot só abre a página de login e olha (`content()` e `url`) a cada intervalo: quem digita e
envia o formulário é o teste, no papel da pessoa.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from playwright.async_api import BrowserContext, Page, Route, async_playwright
from playwright.async_api import Error as ErroDoPlaywright

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from apoio.site_falso import LOCAIS, LeitorFalso, RelogioDoNavegador, SiteFalso
from jobot.navegador import limites
from jobot.navegador.abrir import Lancar
from jobot.navegador.execucao import Dependencias
from jobot.navegador.login_manual import fazer_login
from jobot.navegador.politica import dentro_dos_hosts
from jobot.sistema.cofre import Cofre

pytestmark = [pytest.mark.tela, pytest.mark.anyio]


@dataclass
class Montagem:
    """O navegador sem tela dos testes, com a rota que recusa tudo fora do loopback."""

    dados: Path
    lancar: Lancar
    contextos: list[BrowserContext] = field(default_factory=list)
    fechados: list[object] = field(default_factory=list)  # um por evento `close` do contexto

    def deps(self) -> Dependencias:
        return Dependencias(
            dados=self.dados,
            lancar=self.lancar,
            ambiente=lambda: {"DISPLAY": ":0"},
            politica=lambda leitor: lambda url: dentro_dos_hosts(url, leitor.hosts),
            sortear=lambda: limites.ESPERA_MIN_S,
            cofre=Cofre(self.dados, CofreFalso()),
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
            contexto.on("close", lambda c: m.fechados.append(c))
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


class RelogioComGancho(RelogioDoNavegador):
    """Na primeira dormida, faz o que a pessoa faria na janela enquanto o joBot espera."""

    def __init__(self, gancho: Callable[[], Awaitable[None]]) -> None:
        super().__init__()
        self.gancho: Callable[[], Awaitable[None]] | None = gancho

    async def dormir(self, s: float) -> None:
        await super().dormir(s)
        if self.gancho is not None:
            gancho, self.gancho = self.gancho, None
            await gancho()


def _aba_de_login(montagem: Montagem, site: SiteFalso) -> Page:
    (contexto,) = montagem.contextos
    return next(p for p in contexto.pages if p.url == site.url("/login"))


async def test_fazer_login_espera_e_fecha_quando_logado(
    montagem: Montagem, site: SiteFalso
) -> None:
    async def entrar() -> None:  # a pessoa digita e envia; o joBot só olha
        aba = _aba_de_login(montagem, site)
        for nome, valor in (("usuario", "pessoa"), ("senha", "s3gredo")):
            async with aba.expect_response("**/campo-mudou*"):
                await aba.locator(f"input[name={nome}]").fill(valor)
        async with aba.expect_navigation():
            await aba.locator("button").click()

    relogio = RelogioComGancho(entrar)
    resultado = await fazer_login(LeitorFalso.para(site), montagem.deps(), relogio)
    assert resultado == "pronto"
    assert len(montagem.fechados) == 1  # o evento `close` do contexto: o joBot fechou
    assert relogio.dormidas == [limites.INTERVALO_LOGIN_MANUAL_S]
    assert limites.INTERVALO_LOGIN_MANUAL_S == 5
    # só os dois campos e o envio do teste: o joBot não preencheu nem enviou nada
    assert (site.posts, site.campos_mudados) == (1, 2)
    assert site.visitas["/logado"] == 1  # a página logada que o envio abriu, sem nova visita


async def test_fazer_login_desiste_em_10_minutos(montagem: Montagem, site: SiteFalso) -> None:
    relogio = RelogioFalso()
    inicio = relogio.agora()
    resultado = await fazer_login(LeitorFalso.para(site), montagem.deps(), relogio)
    assert resultado == "tempo_esgotado"
    assert limites.PRAZO_LOGIN_MANUAL_S == 600
    assert relogio.agora() - inicio == timedelta(seconds=limites.PRAZO_LOGIN_MANUAL_S)
    assert len(relogio.dormidas) == limites.PRAZO_LOGIN_MANUAL_S / limites.INTERVALO_LOGIN_MANUAL_S
    assert set(relogio.dormidas) == {limites.INTERVALO_LOGIN_MANUAL_S}
    assert len(montagem.fechados) == 1
    assert site.visitas["/login"] == 1  # abriu a página uma vez e só leu, sem recarregar
    assert (site.posts, site.campos_mudados) == (0, 0)


async def test_fazer_login_com_o_navegador_fechado_pela_pessoa(
    montagem: Montagem, site: SiteFalso
) -> None:
    async def fechar() -> None:
        await montagem.contextos[-1].close()

    relogio = RelogioComGancho(fechar)
    resultado = await fazer_login(LeitorFalso.para(site), montagem.deps(), relogio)
    assert resultado == "fechado"
    assert len(montagem.fechados) == 1
    assert len(relogio.dormidas) == 1  # parou na leitura seguinte, sem esperar o prazo


async def test_cancelar_o_login_fecha_o_navegador(montagem: Montagem, site: SiteFalso) -> None:
    async def cancelar() -> None:  # o `serve` fecha (Ctrl+C) com a janela aberta
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await fazer_login(LeitorFalso.para(site), montagem.deps(), RelogioComGancho(cancelar))
    assert len(montagem.fechados) == 1


async def test_fazer_login_sem_tela(montagem: Montagem, site: SiteFalso) -> None:
    deps = replace(montagem.deps(), ambiente=lambda: {})
    assert await fazer_login(LeitorFalso.para(site), deps, RelogioFalso()) == "sem_tela"
    assert montagem.contextos == []


async def test_fazer_login_sem_navegador(montagem: Montagem, site: SiteFalso) -> None:
    async def nao_abre(**argumentos: Any) -> BrowserContext:
        raise RuntimeError("nenhum navegador")

    deps = replace(montagem.deps(), lancar=nao_abre)
    assert await fazer_login(LeitorFalso.para(site), deps, RelogioFalso()) == "sem_navegador"
    assert site.visitas["/login"] == 0


async def test_fechar_so_a_aba_de_login_desiste_e_fecha_o_navegador(
    montagem: Montagem, site: SiteFalso
) -> None:
    async def fechar_a_aba() -> None:  # a pessoa abre outra aba e fecha a de login
        await montagem.contextos[-1].new_page()
        await _aba_de_login(montagem, site).close()

    relogio = RelogioComGancho(fechar_a_aba)
    resultado = await fazer_login(LeitorFalso.para(site), montagem.deps(), relogio)
    assert resultado == "fechado"
    assert len(montagem.fechados) == 1  # o joBot fechou o contexto com a outra aba aberta


@dataclass
class LeitorQueAceitaVazio(LeitorFalso):
    """Um leitor que diria "logada" para texto e url vazios: o joBot não pode perguntar assim."""

    def pagina_logada(self, html: str, url: str) -> bool:
        return (html, url) == ("", "") or super().pagina_logada(html, url)


async def test_leitura_que_falha_nao_conta_como_logada(
    montagem: Montagem, site: SiteFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Page.content
    falhas: list[str] = []

    async def falha_uma_vez(self: Page) -> str:
        if not falhas:
            falhas.append("trocando")
            raise ErroDoPlaywright("a página está trocando")
        return await original(self)

    monkeypatch.setattr(Page, "content", falha_uma_vez)
    relogio = RelogioFalso()
    resultado = await fazer_login(LeitorQueAceitaVazio.para(site), montagem.deps(), relogio)
    assert falhas == ["trocando"]
    assert resultado == "tempo_esgotado"  # a leitura que falhou não virou "pronto"
    assert len(montagem.fechados) == 1
