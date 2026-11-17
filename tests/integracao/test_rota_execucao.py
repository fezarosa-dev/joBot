"""Buscar agora, andamento e sair (plano T49; desenho 12.3, 13.2 e 13.12; D55, D58, DP8).

A busca de verdade é trocada por um falso pelo nome importado em `painel/rotas/execucao.py`,
menos no teste do dia local, que roda `executar_busca` inteira sem coletor nenhum (sem rede).
"""

import argparse
import asyncio
import os
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from jobot.agenda import execucao as agenda_execucao
from jobot.agenda.andamento import Marcas
from jobot.agenda.login import INTERVALO_MINIMO
from jobot.banco.andamento import abrir_andamento, marcar_fonte, mudar_etapa, planejar
from jobot.banco.cadastros import gravar_config, ligar_fonte, semear, semear_leitores
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import (
    abrir_execucao,
    fechar_execucao,
    gravar_saude,
    interromper_execucao,
)
from jobot.banco.migrar import migrar
from jobot.cli import servir
from jobot.nucleo.andamento import fracao, pesos_da_execucao, valor_mostrado
from jobot.nucleo.http import ClienteEducado
from jobot.nucleo.leitores import registro
from jobot.nucleo.leitores.base import LeitorComLogin
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
        assert _texto("execucao.etapa.preparando") in unescape(resposta.text)
        assert _esperar(lambda: bool(comecou))
        assert painel.trava.locked()
        # a segunda busca avisa que já roda e não começa outra
        resposta = http.post("/buscar-agora", headers=painel.htmx())
        assert _texto("execucao.ja_roda") in unescape(resposta.text)
        assert "andamento-entrada" not in resposta.text  # a que já rodava já estava na tela
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


ETAPAS = ("coleta", "detalhes", "cotacoes", "encaixe")
OOB = 'hx-swap-oob="innerHTML:#andamento-etapa"'


def _busca_com_andamento(painel: Painel, totais: Mapping[str, int] | None = None) -> int:
    """Busca rodando com o andamento aberto em `preparando` e, com `totais`, já planejada."""
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        abrir_andamento(con, id_, ETAPAS, AGORA)
        if totais is not None:
            planejar(con, id_, totais, AGORA)
    return id_


def _valor(texto: str) -> float | None:
    achado = re.search(r'aria-valuenow="([\d.]+)"', texto)
    return None if achado is None else float(achado.group(1))


def _marca(texto: str) -> str:
    achado = re.search(r'hx-get="/execucao/atual\?visto=([^"]*)"', texto)
    assert achado, "a resposta não pergunta de novo com o que mostra"
    return achado.group(1)


def _linha(texto: str) -> str:
    """O texto da linha da etapa (sem a lista de "Ver detalhes")."""
    achado = re.search(r'<p class="progresso-linha"[^>]*>(.*?)</p>', texto, re.S)
    assert achado, "sem a linha da etapa"
    return unescape(achado.group(1)).strip()


def _avancar(painel: Painel, s: float) -> None:
    asyncio.run(painel.app.state.relogio.dormir(s))


def _esperado(
    etapa: str, feitas: int | None, total: int | None, partida: float, parado: float
) -> float:
    p, fim = fracao(pesos_da_execucao(ETAPAS), etapa, feitas, total)
    return round(100 * valor_mostrado(p, fim, partida, parado, fechada=False), 1)


def test_execucao_sem_andamento_fica_indeterminada(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        assert abrir_execucao(con, "busca", "agenda", AGORA) is not None
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert resposta.status_code == 200
    assert 'role="progressbar"' in resposta.text
    assert "aria-valuenow" not in resposta.text  # indeterminada
    assert _linha(resposta.text) == _texto("execucao.etapa.preparando")


def test_com_total_mostra_a_curva(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 40})
    with closing(abrir(painel.banco)) as con:
        mudar_etapa(con, id_, "coleta", 12, 40, 0.0, AGORA)
    with painel.cliente() as http:
        texto = http.get("/execucao/atual", headers=HTMX).text
    esperado = _esperado("coleta", 12, 40, 0.0, 0.0)
    assert esperado > 0
    assert _valor(texto) == esperado
    # a largura vai em data-valor e o app.js a aplica: o CSP (style-src 'self') barra o style
    preenchimento = 'id="andamento-preenchimento" class="progresso-preenchimento"'
    assert f'{preenchimento} data-valor="{esperado}"' in texto
    assert "style=" not in texto
    contagem = _texto("execucao.etapa.coleta", feitas=12, total=40)
    assert contagem == "12 de 40 consultas"
    assert f'aria-valuetext="{contagem}"' in unescape(texto)
    assert contagem in _linha(texto)


