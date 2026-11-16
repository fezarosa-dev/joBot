"""Testes do molde do coletor público: são também os testes de partida da fonte nova.

Na cópia, só mudam as duas linhas com `# MUDE:` (o módulo da fonte e a pasta dos exemplos) e o
trecho de `_pagina_2`, que passa a seguir o campo de próxima página do site.
"""

import importlib.util
import json
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from apoio import molde_coletor as fonte  # MUDE: o módulo da fonte nova
from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.relogio import Relogio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "molde_coletor"  # MUDE: a pasta

pytestmark = pytest.mark.anyio

RAIZ = Path(__file__).resolve().parents[3]
URL_P1 = f"{fonte._API}?q=dev&pagina=1&por_pagina={fonte._POR_PAGINA}"
Responder = Callable[[httpx.Request], httpx.Response]


def _carregar_capturar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capturar_script", RAIZ / "scripts/capturar.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _json(caso: str, status: int = 200, **cabecalhos: str) -> httpx.Response:
    return httpx.Response(
        status, text=_texto(caso), headers={"Content-Type": "application/json", **cabecalhos}
    )


def _pagina_2() -> httpx.Response:
    """A última página, montada do `normal.json` (o `capturar.py` grava só a primeira)."""
    dados = json.loads(_texto("normal"))
    dados["proxima"] = False
    dados["vagas"] = [v | {"id": v["id"] + 1000, "url": f"{v['url']}-p2"} for v in dados["vagas"]]
    return httpx.Response(200, json=dados)


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = "dev",
    leitor: LeitorFixo | None = None,
    condicional: bool = False,
    para_no_429: bool = False,
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    """Roda o coletor de verdade sobre o `ClienteEducado` com transporte falso.

    As respostas saem em ordem; a última se repete.
    """
    pedidos: list[httpx.Request] = []
    fila = list(respostas)

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return r if isinstance(r, httpx.Response) else r(pedido)

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(
        httpx.MockTransport(servidor), relogio, leitor or LeitorFixo(), "0.1.0", resolver=_sem_dns
    )
    try:
        http: HttpEducado = cli.escopo(condicional=condicional, para_no_429=para_no_429)
        resultado = await fonte.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def test_cumpre_o_protocolo() -> None:
    alvo: Coletor = fonte.COLETOR
    assert alvo.chave == fonte.CHAVE


def test_escopos_um_por_termo() -> None:
    ctx = ContextoColeta(empresas=(), termos=(" dev ", "dev", "", "dados"), paises=("BR",))
    assert list(fonte.COLETOR.escopos(ctx)) == ["dev", "dados"]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"), _pagina_2())
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 2)
    assert [p.url.params["pagina"] for p in pedidos] == ["1", "2"]
    vagas = _vagas(resultado)
    assert len(vagas) == 6
    assert all(v.fonte == fonte.CHAVE and v.escopo == "dev" for v in vagas)
    assert all(v.url.startswith("https://") for v in vagas)
    primeira = vagas[0]
    assert primeira.titulo == "Pessoa Desenvolvedora Python Pleno"
    assert primeira.empresa == "Exemplo Tecnologia"
    assert primeira.url == "https://vagas.exemplo.invalid/vaga/1001"
    assert primeira.id_externo == "1001"
    assert primeira.locais == ("São Paulo, SP",)
    assert primeira.descricao_formato == "html"
    assert primeira.publicada_em is not None and primeira.publicada_em.utcoffset() is not None


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["1001"]
    for corpo in ('{"vagas": [1, "x"], "proxima": false}', '{"itens": []}', "não é json"):
        resultado, _ = await _coletar(httpx.Response(200, text=corpo))
        assert (resultado.vagas, resultado.estado) == ((), "falhou"), corpo
        assert resultado.motivo == "saude.formato_mudou", corpo
    # página 2 torta: as vagas da página 1 ficam, mas a lista não veio inteira
    resultado, _ = await _coletar(_json("normal"), httpx.Response(200, text='{"itens": []}'))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 3


async def test_paginacao_para_no_teto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fonte, "_MAX_PAGINAS", 2)
    resultado, pedidos = await _coletar(_json("normal"))  # a próxima nunca acaba
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert (resultado.pedidos, len(pedidos)) == (2, 2)
    assert len(resultado.vagas) == 6


async def test_429_e_erro_de_rede() -> None:
    resultado, _ = await _coletar(httpx.Response(429), para_no_429=True)
    assert (resultado.estado, resultado.motivo) == ("no_limite", "saude.parou_429")

    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    resultado, _ = await _coletar(cai)
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.erro_de_rede"
    resultado, _ = await _coletar(_json("normal"), cai)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(resultado.vagas) == 3


async def test_304(monkeypatch: pytest.MonkeyPatch) -> None:
    paginas: list[Sequence[base.Item]] = []
    juntar = base.juntar_paginas

    async def espia(
        http: HttpEducado, iterador: AsyncIterator[Sequence[base.Item]]
    ) -> ResultadoEscopo:
        async def copia() -> AsyncIterator[Sequence[base.Item]]:
            async for pagina in iterador:
                paginas.append(pagina)
                yield pagina

        return await juntar(http, copia())

    monkeypatch.setattr(fonte, "juntar_paginas", espia)
    etag = 'W/"molde-1"'

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _json("normal", ETag=etag)

    leitor = LeitorFixo({URL_P1: Validadores(etag, None)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-None-Match") for p in pedidos] == [etag]
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_json("vazio"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert pedido.url.host == fonte._HOST
    assert pedido.url.path == httpx.URL(fonte._API).path
    assert dict(pedido.url.params) == {
        "q": "dev",
        "pagina": "1",
        "por_pagina": str(fonte._POR_PAGINA),
    }


async def test_resolver_recusa() -> None:
    relogio: Relogio = RelogioFalso()

    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"resolver não faz pedido: {pedido.url}")

    cli = ClienteEducado(httpx.MockTransport(recusa), relogio, LeitorFixo(), "0.1.0", _sem_dns)
    try:
        with pytest.raises(ValueError):
            await fonte.COLETOR.resolver("qualquer-coisa", cli.escopo())
    finally:
        await cli.fechar()


def test_fixtures_do_molde_sem_problemas() -> None:
    # `test_fixtures.py` só percorre `descobrir()`, que não vê o molde: a pasta se confere aqui.
    assert _carregar_capturar().problemas(PASTA) == []
