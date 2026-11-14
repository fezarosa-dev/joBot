import html
import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, greenhouse, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "greenhouse"
URL_VITTA = "https://boards-api.greenhouse.io/v1/boards/vitta/jobs?content=true"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _json(caso: str, status: int = 200, **cabecalhos: str) -> httpx.Response:
    return httpx.Response(
        status, text=_texto(caso), headers={"Content-Type": "application/json", **cabecalhos}
    )


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = "vitta",
    leitor: LeitorFixo | None = None,
    condicional: bool = False,
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    """Roda o coletor de verdade sobre o `ClienteEducado` com transporte falso."""
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
        http: HttpEducado = cli.escopo(condicional=condicional)
        resultado = await greenhouse.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """O `resolver` do Greenhouse só lê o texto: qualquer pedido é erro do teste."""

    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"resolver não faz pedido: {pedido.url}")

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(httpx.MockTransport(recusa), relogio, LeitorFixo(), "0.1.0", _sem_dns)
    try:
        yield cli.escopo()
    finally:
        await cli.fechar()


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = greenhouse.COLETOR
    assert registro.descobrir()["greenhouse"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("boards-api.greenhouse.io",)


def test_escopos_um_por_empresa() -> None:
    empresas = [
        Empresa(nome="Vitta", fonte="greenhouse", identificador="vitta"),
        Empresa(nome="Nubank", fonte="greenhouse", identificador="nubank"),
        Empresa(nome="Vitta de novo", fonte="greenhouse", identificador="vitta"),
    ]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(greenhouse.COLETOR.escopos(ctx)) == ["vitta", "nubank"]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 3
    primeira = vagas[0]
    assert primeira.fonte == "greenhouse" and primeira.escopo == "vitta"
    assert primeira.url == "https://job-boards.greenhouse.io/vitta/jobs/8182389003"
    assert primeira.titulo == "Analista de Atendimento (Benefícios) | Pleno (Presencial/SP)"
    assert primeira.empresa == "Vitta"
    assert primeira.id_externo == "8182389003"
    assert primeira.locais == ("são paulo",)
    assert primeira.publicada_em == datetime(
        2026, 11, 10, 8, 51, 30, tzinfo=timezone(timedelta(hours=-5))
    )
    assert primeira.prazo is None
    assert primeira.descricao_formato == "html"
    assert primeira.etiquetas == ("Financeiro",)
    assert primeira.url_candidatura is None
    assert all(v.url.startswith(("https://", "http://")) for v in vagas)
    assert len(pedidos) == 1


async def test_conteudo_passa_por_html_unescape() -> None:
    resultado, _ = await _coletar(_json("normal"))
    brutos = [j["content"] for j in json.loads(_texto("normal"))["jobs"]]
    descricoes = [v.descricao for v in _vagas(resultado)]
    assert descricoes == [html.unescape(b) for b in brutos]
    assert all(d.startswith("<p>") and "&lt;" not in d for d in descricoes)


async def test_vazio() -> None:
    resultado, _ = await _coletar(_json("vazio"), escopo="nubank")
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["8182389003"]


@pytest.mark.parametrize(
    "corpo",
    ['{"postings": []}', "[]", '{"jobs": {}}', "isto não é json", '{"jobs": [1, "x"]}'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = json.loads(_texto("prazo"))
    dados["jobs"][0] |= {
        "first_published": "2026-11-10T08:51:30",  # sem fuso
        "application_deadline": "logo",
        "location": None,
        "content": None,
        "departments": "Financeiro",
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.prazo, vaga.locais) == (None, None, ())
    assert (vaga.descricao, vaga.etiquetas) == ("", ())


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = json.loads(_texto("normal"))
    dados["jobs"][1]["absolute_url"] = "javascript:alert(1)"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 2


async def test_prazo_vem_de_application_deadline() -> None:
    resultado, _ = await _coletar(_json("prazo"))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].prazo == date(2026, 12, 15)


async def test_404_empresa_nao_encontrada() -> None:
    resultado, pedidos = await _coletar(_json("nao_encontrado", 404), escopo="nao-existe")
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.empresa_nao_encontrada"
    assert (resultado.pedidos, len(pedidos)) == (1, 1)


async def test_429_e_erro_de_rede() -> None:
    resultado, _ = await _coletar(httpx.Response(429))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.limite_atingido")
    resultado, pedidos = await _coletar(httpx.Response(500))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.erro_de_rede")
    assert len(pedidos) == 3  # duas novas tentativas do HttpEducado

    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    resultado, _ = await _coletar(cai)
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.erro_de_rede"


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

    monkeypatch.setattr(greenhouse, "juntar_paginas", espia)
    etag = 'W/"3f2a819ade76f8809366e46fa007c0f3"'

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _json("normal", ETag=etag)

    leitor = LeitorFixo({URL_VITTA: Validadores(etag, None)})
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
    assert str(pedido.url) == URL_VITTA
    assert dict(pedido.url.params) == {"content": "true"}


async def test_escopo_estranho_nao_muda_o_caminho() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo="../x?y#z")
    assert [p.url.raw_path for p in pedidos] == [b"/v1/boards/..%2Fx%3Fy%23z/jobs?content=true"]


@pytest.mark.parametrize(
    "entrada",
    [
        "vitta",
        " vitta ",
        "https://job-boards.greenhouse.io/vitta",
        "https://job-boards.greenhouse.io/vitta/jobs/8182389003",
        "https://boards.greenhouse.io/vitta/",
        "boards.greenhouse.io/vitta",
        "https://boards.greenhouse.io/embed/job_board?for=vitta",
        "https://boards.greenhouse.io/embed/job_app?for=vitta&token=123",
        "https://job-boards.greenhouse.io/embed/job_app?for=vitta",
        "https://boards-api.greenhouse.io/v1/boards/vitta/jobs?content=true",
    ],
)
async def test_resolver_aceita_url_do_board_e_devolve_o_token(
    entrada: str, http_proibido: HttpEducado
) -> None:
    resolvido = await greenhouse.COLETOR.resolver(entrada, http_proibido)
    assert resolvido == {"identificador": "vitta"}


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "https://jobs.lever.co/vitta",
        "https://job-boards.eu.greenhouse.io/vitta",
        "https://job-boards.greenhouse.io/",
        "https://boards.greenhouse.io/embed/job_board",
        "https://boards.greenhouse.io/embed/job_app?token=1",
        "ftp://boards.greenhouse.io/vitta",
        "vit ta",
        "vítta",
        "x" * 101,
    ],
)
async def test_resolver_recusa_o_que_nao_e_board(entrada: str, http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await greenhouse.COLETOR.resolver(entrada, http_proibido)
