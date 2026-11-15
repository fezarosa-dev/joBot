"""Cola do CAPTCHA na navegação com login, contra o site falso (T216; desenho A7 e A8).

O 2Captcha é um `httpx.MockTransport`; a chave é inventada e mora num `CofreFalso`.
"""

import ast
import asyncio
import json
import logging
import sqlite3
import threading
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.async_api import BrowserContext, Page, Route, async_playwright
from playwright.async_api import Error as ErroDoPlaywright
from playwright.async_api import TimeoutError as EstouroDoPlaywright

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from apoio.site_falso import (
    CHAVE_INVISIVEL,
    CHAVE_TURNSTILE,
    CHAVE_V2,
    CHAVE_V3,
    LOCAIS,
    LeitorFalso,
    RelogioDoNavegador,
    SiteFalso,
)
from jobot.banco.cadastros import gravar_config, ler_config, semear_leitores
from jobot.banco.captcha import NOME_NO_COFRE
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.navegador import execucao, limites
from jobot.navegador.abrir import Lancar
from jobot.navegador.captcha import ChaveDoCofre, Cola, Widget, achar_widget
from jobot.navegador.execucao import Dependencias, dependencias_de_producao, executar_login
from jobot.navegador.pagina import visitar
from jobot.navegador.politica import Politica, dentro_dos_hosts
from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.nucleo.leitores.base import Captura, EscopoLogado
from jobot.sistema import cofre as modulo_cofre
from jobot.sistema.cofre import Cofre, OndeGuardou

pytestmark = [pytest.mark.tela, pytest.mark.anyio]

CHAVE = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"  # inventada
TOKEN = "TOKEN-FALSO-DO-2CAPTCHA"
ESCOPO = EscopoLogado("python", "")
SRC = Path(__file__).resolve().parents[2] / "src"


@dataclass
class Api2Captcha:
    """O 2Captcha falso: abre a tarefa 7 e a devolve pronta (ou com `erro` no resultado)."""

    token: str = TOKEN
    erro: int = 0
    agente: str | None = None  # `userAgent` que a solução do Turnstile traz
    pedidos: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        assert pedido.url.host == "api.2captcha.com"
        corpo = json.loads(pedido.content)
        self.pedidos.append((pedido.url.path, corpo))
        if pedido.url.path == "/createTask":
            return httpx.Response(200, json={"errorId": 0, "taskId": 7})
        assert pedido.url.path == "/getTaskResult"
        if self.erro:
            return httpx.Response(
                200, json={"errorId": self.erro, "errorCode": "ERROR_CAPTCHA_UNSOLVABLE"}
            )
        solucao: dict[str, str] = {"gRecaptchaResponse": self.token, "token": self.token}
        if self.agente is not None:
            solucao["userAgent"] = self.agente
        return httpx.Response(
            200, json={"errorId": 0, "status": "ready", "solution": solucao, "cost": "0.00145"}
        )

    def tarefas(self) -> list[dict[str, Any]]:
        return [corpo["task"] for caminho, corpo in self.pedidos if caminho == "/createTask"]


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _dns_falso(host: str) -> list[str]:
    return ["93.184.215.14"]  # nunca o DNS de verdade


def _cliente(api: Api2Captcha) -> ClienteEducado:
    return ClienteEducado(
        httpx.MockTransport(api), RelogioFalso(), _SemValidadores(), "9.9.9", resolver=_dns_falso
    )


@pytest.fixture
def con() -> Iterator[sqlite3.Connection]:
    c = abrir(Path(":memory:"))
    migrar(c, Path(":memory:"))
    gravar_config(c, "captcha_ligado", True)
    yield c
    c.close()


@pytest.fixture
def cofre(tmp_path: Path) -> Cofre:
    guardado = Cofre(tmp_path, CofreFalso())
    guardado.gravar(NOME_NO_COFRE, CHAVE)
    return guardado


@pytest.fixture
def api() -> Api2Captcha:
    return Api2Captcha()


@pytest.fixture(autouse=True)
def _so_leitura(site: SiteFalso) -> Iterator[None]:
    """A cola não envia formulário nem muda campo, fora o de resposta do widget (D132.11)."""
    yield
    assert (site.posts, site.campos_mudados) == (0, 0)


