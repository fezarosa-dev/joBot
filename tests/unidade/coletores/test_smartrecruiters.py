import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, registro, smartrecruiters
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, ErroDeRede, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "smartrecruiters"
URL_LISTA = (
    "https://api.smartrecruiters.com/v1/companies/NielsenIQ/postings?limit=100&offset=0&country=br"
)
URL_DETALHE = "https://api.smartrecruiters.com/v1/companies/NielsenIQ/postings/744000161500208"
ESCOPO = "NielsenIQ|br"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _dados(caso: str) -> dict[str, object]:
    carregado: dict[str, object] = json.loads(_texto(caso))
    return carregado


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


async def _rodar[T](
    chamada: Callable[[HttpEducado], Awaitable[T]],
    *respostas: httpx.Response | Responder,
    leitor: LeitorFixo | None = None,
    condicional: bool = False,
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
        httpx.MockTransport(servidor), relogio, leitor or LeitorFixo(), "0.1.0", resolver=_sem_dns
    )
    try:
        resultado = await chamada(cli.escopo(condicional=condicional))
    finally:
        await cli.fechar()
    return resultado, pedidos


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = ESCOPO,
    leitor: LeitorFixo | None = None,
    condicional: bool = False,
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    return await _rodar(
        lambda http: smartrecruiters.COLETOR.coletar(escopo, http),
        *respostas,
        leitor=leitor,
        condicional=condicional,
    )


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """O `resolver` só lê o texto: qualquer pedido é erro do teste."""

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
    prova: Coletor = smartrecruiters.COLETOR
    assert registro.descobrir()["smartrecruiters"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("api.smartrecruiters.com",)


def _ctx(paises: Sequence[str], *identificadores: str) -> ContextoColeta:
    empresas = [Empresa(nome=i, fonte="smartrecruiters", identificador=i) for i in identificadores]
    return ContextoColeta(empresas=empresas, termos=["dev"], paises=paises)


def test_escopos_um_por_empresa_e_pais() -> None:
    ctx = _ctx(["BR", "pt", "BR"], "NielsenIQ", "BoschGroup", "NielsenIQ")
    assert list(smartrecruiters.COLETOR.escopos(ctx)) == [
        "NielsenIQ|br",
        "NielsenIQ|pt",
        "BoschGroup|br",
        "BoschGroup|pt",
    ]


def test_escopos_sem_pais_valido_ou_sem_pais_nao_pedem_nada() -> None:
    assert list(smartrecruiters.COLETOR.escopos(_ctx([], "NielsenIQ"))) == []
    assert list(smartrecruiters.COLETOR.escopos(_ctx(["", "bra", "b1", "b|"], "NielsenIQ"))) == []


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 5  # totalFound=6, mas a página curta encerra a listagem
    primeira = vagas[0]
    assert primeira.fonte == "smartrecruiters" and primeira.escopo == ESCOPO
    assert primeira.url == "https://jobs.smartrecruiters.com/NielsenIQ/744000161500208"
    assert primeira.titulo == "Analista de Dados e Relacionamento"
    assert primeira.empresa == "NielsenIQ"
    assert primeira.id_externo == "744000161500208"
    assert primeira.locais == ("Barueri, SP, Brazil",)
    assert primeira.modalidade_declarada == "hybrid"
    assert primeira.publicada_em == datetime(2026, 11, 13, 14, 26, 2, 232000, tzinfo=UTC)
    assert primeira.descricao == "" and primeira.descricao_formato == "html"
    assert primeira.etiquetas == ("General Business",)
    assert primeira.url_candidatura is None and primeira.prazo is None
    assert all(v.url.startswith(("https://", "http://")) for v in vagas)
    assert len(pedidos) == 1


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_remoto_declarado_e_local_montado_sem_full_location() -> None:
    dados = _dados("normal")
    itens = dados["content"]
    assert isinstance(itens, list)
    itens[0]["location"] = {"city": "Porto", "country": "pt", "remote": True, "hybrid": False}
    itens[1]["location"] = {"remote": False, "hybrid": False}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vagas = _vagas(resultado)
    assert (vagas[0].modalidade_declarada, vagas[0].locais) == ("remote", ("Porto, pt",))
    assert (vagas[1].modalidade_declarada, vagas[1].locais) == (None, ())


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["744000161500208"]


@pytest.mark.parametrize(
    "corpo",
    [
        '{"postings": []}',
        "[]",
        '{"content": {}}',
        "isto não é json",
        '{"content": [1, "x"], "totalFound": 2}',
        '{"content": [], "totalFound": "muitas"}',
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _dados("normal")
    itens = dados["content"]
    assert isinstance(itens, list)
    itens[0] |= {"releasedDate": "ontem", "location": "Barueri", "department": 3, "function": None}
    itens[1] |= {"releasedDate": "2026-11-13T14:26:02", "id": 7}  # sem fuso; id inteiro
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vagas = _vagas(resultado)
    assert (vagas[0].publicada_em, vagas[0].locais, vagas[0].etiquetas) == (None, (), ())
    assert (vagas[1].publicada_em, vagas[1].id_externo) == (None, "7")
    assert vagas[1].url == "https://jobs.smartrecruiters.com/NielsenIQ/7"


async def test_id_que_nao_serve_de_caminho_pula_a_vaga() -> None:
    dados = _dados("normal")
    itens = dados["content"]
    assert isinstance(itens, list)
    itens[0]["id"] = "../x?y#z"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 4


async def test_paginacao() -> None:
    modelo = _dados("normal")["content"]
    assert isinstance(modelo, list)

    def pagina(offset: int, n: int) -> httpx.Response:
        itens = [
            modelo[0] | {"id": str(offset + i), "name": f"Vaga {offset + i}"} for i in range(n)
        ]
        return httpx.Response(
            200, json={"offset": offset, "limit": 100, "totalFound": 103, "content": itens}
        )

    def responde(pedido: httpx.Request) -> httpx.Response:
        return pagina(
            int(pedido.url.params["offset"]), 100 if pedido.url.params["offset"] == "0" else 3
        )

    resultado, pedidos = await _coletar(responde)
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 2)
    assert [v.id_externo for v in _vagas(resultado)] == [str(i) for i in range(103)]
    assert [p.url.params["offset"] for p in pedidos] == ["0", "100"]
    assert {p.url.params["limit"] for p in pedidos} == {"100"}


async def test_paginacao_para_quando_o_total_e_atingido_numa_pagina_cheia() -> None:
    modelo = _dados("normal")["content"]
    assert isinstance(modelo, list)
    cheia = [modelo[0] | {"id": str(i)} for i in range(100)]
    resposta = httpx.Response(200, json={"totalFound": 100, "content": cheia})
    resultado, pedidos = await _coletar(lambda _: resposta)
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 100, 1)


async def test_paginacao_para_quando_a_pagina_vem_vazia() -> None:
    # totalFound mente (acima do que existe) e a página cheia seguinte vem vazia
    modelo = _dados("normal")["content"]
    assert isinstance(modelo, list)
    cheia = [modelo[0] | {"id": str(i)} for i in range(100)]

    def responde(pedido: httpx.Request) -> httpx.Response:
        itens = cheia if pedido.url.params["offset"] == "0" else []
        return httpx.Response(200, json={"totalFound": 5000, "content": itens})

    resultado, pedidos = await _coletar(responde)
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 100, 2)


