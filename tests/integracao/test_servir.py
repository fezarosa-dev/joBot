"""Comandos `serve` e `buscar` e rota `/saude-local` (plano T48; desenho 12.1 a 12.3, 12.6, 14.1).

O banco é de verdade, numa pasta temporária; a busca e o laço da agenda são trocados por falsos
pelo nome importado em `cli/servir.py` e `cli/buscar.py`, para nenhum teste ir à rede.
"""

import argparse
import asyncio
import contextlib
import importlib
import logging
import os
import socket
import sqlite3
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from datetime import time as hora
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

import jobot
from apoio.relogio import RelogioFalso
from jobot.agenda.agendador import o_que_roda
from jobot.agenda.login import Login
from jobot.banco.cadastros import gravar_config, ligar_fonte, semear_leitores
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao, gravar_saude
from jobot.banco.migrar import migrar
from jobot.cli import COMANDOS, buscar, servir
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.leitores import registro
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.nucleo.relogio import Relogio
from jobot.painel.app import criar_app
from jobot.sistema import llama
from jobot.sistema.instancia import AVISO_CAPTURA, Trava, pid_do_servidor

pytestmark = pytest.mark.usefixtures("laco_versao_parado")

PORTA = 47999
BASE = f"http://127.0.0.1:{PORTA}"
# 01:00 em UTC é 22:00 do dia 13 em -03: o dia local (DP8) é 13, o dia UTC é 14.
AGORA = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)
HOJE_LOCAL = date(2026, 11, 13)


class _RelogioRapido(RelogioFalso):
    """Cada `dormir` avança a hora falsa e solta o laço de eventos por 10 ms de verdade."""

    async def dormir(self, s: float) -> None:
        await super().dormir(s)
        await asyncio.sleep(0.01)


