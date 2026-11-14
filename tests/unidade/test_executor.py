import asyncio
import inspect
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

import anyio
import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import executor
from jobot.nucleo.coletores.base import (
    SEM_MUDANCA,
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
    juntar_paginas,
)
from jobot.nucleo.coletores.executor import Historico, SaidaEscopo, estado_da_fonte
from jobot.nucleo.http import (
    Bloqueio,
    ClienteEducado,
    ErroDeRede,
    HttpDoEscopo,
    HttpEducado,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    RespostaGrande,
    Validadores,
)
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)  # início do RelogioFalso
MICROSOFT = "apply.careers.microsoft.com"
CTX = ContextoColeta(empresas=(), termos=("dev",), paises=("BR",))
Responder = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


def _vaga(url: str, fonte: str = "f", escopo: str = "") -> VagaColetada:
    return VagaColetada(
        fonte=fonte, escopo=escopo, url=url, titulo="Dev", empresa="Acme", descricao_formato="texto"
    )


def _url_pagina(chave: str, escopo: str, n: int) -> str:
    host = escopo if "." in escopo else f"{chave}.exemplo"
    return f"https://{host}/{escopo}?p={n}"


def _uma_vaga(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"vagas": [f"https://{pedido.url.host}/v/{pedido.url.path}"]})


class Servidor:
    def __init__(self, responder: Responder = _uma_vaga) -> None:
        self.pedidos: list[httpx.Request] = []
        self.responder = responder

    async def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        r = self.responder(pedido)
        return await r if inspect.isawaitable(r) else r

    def hosts(self) -> list[str]:
        return [p.url.host for p in self.pedidos]


class LeitorFixo:
    def __init__(self, guardados: Mapping[str, Validadores] | None = None) -> None:
        self.guardados = dict(guardados or {})

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


