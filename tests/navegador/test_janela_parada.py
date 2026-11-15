"""Janela parada e aviso no computador (T217; desenho A8, D132.10, D132.26, D132.44).

O 2Captcha é um `httpx.MockTransport`; a chave é inventada e mora num `CofreFalso`. A aba que
a pessoa "resolve" é a do `/desafio-pessoa`, que sai do desafio com um cookie, como um site real.
"""

import asyncio
import contextlib
import sqlite3
import threading
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.async_api import BrowserContext, Page, Route, async_playwright
from playwright.async_api import Error as ErroDoPlaywright

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from apoio.site_falso import LOCAIS, LeitorFalso, RelogioDoNavegador, SiteFalso
from jobot.banco.cadastros import gravar_config, semear_leitores
from jobot.banco.captcha import NOME_NO_COFRE
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.navegador import captcha as modulo_captcha
from jobot.navegador import execucao, limites
from jobot.navegador.abrir import Lancar
from jobot.navegador.execucao import Dependencias, dependencias_de_producao, executar_login
from jobot.navegador.politica import dentro_dos_hosts
from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.coletores.executor import estado_da_fonte
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.nucleo.leitores.base import EscopoLogado
from jobot.sistema import cofre as modulo_cofre
from jobot.sistema.cofre import Cofre, OndeGuardou
from jobot.sistema.segundo_plano_linux import Rodar, rodar_comando

pytestmark = [pytest.mark.tela, pytest.mark.anyio]

CHAVE = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"  # inventada
TOKEN = "TOKEN-FALSO-DO-2CAPTCHA"


@dataclass
class Api2Captcha:
    """O 2Captcha falso: abre a tarefa 7 e a devolve pronta, ou responde com `erro`."""

    erro: int = 0
    pedidos: list[str] = field(default_factory=list)

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        assert pedido.url.host == "api.2captcha.com"
        self.pedidos.append(pedido.url.path)
        if self.erro:
            return httpx.Response(200, json={"errorId": self.erro, "errorCode": "ERRO_FALSO"})
        if pedido.url.path == "/createTask":
            return httpx.Response(200, json={"errorId": 0, "taskId": 7})
        solucao = {"gRecaptchaResponse": TOKEN, "token": TOKEN}
        return httpx.Response(
            200, json={"errorId": 0, "status": "ready", "solution": solucao, "cost": "0.00145"}
        )


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _dns_falso(host: str) -> list[str]:
    return ["93.184.215.14"]  # nunca o DNS de verdade


@dataclass
class LeitorFixo(LeitorFalso):
    urls: tuple[tuple[str, str], ...] = ()

    def escopos(self, ctx: ContextoColeta) -> Sequence[EscopoLogado]:
        return [EscopoLogado(i, self.base + c) for i, c in self.urls]


@dataclass
class Montagem:
    """Navegador sem tela, o relógio da execução, os avisos e a hora em que cada aba fechou."""

    relogio: RelogioDoNavegador
    lancar: Lancar
    contextos: list[BrowserContext] = field(default_factory=list)
    avisos: list[tuple[str, str, datetime]] = field(default_factory=list)
    fechadas: list[tuple[str, datetime]] = field(default_factory=list)
    fechamentos: list[datetime] = field(default_factory=list)

    def avisar(self, titulo: str, frase: str) -> None:
        self.avisos.append((titulo, frase, self.relogio.agora()))

    def deps(
        self, dados: Path, cofre: Cofre, sortear: Callable[[], float] = lambda: 0.0
    ) -> Dependencias:
        return Dependencias(
            dados=dados,
            lancar=self.lancar,
            ambiente=lambda: {"DISPLAY": ":0"},
            politica=lambda lido: lambda url: dentro_dos_hosts(url, lido.hosts),
            sortear=sortear,
            cofre=cofre,
            avisar=self.avisar,
        )

    def aba(self, caminho: str) -> Page:
        return next(p for c in self.contextos for p in c.pages if urlsplit(p.url).path == caminho)


