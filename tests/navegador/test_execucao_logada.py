"""A execução `login` contra o site falso (T213; desenho A7, "Uma execução `login`").

O banco é em memória: o batimento fica de fora (`manter_batimento` não abre outra conexão) e
as dormidas do relógio são só as esperas da navegação.
"""

import asyncio
import contextlib
import logging
import socket
import sqlite3
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.async_api import BrowserContext, Route, async_playwright

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from apoio.site_falso import LOCAIS, LeitorFalso, RelogioDoNavegador, SiteFalso
from jobot.banco.buscas import apagar_busca, criar_busca
from jobot.banco.cadastros import semear_leitores
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao
from jobot.banco.gravacao import ValidadoresDoBanco
from jobot.banco.gravacao import gravar_escopo as gravar_escopo_do_banco
from jobot.banco.migrar import migrar
from jobot.navegador import execucao, limites
from jobot.navegador.abrir import Lancar
from jobot.navegador.execucao import Dependencias, dependencias_de_producao, executar_login
from jobot.navegador.pagina import visitar
from jobot.navegador.politica import dentro_dos_hosts
from jobot.nucleo.coletores.base import ContextoColeta, ResultadoEscopo
from jobot.nucleo.coletores.executor import SaidaEscopo
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.leitores.base import EscopoLogado, LeitorComLogin
from jobot.nucleo.modelo import Busca, VagaColetada
from jobot.nucleo.tratamento.tratar import tratar
from jobot.sistema.cofre import Cofre

pytestmark = [pytest.mark.tela, pytest.mark.anyio]

INICIO = RelogioDoNavegador().agora()  # a hora em que toda execução do teste começa
ANTES = INICIO - timedelta(days=3)


@dataclass
class LeitorDeTeste(LeitorFalso):
    """O leitor do site falso com escopos fixos; `urls=None` volta a um escopo por termo."""

    urls: tuple[tuple[str, str], ...] | None = None
    quebrar: bool = False

    def escopos(self, ctx: ContextoColeta) -> Sequence[EscopoLogado]:
        if self.quebrar:
            raise RuntimeError("escopos quebrou")
        if self.urls is None:
            return super().escopos(ctx)
        return [EscopoLogado(i, u) for i, u in self.urls]


def _leitor(site: SiteFalso, *escopos: tuple[str, str], **mudancas: Any) -> LeitorDeTeste:
    """Escopos `(id, caminho)`; caminho que não começa com `/` é a URL inteira."""
    urls = tuple((i, site.url(c) if c.startswith("/") else c) for i, c in escopos)
    return LeitorDeTeste(base=site.url(""), urls=urls, **mudancas)


@dataclass
class Montagem:
    """O navegador sem tela dos testes, com a rota que recusa tudo fora do loopback.

    Pedido a um caminho de `fechar_em` fecha o navegador, como a pessoa fecharia a janela."""

    dados: Path
    lancar: Lancar
    contextos: list[BrowserContext] = field(default_factory=list)
    fechar_em: set[str] = field(default_factory=set)

    def deps(self, sortear: Callable[[], float] = lambda: limites.ESPERA_MIN_S) -> Dependencias:
        return Dependencias(
            dados=self.dados,
            lancar=self.lancar,
            ambiente=lambda: {"DISPLAY": ":0"},
            politica=lambda leitor: lambda url: dentro_dos_hosts(url, leitor.hosts),
            sortear=sortear,
            cofre=Cofre(self.dados, CofreFalso()),
            avisar=lambda titulo, frase: None,
        )


@pytest.fixture
async def montagem(tmp_path: Path) -> AsyncIterator[Montagem]:
    recusados: list[str] = []
    tarefas: list[asyncio.Task[None]] = []
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

        async def filtrar(route: Route) -> None:
            partes = urlsplit(route.request.url)
            if partes.hostname not in LOCAIS:
                recusados.append(route.request.url)
                await route.abort()
                return
            if partes.path in m.fechar_em:
                tarefas.append(asyncio.get_running_loop().create_task(m.contextos[-1].close()))
            with contextlib.suppress(Exception):  # o contexto pode já estar fechando
                await route.continue_()

        try:
            yield m
        finally:
            for tarefa in tarefas:
                await tarefa
            for contexto in m.contextos:
                await contexto.close()
    assert recusados == [], f"pedido para fora do loopback: {recusados}"