def test_total_um_no_singular(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 1})
    with closing(abrir(painel.banco)) as con:
        mudar_etapa(con, id_, "coleta", 1, 1, 0.0, AGORA)
    with painel.cliente() as http:
        linha = _linha(http.get("/execucao/atual", headers=HTMX).text)
    assert "1 de 1 consulta" in linha
    assert "1 de 1 consultas" not in linha


def test_ate_dois_nomes_e_mais(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    chaves = ["gupy", "workday", "lever", "greenhouse", "ashby"]
    id_ = _busca_com_andamento(painel, dict.fromkeys(chaves, 2))
    with closing(abrir(painel.banco)) as con:
        for chave in chaves:
            marcar_fonte(con, id_, chave, "lendo")
    with painel.cliente() as http:
        pt = _linha(http.get("/execucao/atual", headers=HTMX).text)
        en = _linha(http.get("/execucao/atual", headers=HTMX | {"Accept-Language": "en"}).text)
    # os dois primeiros por nome; o resto contado e por inteiro em "Ver detalhes"
    sites = _texto("execucao.etapa.sites_mais", nomes="Ashby, Greenhouse", n=3)
    assert sites == "Ashby, Greenhouse e mais 3"
    assert _texto("execucao.etapa.lendo_sites", sites=sites) in pt
    assert "Gupy" not in pt
    assert "Ashby, Greenhouse, and 3 more" in en


@pytest.mark.parametrize(
    ("chaves", "sites"),
    [(["gupy"], "Gupy"), (["gupy", "lever"], "Gupy e Lever"), (["gupy", "lever", "ashby"], None)],
)
def test_execucao_atual_mostra_ate_2_nomes_e_conta_o_resto(
    tmp_path: Path, chaves: list[str], sites: str | None
) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, dict.fromkeys(chaves, 2))
    with closing(abrir(painel.banco)) as con:
        for chave in chaves:
            marcar_fonte(con, id_, chave, "lendo")
    with painel.cliente() as http:
        linha = _linha(http.get("/execucao/atual", headers=HTMX).text)
    esperado = sites or _texto("execucao.etapa.sites_mais", nomes="Ashby, Gupy", n=1)
    assert linha.startswith(_texto("execucao.etapa.lendo_sites", sites=esperado) + " · ")


def test_so_espera_mostra_contagem(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 4, "lever": 4})
    sete = _texto("execucao.etapa.segundos", n=7)
    with painel.cliente() as http:
        with closing(abrir(painel.banco)) as con:
            marcar_fonte(
                con,
                id_,
                "gupy",
                "esperando",
                espera_ate=AGORA + timedelta(seconds=7),
                espera_motivo="limite",
            )
        limite = _linha(http.get("/execucao/atual", headers=HTMX).text)
        with closing(abrir(painel.banco)) as con:
            marcar_fonte(
                con,
                id_,
                "gupy",
                "esperando",
                espera_ate=AGORA + timedelta(seconds=7),
                espera_motivo="erro",
            )
        erro = _linha(http.get("/execucao/atual", headers=HTMX).text)
        with closing(abrir(painel.banco)) as con:
            marcar_fonte(con, id_, "lever", "lendo")
        com_outra = http.get("/execucao/atual", headers=HTMX).text
    assert limite.startswith(_texto("execucao.etapa.espera", site="Gupy", tempo=sete))
    assert limite == "Esperando o Gupy liberar, 7 s · 0 de 8 consultas"
    assert erro.startswith(_texto("execucao.etapa.nova_tentativa", site="Gupy", tempo=sete))
    # com outro site lendo, a espera só aparece em "Ver detalhes", no estado "Esperando"
    assert "Gupy" not in _linha(com_outra)
    assert _texto("execucao.etapa.lendo_sites", sites="Lever") in _linha(com_outra)
    assert _texto("execucao.etapa.esperando", tempo=sete) in unescape(com_outra)