@pytest.fixture
async def montagem() -> AsyncIterator[Montagem]:
    recusados: list[str] = []

    async def filtrar(route: Route) -> None:
        if urlsplit(route.request.url).hostname in LOCAIS:
            await route.continue_()
        else:
            recusados.append(route.request.url)
            await route.abort()

    def ao_abrir(page: Page) -> None:
        page.on("close", lambda p: m.fechadas.append((urlsplit(p.url).path, m.relogio.agora())))

    async with async_playwright() as playwright:

        async def lancar(**argumentos: Any) -> BrowserContext:
            argumentos.pop("channel", None)  # sempre o Chromium do Playwright, igual no CI
            contexto = await playwright.chromium.launch_persistent_context(
                **argumentos, headless=True
            )
            await contexto.route("**/*", filtrar)
            contexto.on("page", ao_abrir)
            contexto.on("close", lambda _: m.fechamentos.append(m.relogio.agora()))
            m.contextos.append(contexto)
            return contexto

        m = Montagem(RelogioDoNavegador(), lancar)
        try:
            yield m
        finally:
            for contexto in m.contextos:
                await contexto.close()
    assert recusados == [], f"pedido para fora do loopback: {recusados}"


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


@pytest.fixture(autouse=True)
def _so_leitura(site: SiteFalso) -> Iterator[None]:
    """A janela não envia formulário nem muda campo (D132.11)."""
    yield
    assert (site.posts, site.campos_mudados) == (0, 0)


def _cliente(api: Api2Captcha) -> ClienteEducado:
    return ClienteEducado(
        httpx.MockTransport(api), RelogioFalso(), _SemValidadores(), "9.9.9", resolver=_dns_falso
    )


def _ligar(con: sqlite3.Connection, *leitores: LeitorFixo) -> None:
    semear_leitores(con, leitores)
    con.executemany("UPDATE fonte SET ligada = 1 WHERE chave = ?", [(x.chave,) for x in leitores])
    con.commit()


def _saude(con: sqlite3.Connection, execucao_id: int) -> dict[tuple[str, str], tuple[str, Any]]:
    linhas = con.execute(
        "SELECT fonte, escopo, estado, motivo FROM saude WHERE execucao_id = ?", (execucao_id,)
    ).fetchall()
    return {(f, e): (estado, motivo) for f, e, estado, motivo in linhas}


def _sem_endereco(avisos: Sequence[tuple[str, str, datetime]]) -> bool:
    return all("http" not in t + f and "127.0.0.1" not in t + f for t, f, _ in avisos)


# --- os testes -------------------------------------------------------------------------------
@dataclass(frozen=True)
class Caso:
    caminho: str
    ligado: bool = True
    chave: bool = True
    erro: int = 0
    teto: bool = False


@pytest.mark.parametrize(
    "caso",
    [
        pytest.param(Caso("/recaptcha-v2", ligado=False), id="interruptor_desligado"),
        pytest.param(Caso("/recaptcha-v2", chave=False), id="sem_chave"),
        pytest.param(Caso("/recaptcha-v3"), id="nao_aceito"),
        pytest.param(Caso("/recaptcha-v2", erro=10), id="sem_saldo"),
        pytest.param(Caso("/recaptcha-v2", teto=True), id="teto"),
        pytest.param(Caso("/recaptcha-v2"), id="pagina_que_nao_sai_em_30_s"),
    ],
)
async def test_captcha_sem_2captcha_para_a_janela(
    caso: Caso,
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    cofre: Cofre,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)  # a mesma regra, com menos espera real
    if caso.teto:
        monkeypatch.setattr(modulo_captcha, "reservar_resolucao", lambda con, dia: False)
    gravar_config(con, "captcha_ligado", caso.ligado)
    guardado = cofre if caso.chave else Cofre(tmp_path / "vazio", CofreFalso())
    leitor = LeitorFixo(base=site.url(""), urls=(("python", caso.caminho),))
    _ligar(con, leitor)
    api = Api2Captcha(erro=caso.erro)
    execucao_id = await executar_login(
        con,
        _cliente(api),
        montagem.relogio,
        "agenda",
        leitores=[leitor],
        deps=montagem.deps(tmp_path, guardado),
    )
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {("falso_logado", "python"): ("falhou", "saude.captcha")}
    assert len(montagem.avisos) == 1 and _sem_endereco(montagem.avisos)
    avisado_em = montagem.avisos[0][2]
    fechou_em = dict(montagem.fechadas)[caso.caminho]
    assert fechou_em - avisado_em >= timedelta(seconds=limites.JANELA_PARADA_S)
    assert len(montagem.fechamentos) == 1  # o contexto fechou no fim
    if caso.ligado and caso.chave and not caso.teto and caso.caminho == "/recaptcha-v2":
        assert api.pedidos[0] == "/createTask"  # controle: o 2Captcha foi tentado
    else:
        assert api.pedidos == []


