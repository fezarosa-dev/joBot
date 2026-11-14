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
    comecar_fonte,
    fechar_execucao,
    gravar_saude,
    interromper_execucao,
    terminar_fonte,
)
from jobot.banco.migrar import migrar
from jobot.cli import servir
from jobot.nucleo.http import ClienteEducado
from jobot.painel.app import criar_app
from jobot.painel.i18n import t
from jobot.painel.rotas import execucao as rota

pytestmark = pytest.mark.usefixtures("laco_versao_parado")

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
    assert 'hx-get="/execucao/atual?visto=2%3A"' in resposta.text
    assert _texto("execucao.prontas", n=2) in unescape(resposta.text)


def _rodando_a_e_b(painel: Painel) -> int:
    """Busca rodando: `gupy` começou e terminou, `workday` começou e não terminou."""
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        comecar_fonte(con, id_, "gupy", AGORA)
        comecar_fonte(con, id_, "workday", AGORA)
        terminar_fonte(con, id_, "gupy", AGORA)
    return id_


def test_execucao_atual_lista_as_fontes_que_ainda_rodam(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    _rodando_a_e_b(painel)
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    texto = unescape(resposta.text)
    assert _texto("execucao.ainda_rodando", fontes="Workday") in texto
    assert "Gupy" not in texto
    with painel.cliente() as http:
        en = http.get("/execucao/atual", headers=HTMX | {"Accept-Language": "en"})
    assert t("en", "execucao.ainda_rodando", fontes="Workday") in unescape(en.text)


def test_execucao_atual_marca_muda_quando_a_fonte_pendente_termina(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _rodando_a_e_b(painel)
    with painel.cliente() as http:
        primeira = http.get("/execucao/atual", headers=HTMX)
        marca = primeira.text.split('hx-get="/execucao/atual?visto=')[1].split('"')[0]
        igual = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
        with closing(abrir(painel.banco)) as con:
            terminar_fonte(con, id_, "workday", AGORA)
        mudou = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
    assert igual.status_code == 204
    assert mudou.status_code == 200
    assert "Workday" not in unescape(mudou.text)


def _fontes_ligadas(painel: Painel) -> list[str]:
    with closing(abrir(painel.banco)) as con:
        return [
            c for (c,) in con.execute("SELECT chave FROM fonte WHERE ligada = 1 ORDER BY rowid")
        ]


def test_execucao_atual_diz_que_completa_detalhes_quando_toda_fonte_terminou(
    tmp_path: Path,
) -> None:
    painel = Painel(tmp_path)
    ligadas = _fontes_ligadas(painel)
    assert len(ligadas) > 1
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        for fonte in ligadas:
            comecar_fonte(con, id_, fonte, AGORA)
            terminar_fonte(con, id_, fonte, AGORA)
    with painel.cliente() as http:
        pt = http.get("/execucao/atual", headers=HTMX)
        en = http.get("/execucao/atual", headers=HTMX | {"Accept-Language": "en"})
        marca = pt.text.split('hx-get="/execucao/atual?visto=')[1].split('"')[0]
        igual = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
    assert _texto("execucao.detalhes") in unescape(pt.text)
    assert t("en", "execucao.detalhes") in unescape(en.text)
    assert igual.status_code == 204


def test_execucao_atual_marca_muda_quando_a_coleta_acaba(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    ligadas = _fontes_ligadas(painel)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        for fonte in ligadas:
            comecar_fonte(con, id_, fonte, AGORA)
            terminar_fonte(con, id_, fonte, AGORA)
        con.execute("UPDATE execucao_fonte SET terminou_em = NULL WHERE fonte = ?", (ligadas[0],))
        con.commit()
    with painel.cliente() as http:
        primeira = http.get("/execucao/atual", headers=HTMX)
        marca = primeira.text.split('hx-get="/execucao/atual?visto=')[1].split('"')[0]
        with closing(abrir(painel.banco)) as con:
            terminar_fonte(con, id_, ligadas[0], AGORA)
        mudou = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
    assert _texto("execucao.detalhes") not in unescape(primeira.text)
    assert mudou.status_code == 200
    assert _texto("execucao.detalhes") in unescape(mudou.text)


def test_execucao_atual_nao_diz_detalhes_sem_fonte_ou_com_fonte_por_comecar(
    tmp_path: Path,
) -> None:
    painel = Painel(tmp_path)
    ligadas = _fontes_ligadas(painel)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
    with painel.cliente() as http:  # recém-aberta: lista de fontes vazia, a coleta nem começou
        vazia = http.get("/execucao/atual", headers=HTMX)
    with closing(abrir(painel.banco)) as con:  # a fila do semáforo: uma terminou, as outras não
        comecar_fonte(con, id_, ligadas[0], AGORA)
        terminar_fonte(con, id_, ligadas[0], AGORA)
    with painel.cliente() as http:
        fila = http.get("/execucao/atual", headers=HTMX)
    assert _texto("execucao.detalhes") not in unescape(vazia.text)
    assert _texto("execucao.detalhes") not in unescape(fila.text)


@pytest.mark.parametrize(
    ("n", "fontes"),
    [
        (5, "Gupy, Workday, Lever, Greenhouse, Ashby"),
        (6, "Gupy, Workday, Lever, Greenhouse, Ashby +1"),
        (7, "Gupy, Workday, Lever, Greenhouse, Ashby +2"),
    ],
)
def test_execucao_atual_mostra_ate_5_nomes_e_conta_o_resto(
    tmp_path: Path, n: int, fontes: str
) -> None:
    painel = Painel(tmp_path)
    chaves = ["gupy", "workday", "lever", "greenhouse", "ashby", "remotive", "jobicy"]
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        for k, chave in enumerate(chaves[:n]):
            comecar_fonte(con, id_, chave, AGORA + timedelta(seconds=k))
    with painel.cliente() as http:
        texto = unescape(http.get("/execucao/atual", headers=HTMX).text)
    assert f"<p>{_texto('execucao.ainda_rodando', fontes=fontes)}</p>" in texto
    assert ("Remotive" in texto) is False and ("Jobicy" in texto) is False


def test_execucao_atual_sem_fonte_pendente_nao_mostra_a_lista(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        comecar_fonte(con, id_, "gupy", AGORA)
        terminar_fonte(con, id_, "gupy", AGORA)
    with painel.cliente() as http:
        texto = unescape(http.get("/execucao/atual", headers=HTMX).text)
    assert "ainda rodando" not in texto


def test_execucao_atual_sem_mudanca_nao_troca_a_regiao(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        gravar_saude(con, id_, "remotive", "", "ok")
        gravar_saude(con, id_, "jobicy", "", "ok")
    with painel.cliente() as http:
        igual = http.get("/execucao/atual?visto=2%3A", headers=HTMX)
        mudou = http.get("/execucao/atual?visto=1%3A", headers=HTMX)
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


def _montar_parado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relogio: Any) -> FastAPI:
    """App do `montar` com a agenda e a versão paradas num evento até o lifespan cancelar."""
    dados = tmp_path / "dados"
    dados.mkdir()

    async def parado(*args: Any, **kw: Any) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "laco", parado)
    monkeypatch.setattr(servir, "laco_versao", parado)
    app, _ = servir.montar(dados, PORTA, relogio=relogio)
    return app


def test_montar_poe_o_relogio_da_agenda_em_app_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relogio = RelogioFalso(AGORA)
    app = _montar_parado(tmp_path, monkeypatch, relogio)
    # o "Buscar agora" (`relogio_do_painel` de vagas.py) usa o mesmo relógio que a agenda recebeu
    assert getattr(app.state, "relogio", None) is relogio


def test_lifespan_cancela_a_busca_do_buscar_agora_antes_de_fechar_o_cliente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comecou: list[bool] = []
    cancelada: list[bool] = []
    ao_fechar: list[list[bool]] = []

    async def presa(*args: Any, **kw: Any) -> int:
        comecou.append(True)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelada.append(True)
            raise
        return 1

    fechar_original = ClienteEducado.fechar

    async def fechar_espiado(self: Any) -> None:
        ao_fechar.append(list(cancelada))  # o que já tinha sido cancelado nesse instante
        await fechar_original(self)

    monkeypatch.setattr(rota, "executar_busca", presa)
    monkeypatch.setattr(ClienteEducado, "fechar", fechar_espiado)
    app = _montar_parado(tmp_path, monkeypatch, RelogioFalso(AGORA))
    token = app.state.csrf
    # Ctrl+C e SIGTERM chegam como o fim do lifespan: a saída do TestClient roda o `finally`
    with TestClient(app, base_url=BASE) as http:
        resposta = http.post("/buscar-agora", headers=HTMX | {"X-CSRF-Token": token})
        assert resposta.status_code == 200
        assert _esperar(lambda: bool(comecou))
    assert ao_fechar == [[True]]
    assert not app.state.travas["busca"].locked()


def test_sair_marca_saindo_e_buscar_agora_nao_cria_tarefa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path)
    chamadas: list[dict[str, Any]] = []
    _espiar_busca(monkeypatch, chamadas)
    painel.app.state.servidor = SimpleNamespace(should_exit=False)
    with painel.cliente() as http:
        assert http.post("/sair", data={"csrf_token": painel.token}).status_code == 200
        resposta = http.post("/buscar-agora", headers=painel.htmx())
        time.sleep(0.05)
    assert resposta.status_code == 200
    assert _texto("execucao.saindo") in unescape(resposta.text)
    assert POLL not in resposta.text
    assert chamadas == []
    assert not painel.trava.locked()
    assert not getattr(painel.app.state, "tarefas", set())


def test_buscar_agora_sem_htmx_com_busca_rodando_avisa_na_pagina_do_redirect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path)
    chamadas: list[dict[str, Any]] = []
    _espiar_busca(monkeypatch, chamadas)
    asyncio.run(painel.trava.acquire())  # livre: não prende o Lock a outro laço de eventos
    aviso = _texto("execucao.ja_roda")
    with TestClient(painel.app, base_url=BASE) as http:
        # o form do pronto.html (primeira execução) não manda `voltar` nem HX-Request
        resposta = http.post("/buscar-agora", data={"csrf_token": painel.token})
        assert resposta.status_code == 200
        assert resposta.history and resposta.history[0].status_code == 303
        assert aviso in unescape(resposta.text)
        # a carga da casca segue mostrando o andamento com o aviso, e o aviso não se repete
        assert 'hx-get="/execucao/atual?so_rodando=1&amp;ja_roda=1"' in resposta.text
        carga = http.get("/execucao/atual?so_rodando=1&ja_roda=1", headers=HTMX)
        assert aviso in unescape(carga.text)
        assert POLL in carga.text
        depois = http.get("/fontes")
        assert aviso not in unescape(depois.text)
    painel.trava.release()
    assert chamadas == []
