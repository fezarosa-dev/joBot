from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, registro, wwr
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "wwr"
URL_GERAL = "https://weworkremotely.com/remote-jobs.rss"
URL_DEVOPS = "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"
CATEGORIAS = [
    "all-other-remote-jobs",
    "remote-back-end-programming-jobs",
    "remote-customer-support-jobs",
    "remote-design-jobs",
    "remote-devops-sysadmin-jobs",
    "remote-front-end-programming-jobs",
    "remote-full-stack-programming-jobs",
    "remote-management-and-finance-jobs",
    "remote-product-jobs",
    "remote-programming-jobs",
    "remote-sales-and-marketing-jobs",
]
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.xml").read_text(encoding="utf-8")


def _rss(caso: str, status: int = 200, **cabecalhos: str) -> httpx.Response:
    return httpx.Response(
        status,
        text=_texto(caso),
        headers={"Content-Type": "application/rss+xml; charset=utf-8", **cabecalhos},
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
    escopo: str = "geral",
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
        resultado = await wwr.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _rss_com_item(**campos: str) -> httpx.Response:
    """Feed de um item só; o valor `<omitir>` tira o campo."""
    item = {
        "title": "Acme: Dev",
        "region": "Remote",
        "category": "Programming",
        "type": "Full-Time",
        "description": "<p>x</p>",
        "pubDate": "Fri, 13 Nov 2026 21:41:29 +0000",
        "expires_at": "Sun, 13 Dec 2026 21:41:29 +0000",
        "guid": "https://weworkremotely.com/remote-jobs/acme-dev",
        "link": "https://weworkremotely.com/remote-jobs/acme-dev",
    } | campos
    corpo = "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in item.items() if v != "<omitir>")
    texto = f"<rss version='2.0'><channel><title>t</title><item>{corpo}</item></channel></rss>"
    return httpx.Response(200, text=texto)
    return httpx.Response(
        200,
        text=f"<rss version='2.0'><channel><title>t</title><item>{corpo}</item></channel></rss>",
    )


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = wwr.COLETOR
    assert registro.descobrir()["wwr"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("weworkremotely.com",)
    assert prova.credito_obrigatorio is True
    assert prova.intervalo_min == 60


def test_escopos_sao_os_12_feeds() -> None:
    ctx = ContextoColeta(empresas=[], termos=["dev"], paises=["BR"])
    assert list(wwr.COLETOR.escopos(ctx)) == ["geral", *CATEGORIAS]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_rss("normal", ETag='W/"x"'))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 5  # inclui os itens com e sem media:content (namespace)
    primeira = vagas[0]
    assert primeira.fonte == "wwr" and primeira.escopo == "geral"
    assert (
        primeira.url
        == "https://weworkremotely.com/remote-jobs/pavago-seo-digital-marketing-specialist"
    )
    assert primeira.id_externo == primeira.url
    assert primeira.titulo == "SEO & Digital Marketing Specialist"
    assert primeira.empresa == "Pavago"
    assert primeira.locais == ("Anywhere in the World",)
    assert primeira.modalidade_declarada == "remote"
    assert primeira.contrato_declarado == "Full-Time"
    assert primeira.publicada_em == datetime(2026, 11, 13, 21, 41, 29, tzinfo=UTC)
    assert primeira.prazo == date(2026, 12, 13)
    assert primeira.etiquetas == ("Sales and Marketing",)
    assert primeira.descricao_formato == "html"
    assert primeira.url_candidatura is None
    assert all(v.url.startswith("https://weworkremotely.com/") for v in vagas)
    assert len(pedidos) == 1


async def test_descricao_html_sai_do_xml_uma_vez() -> None:
    resultado, _ = await _coletar(_rss("normal"))
    descricao = _vagas(resultado)[0].descricao
    assert descricao.startswith('<img src="https://we-work-remotely.imgix.net/')
    assert "<h2><strong>SEO &amp; Digital Marketing Specialist" in descricao
    assert "&lt;" not in descricao


async def test_locais_juntam_regiao_estado_e_pais_sem_bandeira() -> None:
    resultado, _ = await _coletar(_rss("normal"))
    assert _vagas(resultado)[3].locais == ("California", "United States of America")
    resultado, _ = await _coletar(_rss("categoria"), escopo="remote-devops-sysadmin-jobs")
    vagas = _vagas(resultado)
    assert vagas[1].locais == ("Anywhere in the World", "North Carolina")
    assert vagas[4].locais == ("Anywhere in the World", "United States of America")


async def test_categoria_traz_os_mesmos_campos_do_geral() -> None:
    # a captura contradiz o apêndice 2.2 ("só o geral traz expires_at, type..."): a categoria traz
    resultado, pedidos = await _coletar(_rss("categoria"), escopo="remote-devops-sysadmin-jobs")
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    vagas = _vagas(resultado)
    assert len(vagas) == 5 and str(pedidos[0].url) == URL_DEVOPS
    assert vagas[0].escopo == "remote-devops-sysadmin-jobs"
    assert vagas[0].empresa == "EdgeQ Technologies Private Limited"
    assert vagas[0].prazo == date(2026, 12, 13)
    assert vagas[0].contrato_declarado == "Full-Time"
    assert vagas[0].etiquetas == ("DevOps and Sysadmin",)
    assert vagas[1].publicada_em == datetime(2026, 11, 10, 22, 32, 18, tzinfo=UTC)


async def test_titulo_corta_no_primeiro_dois_pontos() -> None:
    resultado, _ = await _coletar(_rss("normal"))
    segunda = _vagas(resultado)[1]
    assert segunda.empresa == "Terac"
    assert segunda.titulo == "Product Marketing Managers: GTM Brief Review for Bike Repair Tool"


async def test_vazio() -> None:
    resultado, _ = await _coletar(_rss("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_rss("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.empresa for v in _vagas(resultado)] == ["Pavago"]


@pytest.mark.parametrize(
    "corpo",
    [
        "isto não é xml",
        "<rss version='2.0'></rss>",
        "<html><body>manutenção</body></html>",
        "<rss><channel><item><title>sem dois pontos</title></item></channel></rss>",
        "<rss><channel>",
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_bomba_de_entidades_nao_derruba() -> None:
    niveis = "".join(f'<!ENTITY l{i} "{f"&l{i - 1};" * 10}">' for i in range(1, 8))
    corpo = (
        f'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY l0 "lol">{niveis}]>'
        "<rss><channel><title>&l7;</title></channel></rss>"
    )
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    resultado, _ = await _coletar(
        _rss_com_item(
            pubDate="ontem",
            expires_at="logo",
            region="<omitir>",
            type="<omitir>",
            category="<omitir>",
            description="<omitir>",
        )
    )
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.prazo, vaga.locais) == (None, None, ())
    assert (vaga.contrato_declarado, vaga.etiquetas, vaga.descricao) == (None, (), "")


async def test_data_sem_fuso_vale_utc() -> None:
    resultado, _ = await _coletar(_rss_com_item(pubDate="Fri, 13 Nov 2026 21:41:29 -0000"))
    assert _vagas(resultado)[0].publicada_em == datetime(2026, 11, 13, 21, 41, 29, tzinfo=UTC)


async def test_url_fora_de_http_pula_a_vaga() -> None:
    resultado, _ = await _coletar(_rss_com_item(link="javascript:alert(1)"))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    texto = _texto("normal").replace(
        "https://weworkremotely.com/remote-jobs/pavago-seo-digital-marketing-specialist",
        "javascript:alert(1)",
    )
    resultado, _ = await _coletar(httpx.Response(200, text=texto))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 4


async def test_429_e_erro_de_rede() -> None:
    resultado, _ = await _coletar(httpx.Response(429))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.limite_atingido")
    resultado, pedidos = await _coletar(httpx.Response(500))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.erro_de_rede")
    assert len(pedidos) == 3  # duas novas tentativas do HttpEducado
    resultado, _ = await _coletar(httpx.Response(404))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.erro_de_rede"

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

    monkeypatch.setattr(wwr, "juntar_paginas", espia)
    etag = 'W/"da3f4d96776f48cf6f36d67e66f9c987"'

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _rss("normal", ETag=etag)

    leitor = LeitorFixo({URL_GERAL: Validadores(etag, None)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-None-Match") for p in pedidos] == [etag]
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


@pytest.mark.parametrize(
    ("escopo", "url"),
    [("geral", URL_GERAL)]
    + [(c, f"https://weworkremotely.com/categories/{c}.rss") for c in CATEGORIAS],
)
async def test_endereco_e_parametros(escopo: str, url: str) -> None:
    _, pedidos = await _coletar(_rss("vazio"), escopo=escopo)
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert str(pedido.url) == url
    assert dict(pedido.url.params) == {}


async def test_escopo_desconhecido_nao_faz_pedido() -> None:
    with pytest.raises(KeyError):
        await _coletar(_rss("vazio"), escopo="../x")


async def test_detalhar_nao_faz_nada() -> None:
    assert await wwr.COLETOR.detalhar(base.UrlListada(URL_GERAL), None) is None  # type: ignore[arg-type]
