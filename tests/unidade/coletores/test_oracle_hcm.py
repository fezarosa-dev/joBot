import copy
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import oracle_hcm, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, Item, ResultadoEscopo, UrlListada
from jobot.nucleo.http import ClienteEducado, ErroDeRede, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "oracle_hcm"
HOST = "eeho.fa.us2.oraclecloud.com"
ESCOPO = f"{HOST}|CX_45001|jobsearch|BR"
ESCOPO_JPMC = "jpmc.fa.oraclecloud.com|CX_1001|CX_1001|BR"
API = f"https://{HOST}/hcmRestApi/resources/latest/"
URL_DESCOBERTA = (
    API + "recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.secondaryLocations"
    "&finder=findReqs;siteNumber=CX_45001,facetsList=LOCATIONS%3BWORKPLACE_TYPES%3BPOSTING_DATES,"
    "limit=25,offset=0,sortBy=POSTING_DATES_DESC"
)
BRASIL = "300000000106728"
URL_LISTA = URL_DESCOBERTA + f",selectedLocationsFacet={BRASIL}"
URL_DETALHE = (
    API + "recruitingCEJobRequisitionDetails?expand=all&onlyData=true"
    "&finder=ById;Id=%22348989%22,siteNumber=CX_45001"
)
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str, ext: str = "json") -> str:
    return (PASTA / f"{caso}.{ext}").read_text(encoding="utf-8")


def _dados(caso: str) -> dict[str, Any]:
    carregado: dict[str, Any] = json.loads(_texto(caso))
    return carregado


def _meta(caso: str) -> dict[str, Any]:
    carregado: dict[str, Any] = json.loads(_texto(f"{caso}.meta"))
    return carregado


def _json(caso: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=_texto(caso), headers={"Content-Type": "application/json"})


def _finder(pedido: httpx.Request) -> dict[str, str]:
    """Os parâmetros de dentro do `finder` (`findReqs;a=1,b=2`)."""
    _, _, resto = pedido.url.params["finder"].partition(";")
    return dict(par.split("=", 1) for par in resto.split(","))


def _eh_descoberta(pedido: httpx.Request) -> bool:
    return "selectedLocationsFacet" not in _finder(pedido)


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return Validadores(etag='"v1"', last_modified="Wed, 12 Nov 2026 10:00:00 GMT")


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
        if not fila:
            raise AssertionError(f"pedido inesperado: {pedido.url}")
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
    coletor = copy.copy(oracle_hcm.COLETOR)
    return await _rodar(lambda http: coletor.coletar(escopo, http), *respostas)


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _empresa(
    host: str = HOST, site_number: str = "CX_45001", site: str = "jobsearch", nome: str = ""
) -> Empresa:
    return Empresa(
        nome=nome or host,
        fonte="oracle_hcm",
        identificador=host,
        parametros={"site_number": site_number, "site": site},
    )


def _ctx(*empresas: Empresa, paises: tuple[str, ...] = ("BR",)) -> ContextoColeta:
    return ContextoColeta(empresas=empresas, termos=["dev"], paises=paises)


def _pagina(n: int, inicio: int = 0, total: int = 0) -> dict[str, Any]:
    """Página de lista com `n` vagas de `Id` distinto (a partir de `inicio`)."""
    dados = _dados("normal")
    busca = dados["items"][0]
    modelo = busca["requisitionList"][0]
    busca["requisitionList"] = [
        modelo | {"Id": str(1000 + inicio + i), "Title": f"Vaga {inicio + i}"} for i in range(n)
    ]
    busca["TotalJobsCount"] = total
    return dados