async def _pagina(contexto: BrowserContext) -> Page:
    return contexto.pages[0] if contexto.pages else await contexto.new_page()


def _cola(
    page: Page, con: sqlite3.Connection, api: Api2Captcha, cofre: Cofre, relogio: RelogioFalso
) -> Cola:
    return Cola(page, con=con, cliente=_cliente(api), relogio=relogio, chave=ChaveDoCofre(cofre))


def _caminhos(site: SiteFalso) -> dict[str, int]:
    return {c: n for c, n in site.visitas.items() if c != "/favicon.ico"}


# --- execução inteira ------------------------------------------------------------------------
@dataclass
class LeitorFixo(LeitorFalso):
    urls: tuple[tuple[str, str], ...] = ()

    def escopos(self, ctx: ContextoColeta) -> Sequence[EscopoLogado]:
        return [EscopoLogado(i, self.base + c) for i, c in self.urls]


@pytest.fixture
async def lancar() -> AsyncIterator[Lancar]:
    """Navegador sem tela, com a rota que recusa (e conta) tudo fora do loopback."""
    recusados: list[str] = []
    contextos: list[BrowserContext] = []

    async def filtrar(route: Route) -> None:
        if urlsplit(route.request.url).hostname in LOCAIS:
            await route.continue_()
        else:
            recusados.append(route.request.url)
            await route.abort()

    async with async_playwright() as playwright:

        async def lancar_sem_tela(**argumentos: Any) -> BrowserContext:
            argumentos.pop("channel", None)  # sempre o Chromium do Playwright, igual no CI
            contexto = await playwright.chromium.launch_persistent_context(
                **argumentos, headless=True
            )
            await contexto.route("**/*", filtrar)
            contextos.append(contexto)
            return contexto

        try:
            yield lancar_sem_tela
        finally:
            for contexto in contextos:
                await contexto.close()
    assert recusados == [], f"pedido para fora do loopback: {recusados}"


async def _executar(
    con: sqlite3.Connection,
    leitor: LeitorFixo,
    api: Api2Captcha,
    cofre: Cofre,
    lancar: Lancar,
    tmp_path: Path,
) -> dict[tuple[str, str], tuple[str, str | None]]:
    semear_leitores(con, [leitor])
    con.execute("UPDATE fonte SET ligada = 1 WHERE chave = ?", (leitor.chave,))
    con.commit()
    deps = Dependencias(
        dados=tmp_path,
        lancar=lancar,
        ambiente=lambda: {"DISPLAY": ":0"},
        politica=lambda lido: lambda url: dentro_dos_hosts(url, lido.hosts),
        sortear=lambda: limites.ESPERA_MIN_S,
        cofre=cofre,
        avisar=lambda titulo, frase: None,
    )
    execucao_id = await executar_login(
        con, _cliente(api), RelogioDoNavegador(), "agenda", leitores=[leitor], deps=deps
    )
    assert execucao_id is not None
    linhas = con.execute(
        "SELECT fonte, escopo, estado, motivo FROM saude WHERE execucao_id = ?", (execucao_id,)
    ).fetchall()
    return {(f, e): (estado, motivo) for f, e, estado, motivo in linhas}


# --- os testes -------------------------------------------------------------------------------
async def test_login_com_captcha_nao_chama_resolver(
    site: SiteFalso,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
    lancar: Lancar,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "JANELA_PARADA_S", 10)  # o controle cai na janela parada
    leitor = LeitorFixo(base=site.url(""), url_entrada=site.url("/login-recaptcha"))
    saude = await _executar(con, leitor, api, cofre, lancar, tmp_path)
    assert saude == {("falso_logado", ""): ("falhou", "saude.precisa_login")}
    assert api.pedidos == []
    assert site.tokens == []
    # controle: a mesma montagem, numa página de desafio que não é login, chama o 2Captcha
    controle = LeitorFixo(base=site.url(""), urls=(("python", "/recaptcha-v2"),))
    saude = await _executar(con, controle, api, cofre, lancar, tmp_path)
    assert saude == {("falso_logado", "python"): ("falhou", "saude.captcha")}
    assert [t["type"] for t in api.tarefas()] == ["RecaptchaV2TaskProxyless"]


