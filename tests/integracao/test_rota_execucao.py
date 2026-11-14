"""Buscar agora, andamento e sair (plano T49; desenho 12.3, 13.2 e 13.12; D55, D58, DP8).

A busca de verdade é trocada por um falso pelo nome importado em `painel/rotas/execucao.py`,
menos no teste do dia local, que roda `executar_busca` inteira sem coletor nenhum (sem rede).
"""

import argparse
import asyncio
import os
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from jobot.agenda import execucao as agenda_execucao
from jobot.banco.cadastros import semear
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import (
    abrir_execucao,
    fechar_execucao,
    gravar_saude,
    interromper_execucao,
)
from jobot.banco.migrar import migrar
from jobot.cli import servir
from jobot.painel.app import criar_app
from jobot.painel.i18n import t
from jobot.painel.rotas import execucao as rota

PORTA = 47621
BASE = f"http://127.0.0.1:{PORTA}"
AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
# 01:00 em UTC é 22:00 do dia 13 em São Paulo: o dia local (DP8) é 13, o dia UTC é 14
MADRUGADA_UTC = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)
HTMX = {"HX-Request": "true"}
POLL = 'hx-trigger="every 2s"'


class _RelogioRapido(RelogioFalso):
    """`dormir` avança a hora falsa e solta o laço por 10 ms (o batimento não gira em falso)."""

    async def dormir(self, s: float) -> None:
        await super().dormir(s)
        await asyncio.sleep(0.01)


@pytest.fixture
def fuso_sp() -> Iterator[None]:
    antes = os.environ.get("TZ")
    os.environ["TZ"] = "America/Sao_Paulo"
    time.tzset()
    yield
    if antes is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = antes
    time.tzset()


def _esperar(condicao: Callable[[], bool], s: float = 5.0) -> bool:
    fim = time.monotonic() + s
    while not condicao():
        if time.monotonic() >= fim:
            return False
        time.sleep(0.01)
    return True


def _texto(chave: str, **params: object) -> str:
    return t("pt", chave, **params)


class Painel:
    """App do painel com o que o lifespan do `serve` põe em `app.state` (travas e cliente)."""

    def __init__(self, tmp_path: Path, relogio: RelogioFalso | None = None) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            semear(con)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = relogio or RelogioFalso(AGORA)
        self.app.state.travas = {tipo: asyncio.Lock() for tipo in servir.TIPOS}
        self.app.state.cliente = object()
        self.token: str = self.app.state.csrf

    @property
    def trava(self) -> asyncio.Lock:
        trava: asyncio.Lock = self.app.state.travas["busca"]
        return trava

    def cliente(self) -> TestClient:
        return TestClient(self.app, base_url=BASE, follow_redirects=False)

    def htmx(self) -> dict[str, str]:
        return HTMX | {"X-CSRF-Token": self.token}


def _espiar_busca(
    monkeypatch: pytest.MonkeyPatch, chamadas: list[dict[str, Any]], erro: bool = False
) -> None:
    async def falsa(con: Any, cliente: Any, relogio: Any, motivo: str, **kw: Any) -> int:
        chamadas.append({"cliente": cliente, "relogio": relogio, "motivo": motivo, "kw": kw})
        if erro:
            raise RuntimeError("quebrou no meio")
        return 1

    monkeypatch.setattr(rota, "executar_busca", falsa)