def test_espera_longa_vira_minutos(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 4})
    with closing(abrir(painel.banco)) as con:
        marcar_fonte(
            con,
            id_,
            "gupy",
            "esperando",
            espera_ate=AGORA + timedelta(seconds=600),
            espera_motivo="limite",
        )
    with painel.cliente() as http:
        linha = _linha(http.get("/execucao/atual", headers=HTMX).text)
    assert _texto("execucao.etapa.minutos", n=10) == "10 min"
    assert linha.startswith(_texto("execucao.etapa.espera", site="Gupy", tempo="10 min"))


def test_espera_vencida_mostra_lendo(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 4})
    with closing(abrir(painel.banco)) as con:
        marcar_fonte(
            con,
            id_,
            "gupy",
            "esperando",
            espera_ate=AGORA - timedelta(seconds=1),
            espera_motivo="limite",
        )
    with painel.cliente() as http:
        texto = http.get("/execucao/atual", headers=HTMX).text
    # E8: a espera que já acabou volta a ser leitura, sem contagem negativa
    assert _linha(texto).startswith(_texto("execucao.etapa.lendo_sites", sites="Gupy"))
    assert "Esperando" not in unescape(texto)


def test_duas_paginas_no_mesmo_instante_mesmo_valor(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 40})
    with closing(abrir(painel.banco)) as con:
        mudar_etapa(con, id_, "coleta", 12, 40, 0.1, AGORA)
    _avancar(painel, 9)  # parada há 9 s: o avanço lento conta
    with painel.cliente() as http:
        valores = []
        for pagina in ("/vagas", "/buscas"):
            assert 'hx-get="/execucao/atual?so_rodando=1"' in http.get(pagina).text
            casca = http.get(
                "/execucao/atual?so_rodando=1", headers=HTMX | {"HX-Current-URL": BASE + pagina}
            )
            valores.append(_valor(casca.text))
    assert valores[0] == valores[1] == _esperado("coleta", 12, 40, 0.1, 9)


def test_valor_da_pergunta_nunca_desce(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agenda", AGORA)
        assert id_ is not None
        marcas = Marcas(con, id_, painel.app.state.relogio)
        asyncio.run(marcas.comecar(ETAPAS))
        asyncio.run(marcas.planejado({"gupy": 6}))
        valores: list[float] = []
        visto = ""
        with painel.cliente() as http:
            # perguntas a cada 2 s: consultas com pausas longas no meio e a troca de etapa
            for passo in range(24):
                if passo in (2, 3, 10, 18, 19, 20):
                    asyncio.run(marcas.consulta_pronta("gupy"))
                if passo == 21:
                    asyncio.run(marcas.etapa("detalhes", 0, 4))
                resposta = http.get(f"/execucao/atual?visto={visto}", headers=HTMX)
                if resposta.status_code == 200:
                    valor = _valor(resposta.text)
                    assert valor is not None
                    valores.append(valor)
                    visto = _marca(resposta.text)
                _avancar(painel, 2)
    assert len(valores) > 10
    assert valores == sorted(valores), valores
    assert valores[-1] > valores[0]


def test_regiao_viva_so_com_etapa_nova(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 4})
    with painel.cliente() as http:
        primeira = http.get("/execucao/atual", headers=HTMX).text
        with closing(abrir(painel.banco)) as con:
            marcar_fonte(con, id_, "gupy", "lendo", feitas=1)
            mudar_etapa(con, id_, "coleta", 1, 4, 0.0, AGORA)
        mesma = http.get(f"/execucao/atual?visto={_marca(primeira)}", headers=HTMX)
        with closing(abrir(painel.banco)) as con:
            mudar_etapa(con, id_, "detalhes", 0, 3, 0.8, AGORA)
        nova = http.get(f"/execucao/atual?visto={_marca(mesma.text)}", headers=HTMX)
    assert mesma.status_code == 200
    assert OOB not in mesma.text  # mesma etapa: o leitor de tela não ouve de novo
    assert nova.status_code == 200
    achado = re.search(rf"<span {OOB}>\s*<span>([^<]*)</span>\s*</span>", nova.text)
    assert achado, "sem o elemento OOB com o texto num filho"
    assert unescape(achado.group(1)) == _texto("execucao.etapa.detalhes")
    # a primeira carga também dá nome à etapa
    assert OOB in primeira