async def test_total_absurdo_nao_prende_o_coletor() -> None:
    modelo = _dados("normal")["content"]
    assert isinstance(modelo, list)
    cheia = [modelo[0] | {"id": str(i)} for i in range(100)]
    resposta = httpx.Response(200, json={"totalFound": 10**12, "content": cheia})
    resultado, pedidos = await _coletar(lambda _: resposta)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert len(pedidos) == smartrecruiters.MAX_PAGINAS


async def test_pais_vem_do_escopo_e_a_caixa_do_identificador_fica() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo="NielsenIQ|pt")
    assert pedidos[0].url.params["country"] == "pt"
    assert pedidos[0].url.path == "/v1/companies/NielsenIQ/postings"
    _, pedidos = await _coletar(_json("vazio"), escopo="nielseniq|br")
    assert pedidos[0].url.path == "/v1/companies/nielseniq/postings"


async def test_pais_do_contexto_chega_ao_pedido() -> None:
    escopos = smartrecruiters.COLETOR.escopos(_ctx(["PT"], "NielsenIQ"))
    _, pedidos = await _coletar(_json("vazio"), escopo=escopos[0])
    assert dict(pedidos[0].url.params)["country"] == "pt"


async def test_escopo_estranho_nao_muda_o_caminho() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo="../x?y#z|br")
    assert [p.url.raw_path for p in pedidos] == [
        b"/v1/companies/..%2Fx%3Fy%23z/postings?limit=100&offset=0&country=br"
    ]


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

    monkeypatch.setattr(smartrecruiters, "juntar_paginas", espia)
    etag = 'W/"2667-dzFUK+0AptpjOXS5LUsD+nJ3wxY"'

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _json("normal", ETag=etag)

    leitor = LeitorFixo({URL_LISTA: Validadores(etag, None)})
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
    assert str(pedido.url) == URL_LISTA
    assert dict(pedido.url.params) == {"limit": "100", "offset": "0", "country": "br"}