@dataclass
class HistoricoFalso:
    inicios: dict[tuple[str, str | None], datetime] = field(default_factory=dict)
    com_vagas: set[tuple[str, str]] = field(default_factory=set)
    abertas: set[tuple[str, str]] | None = None  # None: todo escopo tem ocorrência aberta
    coletas: dict[tuple[str, str], datetime] = field(default_factory=dict)
    conhecidas: set[str] = field(default_factory=set)
    recentes: set[str] = field(default_factory=set)
    perguntas: list[tuple[str, str | None]] = field(default_factory=list)

    def ultimo_inicio_com_pedido(self, fonte: str, escopo: str | None) -> datetime | None:
        self.perguntas.append((fonte, escopo))
        return self.inicios.get((fonte, escopo))

    def tres_ultimas_ok_trouxeram_vagas(self, fonte: str, escopo: str) -> bool:
        return (fonte, escopo) in self.com_vagas

    def tem_ocorrencia_aberta(self, fonte: str, escopo: str) -> bool:
        return self.abertas is None or (fonte, escopo) in self.abertas

    def ultima_coleta(self, fonte: str, escopo: str) -> datetime | None:
        return self.coletas.get((fonte, escopo))

    def urls_conhecidas(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        return {u for u in urls if u in self.conhecidas}

    def detalhe_recente(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        return {u for u in urls if u in self.recentes}


async def _coleta_padrao(
    chave: str, escopo: str, http: HttpEducado, paginas: int = 1
) -> ResultadoEscopo:
    async def gerar() -> Any:
        for n in range(paginas):
            r = await http.pedir("GET", _url_pagina(chave, escopo, n), condicional=True)
            if r.status == 304:
                yield SEM_MUDANCA
                continue
            dados = cast(dict[str, list[str]], r.json())
            yield tuple(_vaga(u, chave, escopo) for u in dados["vagas"])

    return await juntar_paginas(http, gerar())


Acao = Callable[[str, HttpEducado], Awaitable[ResultadoEscopo]]


@dataclass
class ColetorFalso:
    chave: str
    lista: tuple[str, ...] = ("",)
    nome: str = "Falso"
    leva: Literal["A", "B"] = "A"
    hosts: tuple[str, ...] = ()
    credito_obrigatorio: bool = False
    intervalo_min: int | None = None
    max_pedidos: int | None = None
    espera_s: float = 1.0
    por_escopo: Mapping[str, LimiteEscopo] = field(default_factory=dict)
    acao: Acao | None = None
    paginas: int = 1
    erro_escopos: Exception | None = None
    detalhe: Callable[[Item], VagaColetada | None] | None = None
    contextos: list[ContextoColeta] = field(default_factory=list)
    coletados: list[str] = field(default_factory=list)
    detalhados: list[str] = field(default_factory=list)

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        self.contextos.append(ctx)
        if self.erro_escopos is not None:
            raise self.erro_escopos
        return self.lista

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        self.coletados.append(escopo)
        if self.acao is not None:
            return await self.acao(escopo, http)
        return await _coleta_padrao(self.chave, escopo, http, self.paginas)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        self.detalhados.append(item.url)
        return self.detalhe(item) if self.detalhe is not None else None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        return {}


def _cliente(
    servidor: Servidor | None = None,
    relogio: RelogioFalso | None = None,
    leitor: LeitorFixo | None = None,
) -> ClienteEducado:
    prova: Relogio = relogio or RelogioFalso()
    transporte = httpx.MockTransport(servidor or Servidor())
    return ClienteEducado(transporte, prova, leitor or LeitorFixo(), "9.9.9")


async def _rodar(
    coletores: Iterable[ColetorFalso],
    *,
    historico: HistoricoFalso | None = None,
    servidor: Servidor | None = None,
    relogio: RelogioFalso | None = None,
    leitor: LeitorFixo | None = None,
    cliente: ClienteEducado | None = None,
    ligadas: Set[str] | None = None,
    max_detalhes: int = 50,
    ctx: ContextoColeta = CTX,
    ao_terminar: Callable[[SaidaEscopo], Awaitable[None]] | None = None,
) -> list[SaidaEscopo]:
    rel = relogio or RelogioFalso()
    cli = cliente or _cliente(servidor, rel, leitor)
    prova: Historico = historico or HistoricoFalso()
    por_chave = {c.chave: c for c in coletores}
    saidas: list[SaidaEscopo] = []

    async def guardar(saida: SaidaEscopo) -> None:
        saidas.append(saida)

    try:
        await executor.rodar(
            por_chave,
            ctx,
            cli,
            prova,
            rel,
            ligadas=set(por_chave) if ligadas is None else ligadas,
            ao_terminar_escopo=ao_terminar or guardar,
            max_detalhes_por_fonte=max_detalhes,
        )
    finally:
        await cli.fechar()
    return saidas


def _estados(saidas: Sequence[SaidaEscopo]) -> dict[str, tuple[str, str | None]]:
    """(fonte ou escopo) -> (estado, motivo)."""
    return {
        (s.escopo or s.fonte): (s.resultado.estado, s.resultado.motivo)
        for s in sorted(saidas, key=lambda s: (s.fonte, s.escopo))
    }


def _sitemap(*itens: UrlListada) -> Acao:
    async def acao(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        return ResultadoEscopo(tuple(itens), "ok", None, 1)

    return acao


def _com_titulo(item: Item) -> VagaColetada:
    return _vaga(item.url, "s")


# --- falha isolada e prazo -------------------------------------------------------------------


async def test_excecao_vira_falhou_e_as_outras_terminam() -> None:
    async def quebra(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        raise RuntimeError("fonte quebrou")

    saidas = await _rodar([ColetorFalso("a", acao=quebra), ColetorFalso("b")])
    assert _estados(saidas) == {
        "a": ("falhou", "saude.excecao:RuntimeError"),
        "b": ("ok", None),
    }
    assert len(next(s for s in saidas if s.fonte == "b").resultado.vagas) == 1


@pytest.mark.parametrize(
    ("erro", "motivo"),
    [
        (RespostaGrande("corpo grande"), "saude.resposta_grande"),
        (ErroDeRede("fora do ar"), "saude.erro_de_rede"),
    ],
)
async def test_excecao_conhecida_do_http_no_escopo_vira_o_motivo_proprio(
    erro: Exception, motivo: str
) -> None:
    async def quebra(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        raise erro

    saidas = await _rodar([ColetorFalso("a", acao=quebra)])
    assert _estados(saidas) == {"a": ("falhou", motivo)}


@pytest.mark.parametrize("erro", [Bloqueio("403"), LimiteAtingido("lim"), Parou429("429")])
async def test_parada_que_escapa_do_coletar_segue_saude_excecao(erro: Exception) -> None:
    async def quebra(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        raise erro

    saidas = await _rodar([ColetorFalso("a", acao=quebra)])
    assert _estados(saidas) == {"a": ("falhou", f"saude.excecao:{type(erro).__name__}")}


async def test_resposta_grande_em_escopos_vira_resposta_grande() -> None:
    saidas = await _rodar([ColetorFalso("a", erro_escopos=RespostaGrande("grande"))])
    assert _estados(saidas) == {"a": ("falhou", "saude.resposta_grande")}


async def test_escopos_com_erro_vira_falhou() -> None:
    saidas = await _rodar([ColetorFalso("a", erro_escopos=ValueError("ctx")), ColetorFalso("b")])
    assert _estados(saidas) == {"a": ("falhou", "saude.excecao:ValueError"), "b": ("ok", None)}


async def test_tempo_esgotado_em_5_min_vira_falhou() -> None:
    def lenta(rel: RelogioFalso, s: float) -> Acao:
        async def acao(escopo: str, http: HttpEducado) -> ResultadoEscopo:
            await rel.dormir(s)  # a fonte lenta (esperas do HttpEducado) avança o relógio
            return ResultadoEscopo((_vaga("https://a.exemplo/v/1", "a"),), "ok", None, 1)

        return acao

    rel = RelogioFalso()
    saidas = await _rodar([ColetorFalso("a", acao=lenta(rel, 301))], relogio=rel)
    assert _estados(saidas) == {"a": ("falhou", "saude.tempo_esgotado")}
    assert saidas[0].resultado.vagas == ()
    assert saidas[0].duracao_ms == 301_000
    assert executor.PRAZO_ESCOPO_S == 300

    rel = RelogioFalso()
    saidas = await _rodar([ColetorFalso("a", acao=lenta(rel, 299))], relogio=rel)
    assert _estados(saidas) == {"a": ("ok", None)}


async def test_tempo_esgotado_cancela_a_coleta(monkeypatch: pytest.MonkeyPatch) -> None:
    cancelada = False

    async def presa(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        nonlocal cancelada
        try:
            await asyncio.Event().wait()  # nunca termina sozinha
        except asyncio.CancelledError:
            cancelada = True
            raise
        raise AssertionError("não chega aqui")

    monkeypatch.setattr(executor, "PRAZO_ESCOPO_S", 0)  # o corte vem na próxima volta do laço
    with anyio.fail_after(5):
        saidas = await _rodar([ColetorFalso("a", acao=presa), ColetorFalso("b")])
    assert _estados(saidas) == {"a": ("falhou", "saude.tempo_esgotado"), "b": ("ok", None)}
    assert cancelada


async def test_cancelar_rodar_nao_deixa_tarefa_solta() -> None:
    comecaram = {"a": asyncio.Event(), "b": asyncio.Event()}
    canceladas: list[str] = []

    def presa(chave: str) -> Acao:
        async def acao(escopo: str, http: HttpEducado) -> ResultadoEscopo:
            comecaram[chave].set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                canceladas.append(chave)
                raise
            raise AssertionError("não chega aqui")

        return acao

    antes = asyncio.all_tasks()
    tarefa = asyncio.create_task(
        _rodar([ColetorFalso("a", acao=presa("a")), ColetorFalso("b", acao=presa("b"))])
    )

    async def ambas() -> None:
        await comecaram["a"].wait()
        await comecaram["b"].wait()

    espera = asyncio.create_task(ambas())
    try:
        with anyio.fail_after(5):
            await asyncio.wait({tarefa, espera}, return_when=asyncio.FIRST_COMPLETED)
        assert not tarefa.done(), "rodar terminou sem esperar as coletas"
    finally:
        espera.cancel()
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa
    assert sorted(canceladas) == ["a", "b"]
    assert asyncio.all_tasks() == antes


async def test_erro_no_ao_terminar_escopo_sobe_e_cancela_as_outras() -> None:
    b_comecou = asyncio.Event()
    b_cancelada = False

    async def rapida(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        await b_comecou.wait()
        return ResultadoEscopo((), "ok", None, 0)

    async def presa(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        nonlocal b_cancelada
        b_comecou.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            b_cancelada = True
            raise
        raise AssertionError("não chega aqui")

    async def grava_e_quebra(saida: SaidaEscopo) -> None:
        raise RuntimeError("banco caiu")

    antes = asyncio.all_tasks()
    with anyio.fail_after(5), pytest.raises(ExceptionGroup) as erro:
        await _rodar(
            [ColetorFalso("a", acao=rapida), ColetorFalso("b", acao=presa)],
            ao_terminar=grava_e_quebra,
        )
    assert erro.group_contains(RuntimeError, match="banco caiu")
    assert b_cancelada
    assert asyncio.all_tasks() == antes


# --- liga/desliga, intervalo, orçamento ----------------------------------------------------------


async def test_fonte_desligada() -> None:
    a, b = ColetorFalso("a"), ColetorFalso("b")
    servidor = Servidor()
    saidas = await _rodar([a, b], servidor=servidor, ligadas={"b"})
    assert [s.fonte for s in saidas] == ["b"]
    assert a.contextos == [] and a.coletados == []
    assert servidor.hosts() == ["b.exemplo"]


async def test_intervalo_nao_cumprido_vira_no_limite() -> None:
    historico = HistoricoFalso(inicios={("a", None): AGORA - timedelta(minutes=30)})
    a = ColetorFalso("a", intervalo_min=60)
    saidas = await _rodar([a], historico=historico)
    assert _estados(saidas) == {"a": ("no_limite", "saude.intervalo")}
    assert saidas[0].resultado.pedidos == 0
    assert a.coletados == []
    assert ("a", None) in historico.perguntas  # conta do início da última execução com pedido

    historico = HistoricoFalso(inicios={("a", None): AGORA - timedelta(minutes=60)})
    assert _estados(await _rodar([ColetorFalso("a", intervalo_min=60)], historico=historico)) == {
        "a": ("ok", None)
    }


async def test_fonte_sem_intervalo_sempre_roda() -> None:
    historico = HistoricoFalso(inicios={("a", None): AGORA - timedelta(minutes=1)})
    a = ColetorFalso("a")
    saidas = await _rodar([a], historico=historico)
    assert _estados(saidas) == {"a": ("ok", None)}
    assert a.coletados == [""]


async def test_inicio_no_futuro_conta_como_vencido() -> None:
    historico = HistoricoFalso(inicios={("a", None): AGORA + timedelta(days=1)})
    a = ColetorFalso("a", intervalo_min=60)
    saidas = await _rodar([a], historico=historico)
    assert _estados(saidas) == {"a": ("ok", None)}
    assert a.coletados == [""]


async def test_orcamento_atende_os_escopos_mais_antigos() -> None:
    historico = HistoricoFalso(
        coletas={
            ("g", "e1.exemplo"): AGORA - timedelta(days=3),
            ("g", "e3.exemplo"): AGORA - timedelta(days=1),
        }  # e2 nunca foi coletado: é o mais antigo
    )
    servidor = Servidor()
    g = ColetorFalso("g", lista=("e1.exemplo", "e2.exemplo", "e3.exemplo"), max_pedidos=2)
    saidas = await _rodar([g], historico=historico, servidor=servidor)
    assert servidor.hosts() == ["e2.exemplo", "e1.exemplo"]
    assert _estados(saidas) == {
        "e1.exemplo": ("ok", None),
        "e2.exemplo": ("ok", None),
        "e3.exemplo": ("no_limite", "saude.orcamento"),
    }


def _microsoft_429(pedido: httpx.Request) -> httpx.Response:
    if pedido.url.host == MICROSOFT:
        return httpx.Response(429)
    return _uma_vaga(pedido)


def _eightfold() -> ColetorFalso:
    return ColetorFalso(
        "eightfold",
        lista=(MICROSOFT, "a.exemplo", "b.exemplo", "c.exemplo"),
        por_escopo={MICROSOFT: LimiteEscopo(intervalo_min=1440, espera_s=5, para_no_429=True)},
    )


async def test_limite_por_escopo_segura_so_aquele_escopo(monkeypatch: pytest.MonkeyPatch) -> None:
    rel = RelogioFalso()
    servidor = Servidor(_microsoft_429)
    cli = _cliente(servidor, rel)
    aberturas: list[dict[str, Any]] = []
    original = cli.escopo

    def espiao(**kw: Any) -> HttpDoEscopo:
        aberturas.append(kw)
        return original(**kw)

    monkeypatch.setattr(cli, "escopo", espiao)
    saidas = await _rodar([_eightfold()], servidor=servidor, relogio=rel, cliente=cli)
    assert _estados(saidas) == {
        MICROSOFT: ("no_limite", "saude.parou_429"),
        "a.exemplo": ("ok", None),
        "b.exemplo": ("ok", None),
        "c.exemplo": ("ok", None),
    }
    assert servidor.hosts().count(MICROSOFT) == 1
    assert next(s for s in saidas if s.escopo == MICROSOFT).resultado.pedidos == 1
    assert 30.0 not in rel.dormidas  # o 429 não espera
    assert [(k["espera_s"], k["para_no_429"]) for k in aberturas] == [
        (5, True),
        (1.0, False),
        (1.0, False),
        (1.0, False),
    ]


async def test_intervalo_do_escopo_segura_so_aquele_escopo() -> None:
    historico = HistoricoFalso(
        inicios={("eightfold", MICROSOFT): AGORA - timedelta(hours=2)}  # 1440 min não passaram
    )
    servidor = Servidor()
    saidas = await _rodar([_eightfold()], historico=historico, servidor=servidor)
    assert _estados(saidas) == {
        MICROSOFT: ("no_limite", "saude.intervalo"),
        "a.exemplo": ("ok", None),
        "b.exemplo": ("ok", None),
        "c.exemplo": ("ok", None),
    }
    assert MICROSOFT not in servidor.hosts()
    assert servidor.hosts() == ["a.exemplo", "b.exemplo", "c.exemplo"]


async def test_contexto_so_com_as_empresas_da_fonte() -> None:
    empresas = (
        Empresa(nome="Acme", fonte="greenhouse", identificador="acme"),
        Empresa(nome="Beta", fonte="lever", identificador="beta"),
    )
    g = ColetorFalso("greenhouse")
    await _rodar([g], ctx=ContextoColeta(empresas=empresas, termos=("dev",), paises=("BR",)))
    assert len(g.contextos) == 1
    assert [e.identificador for e in g.contextos[0].empresas] == ["acme"]
    assert g.contextos[0].termos == ("dev",) and g.contextos[0].paises == ("BR",)


# --- estados do escopo ----------------------------------------------------------------------------


def _zero(estado: Literal["ok", "sem_mudanca"]) -> Acao:
    async def acao(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        return ResultadoEscopo((), estado, None, 1)

    return acao


async def test_zero_inesperado() -> None:
    historico = HistoricoFalso(com_vagas={("a", "")})
    saidas = await _rodar([ColetorFalso("a", acao=_zero("ok"))], historico=historico)
    assert _estados(saidas) == {"a": ("parcial", "saude.zero_inesperado")}

    sem_historia = await _rodar([ColetorFalso("a", acao=_zero("ok"))])
    assert _estados(sem_historia) == {"a": ("ok", None)}
    sem_mudanca = await _rodar([ColetorFalso("a", acao=_zero("sem_mudanca"))], historico=historico)
    assert _estados(sem_mudanca) == {"a": ("sem_mudanca", None)}


async def test_escopo_sem_ocorrencia_aberta_nao_pede_condicional() -> None:
    leitor = LeitorFixo(
        {_url_pagina("a", e, 0): Validadores('"v1"', "Thu, 12 Nov 2026 10:00:00 GMT") for e in "xy"}
    )
    servidor = Servidor()
    historico = HistoricoFalso(abertas={("a", "y")})
    await _rodar(
        [ColetorFalso("a", lista=("x", "y"))], historico=historico, servidor=servidor, leitor=leitor
    )
    assert [p.url.path for p in servidor.pedidos] == ["/x", "/y"]
    por_escopo = {p.url.path: p.headers for p in servidor.pedidos}
    assert "If-None-Match" not in por_escopo["/x"]
    assert "If-Modified-Since" not in por_escopo["/x"]
    assert por_escopo["/y"]["If-None-Match"] == '"v1"'


async def test_pagina_200_no_meio_refaz_sem_condicional() -> None:
    leitor = LeitorFixo({_url_pagina("a", "", n): Validadores('"v"', None) for n in (0, 1)})

    def primeira_igual(pedido: httpx.Request) -> httpx.Response:
        if "If-None-Match" in pedido.headers and pedido.url.params["p"] == "0":
            return httpx.Response(304)
        return _uma_vaga(pedido)

    servidor = Servidor(primeira_igual)
    saidas = await _rodar([ColetorFalso("a", paginas=2)], servidor=servidor, leitor=leitor)
    assert ["If-None-Match" in p.headers for p in servidor.pedidos] == [True, True, False, False]
    assert _estados(saidas) == {"a": ("ok", None)}
    assert len(saidas[0].resultado.vagas) == 2
    assert saidas[0].resultado.pedidos == 4

    tudo_304 = Servidor(lambda p: httpx.Response(304))
    saidas = await _rodar([ColetorFalso("a", paginas=2)], servidor=tudo_304, leitor=leitor)
    assert _estados(saidas) == {"a": ("sem_mudanca", None)}
    assert len(tudo_304.pedidos) == 2


async def test_quatro_hosts_em_paralelo_um_pedido_por_host() -> None:
    em_voo: Counter[str] = Counter()
    maximo_host: Counter[str] = Counter()
    liberar = asyncio.Event()

    async def segura(pedido: httpx.Request) -> httpx.Response:
        host = pedido.url.host
        em_voo[host] += 1
        maximo_host[host] = max(maximo_host[host], em_voo[host])
        await liberar.wait()
        em_voo[host] -= 1
        return httpx.Response(200, json={"vagas": []})

    # seis fontes em cinco hosts: f5 divide o host com f0
    coletores = [ColetorFalso(f"f{n}", lista=(f"h{n}.exemplo",)) for n in range(5)]
    coletores.append(ColetorFalso("f5", lista=("h0.exemplo",)))
    tarefa = asyncio.create_task(_rodar(coletores, servidor=Servidor(segura)))
    try:
        for _ in range(200):  # só cede a vez ao laço: quem pode chegar ao servidor chega
            await asyncio.sleep(0)
        em_paralelo = em_voo.total()
    finally:
        liberar.set()
    with anyio.fail_after(5):
        saidas = await tarefa
    assert em_paralelo == 4
    assert max(maximo_host.values()) == 1
    assert len(saidas) == 6 and all(s.resultado.estado == "ok" for s in saidas)


def test_estado_da_fonte() -> None:
    assert estado_da_fonte(["falhou", "falhou"]) == "falhou"
    assert estado_da_fonte(["ok", "sem_mudanca"]) == "ok"
    assert estado_da_fonte(["ok", "falhou"]) == "parcial"
    assert estado_da_fonte(["ok", "parcial"]) == "parcial"
    assert estado_da_fonte(["no_limite", "no_limite"]) == "no_limite"
    assert estado_da_fonte(["no_limite", "ok"]) == "ok"
    assert estado_da_fonte(["no_limite", "falhou"]) == "falhou"


# --- URL listada (DR-70) -------------------------------------------------------------------------


async def test_url_listada_conhecida_conta_como_vista() -> None:
    conhecida, nova = "https://s.exemplo/v/1", "https://s.exemplo/v/2"
    s = ColetorFalso(
        "s", acao=_sitemap(UrlListada(conhecida), UrlListada(nova)), detalhe=_com_titulo
    )
    saidas = await _rodar([s], historico=HistoricoFalso(conhecidas={conhecida}))
    assert len(saidas) == 1
    assert saidas[0].urls_vistas == (conhecida,)
    assert s.detalhados == [nova]
    assert [v.url for v in saidas[0].resultado.vagas] == [nova]


async def test_url_conhecida_com_data_velha_conta_como_vista() -> None:
    url = "https://s.exemplo/v/1"
    s = ColetorFalso("s", acao=_sitemap(UrlListada(url, AGORA - timedelta(days=90))))
    saidas = await _rodar([s], historico=HistoricoFalso(conhecidas={url}))
    assert len(saidas) == 1
    assert saidas[0].urls_vistas == (url,)
    assert s.detalhados == []
    assert saidas[0].detalhes == 0


async def test_url_nova_com_data_velha_nao_vai_ao_detalhar() -> None:
    velha, recente, sem_data = (f"https://s.exemplo/v/{n}" for n in (31, 29, 0))
    s = ColetorFalso(
        "s",
        acao=_sitemap(
            UrlListada(sem_data),
            UrlListada(velha, AGORA - timedelta(days=31)),
            UrlListada(recente, AGORA - timedelta(days=29)),
        ),
        detalhe=_com_titulo,
    )
    saidas = await _rodar([s])
    assert len(saidas) == 1
    assert s.detalhados == [recente, sem_data]  # mais recente primeiro, sem data por último
    assert saidas[0].urls_vistas == ()
    assert saidas[0].detalhes == 2


async def test_url_listada_sem_titulo_nao_volta_ao_detalhar_por_30_dias() -> None:
    url = "https://s.exemplo/v/1"
    s = ColetorFalso("s", acao=_sitemap(UrlListada(url)))  # detalhar devolve None
    saidas = await _rodar([s])
    assert len(saidas) == 1
    assert saidas[0].urls_sem_detalhe == (url,)
    assert _estados(saidas) == {"s": ("ok", "saude.sem_detalhe_n:1")}
    assert saidas[0].resultado.vagas == ()

    s = ColetorFalso("s", acao=_sitemap(UrlListada(url)))
    saidas = await _rodar([s], historico=HistoricoFalso(recentes={url}))
    assert s.detalhados == []
    assert saidas[0].urls_sem_detalhe == ()
    assert _estados(saidas) == {"s": ("ok", None)}


async def test_url_listada_nova_so_grava_com_titulo_e_empresa() -> None:
    sem, com = "https://s.exemplo/v/sem", "https://s.exemplo/v/com"
    s = ColetorFalso(
        "s",
        acao=_sitemap(UrlListada(sem), UrlListada(com)),
        detalhe=lambda item: _com_titulo(item) if item.url == com else None,
    )
    saidas = await _rodar([s])
    assert sorted(s.detalhados) == sorted([sem, com])
    assert saidas[0].resultado.vagas == (_vaga(com, "s"),)
    assert all(isinstance(v, VagaColetada) for v in saidas[0].resultado.vagas)
    assert saidas[0].urls_sem_detalhe == (sem,)


def _sessenta() -> list[UrlListada]:
    # a URL n tem n horas de idade: as 50 mais recentes são n = 0..49
    return [
        UrlListada(f"https://s.exemplo/v/{n}", AGORA - timedelta(hours=n))
        for n in (*range(30, 60), *range(30))
    ]


async def test_url_listada_respeita_orcamento_e_ordem() -> None:
    s = ColetorFalso("s", acao=_sitemap(*_sessenta()), detalhe=_com_titulo)
    saidas = await _rodar([s])
    assert s.detalhados == [f"https://s.exemplo/v/{n}" for n in range(50)]
    assert saidas[0].detalhes == 50
    assert _estados(saidas) == {"s": ("ok", None)}
    assert len(saidas[0].resultado.vagas) == 50

    s = ColetorFalso("s", acao=_sitemap(*_sessenta()), detalhe=_com_titulo)
    saidas = await _rodar([s], max_detalhes=0)
    assert s.detalhados == []
    assert saidas[0].detalhes == 0
    assert _estados(saidas) == {"s": ("ok", None)}


async def test_orcamento_de_detalhes_vale_para_a_fonte_inteira() -> None:
    def trinta(escopo: str) -> list[UrlListada]:
        return [UrlListada(f"https://s.exemplo/{escopo}/{n}") for n in range(30)]

    async def acao(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        return ResultadoEscopo(tuple(trinta(escopo)), "ok", None, 1)

    s = ColetorFalso("s", lista=("e1", "e2"), acao=acao, detalhe=_com_titulo)
    saidas = await _rodar([s])
    assert [x.detalhes for x in saidas] == [30, 20]


async def test_detalhar_com_erro_pula_so_aquela_url() -> None:
    ruim, boa = "https://s.exemplo/v/ruim", "https://s.exemplo/v/boa"

    def detalhe(item: Item) -> VagaColetada:
        if item.url == ruim:
            raise ErroDeRede("404", 404)
        return _com_titulo(item)

    s = ColetorFalso("s", acao=_sitemap(UrlListada(ruim), UrlListada(boa)), detalhe=detalhe)
    saidas = await _rodar([s])
    # o erro aparece no motivo; o estado fica "ok", porque a lista veio inteira
    assert _estados(saidas) == {"s": ("ok", "saude.erro_de_rede")}
    assert [v.url for v in saidas[0].resultado.vagas] == [boa]
    assert saidas[0].urls_sem_detalhe == ()  # tenta de novo na próxima execução


async def test_detalhar_com_resposta_grande_aparece_no_motivo() -> None:
    def detalhe(item: Item) -> VagaColetada:
        raise RespostaGrande("página grande")

    s = ColetorFalso("s", acao=_sitemap(UrlListada("https://s.exemplo/v/1")), detalhe=detalhe)
    saidas = await _rodar([s])
    assert _estados(saidas) == {"s": ("ok", "saude.resposta_grande")}


async def test_detalhar_com_erro_inesperado_aparece_no_motivo() -> None:
    def detalhe(item: Item) -> VagaColetada:
        raise ValueError("html mudou")

    s = ColetorFalso("s", acao=_sitemap(UrlListada("https://s.exemplo/v/1")), detalhe=detalhe)
    saidas = await _rodar([s])
    assert _estados(saidas) == {"s": ("ok", "saude.excecao:ValueError")}


@pytest.mark.parametrize(
    ("erro", "motivo"),
    [
        (Bloqueio(), "saude.bloqueio"),
        (LimiteAtingido(), "saude.limite_atingido"),
        (OrcamentoGasto(), "saude.orcamento"),
        (Parou429(), "saude.parou_429"),
    ],
)
async def test_detalhar_parado_para_os_detalhes_da_fonte_inteira(
    erro: Exception, motivo: str
) -> None:
    def urls(escopo: str) -> tuple[UrlListada, ...]:
        return tuple(UrlListada(f"https://s.exemplo/{escopo}/{n}") for n in range(3))

    async def acao(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        return ResultadoEscopo(urls(escopo), "ok", None, 1)

    def detalhe(item: Item) -> VagaColetada | None:
        if item.url.endswith("/0"):
            return None  # sem detalhe; o erro de parada vem antes no motivo
        raise erro

    s = ColetorFalso("s", lista=("e1", "e2"), acao=acao, detalhe=detalhe)
    saidas = await _rodar([s])
    assert s.detalhados == ["https://s.exemplo/e1/0", "https://s.exemplo/e1/1"]
    assert _estados(saidas) == {"e1": ("ok", motivo), "e2": ("ok", None)}
    assert saidas[0].urls_sem_detalhe == ("https://s.exemplo/e1/0",)
    assert [x.detalhes for x in saidas] == [2, 0]


async def test_sem_detalhe_soma_com_o_do_coletor() -> None:
    async def acao(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        itens = (UrlListada("https://s.exemplo/v/1"),)
        return ResultadoEscopo(itens, "ok", "saude.sem_detalhe_n:2", 1)  # 2 que o molde descartou

    saidas = await _rodar([ColetorFalso("s", acao=acao)])
    assert _estados(saidas) == {"s": ("ok", "saude.sem_detalhe_n:3")}


class HistoricoQuebrado(HistoricoFalso):
    def __init__(self, metodo: str) -> None:
        super().__init__()
        self.metodo = metodo

    def _talvez_quebrar(self, metodo: str) -> None:
        if metodo == self.metodo:
            raise RuntimeError(f"banco caiu em {metodo}")

    def urls_conhecidas(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        self._talvez_quebrar("urls_conhecidas")
        return super().urls_conhecidas(fonte, urls)

    def detalhe_recente(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        self._talvez_quebrar("detalhe_recente")
        return super().detalhe_recente(fonte, urls)

    def tres_ultimas_ok_trouxeram_vagas(self, fonte: str, escopo: str) -> bool:
        self._talvez_quebrar("tres_ultimas_ok_trouxeram_vagas")
        return super().tres_ultimas_ok_trouxeram_vagas(fonte, escopo)

    def tem_ocorrencia_aberta(self, fonte: str, escopo: str) -> bool:
        self._talvez_quebrar("tem_ocorrencia_aberta")
        return super().tem_ocorrencia_aberta(fonte, escopo)


@pytest.mark.parametrize(
    "metodo",
    [
        "urls_conhecidas",
        "detalhe_recente",
        "tres_ultimas_ok_trouxeram_vagas",
        "tem_ocorrencia_aberta",
    ],
)
async def test_erro_do_historico_sobe_como_o_do_ao_terminar(metodo: str) -> None:
    # lista vazia: só assim o executor pergunta tres_ultimas_ok_trouxeram_vagas
    itens = (
        ()
        if metodo == "tres_ultimas_ok_trouxeram_vagas"
        else (UrlListada("https://s.exemplo/v/1"),)
    )
    s = ColetorFalso("s", acao=_sitemap(*itens), detalhe=_com_titulo)
    with anyio.fail_after(5), pytest.raises(ExceptionGroup) as erro:
        await _rodar([s], historico=HistoricoQuebrado(metodo))
    assert erro.group_contains(RuntimeError, match=f"banco caiu em {metodo}")


async def test_zero_inesperado_conta_urls_listadas() -> None:
    url = "https://s.exemplo/v/1"
    historico = HistoricoFalso(com_vagas={("s", "")}, conhecidas={url})
    saidas = await _rodar([ColetorFalso("s", acao=_sitemap(UrlListada(url)))], historico=historico)
    assert _estados(saidas) == {"s": ("ok", None)}
    assert saidas[0].resultado.vagas == ()

    historico = HistoricoFalso(com_vagas={("s", "")}, recentes={url})
    saidas = await _rodar([ColetorFalso("s", acao=_sitemap(UrlListada(url)))], historico=historico)
    assert _estados(saidas) == {"s": ("ok", None)}

    historico = HistoricoFalso(com_vagas={("s", "")})
    saidas = await _rodar([ColetorFalso("s", acao=_sitemap())], historico=historico)
    assert _estados(saidas) == {"s": ("parcial", "saude.zero_inesperado")}
