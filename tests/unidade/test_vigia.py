"""Vigia semanal das fontes (T84, ADR 0018): coletor e API do GitHub falsos, sem rede."""

import importlib.util
import json
import re
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
    juntar_paginas,
)
from jobot.nucleo.http import ClienteEducado, ErroDeRede, HttpEducado, OrcamentoGasto, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada

pytestmark = pytest.mark.anyio

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github" / "workflows" / "vigia.yml"
CI = RAIZ / ".github" / "workflows" / "ci.yml"
CATALOGOS = [RAIZ / "src" / "jobot" / "painel" / "i18n" / i / "comum.json" for i in ("pt", "en")]
BOT = "github-actions[bot]"
PESSOA = "alguem"


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vigia_script", RAIZ / "scripts/vigia.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo  # o dataclass procura o módulo pelo nome
    spec.loader.exec_module(modulo)
    return modulo


vigia = _carregar()


# --- coletor e cliente das fontes, falsos -------------------------------------------------


def _vaga(url: str = "https://falsa.exemplo/v/1", **campos: str) -> VagaColetada:
    base = {"titulo": "Dev", "empresa": "Acme"} | campos
    return VagaColetada(
        fonte="falsa",
        escopo="",
        url=url,
        titulo=base["titulo"],
        empresa=base["empresa"],
        descricao_formato="texto",
    )


def _urls(n: int) -> tuple[UrlListada, ...]:
    """`n` URLs com `atualizada_em` crescente: a última é a mais recente."""
    inicio = datetime(2026, 11, 1, tzinfo=UTC)
    return tuple(
        UrlListada(f"https://falsa.exemplo/u/{i}", inicio + timedelta(hours=i)) for i in range(n)
    )


Acao = Callable[[str, HttpEducado], Awaitable[ResultadoEscopo]]
Detalhe = Callable[[Item, HttpEducado], Awaitable[VagaColetada | None]]


def _fixo(ctx: ContextoColeta) -> Sequence[str]:
    return [""]


def _por_empresa(ctx: ContextoColeta) -> Sequence[str]:
    return [e.identificador for e in ctx.empresas]


@dataclass
class ColetorFalso:
    chave: str = "falsa"
    lista: Callable[[ContextoColeta], Sequence[str]] = _fixo
    acao: Acao | None = None
    detalhe: Detalhe | None = None
    nome: str = "Falsa"
    leva: Literal["A", "B"] = "A"
    hosts: tuple[str, ...] = ()
    credito_obrigatorio: bool = False
    intervalo_min: int | None = None
    max_pedidos: int | None = None
    espera_s: float = 1.0
    por_escopo: Mapping[str, LimiteEscopo] = field(default_factory=dict)
    coletados: list[str] = field(default_factory=list)
    detalhados: list[str] = field(default_factory=list)

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return self.lista(ctx)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        self.coletados.append(escopo)
        assert self.acao is not None
        return await self.acao(escopo, http)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        self.detalhados.append(item.url)
        return None if self.detalhe is None else await self.detalhe(item, http)

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        return {}


