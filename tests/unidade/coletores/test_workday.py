import copy
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, registro, workday
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, ErroDeRede, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "workday"
ESCOPO = "santander/SantanderCareers|wd3"
URL_LISTA = "https://santander.wd3.myworkdayjobs.com/wday/cxs/santander/SantanderCareers/jobs"
ESCOPO_MC = "mastercard/CorporateCareers|wd1"
CAMINHO_MC = "/job/Sao-Paulo-Brazil/SME-Mid-Market-Business-Development-Director_R-295134-1"
URL_DETALHE_MC = (
    "https://mastercard.wd1.myworkdayjobs.com/wday/cxs/mastercard/CorporateCareers" + CAMINHO_MC
)
BRASIL = "1a29bb1357b240ab99a2fa755cc87c0e"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _dados(caso: str) -> dict[str, Any]:
    carregado: dict[str, Any] = json.loads(_texto(caso))
    return carregado


def _json(caso: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=_texto(caso), headers={"Content-Type": "application/json"})


def _corpo(pedido: httpx.Request) -> dict[str, Any]:
    carregado: dict[str, Any] = json.loads(pedido.content)
    return carregado


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _rodar[T](
    chamada: Callable[[HttpEducado], Awaitable[T]], *respostas: httpx.Response | Responder
) -> tuple[T, list[httpx.Request]]:
    """Roda a chamada sobre o `ClienteEducado` de verdade, com transporte falso."""
    pedidos: list[httpx.Request] = []
    fila = list(respostas)

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return r if isinstance(r, httpx.Response) else r(pedido)

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(
        httpx.MockTransport(servidor), relogio, LeitorFixo(), "0.1.0", resolver=_sem_dns
    )
    try:
        resultado = await chamada(cli.escopo())
    finally:
        await cli.fechar()
    return resultado, pedidos


async def _coletar(
    *respostas: httpx.Response | Responder, escopo: str = ESCOPO
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    coletor = copy.copy(workday.COLETOR)
    return await _rodar(lambda http: coletor.coletar(escopo, http), *respostas)


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _empresa(identificador: str, wd: str | None = "wd3", nome: str = "") -> Empresa:
    parametros = {} if wd is None else {"wd": wd}
    return Empresa(
        nome=nome or identificador,
        fonte="workday",
        identificador=identificador,
        parametros=parametros,
    )


def _ctx(*empresas: Empresa) -> ContextoColeta:
    return ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])


def _pagina(n: int, inicio: int = 0, total: int = 0) -> dict[str, Any]:
    """Página de lista com `n` vagas de caminho distinto (a partir de `inicio`)."""
    modelo = _dados("normal")["jobPostings"][0]
    vagas = [
        modelo | {"externalPath": f"/job/SP/Vaga_{inicio + i}", "title": f"Vaga {inicio + i}"}
        for i in range(n)
    ]
    return {"total": total, "jobPostings": vagas, "facets": [], "userAuthenticated": False}


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = workday.COLETOR
    assert registro.descobrir()["workday"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "B"
    assert prova.espera_s == registro.limites("workday").espera_s
    assert prova.nome == "Workday"


def test_escopos_um_por_empresa_com_o_wd() -> None:
    ctx = _ctx(
        _empresa("santander/SantanderCareers"),
        _empresa("mastercard/CorporateCareers", "wd1"),
        _empresa("santander/SantanderCareers"),
    )
    assert list(copy.copy(workday.COLETOR).escopos(ctx)) == [ESCOPO, ESCOPO_MC]


@pytest.mark.parametrize(
    ("identificador", "wd"),
    [
        ("santander/SantanderCareers", None),  # sem wd não há host
        ("santander/SantanderCareers", "wd3.evil.com"),
        ("santander", "wd3"),  # sem site
        ("santander/Santander/Careers", "wd3"),
        ("evil.com#/x", "wd3"),
        ("santander/Santander|x", "wd3"),
    ],
)
def test_escopos_pula_empresa_sem_parametro_valido(identificador: str, wd: str | None) -> None:
    coletor = copy.copy(workday.COLETOR)  # `escopos` guarda estado: não sujar o global
    assert list(coletor.escopos(_ctx(_empresa(identificador, wd)))) == []


async def test_normal() -> None:
    coletor = copy.copy(workday.COLETOR)
    coletor.escopos(_ctx(_empresa("santander/SantanderCareers", nome="Banco Santander")))
    resultado, pedidos = await _rodar(
        lambda http: coletor.coletar(ESCOPO, http), _json("normal"), _json("normal")
    )
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 2)
    vagas = _vagas(resultado)
    assert len(vagas) == 5  # a página curta encerra a listagem, mesmo com total 333
    ultima = vagas[4]
    assert ultima.fonte == "workday" and ultima.escopo == ESCOPO
    assert ultima.url == (
        "https://santander.wd3.myworkdayjobs.com/SantanderCareers"
        "/job/SAO-PAULO/Espec-Santander-II-8h_Req1628949"
    )
    assert ultima.titulo == "Espec Santander II 8h - Vaga exclusiva para PcD"
    assert ultima.empresa == "Banco Santander"
    assert ultima.id_externo == "/job/SAO-PAULO/Espec-Santander-II-8h_Req1628949"
    assert ultima.locais == ("SAO PAULO",)
    assert ultima.publicada_em is None  # `postedOn` é texto relativo: não serve de data
    assert ultima.descricao == "" and ultima.descricao_formato == "html"
    assert all(v.url.startswith("https://") for v in vagas)