@pytest.fixture
def dados(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    return pasta


@pytest.fixture
def fuso_local() -> Iterator[None]:
    antes = os.environ.get("TZ")
    os.environ["TZ"] = "America/Sao_Paulo"
    time.tzset()
    yield
    if antes is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = antes
    time.tzset()


def _banco(dados: Path) -> sqlite3.Connection:
    con = abrir(dados / "jobot.db")
    migrar(con, dados / "jobot.db")
    return con


def _esperar(condicao: Callable[[], bool], s: float = 5.0) -> bool:
    fim = time.monotonic() + s
    while not condicao():
        if time.monotonic() >= fim:
            return False
        time.sleep(0.01)
    return True


def test_todo_comando_da_tabela_resolve() -> None:
    sem_executar = []
    for nome, modulo in COMANDOS.items():
        try:
            achado = importlib.import_module(modulo)
        except ImportError:
            sem_executar.append(nome)
            continue
        if not callable(getattr(achado, "executar", None)):
            sem_executar.append(nome)
    assert sem_executar == []


def test_saude_local_responde_jobot_e_versao(dados: Path) -> None:
    _banco(dados).close()  # sem linha `segundo_plano`: vale desligado (desenho 5.5)
    cliente = TestClient(criar_app(dados, PORTA), base_url=BASE)
    resposta = cliente.get("/saude-local")
    assert resposta.status_code == 200
    assert resposta.json() == {
        "app": "jobot",
        "versao": jobot.__version__,
        "segundo_plano": False,
    }


@pytest.mark.parametrize(("gravado", "esperado"), [(True, True), (False, False), ("sim", False)])
def test_saude_local_diz_o_segundo_plano(dados: Path, gravado: object, esperado: bool) -> None:
    with closing(_banco(dados)) as con:
        gravar_config(con, "segundo_plano", gravado)
    cliente = TestClient(criar_app(dados, PORTA), base_url=BASE)
    assert cliente.get("/saude-local").json().get("segundo_plano") is esperado


def test_escuta_so_em_127(dados: Path) -> None:
    app, config = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    assert config.host == "127.0.0.1"
    assert config.port == PORTA
    assert config.server_header is False
    assert config.proxy_headers is False
    assert config.app is app


def test_monta_sem_console_como_no_pythonw(dados: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # a tarefa do Windows roda `pythonw -m jobot serve`: lá sys.stdout e sys.stderr são None
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    _, config = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    assert config.use_colors is False


def test_ao_subir_marca_interrompidas_migra_e_semeia(dados: Path) -> None:
    servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    with closing(abrir(dados / "jobot.db")) as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] > 0  # migrou
        assert con.execute("SELECT count(*) FROM fonte").fetchone()[0] > 0  # semeou
        velha = abrir_execucao(con, "busca", "agenda", AGORA - timedelta(minutes=10))
        nova = abrir_execucao(con, "descoberta", "agenda", AGORA - timedelta(minutes=1))

    servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    with closing(abrir(dados / "jobot.db")) as con:
        estados = dict(con.execute("SELECT id, estado FROM execucao").fetchall())
    assert estados == {velha: "interrompida", nova: "rodando"}  # batimento de 5 min (12.3)


def _espiar(monkeypatch: pytest.MonkeyPatch, nome: str, chamadas: list[dict[str, Any]]) -> None:
    def falso(con: sqlite3.Connection, *args: Any, **kwargs: Any) -> None:
        chamadas.append({"args": args, **kwargs})

    monkeypatch.setattr(servir, nome, falso)


@pytest.mark.usefixtures("fuso_local")
def test_reprocessa_quando_as_regras_mudam(dados: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mudadas = [1]
    monkeypatch.setattr(servir, "reprocessar_se_regras_mudaram", lambda con: mudadas.pop())
    cotacoes: list[dict[str, Any]] = []
    encaixes: list[dict[str, Any]] = []
    _espiar(monkeypatch, "aplicar_cotacoes", cotacoes)
    _espiar(monkeypatch, "recalcular_encaixe", encaixes)

    servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    # aplica na hora: as `_brl` e o encaixe das vagas reprocessadas saem novos, com o dia local
    assert cotacoes == [{"args": (), "conversao_ligada": True, "hoje": HOJE_LOCAL}]
    assert encaixes == [{"args": (None, True), "hoje": HOJE_LOCAL}]

    monkeypatch.setattr(servir, "reprocessar_se_regras_mudaram", lambda con: 0)
    servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    assert len(cotacoes) == 1 and len(encaixes) == 1  # nada mudou: nada a recalcular


def test_laco_da_agenda_sobe_com_o_app(dados: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with closing(_banco(dados)) as con:  # a última busca completa foi há 5 h: a perdida recupera
        gravar_config(con, "primeira_execucao_concluida", True)
        antiga = abrir_execucao(con, "busca", "agenda", AGORA - timedelta(hours=5))
        assert antiga is not None
        fechar_execucao(con, antiga, AGORA - timedelta(hours=5))
    motivos: list[str] = []

    async def busca_falsa(
        con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio, motivo: str, **_: object
    ) -> None:
        assert isinstance(cliente, ClienteEducado)
        motivos.append(motivo)

    monkeypatch.setattr(servir, "executar_busca", busca_falsa)
    app, _ = servir.montar(dados, PORTA, relogio=_RelogioRapido(AGORA))
    with TestClient(app, base_url=BASE):
        assert _esperar(lambda: len(motivos) >= 2), "o laço da agenda não disparou a busca"
    assert motivos[:2] == ["recuperacao", "agenda"]
    parou_em = len(motivos)
    time.sleep(0.1)
    assert len(motivos) == parou_em  # o laço para junto com o app


def test_agenda_nao_dispara_nada_antes_da_primeira_execucao(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with closing(_banco(dados)):  # pasta nova: `primeira_execucao_concluida` ausente
        pass
    chamadas: list[str] = []

    async def falsa(*_: object) -> None:
        chamadas.append("x")

    for nome in ("executar_busca", "executar_descoberta", "executar_paginas"):
        monkeypatch.setattr(servir, nome, falsa)
    app, _ = servir.montar(dados, PORTA, relogio=_RelogioRapido(AGORA))
    with TestClient(app, base_url=BASE):
        time.sleep(0.3)  # várias voltas do laço (passou a espera de 60 s, o tempo é falso)
    assert chamadas == []


@pytest.mark.parametrize("valor", [None, False, True])
def test_estado_so_liga_a_agenda_com_a_primeira_execucao_concluida(
    dados: Path, valor: bool | None
) -> None:
    with closing(_banco(dados)) as con:
        if valor is not None:
            gravar_config(con, "primeira_execucao_concluida", valor)
    interruptores = servir._EstadoDoBanco(dados / "jobot.db").interruptores()
    vencidos = o_que_roda(AGORA, None, None, None, AGORA - timedelta(hours=1), interruptores)
    assert vencidos == (["busca", "descoberta", "paginas"] if valor is True else [])


def _com_leitor(monkeypatch: pytest.MonkeyPatch, con: sqlite3.Connection, ligada: bool) -> None:
    leitor = cast(LeitorComLogin, SimpleNamespace(chave="teste_logado"))
    monkeypatch.setattr(registro, "LEITORES", (leitor,))
    semear_leitores(con, [leitor])
    ligar_fonte(con, "teste_logado", ligada)


def test_horarios_tortos_no_banco_valem_o_padrao(
    dados: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with closing(_banco(dados)) as con:
        _com_leitor(monkeypatch, con, True)
        gravar_config(con, "login_horarios", "x")
    with caplog.at_level(logging.WARNING, logger="jobot.cli.servir"):
        login = servir._EstadoDoBanco(dados / "jobot.db").login()
    assert login == Login((hora(9), hora(18)), None)
    chave = "configuracoes.sites_com_login.horarios.formato"
    assert [r.getMessage() for r in caplog.records if chave in r.getMessage()]


def test_horarios_tortos_avisam_uma_vez_por_valor(
    dados: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # o laço lê o estado a cada 60 s: o mesmo valor torto não enche o log
    with closing(_banco(dados)) as con:
        _com_leitor(monkeypatch, con, True)
        gravar_config(con, "login_horarios", "x")
    estado = servir._EstadoDoBanco(dados / "jobot.db")
    with caplog.at_level(logging.WARNING, logger="jobot.cli.servir"):
        estado.login()
        estado.login()
        with closing(abrir(dados / "jobot.db")) as con:
            gravar_config(con, "login_horarios", "y")
        estado.login()
    avisos = [r for r in caplog.records if "login_horarios" in r.getMessage()]
    assert len(avisos) == 2


def test_estado_login_le_horarios_e_ultima_do_banco(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with closing(_banco(dados)) as con:
        _com_leitor(monkeypatch, con, True)
        gravar_config(con, "login_horarios", ["20:00", "08:00"])
        id_ = abrir_execucao(con, "login", "agenda", AGORA)
        assert id_ is not None
        fechar_execucao(con, id_, AGORA + timedelta(minutes=5))
    login = servir._EstadoDoBanco(dados / "jobot.db").login()
    assert login == Login((hora(8), hora(20)), AGORA)


def test_estado_login_none_sem_site_ligado(dados: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    caminho = dados / "jobot.db"
    with closing(_banco(dados)) as con:
        _com_leitor(monkeypatch, con, False)
    assert servir._EstadoDoBanco(caminho).login() is None
    # fonte com login ligada no banco, mas sem leitor registrado: também não roda
    with closing(abrir(caminho)) as con:
        ligar_fonte(con, "teste_logado", True)
    monkeypatch.setattr(registro, "LEITORES", ())
    assert servir._EstadoDoBanco(caminho).login() is None


def test_login_parado_antes_da_primeira_execucao(dados: Path) -> None:
    caminho = dados / "jobot.db"
    with closing(_banco(dados)):
        pass
    assert servir._EstadoDoBanco(caminho).interruptores().get("login", True) is False
    with closing(abrir(caminho)) as con:
        gravar_config(con, "primeira_execucao_concluida", True)
    assert servir._EstadoDoBanco(caminho).interruptores().get("login", True) is True


def test_laco_e_rota_buscar_agora_dividem_as_mesmas_travas(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recebidas: list[Mapping[str, asyncio.Lock] | None] = []

    async def laco_falso(
        tarefas: Mapping[str, Callable[[], Awaitable[None]]],
        estado: object,
        relogio: Relogio,
        *,
        travas: Mapping[str, asyncio.Lock] | None = None,
    ) -> None:
        recebidas.append(travas)
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "laco", laco_falso)
    app, _ = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    with TestClient(app, base_url=BASE):
        assert _esperar(lambda: bool(recebidas))
    travas: dict[str, asyncio.Lock] = app.state.travas
    assert set(travas) == {"busca", "descoberta", "paginas", "login"}
    assert all(isinstance(trava, asyncio.Lock) for trava in travas.values())
    assert recebidas[0] is travas  # o mesmo objeto, não uma cópia (D55)


def test_travas_tem_login_e_e_o_mesmo_objeto_do_laco(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recebidas: list[
        tuple[Mapping[str, Callable[[], Awaitable[None]]], Mapping[str, asyncio.Lock] | None]
    ] = []

    async def laco_falso(
        tarefas: Mapping[str, Callable[[], Awaitable[None]]],
        estado: object,
        relogio: Relogio,
        *,
        travas: Mapping[str, asyncio.Lock] | None = None,
    ) -> None:
        recebidas.append((tarefas, travas))
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "laco", laco_falso)
    app, _ = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    with TestClient(app, base_url=BASE):
        assert _esperar(lambda: bool(recebidas))
    tarefas, travas = recebidas[0]
    assert travas is app.state.travas  # o mesmo objeto que o "Buscar agora" usa (D55)
    assert travas is not None
    assert isinstance(travas.get("login"), asyncio.Lock)
    assert "login" in tarefas
    assert app.state.tarefa_login is tarefas["login"]  # a rota dispara a mesma tarefa do laço


def test_tarefa_login_usa_as_dependencias_de_producao(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps = object()
    eventos: list[str] = []
    chamadas: list[dict[str, Any]] = []

    @contextlib.asynccontextmanager
    async def producao_falsa(pasta: Path, env: Mapping[str, str]) -> AsyncIterator[object]:
        eventos.append(f"abriu:{pasta == dados}:{env.get('JOBOT_TESTE')}")
        yield deps
        eventos.append("fechou")

    async def login_falso(
        con: sqlite3.Connection, cliente: Any, relogio: Any, motivo: str, **kw: Any
    ) -> None:
        con.execute("SELECT 1")  # a conexão própria está aberta durante a leitura
        chamadas.append({"cliente": cliente, "relogio": relogio, "motivo": motivo, **kw})

    leitor = cast(LeitorComLogin, SimpleNamespace(chave="teste_logado"))
    monkeypatch.setattr(registro, "LEITORES", (leitor,))
    monkeypatch.setattr(servir, "navegador_instalado", _instalado_falso([]))
    monkeypatch.setattr(servir, "laco", _parado)
    monkeypatch.setattr(servir, "dependencias_de_producao", producao_falsa)
    monkeypatch.setattr(servir, "executar_login", login_falso)
    relogio = RelogioFalso(AGORA)
    app, _ = servir.montar(dados, PORTA, relogio=relogio, env={"JOBOT_TESTE": "sim"})
    with TestClient(app, base_url=BASE) as http:
        tarefa = getattr(app.state, "tarefa_login", None)
        assert tarefa is not None, "o lifespan não guardou a tarefa login"
        portal = http.portal
        assert portal is not None  # dentro do `with` o TestClient tem o laço do app
        portal.call(tarefa)
        portal.call(tarefa, "agora")
        cliente = app.state.cliente
    assert eventos == ["abriu:True:sim", "fechou", "abriu:True:sim", "fechou"]
    assert [c["motivo"] for c in chamadas] == ["agenda", "agora"]
    assert all(c["deps"] is deps and c["cliente"] is cliente for c in chamadas)
    assert all(c["relogio"] is relogio and c["leitores"] == (leitor,) for c in chamadas)


async def _parado(*_: object, **__: object) -> None:
    await asyncio.Event().wait()


def test_servidor_encerra_a_sobra_do_llama_ao_subir_e_ao_parar(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # desenho 7: a subida do servidor encerra a sobra; a instância cai quando ele para (D194.4)
    chamadas: list[Path] = []
    monkeypatch.setattr(llama, "encerrar_sobra", chamadas.append)
    monkeypatch.setattr(servir, "laco", _parado)
    app, _ = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    assert chamadas == []
    with TestClient(app, base_url=BASE):
        assert chamadas == [dados]
    assert chamadas == [dados, dados]


def _instalado_falso(chamadas: list[str]) -> Callable[[], Awaitable[str | None]]:
    async def instalado() -> str | None:
        chamadas.append("x")
        return "chrome"

    return instalado


def test_servir_so_sobe_o_driver_com_leitor(dados: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []
    monkeypatch.setattr(servir, "navegador_instalado", _instalado_falso(chamadas))
    monkeypatch.setattr(servir, "laco", _parado)
    monkeypatch.setattr(registro, "LEITORES", ())
    app, _ = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    with TestClient(app, base_url=BASE):
        pass
    assert chamadas == []  # sem leitor registrado, o driver do Playwright nem sobe
    assert not hasattr(app.state, "navegador_instalado")
    # controle: com um leitor registrado, calcula uma vez ao subir e guarda em app.state
    leitor = cast(LeitorComLogin, SimpleNamespace(chave="teste_logado"))
    monkeypatch.setattr(registro, "LEITORES", (leitor,))
    app, _ = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    with TestClient(app, base_url=BASE) as http:
        http.get("/saude-local")
    assert chamadas == ["x"]
    assert app.state.navegador_instalado == "chrome"


@pytest.fixture
def isolado(dados: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """`executar` mexe no umask e no logger `jobot`: o teste devolve os dois como estavam."""
    monkeypatch.setenv("JOBOT_DADOS", str(dados))
    umask = os.umask(0o022)
    os.umask(umask)
    raiz = logging.getLogger("jobot")
    handlers, nivel = list(raiz.handlers), raiz.level
    yield dados
    os.umask(umask)
    for handler in [h for h in raiz.handlers if h not in handlers]:
        raiz.removeHandler(handler)
        handler.close()
    raiz.setLevel(nivel)


def test_buscar_roda_uma_busca_e_imprime_o_resumo(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    motivos: list[str] = []

    async def busca_falsa(
        con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio, motivo: str
    ) -> int | None:
        assert isinstance(cliente, ClienteEducado)
        motivos.append(motivo)
        execucao_id = abrir_execucao(con, "busca", motivo, AGORA)  # type: ignore[arg-type]
        assert execucao_id is not None
        gravar_saude(con, execucao_id, "remotive", "", "ok", vagas=7)
        gravar_saude(con, execucao_id, "lever", "acme", "falhou", vagas=0, motivo="saude.bloqueio")
        fechar_execucao(con, execucao_id, AGORA)
        return execucao_id

    monkeypatch.setattr(buscar, "executar_busca", busca_falsa)
    assert buscar.executar(argparse.Namespace(comando="buscar")) == 0
    assert motivos == ["agora"]
    saida = capsys.readouterr().out
    assert "remotive" in saida and "ok" in saida and "7" in saida
    assert "lever acme" in saida and "falhou" in saida and "A fonte bloqueou o acesso" in saida
    assert (isolado / "jobot.db").exists()
    assert (isolado / "jobot.db").stat().st_mode & 0o077 == 0  # D7: o banco nasce 0600


def _buscar_com_motivo(
    motivo: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> str:
    async def busca_falsa(con: sqlite3.Connection, *args: object) -> int | None:
        execucao_id = abrir_execucao(con, "busca", "agora", AGORA)
        assert execucao_id is not None
        gravar_saude(con, execucao_id, "lever", "acme", "falhou", vagas=0, motivo=motivo)
        fechar_execucao(con, execucao_id, AGORA)
        return execucao_id

    monkeypatch.setattr(buscar, "executar_busca", busca_falsa)
    assert buscar.executar(argparse.Namespace(comando="buscar")) == 0
    return capsys.readouterr().out


def test_buscar_imprime_o_motivo_em_portugues(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    saida = _buscar_com_motivo("saude.bloqueio", monkeypatch, capsys)
    assert "A fonte bloqueou o acesso" in saida
    assert "saude.bloqueio" not in saida


def test_buscar_traduz_motivo_com_parametro(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert "3 vagas lidas" in _buscar_com_motivo("saude.parcial_n:3", monkeypatch, capsys)
    assert "Erro inesperado: KeyError" in _buscar_com_motivo(
        "saude.excecao:KeyError", monkeypatch, capsys
    )


def test_buscar_motivo_desconhecido_sai_cru(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert "saude.nao_existe" in _buscar_com_motivo("saude.nao_existe", monkeypatch, capsys)
    # chave com texto que pede outro parâmetro levanta KeyError no format: sai crua, sem quebrar
    assert "fontes.reportar_aviso" in _buscar_com_motivo(
        "fontes.reportar_aviso", monkeypatch, capsys
    )


def test_buscar_com_outra_busca_rodando_avisa(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def busca_ocupada(*args: object) -> None:
        return None

    monkeypatch.setattr(buscar, "executar_busca", busca_ocupada)
    assert buscar.executar(argparse.Namespace(comando="buscar")) == 1
    assert "já" in capsys.readouterr().err


def test_serve_com_outro_jobot_aberto_avisa_e_sai_com_0(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # sai com 0 (D175 item 9): o KeepAlive do launchd e o Restart=on-failure do systemd
    # não refazem o serve enquanto o painel está aberto
    def montar_proibido(*args: object, **kwargs: object) -> None:
        raise AssertionError("não sobe nada com a trava presa")

    monkeypatch.setattr(servir, "montar", montar_proibido)
    monkeypatch.setenv("JOBOT_PORTA", str(PORTA))
    outro = Trava(isolado, PORTA)
    assert outro.pegar()
    try:
        assert servir.executar(argparse.Namespace(comando="serve")) == 0
    finally:
        outro.soltar()
    assert "já está aberto" in capsys.readouterr().err


def test_serve_com_captura_no_ar_diz_qual_e(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def montar_proibido(*args: object, **kwargs: object) -> None:
        raise AssertionError("não sobe nada com a trava presa")

    monkeypatch.setattr(servir, "montar", montar_proibido)
    monkeypatch.setenv("JOBOT_PORTA", str(PORTA))
    captura = Trava(isolado, 0)  # porta 0: é o `capturar_logado.py` quem prende (T215)
    assert captura.pegar()
    try:
        assert servir.executar(argparse.Namespace(comando="serve")) == 1
    finally:
        captura.soltar()
    erro = capsys.readouterr().err
    assert AVISO_CAPTURA in erro
    assert "já está aberto" not in erro


def test_serve_com_porta_ocupada_avisa_e_solta_a_trava(
    isolado: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with socket.socket() as alheio:  # outro programa escutando na porta (D23)
        alheio.bind(("127.0.0.1", 0))
        alheio.listen()
        ocupada = alheio.getsockname()[1]
        monkeypatch.setenv("JOBOT_PORTA", str(ocupada))
        assert servir.executar(argparse.Namespace(comando="serve")) == 1
    assert f"127.0.0.1:{ocupada}" in capsys.readouterr().err
    assert pid_do_servidor(isolado) is None  # a trava foi solta
    texto = (isolado / "logs" / "jobot.log").read_text(encoding="utf-8")
    assert "porta ocupada" in texto