def test_204_quando_nada_muda(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 40})
    with closing(abrir(painel.banco)) as con:
        mudar_etapa(con, id_, "coleta", 12, 40, 0.0, AGORA)
    with painel.cliente() as http:
        primeira = http.get("/execucao/atual", headers=HTMX)
        marca = _marca(primeira.text)
        igual = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
        _avancar(painel, 10)  # nada mudou no banco, mas o avanço lento andou a barra
        andou = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
    assert igual.status_code == 204
    assert igual.text == ""
    assert andou.status_code == 200
    assert _valor(andou.text) > _valor(primeira.text)  # type: ignore[operator]


def test_entrada_so_na_resposta_do_clique(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    painel = Painel(tmp_path)
    liberar = threading.Event()

    async def lenta(*args: Any, **kw: Any) -> int:
        while not liberar.is_set():
            await asyncio.sleep(0.01)
        return 1

    monkeypatch.setattr(rota, "executar_busca", lenta)
    with painel.cliente() as http:
        clique = http.post("/buscar-agora", headers=painel.htmx())
        pergunta = http.get("/execucao/atual", headers=HTMX)
        liberar.set()
        assert _esperar(lambda: not painel.trava.locked())
    assert re.search(r'<div class="andamento-entrada"[ >]', clique.text)
    # a entrada pergunta uma vez antes do limiar de 1 s: busca curta mostra só o fim
    assert 'hx-trigger="load delay:800ms"' in clique.text
    assert POLL in clique.text
    assert "andamento-entrada" not in pergunta.text
    assert POLL in pergunta.text
    # htmx 2 herda hx-target: sem alvo próprio, o filho que pergunta herdaria o "find .andamento"
    # do envoltório, procuraria entre os próprios filhos e o pedido nem sairia (htmx:targetError)
    filho = re.search(r'<div class="andamento"[ >][^>]*>', clique.text)
    assert filho and 'hx-target="this"' in filho.group(0), filho


def test_fim_diz_pronto(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agora", AGORA)
        assert id_ is not None
        fechar_execucao(con, id_, AGORA + timedelta(minutes=5))
        inserir_vaga(con, primeira_vista_em=(AGORA + timedelta(minutes=1)).isoformat())
    with painel.cliente() as http:
        pt = http.get("/execucao/atual", headers=HTMX).text
        en = http.get("/execucao/atual", headers=HTMX | {"Accept-Language": "en"}).text
    assert "Pronto. Vagas novas: 1." in unescape(pt)
    assert "Done. New jobs: 1." in unescape(en)
    assert _valor(pt) == 100.0  # a barra chega ao fim quando a execução fecha
    assert OOB in pt  # o fim é anunciado
    with closing(abrir(painel.banco)) as con:
        id_ = abrir_execucao(con, "busca", "agora", AGORA + timedelta(hours=1))
        assert id_ is not None
        interromper_execucao(con, id_, AGORA + timedelta(hours=1, minutes=2), parada="erro")
    with painel.cliente() as http:
        parada = unescape(http.get("/execucao/atual", headers=HTMX).text)
    assert _texto("execucao.parada.erro") in parada  # os motivos de parada de hoje
    assert "Pronto" not in parada
    assert "aria-valuenow" not in parada


def test_execucao_atual_mostra_o_andamento_e_pergunta_a_cada_2s(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"remotive": 1, "jobicy": 1})
    with closing(abrir(painel.banco)) as con:
        mudar_etapa(con, id_, "coleta", 2, 2, 0.0, AGORA)
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert resposta.status_code == 200
    assert POLL in resposta.text
    # a próxima pergunta diz o que já mostra: sem mudança, nada é trocado
    assert 'hx-get="/execucao/atual?visto=coleta.' in resposta.text
    assert _texto("execucao.etapa.coleta", feitas=2, total=2) in _linha(resposta.text)


def test_execucao_atual_lista_as_fontes_que_ainda_rodam(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 1, "workday": 1})
    with closing(abrir(painel.banco)) as con:
        marcar_fonte(con, id_, "gupy", "pronto", feitas=1)
        marcar_fonte(con, id_, "workday", "lendo")
    with painel.cliente() as http:
        pt = _linha(http.get("/execucao/atual", headers=HTMX).text)
        en = _linha(http.get("/execucao/atual", headers=HTMX | {"Accept-Language": "en"}).text)
    assert pt.startswith(_texto("execucao.etapa.lendo_sites", sites="Workday") + " · ")
    assert "Gupy" not in pt
    assert en.startswith(t("en", "execucao.etapa.lendo_sites", sites="Workday"))