async def test_sem_escopos_a_empresa_e_o_tenant() -> None:
    resultado, _ = await _coletar(_json("normal"), _json("normal"))
    assert {v.empresa for v in _vagas(resultado)} == {"santander"}


async def test_faceta_brasil_lida_da_resposta() -> None:
    dados = _dados("normal")
    grupo = dados["facets"][4]["values"][0]
    assert grupo["facetParameter"] == "locationCountry"
    grupo["values"][0]["id"] = "id-do-brasil-neste-tenant"
    resultado, pedidos = await _coletar(httpx.Response(200, json=dados), _json("normal"))
    assert resultado.estado == "ok"
    assert [_corpo(p)["appliedFacets"] for p in pedidos] == [
        {},
        {"locationCountry": ["id-do-brasil-neste-tenant"]},
    ]


async def test_faceta_de_pais_vence_a_de_locais() -> None:
    dados = _dados("normal")
    regioes = dados["facets"][4]["values"][1]["values"]
    regioes.append({"descriptor": "Curitiba, PR", "id": "curitiba", "count": 2})
    _, pedidos = await _coletar(httpx.Response(200, json=dados), _json("normal"))
    assert _corpo(pedidos[1])["appliedFacets"] == {"locationCountry": [BRASIL]}


async def test_tenant_so_com_locations_filtra_pelos_locais_do_brasil() -> None:
    dados = _dados("so_locations")
    locais = dados["facets"][3]["values"][0]
    assert locais["facetParameter"] == "locations"
    locais["values"] += [
        {"descriptor": "Sao Paulo, Brazil", "id": "sp", "count": 13},
        {"descriptor": "Boston, MA", "id": "boston", "count": 3},
        {"descriptor": "Rio de Janeiro, Brasil", "id": "rj", "count": 1},
    ]
    resultado, pedidos = await _coletar(
        httpx.Response(200, json=dados), _json("so_locations"), escopo=ESCOPO_MC
    )
    assert resultado.estado == "ok" and len(resultado.vagas) == 5
    assert _corpo(pedidos[1])["appliedFacets"] == {"locations": ["sp", "rj"]}


async def test_sem_faceta_do_brasil_e_ok_vazio_sem_segundo_pedido() -> None:
    resultado, pedidos = await _coletar(_json("so_locations"), escopo=ESCOPO_MC)
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("normal"), _json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 4


@pytest.mark.parametrize(
    "corpo",
    [
        "isto não é json",
        "[]",
        '{"total": 3, "jobPostings": []}',  # sem facets
        '{"total": 3, "jobPostings": [], "facets": {}}',
        '{"total": "muitas", "jobPostings": [], "facets": []}',
        '{"total": true, "jobPostings": [], "facets": []}',
    ],
)
async def test_descoberta_fora_do_formato_falhou(corpo: str) -> None:
    resultado, pedidos = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"
    assert len(pedidos) == 1


@pytest.mark.parametrize(
    "corpo",
    [
        '{"total": 3, "jobPostings": {}}',
        '{"jobPostings": [1, "x"], "total": 2}',
        '{"jobPostings": [{"title": "Sem caminho"}], "total": 1}',
        '{"jobPostings": [{"title": "x", "externalPath": "job/sem/barra"}], "total": 1}',
        '{"jobPostings": [{"title": "x", "externalPath": "//evil.com/job"}], "total": 1}',
    ],
)
async def test_pagina_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(_json("normal"), httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_paginacao_total_so_na_primeira_pagina() -> None:
    # como na conferência: com offset > 0 o `total` vem 0, e a listagem segue mesmo assim
    def responde(pedido: httpx.Request) -> httpx.Response:
        corpo = _corpo(pedido)
        if not corpo["appliedFacets"]:
            return _json("normal")
        offset = corpo["offset"]
        n = 20 if offset < 40 else 5
        return httpx.Response(200, json=_pagina(n, offset, 45 if offset == 0 else 0))

    resultado, pedidos = await _coletar(responde)
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 4)
    assert [v.titulo for v in _vagas(resultado)] == [f"Vaga {i}" for i in range(45)]
    assert [_corpo(p)["offset"] for p in pedidos[1:]] == [0, 20, 40]
    assert {_corpo(p)["limit"] for p in pedidos} == {20}