async def test_cloudflare_que_nao_sai_vai_para_a_janela_sem_resolver(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    cofre: Cofre,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)
    leitor = LeitorFixo(base=site.url(""), urls=(("python", "/cloudflare-fica"),))
    _ligar(con, leitor)
    api = Api2Captcha()
    execucao_id = await executar_login(
        con,
        _cliente(api),
        montagem.relogio,
        "agenda",
        leitores=[leitor],
        deps=montagem.deps(tmp_path, cofre),
    )
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {("falso_logado", "python"): ("falhou", "saude.captcha")}
    assert api.pedidos == []  # o 2Captcha está pronto, mas o desafio gerenciado não vai a ele
    assert site.visitas["/turnstile-quadro"] >= 1  # o iframe do Turnstile estava na página
    assert len(montagem.avisos) == 1
    avisado_em = montagem.avisos[0][2]
    fechou_em = dict(montagem.fechadas)["/cloudflare-fica"]
    assert fechou_em - avisado_em >= timedelta(seconds=limites.JANELA_PARADA_S)


async def test_duas_abas_dividem_os_15_minutos(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    cofre: Cofre,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gravar_config(con, "captcha_ligado", False)  # sem 2Captcha: as duas param
    # o relógio da janela só anda depois que a pessoa resolve: assim "resolveu cedo" não depende
    # da velocidade da máquina
    resolvido = asyncio.Event()
    dormir = montagem.relogio.dormir

    async def dormir_depois_de_resolver(s: float) -> None:
        if s > 0:
            await resolvido.wait()
        await dormir(s)

    monkeypatch.setattr(montagem.relogio, "dormir", dormir_depois_de_resolver)
    um = LeitorFixo(base=site.url(""), urls=(("python", "/desafio-pessoa"),))
    dois = LeitorFixo(base=site.url(""), urls=(("java", "/recaptcha-v2"),), chave="outro_logado")
    _ligar(con, um, dois)
    tarefa = asyncio.create_task(
        executar_login(
            con,
            _cliente(Api2Captcha()),
            montagem.relogio,
            "agenda",
            leitores=[um, dois],
            deps=montagem.deps(tmp_path, cofre),
        )
    )
    while not montagem.avisos and not tarefa.done():
        await asyncio.sleep(0.01)
    assert montagem.avisos, "a execução acabou sem parar na janela"
    # a pessoa resolve o desafio da primeira aba; o site guarda a resposta num cookie
    aba = montagem.aba("/desafio-pessoa")
    with contextlib.suppress(ErroDoPlaywright):  # a página recarrega no meio da chamada
        await aba.evaluate("document.cookie = 'pessoa_ok=1; path=/'; location.reload()")
    await aba.wait_for_load_state()
    resolvido.set()
    execucao_id = await tarefa
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {
        ("falso_logado", "python"): ("ok", None),
        ("outro_logado", "java"): ("falhou", "saude.captcha"),
    }
    vagas = con.execute("SELECT count(*) FROM ocorrencia WHERE fonte = 'falso_logado'").fetchone()
    assert vagas == (2,)  # a aba resolvida seguiu o site e gravou as vagas
    assert len(montagem.avisos) == 1 and _sem_endereco(montagem.avisos)
    # a espera da janela conta uma vez só, para as duas abas (o sorteio é 0 s)
    assert sum(montagem.relogio.dormidas) == limites.JANELA_PARADA_S
    assert max(montagem.relogio.dormidas) <= 5  # olha cada aba a cada 5 s
    # a aba resolvida seguiu logo na primeira olhada, não no fim do prazo
    fechou_em = dict(montagem.fechadas)["/desafio-pessoa"]
    assert fechou_em - montagem.avisos[0][2] < timedelta(seconds=10)
    assert len(montagem.fechamentos) == 1  # o contexto fechou no fim


async def test_sem_parada_nao_avisa_nem_espera(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    cofre: Cofre,
    tmp_path: Path,
) -> None:
    leitor = LeitorFixo(base=site.url(""), urls=(("python", "/lista-html"),))
    _ligar(con, leitor)
    execucao_id = await executar_login(
        con,
        _cliente(Api2Captcha()),
        montagem.relogio,
        "agenda",
        leitores=[leitor],
        deps=montagem.deps(tmp_path, cofre),
    )
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {("falso_logado", "python"): ("ok", None)}
    assert montagem.avisos == []
    assert sum(montagem.relogio.dormidas) == 0


async def test_dependencias_de_producao_ligam_o_aviso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class PlaywrightFalso:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            pass

    chamadas: list[tuple[str, str, dict[str, str], Rodar]] = []

    def avisar(titulo: str, frase: str, env: Any, rodar: Rodar) -> None:
        chamadas.append((titulo, frase, dict(env), rodar))

    monkeypatch.setattr(execucao, "async_playwright", PlaywrightFalso)
    monkeypatch.setattr(execucao, "avisar", avisar)
    monkeypatch.setattr(modulo_cofre, "keyring", CofreFalso())  # nunca o cofre de quem roda
    async with dependencias_de_producao(tmp_path, {"CONTAINER_ID": "caixa"}) as deps:
        deps.avisar("joBot", "Uma frase.")
    assert chamadas == [("joBot", "Uma frase.", {"CONTAINER_ID": "caixa"}, rodar_comando)]


@pytest.mark.parametrize(
    ("caminho", "saude", "avisos"),
    [
        ("/lista-desafio-na-vaga", ("falhou", "saude.captcha"), 1),
        ("/lista-bloqueio-na-vaga", ("falhou", "saude.bloqueio"), 0),
    ],
)
async def test_parada_no_detalhe_grava_a_saude_do_site(
    caminho: str,
    saude: tuple[str, str],
    avisos: int,
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    cofre: Cofre,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)
    gravar_config(con, "captcha_ligado", False)
    leitor = LeitorFixo(base=site.url(""), urls=(("python", caminho),), lista_tem_descricao=False)
    _ligar(con, leitor)
    execucao_id = await executar_login(
        con,
        _cliente(Api2Captcha()),
        montagem.relogio,
        "agenda",
        leitores=[leitor],
        deps=montagem.deps(tmp_path, cofre),
    )
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {
        ("falso_logado", "python"): ("ok", None),
        ("falso_logado", ""): saude,
    }
    assert len(montagem.avisos) == avisos  # o 403 não abre a janela parada
    estados = [
        e for (fonte, _), (e, _) in _saude(con, execucao_id).items() if fonte == "falso_logado"
    ]
    assert estado_da_fonte(estados) == "parcial"


def _travar_relogio(montagem: Montagem, monkeypatch: pytest.MonkeyPatch) -> asyncio.Event:
    """O relógio da janela só anda depois do `set`: a pessoa age antes da primeira olhada."""
    solto = asyncio.Event()
    dormir = montagem.relogio.dormir

    async def dormir_depois(s: float) -> None:
        if s > 0:
            await solto.wait()
        await dormir(s)

    monkeypatch.setattr(montagem.relogio, "dormir", dormir_depois)
    return solto


async def _ate_avisar(montagem: Montagem, tarefa: asyncio.Task[int | None]) -> None:
    while not montagem.avisos and not tarefa.done():
        await asyncio.sleep(0.01)
    assert montagem.avisos, "a execução acabou sem parar na janela"


@pytest.mark.parametrize("quando", ["logo", "depois"])
async def test_fechar_a_aba_parada_encerra_a_espera(
    quando: str,
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    cofre: Cofre,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)
    monkeypatch.setattr(limites, "ESPERA_FECHAR_S", 0.05)  # o navegador não fecha: iria ao fim
    gravar_config(con, "captcha_ligado", False)
    solto = _travar_relogio(montagem, monkeypatch)
    if quando == "logo":  # a pessoa fecha a aba enquanto o aviso aparece
        loop = asyncio.get_running_loop()

        async def fechar_aba() -> None:
            await montagem.aba("/recaptcha-v2").close()
            # o `close` da aba chegou antes de o `close()` voltar: a ordem não é corrida
            assert "/recaptcha-v2" in dict(montagem.fechadas)

        def avisar_e_fechar(titulo: str, frase: str) -> None:
            montagem.avisos.append((titulo, frase, montagem.relogio.agora()))
            asyncio.run_coroutine_threadsafe(fechar_aba(), loop).result()

        monkeypatch.setattr(montagem, "avisar", avisar_e_fechar)
        solto.set()
    leitor = LeitorFixo(base=site.url(""), urls=(("python", "/recaptcha-v2"),))
    _ligar(con, leitor)
    tarefa = asyncio.create_task(
        executar_login(
            con,
            _cliente(Api2Captcha()),
            montagem.relogio,
            "agenda",
            leitores=[leitor],
            deps=montagem.deps(tmp_path, cofre),
        )
    )
    await _ate_avisar(montagem, tarefa)
    if quando == "depois":
        await montagem.aba("/recaptcha-v2").close()
        solto.set()
    execucao_id = await tarefa
    assert execucao_id is not None
    assert sum(montagem.relogio.dormidas) <= limites.OLHAR_S  # uma olhada, não o prazo inteiro
    assert _saude(con, execucao_id) == {("falso_logado", "python"): ("falhou", "saude.captcha")}
    estado = con.execute("SELECT estado FROM execucao WHERE id = ?", (execucao_id,)).fetchone()
    assert estado == ("concluida",)


async def test_fechar_o_navegador_com_a_janela_parada_interrompe(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    cofre: Cofre,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)  # o `ESPERA_FECHAR_S` fica o de produção
    gravar_config(con, "captcha_ligado", False)
    # o contexto começa a fechar quando a primeira olhada acorda: ela vê a aba fechada e o
    # contexto ainda fechando (fechado antes, o `close` dele chegaria antes da olhada)
    solto = asyncio.Event()
    fechando: list[asyncio.Task[None]] = []
    dormir = montagem.relogio.dormir

    async def dormir_e_fechar(s: float) -> None:
        if s > 0:
            await solto.wait()
        await dormir(s)
        if s > 0 and not fechando:
            fechando.append(asyncio.create_task(montagem.contextos[0].close()))

    monkeypatch.setattr(montagem.relogio, "dormir", dormir_e_fechar)
    leitor = LeitorFixo(base=site.url(""), urls=(("python", "/recaptcha-v2"),))
    _ligar(con, leitor)
    tarefa = asyncio.create_task(
        executar_login(
            con,
            _cliente(Api2Captcha()),
            montagem.relogio,
            "agenda",
            leitores=[leitor],
            deps=montagem.deps(tmp_path, cofre),
        )
    )
    await _ate_avisar(montagem, tarefa)
    await montagem.aba("/recaptcha-v2").close()  # o navegador fecha as abas antes de si
    solto.set()
    execucao_id = await tarefa
    await fechando[0]
    assert len(montagem.fechamentos) == 1  # o `close` do contexto chegou
    assert execucao_id is not None
    estado = con.execute(
        "SELECT estado, parada FROM execucao WHERE id = ?", (execucao_id,)
    ).fetchone()
    assert estado == ("interrompida", "fechado")


async def test_fechar_uma_aba_nao_encerra_a_espera_da_outra(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    cofre: Cofre,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)
    gravar_config(con, "captcha_ligado", False)
    solto = _travar_relogio(montagem, monkeypatch)
    um = LeitorFixo(base=site.url(""), urls=(("python", "/recaptcha-v2"),))
    dois = LeitorFixo(base=site.url(""), urls=(("java", "/turnstile"),), chave="outro_logado")
    _ligar(con, um, dois)
    tarefa = asyncio.create_task(
        executar_login(
            con,
            _cliente(Api2Captcha()),
            montagem.relogio,
            "agenda",
            leitores=[um, dois],
            deps=montagem.deps(tmp_path, cofre),
        )
    )
    await _ate_avisar(montagem, tarefa)
    await montagem.aba("/recaptcha-v2").close()  # só a primeira
    solto.set()
    execucao_id = await tarefa
    assert execucao_id is not None
    assert sum(montagem.relogio.dormidas) == limites.JANELA_PARADA_S  # a outra esperou o prazo
    assert _saude(con, execucao_id) == {
        ("falso_logado", "python"): ("falhou", "saude.captcha"),
        ("outro_logado", "java"): ("falhou", "saude.captcha"),
    }


def _cofre_contado(dados: Path, backend: CofreFalso, lidos: list[str]) -> Cofre:
    """Um `Cofre` que anota cada leitura que entra no cofre."""

    class CofreContado(Cofre):
        def ler(self, nome: str) -> tuple[str, OndeGuardou] | None:
            lidos.append(nome)
            return super().ler(nome)

    return CofreContado(dados, backend)


async def test_chave_lida_do_cofre_uma_vez_por_execucao(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection, tmp_path: Path
) -> None:
    lidos: list[str] = []
    cofre = _cofre_contado(tmp_path, CofreFalso(), lidos)
    cofre.gravar(NOME_NO_COFRE, CHAVE)
    um = LeitorFixo(base=site.url(""), urls=(("python", "/recaptcha-passa"),))
    dois = LeitorFixo(base=site.url(""), urls=(("java", "/recaptcha-passa"),), chave="outro_logado")
    _ligar(con, um, dois)
    api = Api2Captcha()
    execucao_id = await executar_login(
        con,
        _cliente(api),
        montagem.relogio,
        "agenda",
        leitores=[um, dois],
        deps=montagem.deps(tmp_path, cofre),
    )
    assert execucao_id is not None
    assert lidos == [NOME_NO_COFRE]  # as duas abas usam a mesma leitura (D135.5)
    assert api.pedidos.count("/createTask") == 2  # controle: as duas abas usaram a chave


async def test_cofre_que_nao_responde_custa_um_prazo_por_execucao(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "PRAZO_COFRE_S", 0.05)
    monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)
    trava = threading.Event()
    lidos: list[str] = []
    cofre = _cofre_contado(tmp_path, CofreFalso(trava=trava), lidos)
    um = LeitorFixo(base=site.url(""), urls=(("python", "/recaptcha-v2"),))
    dois = LeitorFixo(base=site.url(""), urls=(("java", "/turnstile"),), chave="outro_logado")
    _ligar(con, um, dois)
    api = Api2Captcha()
    try:
        execucao_id = await executar_login(
            con,
            _cliente(api),
            montagem.relogio,
            "agenda",
            leitores=[um, dois],
            deps=montagem.deps(tmp_path, cofre),
        )
    finally:
        trava.set()  # solta a thread presa no cofre
    assert execucao_id is not None
    assert lidos == [NOME_NO_COFRE]  # o estouro fica guardado: um prazo por execução
    assert _saude(con, execucao_id) == {
        ("falso_logado", "python"): ("falhou", "saude.captcha"),
        ("outro_logado", "java"): ("falhou", "saude.captcha"),
    }
    assert api.pedidos == []