def _lista(n: int, total: int) -> Responder:
    """Descoberta com o `normal`; lista paginada com `n` vagas por página até `total`."""

    def responde(pedido: httpx.Request) -> httpx.Response:
        if _eh_descoberta(pedido):
            return _json("normal")
        offset = int(_finder(pedido)["offset"])
        return httpx.Response(200, json=_pagina(min(n, max(total - offset, 0)), offset, total))

    return responde


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = oracle_hcm.COLETOR
    assert registro.descobrir()["oracle_hcm"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "B"
    assert prova.espera_s == registro.limites("oracle_hcm").espera_s
    assert prova.nome == "Oracle HCM"


def test_escopos_um_por_empresa_e_pais() -> None:
    ctx = _ctx(
        _empresa(),
        _empresa(" JPMC.fa.oraclecloud.com ", "CX_1001", "CX_1001"),
        _empresa(),
        paises=("BR", " mx", "BR", "x1"),
    )
    assert list(copy.copy(oracle_hcm.COLETOR).escopos(ctx)) == [
        ESCOPO,
        f"{HOST}|CX_45001|jobsearch|MX",
        ESCOPO_JPMC,
        "jpmc.fa.oraclecloud.com|CX_1001|CX_1001|MX",
    ]


def test_sem_pais_busca_o_brasil() -> None:
    coletor = copy.copy(oracle_hcm.COLETOR)
    assert list(coletor.escopos(_ctx(_empresa(), paises=()))) == [ESCOPO]


@pytest.mark.parametrize(
    ("host", "site_number", "site"),
    [
        ("evil.com", "CX_1", "s"),  # fora do Oracle Cloud
        ("eeho.fa.us2.oraclecloud.com.evil.com", "CX_1", "s"),
        ("eeho.fa.us2.oraclecloud.com/x", "CX_1", "s"),
        ("-eeho.oraclecloud.com", "CX_1", "s"),
        (HOST, "", "jobsearch"),  # sem site_number
        (HOST, "CX_1", ""),  # sem site
        (HOST, "CX 1", "jobsearch"),
        (HOST, "CX_1|BR", "jobsearch"),
        (HOST, "CX_1", "../jobsearch"),
    ],
)
def test_escopos_pula_empresa_sem_parametro_valido(host: str, site_number: str, site: str) -> None:
    coletor = copy.copy(oracle_hcm.COLETOR)  # `escopos` guarda estado: não sujar o global
    assert list(coletor.escopos(_ctx(_empresa(host, site_number, site)))) == []


async def test_normal() -> None:
    coletor = copy.copy(oracle_hcm.COLETOR)
    coletor.escopos(_ctx(_empresa(nome="Oracle")))
    resultado, pedidos = await _rodar(
        lambda http: coletor.coletar(ESCOPO, http), _json("normal"), _json("normal")
    )
    # o exemplo é um recorte (5 de 8 vagas): a lista não veio inteira, nada fecha na hora
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.listagem_incompleta")
    assert (resultado.pedidos, len(pedidos)) == (2, 2)
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert (primeira.fonte, primeira.escopo, primeira.empresa) == ("oracle_hcm", ESCOPO, "Oracle")
    assert primeira.url == (
        f"https://{HOST}/hcmUI/CandidateExperience/en/sites/jobsearch/job/344470"
    )
    assert primeira.id_externo == "344470"
    assert primeira.titulo == (
        "LAD PMO Business Process - Vaga Exclusiva para Pessoa com Deficiência (PCD)"
    )
    assert primeira.locais == ("SAO PAULO, SP, Brazil",)
    assert primeira.publicada_em == datetime(2026, 11, 13, tzinfo=UTC)
    assert primeira.prazo is None
    assert primeira.descricao == "" and primeira.descricao_formato == "html"  # vem no `detalhar`
    assert all(v.url.startswith("https://") for v in vagas)


async def test_lista_inteira_e_ok() -> None:
    resultado, pedidos = await _coletar(_lista(25, 3))
    assert (resultado.estado, resultado.motivo, len(resultado.vagas)) == ("ok", None, 3)
    assert len(pedidos) == 2


async def test_sem_escopos_a_empresa_e_o_primeiro_rotulo_do_host() -> None:
    resultado, _ = await _coletar(_lista(25, 3))
    assert {v.empresa for v in _vagas(resultado)} == {"eeho"}


async def test_locais_secundarios_e_prazo() -> None:
    pagina = _pagina(1, 0, 1)
    vaga = pagina["items"][0]["requisitionList"][0]
    vaga["secondaryLocations"] = [{"Name": "Rio de Janeiro, RJ, Brazil", "CountryCode": "BR"}]
    vaga["PostingEndDate"] = "2026-12-01"
    vaga["WorkplaceType"] = "Hybrid"
    resultado, _ = await _coletar(_json("normal"), httpx.Response(200, json=pagina))
    [lida] = _vagas(resultado)
    assert lida.locais == ("SAO PAULO, SP, Brazil", "Rio de Janeiro, RJ, Brazil")
    assert lida.prazo == date(2026, 12, 1)
    assert lida.modalidade_declarada == "Hybrid"


async def test_geografia_lida_da_resposta_de_cada_empresa() -> None:
    # o id do Brasil muda por empresa: o da JPMorgan não é o da Oracle (apêndice 3.3)
    _, pedidos = await _coletar(
        _json("outra_empresa"), httpx.Response(200, json=_pagina(1, 0, 1)), escopo=ESCOPO_JPMC
    )
    assert _finder(pedidos[1])["selectedLocationsFacet"] == "300000000289141"
    assert _finder(pedidos[1])["siteNumber"] == "CX_1001"


async def test_escopo_de_outro_pais_filtra_pela_faceta_dele() -> None:
    _, pedidos = await _coletar(
        _json("normal"), httpx.Response(200, json=_pagina(1, 0, 1)), escopo=ESCOPO[:-2] + "MX"
    )
    assert _finder(pedidos[1])["selectedLocationsFacet"] == "300000000149103"  # Mexico


async def test_faceta_de_estado_ou_cidade_nao_vale_como_pais() -> None:
    dados = _dados("normal")
    busca = dados["items"][0]
    busca["locationsFacet"] = [f for f in busca["locationsFacet"] if "," in f["Name"]]
    assert busca["locationsFacet"]  # sobram "SP, Brazil" e a cidade
    resultado, pedidos = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 2  # a descoberta sem filtro e a com keyword; nada de lista


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 2  # sem faceta do país nas duas descobertas, nem pede a lista
    assert [_finder(p).get("keyword") for p in pedidos] == [None, '"Brazil"']


async def test_oracle_descoberta_cortada_repete_com_keyword() -> None:
    # resposta real (T55c): a descoberta sem filtro só traz as facetas dos países com mais vagas
    # e o Brasil fica de fora; com keyword=Brazil a faceta aparece (decisão A47)
    resultado, pedidos = await _coletar(
        _json("descoberta_sem_filtro"), _json("descoberta_keyword"), _json("lista_br")
    )
    assert len(pedidos) == 3
    assert "keyword" not in _finder(pedidos[0])
    assert "keyword=%22Brazil%22" in str(pedidos[1].url)  # na mesma URL do finder
    assert _finder(pedidos[1])["keyword"] == '"Brazil"'
    assert "selectedLocationsFacet" not in _finder(pedidos[1])
    assert str(pedidos[1].url) == URL_DESCOBERTA + ",keyword=%22Brazil%22"
    # a lista vai filtrada só pela faceta, sem keyword
    assert str(pedidos[2].url) == URL_LISTA
    assert "keyword" not in _finder(pedidos[2])
    # o exemplo é um recorte (5 de 8 vagas): a lista não veio inteira
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.listagem_incompleta")
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    assert all(v.locais[0].endswith("Brazil") for v in vagas)


async def test_oracle_sem_faceta_nas_duas_descobertas_termina_ok_vazio() -> None:
    keyword = _dados("descoberta_keyword")
    busca = keyword["items"][0]
    busca["locationsFacet"] = [f for f in busca["locationsFacet"] if f["Name"] != "Brazil"]
    assert busca["locationsFacet"]  # sobra a Índia
    resultado, pedidos = await _coletar(
        _json("descoberta_sem_filtro"), httpx.Response(200, json=keyword)
    )
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 2
    assert _finder(pedidos[1])["keyword"] == '"Brazil"'


async def test_oracle_faceta_na_primeira_descoberta_nao_repete() -> None:
    resultado, pedidos = await _coletar(_json("normal"), _json("normal"))
    assert len(pedidos) == 2
    assert [_finder(p).get("keyword") for p in pedidos] == [None, None]
    assert len(resultado.vagas) == 5


async def test_oracle_keyword_e_o_nome_em_ingles_do_pais_do_escopo() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo=ESCOPO[:-2] + "MX")
    assert [_finder(p).get("keyword") for p in pedidos] == [None, '"Mexico"']


