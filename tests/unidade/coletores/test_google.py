import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo import http as nucleo_http
from jobot.nucleo.coletores import base, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.coletores.carreiras import google
from jobot.nucleo.http import ClienteEducado, HttpEducado, RespostaGrande, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "google"
URL_FEED = "https://www.google.com/about/careers/applications/jobs/feed.xml"
LAST_MODIFIED = "Fri, 13 Nov 2026 22:53:10 GMT"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.xml").read_text(encoding="utf-8")


def _xml(corpo: str, cabecalhos: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        200, text=corpo, headers={"Content-Type": "text/xml", **(cabecalhos or {})}
    )


def _caso(caso: str) -> httpx.Response:
    return _xml(_texto(caso), {"Last-Modified": LAST_MODIFIED})


def _editado(mudar: Callable[[ET.Element], None], caso: str = "normal") -> httpx.Response:
    """Variação pequena do exemplo, montada no próprio teste (molde do coletor)."""
    raiz = ET.fromstring(_texto(caso))
    mudar(raiz)
    return _xml(ET.tostring(raiz, encoding="unicode"))


def _paises(raiz: ET.Element, n_job: int, *paises: str) -> None:
    """Troca os locais do `n_job`-ésimo `<job>` por um local por país dado."""
    job = raiz.findall("job")[n_job]
    locais = job.find("locations")
    assert locais is not None
    locais.clear()
    for pais in paises:
        local = ET.SubElement(locais, "location")
        ET.SubElement(local, "city").text = "Cidade"
        ET.SubElement(local, "country").text = pais


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
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
        escopo = google.COLETOR.escopos(ContextoColeta(empresas=[], termos=[], paises=[]))[0]
        resultado = await google.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = google.COLETOR
    limites = registro.limites("google")
    assert registro.descobrir()["google"] is prova
    assert prova.leva == limites.leva == "B"
    assert prova.intervalo_min == limites.intervalo_min == 1440
    assert (prova.espera_s, prova.max_pedidos) == (limites.espera_s, limites.max_pedidos)
    assert prova.hosts == ("www.google.com",)


