"""Checagem diária de versão nova (plano T85; ADR 0018; D31).

Banco de verdade numa pasta temporária e GitHub falso por `httpx.MockTransport`: nada vai à rede.
"""

import asyncio
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot import __version__
from jobot.agenda import versao
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.http import ClienteEducado, Validadores

AGORA = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
UA = f"joBot/{__version__} (+https://github.com/fezarosa-dev/joBot)"


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


class _GitHub:
    """GitHub falso: anota os pedidos e responde com a etiqueta dada (ou com `resposta`)."""

    def __init__(self, etiqueta: str = "v99.0.0") -> None:
        self.pedidos: list[httpx.Request] = []
        self.resposta: Callable[[httpx.Request], httpx.Response] = lambda _: httpx.Response(
            200, json={"tag_name": etiqueta, "name": "qualquer"}
        )

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        return self.resposta(pedido)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(abrir(tmp_path / "jobot.db")) as conexao:
        migrar(conexao, tmp_path / "jobot.db")
        yield conexao


def _checar(con: sqlite3.Connection, github: _GitHub, relogio: RelogioFalso) -> None:
    async def rodar() -> None:
        cliente = ClienteEducado(
            httpx.MockTransport(github), relogio, _SemValidadores(), __version__
        )
        try:
            await versao.checar_versao_nova(con, cliente, relogio)
        finally:
            await cliente.fechar()

    asyncio.run(rodar())


def test_checa_uma_vez_por_dia(con: sqlite3.Connection) -> None:
    gravar_config(con, "aviso_versao_ligada", True)
    github = _GitHub()
    relogio = RelogioFalso(AGORA)
    _checar(con, github, relogio)
    _checar(con, github, relogio)
    assert len(github.pedidos) == 1
    relogio._agora = AGORA + timedelta(hours=23, minutes=59)
    _checar(con, github, relogio)
    assert len(github.pedidos) == 1
    relogio._agora = AGORA + timedelta(days=1)
    _checar(con, github, relogio)
    assert len(github.pedidos) == 2


def test_checagem_no_futuro_conta_como_vencida(con: sqlite3.Connection) -> None:
    # RF4: relógio que voltou não pode travar a checagem para sempre
    gravar_config(con, "aviso_versao_ligada", True)
    gravar_config(con, "versao_checada_em", (AGORA + timedelta(days=30)).isoformat())
    github = _GitHub()
    _checar(con, github, RelogioFalso(AGORA))
    assert len(github.pedidos) == 1


@pytest.mark.parametrize(
    ("atual", "etiqueta", "avisa"),
    [
        ("0.1.0", "v0.1.0", False),
        ("0.1.0", "v0.0.9", False),
        ("0.1.0", "0.1.1", True),
        ("0.1.0", "v1.0.0", True),
        ("0.9.0", "v0.10.0", True),  # compara inteiros, não texto
        ("0.10.0", "v0.9.0", False),
    ],
)
def test_aviso_so_para_versao_maior(
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    atual: str,
    etiqueta: str,
    avisa: bool,
) -> None:
    monkeypatch.setattr(versao, "__version__", atual)
    gravar_config(con, "aviso_versao_ligada", True)
    gravar_config(con, "versao_nova", etiqueta)
    assert versao.versao_para_avisar(con) == (etiqueta if avisa else None)


def test_aviso_desligado_nao_mostra_versao_gravada(con: sqlite3.Connection) -> None:
    gravar_config(con, "versao_nova", "v99.0.0")
    assert versao.versao_para_avisar(con) is None
    gravar_config(con, "aviso_versao_ligada", False)
    assert versao.versao_para_avisar(con) is None


@pytest.mark.parametrize(
    "falha",
    [
        lambda _: httpx.Response(403),
        lambda _: httpx.Response(404),
        lambda _: httpx.Response(200, text="não é json"),
        lambda _: httpx.Response(200, json=["lista"]),
        lambda _: httpx.Response(200, json={"tag_name": 3}),
        lambda _: httpx.Response(200, json={"name": "sem tag_name"}),
    ],
    ids=["403", "404", "json_ruim", "lista", "etiqueta_numero", "sem_etiqueta"],
)
def test_falha_de_rede_na_checagem_mantem_o_aviso(
    con: sqlite3.Connection, falha: Callable[[httpx.Request], httpx.Response]
) -> None:
    gravar_config(con, "aviso_versao_ligada", True)
    gravar_config(con, "versao_nova", "v99.0.0")
    gravar_config(con, "versao_checada_em", (AGORA - timedelta(days=2)).isoformat())
    github = _GitHub()
    github.resposta = falha
    relogio = RelogioFalso(AGORA)
    _checar(con, github, relogio)
    assert len(github.pedidos) >= 1
    assert ler_config(con, "versao_nova", None) == "v99.0.0"
    assert versao.versao_para_avisar(con) == "v99.0.0"
    # houve resposta do servidor: a hora conta, e a próxima volta do laço não pergunta de novo
    pedidos = len(github.pedidos)
    relogio._agora = AGORA + timedelta(hours=1)
    _checar(con, github, relogio)
    assert len(github.pedidos) == pedidos