async def _detalhar(
    item: base.Item, *respostas: httpx.Response | Responder
) -> tuple[VagaColetada | None, list[httpx.Request]]:
    return await _rodar(
        lambda http: smartrecruiters.COLETOR.detalhar(item, http),
        *respostas,
    )


async def _vaga_da_lista() -> VagaColetada:
    resultado, _ = await _coletar(_json("normal"))
    return _vagas(resultado)[0]


async def test_detalhar_le_job_ad_sections() -> None:
    vaga = await _vaga_da_lista()
    detalhada, pedidos = await _detalhar(vaga, _json("detalhe"))
    assert detalhada is not None
    assert [str(p.url) for p in pedidos] == [URL_DETALHE]
    assert pedidos[0].method == "GET"
    secoes = _dados("detalhe")["jobAd"]["sections"]  # type: ignore[index]
    assert detalhada.descricao_formato == "html"
    assert secoes["jobDescription"]["text"] in detalhada.descricao
    assert "Descrição da vaga" in detalhada.descricao  # o título da seção entra
    assert detalhada.descricao.index("Descrição da vaga") < detalhada.descricao.index(
        secoes["jobDescription"]["text"]
    )
    # o resto da vaga fica como veio da lista (a URL é a chave: não muda)
    assert (detalhada.url, detalhada.titulo, detalhada.id_externo) == (
        vaga.url,
        vaga.titulo,
        vaga.id_externo,
    )
    assert detalhada.escopo == vaga.escopo and detalhada.empresa == vaga.empresa


async def test_detalhar_nao_guarda_o_criador() -> None:
    vaga = await _vaga_da_lista()
    dados = _dados("detalhe")
    dados["creator"] = {"name": "Fulana de Tal", "avatarUrl": "https://x.example/f.png"}
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, json=dados))
    assert detalhada is not None
    assert "Fulana" not in detalhada.para_json() and "avatar" not in detalhada.para_json()


async def test_detalhar_junta_so_as_secoes_com_texto_e_escapa_o_titulo() -> None:
    vaga = await _vaga_da_lista()
    dados = {
        "jobAd": {
            "sections": {
                "companyDescription": {"title": "A <empresa>", "text": ""},
                "jobDescription": {"title": "Vaga", "text": "<p>faz isto</p>"},
                "qualifications": {"title": "Requisitos", "text": "<ul><li>x</li></ul>"},
                "additionalInformation": {"title": "Mais", "text": None},
                "inesperada": {"title": "Fora", "text": "<p>não entra</p>"},
            }
        }
    }
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, json=dados))
    assert detalhada is not None
    assert "<p>faz isto</p>" in detalhada.descricao and "<li>x</li>" in detalhada.descricao
    assert detalhada.descricao.index("faz isto") < detalhada.descricao.index("Requisitos")
    assert "A <empresa>" not in detalhada.descricao and "&lt;empresa&gt;" not in detalhada.descricao
    assert "Mais" not in detalhada.descricao and "não entra" not in detalhada.descricao


