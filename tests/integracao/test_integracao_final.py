"""Integração final da fase 1 (plano T77; desenho 12.1, 13.7 e 13.8; critérios 6 e 26).

Três conferências que cruzam as camadas: toda fonte tem coletor, interruptor e linha na saúde;
a descoberta e as páginas acompanhadas rodam na agenda do servidor; toda chave da seção 13.7,
desligada, faz a função parar. Banco de verdade numa pasta temporária; nenhuma rede (o cliente
usa `httpx.MockTransport` e DNS falso).
"""

import asyncio
import contextlib
import sqlite3
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.segundo_plano_falso import FalsoSistema
from jobot.agenda.agendador import o_que_roda
from jobot.agenda.descoberta import executar_descoberta
from jobot.agenda.execucao import executar_busca
from jobot.banco.buscas import criar_busca
from jobot.banco.cadastros import (
    PADROES,
    ativar_empresa,
    empresas,
    fontes,
    gravar_config,
    ler_config,
    ligar_fonte,
    remover_empresa,
    semear,
)
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.sugeridas import gravar_sugestoes, sugeridas
from jobot.cli import servir
from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
)
from jobot.nucleo.coletores.descoberta_cc import Sugestao
from jobot.nucleo.coletores.registro import descobrir, limites
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Busca, VagaColetada
from jobot.nucleo.url import canonica, hash_url
from jobot.painel.app import criar_app
from jobot.painel.i18n import carregar
from jobot.painel.seguranca import CAMPO_CSRF

pytestmark = pytest.mark.usefixtures("laco_versao_parado")

PORTA = 47998
BASE = f"http://127.0.0.1:{PORTA}"
AGORA = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)
HOJE = date(2026, 11, 13)  # o dia local (-03) de AGORA
PTAX = Path(__file__).resolve().parents[1] / "fixtures" / "ptax" / "usd_semana.json"
DESCRICAO = (
    "Estamos contratando uma pessoa desenvolvedora Python para trabalhar remoto com a nossa"
    " equipe de produto, cuidando de serviços, testes automatizados e entregas semanais."
)