async def test_captcha_resolvido_com_2captcha_pronto(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
) -> None:
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)
    url = site.url("/recaptcha-passa")
    visita = await visitar(page, url, leitor, politica_local, relogio, cola=cola)
    agentes = set(site.agentes)
    assert len(agentes) == 1 and "" not in agentes
    assert api.tarefas() == [
        {
            "type": "RecaptchaV2TaskProxyless",
            "websiteURL": url,
            "websiteKey": CHAVE_V2,
            "isInvisible": False,
            "userAgent": agentes.pop(),
        }
    ]
    assert site.tokens == [TOKEN]  # a função de retorno do widget recebeu o token
    # depois do token, só os pedidos que a função de retorno faz: nada de nova navegação
    assert _caminhos(site) == {"/recaptcha-passa": 1, "/conferir-token": 1, "/lista-html": 1}
    assert isinstance(visita, Captura)
    assert urlsplit(visita.url).path == "/lista-html"
    assert [v.titulo for v in leitor.ler(visita, ESCOPO).vagas] == ["Vaga 1", "Vaga 2"]
    assert ler_config(con, "captcha_uso", None)["n"] == 1  # contou no teto do dia


async def test_uma_tentativa_por_pagina(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
) -> None:
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)
    url = site.url("/recaptcha-v2")  # o token chega, mas a página não sai do desafio
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert len(api.tarefas()) == 1
    assert site.tokens == [TOKEN]
    # erro do 2Captcha também não tenta de novo: uma tarefa, uma consulta
    api.erro = 12
    url_t = site.url("/turnstile")
    assert await visitar(page, url_t, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert len(api.tarefas()) == 2
    assert [c for c, _ in api.pedidos].count("/getTaskResult") == 2
    # controle: outra execução (outra cola) tenta a mesma página de novo
    api.erro = 0
    outra = _cola(page, con, api, cofre, relogio)
    assert await visitar(page, url, leitor, politica_local, relogio, cola=outra) == "captcha"
    assert len(api.tarefas()) == 3


async def test_403_com_turnstile_e_429_com_recaptcha_vao_ao_captcha(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
) -> None:
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    leitor = LeitorFalso.para(site)
    # sem quem resolva, a visita devolve o widget achado
    sem_cola = await visitar(page, site.url("/403-turnstile"), leitor, politica_local, relogio)
    assert sem_cola == Widget("turnstile", CHAVE_TURNSTILE, False, "recebeu", None)
    cola = _cola(page, con, api, cofre, relogio)
    url = site.url("/403-turnstile")
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    url = site.url("/429-recaptcha")
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert site.visitas["/429-recaptcha"] == 1  # nem a espera do 429 nem outra tentativa
    assert [t["type"] for t in api.tarefas()] == [
        "TurnstileTaskProxyless",
        "RecaptchaV2TaskProxyless",
    ]
    # o 403 era do desafio: a página que sai dele no lugar segue como lida
    url = site.url("/403-turnstile-some")
    visita = await visitar(page, url, leitor, politica_local, relogio, cola=cola)
    assert isinstance(visita, Captura)
    assert [v.titulo for v in leitor.ler(visita, ESCOPO).vagas] == ["Vaga 1", "Vaga 2"]
    assert site.tokens == [TOKEN, TOKEN, TOKEN]


async def test_desafio_que_volta_e_bloqueio(
    site: SiteFalso,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
    lancar: Lancar,
    tmp_path: Path,
) -> None:
    leitor = LeitorFixo(base=site.url(""), urls=(("python", "/desafio-volta"),))
    saude = await _executar(con, leitor, api, cofre, lancar, tmp_path)
    assert saude == {("falso_logado", "python"): ("falhou", "saude.bloqueio")}
    assert len(api.tarefas()) == 1  # o desafio que voltou não vai de novo ao 2Captcha
    assert site.visitas["/desafio-volta"] == 2  # a função de retorno levou à página de novo


async def test_recaptcha_v3_nao_chama_resolver(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
) -> None:
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)
    url = site.url("/recaptcha-v3")
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert api.pedidos == []
    assert ler_config(con, "captcha_uso", None) is None  # nem contou no teto
    # controle: a mesma cola resolve o v2
    url = site.url("/recaptcha-v2")
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert len(api.tarefas()) == 1