def test_execucao_atual_marca_muda_quando_a_fonte_pendente_termina(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 1, "workday": 1})
    with closing(abrir(painel.banco)) as con:
        marcar_fonte(con, id_, "workday", "lendo")
    with painel.cliente() as http:
        primeira = http.get("/execucao/atual", headers=HTMX)
        marca = _marca(primeira.text)
        igual = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
        with closing(abrir(painel.banco)) as con:
            marcar_fonte(con, id_, "workday", "pronto", feitas=1)
        mudou = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
    assert igual.status_code == 204
    assert mudou.status_code == 200
    assert "Workday" not in _linha(mudou.text)


def test_detalhes_mostram_estado_icone_contagem_e_motivo(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 3, "lever": 2, "ashby": 1, "workday": 1})
    with closing(abrir(painel.banco)) as con:
        marcar_fonte(con, id_, "gupy", "pronto", feitas=3)
        marcar_fonte(con, id_, "lever", "lendo", feitas=1)
        marcar_fonte(con, id_, "ashby", "falhou")
        gravar_saude(con, id_, "ashby", "", "falhou", motivo="saude.bloqueio")
    with painel.cliente() as http:
        texto = unescape(http.get("/execucao/atual", headers=HTMX).text)
    assert 'popovertarget="andamento-detalhes"' in texto
    assert f'aria-label="{_texto("execucao.etapa.ver_detalhes_andamento")}"' in texto
    detalhes = texto.split('id="andamento-detalhes"')[1]
    # lendo primeiro, depois na fila, falhou e pronto
    ordem = [detalhes.index(n) for n in ("Lever", "Workday", "Ashby", "Gupy")]
    assert ordem == sorted(ordem)
    assert 'data-icone="book-open"' in detalhes and 'data-icone="circle-x"' in detalhes
    assert _texto("execucao.etapa.falhou") in detalhes
    assert _texto("saude.bloqueio") in detalhes
    assert _texto("execucao.etapa.contagem", feitas=1, total=2) in detalhes


def test_execucao_atual_diz_que_completa_detalhes(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 2})
    with closing(abrir(painel.banco)) as con:
        mudar_etapa(con, id_, "coleta", 2, 2, 0.0, AGORA)
    with painel.cliente() as http:
        coleta = http.get("/execucao/atual", headers=HTMX)
        with closing(abrir(painel.banco)) as con:
            mudar_etapa(con, id_, "detalhes", 3, 10, 0.75, AGORA)
        pt = http.get(f"/execucao/atual?visto={_marca(coleta.text)}", headers=HTMX)
        en = http.get("/execucao/atual", headers=HTMX | {"Accept-Language": "en"})
        igual = http.get(f"/execucao/atual?visto={_marca(pt.text)}", headers=HTMX)
    assert _texto("execucao.etapa.detalhes") not in _linha(coleta.text)
    assert pt.status_code == 200
    contagem = _texto("execucao.etapa.contagem", feitas=3, total=10)
    assert _linha(pt.text) == f"{_texto('execucao.etapa.detalhes')} · {contagem}"
    assert _linha(en.text) == "Completing job details · 3 of 10"
    # o leitor de tela ouve a contagem, não só a porcentagem (desenho 5.9)
    assert f'aria-valuetext="{contagem}"' in unescape(pt.text)
    assert 'aria-valuetext="3 of 10"' in unescape(en.text)
    assert igual.status_code == 204