def test_erro_de_conexao_na_checagem_mantem_o_aviso(con: sqlite3.Connection) -> None:
    gravar_config(con, "aviso_versao_ligada", True)
    gravar_config(con, "versao_nova", "v99.0.0")
    github = _GitHub()

    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    github.resposta = cai
    relogio = RelogioFalso(AGORA)
    _checar(con, github, relogio)
    assert len(github.pedidos) >= 1
    assert ler_config(con, "versao_nova", None) == "v99.0.0"
    # sem resposta do servidor a hora não conta: a próxima volta do laço tenta de novo
    pedidos = len(github.pedidos)
    relogio._agora = AGORA + timedelta(hours=1)
    _checar(con, github, relogio)
    assert len(github.pedidos) > pedidos


@pytest.mark.parametrize(
    "etiqueta",
    [
        "nightly",
        "v2.0-beta",
        "",
        "1.2.3\n",
        "v١.٢.٣",
        "1.2.3" + "0" * 30,
        "v1.2." + "9" * 5000,
    ],
    ids=["nightly", "beta", "vazia", "quebra_de_linha", "digitos_arabes", "35_chars", "5000_noves"],
)
def test_etiqueta_fora_do_padrao_e_ignorada(con: sqlite3.Connection, etiqueta: str) -> None:
    gravar_config(con, "aviso_versao_ligada", True)
    github = _GitHub(etiqueta)
    _checar(con, github, RelogioFalso(AGORA))
    assert len(github.pedidos) == 1
    assert ler_config(con, "versao_nova", None) is None
    assert versao.versao_para_avisar(con) is None


def test_etiqueta_valida_grava(con: sqlite3.Connection) -> None:
    # controle do teste acima
    gravar_config(con, "aviso_versao_ligada", True)
    _checar(con, _GitHub("v1.2.3"), RelogioFalso(AGORA))
    assert ler_config(con, "versao_nova", None) == "v1.2.3"
    assert ler_config(con, "versao_checada_em", None) == AGORA.isoformat()


def test_checagem_leva_so_o_user_agent_fixo(con: sqlite3.Connection) -> None:
    gravar_config(con, "aviso_versao_ligada", True)
    github = _GitHub()
    _checar(con, github, RelogioFalso(AGORA))
    assert len(github.pedidos) == 1
    pedido = github.pedidos[0]
    assert pedido.method == "GET"
    assert str(pedido.url) == versao.URL_VERSOES
    assert pedido.url.host == "api.github.com"
    assert pedido.url.query == b""
    assert pedido.headers["user-agent"] == UA
    nomes = {nome.lower() for nome in pedido.headers}
    assert nomes <= {"host", "user-agent", "accept", "accept-encoding", "connection"}
    assert not nomes & {"cookie", "authorization", "origin", "referer"}


def test_laco_versao_usa_conexao_propria_e_a_fecha_ao_cancelar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as preparo:
        migrar(preparo, banco)
    abertas: list[tuple[Path, sqlite3.Connection]] = []

    def abrir_anotando(caminho: Path) -> sqlite3.Connection:
        conexao = abrir(caminho)
        abertas.append((caminho, conexao))
        return conexao

    class _RelogioParado(RelogioFalso):
        async def dormir(self, s: float) -> None:
            self.dormidas.append(s)
            await asyncio.Event().wait()

    monkeypatch.setattr(versao, "abrir", abrir_anotando)
    relogio = _RelogioParado(AGORA)

    async def rodar() -> None:
        cliente = ClienteEducado(
            httpx.MockTransport(_GitHub()), relogio, _SemValidadores(), __version__
        )
        tarefa = asyncio.create_task(versao.laco_versao(banco, cliente, relogio))
        while not relogio.dormidas and not tarefa.done():
            await asyncio.sleep(0)
        assert not tarefa.done()
        assert len(abertas) == 1
        abertas[0][1].execute("SELECT 1")  # aberta enquanto o laço vive
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa
        await cliente.fechar()

    asyncio.run(rodar())
    assert relogio.dormidas == [versao.INTERVALO_S]
    assert [caminho for caminho, _ in abertas] == [banco]
    with pytest.raises(sqlite3.ProgrammingError):
        abertas[0][1].execute("SELECT 1")  # fechada depois do cancel


def test_laco_versao_sobrevive_a_erro_na_checagem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as preparo:
        migrar(preparo, banco)
    voltas: list[int] = []

    async def checar_que_quebra(*_: object) -> None:
        voltas.append(1)
        raise sqlite3.OperationalError("banco ocupado")

    class _RelogioContado(RelogioFalso):
        async def dormir(self, s: float) -> None:
            await super().dormir(s)
            if len(self.dormidas) >= 2:
                await asyncio.Event().wait()

    monkeypatch.setattr(versao, "checar_versao_nova", checar_que_quebra)
    relogio = _RelogioContado(AGORA)

    async def rodar() -> None:
        tarefa = asyncio.create_task(
            versao.laco_versao(banco, cast(ClienteEducado, object()), relogio)
        )
        while len(relogio.dormidas) < 2 and not tarefa.done():
            await asyncio.sleep(0)
        assert not tarefa.done()
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa

    asyncio.run(rodar())
    assert len(voltas) == 2