async def test_oracle_pais_sem_nome_em_ingles_nao_repete() -> None:
    resultado, pedidos = await _coletar(_json("vazio"), escopo=ESCOPO[:-2] + "ZZ")
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


@pytest.mark.parametrize(
    "corpo",
    ["não é json", '{"items": []}', '{"items": [{"TotalJobsCount": 3}]}'],
)
async def test_oracle_descoberta_com_keyword_fora_do_formato_falhou(corpo: str) -> None:
    resultado, pedidos = await _coletar(
        _json("descoberta_sem_filtro"), httpx.Response(200, text=corpo)
    )
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"
    assert len(pedidos) == 2


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("normal"), _json("formato_mudou"))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_item_ilegivel_deixa_parcial_com_as_outras() -> None:
    pagina = _pagina(3, 0, 3)
    lista = pagina["items"][0]["requisitionList"]
    lista[1]["Id"] = "../../x"  # o Id entra na URL: só dígitos ASCII
    lista[2]["Title"] = ""
    resultado, _ = await _coletar(_json("normal"), httpx.Response(200, json=pagina))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.titulo for v in _vagas(resultado)] == ["Vaga 0"]


@pytest.mark.parametrize(
    "corpo",
    [
        "não é json",
        "[]",
        '{"items": []}',
        '{"items": [1]}',
        '{"items": [{"TotalJobsCount": 3}]}',  # sem facetas
        '{"items": [{"TotalJobsCount": 3, "locationsFacet": {}}]}',
        '{"items": [{"TotalJobsCount": true, "locationsFacet": []}]}',
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
        '{"items": [{"TotalJobsCount": 2, "requisitionList": {}}]}',
        '{"items": [{"TotalJobsCount": "2", "requisitionList": []}]}',
        '{"items": [{"TotalJobsCount": 2, "requisitionList": [1, "x"]}]}',
        '{"items": [{"TotalJobsCount": 1, "requisitionList": [{"Id": 7, "Title": "x"}]}]}',
    ],
)
async def test_primeira_pagina_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(_json("normal"), httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_paginacao_limit_e_offset_dentro_do_finder() -> None:
    resultado, pedidos = await _coletar(_lista(25, 60))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 4)
    assert [v.titulo for v in _vagas(resultado)] == [f"Vaga {i}" for i in range(60)]
    finders = [_finder(p) for p in pedidos[1:]]
    assert [f["offset"] for f in finders] == ["0", "25", "50"]
    assert {f["limit"] for f in finders} == {"25"}
    assert all(set(p.url.params) == {"onlyData", "expand", "finder"} for p in pedidos)