def _listar(
    itens: Sequence[Item] = (),
    *,
    pedidos: int = 1,
    estado: str = "ok",
    motivo: str | None = None,
) -> Acao:
    async def acao(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        for n in range(pedidos):
            await http.pedir("GET", f"https://falsa.exemplo/lista/{n}")
        return ResultadoEscopo(tuple(itens), estado, motivo, pedidos)  # type: ignore[arg-type]

    return acao


class Servidor:
    def __init__(self, status: int = 200) -> None:
        self.pedidos: list[httpx.Request] = []
        self.status = status

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        return httpx.Response(self.status, json={})


class SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


def _cliente(servidor: Servidor) -> ClienteEducado:
    return ClienteEducado(httpx.MockTransport(servidor), RelogioFalso(), SemValidadores(), "9.9.9")


async def _rodar(
    *coletores: ColetorFalso,
    servidor: Servidor | None = None,
    empresas: Sequence[Empresa] = (),
) -> list[Any]:
    cliente = _cliente(servidor or Servidor())
    try:
        resultados: list[Any] = await vigia.rodar(
            cliente,
            RelogioFalso(),
            coletores={c.chave: c for c in coletores},
            empresas=empresas,
        )
    finally:
        await cliente.fechar()
    return resultados


def _um(resultados: list[Any], fonte: str = "falsa") -> Any:
    achados = [r for r in resultados if r.fonte == fonte]
    assert len(achados) == 1
    return achados[0]


# --- API do GitHub, falsa -------------------------------------------------------------------

ANTES = "2026-11-02T10:00:00Z"
DEPOIS = "2026-11-09T10:00:00Z"


def _issue(
    n: int,
    fonte: str = "falsa",
    *,
    autor: str = BOT,
    rotulo: bool = True,
    marca: bool = True,
    estado: str = "open",
    pr: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "number": n,
        "state": estado,
        "user": {"login": autor},
        "labels": [{"name": "fonte-quebrada"}] if rotulo else [],
        "body": f"<!-- vigia:{fonte} -->\nquebrou" if marca else "quebrou",
    }
    if pr:
        item["pull_request"] = {"url": "https://api.github.com/x"}
    return item


@dataclass
class ApiFalsa:
    lista: list[dict[str, Any]] = field(default_factory=list)
    eventos_de: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    comentarios_de: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    criadas: list[tuple[str, str]] = field(default_factory=list)
    edicoes: list[tuple[int, dict[str, str]]] = field(default_factory=list)
    comentados: list[tuple[int, str]] = field(default_factory=list)
    agora: str = "2026-11-16T06:30:00Z"

    async def issues(self) -> list[dict[str, Any]]:
        return [dict(i) for i in self.lista]

    async def eventos(self, n: int) -> list[dict[str, Any]]:
        return list(self.eventos_de.get(n, []))

    async def comentarios(self, n: int) -> list[dict[str, Any]]:
        return list(self.comentarios_de.get(n, []))

    async def criar(self, titulo: str, corpo: str) -> None:
        self.criadas.append((titulo, corpo))
        novo = max((i["number"] for i in self.lista), default=0) + 1
        self.lista.append(
            {
                "number": novo,
                "state": "open",
                "user": {"login": BOT},
                "labels": [{"name": "fonte-quebrada"}],
                "body": corpo,
            }
        )

    async def editar(self, n: int, campos: Mapping[str, str]) -> None:
        self.edicoes.append((n, dict(campos)))
        issue = next(i for i in self.lista if i["number"] == n)
        if campos.get("state") == "closed" and issue["state"] == "open":
            self.eventos_de.setdefault(n, []).append(_evento("closed", BOT, self.agora))
        issue.update({"state": campos.get("state", issue["state"])})
        if "body" in campos:
            issue["body"] = campos["body"]

    async def comentar(self, n: int, corpo: str) -> None:
        self.comentados.append((n, corpo))
        self.comentarios_de.setdefault(n, []).append(_comentario(BOT, corpo, self.agora))

    def tocadas(self) -> set[int]:
        return {n for n, _ in self.edicoes} | {n for n, _ in self.comentados}


def _evento(nome: str, ator: str, quando: str) -> dict[str, Any]:
    return {"event": nome, "actor": {"login": ator}, "created_at": quando}


def _comentario(autor: str, corpo: str, quando: str) -> dict[str, Any]:
    return {"user": {"login": autor}, "body": corpo, "created_at": quando}


def _r(**campos: Any) -> Any:
    return vigia.Resultado(**({"fonte": "falsa", "estado": "ok"} | campos))


QUEBRADA = {"estado": "falhou", "motivo": "saude.formato_mudou"}
VOLTOU = {"estado": "ok", "listadas": 3, "vagas": 3}


def _reaberturas(api: ApiFalsa) -> list[int]:
    return [n for n, c in api.edicoes if c.get("state") == "open"]


# --- quais fontes e qual contexto -----------------------------------------------------------


def test_fontes_vigiadas_exclui_eureca_abler_e_gupy(monkeypatch: pytest.MonkeyPatch) -> None:
    assert vigia.FONTES_FORA == {"eureca", "abler", "gupy"}
    falsos = {c: ColetorFalso(chave=c) for c in ("eureca", "abler", "gupy", "remotive", "lever")}
    monkeypatch.setattr(vigia, "descobrir", lambda: falsos)
    assert vigia.fontes_vigiadas() == ["lever", "remotive"]


async def test_rodar_nao_roda_eureca_abler_nem_gupy() -> None:
    fora = [ColetorFalso(chave=c, acao=_listar(())) for c in ("eureca", "abler", "gupy")]
    dentro = ColetorFalso(acao=_listar(()))
    resultados = await _rodar(*fora, dentro)
    assert [r.fonte for r in resultados] == ["falsa"]
    assert all(c.coletados == [] for c in fora)


def test_fontes_vigiadas_do_registro_real() -> None:
    vigiadas = vigia.fontes_vigiadas()
    assert "remotive" in vigiadas and "greenhouse" in vigiadas
    assert "gupy" not in vigiadas


def test_contexto_fixo_usa_a_primeira_empresa_de_cada_fonte() -> None:
    gh1 = Empresa(nome="Um", fonte="greenhouse", identificador="um")
    gh2 = Empresa(nome="Dois", fonte="greenhouse", identificador="dois")
    lv = Empresa(nome="Tres", fonte="lever", identificador="tres")
    empresas = [gh1, lv, gh2]
    contextos = {f: vigia.contexto_da_fonte(f, empresas) for f in ("greenhouse", "lever", "x")}
    assert tuple(contextos["greenhouse"].empresas) == (gh1,)
    assert tuple(contextos["lever"].empresas) == (lv,)
    assert tuple(contextos["x"].empresas) == ()
    for ctx in contextos.values():
        assert tuple(ctx.termos) == ("developer",)
        assert tuple(ctx.paises) == ("BR",)


def test_escopo_unico_e_o_que_nao_depende_do_contexto() -> None:
    assert vigia.escopo_unico(ColetorFalso(lista=_fixo)) is True
    assert vigia.escopo_unico(ColetorFalso(lista=_por_empresa)) is False
    assert vigia.escopo_unico(ColetorFalso(lista=lambda ctx: ["a", "b"])) is False


async def test_vigia_pega_o_escopo_do_escopos_na_mesma_instancia() -> None:
    @dataclass
    class ComEstado(ColetorFalso):
        rodada: int = 0

        def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
            self.rodada += 1  # cada chamada inventa um escopo novo, guardado na instância
            return [f"escopo-{self.rodada}"]

        async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
            if escopo != f"escopo-{self.rodada}":
                raise AssertionError("escopo montado à mão ou de outra instância")
            return ResultadoEscopo((_vaga(),), "ok", None, 0)

    r = _um(await _rodar(ComEstado()))
    assert (r.estado, r.motivo, r.listadas) == ("ok", None, 1)


async def test_fonte_sem_escopo_fica_nao_vigiada() -> None:
    servidor = Servidor()
    coletor = ColetorFalso(lista=lambda ctx: [], acao=_listar([_vaga()]))
    r = _um(await _rodar(coletor, servidor=servidor))
    assert r.estado == "nao_vigiada"
    assert servidor.pedidos == [] and coletor.coletados == []
    assert "não vigiada" in vigia.resumo([r])
    api = ApiFalsa(lista=[_issue(7)])
    await vigia.atualizar_issues([r], api)
    assert api.criadas == [] and api.edicoes == [] and api.comentados == []


# --- classificação --------------------------------------------------------------------------


def test_toda_chave_saude_do_catalogo_esta_classificada_no_vigia() -> None:
    assert vigia.ABRE_ISSUE == {"saude.formato_mudou", "saude.excecao"}
    assert not vigia.ABRE_ISSUE & vigia.SO_RESUMO
    for caminho in CATALOGOS:
        catalogo = json.loads(caminho.read_text(encoding="utf-8"))
        chaves = {c for c in catalogo if c.startswith("saude.")}
        assert chaves, caminho
        assert chaves == vigia.ABRE_ISSUE | vigia.SO_RESUMO, caminho


CASOS_QUEBRA = [
    pytest.param({"estado": "falhou", "motivo": "saude.formato_mudou"}, True, id="falhou-formato"),
    pytest.param({"estado": "parcial", "motivo": "saude.formato_mudou"}, True, id="parcial-fmt"),
    pytest.param({"estado": "falhou", "motivo": "saude.excecao:KeyError"}, True, id="falhou-exc"),
    pytest.param({"estado": "ok", "motivo": "saude.excecao:KeyError"}, False, id="ok-excecao"),
    pytest.param({"estado": "parcial", "motivo": "saude.excecao:X", "listadas": 2}, False, id="p"),
    pytest.param({"estado": "no_limite", "motivo": "saude.orcamento"}, False, id="no_limite"),
    pytest.param({"estado": "ok", "escopo_unico": True}, True, id="zero-em-fonte-unica"),
    pytest.param({"estado": "ok", "escopo_unico": False}, False, id="zero-em-outra-fonte"),
    pytest.param({"estado": "ok", "escopo_unico": True, "listadas": 1}, False, id="unica-com-1"),
    pytest.param({"estado": "nao_vigiada", "escopo_unico": True}, False, id="nao-vigiada"),
]


@pytest.mark.parametrize(("campos", "abre"), CASOS_QUEBRA)
def test_abrem_issue_formato_mudou_excecao_e_zero_em_fonte_unica(
    campos: dict[str, Any], abre: bool
) -> None:
    assert vigia.quebrou(_r(**campos)) is abre


@pytest.mark.parametrize("estado", ["falhou", "parcial", "no_limite"])
def test_chaves_so_resumo_nao_abrem_issue(estado: str) -> None:
    assert len(vigia.SO_RESUMO) == 14
    for chave in sorted(vigia.SO_RESUMO):
        assert vigia.quebrou(_r(estado=estado, motivo=chave, listadas=1)) is False, chave


def test_motivo_com_parametro_e_classificado_pela_chave() -> None:
    assert vigia.quebrou(_r(estado="falhou", motivo="saude.excecao:KeyError")) is True
    assert vigia.quebrou(_r(estado="parcial", motivo="saude.sem_detalhe_n:3", listadas=3)) is False
    assert vigia.quebrou(_r(estado="parcial", motivo="saude.formato_mudou:2", listadas=3)) is True


async def test_bloqueio_nao_abre_issue() -> None:
    async def lista(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        async def paginas() -> Any:
            await http.pedir("GET", "https://falsa.exemplo/lista")
            yield ()

        return await juntar_paginas(http, paginas())

    servidor = Servidor(status=403)
    r = _um(await _rodar(ColetorFalso(acao=lista), servidor=servidor))
    assert (r.estado, r.motivo) == ("falhou", "saude.bloqueio")
    assert len(servidor.pedidos) == 1
    api = ApiFalsa()
    await vigia.atualizar_issues([r], api)
    assert api.criadas == []


# --- orçamento e detalhes -------------------------------------------------------------------


async def test_respeita_orcamento_de_pedidos_por_fonte() -> None:
    assert vigia.VIGIA_MAX_PEDIDOS == 5

    async def sem_fim(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        async def paginas() -> Any:
            n = 0
            while True:
                await http.pedir("GET", f"https://{escopo or 'livre'}.exemplo/{n}")
                n += 1
                yield (_vaga(f"https://falsa.exemplo/v/{escopo}{n}"),)

        return await juntar_paginas(http, paginas())

    servidor = Servidor()
    livre = ColetorFalso(chave="livre", acao=sem_fim)
    curta = ColetorFalso(chave="curta", acao=sem_fim, lista=lambda ctx: ["curta"], max_pedidos=3)
    resultados = await _rodar(livre, curta, servidor=servidor)
    assert _um(resultados, "livre").pedidos == 5
    assert _um(resultados, "curta").pedidos == 3  # o limite da fonte vale quando é menor
    hosts = [p.url.host for p in servidor.pedidos]
    assert hosts.count("livre.exemplo") == 5 and hosts.count("curta.exemplo") == 3
    assert _um(resultados, "livre").motivo == "saude.orcamento"


async def _uma_vaga_por_pedido(item: Item, http: HttpEducado) -> VagaColetada:
    await http.pedir("GET", item.url)
    return _vaga(item.url)


async def test_sitemap_com_orcamento_de_5_nao_abre_issue() -> None:
    assert vigia.VIGIA_MAX_DETALHES == 2
    urls = _urls(20)
    coletor = ColetorFalso(acao=_listar(urls, pedidos=4), detalhe=_uma_vaga_por_pedido)
    r = _um(await _rodar(coletor))
    assert coletor.detalhados == [urls[19].url, urls[18].url]  # as mais recentes primeiro
    assert (r.estado, r.motivo, r.listadas, r.vagas) == ("ok", "saude.orcamento", 20, 1)
    assert r.pedidos == 5
    assert vigia.quebrou(r) is False
    api = ApiFalsa()
    await vigia.atualizar_issues([r], api)
    assert api.criadas == []


async def test_detalhar_com_erro_comum_mantem_o_estado_do_coletar() -> None:
    urls = _urls(3)

    async def detalhe(item: Item, http: HttpEducado) -> VagaColetada:
        if item.url == urls[2].url:
            raise KeyError("x")
        return _vaga(item.url)

    coletor = ColetorFalso(acao=_listar(urls), detalhe=detalhe)
    r = _um(await _rodar(coletor))
    assert coletor.detalhados == [urls[2].url, urls[1].url]
    assert (r.estado, r.motivo, r.vagas) == ("ok", "saude.excecao:KeyError", 1)
    assert vigia.quebrou(r) is False


async def test_zero_vagas_conta_os_itens_listados() -> None:
    varias = ColetorFalso(lista=_por_empresa, acao=_listar(_urls(3)))
    empresa = Empresa(nome="Acme", fonte="falsa", identificador="acme")
    r = _um(await _rodar(varias, empresas=[empresa]))
    assert r.escopo_unico is False
    assert (r.estado, r.listadas, r.vagas) == ("ok", 3, 0)
    assert len(varias.detalhados) == 2
    assert vigia.quebrou(r) is False
    vazia = _um(await _rodar(ColetorFalso(acao=_listar(()))))
    assert vazia.escopo_unico is True and vazia.listadas == 0
    assert vigia.quebrou(vazia) is True


def _detalhe_em_sequencia(*passos: Callable[[Item, HttpEducado], Awaitable[Any]]) -> Detalhe:
    feitos: list[int] = []

    async def detalhe(item: Item, http: HttpEducado) -> VagaColetada | None:
        feitos.append(1)
        resultado: VagaColetada | None = await passos[len(feitos) - 1](item, http)
        return resultado

    return detalhe


async def _levanta_segredo(item: Item, http: HttpEducado) -> None:
    raise KeyError("segredo")


async def _nenhuma(item: Item, http: HttpEducado) -> None:
    return None


async def _uma(item: Item, http: HttpEducado) -> VagaColetada:
    return _vaga(item.url)


async def _orcamento(item: Item, http: HttpEducado) -> None:
    raise OrcamentoGasto("5 pedidos já feitos")


async def _erro_de_rede(item: Item, http: HttpEducado) -> None:
    raise ErroDeRede("caiu", status=None)


CASOS_DETALHE = [
    pytest.param(_fixo, _nenhuma, True, id="unica-erro-e-none-abre"),
    pytest.param(_fixo, _uma, False, id="segunda-traz-vaga"),
    pytest.param(_fixo, _orcamento, False, id="segunda-bate-no-orcamento"),
    pytest.param(_por_empresa, _nenhuma, False, id="fonte-que-nao-e-unica"),
    pytest.param(_fixo, _erro_de_rede, False, id="segunda-com-erro-de-rede"),
]


@pytest.mark.parametrize(("lista", "segundo", "abre"), CASOS_DETALHE)
async def test_detalhe_quebrado_em_fonte_unica_abre_issue(
    lista: Callable[[ContextoColeta], Sequence[str]], segundo: Detalhe, abre: bool
) -> None:
    coletor = ColetorFalso(
        lista=lista,
        acao=_listar(_urls(5)),
        detalhe=_detalhe_em_sequencia(_levanta_segredo, segundo),
    )
    empresa = Empresa(nome="Acme", fonte="falsa", identificador="acme")
    r = _um(await _rodar(coletor, empresas=[empresa]))
    assert len(coletor.detalhados) == 2
    assert r.estado == "ok"
    assert vigia.quebrou(r) is abre
    api = ApiFalsa()
    await vigia.atualizar_issues([r], api)
    assert len(api.criadas) == int(abre)
    if abre:
        _, corpo = api.criadas[0]
        assert "KeyError" in corpo and "segredo" not in corpo


async def test_detalhe_quebrado_com_vaga_ja_coletada_nao_abre_issue() -> None:
    coletor = ColetorFalso(
        acao=_listar((_vaga("https://falsa.exemplo/pronta"), *_urls(5))),
        detalhe=_detalhe_em_sequencia(_levanta_segredo, _nenhuma),
    )
    r = _um(await _rodar(coletor))
    assert len(coletor.detalhados) == 2
    assert (r.escopo_unico, r.vagas) == (True, 1)
    assert r.detalhe_quebrado is False
    assert vigia.quebrou(r) is False


async def test_url_repetida_vale_a_primeira_como_no_executor() -> None:
    velha, nova = _urls(2)
    repetida = UrlListada(velha.url, datetime(2026, 11, 2, tzinfo=UTC))  # a mais recente
    coletor = ColetorFalso(acao=_listar((velha, nova, repetida)))
    r = _um(await _rodar(coletor))
    assert coletor.detalhados == [nova.url, velha.url]
    assert r.listadas == 3


async def test_excecao_do_coletor_vira_falhou_e_abre_issue_so_com_o_tipo() -> None:
    async def quebra(escopo: str, http: HttpEducado) -> ResultadoEscopo:
        raise KeyError("segredo")

    resultados = await _rodar(
        ColetorFalso(chave="a", acao=quebra), ColetorFalso(chave="b", acao=_listar([_vaga()]))
    )
    a, b = _um(resultados, "a"), _um(resultados, "b")
    assert (a.estado, a.motivo) == ("falhou", "saude.excecao:KeyError")
    assert (b.estado, b.listadas) == ("ok", 1)  # a fonte seguinte roda
    assert "segredo" not in vigia.resumo(resultados)
    api = ApiFalsa()
    await vigia.atualizar_issues(resultados, api)
    assert len(api.criadas) == 1
    titulo, corpo = api.criadas[0]
    assert "<!-- vigia:a -->" in corpo
    assert "KeyError" in corpo and "segredo" not in corpo + titulo


async def test_excecao_no_escopos_vira_falhou() -> None:
    def quebra(ctx: ContextoColeta) -> Sequence[str]:
        raise TypeError("segredo")

    r = _um(await _rodar(ColetorFalso(lista=quebra, acao=_listar())))
    assert (r.estado, r.motivo) == ("falhou", "saude.excecao:TypeError")
    assert vigia.quebrou(r) is True


async def test_corpo_da_issue_nao_tem_conteudo_de_vaga() -> None:
    vaga = _vaga("https://falsa.exemplo/vaga-secreta", titulo="Cargo Secreto", empresa="Oculta SA")
    coletor = ColetorFalso(acao=_listar([vaga], estado="parcial", motivo="saude.formato_mudou"))
    r = _um(await _rodar(coletor))
    api = ApiFalsa()
    await vigia.atualizar_issues([r], api)
    assert len(api.criadas) == 1
    texto = "".join(api.criadas[0])
    for proibido in ("vaga-secreta", "Cargo Secreto", "Oculta SA"):
        assert proibido not in texto
    assert "saude.formato_mudou" in texto


# --- issues ---------------------------------------------------------------------------------


async def test_issue_nova_tem_rotulo_e_marca() -> None:
    assert (vigia.ROTULO, vigia.AUTOR_DO_VIGIA) == ("fonte-quebrada", BOT)
    api = ApiFalsa()
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert len(api.criadas) == 1
    titulo, corpo = api.criadas[0]
    assert corpo.startswith("<!-- vigia:falsa -->")
    assert "falsa" in titulo


async def test_issue_existente_e_atualizada_e_fechada_quando_volta() -> None:
    api = ApiFalsa(lista=[_issue(3)])
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert api.criadas == []
    assert len(api.edicoes) == 1 and api.edicoes[0][0] == 3
    assert "saude.formato_mudou" in api.edicoes[0][1]["body"]
    assert "state" not in api.edicoes[0][1]
    await vigia.atualizar_issues([_r(**VOLTOU)], api)
    assert api.comentados == [(3, api.comentados[0][1])]
    assert "<!-- vigia:falsa:voltou -->" in api.comentados[0][1]
    assert api.edicoes[-1] == (3, {"state": "closed"})
    await vigia.atualizar_issues([_r(**VOLTOU)], api)  # já fechada: nada mais
    assert len(api.comentados) == 1 and len(api.edicoes) == 2


async def _issue_de_detalhe_quebrado() -> ApiFalsa:
    """Abre a issue de verdade: uma vigia com o detalhe quebrado em fonte de escopo único."""
    quebrado = ColetorFalso(
        acao=_listar(_urls(5)), detalhe=_detalhe_em_sequencia(_levanta_segredo, _nenhuma)
    )
    r = _um(await _rodar(quebrado))
    assert r.detalhe_quebrado is True
    api = ApiFalsa()
    await vigia.atualizar_issues([r], api)
    assert len(api.criadas) == 1 and api.lista[0]["state"] == "open"
    return api


@pytest.mark.parametrize(
    "coletor",
    [
        pytest.param(
            ColetorFalso(acao=_listar(_urls(5)), detalhe=_orcamento), id="parou-por-orcamento"
        ),
        pytest.param(
            ColetorFalso(acao=_listar((_vaga("https://falsa.exemplo/pronta"),))),
            id="sem-vaga-para-detalhar",
        ),
    ],
)
async def test_detalhe_nao_conferido_nao_fecha_issue(coletor: ColetorFalso) -> None:
    api = await _issue_de_detalhe_quebrado()
    r = _um(await _rodar(coletor))
    assert r.estado == "ok" and vigia.quebrou(r) is False
    await vigia.atualizar_issues([r], api)
    assert api.lista[0]["state"] == "open"
    assert api.comentados == [] and [c for _, c in api.edicoes if "state" in c] == []


async def test_detalhe_conferido_e_bom_fecha_issue() -> None:
    api = await _issue_de_detalhe_quebrado()
    bom = ColetorFalso(acao=_listar(_urls(5)), detalhe=_uma)
    r = _um(await _rodar(bom))
    assert len(bom.detalhados) == 2 and vigia.quebrou(r) is False
    await vigia.atualizar_issues([r], api)
    assert "<!-- vigia:falsa:voltou -->" in api.comentados[0][1]
    assert api.edicoes[-1] == (1, {"state": "closed"})


async def test_bloqueio_nao_fecha_a_issue_aberta() -> None:
    api = ApiFalsa(lista=[_issue(3)])
    await vigia.atualizar_issues([_r(estado="falhou", motivo="saude.bloqueio")], api)
    assert api.tocadas() == set() and api.criadas == []


async def test_issue_fechada_pelo_vigia_reabre_se_quebrar_de_novo() -> None:
    api = ApiFalsa(
        lista=[_issue(4, estado="closed")],
        eventos_de={4: [_evento("closed", PESSOA, ANTES), _evento("closed", BOT, DEPOIS)]},
    )
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert _reaberturas(api) == [4]
    assert api.criadas == []


async def test_issue_fechada_por_pessoa_ganha_um_so_comentario_e_nao_reabre() -> None:
    api = ApiFalsa(
        lista=[_issue(5, estado="closed")],
        eventos_de={5: [_evento("closed", BOT, ANTES), _evento("closed", PESSOA, DEPOIS)]},
    )
    for _ in range(2):
        await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert _reaberturas(api) == [] and api.criadas == []
    assert len(api.comentados) == 1
    assert "<!-- vigia:falsa:visto -->" in api.comentados[0][1]


async def test_visto_antigo_nao_vale_depois_de_novo_fechamento() -> None:
    visto = _comentario(BOT, "<!-- vigia:falsa:visto -->", ANTES)
    api = ApiFalsa(
        lista=[_issue(5, estado="closed")],
        eventos_de={5: [_evento("closed", PESSOA, DEPOIS)]},
        comentarios_de={5: [visto]},
    )
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert len(api.comentados) == 1


async def test_issue_reaberta_e_fechada_por_pessoa_nao_reabre_de_novo() -> None:
    api = ApiFalsa(
        lista=[_issue(6, estado="closed")],
        eventos_de={
            6: [
                _evento("closed", BOT, "2026-11-02T06:30:00Z"),
                _evento("reopened", BOT, "2026-11-09T06:30:00Z"),
                _evento("closed", PESSOA, "2026-11-10T09:00:00Z"),
            ]
        },
        comentarios_de={6: [_comentario(BOT, "<!-- vigia:falsa:voltou -->", ANTES)]},
    )
    for _ in range(2):
        await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert _reaberturas(api) == [] and api.criadas == []
    assert len(api.comentados) == 1
    assert "<!-- vigia:falsa:visto -->" in api.comentados[0][1]


async def test_issue_sem_a_marca_nao_e_tocada() -> None:
    api = ApiFalsa(lista=[_issue(8, marca=False)])
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert 8 not in api.tocadas()
    assert len(api.criadas) == 1


async def test_issue_sem_a_marca_nao_fecha_quando_volta() -> None:
    api = ApiFalsa(lista=[_issue(8, marca=False), _issue(9, rotulo=False)])
    await vigia.atualizar_issues([_r(**VOLTOU)], api)
    assert api.tocadas() == set()


async def test_issue_com_a_marca_escrita_por_pessoa_nao_e_tocada_nem_impede_a_issue_real() -> None:
    api = ApiFalsa(lista=[_issue(9, autor=PESSOA)])
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert 9 not in api.tocadas()
    assert len(api.criadas) == 1
    pessoa = ApiFalsa(lista=[_issue(9, autor=PESSOA)])
    await vigia.atualizar_issues([_r(**VOLTOU)], pessoa)
    assert pessoa.tocadas() == set()


async def test_comentario_voltou_de_pessoa_nao_conta() -> None:
    api = ApiFalsa(
        lista=[_issue(10, estado="closed")],
        eventos_de={10: [_evento("closed", PESSOA, ANTES)]},
        comentarios_de={10: [_comentario(PESSOA, "<!-- vigia:falsa:voltou -->", DEPOIS)]},
    )
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert _reaberturas(api) == [] and api.criadas == []


async def test_visto_de_pessoa_nao_conta() -> None:
    api = ApiFalsa(
        lista=[_issue(10, estado="closed")],
        eventos_de={10: [_evento("closed", PESSOA, ANTES)]},
        comentarios_de={10: [_comentario(PESSOA, "<!-- vigia:falsa:visto -->", DEPOIS)]},
    )
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert len(api.comentados) == 1


async def test_pull_request_na_listagem_e_ignorado() -> None:
    api = ApiFalsa(lista=[_issue(11, pr=True)])
    await vigia.atualizar_issues([_r(**QUEBRADA)], api)
    assert 11 not in api.tocadas()
    assert len(api.criadas) == 1


# --- API real do GitHub (por MockTransport) e workflow --------------------------------------


class GithubFalso:
    def __init__(self, paginas: Mapping[str, tuple[list[Any], str | None]] | None = None) -> None:
        self.pedidos: list[httpx.Request] = []
        self.paginas = dict(paginas or {})

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if pedido.method == "GET":
            corpo, proxima = self.paginas.get(str(pedido.url), ([], None))
            cabecalhos = {"Link": f'<{proxima}>; rel="next"'} if proxima else {}
            return httpx.Response(200, json=corpo, headers=cabecalhos)
        return httpx.Response(201, json={})


async def test_token_so_vai_para_api_github() -> None:
    servidor = Servidor()
    coletor = ColetorFalso(acao=_listar(pedidos=2, estado="falhou", motivo="saude.formato_mudou"))
    resultados = await _rodar(coletor, servidor=servidor)
    github = GithubFalso()
    api = vigia.ApiGithub("tok-123", "dono/repo", transporte=httpx.MockTransport(github))
    try:
        await vigia.atualizar_issues(resultados, api)
    finally:
        await api.fechar()
    assert len(servidor.pedidos) == 2
    for pedido in servidor.pedidos:
        assert "authorization" not in pedido.headers
        assert "tok-123" not in str(pedido.headers)
    assert [p.method for p in github.pedidos] == ["GET", "POST"]
    for pedido in github.pedidos:
        assert pedido.url.scheme == "https" and pedido.url.host == "api.github.com"
        assert pedido.headers["authorization"] == "Bearer tok-123"
    criada = json.loads(github.pedidos[1].content)
    assert github.pedidos[1].url.path == "/repos/dono/repo/issues"
    assert criada["labels"] == ["fonte-quebrada"]
    assert "<!-- vigia:falsa -->" in criada["body"]


async def test_api_segue_a_proxima_pagina_so_dentro_da_api_github() -> None:
    base = "https://api.github.com/repos/dono/repo/issues/1/events"
    p1 = f"{base}?per_page=100"
    p2 = f"{base}?per_page=100&page=2"
    github = GithubFalso(
        {
            p1: ([_evento("closed", BOT, ANTES)], p2),
            p2: ([_evento("closed", PESSOA, DEPOIS)], "https://outro.exemplo/roubar"),
        }
    )
    api = vigia.ApiGithub("tok-123", "dono/repo", transporte=httpx.MockTransport(github))
    try:
        with pytest.raises(ValueError):
            await api.eventos(1)
    finally:
        await api.fechar()
    assert [str(p.url) for p in github.pedidos] == [p1, p2]


async def test_api_lista_issues_so_por_estado_e_rotulo() -> None:
    github = GithubFalso()
    api = vigia.ApiGithub("tok-123", "dono/repo", transporte=httpx.MockTransport(github))
    try:
        await api.issues()
    finally:
        await api.fechar()
    (pedido,) = github.pedidos
    assert pedido.url.path == "/repos/dono/repo/issues"
    assert dict(pedido.url.params) == {
        "per_page": "100",
        "state": "all",
        "labels": "fonte-quebrada",
    }


def test_api_recusa_repositorio_fora_do_formato() -> None:
    with pytest.raises(ValueError):
        vigia.ApiGithub("tok", "dono/repo/../../outro")


def _secao(texto: str, chave: str) -> list[str]:
    linhas = texto.splitlines()
    inicio = linhas.index(f"{chave}:")
    corpo = []
    for linha in linhas[inicio + 1 :]:
        if linha and not linha.startswith(" "):
            break
        if linha.strip() and not linha.strip().startswith("#"):
            corpo.append(linha.strip())
    return corpo


def test_workflow_so_em_schedule_e_dispatch_com_permissoes_minimas() -> None:
    assert WORKFLOW.exists()
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request" not in texto
    gatilhos = _secao(texto, "on")
    assert gatilhos[0] == "schedule:" and "workflow_dispatch:" in gatilhos
    assert '- cron: "23 6 * * 1"' in gatilhos
    assert len(gatilhos) == 3
    assert texto.count("permissions:") == 1
    assert _secao(texto, "permissions") == ["contents: read", "issues: write"]
    assert set(re.findall(r"secrets\.(\w+)", texto)) <= {"GITHUB_TOKEN"}
    assert "uv run python scripts/vigia.py" in texto
    assert "persist-credentials: false" in texto
    usos = set(re.findall(r"uses: (\S+)", texto))
    assert usos and usos <= set(re.findall(r"uses: (\S+)", CI.read_text(encoding="utf-8")))