async def test_paginacao_para_quando_o_total_e_atingido_numa_pagina_cheia() -> None:
    resultado, pedidos = await _coletar(
        _json("normal"), httpx.Response(200, json=_pagina(20, 0, 20))
    )
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 20, 2)


async def test_paginacao_para_quando_a_pagina_vem_vazia() -> None:
    def responde(pedido: httpx.Request) -> httpx.Response:
        corpo = _corpo(pedido)
        if not corpo["appliedFacets"]:
            return _json("normal")
        n = 20 if corpo["offset"] == 0 else 0
        return httpx.Response(200, json=_pagina(n, corpo["offset"], 5000))

    resultado, pedidos = await _coletar(responde)
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 20, 3)


async def test_total_absurdo_nao_prende_o_coletor() -> None:
    def responde(pedido: httpx.Request) -> httpx.Response:
        corpo = _corpo(pedido)
        if not corpo["appliedFacets"]:
            return _json("normal")
        return httpx.Response(200, json=_pagina(20, corpo["offset"], 10**12))

    resultado, pedidos = await _coletar(responde)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert len(resultado.vagas) == 20 * workday.MAX_PAGINAS
    assert len(pedidos) == 1 + workday.MAX_PAGINAS


async def test_erro_depois_de_uma_pagina_e_parcial_com_as_vagas_lidas() -> None:
    resultado, _ = await _coletar(
        _json("normal"), httpx.Response(200, json=_pagina(20, 0, 45)), httpx.Response(500)
    )
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(resultado.vagas) == 20


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


async def test_404_empresa_nao_encontrada() -> None:
    resultado, pedidos = await _coletar(httpx.Response(404, text="Not Found"))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.empresa_nao_encontrada"
    assert (resultado.pedidos, len(pedidos)) == (1, 1)


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_json("normal"), _json("normal"))
    assert len(pedidos) == 2
    for pedido in pedidos:
        assert pedido.method == "POST"
        assert str(pedido.url) == URL_LISTA
        assert pedido.headers["Content-Type"] == "application/json"
        assert pedido.headers["Accept"] == "application/json"
        assert pedido.headers["Accept-Language"].startswith("pt-BR")
    assert _corpo(pedidos[0]) == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
    assert _corpo(pedidos[1]) == {
        "appliedFacets": {"locationCountry": [BRASIL]},
        "limit": 20,
        "offset": 0,
        "searchText": "",
    }


@pytest.mark.parametrize(
    "escopo", ["evil.com#/x|wd1", "santander/SantanderCareers", "a/b|wd1.evil.com", "a|wd1"]
)
async def test_escopo_malformado_nao_faz_pedido(escopo: str) -> None:
    with pytest.raises(ValueError):
        await _coletar(_json("normal"), escopo=escopo)


async def _vaga_mastercard() -> VagaColetada:
    dados = _dados("so_locations")
    dados["facets"][3]["values"][0]["values"].append(
        {"descriptor": "Sao Paulo, Brazil", "id": "sp", "count": 13}
    )
    resultado, _ = await _coletar(
        httpx.Response(200, json=dados), _json("so_locations"), escopo=ESCOPO_MC
    )
    return _vagas(resultado)[0]


async def _detalhar(
    item: base.Item, *respostas: httpx.Response | Responder
) -> tuple[VagaColetada | None, list[httpx.Request]]:
    return await _rodar(lambda http: workday.COLETOR.detalhar(item, http), *respostas)