@pytest.mark.parametrize(
    ("etapa", "chave"),
    [("regras", "regras"), ("cotacoes", "cotacoes"), ("encaixe", "encaixe")],
)
def test_etapas_sem_contagem_dizem_o_passo(tmp_path: Path, etapa: str, chave: str) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 2})
    with closing(abrir(painel.banco)) as con:
        mudar_etapa(con, id_, etapa, None, None, 0.9, AGORA)
    with painel.cliente() as http:
        texto = http.get("/execucao/atual", headers=HTMX).text
    assert _linha(texto) == _texto(f"execucao.etapa.{chave}")
    assert _valor(texto) is not None  # com total planejado, a barra nunca volta a indeterminada


def test_execucao_atual_sem_fonte_lendo_nao_lista_nomes(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 1, "lever": 1})
    with closing(abrir(painel.banco)) as con:
        marcar_fonte(con, id_, "gupy", "pronto", feitas=1)
        mudar_etapa(con, id_, "coleta", 1, 2, 0.0, AGORA)
    with painel.cliente() as http:
        linha = _linha(http.get("/execucao/atual", headers=HTMX).text)
    assert linha == f"{_texto('execucao.etapa.lendo_fontes')} · 1 de 2 consultas"


def test_execucao_atual_sem_mudanca_nao_troca_a_regiao(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    id_ = _busca_com_andamento(painel, {"gupy": 4})
    with painel.cliente() as http:
        marca = _marca(http.get("/execucao/atual", headers=HTMX).text)
        igual = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
        with closing(abrir(painel.banco)) as con:
            mudar_etapa(con, id_, "coleta", 2, 4, 0.0, AGORA)
        mudou = http.get(f"/execucao/atual?visto={marca}", headers=HTMX)
    # 204: o HTMX não troca nada e segue perguntando
    assert igual.status_code == 204
    assert igual.text == ""
    assert mudou.status_code == 200
    assert _texto("execucao.etapa.coleta", feitas=2, total=4) in _linha(mudou.text)


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
        interromper_execucao(con, id_, AGORA + timedelta(minutes=2), parada="erro")
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
    assert POLL not in resposta.text
    texto = unescape(resposta.text)
    assert _texto("execucao.parada.erro") in texto  # o motivo da parada (T153)
    assert _texto("execucao.parada.novas", n=1) in texto


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
    # a região viva guarda só o nome da etapa, num nó fixo fora do #andamento (E12)
    assert '<span id="andamento-etapa" role="status" aria-live="polite"' in pagina
    regiao = re.search(r'<div id="andamento"[^>]*>', pagina)
    assert regiao and "role=" not in regiao.group(0) and "aria-live" not in regiao.group(0)
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
    # o "Buscar agora" (`relogio_do_painel`, consultas.py) usa o relógio que a agenda recebeu
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
    # o "Tudo pronto" só aparece com a primeira execução concluída: o "/" leva às Vagas, que têm a
    # barra (os passos do assistente não têm, T263)
    with closing(abrir(painel.banco)) as con:
        gravar_config(con, "primeira_execucao_concluida", True)
    chamadas: list[dict[str, Any]] = []
    _espiar_busca(monkeypatch, chamadas)
    asyncio.run(painel.trava.acquire())  # livre: não prende o Lock a outro laço de eventos
    aviso = _texto("execucao.ja_roda")
    with TestClient(painel.app, base_url=BASE) as http:
        # form sem `voltar` nem HX-Request: o redirect passa pelo "/"
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


class _LeituraEspiada:
    """Troca a tarefa `login` do lifespan: conta os motivos e só termina quando liberada."""

    def __init__(self) -> None:
        self.motivos: list[str] = []
        self.liberar = threading.Event()

    async def __call__(self, motivo: str = "agenda") -> None:
        self.motivos.append(motivo)
        for _ in range(500):  # prazo de 5 s: uma rota que espera a leitura falha, não pendura
            if self.liberar.is_set():
                return
            await asyncio.sleep(0.01)


def _ligar_site_com_login(
    painel: Painel, monkeypatch: pytest.MonkeyPatch, *, registrado: bool = True
) -> None:
    leitor = cast(LeitorComLogin, SimpleNamespace(chave="teste_logado"))
    if registrado:
        monkeypatch.setattr(registro, "LEITORES", (leitor,))
    with closing(abrir(painel.banco)) as con:
        semear_leitores(con, [leitor])
        ligar_fonte(con, "teste_logado", True)


def _leitura_login(painel: Painel, ha: timedelta) -> None:
    with closing(abrir(painel.banco)) as con:
        execucao = abrir_execucao(con, "login", "agenda", AGORA - ha)
        assert execucao is not None
        fechar_execucao(con, execucao, AGORA - ha + timedelta(minutes=5))


@pytest.mark.parametrize(
    "caso",
    ["sem_tarefa", "sem_site_ligado", "fonte_sem_leitor", "ultima_ha_3h", "trava_presa", "dispara"],
)
def test_buscar_agora(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caso: str) -> None:
    painel = Painel(tmp_path)
    _espiar_busca(monkeypatch, [])  # a busca sem login segue o caminho de sempre, sem rede
    espiao = _LeituraEspiada()
    if caso != "sem_tarefa":
        painel.app.state.tarefa_login = espiao
    if caso != "sem_site_ligado":
        # fonte com login ligada de um banco mais novo, sem leitor registrado: não sobe o navegador
        _ligar_site_com_login(painel, monkeypatch, registrado=caso != "fonte_sem_leitor")
    # a última leitura há 3 h ainda segura; há exatamente o intervalo mínimo (4 h), já pode
    _leitura_login(painel, timedelta(hours=3) if caso == "ultima_ha_3h" else INTERVALO_MINIMO)
    trava: asyncio.Lock = painel.app.state.travas["login"]
    if caso == "trava_presa":
        asyncio.run(trava.acquire())  # livre: não prende o Lock a outro laço de eventos
    with painel.cliente() as http:
        resposta = http.post("/buscar-agora", headers=painel.htmx())
        assert resposta.status_code == 200
        if caso != "dispara":
            time.sleep(0.1)
            assert espiao.motivos == []
            assert trava.locked() is (caso == "trava_presa")
            return
        # a resposta já voltou e o espião segue preso: a rota não espera a leitura
        assert _esperar(lambda: espiao.motivos == ["agora"]), "a rota não disparou a leitura"
        assert trava.locked()
        assert painel.app.state.tarefas  # guardada para o Sair e o lifespan cancelarem
        espiao.liberar.set()
        assert _esperar(lambda: not trava.locked()), "a trava login não foi solta no fim"


def test_buscar_agora_duas_vezes_dispara_uma_leitura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path)
    _espiar_busca(monkeypatch, [])
    espiao = _LeituraEspiada()
    painel.app.state.tarefa_login = espiao
    _ligar_site_com_login(painel, monkeypatch)
    with painel.cliente() as http:
        assert http.post("/buscar-agora", headers=painel.htmx()).status_code == 200
        assert http.post("/buscar-agora", headers=painel.htmx()).status_code == 200
        assert _esperar(lambda: bool(espiao.motivos))
        time.sleep(0.1)
        assert espiao.motivos == ["agora"]  # o clique duplo dispara uma leitura só (RF4)
        espiao.liberar.set()
        assert _esperar(lambda: not painel.app.state.travas["login"].locked())


def test_andamento_nao_mostra_a_leitura_com_login(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    with closing(abrir(painel.banco)) as con:
        assert abrir_execucao(con, "login", "agenda", AGORA) is not None
    asyncio.run(painel.app.state.travas["login"].acquire())  # a leitura com login segura a sua
    with painel.cliente() as http:
        resposta = http.get("/execucao/atual", headers=HTMX)
        assert resposta.status_code == 200
        assert POLL not in resposta.text  # a leitura com login não tem andamento aqui
        # controle: com uma busca rodando junto, o andamento aparece
        with closing(abrir(painel.banco)) as con:
            assert abrir_execucao(con, "busca", "agenda", AGORA - timedelta(minutes=1))
        resposta = http.get("/execucao/atual", headers=HTMX)
        assert POLL in resposta.text