@pytest.fixture
def dados(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    return pasta


def _banco(dados: Path, *, semeado: bool = True) -> sqlite3.Connection:
    con = abrir(dados / "jobot.db")
    migrar(con, dados / "jobot.db")
    if semeado:
        semear(con)
    return con


def _app(dados: Path) -> TestClient:
    app = criar_app(dados, PORTA)
    app.state.relogio = RelogioFalso(AGORA)
    return TestClient(app, base_url=BASE, follow_redirects=False)


def _esperar(condicao: Callable[[], bool], s: float = 5.0) -> bool:
    fim = time.monotonic() + s
    while not condicao():
        if time.monotonic() >= fim:
            return False
        time.sleep(0.01)
    return True


# ------------------------------------------------------------------ critério 6


def test_toda_fonte_tem_coletor_interruptor_e_saude(dados: Path) -> None:
    # Nenhuma fonte fica de fora: a exceção do critério 6 (fonte sem caminho público ou fora por
    # termos de uso) só valeria com motivo no `duvidas.md`, e hoje não há nenhuma.
    coletores = descobrir()
    catalogo = carregar()
    with closing(_banco(dados)) as con:
        cadastradas = {f.chave: f for f in fontes(con)}
    cliente = _app(dados)
    saude = cliente.get("/fontes").text
    config = cliente.get("/configuracoes/fontes").text

    problemas: list[str] = []
    for chave, fonte in cadastradas.items():
        if chave not in coletores or coletores[chave].chave != chave:
            problemas.append(f"{chave}: sem coletor")
        if fonte.ligada != limites(chave).ligada_padrao:
            problemas.append(f"{chave}: nasce diferente do `ligada_padrao`")
        marca = f'name="fonte" value="{chave}"'
        if marca not in config or ((marca + " checked") in config) != fonte.ligada:
            problemas.append(f"{chave}: sem interruptor em Configurações")
        acao = "desligar" if fonte.ligada else "ligar"
        if f'action="/fontes/{chave}/{acao}"' not in saude:
            problemas.append(f"{chave}: sem interruptor na saúde")
        if f'id="fonte-{chave}"' not in saude:
            problemas.append(f"{chave}: sem linha na saúde")
        for idioma in ("pt", "en"):
            if not catalogo[idioma].get(f"fonte.{chave}"):
                problemas.append(f"{chave}: sem nome em {idioma}")
    assert problemas == []
    assert set(coletores) == set(cadastradas)  # coletor sem fonte no `fontes.json` também falha
    assert len(cadastradas) >= 28


# ------------------------------------------------------------------ agenda do servidor


class _RelogioRapido(RelogioFalso):
    """Cada `dormir` avança a hora falsa e solta o laço de eventos por 10 ms de verdade."""

    async def dormir(self, s: float) -> None:
        await super().dormir(s)
        await asyncio.sleep(0.01)


@pytest.mark.parametrize("desligada", [None, "descoberta_cc_ligada", "paginas_ligadas"])
def test_descoberta_e_paginas_ligadas_na_agenda(
    dados: Path, monkeypatch: pytest.MonkeyPatch, desligada: str | None
) -> None:
    with closing(_banco(dados)) as con:
        if desligada is not None:
            gravar_config(con, desligada, False)
    chamadas: dict[str, list[tuple[sqlite3.Connection, ClienteEducado]]] = {
        "busca": [],
        "descoberta": [],
        "paginas": [],
    }

    def falso(tipo: str) -> Callable[..., Awaitable[None]]:
        async def executar(con: sqlite3.Connection, cliente: ClienteEducado, *_: object) -> None:
            con.execute("SELECT 1")  # a conexão chega aberta
            chamadas[tipo].append((con, cliente))

        return executar

    for tipo, nome in (
        ("busca", "executar_busca"),
        ("descoberta", "executar_descoberta"),
        ("paginas", "executar_paginas"),
    ):
        monkeypatch.setattr(servir, nome, falso(tipo))

    app, _ = servir.montar(dados, PORTA, relogio=_RelogioRapido(AGORA))
    parada = {"descoberta_cc_ligada": "descoberta", "paginas_ligadas": "paginas"}.get(
        desligada or ""
    )
    esperadas = {"busca", "descoberta", "paginas"} - {parada}
    with TestClient(app, base_url=BASE):
        assert _esperar(lambda: all(chamadas[t] for t in esperadas)), chamadas
        time.sleep(0.2)  # o desligado teve várias voltas do laço para (não) rodar
    assert {t for t, vezes in chamadas.items() if vezes} == esperadas
    # um cliente só para os três tipos (o ritmo por host vale entre eles) e uma conexão por tipo
    clientes = {id(c) for vezes in chamadas.values() for _, c in vezes}
    assert clientes == {id(app.state.cliente)}
    conexoes = [vezes[0][0] for vezes in chamadas.values() if vezes]
    assert len({id(c) for c in conexoes}) == len(conexoes)


# ------------------------------------------------------------------ critério 26


class Falso:
    """Coletor falso: devolve `itens` num escopo só e guarda o que o executor lhe pediu."""

    nome = "Falso"
    leva: Literal["A", "B"] = "A"
    hosts: tuple[str, ...] = ()
    credito_obrigatorio = False
    intervalo_min: int | None = None
    max_pedidos: int | None = None
    espera_s = 1.0
    por_escopo: Mapping[str, LimiteEscopo] = {}

    def __init__(self, chave: str, itens: Sequence[Item] = ()) -> None:
        self.chave = chave
        self.itens = tuple(itens)
        self.contextos: list[ContextoColeta] = []
        self.detalhados: list[str] = []

    def escopos(self, ctx: ContextoColeta) -> tuple[str, ...]:
        self.contextos.append(ctx)
        return ("",)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        return ResultadoEscopo(self.itens, "ok", None, 0)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        self.detalhados.append(item.url)
        return _vaga(self.chave, item.url, titulo="Estágio em dados")

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        return {}


def _vaga(fonte: str, url: str, **campos: Any) -> VagaColetada:
    base: dict[str, Any] = {
        "fonte": fonte,
        "escopo": "",
        "url": url,
        "titulo": "Desenvolvedor Python",
        "empresa": "Acme",
        "descricao_formato": "texto",
        "descricao": DESCRICAO,
    }
    return VagaColetada(**(base | campos))


class _Servidor:
    """PTAX falso; qualquer outro host responde 404. Guarda os pedidos."""

    def __init__(self) -> None:
        self.pedidos: list[httpx.Request] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if pedido.url.host == "olinda.bcb.gov.br":
            return httpx.Response(200, text=PTAX.read_text(encoding="utf-8"))
        return httpx.Response(404)

    def ptax(self) -> list[httpx.Request]:
        return [p for p in self.pedidos if p.url.host == "olinda.bcb.gov.br"]


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


class _RelogioParado(RelogioFalso):
    """O batimento da execução dorme para sempre."""

    async def dormir(self, s: float) -> None:
        await asyncio.Event().wait()


async def _dns_publico(host: str) -> list[str]:
    return ["93.184.216.34"]  # o teste nunca consulta DNS: o transporte é falso


def _cliente(servidor: _Servidor) -> ClienteEducado:
    return ClienteEducado(
        httpx.MockTransport(servidor),
        RelogioFalso(AGORA),
        _SemValidadores(),
        "9.9.9",
        resolver=_dns_publico,
    )


async def _buscar(
    con: sqlite3.Connection, *coletores: Falso, servidor: _Servidor | None = None
) -> None:
    cliente = _cliente(servidor or _Servidor())
    try:
        await executar_busca(
            con, cliente, _RelogioParado(AGORA), "agenda", coletores={c.chave: c for c in coletores}
        )
    finally:
        await cliente.fechar()


def _um(con: sqlite3.Connection, sql: str, *params: object) -> Any:
    linha = con.execute(sql, params).fetchone()
    return None if linha is None else linha[0]


def _oculta(con: sqlite3.Connection, busca_id: int, url: str) -> Any:
    return _um(
        con,
        "SELECT e.oculta_motivo FROM encaixe e JOIN vaga v ON v.id = e.vaga_id"
        " WHERE e.busca_id = ? AND v.url_hash = ?",
        busca_id,
        hash_url(canonica(url)),
    )


async def _fonte(dados: Path) -> None:
    with closing(_banco(dados)) as con:
        ligar_fonte(con, "remoteok", False)
        remotive = Falso("remotive", [_vaga("remotive", "https://remotive.exemplo.test/vagas/1")])
        remoteok = Falso("remoteok", [_vaga("remoteok", "https://remoteok.exemplo.test/vagas/1")])
        await _buscar(con, remotive, remoteok)
        assert len(remotive.contextos) == 1  # a ligada coleta (controle)
        assert remoteok.contextos == []  # a desligada nem lista os escopos
        assert _um(con, "SELECT count(*) FROM vaga") == 1
        estados = dict(con.execute("SELECT fonte, estado FROM saude").fetchall())
        assert estados == {"remotive": "ok", "remoteok": "desligada"}


async def _empresa(dados: Path) -> None:
    with closing(_banco(dados)) as con:
        antes = [
            e for e in empresas(con) if e.fonte == "greenhouse"
        ]  # o coletor só vê as da fonte dele
        desligada, removida, ligada = antes[0], antes[1], antes[2]
        ativar_empresa(con, desligada.id or 0, False)
        remover_empresa(con, removida.id or 0, AGORA)
        falso = Falso("greenhouse")
        await _buscar(con, falso)
        buscadas = {e.id for e in falso.contextos[0].empresas}
        assert ligada.id in buscadas  # controle: a ligada é buscada
        assert desligada.id not in buscadas
        assert removida.id not in buscadas
        # a remoção só marca a linha e uma nova carga do `empresas.json` não a traz de volta
        total = _um(con, "SELECT count(*) FROM empresa")
        semear(con)
        assert _um(con, "SELECT count(*) FROM empresa") == total
        assert _um(con, "SELECT removida_em FROM empresa WHERE id = ?", removida.id) is not None
        assert removida.id not in {e.id for e in empresas(con)}


async def _descoberta(dados: Path) -> None:
    sugestao = Sugestao(fonte="greenhouse", identificador="acme", url_exemplo="https://x.test/a")
    with closing(_banco(dados)) as con:
        gravar_sugestoes(con, [sugestao], AGORA)
        gravar_config(con, "descoberta_cc_ligada", False)
        servidor = _Servidor()
        cliente = _cliente(servidor)
        await executar_descoberta(con, cliente, _RelogioParado(AGORA))
        assert servidor.pedidos == []  # nenhum pedido ao Common Crawl
        assert _um(con, "SELECT count(*) FROM execucao WHERE tipo = 'descoberta'") == 0
        assert [s.identificador for s in sugeridas(con)] == ["acme"]  # as já feitas continuam
        gravar_config(con, "descoberta_cc_ligada", True)  # controle: ligada, ela tenta rodar
        with contextlib.suppress(Exception):
            await executar_descoberta(con, cliente, _RelogioParado(AGORA))
        assert servidor.pedidos != []
        assert _um(con, "SELECT count(*) FROM execucao WHERE tipo = 'descoberta'") == 1
        await cliente.fechar()


async def _paginas(dados: Path) -> None:
    with closing(_banco(dados)) as con:
        gravar_config(con, "paginas_ligadas", False)
    estado = servir._EstadoDoBanco(dados / "jobot.db")
    antigo = AGORA - timedelta(hours=1)  # passou a espera de 60 s do início
    assert estado.interruptores()["paginas"] is False
    assert "paginas" not in o_que_roda(AGORA, None, None, None, antigo, estado.interruptores())
    with closing(abrir(dados / "jobot.db")) as con:
        gravar_config(con, "paginas_ligadas", True)
    assert "paginas" in o_que_roda(AGORA, None, None, None, antigo, estado.interruptores())


async def _enriquecimento(dados: Path) -> None:
    mapa = "https://super-estagios.exemplo.test/vagas/m1"
    sem_texto = _vaga("remotive", "https://remotive.exemplo.test/vagas/sem-texto", descricao="")
    with closing(_banco(dados)) as con:
        gravar_config(con, "enriquecimento_ligado", False)
        sitemap = Falso("super_estagios", [UrlListada(mapa, AGORA - timedelta(hours=1))])
        lista = Falso("remotive", [sem_texto])
        await _buscar(con, sitemap, lista)
        assert sitemap.detalhados == [] and lista.detalhados == []  # nenhuma página de detalhe
        assert _um(con, "SELECT count(*) FROM vaga") == 1  # o sitemap não trouxe vaga nova
        gravar_config(con, "enriquecimento_ligado", True)  # controle
        await _buscar(con, sitemap, lista)
        assert sitemap.detalhados == [mapa]
        assert lista.detalhados == [sem_texto.url]
        assert _um(con, "SELECT count(*) FROM vaga") == 2


async def _destaques(dados: Path) -> None:
    with closing(_banco(dados)) as con:
        gravar_config(con, "primeira_execucao_concluida", True)
        cliente = _app(dados)
        assert cliente.get("/").headers["location"] == "/vagas?aba=destaques"  # controle
        assert 'id="aba-destaques"' in cliente.get("/vagas?aba=destaques").text
        gravar_config(con, "destaques_ligados", False)
        assert cliente.get("/").headers["location"] == "/vagas?aba=todas"
        assert 'id="aba-destaques"' not in cliente.get("/vagas?aba=destaques").text


async def _conversao(dados: Path) -> None:
    usd = _vaga(
        "remotive", "https://remotive.exemplo.test/vagas/usd", salario_texto="US$ 5,000/month"
    )
    with closing(_banco(dados)) as con:
        servidor = _Servidor()  # controle: ligada, busca o PTAX e põe o valor em reais
        await _buscar(con, Falso("remotive", [usd]), servidor=servidor)
        assert len(servidor.ptax()) == 1
        assert _um(con, "SELECT sal_mensal_min_brl FROM vaga") is not None
        con.execute("UPDATE vaga SET sal_mensal_min_brl = NULL, sal_cotacao_data = NULL")
        con.commit()
        gravar_config(con, "conversao_moeda_ligada", False)
        servidor = _Servidor()  # a cotação do dia já está no banco: só o interruptor segura
        await _buscar(con, Falso("remotive", [usd]), servidor=servidor)
        assert servidor.ptax() == []  # nenhum pedido ao PTAX
        assert _um(con, "SELECT sal_mensal_min_brl FROM vaga") is None  # só o valor original
        con.execute("DELETE FROM cotacao")
        con.commit()
        await _buscar(con, Falso("remotive", [usd]), servidor=servidor)
        assert servidor.ptax() == [] and _um(con, "SELECT count(*) FROM cotacao") == 0


async def _ocultar(dados: Path, geral: bool, regras_da_busca: Mapping[str, bool]) -> None:
    """Duas buscas iguais, uma com `regras_da_busca`; a vaga em BRL fica abaixo do mínimo."""
    brl = _vaga("remotive", "https://remotive.exemplo.test/vagas/brl", salario_texto="R$ 3.000/mês")
    with closing(_banco(dados)) as con:
        ids = [
            criar_busca(
                con,
                Busca(nome=n, salario_min_centavos=500_000, salario_moeda="BRL", regras_ocultar=r),
                AGORA,
                regras_ligadas=True,
                hoje=HOJE,
            )
            for n, r in (("com regras", regras_da_busca), ("padrão", {}))
        ]
        gravar_config(con, "regras_ocultar_ligadas", geral)
        await _buscar(con, Falso("remotive", [brl]))
        assert _oculta(con, ids[0], brl.url) is None
        assert _oculta(con, ids[1], brl.url) == ("salario" if geral else None)
        if not geral:  # controle: ligada a chave geral, a regra volta a ocultar
            gravar_config(con, "regras_ocultar_ligadas", True)
            await _buscar(con, Falso("remotive", [brl]))
            assert _oculta(con, ids[0], brl.url) == "salario"


async def _ocultar_geral(dados: Path) -> None:
    await _ocultar(dados, False, {})


async def _ocultar_por_busca(dados: Path) -> None:
    await _ocultar(dados, True, {"salario": False})


async def _segundo_plano(dados: Path) -> None:
    with closing(_banco(dados)):
        pass
    app = criar_app(dados, PORTA)
    sistema = FalsoSistema(home=str(dados))
    app.state.relogio = RelogioFalso(AGORA)
    app.state.rodar_comando = sistema
    app.state.ambiente = {"HOME": str(dados)}
    app.state.plataforma = "linux"
    cliente = TestClient(app, base_url=BASE, follow_redirects=False)

    def enviar(**campos: str) -> None:
        resposta = cliente.post(
            "/configuracoes/segundo-plano", data={CAMPO_CSRF: app.state.csrf, **campos}
        )
        assert resposta.status_code == 303

    enviar(segundo_plano="on")  # controle
    assert ("enable", "--now", "jobot.service") in sistema.systemctl()
    enviar()
    assert ("disable", "--now", "jobot.service") in sistema.systemctl()  # não inicia sozinho
    with closing(abrir(dados / "jobot.db")) as con:
        assert ler_config(con, "segundo_plano") is False


CASOS: Mapping[str, Callable[[Path], Awaitable[None]]] = {
    "fonte": _fonte,
    "empresa": _empresa,
    "descoberta_cc_ligada": _descoberta,
    "paginas_ligadas": _paginas,
    "enriquecimento_ligado": _enriquecimento,
    "destaques_ligados": _destaques,
    "conversao_moeda_ligada": _conversao,
    "regras_ocultar_ligadas": _ocultar_geral,
    "regras_ocultar_por_busca": _ocultar_por_busca,
    "segundo_plano": _segundo_plano,
}


@pytest.mark.anyio
@pytest.mark.parametrize("chave", list(CASOS))
async def test_cada_interruptor_para_a_funcao(dados: Path, chave: str) -> None:
    await CASOS[chave](dados)


def test_todo_interruptor_da_13_7_tem_caso() -> None:
    # chave nova em `PADROES` sem caso aqui reprova: a 13.7 e o critério 26 pedem um teste por chave
    chaves = {c for c in PADROES if c.endswith(("_ligada", "_ligadas", "_ligado", "_ligados"))}
    assert chaves <= set(CASOS)
    assert {"fonte", "empresa", "segundo_plano"} <= set(CASOS)