def test_escopos_lista_unica() -> None:
    empresas = [Empresa(nome="Google", fonte="google", identificador="google")]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["US"])
    assert list(google.COLETOR.escopos(ctx)) == [""]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_caso("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    assert len(pedidos) == 1
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    assert all(v.url.startswith(("http://", "https://")) for v in vagas)
    assert {v.fonte for v in vagas} == {"google"}
    primeira = vagas[0]
    assert primeira.escopo == ""
    assert primeira.id_externo == "122388138554204870"
    assert primeira.titulo == (
        "Market Responsibility Lead, YouTube Trust and Safety (English, Portuguese)"
    )
    assert primeira.empresa == "YouTube"
    assert primeira.url == (
        "https://careers.google.com/jobs/results/122388138554204870-market-responsibility-lead/"
    )
    assert primeira.url_candidatura is None
    assert primeira.descricao_formato == "html"
    assert primeira.descricao.startswith("<p><b>Please submit your resume in English")
    assert primeira.locais == ("São Paulo, Brazil",)
    assert primeira.modalidade_declarada == "onsite"
    assert primeira.contrato_declarado == "FULL_TIME"
    assert primeira.etiquetas == ("BUSINESS_STRATEGY",)
    assert primeira.publicada_em == datetime(2026, 11, 5, 13, 9, 55, 873000, tzinfo=UTC)
    assert vagas[1].locais == (
        "Belo Horizonte, State of Minas Gerais, Brazil",
        "São Paulo, State of São Paulo, Brazil",
    )
    assert vagas[1].empresa == "Google"


async def test_filtra_so_country_brazil() -> None:
    def fora(raiz: ET.Element) -> None:
        _paises(raiz, 0, "USA")
        _paises(raiz, 1, "brazil")  # o filtro é `country == 'Brazil'`, como no apêndice

    resultado, _ = await _coletar(_editado(fora))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert [v.id_externo for v in _vagas(resultado)] == [
        "74985848252048070",
        "138123272494424774",
        "135157584154763974",
    ]


async def test_vaga_com_algum_local_no_brasil_entra_com_todos_os_locais() -> None:
    resultado, _ = await _coletar(_editado(lambda raiz: _paises(raiz, 0, "USA", "Brazil")))
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    assert vagas[0].locais == ("Cidade, USA", "Cidade, Brazil")


async def test_vazio() -> None:
    resultado, _ = await _coletar(_caso("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_so_vagas_fora_do_brasil_e_ok_vazio() -> None:
    def fora(raiz: ET.Element) -> None:
        for n in range(5):
            _paises(raiz, n, "USA")

    resultado, _ = await _coletar(_editado(fora))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_caso("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(_vagas(resultado)) == 4


def _sem_titulo(raiz: ET.Element) -> None:
    for job in raiz.findall("job"):
        titulo = job.find("title")
        assert titulo is not None
        job.remove(titulo)


def _sem_pais(raiz: ET.Element) -> None:
    for job in raiz.findall("job"):
        locais = job.find("locations")
        assert locais is not None
        job.remove(locais)


def _job_renomeado(raiz: ET.Element) -> None:
    for job in raiz.findall("job"):
        job.tag = "posting"


@pytest.mark.parametrize(
    "resposta",
    [
        _xml("<rss><channel /></rss>"),
        _xml("<jobs><job><title>corta no meio"),
        _xml('{"jobs": []}'),
        _editado(_sem_titulo),
        _editado(_sem_pais),
        _editado(_job_renomeado),
    ],
    ids=[
        "outra_raiz",
        "xml_quebrado",
        "json",
        "nenhuma_vaga_legivel",
        "pais_sumiu",
        "filho_renomeado",
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(resposta: httpx.Response) -> None:
    resultado, pedidos = await _coletar(resposta)
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert (resultado.motivo, resultado.pedidos, len(pedidos)) == ("saude.formato_mudou", 1, 1)


async def test_url_fora_de_http_pula_a_vaga() -> None:
    def javascript(raiz: ET.Element) -> None:
        url = raiz.findall("job")[0].find("url")
        assert url is not None
        url.text = "javascript:alert(1)"

    resultado, _ = await _coletar(_editado(javascript))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(_vagas(resultado)) == 4


@pytest.mark.parametrize(
    ("remote", "is_remote", "is_hybrid", "esperada"),
    [
        ("onsite", "No", "Yes", "hybrid"),
        ("remote", "No", "No", "remote"),
        ("onsite", "Yes", "No", "remote"),
        ("onsite", "No", "No", "onsite"),
    ],
)
async def test_modalidade_lida_de_remote_is_remote_e_is_hybrid(
    remote: str, is_remote: str, is_hybrid: str, esperada: str
) -> None:
    def modalidade(raiz: ET.Element) -> None:
        job = raiz.findall("job")[0]
        for campo, valor in (("remote", remote), ("isRemote", is_remote), ("isHybrid", is_hybrid)):
            no = job.find(campo)
            assert no is not None
            no.text = valor

    resultado, _ = await _coletar(_editado(modalidade))
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    assert vagas[0].modalidade_declarada == esperada


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    def estranho(raiz: ET.Element) -> None:
        job = raiz.findall("job")[0]
        for campo in ("employer", "published", "jobid", "jobtype", "categories", "description"):
            no = job.find(campo)
            assert no is not None
            job.remove(no)
        ET.SubElement(job, "published").text = "ontem"

    resultado, _ = await _coletar(_editado(estranho))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    vaga = _vagas(resultado)[0]
    assert (vaga.empresa, vaga.publicada_em, vaga.id_externo) == ("Google", None, None)
    assert (vaga.contrato_declarado, vaga.etiquetas, vaga.descricao) == (None, (), "")


async def test_teto_proprio_no_lugar_do_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    # o feed real tem 19,8 MB: o teto padrão (5 MB) daria `RespostaGrande`
    monkeypatch.setattr(nucleo_http, "TETO_PADRAO", 1024)
    resultado, _ = await _coletar(_caso("normal"))
    assert (resultado.estado, len(resultado.vagas)) == ("ok", 5)


async def test_feed_acima_do_teto_sobe_resposta_grande(monkeypatch: pytest.MonkeyPatch) -> None:
    # como no Ashby: o executor traduz `RespostaGrande` em "falhou" com saude.resposta_grande
    corpo = _texto("normal")
    monkeypatch.setattr(google, "TETO_FEED_BYTES", len(corpo.encode()) - 1)
    with pytest.raises(RespostaGrande):
        await _coletar(_xml(corpo))


def test_teto_do_feed_e_32_mb() -> None:
    assert google.TETO_FEED_BYTES == 32 * 1024 * 1024


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

    monkeypatch.setattr(google, "juntar_paginas", espia)

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-Modified-Since") == LAST_MODIFIED:
            return httpx.Response(304, headers={"Last-Modified": LAST_MODIFIED})
        return _caso("normal")

    leitor = LeitorFixo({URL_FEED: Validadores(None, LAST_MODIFIED)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-Modified-Since") for p in pedidos] == [LAST_MODIFIED]
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_caso("vazio"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert str(pedido.url) == URL_FEED
    assert dict(pedido.url.params) == {}
    assert "If-Modified-Since" not in pedido.headers  # sem validador guardado


async def test_detalhar_e_resolver(http_proibido: HttpEducado) -> None:
    vaga = VagaColetada(
        fonte="google",
        escopo="",
        url=URL_FEED,
        titulo="x",
        empresa="Google",
        descricao_formato="html",
    )
    assert await google.COLETOR.detalhar(vaga, http_proibido) is None
    with pytest.raises(ValueError, match="identificador"):
        await google.COLETOR.resolver("google", http_proibido)


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não faz pedido: {pedido.url}")

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(httpx.MockTransport(recusa), relogio, LeitorFixo(), "0.1.0", _sem_dns)
    try:
        yield cli.escopo()
    finally:
        await cli.fechar()