def test_buscar_agora_usa_a_mesma_trava_do_agendador(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dados = tmp_path / "dados"
    dados.mkdir()
    recebidas: list[Mapping[str, asyncio.Lock]] = []

    async def laco_falso(*args: Any, travas: Mapping[str, asyncio.Lock], **kw: Any) -> None:
        recebidas.append(travas)
        await asyncio.Event().wait()  # fica de pé até o lifespan cancelar

    chamadas: list[dict[str, Any]] = []
    monkeypatch.setattr(servir, "laco", laco_falso)
    _espiar_busca(monkeypatch, chamadas)
    app, _ = servir.montar(dados, PORTA, relogio=RelogioFalso(AGORA))
    token = app.state.csrf
    with TestClient(app, base_url=BASE) as http:
        assert _esperar(lambda: bool(recebidas)), "o laço da agenda não subiu"
        trava = recebidas[0]["busca"]  # a trava que o laço da agenda recebeu
        asyncio.run(trava.acquire())  # livre: não prende o Lock a outro laço de eventos
        try:
            resposta = http.post("/buscar-agora", headers=HTMX | {"X-CSRF-Token": token})
            assert resposta.status_code == 200
            assert _texto("execucao.ja_roda") in unescape(resposta.text)
            assert POLL in resposta.text  # mostra o andamento da que já roda
            time.sleep(0.1)
            assert chamadas == []  # não dispara outra
        finally:
            trava.release()
        resposta = http.post("/buscar-agora", headers=HTMX | {"X-CSRF-Token": token})
        assert resposta.status_code == 200
        assert _texto("execucao.ja_roda") not in unescape(resposta.text)
        assert _esperar(lambda: bool(chamadas)), "a rota não disparou a busca"
        assert _esperar(lambda: not trava.locked()), "a trava não foi solta no fim"
        assert chamadas[0]["cliente"] is app.state.cliente  # o cliente do lifespan (D58)
        assert chamadas[0]["motivo"] == "agora"


def test_buscar_agora_nao_bloqueia_o_pedido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path)
    liberar = threading.Event()
    comecou: list[bool] = []

    async def lenta(*args: Any, **kw: Any) -> int:
        comecou.append(True)
        while not liberar.is_set():
            await asyncio.sleep(0.01)
        return 1

    monkeypatch.setattr(rota, "executar_busca", lenta)
    with painel.cliente() as http:
        resposta = http.post("/buscar-agora", headers=painel.htmx())
        assert resposta.status_code == 200  # voltou com a busca ainda rodando
        assert POLL in resposta.text
        assert _texto("execucao.rodando") in unescape(resposta.text)
        assert _esperar(lambda: bool(comecou))
        assert painel.trava.locked()
        # a segunda busca avisa que já roda e não começa outra
        resposta = http.post("/buscar-agora", headers=painel.htmx())
        assert _texto("execucao.ja_roda") in unescape(resposta.text)
        assert len(comecou) == 1
        liberar.set()
        assert _esperar(lambda: not painel.trava.locked())


@pytest.mark.usefixtures("fuso_sp")
def test_buscar_agora_passa_o_dia_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    painel = Painel(tmp_path, _RelogioRapido(MADRUGADA_UTC))
    dias: list[date] = []

    def espiar(nome: str) -> None:
        original = getattr(agenda_execucao, nome)

        def espia(*args: Any, hoje: date, **kw: Any) -> Any:
            dias.append(hoje)
            return original(*args, hoje=hoje, **kw)

        monkeypatch.setattr(agenda_execucao, nome, espia)

    async def sem_cotacoes(*args: Any) -> None:
        return None

    monkeypatch.setattr(agenda_execucao, "descobrir", lambda: {})  # nenhum coletor: sem rede
    monkeypatch.setattr(agenda_execucao, "_cotacoes", sem_cotacoes)
    espiar("aplicar_cotacoes")
    espiar("recalcular_encaixe")
    with painel.cliente() as http:
        assert http.post("/buscar-agora", headers=painel.htmx()).status_code == 200
        assert _esperar(lambda: len(dias) >= 2 and not painel.trava.locked())
    assert dias == [date(2026, 11, 13), date(2026, 11, 13)]  # o dia local, não o 14 do UTC
    with closing(abrir(painel.banco)) as con:
        execucoes = con.execute("SELECT tipo, motivo, estado FROM execucao").fetchall()
    assert execucoes == [("busca", "agora", "concluida")]