async def test_paginacao_para_quando_o_total_e_atingido_numa_pagina_cheia() -> None:
    resultado, pedidos = await _coletar(_lista(25, 25))
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 25, 2)


async def test_paginacao_para_quando_a_pagina_vem_vazia() -> None:
    def responde(pedido: httpx.Request) -> httpx.Response:
        if _eh_descoberta(pedido):
            return _json("normal")
        offset = int(_finder(pedido)["offset"])
        return httpx.Response(200, json=_pagina(25 if offset == 0 else 0, offset, 5000))

    resultado, pedidos = await _coletar(responde)
    assert len(pedidos) == 3
    # a lista acabou antes do total declarado: não vale como lista inteira
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.listagem_incompleta")
    assert len(resultado.vagas) == 25


async def test_total_absurdo_nao_prende_o_coletor() -> None:
    def responde(pedido: httpx.Request) -> httpx.Response:
        if _eh_descoberta(pedido):
            return _json("normal")
        offset = int(_finder(pedido)["offset"])
        assert offset < 25 * oracle_hcm.MAX_PAGINAS  # sem teto, o teste falha aqui, não trava
        return httpx.Response(200, json=_pagina(25, offset, 10**12))

    resultado, pedidos = await _coletar(responde)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert len(resultado.vagas) == 25 * oracle_hcm.MAX_PAGINAS
    assert len(pedidos) == 1 + oracle_hcm.MAX_PAGINAS


async def test_erro_depois_de_uma_pagina_e_parcial_com_as_vagas_lidas() -> None:
    resultado, _ = await _coletar(
        _json("normal"), httpx.Response(200, json=_pagina(25, 0, 45)), httpx.Response(500)
    )
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(resultado.vagas) == 25