async def test_widget_em_pagina_logada_e_da_pagina(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
) -> None:
    """reCAPTCHA de formulário numa página logada com 200 não é desafio: não vai ao 2Captcha."""
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)
    url = site.url("/logada-com-formulario")
    visita = await visitar(page, url, leitor, politica_local, relogio, cola=cola)
    assert isinstance(visita, Captura)
    assert [v.titulo for v in leitor.ler(visita, ESCOPO).vagas] == ["Vaga 1", "Vaga 2"]
    assert (api.pedidos, site.tokens) == ([], [])  # a função de retorno não foi chamada
    assert ler_config(con, "captcha_uso", None) is None
    assert await achar_widget(page) is not None  # controle: o widget está na página


async def test_callback_de_nome_torto_nao_resolve_nem_chama_nada(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
) -> None:
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)
    url = site.url("/callback-torto")
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert api.pedidos == []
    assert ler_config(con, "captcha_uso", None) is None
    assert await page.evaluate("window.__alertas") == 0
    await page.evaluate("alert(1)")  # controle: o contador do site falso vê a chamada
    assert await page.evaluate("window.__alertas") == 1


async def test_salto_para_pagina_recusada_pela_politica_e_bloqueio(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A política vale também para a página final de um salto (o http no próprio host)."""
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)

    def politica(url: str) -> bool:  # análogo do http: mesmo host, caminho recusado
        return dentro_dos_hosts(url, leitor.hosts) and "/inseguro" not in url

    url = site.url("/salto-mesmo-host")
    assert politica(url)  # a entrada passa; só a página final é recusada
    with caplog.at_level(logging.INFO, logger="jobot.navegador.pagina"):
        visita = await visitar(page, url, leitor, politica, relogio, cola=cola)
    assert visita == "bloqueio"
    assert (api.pedidos, site.tokens) == ([], [])
    assert ler_config(con, "captcha_uso", None) is None
    assert any(
        "política" in r.getMessage() and "127.0.0.1" in r.getMessage() for r in caplog.records
    )
    # controle: com a política que aceita o caminho, a mesma página vai ao 2Captcha
    aceita = await visitar(page, url, leitor, lambda u: dentro_dos_hosts(u, leitor.hosts), relogio)
    assert aceita == Widget("recaptcha_v2", CHAVE_V2, False, "recebeu", None)


async def test_retorno_do_widget_que_leva_a_pagina_recusada_e_bloqueio(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
) -> None:
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)

    def politica(url: str) -> bool:
        return dentro_dos_hosts(url, leitor.hosts) and "/inseguro" not in url

    url = site.url("/recaptcha-vai-inseguro")
    assert await visitar(page, url, leitor, politica, relogio, cola=cola) == "bloqueio"
    assert site.visitas["/inseguro/lista"] == 1  # controle: a função de retorno levou lá
    assert len(api.tarefas()) == 1  # só a página aceita foi ao 2Captcha


@pytest.mark.parametrize("caminho", ["/botao-recaptcha", "/input-recaptcha", "/botao-turnstile"])
async def test_widget_preso_a_botao_nao_e_desafio(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
    caminho: str,
) -> None:
    """reCAPTCHA invisível ou Turnstile num botão envia o formulário pela função de retorno: a
    visita não o resolve, nem numa página não logada (A8, D132.11)."""
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)
    visita = await visitar(page, site.url(caminho), leitor, politica_local, relogio, cola=cola)
    assert isinstance(visita, Captura)
    assert [v.titulo for v in leitor.ler(visita, ESCOPO).vagas] == ["Vaga 1", "Vaga 2"]
    assert (api.pedidos, site.tokens) == ([], [])  # a função de retorno não foi chamada
    assert await achar_widget(page) is None
    assert await page.locator("[data-sitekey]").count() == 1  # controle: o botão está na página


async def test_turnstile_com_user_agent_diferente_nao_troca_o_do_navegador(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
) -> None:
    api.agente = "Outro/1.0 (do 2Captcha)"
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)
    url = site.url("/turnstile")
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert site.tokens == [TOKEN]  # o token foi tentado
    await page.goto(site.url("/lista-html"))  # depois do token, o navegador segue o mesmo
    agentes = set(site.agentes)
    assert len(agentes) == 1
    assert api.agente not in agentes
    assert [t["type"] for t in api.tarefas()] == ["TurnstileTaskProxyless"]


async def test_log_sem_cookie_token_nem_query(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    cofre: Cofre,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    api.token = "SEGREDO-TOKEN"
    await contexto_de_teste.add_cookies(
        [{"name": "sessao", "value": "SEGREDO-COOKIE", "url": site.url("/")}]
    )
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    cola = _cola(page, con, api, cofre, relogio)
    leitor = LeitorFalso.para(site)
    url = site.url("/recaptcha-v2?q=SEGREDO-QUERY")
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert site.tokens == ["SEGREDO-TOKEN"]  # o token passou pela cola
    assert api.tarefas()[0]["websiteURL"] == site.url("/recaptcha-v2")  # sem a query
    assert "/recaptcha-v2" in caplog.text  # controle: a cola e a parada foram ao log
    for segredo in ("SEGREDO-COOKIE", "SEGREDO-TOKEN", "SEGREDO-QUERY", CHAVE):
        assert segredo not in caplog.text


async def test_2captcha_desligado_nao_abre_o_cofre(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    con: sqlite3.Connection,
    api: Api2Captcha,
    tmp_path: Path,
) -> None:
    lidos: list[str] = []

    class CofreContado(Cofre):
        def ler(self, nome: str) -> tuple[str, OndeGuardou] | None:
            lidos.append(nome)
            return super().ler(nome)

    cofre = CofreContado(tmp_path, CofreFalso())
    cofre.gravar(NOME_NO_COFRE, CHAVE)
    gravar_config(con, "captcha_ligado", False)
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    leitor = LeitorFalso.para(site)
    url = site.url("/recaptcha-v2")
    cola = _cola(page, con, api, cofre, relogio)
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert (lidos, api.pedidos) == ([], [])  # o cofre do sistema pode pedir a senha da pessoa
    # controle: ligado, a mesma página lê a chave e chama o 2Captcha
    gravar_config(con, "captcha_ligado", True)
    cola = _cola(page, con, api, cofre, relogio)
    assert await visitar(page, url, leitor, politica_local, relogio, cola=cola) == "captcha"
    assert lidos == [NOME_NO_COFRE]
    assert len(api.tarefas()) == 1


def test_nome_no_cofre_definido_uma_vez() -> None:
    """O nome da chave no cofre é atribuído uma vez só em `src/`, em `banco/captcha.py`."""
    achados: list[tuple[str, str]] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Assign):
                alvos, valor = no.targets, no.value
            elif isinstance(no, ast.AnnAssign) and no.value is not None:
                alvos, valor = [no.target], no.value
            else:
                continue
            nomes = [a.id for a in alvos if isinstance(a, ast.Name)]
            literal = isinstance(valor, ast.Constant) and valor.value == "2captcha"
            if literal or "NOME_NO_COFRE" in nomes:
                for nome in nomes:
                    achados.append((arquivo.relative_to(SRC).as_posix(), nome))
    assert achados == [("jobot/banco/captcha.py", "NOME_NO_COFRE")]


def test_prazo_do_cofre_definido_uma_vez() -> None:
    """O prazo do cofre é atribuído uma vez só em `src/`, em `navegador/limites.py` (D135.4)."""
    achados: list[tuple[str, str]] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Assign):
                alvos = no.targets
            elif isinstance(no, ast.AnnAssign) and no.value is not None:
                alvos = [no.target]
            else:
                continue
            for nome in [a.id for a in alvos if isinstance(a, ast.Name)]:
                if nome == "PRAZO_COFRE_S":
                    achados.append((arquivo.relative_to(SRC).as_posix(), nome))
    assert achados == [("jobot/navegador/limites.py", "PRAZO_COFRE_S")]


async def test_duas_leituras_ao_mesmo_tempo_leem_o_cofre_uma_vez(tmp_path: Path) -> None:
    """O `asyncio.Lock` da `ChaveDoCofre`: a segunda leitura espera a primeira (D135.5)."""
    lidos: list[str] = []
    contagem = threading.Lock()
    entrou, solta = threading.Event(), threading.Event()
    dentro = maximo = 0

    class CofreContado(Cofre):
        def ler(self, nome: str) -> tuple[str, OndeGuardou] | None:
            nonlocal dentro, maximo
            with contagem:
                lidos.append(nome)
                dentro += 1
                maximo = max(maximo, dentro)
            entrou.set()
            solta.wait()
            try:
                return super().ler(nome)
            finally:
                with contagem:
                    dentro -= 1

    cofre = CofreContado(tmp_path, CofreFalso())
    cofre.gravar(NOME_NO_COFRE, CHAVE)
    chave = ChaveDoCofre(cofre)
    solta.set()
    assert cofre.ler(NOME_NO_COFRE) is not None  # controle: a chave está no cofre
    lidos.clear()
    solta.clear()
    entrou.clear()
    try:
        primeira = asyncio.create_task(chave.ler())
        await asyncio.to_thread(entrou.wait)  # a primeira leitura está dentro do cofre
        segunda = asyncio.create_task(chave.ler())
        await asyncio.sleep(0)  # a segunda chega à trava (sem ela, ao cofre) antes de soltar
        solta.set()
        a, b = await asyncio.gather(primeira, segunda)
    finally:
        solta.set()  # nunca deixa thread presa
    assert lidos == [NOME_NO_COFRE]
    assert a == b
    assert a is not None and a[0] == CHAVE
    assert maximo == 1


# --- apoio da cola ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("caminho", "esperado"),
    [
        ("/recaptcha-v2", Widget("recaptcha_v2", CHAVE_V2, False, "recebeu", None)),
        ("/login-recaptcha", Widget("recaptcha_v2", CHAVE_INVISIVEL, True, "enviar", None)),
        ("/turnstile", Widget("turnstile", CHAVE_TURNSTILE, False, "recebeu", None)),
        ("/turnstile-acao", Widget("turnstile", CHAVE_TURNSTILE, False, None, "busca/vagas")),
        ("/recaptcha-v3", Widget("nao_aceito", CHAVE_V3, False, None, None)),
        ("/callback-torto", Widget("nao_aceito", CHAVE_V2, False, None, None)),
        ("/lista-html", None),
    ],
)
async def test_achar_widget_le_os_atributos(
    site: SiteFalso, contexto_de_teste: BrowserContext, caminho: str, esperado: Widget | None
) -> None:
    page = await _pagina(contexto_de_teste)
    await page.goto(site.url(caminho))
    assert await achar_widget(page) == esperado


class _AlvoQueLevanta:
    def __init__(self, erro: Exception) -> None:
        self.erro = erro

    async def get_attribute(self, nome: str, *, timeout: float) -> str | None:
        raise self.erro


class _PaginaFalsa:
    """Todo `locator(...).all()` devolve um alvo cujo `get_attribute` levanta `erro`."""

    def __init__(self, erro: Exception) -> None:
        self.erro = erro

    def locator(self, _seletor: str) -> _PaginaFalsa:
        return self

    async def all(self) -> list[_AlvoQueLevanta]:
        return [_AlvoQueLevanta(self.erro)]


async def test_estouro_ao_ler_atributo_vira_desafio_nao_aceito() -> None:
    pagina: Any = _PaginaFalsa(EstouroDoPlaywright("estourou"))
    assert await achar_widget(pagina) == Widget("nao_aceito", "", False, None, None)


async def test_pagina_trocando_no_meio_continua_sem_widget() -> None:
    pagina: Any = _PaginaFalsa(ErroDoPlaywright("Execution context was destroyed"))
    assert await achar_widget(pagina) is None


async def test_dependencias_de_producao_ligam_o_cofre_da_pasta_de_dados(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class PlaywrightFalso:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            pass

    monkeypatch.setattr(execucao, "async_playwright", PlaywrightFalso)
    monkeypatch.setattr(modulo_cofre, "keyring", CofreFalso())  # nunca o cofre de quem roda
    (tmp_path / f"{NOME_NO_COFRE}.segredo").write_text(CHAVE, encoding="utf-8")
    async with dependencias_de_producao(tmp_path, {"DISPLAY": ":0"}) as deps:
        assert deps.cofre.ler(NOME_NO_COFRE) == (CHAVE, "arquivo")