def test_erro_na_busca_solta_a_trava(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    painel = Painel(tmp_path)
    chamadas: list[dict[str, Any]] = []
    _espiar_busca(monkeypatch, chamadas, erro=True)
    with painel.cliente() as http:
        assert http.post("/buscar-agora", headers=painel.htmx()).status_code == 200
        assert _esperar(lambda: bool(chamadas) and not painel.trava.locked())
        # a próxima volta pode buscar de novo
        assert http.post("/buscar-agora", headers=painel.htmx()).status_code == 200
        assert _esperar(lambda: len(chamadas) == 2)


def test_buscar_agora_sem_htmx_volta_para_a_pagina(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path)
    chamadas: list[dict[str, Any]] = []
    _espiar_busca(monkeypatch, chamadas)
    with painel.cliente() as http:
        resposta = http.post(
            "/buscar-agora", data={"csrf_token": painel.token, "voltar": "/fontes?x=1"}
        )
        assert resposta.status_code == 303
        assert resposta.headers["location"] == "/fontes?x=1"
        assert _esperar(lambda: bool(chamadas))
        resposta = http.post(
            "/buscar-agora", data={"csrf_token": painel.token, "voltar": "https://fora.test/"}
        )
        assert resposta.headers["location"] == "/"  # sem open redirect


def test_buscar_agora_sem_csrf_recusa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    painel = Painel(tmp_path)
    chamadas: list[dict[str, Any]] = []
    _espiar_busca(monkeypatch, chamadas)
    with painel.cliente() as http:
        assert http.post("/buscar-agora", headers=HTMX).status_code == 403
        time.sleep(0.05)
    assert chamadas == []


def test_execucao_atual_mostra_o_andamento_e_pergunta_a_cada_2s(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        gravar_saude(con, id_, "remotive", "", "ok")
        gravar_saude(con, id_, "jobicy", "", "ok")
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert resposta.status_code == 200
    assert POLL in resposta.text
    # a próxima pergunta diz o que já mostra: sem mudança, nada é trocado na região viva
    assert 'hx-get="/execucao/atual?visto=2"' in resposta.text
    assert _texto("execucao.prontas", n=2) in unescape(resposta.text)


def test_execucao_atual_sem_mudanca_nao_troca_a_regiao(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        gravar_saude(con, id_, "remotive", "", "ok")
        gravar_saude(con, id_, "jobicy", "", "ok")
    with painel.cliente() as http:
        igual = http.get("/execucao/atual?visto=2", headers=HTMX)
        mudou = http.get("/execucao/atual?visto=1", headers=HTMX)
    # 204: o HTMX não troca nada e segue perguntando (o leitor de tela não repete o anúncio)
    assert igual.status_code == 204
    assert igual.text == ""
    assert mudou.status_code == 200
    assert _texto("execucao.prontas", n=2) in unescape(mudou.text)


def test_execucao_atual_visto_com_a_busca_acabada_mostra_o_fim(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agora", AGORA)
        assert id_ is not None
        fechar_execucao(con, id_, AGORA + timedelta(minutes=5))
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual?visto=0", headers=HTMX)
    assert resposta.status_code == 200
    assert _texto("execucao.terminou", n=0) in unescape(resposta.text)


def test_execucao_atual_so_rodando(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agora", AGORA)
        assert id_ is not None
        fechar_execucao(con, id_, AGORA + timedelta(minutes=5))
    with painel.cliente() as http:
        parada = http.get("/execucao/atual?so_rodando=1", headers=HTMX)
        with closing(abrir(painel.banco)) as con:
            assert abrir_execucao(con, "busca", "agenda", AGORA + timedelta(hours=1)) is not None
        rodando = http.get("/execucao/atual?so_rodando=1", headers=HTMX)
    # a carga da casca não repete o fim de uma busca velha em toda página
    assert parada.status_code == 204
    assert rodando.status_code == 200
    assert POLL in rodando.text


def test_execucao_atual_ignora_descoberta_rodando(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        assert abrir_execucao(con, "descoberta", "agenda", AGORA) is not None
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert resposta.status_code == 200
    assert POLL not in resposta.text  # só a busca tem andamento aqui


def test_fim_mostra_a_contagem_de_novas(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agora", AGORA)
        assert id_ is not None
        fechar_execucao(con, id_, AGORA + timedelta(minutes=5))
        # duas vistas pela primeira vez durante a busca, uma de antes e uma de depois
        inserir_vaga(con, primeira_vista_em=(AGORA + timedelta(minutes=1)).isoformat())
        inserir_vaga(con, primeira_vista_em=(AGORA + timedelta(minutes=5)).isoformat())
        inserir_vaga(con, primeira_vista_em=(AGORA - timedelta(seconds=1)).isoformat())
        inserir_vaga(con, primeira_vista_em=(AGORA + timedelta(minutes=6)).isoformat())
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert resposta.status_code == 200
    assert POLL not in resposta.text  # acabou: o HTMX para de perguntar
    assert _texto("execucao.terminou", n=2) in unescape(resposta.text)


def test_fim_conta_a_ultima_busca_com_fuso_diferente_no_texto(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        velha = abrir_execucao(con, "busca", "agenda", AGORA - timedelta(hours=3))
        assert velha is not None
        fechar_execucao(con, velha, AGORA - timedelta(hours=2))
        id_ = abrir_execucao(con, "busca", "agora", AGORA)
        assert id_ is not None
        fechar_execucao(con, id_, AGORA + timedelta(minutes=5))
        # 09:02 em -03 é 12:02 UTC: dentro da busca, apesar do texto "09:02" ser menor
        inserir_vaga(con, primeira_vista_em="2026-11-13T09:02:00-03:00")
        inserir_vaga(con, primeira_vista_em=(AGORA - timedelta(hours=2, minutes=30)).isoformat())
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert _texto("execucao.terminou", n=1) in unescape(resposta.text)


def test_busca_interrompida_avisa(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agora", AGORA)
        assert id_ is not None
        inserir_vaga(con, primeira_vista_em=(AGORA + timedelta(minutes=1)).isoformat())
        interromper_execucao(con, id_, AGORA + timedelta(minutes=2))
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert POLL not in resposta.text
    assert _texto("execucao.interrompida", n=1) in unescape(resposta.text)


def test_sem_busca_nenhuma_nao_pergunta(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert resposta.status_code == 200
    assert POLL not in resposta.text


def test_carga_da_casca_sem_o_lifespan_nao_quebra(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    del painel.app.state.travas  # app sem o lifespan do serve (testes de outras telas)
    with TestClient(painel.app, base_url=BASE, raise_server_exceptions=False) as http:
        resposta = http.get("/execucao/atual?so_rodando=1", headers=HTMX)
    assert resposta.status_code == 204  # a casca carrega em toda página: sem 500


def test_casca_tem_buscar_agora_sair_e_regiao_aria_live(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with painel.cliente() as http:
        pagina = http.get("/fontes").text
    assert 'id="andamento"' in pagina
    assert 'aria-live="polite"' in pagina
    # a página que chega depois do redirect (form sem HTMX) já mostra a busca que roda
    assert 'hx-get="/execucao/atual?so_rodando=1" hx-trigger="load"' in pagina
    assert 'hx-post="/buscar-agora"' in pagina
    assert 'action="/sair"' in pagina
    assert _texto("execucao.buscar_agora") in unescape(pagina)
    assert _texto("execucao.sair") in unescape(pagina)
    assert "/static/css/execucao.css" in pagina


def test_sair_encerra_o_servidor(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    servidor = SimpleNamespace(should_exit=False)
    painel.app.state.servidor = servidor
    with painel.cliente() as http:
        resposta = http.post("/sair", data={"csrf_token": painel.token})
    assert resposta.status_code == 200
    assert servidor.should_exit is True  # o uvicorn sai limpo e o lifespan cancela a agenda
    assert _texto("execucao.saiu") in unescape(resposta.text)
    # com o servidor parando, a página de despedida não oferece Buscar agora nem Sair
    assert 'action="/sair"' not in resposta.text
    assert 'id="andamento"' not in resposta.text


def test_sair_cancela_a_busca_que_roda_antes_de_encerrar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path)
    comecou: list[bool] = []
    cancelada: list[bool] = []
    ao_sair: list[list[bool]] = []

    async def lenta(*args: Any, **kw: Any) -> int:
        comecou.append(True)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelada.append(True)
            raise
        return 1

    class _Servidor:
        @property
        def should_exit(self) -> bool:
            return bool(ao_sair)

        @should_exit.setter
        def should_exit(self, valor: bool) -> None:
            ao_sair.append(list(cancelada))  # o que já tinha sido cancelado nesse instante

    monkeypatch.setattr(rota, "executar_busca", lenta)
    painel.app.state.servidor = _Servidor()
    with painel.cliente() as http:
        assert http.post("/buscar-agora", headers=painel.htmx()).status_code == 200
        assert _esperar(lambda: bool(comecou))
        resposta = http.post("/sair", data={"csrf_token": painel.token})
    assert resposta.status_code == 200
    # a busca é cancelada e esperada antes do should_exit: o lifespan fecha o cliente depois
    assert ao_sair == [[True]]
    assert not painel.trava.locked()


def test_sair_sem_csrf_nao_encerra(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    servidor = SimpleNamespace(should_exit=False)
    painel.app.state.servidor = servidor
    with painel.cliente() as http:
        assert http.post("/sair", data={"csrf_token": "errado"}).status_code == 403
        assert http.get("/sair").status_code == 405
    assert servidor.should_exit is False


def test_sair_sem_servidor_avisa(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with painel.cliente() as http:
        resposta = http.post("/sair", data={"csrf_token": painel.token})
    assert resposta.status_code == 503


def test_serve_guarda_o_servidor_para_o_sair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dados = tmp_path / "dados"
    dados.mkdir()
    vistos: list[bool] = []

    class _Trava:
        def __init__(self, *args: Any) -> None: ...

        def pegar(self) -> bool:
            return True

        def soltar(self) -> None: ...

    class _Servidor:
        def __init__(self, config: Any) -> None:
            self.config = config
            self.started = False

        def run(self) -> None:  # não escuta nada: só confere o que o `sair` vai achar
            app: FastAPI = self.config.app
            vistos.append(getattr(app.state, "servidor", None) is self)
            self.started = True

    monkeypatch.setattr(servir, "preparar_dados", lambda env: dados)
    monkeypatch.setattr(servir, "porta", lambda env: PORTA)
    monkeypatch.setattr(servir, "Trava", _Trava)
    monkeypatch.setattr(uvicorn, "Server", _Servidor)
    assert servir.executar(argparse.Namespace()) == 0
    assert vistos == [True]