async def test_404_depois_da_primeira_pagina_nao_e_empresa_nao_encontrada() -> None:
    resultado, _ = await _coletar(
        _json("normal"), httpx.Response(200, json=_pagina(25, 0, 45)), httpx.Response(404)
    )
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(resultado.vagas) == 25


async def test_pagina_seguinte_ilegivel_e_parcial_com_as_lidas() -> None:
    resultado, _ = await _coletar(
        _json("normal"),
        httpx.Response(200, json=_pagina(25, 0, 45)),
        httpx.Response(200, text="[]"),
    )
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 25


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
    waf = "<html><body><h1>W4S-402: Blocked by WAF4SaaS</h1></body></html>"
    resultado, pedidos = await _coletar(httpx.Response(403, text=waf))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_json("normal"), _json("normal"))
    assert [p.method for p in pedidos] == ["GET", "GET"]
    assert [str(p.url) for p in pedidos] == [URL_DESCOBERTA, URL_LISTA]
    assert str(pedidos[1].url) == _meta("normal")["url"]  # a URL da conferência ao vivo
    assert dict(pedidos[1].url.params) == {
        "onlyData": "true",
        "expand": "requisitionList.secondaryLocations",
        "finder": "findReqs;siteNumber=CX_45001,facetsList=LOCATIONS;WORKPLACE_TYPES;"
        f"POSTING_DATES,limit=25,offset=0,sortBy=POSTING_DATES_DESC,selectedLocationsFacet={BRASIL}",
    }
    for pedido in pedidos:  # a captura não mostrou validador: nunca pede condicional
        assert "If-None-Match" not in pedido.headers
        assert "If-Modified-Since" not in pedido.headers


@pytest.mark.parametrize(
    "escopo",
    [
        f"{HOST}|CX_45001|jobsearch",  # sem país
        f"{HOST}|CX_45001|jobsearch|br",
        f"{HOST}|CX_45001|jobsearch|BR|x",
        "evil.com|CX_45001|jobsearch|BR",
        f"{HOST}#/x|CX_45001|jobsearch|BR",
        f"{HOST}|CX_45001,limit=999|jobsearch|BR",
        f"{HOST}|CX_45001|job/search|BR",
    ],
)
async def test_escopo_malformado_nao_faz_pedido(escopo: str) -> None:
    with pytest.raises(ValueError):
        await _coletar(_json("normal"), escopo=escopo)


def _vaga_para_detalhar(**campos: Any) -> VagaColetada:
    base: dict[str, Any] = {
        "fonte": "oracle_hcm",
        "escopo": ESCOPO,
        "url": f"https://{HOST}/hcmUI/CandidateExperience/en/sites/jobsearch/job/348989",
        "titulo": "Engenheiro(a) DevOps",
        "empresa": "Oracle",
        "descricao_formato": "html",
        "id_externo": "348989",
    }
    return VagaColetada(**(base | campos))


async def _detalhar(
    item: Item, *respostas: httpx.Response | Responder
) -> tuple[VagaColetada | None, list[httpx.Request]]:
    return await _rodar(lambda http: oracle_hcm.COLETOR.detalhar(item, http), *respostas)


async def test_detalhar_le_descricao_e_datas() -> None:
    item = _vaga_para_detalhar()
    vaga, pedidos = await _detalhar(item, _json("detalhe"))
    assert [(p.method, str(p.url)) for p in pedidos] == [("GET", URL_DETALHE)]
    assert str(pedidos[0].url) == _meta("detalhe")["url"]
    assert vaga is not None
    dados = _dados("detalhe")["items"][0]
    assert vaga.descricao == (
        dados["ExternalDescriptionStr"] + "\n" + dados["ExternalResponsibilitiesStr"]
    )
    assert "Only Oracle brings" not in vaga.descricao  # o texto institucional fica de fora
    assert vaga.descricao_formato == "html"
    assert vaga.publicada_em == datetime(2026, 10, 29, 4, 9, 58, tzinfo=UTC)
    assert (vaga.url, vaga.titulo, vaga.id_externo) == (item.url, item.titulo, item.id_externo)