@pytest.fixture
def con() -> Iterator[sqlite3.Connection]:
    c = abrir(Path(":memory:"))
    migrar(c, Path(":memory:"))
    c.execute("INSERT INTO fonte (chave, leva, ligada) VALUES ('publica', 'A', 1)")
    c.commit()
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _so_leitura(site: SiteFalso) -> Iterator[None]:
    """Nenhuma execução envia formulário nem muda campo (D132.11)."""
    yield
    assert (site.posts, site.campos_mudados) == (0, 0)


def _ligar(con: sqlite3.Connection, *leitores: LeitorComLogin, ligada: bool = True) -> None:
    semear_leitores(con, leitores)
    con.executemany(
        "UPDATE fonte SET ligada = ? WHERE chave = ?", [(int(ligada), x.chave) for x in leitores]
    )
    con.commit()


def _cliente(con: sqlite3.Connection) -> ClienteEducado:
    def nunca(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError("a leitura com login não usa o cliente HTTP")

    return ClienteEducado(
        httpx.MockTransport(nunca), RelogioFalso(), ValidadoresDoBanco(con), "9.9.9"
    )


async def _rodar(
    con: sqlite3.Connection,
    leitores: Sequence[LeitorComLogin],
    deps: Dependencias,
    relogio: RelogioFalso | None = None,
) -> int | None:
    return await executar_login(
        con,
        _cliente(con),
        relogio or RelogioDoNavegador(),
        "agenda",
        leitores=leitores,
        deps=deps,
    )


def _saude(con: sqlite3.Connection, execucao_id: int) -> dict[tuple[str, str], tuple[str, Any]]:
    linhas = con.execute(
        "SELECT fonte, escopo, estado, motivo FROM saude WHERE execucao_id = ?", (execucao_id,)
    ).fetchall()
    return {(f, e): (estado, motivo) for f, e, estado, motivo in linhas}


def _execucao(con: sqlite3.Connection, execucao_id: int) -> tuple[str, str, str | None]:
    tipo, estado, parada = con.execute(
        "SELECT tipo, estado, parada FROM execucao WHERE id = ?", (execucao_id,)
    ).fetchone()
    return tipo, estado, parada


def _abertas(con: sqlite3.Connection, fonte: str, escopo: str) -> set[str]:
    """Caminhos das vagas com ocorrência aberta do escopo."""
    linhas = con.execute(
        "SELECT v.url FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id"
        " WHERE o.fonte = ? AND o.escopo = ? AND o.sumiu_em IS NULL",
        (fonte, escopo),
    ).fetchall()
    return {urlsplit(u).path for (u,) in linhas}


def _ultima_execucao(con: sqlite3.Connection, fonte: str, escopo: str) -> int | None:
    linha = con.execute(
        "SELECT max(execucao_id) FROM saude WHERE fonte = ? AND escopo = ?", (fonte, escopo)
    ).fetchone()
    return int(linha[0]) if linha[0] is not None else None


def _semear(
    con: sqlite3.Connection, quando: datetime, fonte: str, escopo: str, urls: Sequence[str] = ()
) -> int:
    """Uma execução antiga, já fechada, com uma linha "ok" do escopo e as vagas de `urls`."""
    execucao_id = abrir_execucao(con, "login", "agenda", quando)
    assert execucao_id is not None
    vagas = tuple(
        VagaColetada(
            fonte=fonte,
            escopo=escopo,
            url=u,
            titulo="Vaga antiga",
            empresa="Empresa antiga",
            descricao_formato="texto",
        )
        for u in urls
    )
    saida = SaidaEscopo(fonte, escopo, ResultadoEscopo(vagas, "ok", None, 1), 0, {})
    gravar_escopo_do_banco(con, execucao_id, saida, [tratar(v) for v in vagas], quando)
    fechar_execucao(con, execucao_id, quando)
    return execucao_id


async def test_execucao_grava_vaga_com_fonte_e_escopo(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = LeitorDeTeste(base=site.url(""))  # um escopo por termo das buscas
    _ligar(con, leitor)
    criar_busca(
        con, Busca(nome="b", cargos=("python",)), ANTES, regras_ligadas=True, hoje=date.today()
    )
    _semear(con, ANTES, "publica", "geral", [site.url("/vaga/1")])
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    assert _execucao(con, execucao_id) == ("login", "concluida", None)
    assert _saude(con, execucao_id) == {("falso_logado", "python"): ("ok", None)}
    assert _abertas(con, "falso_logado", "python") == {"/vaga/1", "/vaga/2"}
    # a mesma URL da fonte pública: uma vaga, duas ocorrências
    assert con.execute("SELECT count(*) FROM vaga").fetchone()[0] == 2
    assert con.execute("SELECT count(*) FROM ocorrencia").fetchone()[0] == 3


async def test_uma_gravacao_por_escopo_sem_cache_http(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leitor = _leitor(site, ("a", "/paginada"), ("b", "/paginada"))
    _ligar(con, leitor)
    gravadas: list[SaidaEscopo] = []

    def espiao(c: sqlite3.Connection, eid: int, saida: SaidaEscopo, *args: Any) -> Any:
        gravadas.append(saida)
        return gravar_escopo_do_banco(c, eid, saida, *args)

    monkeypatch.setattr(execucao, "gravar_escopo", espiao)
    cache_antes = con.execute("SELECT count(*) FROM cache_http").fetchone()[0]
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    assert [(s.escopo, len(s.resultado.vagas), s.resultado.pedidos) for s in gravadas] == [
        ("a", 4, 2),
        ("b", 4, 2),
    ]
    assert all(s.validadores == {} and s.urls_sem_detalhe == () for s in gravadas)
    assert [len(s.urls_vistas) for s in gravadas] == [2, 2]  # as páginas de lista
    assert con.execute("SELECT count(*) FROM cache_http").fetchone()[0] == cache_antes


async def test_sem_login_e_precisa_login_e_o_outro_site_segue(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    sem_login = _leitor(site, ("a", "/paginada"), url_entrada=site.url("/entrar/sem-senha"))
    outro = _leitor(site, ("b", "/lista-html?q=b"), chave="outro_logado")
    _ligar(con, sem_login, outro)
    execucao_id = await _rodar(con, [sem_login, outro], montagem.deps())
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {
        ("falso_logado", ""): ("falhou", "saude.precisa_login"),
        ("outro_logado", "b"): ("ok", None),
    }
    assert site.visitas["/paginada"] == 0
    assert _abertas(con, "outro_logado", "b") == {"/vaga/1", "/vaga/2"}


@pytest.mark.parametrize(
    ("caminho", "estado", "motivo", "abertas"),
    [
        pytest.param("/sem-lista", "falhou", "saude.formato_mudou", set(), id="sem_lista"),
        pytest.param(
            "/paginada-torta", "falhou", "saude.formato_mudou", set(), id="segunda_sem_formato"
        ),
        pytest.param(
            "/proxima-fora", "parcial", "saude.listagem_incompleta", {"/vaga/1"}, id="proxima_fora"
        ),
        pytest.param("::1", "falhou", "saude.listagem_incompleta", set(), id="url_inicial_fora"),
        pytest.param(
            "/lista-e-login",
            "falhou",
            "saude.precisa_login",
            {"/vaga/1", "/vaga/2"},
            id="login_no_meio",
        ),
    ],
)
async def test_estado_do_escopo_de_ponta_a_ponta(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    caminho: str,
    estado: str,
    motivo: str,
    abertas: set[str],
) -> None:
    url = site.url6("/lista-html") if caminho == "::1" else site.url(caminho)
    leitor = _leitor(site, ("x", url))
    _ligar(con, leitor)
    _semear(con, ANTES, leitor.chave, "x", [site.url("/vaga/99")])
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {("falso_logado", "x"): (estado, motivo)}
    # a antiga continua aberta: nenhum destes estados fecha o que não foi visto
    assert _abertas(con, leitor.chave, "x") == {"/vaga/99"} | abertas
    if caminho == "::1":
        assert site.visitas["/lista-html"] == 0


async def test_403_para_o_site_e_o_proximo_segue(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    bloqueado = _leitor(site, ("a", "/403"), ("b", "/paginada"))
    outro = _leitor(site, ("c", "/lista-html?q=c"), chave="outro_logado")
    _ligar(con, bloqueado, outro)
    anterior = _semear(con, ANTES, bloqueado.chave, "b")
    execucao_id = await _rodar(con, [bloqueado, outro], montagem.deps())
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {
        ("falso_logado", "a"): ("falhou", "saude.bloqueio"),
        ("outro_logado", "c"): ("ok", None),
    }
    assert site.visitas["/paginada"] == 0
    assert _ultima_execucao(con, bloqueado.chave, "b") == anterior


async def test_429_repetido_para_o_site_sem_gravar_os_seguintes(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("a", "/429-sempre"), ("b", "/paginada"))
    _ligar(con, leitor)
    anterior = _semear(con, ANTES, leitor.chave, "b")
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {("falso_logado", "a"): ("no_limite", "saude.parou_429")}
    assert site.visitas["/paginada"] == 0
    assert _ultima_execucao(con, leitor.chave, "b") == anterior


async def test_teto_de_10_paginas_de_lista_por_site(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    escopos = [(e, f"/quatro?q={e}") for e in "abcd"]
    leitor = _leitor(site, *escopos)
    _ligar(con, leitor)
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    # a entrada conta como uma das páginas de lista (E16)
    assert site.visitas["/logado"] + site.visitas["/quatro"] == limites.MAX_LISTA == 10
    assert _saude(con, execucao_id) == {
        ("falso_logado", "a"): ("ok", None),
        ("falso_logado", "b"): ("ok", None),
        ("falso_logado", "c"): ("parcial", "saude.listagem_incompleta"),
    }


async def test_espera_entre_3_e_8_s_em_toda_navegacao(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("a", "/paginada"), ("b", "/lista-html?q=b"))
    _ligar(con, leitor)
    sorteios = iter([3.5, 4.5, 5.5, 6.5])
    relogio = RelogioDoNavegador()
    execucao_id = await _rodar(con, [leitor], montagem.deps(lambda: next(sorteios)), relogio)
    assert execucao_id is not None
    navegacoes = site.visitas["/logado"] + site.visitas["/paginada"] + site.visitas["/lista-html"]
    assert navegacoes == 4
    # uma espera antes de cada navegação, menos a primeira
    assert relogio.dormidas == [3.5, 4.5, 5.5]


async def test_rodizio_vai_nos_mais_antigos(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "MAX_LISTA", 3)  # a entrada e mais dois escopos
    leitor = _leitor(site, *[(e, f"/lista-html?q={e}") for e in "abc"])
    _ligar(con, leitor)
    _semear(con, INICIO - timedelta(days=1), leitor.chave, "a")
    _semear(con, INICIO - timedelta(days=3), leitor.chave, "b")
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    assert set(_saude(con, execucao_id)) == {("falso_logado", "b"), ("falso_logado", "c")}


@pytest.mark.parametrize("caso", ["busca_removida", "pulado_pelo_teto", "parou_na_entrada"])
async def test_escopos_extintos(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    caso: str,
) -> None:
    if caso == "busca_removida":
        leitor = LeitorDeTeste(base=site.url(""))  # um escopo por termo das buscas
        _ligar(con, leitor)
        hoje = date.today()
        criar_busca(con, Busca(nome="p", cargos=("python",)), ANTES, regras_ligadas=True, hoje=hoje)
        java = criar_busca(
            con, Busca(nome="j", cargos=("java",)), ANTES, regras_ligadas=True, hoje=hoje
        )
        assert await _rodar(con, [leitor], montagem.deps()) is not None
        assert _abertas(con, leitor.chave, "java") == {"/vaga/1", "/vaga/2"}
        apagar_busca(con, java)
        relogio = RelogioDoNavegador(INICIO + timedelta(hours=4))
        assert await _rodar(con, [leitor], montagem.deps(), relogio) is not None
        assert _abertas(con, leitor.chave, "java") == set()
        assert _abertas(con, leitor.chave, "python") == {"/vaga/1", "/vaga/2"}
    elif caso == "pulado_pelo_teto":
        monkeypatch.setattr(limites, "MAX_LISTA", 2)  # a entrada e um escopo
        leitor = _leitor(site, ("a", "/lista-html?q=a"), ("c", "/paginada"))
        _ligar(con, leitor)
        _semear(con, ANTES, leitor.chave, "c", [site.url("/vaga/99")])
        execucao_id = await _rodar(con, [leitor], montagem.deps())
        assert execucao_id is not None
        assert set(_saude(con, execucao_id)) == {("falso_logado", "a")}
        assert _abertas(con, leitor.chave, "c") == {"/vaga/99"}
    else:
        leitor = _leitor(site, ("a", "/lista-html?q=a"), url_entrada=site.url("/login"))
        _ligar(con, leitor)
        _semear(con, ANTES, leitor.chave, "velho", [site.url("/vaga/99")])
        execucao_id = await _rodar(con, [leitor], montagem.deps())
        assert execucao_id is not None
        assert _saude(con, execucao_id) == {("falso_logado", ""): ("falhou", "saude.precisa_login")}
        assert _abertas(con, leitor.chave, "velho") == {"/vaga/99"}


async def test_escopos_que_quebram_gravam_falhou_e_nao_fecham(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    quebrado = _leitor(site, quebrar=True)
    outro = _leitor(site, ("b", "/lista-html?q=b"), chave="outro_logado")
    _ligar(con, quebrado, outro)
    _semear(con, ANTES, quebrado.chave, "velho", [site.url("/vaga/99")])
    caplog.set_level(logging.INFO, logger="jobot")
    execucao_id = await _rodar(con, [quebrado, outro], montagem.deps())
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {
        ("falso_logado", ""): ("falhou", "saude.excecao:RuntimeError"),
        ("outro_logado", "b"): ("ok", None),
    }
    assert _abertas(con, quebrado.chave, "velho") == {"/vaga/99"}
    assert any(r.exc_info for r in caplog.records)


async def test_banco_quebrado_interrompe_com_banco(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leitor = _leitor(site, ("a", "/lista-html?q=a"))
    outro = _leitor(site, ("b", "/lista-html?q=b"), chave="outro_logado")
    _ligar(con, leitor, outro)

    def quebrar(*_: Any) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(execucao, "gravar_escopo", quebrar)
    with pytest.raises(sqlite3.OperationalError):
        await _rodar(con, [leitor, outro], montagem.deps())
    execucao_id = con.execute("SELECT max(id) FROM execucao").fetchone()[0]
    assert _execucao(con, execucao_id) == ("login", "interrompida", "banco")
    assert _saude(con, execucao_id) == {}
    assert site.visitas["/lista-html"] == 1  # o segundo site não foi lido


async def test_erro_do_playwright_com_o_navegador_aberto_falha_so_o_site(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(limites, "ESPERA_FECHAR_S", 0.05)
    with socket.socket() as livre:
        livre.bind(("127.0.0.1", 0))
        porta = livre.getsockname()[1]  # fechada: o `goto` recebe conexão recusada
    caido = _leitor(site, ("a", f"http://127.0.0.1:{porta}/x?q=segredo"))
    outro = _leitor(site, ("b", "/lista-html?q=b"), chave="outro_logado")
    _ligar(con, caido, outro)
    caplog.set_level(logging.DEBUG, logger="jobot")
    execucao_id = await _rodar(con, [caido, outro], montagem.deps())
    assert execucao_id is not None
    assert _execucao(con, execucao_id) == ("login", "concluida", None)
    assert _saude(con, execucao_id) == {
        ("falso_logado", ""): ("falhou", "saude.excecao:Error"),
        ("outro_logado", "b"): ("ok", None),
    }
    # a mensagem do Playwright traz a URL com a query: no log vai só o nome do erro
    assert not any(r.exc_info for r in caplog.records)
    assert "segredo" not in caplog.text


async def test_entrada_recusada_pela_politica_grava_listagem_incompleta(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("a", "/lista-html?q=a"), url_entrada=site.url6("/logado"))
    _ligar(con, leitor)
    _semear(con, ANTES, leitor.chave, "velho", [site.url("/vaga/99")])
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {
        ("falso_logado", ""): ("falhou", "saude.listagem_incompleta")
    }
    assert site.visitas["/logado"] == site.visitas["/lista-html"] == 0
    assert _abertas(con, leitor.chave, "velho") == {"/vaga/99"}


async def test_fechar_durante_a_conferencia_nao_grava_o_escopo(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = visitar

    async def visitar_e_fechar(aba: Any, url: str, *argumentos: Any, **nomeados: Any) -> Any:
        if url.endswith("q=cf"):  # fecha enquanto confere a página, como no `_e_cloudflare`
            await aba.context.close()
            return "captcha"
        return await original(aba, url, *argumentos, **nomeados)

    monkeypatch.setattr(execucao, "visitar", visitar_e_fechar)
    leitor = _leitor(site, ("a", "/lista-html?q=a"), ("b", "/lista-html?q=cf"))
    _ligar(con, leitor)
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    assert _execucao(con, execucao_id) == ("login", "interrompida", "fechado")
    assert _saude(con, execucao_id) == {("falso_logado", "a"): ("ok", None)}


async def test_execucao_sem_captcha_nao_faz_post(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("a", "/lista-html?q=a"), url_entrada=site.url("/logado"))
    _ligar(con, leitor)
    execucao_id = await _rodar(con, [leitor], montagem.deps())
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {("falso_logado", "a"): ("ok", None)}
    assert site.visitas["/logado"] == 1
    assert (site.posts, site.campos_mudados) == (0, 0)


async def test_site_desligado_grava_desligada(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    desligado = _leitor(site, ("a", "/paginada"))
    ligado = _leitor(site, ("b", "/lista-html?q=b"), chave="outro_logado")
    _ligar(con, ligado)
    _ligar(con, desligado, ligada=False)
    # controle: sem site ligado, nenhuma execução abre
    assert await _rodar(con, [desligado], montagem.deps()) is None
    assert con.execute("SELECT count(*) FROM execucao").fetchone()[0] == 0
    execucao_id = await _rodar(con, [desligado, ligado], montagem.deps())
    assert execucao_id is not None
    assert _saude(con, execucao_id) == {
        ("falso_logado", ""): ("desligada", None),
        ("outro_logado", "b"): ("ok", None),
    }
    assert site.visitas["/paginada"] == 0


def _deps_sem_navegador(
    tmp_path: Path, ambiente: Mapping[str, str], lancados: list[dict[str, Any]]
) -> Dependencias:
    async def lancar(**argumentos: Any) -> BrowserContext:
        lancados.append(argumentos)
        raise RuntimeError("sem bibliotecas do sistema")

    return Dependencias(
        dados=tmp_path,
        lancar=lancar,
        ambiente=lambda: ambiente,
        politica=lambda leitor: lambda url: True,
        sortear=lambda: limites.ESPERA_MIN_S,
        cofre=Cofre(tmp_path, CofreFalso()),
        avisar=lambda titulo, frase: None,
    )


async def test_sem_tela_grava_sem_tela_e_nao_lanca(
    site: SiteFalso, con: sqlite3.Connection, tmp_path: Path
) -> None:
    um = _leitor(site, ("a", "/paginada"))
    dois = _leitor(site, ("b", "/paginada"), chave="outro_logado")
    _ligar(con, um, dois)
    lancados: list[dict[str, Any]] = []
    execucao_id = await _rodar(con, [um, dois], _deps_sem_navegador(tmp_path, {}, lancados))
    assert execucao_id is not None
    assert lancados == []
    assert _execucao(con, execucao_id) == ("login", "concluida", None)
    assert _saude(con, execucao_id) == {
        ("falso_logado", ""): ("falhou", "saude.sem_tela"),
        ("outro_logado", ""): ("falhou", "saude.sem_tela"),
    }


async def test_sem_navegador_grava_sem_navegador(
    site: SiteFalso, con: sqlite3.Connection, tmp_path: Path
) -> None:
    leitor = _leitor(site, ("a", "/paginada"))
    _ligar(con, leitor)
    lancados: list[dict[str, Any]] = []
    deps = _deps_sem_navegador(tmp_path, {"DISPLAY": ":0"}, lancados)
    execucao_id = await _rodar(con, [leitor], deps)
    assert execucao_id is not None
    assert len(lancados) == 2  # o Chrome e o Chromium
    assert _execucao(con, execucao_id) == ("login", "concluida", None)
    assert _saude(con, execucao_id) == {("falso_logado", ""): ("falhou", "saude.sem_navegador")}


async def test_fechar_o_navegador_interrompe_com_fechado(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    leitor = _leitor(site, ("a", "/lista-html?q=a"), ("b", "/fechar"))
    depois = _leitor(site, ("c", "/paginada"), chave="outro_logado")
    _ligar(con, leitor, depois)
    montagem.fechar_em.add("/fechar")
    caplog.set_level(logging.DEBUG, logger="jobot")
    execucao_id = await _rodar(con, [leitor, depois], montagem.deps())
    assert execucao_id is not None
    assert _execucao(con, execucao_id) == ("login", "interrompida", "fechado")
    assert _saude(con, execucao_id) == {("falso_logado", "a"): ("ok", None)}
    assert _abertas(con, leitor.chave, "a") == {"/vaga/1", "/vaga/2"}
    assert site.visitas["/paginada"] == 0
    assert [r.getMessage() for r in caplog.records if r.exc_info] == []


class RelogioQuePrende(RelogioDoNavegador):
    """Prende para sempre na espera de `PRENDE` segundos: o teste cancela ali."""

    PRENDE = 5.0

    def __init__(self) -> None:
        super().__init__()
        self.preso = asyncio.Event()

    async def dormir(self, s: float) -> None:
        if s == self.PRENDE:
            self.preso.set()
            await asyncio.Event().wait()
        await super().dormir(s)


async def test_cancelar_a_leitura_fecha_o_navegador(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("a", "/lista-html?q=a"))
    _ligar(con, leitor)
    relogio = RelogioQuePrende()
    deps = montagem.deps(lambda: RelogioQuePrende.PRENDE)
    tarefa = asyncio.create_task(_rodar(con, [leitor], deps, relogio))
    preso = asyncio.create_task(relogio.preso.wait())
    await asyncio.wait({tarefa, preso}, return_when=asyncio.FIRST_COMPLETED)
    preso.cancel()
    assert relogio.preso.is_set()  # parou na espera antes do escopo
    assert len(montagem.contextos) == 1
    fechou = asyncio.Event()
    montagem.contextos[0].on("close", lambda _: fechou.set())
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa
    assert fechou.is_set()  # o finally fechou o contexto, não só a aba
    execucao_id = con.execute("SELECT max(id) FROM execucao").fetchone()[0]
    assert _execucao(con, execucao_id) == ("login", "interrompida", "fechado")


async def test_dependencias_de_producao_fecham_o_playwright(
    site: SiteFalso, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class PlaywrightFalso:
        saidas = 0

        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            self.saidas += 1

    falso = PlaywrightFalso()
    monkeypatch.setattr(execucao, "async_playwright", lambda: falso)
    lancados: list[tuple[Mapping[str, str], dict[str, object]]] = []

    def lancador_falso(_playwright: object, ambiente: Mapping[str, str]) -> object:
        async def lancar(**argumentos: object) -> object:
            lancados.append((ambiente, argumentos))
            return "contexto"

        return lancar

    monkeypatch.setattr(execucao, "lancador_de_producao", lancador_falso)
    leitor = _leitor(site)
    async with dependencias_de_producao(tmp_path, {"DISPLAY": ":0"}) as deps:
        assert falso.saidas == 0
        assert deps.dados == tmp_path
        assert deps.ambiente() == {"DISPLAY": ":0"}
        lancado: object = await deps.lancar(user_data_dir="x")
        assert lancado == "contexto"
        assert lancados == [({"DISPLAY": ":0"}, {"user_data_dir": "x"})]
        assert limites.ESPERA_MIN_S <= deps.sortear() <= limites.ESPERA_MAX_S
        assert not deps.politica(leitor)(site.url("/lista-html"))  # http e host local
    assert falso.saidas == 1