@pytest.mark.parametrize(
    "corpo",
    [
        '{"jobAd": {}}',
        '{"jobAd": {"sections": []}}',
        "[]",
        "não é json",
        '{"jobAd": {"sections": {}}}',
    ],
)
async def test_detalhar_sem_secoes_devolve_none(corpo: str) -> None:
    vaga = await _vaga_da_lista()
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, text=corpo))
    assert detalhada is None


async def test_detalhar_404_devolve_none_e_outro_erro_sobe() -> None:
    vaga = await _vaga_da_lista()
    detalhada, pedidos = await _detalhar(vaga, httpx.Response(404, text="Not Found"))
    assert (detalhada, len(pedidos)) == (None, 1)
    with pytest.raises(ErroDeRede):
        await _detalhar(vaga, httpx.Response(500))


async def test_detalhar_usa_o_identificador_com_maiusculas_do_escopo() -> None:
    vaga = await _vaga_da_lista()
    _, pedidos = await _detalhar(vaga, _json("detalhe"))
    assert pedidos[0].url.path == "/v1/companies/NielsenIQ/postings/744000161500208"


async def test_detalhar_item_sem_id_ou_de_sitemap_nao_pede_nada() -> None:
    vaga = await _vaga_da_lista()
    sem_id = VagaColetada(**{**vaga.__dict__, "id_externo": None})
    sitemap = base.UrlListada("https://jobs.smartrecruiters.com/NielsenIQ/1")
    for item in (sem_id, sitemap):
        detalhada, pedidos = await _detalhar(item, _json("detalhe"))
        assert (detalhada, pedidos) == (None, [])


@pytest.mark.parametrize(
    "entrada",
    [
        "NielsenIQ",
        " NielsenIQ ",
        "https://jobs.smartrecruiters.com/NielsenIQ",
        "https://jobs.smartrecruiters.com/NielsenIQ/",
        "jobs.smartrecruiters.com/NielsenIQ/744000161500208-analista-de-dados",
        "https://careers.smartrecruiters.com/NielsenIQ",
        "https://jobs.smartrecruiters.com/oneclick-ui/company/NielsenIQ/publication/c9270513",
        "https://jobs.smartrecruiters.com/external-referrals/company/NielsenIQ/publication/c92",
        "https://api.smartrecruiters.com/v1/companies/NielsenIQ/postings?limit=100",
        "https://api.smartrecruiters.com/v1/companies/NielsenIQ",
    ],
)
async def test_resolver_aceita_url_e_devolve_o_identificador(
    entrada: str, http_proibido: HttpEducado
) -> None:
    resolvido = await smartrecruiters.COLETOR.resolver(entrada, http_proibido)
    assert resolvido == {"identificador": "NielsenIQ"}


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "https://jobs.lever.co/NielsenIQ",
        "https://jobs.smartrecruiters.com/",
        "https://jobs.smartrecruiters.com/oneclick-ui",
        "https://jobs.smartrecruiters.com/oneclick-ui/company",
        "https://jobs.smartrecruiters.com/oneclick-ui/publication/c92",
        "https://jobs.smartrecruiters.com/external-referrals/company",
        "https://jobs.smartrecruiters.com/search",
        "https://api.smartrecruiters.com/v1/companies",
        "https://api.smartrecruiters.com/v1/postings/NielsenIQ",
        "ftp://jobs.smartrecruiters.com/NielsenIQ",
        "Nielsen IQ",
        "NielsenÍQ",
        "x" * 101,
    ],
)
async def test_resolver_recusa_o_que_nao_e_empresa(
    entrada: str, http_proibido: HttpEducado
) -> None:
    with pytest.raises(ValueError):
        await smartrecruiters.COLETOR.resolver(entrada, http_proibido)
