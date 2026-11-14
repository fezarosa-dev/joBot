"""Execução completa da busca (plano T41; desenho 10.6, 12.3 e 12.4; decisões 16, 17, 19 e 23).

O relógio da execução é falso e o batimento dorme até o teste mandar (`RelogioParado`); o
`ClienteEducado` tem o seu próprio `RelogioFalso`, para o ritmo por host não travar nada.
Datas em UTC com fuso (`astimezone(UTC).isoformat()`), como a T22.
"""

import asyncio
import json
import sqlite3
import time
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.agenda import execucao
from jobot.agenda.execucao import executar_busca, reprocessar_se_regras_mudaram
from jobot.banco.buscas import criar_busca
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.cotacoes import gravar_cotacao
from jobot.banco.execucoes import abrir_execucao, fechar_execucao, gravar_saude
from jobot.banco.migrar import migrar
from jobot.nucleo.cambio import Cotacao
from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
)
from jobot.nucleo.http import ClienteEducado, HttpDoEscopo, HttpEducado, Parou429, Validadores
from jobot.nucleo.modelo import Busca, Local, VagaColetada
from jobot.nucleo.tratamento.rotulos import VERSAO_REGRAS
from jobot.nucleo.url import canonica, hash_url

pytestmark = pytest.mark.anyio

# 01:00 em UTC é 22:00 do dia 13 em -03: o dia local (DP8) é 13, o dia UTC é 14.
AGORA = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)
HOJE = date(2026, 11, 13)
FONTE = "falsa"
PTAX = Path(__file__).resolve().parents[1] / "fixtures" / "ptax"
DESCRICAO_PT = (
    "Estamos contratando uma pessoa desenvolvedora Python para trabalhar remoto com a nossa"
    " equipe de produto, cuidando de serviços, testes automatizados e entregas semanais."
)
DETALHE = "Descrição completa vinda do detalhe, com responsabilidades e requisitos da vaga."


def _iso(quando: datetime) -> str:
    return quando.astimezone(UTC).isoformat()