async def test_detalhar_le_job_posting_info() -> None:
    vaga = await _vaga_mastercard()
    assert vaga.url == "https://mastercard.wd1.myworkdayjobs.com/CorporateCareers" + CAMINHO_MC
    detalhada, pedidos = await _detalhar(vaga, _json("detalhe"))
    assert detalhada is not None
    assert [(p.method, str(p.url)) for p in pedidos] == [("GET", URL_DETALHE_MC)]
    assert pedidos[0].headers["Accept"] == "application/json"
    info = _dados("detalhe")["jobPostingInfo"]
    assert detalhada.descricao == info["jobDescription"]
    assert detalhada.descricao_formato == "html"
    assert detalhada.publicada_em == datetime(2026, 11, 11, tzinfo=UTC)  # startDate
    assert detalhada.prazo == date(2026, 12, 11)  # endDate
    assert detalhada.contrato_declarado == "Full time"  # timeType
    # o resto fica como veio da lista (a URL é a chave: não muda)
    assert (detalhada.url, detalhada.titulo, detalhada.empresa, detalhada.escopo) == (
        vaga.url,
        vaga.titulo,
        vaga.empresa,
        vaga.escopo,
    )


async def test_detalhar_campo_opcional_estranho_fica_vazio() -> None:
    vaga = await _vaga_mastercard()
    dados = _dados("detalhe")
    dados["jobPostingInfo"] |= {"startDate": "ontem", "endDate": 3, "timeType": None}
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, json=dados))
    assert detalhada is not None
    assert (detalhada.publicada_em, detalhada.prazo, detalhada.contrato_declarado) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    "corpo",
    ["não é json", "[]", '{"jobPostingInfo": []}', '{"jobPostingInfo": {"jobDescription": ""}}'],
)
async def test_detalhar_sem_descricao_devolve_none(corpo: str) -> None:
    vaga = await _vaga_mastercard()
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, text=corpo))
    assert detalhada is None


async def test_detalhar_404_devolve_none_e_outro_erro_sobe() -> None:
    vaga = await _vaga_mastercard()
    detalhada, pedidos = await _detalhar(vaga, httpx.Response(404, text="Not Found"))
    assert (detalhada, len(pedidos)) == (None, 1)
    with pytest.raises(ErroDeRede):
        await _detalhar(vaga, httpx.Response(500))


async def test_detalhar_item_de_outra_fonte_ou_de_sitemap_nao_pede_nada() -> None:
    vaga = await _vaga_mastercard()
    sem_caminho = VagaColetada(**{**vaga.__dict__, "id_externo": None})
    outra = VagaColetada(**{**vaga.__dict__, "escopo": "lixo"})
    sitemap = base.UrlListada("https://mastercard.wd1.myworkdayjobs.com/x")
    for item in (sem_caminho, outra, sitemap):
        detalhada, pedidos = await _detalhar(item, _json("detalhe"))
        assert (detalhada, pedidos) == (None, [])


@pytest.fixture
async def http_proibido() -> Any:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"resolver não faz pedido: {pedido.url}")

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(httpx.MockTransport(recusa), relogio, LeitorFixo(), "0.1.0", _sem_dns)
    try:
        yield cli.escopo()
    finally:
        await cli.fechar()


@pytest.mark.parametrize(
    "entrada",
    [
        "https://santander.wd3.myworkdayjobs.com/SantanderCareers",
        " https://santander.wd3.myworkdayjobs.com/SantanderCareers/ ",
        "santander.wd3.myworkdayjobs.com/pt-BR/SantanderCareers",
        "https://santander.wd3.myworkdayjobs.com/en-US/SantanderCareers/job/SAO-PAULO/X_Req1",
        "https://SANTANDER.WD3.myworkdayjobs.com/SantanderCareers/details/X_Req1",
        "https://santander.wd3.myworkdayjobs.com/wday/cxs/santander/SantanderCareers/jobs",
    ],
)
async def test_resolver_le_tenant_site_e_wd_do_endereco(
    entrada: str, http_proibido: HttpEducado
) -> None:
    resolvido = await workday.COLETOR.resolver(entrada, http_proibido)
    assert resolvido == {"identificador": "santander/SantanderCareers", "wd": "wd3"}


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "santander/SantanderCareers",  # sem o endereço não há wd
        "https://santander.wd3.myworkdayjobs.com/",
        "https://santander.wd3.myworkdayjobs.com/pt-BR",
        "https://santander.wd3.myworkdayjobs.com.evil.com/SantanderCareers",
        "https://santander.myworkdayjobs.com/SantanderCareers",
        "https://a.b.wd3.myworkdayjobs.com/SantanderCareers",
        "ftp://santander.wd3.myworkdayjobs.com/SantanderCareers",
        "https://santander.wd3.myworkdayjobs.com/wday/cxs/santander",
        "https://jobs.lever.co/santander",
    ],
)
async def test_resolver_recusa_o_que_nao_e_quadro_do_workday(
    entrada: str, http_proibido: HttpEducado
) -> None:
    with pytest.raises(ValueError):
        await workday.COLETOR.resolver(entrada, http_proibido)