async def test_detalhar_mantem_a_data_da_lista_e_le_o_prazo() -> None:
    lista = datetime(2026, 11, 1, tzinfo=UTC)
    dados = _dados("detalhe")
    dados["items"][0]["ExternalPostedEndDate"] = "2026-12-15T23:59:00+00:00"
    vaga, _ = await _detalhar(
        _vaga_para_detalhar(publicada_em=lista), httpx.Response(200, json=dados)
    )
    assert vaga is not None
    assert (vaga.publicada_em, vaga.prazo) == (lista, date(2026, 12, 15))


@pytest.mark.parametrize(
    "corpo",
    [
        "não é json",
        '{"items": []}',
        '{"items": [{"ExternalDescriptionStr": "", "ExternalResponsibilitiesStr": null}]}',
    ],
)
async def test_detalhar_sem_descricao_devolve_none(corpo: str) -> None:
    vaga, _ = await _detalhar(_vaga_para_detalhar(), httpx.Response(200, text=corpo))
    assert vaga is None


async def test_detalhar_404_devolve_none_e_outro_erro_sobe() -> None:
    vaga, _ = await _detalhar(_vaga_para_detalhar(), httpx.Response(404))
    assert vaga is None
    with pytest.raises(ErroDeRede):
        await _detalhar(_vaga_para_detalhar(), httpx.Response(500))


@pytest.mark.parametrize(
    "item",
    [
        UrlListada(f"https://{HOST}/hcmUI/CandidateExperience/en/sites/jobsearch/job/1"),
        _vaga_para_detalhar(id_externo="34%22,siteNumber=X"),
        _vaga_para_detalhar(id_externo=None),
        _vaga_para_detalhar(escopo="evil.com|CX_1|s|BR"),
    ],
)
async def test_detalhar_item_fora_do_formato_nao_pede_nada(item: Item) -> None:
    vaga, pedidos = await _detalhar(item, _json("detalhe"))
    assert (vaga, pedidos) == (None, [])


async def _resolver(
    identificador: str, *respostas: httpx.Response | Responder
) -> tuple[dict[str, str], list[httpx.Request]]:
    coletor = oracle_hcm.COLETOR
    resultado, pedidos = await _rodar(
        lambda http: coletor.resolver(identificador, http), *respostas
    )
    return dict(resultado), pedidos


def _pagina_carreira(status: int = 200) -> httpx.Response:
    texto = _texto("pagina_carreira", "html")
    return httpx.Response(status, text=texto, headers={"Content-Type": "text/html"})


@pytest.mark.parametrize(
    "endereco",
    [
        f"https://{HOST}/hcmUI/CandidateExperience/en/sites/jobsearch/jobs",
        f"https://{HOST.upper()}/hcmUI/CandidateExperience/pt-BR/sites/jobsearch/job/348989?x=1",
        f" {HOST}/hcmUI/CandidateExperience/en/sites/jobsearch ",
    ],
)
async def test_resolver_le_host_site_e_site_number(endereco: str) -> None:
    parametros, pedidos = await _resolver(endereco, _pagina_carreira())
    assert parametros == {"identificador": HOST, "site_number": "CX_45001", "site": "jobsearch"}
    assert [str(p.url) for p in pedidos] == [_meta("pagina_carreira")["url"]]


@pytest.mark.parametrize(
    "endereco",
    [
        HOST,  # sem o site
        "https://evil.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs",
        f"https://{HOST}.evil.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs",
        f"ftp://{HOST}/hcmUI/CandidateExperience/en/sites/jobsearch/jobs",
        f"https://{HOST}/hcmUI/CandidateExperience/en/jobs",
        f"https://{HOST}/hcmUI/CandidateExperience/en/sites/",
        f"https://{HOST}/hcmUI/CandidateExperience/en/sites/job%2Fsearch/jobs",
    ],
)
async def test_resolver_recusa_o_que_nao_e_site_do_oracle_sem_pedido(endereco: str) -> None:
    def proibido(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"pedido feito: {pedido.url}")

    with pytest.raises(ValueError):
        await _resolver(endereco, proibido)


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, text="<html><body>sem atributo</body></html>"),
        httpx.Response(200, text='<div data-sitenumber="CX 1,x"></div>'),
        httpx.Response(404),
    ],
)
async def test_resolver_sem_site_number_na_pagina_da_value_error(resposta: httpx.Response) -> None:
    with pytest.raises(ValueError):
        await _resolver(f"https://{HOST}/hcmUI/CandidateExperience/en/sites/jobsearch", resposta)