@pytest.fixture
def fuso_local() -> Iterator[None]:
    """Fuso -03 sem depender do tzdata da máquina; desfeito no fim."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TZ", "<-03>3")
        time.tzset()
        yield
    time.tzset()


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    _fonte(c, FONTE)
    yield c
    c.close()


def _fonte(
    con: sqlite3.Connection, chave: str, *, ligada: bool = True, intervalo_min: int | None = None
) -> None:
    con.execute(
        "INSERT INTO fonte (chave, leva, ligada, intervalo_min) VALUES (?, 'A', ?, ?)",
        (chave, int(ligada), intervalo_min),
    )
    con.commit()


def _vaga(n: int | str, *, fonte: str = FONTE, escopo: str = "", **campos: Any) -> VagaColetada:
    base: dict[str, Any] = {
        "fonte": fonte,
        "escopo": escopo,
        "url": f"https://{fonte}.exemplo.test/vagas/{n}",
        "titulo": "Desenvolvedor Python",
        "empresa": "Acme",
        "descricao_formato": "texto",
        "descricao": DESCRICAO_PT,
    }
    return VagaColetada(**(base | campos))


def _detalhe_completo(item: Item) -> VagaColetada | None:
    if isinstance(item, UrlListada):
        return VagaColetada(
            fonte="mapa",
            escopo="",
            url=item.url,
            titulo="Estágio em dados",
            empresa="Beta",
            descricao_formato="texto",
            descricao=DESCRICAO_PT,
        )
    return replace(item, descricao=DETALHE)


@dataclass
class Falso:
    chave: str = FONTE
    lista: dict[str, tuple[Item, ...]] = field(default_factory=lambda: {"": ()})
    nome: str = "Falsa"
    leva: Literal["A", "B"] = "A"
    hosts: tuple[str, ...] = ()
    credito_obrigatorio: bool = False
    intervalo_min: int | None = None
    max_pedidos: int | None = None
    espera_s: float = 1.0
    por_escopo: Mapping[str, LimiteEscopo] = field(default_factory=dict)
    detalhe: Callable[[Item], VagaColetada | None] | None = None
    erro_escopos: bool = False
    antes_de_coletar: Callable[[], Awaitable[None]] | None = None
    contextos: list[ContextoColeta] = field(default_factory=list)
    coletados: list[str] = field(default_factory=list)
    detalhados: list[str] = field(default_factory=list)

    def escopos(self, ctx: ContextoColeta) -> tuple[str, ...]:
        self.contextos.append(ctx)
        if self.erro_escopos:
            raise RuntimeError("escopos quebrou")
        return tuple(self.lista)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        self.coletados.append(escopo)
        if self.antes_de_coletar is not None:
            await self.antes_de_coletar()
        return ResultadoEscopo(self.lista[escopo], "ok", None, 0)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        self.detalhados.append(item.url)
        return None if self.detalhe is None else self.detalhe(item)

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        return {}


class RelogioParado(RelogioFalso):
    """O batimento dorme para sempre: a hora só muda quando o teste cria outro relógio."""

    async def dormir(self, s: float) -> None:
        self.dormidas.append(s)
        await asyncio.Event().wait()


class RelogioDeBatimento(RelogioFalso):
    """Cada `dormir` espera um tique do teste e então anda `s` segundos."""

    def __init__(self, inicio: datetime) -> None:
        super().__init__(inicio)
        self.tiques: asyncio.Queue[None] = asyncio.Queue()

    async def dormir(self, s: float) -> None:
        await self.tiques.get()
        await super().dormir(s)


class Servidor:
    """PTAX falso; qualquer outro host responde 404."""

    def __init__(self, ptax: str = "usd_semana") -> None:
        self.pedidos: list[httpx.Request] = []
        self.ptax = (PTAX / f"{ptax}.json").read_text(encoding="utf-8")

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if pedido.url.host == "olinda.bcb.gov.br":
            return httpx.Response(200, text=self.ptax)
        return httpx.Response(404)


class SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _executar(
    con: sqlite3.Connection,
    coletores: Iterable[Falso],
    *,
    relogio: RelogioFalso | None = None,
    servidor: Servidor | None = None,
    motivo: Literal["agenda", "agora", "recuperacao"] = "agenda",
) -> int | None:
    cliente = ClienteEducado(
        httpx.MockTransport(servidor or Servidor()),
        RelogioFalso(AGORA),
        SemValidadores(),
        "9.9.9",
        resolver=_sem_dns,
    )
    try:
        return await executar_busca(
            con,
            cliente,
            relogio or RelogioParado(AGORA),
            motivo,
            coletores={c.chave: c for c in coletores},
        )
    finally:
        await cliente.fechar()


async def _ate_coletar(comecou: asyncio.Event, tarefa: asyncio.Task[Any]) -> None:
    """Espera o coletor começar (ou a execução acabar antes disso, o que é falha)."""
    espera = asyncio.ensure_future(comecou.wait())
    await asyncio.wait({espera, tarefa}, timeout=5, return_when=asyncio.FIRST_COMPLETED)
    espera.cancel()
    assert comecou.is_set(), "a execução não chegou a coletar"


def _um(con: sqlite3.Connection, sql: str, *params: object) -> Any:
    linha = con.execute(sql, params).fetchone()
    return None if linha is None else linha[0]


def _vaga_id(con: sqlite3.Connection, url: str) -> Any:
    return _um(con, "SELECT id FROM vaga WHERE url_hash = ?", hash_url(canonica(url)))


def _saude(con: sqlite3.Connection, execucao_id: int) -> set[tuple[Any, ...]]:
    linhas = con.execute(
        "SELECT fonte, escopo, estado, vagas, motivo FROM saude WHERE execucao_id = ?",
        (execucao_id,),
    ).fetchall()
    return {tuple(linha) for linha in linhas}


def _coletada(con: sqlite3.Connection, url: str) -> VagaColetada:
    texto = _um(
        con,
        "SELECT o.coletada FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id WHERE v.url_hash = ?",
        hash_url(canonica(url)),
    )
    return VagaColetada.de_json(texto)


def _brl(con: sqlite3.Connection, url: str) -> tuple[Any, ...] | None:
    linha = con.execute(
        "SELECT sal_mensal_min_brl, sal_cotacao_data FROM vaga WHERE url_hash = ?",
        (hash_url(canonica(url)),),
    ).fetchone()
    return None if linha is None else tuple(linha)


def _oculta(con: sqlite3.Connection, busca_id: int, url: str) -> Any:
    return _um(
        con,
        "SELECT e.oculta_motivo FROM encaixe e JOIN vaga v ON v.id = e.vaga_id"
        " WHERE e.busca_id = ? AND v.url_hash = ?",
        busca_id,
        hash_url(canonica(url)),
    )


def _espiar(monkeypatch: pytest.MonkeyPatch, nome: str) -> list[dict[str, Any]]:
    """Troca `execucao.<nome>` por uma espia que guarda os argumentos nomeados e repassa."""
    original = getattr(execucao, nome)
    chamadas: list[dict[str, Any]] = []

    def espia(*args: Any, **kwargs: Any) -> Any:
        chamadas.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(execucao, nome, espia)
    return chamadas


# ---------------------------------------------------------------- passos


async def test_ponta_a_ponta_com_coletor_falso(con: sqlite3.Connection) -> None:
    _fonte(con, "desligada", ligada=False)
    busca_id = criar_busca(
        con, Busca(nome="py", cargos=("python",)), AGORA, regras_ligadas=True, hoje=HOJE
    )
    falso = Falso(lista={"": (_vaga(1),)})
    desligada = Falso(chave="desligada", lista={"": (_vaga(2, fonte="desligada"),)})

    execucao_id = await _executar(con, [falso, desligada])

    assert execucao_id is not None
    assert con.execute("SELECT titulo FROM vaga").fetchall() == [("Desenvolvedor Python",)]
    vaga_id = _vaga_id(con, _vaga(1).url)
    assert _saude(con, execucao_id) == {
        (FONTE, "", "ok", 1, None),
        ("desligada", "", "desligada", 0, None),
    }
    assert desligada.coletados == []
    nota = _um(
        con, "SELECT nota FROM encaixe WHERE busca_id = ? AND vaga_id = ?", busca_id, vaga_id
    )
    assert nota is not None
    linha = con.execute(
        "SELECT estado, terminada_em FROM execucao WHERE id = ?", (execucao_id,)
    ).fetchone()
    assert tuple(linha) == ("concluida", _iso(AGORA))


async def test_segunda_ao_mesmo_tempo_devolve_none(con: sqlite3.Connection) -> None:
    comecou, liberar = asyncio.Event(), asyncio.Event()

    async def segurar() -> None:
        comecou.set()
        await liberar.wait()

    primeira = Falso(lista={"": (_vaga(1),)}, antes_de_coletar=segurar)
    tarefa = asyncio.create_task(_executar(con, [primeira]))
    await _ate_coletar(comecou, tarefa)
    segunda = Falso(lista={"": (_vaga(2),)})

    assert await _executar(con, [segunda], motivo="agora") is None
    assert segunda.coletados == []

    liberar.set()
    execucao_id = await tarefa
    assert execucao_id is not None
    assert _um(con, "SELECT estado FROM execucao WHERE id = ?", execucao_id) == "concluida"
    assert _um(con, "SELECT count(*) FROM execucao") == 1


async def test_agora_respeita_intervalo_min(con: sqlite3.Connection) -> None:
    _fonte(con, "lenta", intervalo_min=60)
    anterior = abrir_execucao(con, "busca", "agenda", AGORA - timedelta(minutes=10))
    assert anterior is not None
    gravar_saude(con, anterior, "lenta", "", "ok", vagas=1, pedidos=1)
    fechar_execucao(con, anterior, AGORA - timedelta(minutes=9))
    lenta = Falso(chave="lenta", intervalo_min=60, lista={"": (_vaga(9, fonte="lenta"),)})
    rapida = Falso(lista={"": (_vaga(1),)})

    execucao_id = await _executar(con, [lenta, rapida], motivo="agora")

    assert execucao_id is not None
    assert _saude(con, execucao_id) == {
        ("lenta", "", "no_limite", 0, "saude.intervalo"),
        (FONTE, "", "ok", 1, None),
    }
    assert lenta.coletados == []
    assert rapida.coletados == [""]


# ---------------------------------------------------------------- enriquecimento


async def test_enriquecimento(con: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    assert (execucao.MAX_DETALHES_POR_FONTE, execucao.MAX_DETALHES_POR_EXECUCAO) == (50, 200)
    _fonte(con, "mapa")
    velha = _vaga("velha", descricao="")
    # vaga de uma execução anterior, gravada com o enriquecimento desligado
    gravar_config(con, "enriquecimento_ligado", False)
    ontem = AGORA - timedelta(days=1)
    await _executar(con, [Falso(lista={"": (velha,)})], relogio=RelogioParado(ontem))
    gravar_config(con, "enriquecimento_ligado", True)

    cacheada = _vaga("cacheada", descricao="")
    con.execute(
        "INSERT INTO enriquecimento (url_hash, buscado_em, conteudo) VALUES (?, ?, '')",
        (hash_url(canonica(cacheada.url)), _iso(AGORA - timedelta(days=10))),
    )
    con.commit()
    com_descricao = _vaga("com-descricao")
    novas = [_vaga(f"nova-{n}", descricao="") for n in range(5)]
    lista = Falso(lista={"": (velha, cacheada, com_descricao, *novas)}, detalhe=_detalhe_completo)
    m1 = UrlListada("https://mapa.exemplo.test/vagas/m1", AGORA - timedelta(hours=1))
    m2 = UrlListada("https://mapa.exemplo.test/vagas/m2", AGORA - timedelta(hours=2))
    mapa = Falso(chave="mapa", lista={"": (m1, m2)}, detalhe=_detalhe_completo)
    # 3 por fonte e 4 por execução: os 2 detalhes do sitemap deixam só 2 para a lista
    monkeypatch.setattr(execucao, "MAX_DETALHES_POR_FONTE", 3)
    monkeypatch.setattr(execucao, "MAX_DETALHES_POR_EXECUCAO", 4)

    await _executar(con, [mapa, lista])

    assert mapa.detalhados == [m1.url, m2.url]
    assert len(lista.detalhados) == 2
    assert set(lista.detalhados) <= {v.url for v in novas}
    for url in lista.detalhados:
        assert _coletada(con, url).descricao == DETALHE
        assert DETALHE in _um(
            con, "SELECT descricao_texto FROM vaga WHERE id = ?", _vaga_id(con, url)
        )
        linha = con.execute(
            "SELECT buscado_em, conteudo FROM enriquecimento WHERE url_hash = ?",
            (hash_url(canonica(url)),),
        ).fetchone()
        assert linha[0] == _iso(AGORA)
        assert VagaColetada.de_json(linha[1]).descricao == DETALHE
    sobra = {v.url for v in novas} - set(lista.detalhados)
    for url in sobra:
        assert _coletada(con, url).descricao == ""

    # o que não coube vai na próxima, as mais recentes primeiro; a velha (sem detalhe e sem
    # tentativa no cache) vem depois; a cacheada e a que já tem descrição nunca
    await _executar(con, [mapa, lista], relogio=RelogioParado(AGORA + timedelta(hours=1)))
    assert mapa.detalhados == [m1.url, m2.url]
    assert set(lista.detalhados[2:]) == sobra
    assert all(_coletada(con, url).descricao == DETALHE for url in sobra)

    await _executar(con, [mapa, lista], relogio=RelogioParado(AGORA + timedelta(hours=2)))
    assert lista.detalhados[5:] == [velha.url]
    assert _coletada(con, velha.url).descricao == DETALHE


async def test_detalhe_que_falhou_volta_na_proxima(con: sqlite3.Connection) -> None:
    def instavel(item: Item) -> VagaColetada | None:
        if len(lista.detalhados) == 1:
            raise RuntimeError("fora do ar")
        return _detalhe_completo(item)

    vaga = _vaga(1, descricao="")
    lista = Falso(lista={"": (vaga,)}, detalhe=instavel)
    await _executar(con, [lista], relogio=RelogioParado(AGORA - timedelta(hours=1)))
    assert _um(con, "SELECT count(*) FROM enriquecimento") == 0

    await _executar(con, [lista])

    assert lista.detalhados == [vaga.url, vaga.url]
    assert _coletada(con, vaga.url).descricao == DETALHE


async def test_sitemap_detalhado_pelo_executor_nao_repete_no_passo_4(
    con: sqlite3.Connection,
) -> None:
    _fonte(con, "mapa")
    m1 = UrlListada("https://mapa.exemplo.test/vagas/m1", AGORA - timedelta(hours=1))

    def sem_descricao(item: Item) -> VagaColetada | None:
        v = _detalhe_completo(item)
        return None if v is None else replace(v, descricao="")

    mapa = Falso(chave="mapa", lista={"": (m1,)}, detalhe=sem_descricao)

    await _executar(con, [mapa])

    assert mapa.detalhados == [m1.url]


async def test_cache_so_depois_do_detalhe_gravado(con: sqlite3.Connection) -> None:
    # o detalhe falha ao gravar: o cache, na mesma transação, também não fica
    con.execute(
        "CREATE TRIGGER quebra BEFORE UPDATE OF coletada ON ocorrencia"
        " BEGIN SELECT RAISE(ABORT, 'disco cheio'); END"
    )
    con.commit()
    lista = Falso(lista={"": (_vaga(1, descricao=""),)}, detalhe=_detalhe_completo)

    with pytest.raises(sqlite3.IntegrityError, match="disco cheio"):
        await _executar(con, [lista])

    assert lista.detalhados == [_vaga(1).url]
    assert _um(con, "SELECT count(*) FROM enriquecimento") == 0


async def test_excecao_na_busca_marca_a_execucao_interrompida_na_hora(
    con: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    # O executor absorve a exceção do próprio coletor (vira saúde "falhou"); o erro que sobe
    # vem de um passo seguinte, aqui o encaixe, que ainda deixa uma transação aberta.
    def quebra(c: sqlite3.Connection, *args: Any, **kwargs: Any) -> int:
        c.execute("UPDATE vaga SET titulo = 'meio do caminho'")
        raise RuntimeError("encaixe quebrou")

    monkeypatch.setattr(execucao, "recalcular_encaixe", quebra)
    falso = Falso(lista={"": (_vaga(1),)})

    with pytest.raises(RuntimeError, match="encaixe quebrou"):
        await _executar(con, [falso])

    linha = con.execute("SELECT estado, terminada_em FROM execucao").fetchone()
    assert tuple(linha) == ("interrompida", _iso(AGORA))
    assert _um(con, "SELECT count(*) FROM vaga WHERE titulo = 'meio do caminho'") == 0
    assert not con.in_transaction

    # a próxima abre no mesmo instante, sem esperar os 5 min do batimento velho
    monkeypatch.undo()
    segunda = await _executar(con, [falso])
    assert segunda is not None
    assert _um(con, "SELECT estado FROM execucao WHERE id = ?", segunda) == "concluida"


async def _pendente_de_ontem(con: sqlite3.Connection, coletor: Falso) -> VagaColetada:
    """Grava, numa execução de ontem com o enriquecimento desligado, uma vaga sem descrição."""
    vaga = _vaga(1, fonte=coletor.chave, descricao="")
    gravar_config(con, "enriquecimento_ligado", False)
    await _executar(
        con,
        [replace(coletor, lista={"": (vaga,)})],
        relogio=RelogioParado(AGORA - timedelta(days=1)),
    )
    gravar_config(con, "enriquecimento_ligado", True)
    assert _coletada(con, vaga.url).descricao == ""
    return vaga


async def test_passo_4_nao_pede_a_fonte_desligada(con: sqlite3.Connection) -> None:
    lista = Falso(detalhe=_detalhe_completo)
    await _pendente_de_ontem(con, lista)
    con.execute("UPDATE fonte SET ligada = 0 WHERE chave = ?", (FONTE,))
    con.commit()

    await _executar(con, [lista])

    assert lista.coletados == [""]  # só a de ontem
    assert lista.detalhados == []


async def test_passo_4_nao_pede_a_fonte_no_intervalo(con: sqlite3.Connection) -> None:
    _fonte(con, "lenta", intervalo_min=60)
    lenta = Falso(chave="lenta", intervalo_min=60, detalhe=_detalhe_completo)
    await _pendente_de_ontem(con, lenta)
    anterior = abrir_execucao(con, "busca", "agenda", AGORA - timedelta(minutes=10))
    assert anterior is not None
    gravar_saude(con, anterior, "lenta", "", "ok", vagas=1, pedidos=1)
    fechar_execucao(con, anterior, AGORA - timedelta(minutes=9))

    execucao_id = await _executar(con, [lenta])

    assert execucao_id is not None
    assert ("lenta", "", "no_limite", 0, "saude.intervalo") in _saude(con, execucao_id)
    assert lenta.detalhados == []


@pytest.mark.parametrize(
    ("estado", "motivo"),
    [
        ("no_limite", "saude.parou_429"),
        ("no_limite", "saude.orcamento"),
        ("falhou", "saude.bloqueio"),
        ("parcial", "saude.limite_atingido"),
    ],
)
async def test_passo_4_nao_pede_a_fonte_que_parou_na_listagem(
    con: sqlite3.Connection, estado: Literal["no_limite", "falhou", "parcial"], motivo: str
) -> None:
    @dataclass
    class Parada(Falso):
        async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
            self.coletados.append(escopo)
            return ResultadoEscopo((), estado, motivo, 1)

    lista = Falso(detalhe=_detalhe_completo)
    await _pendente_de_ontem(con, lista)
    parada = Parada(detalhe=_detalhe_completo)

    await _executar(con, [parada])

    assert parada.coletados == [""]
    assert parada.detalhados == []


Estado = Literal["ok", "parcial", "no_limite", "falhou"]


@dataclass
class PorEscopo(Falso):
    """Cada escopo devolve o (estado, motivo, pedidos) de `saidas`; sem entrada, ok e 0 pedidos."""

    saidas: dict[str, tuple[Estado, str | None, int]] = field(default_factory=dict)
    https: dict[str, HttpEducado] = field(default_factory=dict)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        self.coletados.append(escopo)
        estado, motivo, pedidos = self.saidas.get(escopo, ("ok", None, 0))
        return ResultadoEscopo(
            self.lista[escopo] if estado == "ok" else (), estado, motivo, pedidos
        )

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        self.https[item.url] = http
        return await super().detalhar(item, http)


async def _pendentes_por_escopo(
    con: sqlite3.Connection, coletor: PorEscopo, quantas: Mapping[str, int]
) -> dict[str, list[VagaColetada]]:
    """Grava ontem, com o enriquecimento desligado, `quantas[e]` vagas sem descrição em `e`."""
    vagas = {
        e: [_vaga(f"{e}-{i}", fonte=coletor.chave, escopo=e, descricao="") for i in range(n)]
        for e, n in quantas.items()
    }
    coletor.lista = {e: tuple(vs) for e, vs in vagas.items()}
    gravar_config(con, "enriquecimento_ligado", False)
    await _executar(con, [coletor], relogio=RelogioParado(AGORA - timedelta(days=1)))
    gravar_config(con, "enriquecimento_ligado", True)
    coletor.coletados.clear()
    assert coletor.detalhados == []
    return vagas


async def test_escopo_parado_so_tira_as_candidatas_dele(con: sqlite3.Connection) -> None:
    coletor = PorEscopo(detalhe=_detalhe_completo)
    vagas = await _pendentes_por_escopo(con, coletor, {"a": 1, "b": 1})
    coletor.saidas = {"a": ("no_limite", "saude.parou_429", 1)}

    await _executar(con, [coletor])

    assert coletor.coletados == ["a", "b"]
    assert coletor.detalhados == [vagas["b"][0].url]
    assert _coletada(con, vagas["b"][0].url).descricao == DETALHE
    assert _coletada(con, vagas["a"][0].url).descricao == ""


@pytest.mark.parametrize(
    ("estado", "motivo"),
    [
        ("no_limite", "saude.orcamento"),
        ("falhou", "saude.bloqueio"),
        ("parcial", "saude.limite_atingido"),
    ],
)
async def test_parada_da_fonte_tira_todos_os_escopos(
    con: sqlite3.Connection, estado: Estado, motivo: str
) -> None:
    coletor = PorEscopo(detalhe=_detalhe_completo)
    await _pendentes_por_escopo(con, coletor, {"a": 1, "b": 1})
    coletor.saidas = {"a": (estado, motivo, 1)}

    await _executar(con, [coletor])

    assert coletor.coletados == ["a", "b"]
    assert coletor.detalhados == []


async def test_detalhe_usa_a_espera_do_por_escopo(
    con: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    aberturas: dict[int, dict[str, Any]] = {}
    original = ClienteEducado.escopo

    def espia(self: ClienteEducado, **kw: Any) -> HttpDoEscopo:
        http = original(self, **kw)
        aberturas[id(http)] = kw
        return http

    coletor = PorEscopo(
        espera_s=2.0,
        por_escopo={"lento": LimiteEscopo(espera_s=5, para_no_429=True)},
        detalhe=_detalhe_completo,
    )
    vagas = await _pendentes_por_escopo(con, coletor, {"lento": 1, "normal": 1})
    monkeypatch.setattr(ClienteEducado, "escopo", espia)

    await _executar(con, [coletor])

    lento, normal = vagas["lento"][0].url, vagas["normal"][0].url
    assert coletor.detalhados == [lento, normal]
    ritmo = {
        url: (kw["espera_s"], kw.get("para_no_429", False))
        for url, kw in ((u, aberturas[id(h)]) for u, h in coletor.https.items())
    }
    assert ritmo == {lento: (5, True), normal: (2.0, False)}


async def test_parou429_no_detalhe_para_so_o_escopo(con: sqlite3.Connection) -> None:
    def detalhe(item: Item) -> VagaColetada | None:
        if "/vagas/a-" in item.url:
            raise Parou429(f"{item.url}: HTTP 429")
        return _detalhe_completo(item)

    coletor = PorEscopo(detalhe=detalhe)
    vagas = await _pendentes_por_escopo(con, coletor, {"a": 2, "b": 1})

    await _executar(con, [coletor])

    # o 429 no a-0 poupa o a-1, mas o escopo b segue
    assert coletor.detalhados == [vagas["a"][0].url, vagas["b"][0].url]
    assert _coletada(con, vagas["b"][0].url).descricao == DETALHE


async def test_orcamento_da_fonte_e_um_so_entre_escopos(con: sqlite3.Connection) -> None:
    @dataclass
    class Pedinte(PorEscopo):
        async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
            self.detalhados.append(item.url)
            await http.pedir("GET", item.url)  # o servidor falso responde 404: erro desta URL
            return None

    # 1 pedido na fonte; a listagem falsa não pede nada (o executor conta os pedidos reais)
    coletor = Pedinte(max_pedidos=1)
    vagas = await _pendentes_por_escopo(con, coletor, {"a": 1, "b": 1})
    servidor = Servidor()

    await _executar(con, [coletor], servidor=servidor)

    # o b esbarra no orçamento antes de pedir. Mutante que deixa o teste vermelho (o servidor
    # recebe 2 pedidos): em _enriquecer, `gastos += http.pedidos` trocado por `pass`
    assert coletor.detalhados == [vagas["a"][0].url, vagas["b"][0].url]
    assert [str(p.url) for p in servidor.pedidos] == [vagas["a"][0].url]


async def test_enriquecimento_interruptor_desligado(
    con: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fonte(con, "mapa")
    conhecida = UrlListada("https://mapa.exemplo.test/vagas/conhecida", AGORA - timedelta(days=2))
    ontem = AGORA - timedelta(days=1)
    mapa = Falso(chave="mapa", lista={"": (conhecida,)}, detalhe=_detalhe_completo)
    await _executar(con, [mapa], relogio=RelogioParado(ontem))
    assert _vaga_id(con, conhecida.url) is not None

    gravar_config(con, "enriquecimento_ligado", False)
    rodadas = _espiar(monkeypatch, "rodar")
    nova = UrlListada("https://mapa.exemplo.test/vagas/nova", AGORA - timedelta(hours=1))
    mapa.lista = {"": (conhecida, nova)}
    lista = Falso(lista={"": (_vaga(1, descricao=""),)}, detalhe=_detalhe_completo)
    servidor = Servidor()

    await _executar(con, [mapa, lista], servidor=servidor)

    assert [r["max_detalhes_por_fonte"] for r in rodadas] == [0]
    assert mapa.detalhados == [conhecida.url]  # só o da execução de ontem
    assert lista.detalhados == []
    assert servidor.pedidos == []
    assert _vaga_id(con, nova.url) is None
    ultima = _um(
        con,
        "SELECT o.ultima_vista_em FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id"
        " WHERE v.url_hash = ?",
        hash_url(canonica(conhecida.url)),
    )
    assert ultima == _iso(AGORA)


async def test_cache_de_enriquecimento_vencido_nao_apaga_descricao(
    con: sqlite3.Connection,
) -> None:
    html = f"<p>{DETALHE}</p>"

    def detalhe_html(item: Item) -> VagaColetada | None:
        assert isinstance(item, VagaColetada)
        return replace(item, descricao=html, descricao_formato="html")

    lista = Falso(lista={"": (_vaga(1, descricao=""),)}, detalhe=detalhe_html)
    await _executar(con, [lista], relogio=RelogioParado(AGORA - timedelta(days=31)))
    url = _vaga(1).url
    assert lista.detalhados == [url]
    assert DETALHE in _um(con, "SELECT descricao_texto FROM vaga")

    # 31 dias depois o cache venceu; a listagem traz a vaga de novo, sem descrição
    await _executar(con, [lista])

    assert lista.detalhados == [url]
    assert _coletada(con, url).descricao == html
    assert DETALHE in _um(con, "SELECT descricao_texto FROM vaga")
    assert _um(con, "SELECT count(*) FROM enriquecimento") == 1


# ---------------------------------------------------------------- câmbio e encaixe


@pytest.mark.usefixtures("fuso_local")
@pytest.mark.parametrize("ligada", [True, False])
async def test_cotacao_so_com_interruptor_ligado(
    con: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch, ligada: bool
) -> None:
    assert AGORA.astimezone().date() == HOJE
    gravar_config(con, "conversao_moeda_ligada", ligada)
    aplicadas = _espiar(monkeypatch, "aplicar_cotacoes")
    usd = _vaga(1, salario_texto="US$ 5,000/month")
    servidor = Servidor()

    await _executar(con, [Falso(lista={"": (usd,)})], servidor=servidor)

    assert aplicadas == [{"conversao_ligada": ligada, "hoje": HOJE}]
    ptax = [p for p in servidor.pedidos if p.url.host == "olinda.bcb.gov.br"]
    if ligada:
        assert len(ptax) == 1
        assert ptax[0].url.params["@dataFinalCotacao"] == "'11-13-2026'"  # o dia local
        assert _um(con, "SELECT count(*) FROM cotacao WHERE moeda = 'USD'") == 1
        assert _brl(con, usd.url) == (28275, "2026-11-13")  # 5.000 x 5,6549
    else:
        assert ptax == []
        assert _um(con, "SELECT count(*) FROM cotacao") == 0
        assert _brl(con, usd.url) == (None, None)


async def test_conversao_desligada_ainda_filtra_vaga_em_brl(con: sqlite3.Connection) -> None:
    gravar_config(con, "conversao_moeda_ligada", False)
    gravar_cotacao(con, Cotacao(moeda="USD", data=HOJE, venda=Decimal("5.65")), AGORA)
    busca = Busca(nome="mínimo", salario_min_centavos=500_000, salario_moeda="BRL")
    busca_id = criar_busca(con, busca, AGORA, regras_ligadas=True, hoje=HOJE)
    brl = _vaga("brl", salario_texto="R$ 3.000/mês")
    usd = _vaga("usd", salario_texto="US$ 5,000/month")

    await _executar(con, [Falso(lista={"": (brl, usd)})])

    assert _brl(con, brl.url) == (3000, None)
    assert _brl(con, usd.url) == (None, None)
    assert _oculta(con, busca_id, brl.url) == "salario"
    assert _oculta(con, busca_id, usd.url) is None


@pytest.mark.usefixtures("fuso_local")
@pytest.mark.parametrize(("dias", "em_reais", "oculta"), [(8, None, None), (7, 28250, "salario")])
async def test_cotacao_de_8_dias_nao_converte(
    con: sqlite3.Connection, dias: int, em_reais: int | None, oculta: str | None
) -> None:
    # com o dia UTC (14) a de 7 dias teria 8: só converte se `hoje` for o dia local (DP8)
    dia = HOJE - timedelta(days=dias)
    gravar_cotacao(
        con, Cotacao(moeda="USD", data=dia, venda=Decimal("5.65")), AGORA - timedelta(days=dias)
    )
    busca = Busca(nome="mínimo", salario_min_centavos=3_000_000, salario_moeda="BRL")
    busca_id = criar_busca(con, busca, AGORA, regras_ligadas=True, hoje=HOJE)
    usd = _vaga(1, salario_texto="US$ 5,000/month")

    await _executar(con, [Falso(lista={"": (usd,)})], servidor=Servidor("vazio"))

    assert _brl(con, usd.url) == (em_reais, None if em_reais is None else dia.isoformat())
    assert _oculta(con, busca_id, usd.url) == oculta
    motivos = json.loads(
        _um(
            con,
            "SELECT motivos FROM encaixe WHERE busca_id = ? AND vaga_id = ?",
            busca_id,
            _vaga_id(con, usd.url),
        )
    )
    chave = "encaixe.salario_nao_informado" if em_reais is None else "encaixe.salario_abaixo"
    assert chave in [m["chave"] for m in motivos]


async def test_paises_das_buscas_vao_no_contexto(con: sqlite3.Connection) -> None:
    lisboa = Local(cidade="Lisboa", pais="PT")
    criar_busca(
        con,
        Busca(nome="a", cargos=("Python",), cidades=(lisboa,)),
        AGORA,
        regras_ligadas=True,
        hoje=HOJE,
    )
    criar_busca(con, Busca(nome="b", cargos=("Dados",)), AGORA, regras_ligadas=True, hoje=HOJE)
    falso = Falso(lista={"": (_vaga(1),)})

    await _executar(con, [falso])

    assert [c.paises for c in falso.contextos] == [("BR", "PT")]
    assert [c.termos for c in falso.contextos] == [("Python", "Dados")]


# ---------------------------------------------------------------- batimento e escopos


async def _esperar(condicao: Callable[[], bool]) -> None:
    for _ in range(1000):
        if condicao():
            return
        await asyncio.sleep(0)
    raise AssertionError("condição não chegou")


async def test_batimento_a_cada_30_s(con: sqlite3.Connection) -> None:
    relogio = RelogioDeBatimento(AGORA)
    comecou, liberar = asyncio.Event(), asyncio.Event()

    async def segurar() -> None:
        comecou.set()
        await liberar.wait()

    falso = Falso(lista={"": (_vaga(1),)}, antes_de_coletar=segurar)
    tarefa = asyncio.create_task(_executar(con, [falso], relogio=relogio))
    await _ate_coletar(comecou, tarefa)

    def batimento() -> Any:
        return _um(con, "SELECT batimento_em FROM execucao WHERE estado = 'rodando'")

    assert batimento() == _iso(AGORA)
    for n in (1, 2):
        relogio.tiques.put_nowait(None)
        esperado = _iso(AGORA + timedelta(seconds=30 * n))
        await _esperar(lambda esperado=esperado: batimento() == esperado)  # type: ignore[misc]
    liberar.set()
    execucao_id = await tarefa

    assert relogio.dormidas == [30.0, 30.0]
    linha = con.execute(
        "SELECT estado, batimento_em FROM execucao WHERE id = ?", (execucao_id,)
    ).fetchone()
    assert tuple(linha) == ("concluida", _iso(AGORA + timedelta(seconds=60)))


async def test_escopo_extinto_marca_ocorrencias(con: sqlite3.Connection) -> None:
    acme, beta = _vaga("acme", escopo="acme"), _vaga("beta", escopo="beta")
    falso = Falso(lista={"acme": (acme,), "beta": (beta,)})
    await _executar(con, [falso], relogio=RelogioParado(AGORA - timedelta(days=2)))

    def sumiu(url: str) -> Any:
        return _um(
            con,
            "SELECT o.sumiu_em FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id"
            " WHERE v.url_hash = ?",
            hash_url(canonica(url)),
        )

    def fechada(url: str) -> Any:
        return _um(con, "SELECT fechada_em FROM vaga WHERE id = ?", _vaga_id(con, url))

    # a empresa do escopo "beta" saiu da lista
    falso.lista = {"acme": (acme,)}
    ontem = AGORA - timedelta(days=1)
    await _executar(con, [falso], relogio=RelogioParado(ontem))

    assert sumiu(beta.url) == _iso(ontem)
    assert fechada(beta.url) == _iso(ontem)
    assert sumiu(acme.url) is None
    assert fechada(acme.url) is None

    # controle: `escopos` que quebra não é escopo extinto; nada é marcado
    falso.erro_escopos = True
    await _executar(con, [falso])
    assert sumiu(acme.url) is None


async def test_reprocessar_se_regras_mudaram(con: sqlite3.Connection) -> None:
    await _executar(con, [Falso(lista={"": (_vaga(1),)})])
    assert reprocessar_se_regras_mudaram(con) == 0
    con.execute("UPDATE vaga SET versao_regras = 'velha'")
    con.commit()

    assert reprocessar_se_regras_mudaram(con) == 1
    assert _um(con, "SELECT versao_regras FROM vaga") == VERSAO_REGRAS
    assert reprocessar_se_regras_mudaram(con) == 0
