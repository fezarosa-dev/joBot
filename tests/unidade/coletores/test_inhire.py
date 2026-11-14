import json
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, inhire, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, ErroDeRede, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "inhire"
URL_LISTA = "https://api.inhire.app/job-posts/public/pages"
ID_VAGA = "ad3e4c83-e350-4a0d-87c7-52dfea7952f7"
URL_DETALHE = f"{URL_LISTA}/{ID_VAGA}"
ESCOPO = "riachuelo"
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
        lambda http: inhire.COLETOR.coletar(escopo, http),
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


def _jobs(dados: dict[str, object]) -> list[dict[str, object]]:
    jobs = dados["jobsPage"]
    assert isinstance(jobs, list)
    return jobs


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = inhire.COLETOR
    assert registro.descobrir()["inhire"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "B"
    assert prova.hosts == ("api.inhire.app",)


def test_escopos_um_por_empresa_sem_repetir() -> None:
    empresas = [
        Empresa(nome=n, fonte="inhire", identificador=i)
        for n, i in (("Riachuelo", "riachuelo"), ("InHire", "carreiras"), ("Outra", "riachuelo"))
    ]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["br"])
    assert list(inhire.COLETOR.escopos(ctx)) == ["riachuelo", "carreiras"]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert primeira.fonte == "inhire" and primeira.escopo == ESCOPO
    assert primeira.url == f"https://riachuelo.inhire.app/vagas/{ID_VAGA}"
    assert primeira.titulo == "Analista de Planejamento Comercial Pleno"  # sem o espaço da API
    assert primeira.empresa == "Riachuelo"
    assert primeira.id_externo == ID_VAGA
    assert primeira.locais == ("São Paulo, SP, BR",)
    assert primeira.modalidade_declarada == "Hybrid"
    assert primeira.descricao == "" and primeira.descricao_formato == "html"
    assert primeira.publicada_em is None and primeira.contrato_declarado is None
    assert primeira.url_candidatura is None and primeira.prazo is None
    assert [v.modalidade_declarada for v in vagas[:2]] == ["Hybrid", "On-site"]
    assert all(v.url.startswith("https://riachuelo.inhire.app/vagas/") for v in vagas)
    assert len({v.id_externo for v in vagas}) == 5
    assert len(pedidos) == 1


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == [ID_VAGA]


@pytest.mark.parametrize(
    "corpo",
    [
        "[]",
        "{}",
        '{"tenantName": "X"}',
        '{"jobsPage": {}}',
        '{"jobsPage": null}',
        "isto não é json",
        '{"tenantName": "X", "jobsPage": [1, "x"]}',
        '{"tenantName": "X", "jobsPage": [{"jobId": "a"}]}',
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _dados("normal")
    jobs = _jobs(dados)
    jobs[0] |= {"location": 3, "workplaceType": ["Remote"], "contractType": 7}
    jobs[1] |= {"jobId": 7, "location": "  ", "workplaceType": ""}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    assert (vagas[0].locais, vagas[0].modalidade_declarada, vagas[0].contrato_declarado) == (
        (),
        None,
        None,
    )
    assert (vagas[1].id_externo, vagas[1].locais, vagas[1].modalidade_declarada) == ("7", (), None)
    assert vagas[1].url == "https://riachuelo.inhire.app/vagas/7"


async def test_sem_nome_da_empresa_cai_no_identificador() -> None:
    dados = _dados("normal")
    dados["tenantName"] = None
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    assert {v.empresa for v in _vagas(resultado)} == {ESCOPO}


async def test_contrato_da_lista_quando_vier() -> None:
    dados = _dados("normal")
    jobs = _jobs(dados)
    jobs[0]["contractType"] = ["CLT", "PJ"]
    jobs[1]["contractType"] = "Estágio"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    vagas = _vagas(resultado)
    assert [v.contrato_declarado for v in vagas[:3]] == ["CLT, PJ", "Estágio", None]


@pytest.mark.parametrize("id_vaga", ["../x?y#z", "a b", "", "x" * 101, True])
async def test_job_id_que_nao_serve_de_caminho_pula_a_vaga(id_vaga: object) -> None:
    dados = _dados("normal")
    _jobs(dados)[0]["jobId"] = id_vaga
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 4


async def test_404_empresa_nao_encontrada() -> None:
    resultado, pedidos = await _coletar(_json("nao_encontrado", 404), escopo="inhire")
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.empresa_nao_encontrada"
    assert (resultado.pedidos, len(pedidos)) == (1, 1)


@pytest.mark.parametrize("escopo", ["x.evil.com/#", "Riachuelo", "-a", "a_b", "", "x" * 64])
async def test_identificador_que_nao_e_subdominio_nao_faz_pedido(escopo: str) -> None:
    resultado, pedidos = await _coletar(_json("normal"), escopo=escopo)
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.empresa_nao_encontrada"
    assert (resultado.pedidos, pedidos) == (0, [])


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


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_sem_validador_na_captura_nao_pede_condicional() -> None:
    # a resposta não traz ETag nem Last-Modified: coletar não usa `condicional=True`
    leitor = LeitorFixo({URL_LISTA: Validadores('W/"x"', "Fri, 13 Nov 2026 00:00:00 GMT")})
    resultado, pedidos = await _coletar(_json("normal"), leitor=leitor, condicional=True)
    assert resultado.estado == "ok"
    assert "if-none-match" not in pedidos[0].headers
    assert "if-modified-since" not in pedidos[0].headers


async def test_endereco_e_cabecalho_x_tenant() -> None:
    _, pedidos = await _coletar(_json("vazio"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert str(pedido.url) == URL_LISTA
    assert pedido.headers["X-Tenant"] == ESCOPO
    assert not {"origin", "cookie", "authorization", "referer"} & set(pedido.headers)
    _, pedidos = await _coletar(_json("vazio"), escopo="carreiras")
    assert pedidos[0].headers["X-Tenant"] == "carreiras"
    assert str(pedidos[0].url) == URL_LISTA


async def _detalhar(
    item: base.Item, *respostas: httpx.Response | Responder
) -> tuple[VagaColetada | None, list[httpx.Request]]:
    return await _rodar(lambda http: inhire.COLETOR.detalhar(item, http), *respostas)


async def _vaga_da_lista() -> VagaColetada:
    resultado, _ = await _coletar(_json("normal"))
    return _vagas(resultado)[0]


async def test_detalhar_le_o_detalhe_com_x_tenant() -> None:
    vaga = await _vaga_da_lista()
    detalhada, pedidos = await _detalhar(vaga, _json("detalhe"))
    assert detalhada is not None
    assert [(p.method, str(p.url)) for p in pedidos] == [("GET", URL_DETALHE)]
    assert pedidos[0].headers["X-Tenant"] == ESCOPO
    assert not {"origin", "cookie", "authorization", "referer"} & set(pedidos[0].headers)
    descricao = _dados("detalhe")["description"]
    assert isinstance(descricao, str)
    assert (detalhada.descricao, detalhada.descricao_formato) == (descricao.strip(), "html")
    assert "Planejamento" in detalhada.descricao
    assert detalhada.publicada_em == datetime(2026, 11, 4, 19, 55, 35, 484000, tzinfo=UTC)
    assert detalhada.contrato_declarado == "CLT"
    # o resto fica como veio da lista (a URL é a chave da vaga)
    assert (detalhada.url, detalhada.titulo, detalhada.id_externo) == (
        vaga.url,
        vaga.titulo,
        vaga.id_externo,
    )
    assert (detalhada.escopo, detalhada.empresa) == (vaga.escopo, vaga.empresa)
    assert (detalhada.locais, detalhada.modalidade_declarada) == (
        vaga.locais,
        vaga.modalidade_declarada,
    )


async def test_detalhar_nao_guarda_o_que_nao_e_da_vaga() -> None:
    vaga = await _vaga_da_lista()
    dados = _dados("detalhe") | {"creator": {"name": "Fulana de Tal"}, "recruiter": "Beltrano"}
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, json=dados))
    assert detalhada is not None
    saida = detalhada.para_json()
    assert "Fulana" not in saida and "Beltrano" not in saida


async def test_detalhar_data_ou_contrato_estranhos_mantem_o_da_lista() -> None:
    vaga = await _vaga_da_lista()
    dados = _dados("detalhe") | {"publishedAt": "ontem", "contractType": [3, ""]}
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, json=dados))
    assert detalhada is not None and detalhada.descricao
    assert (detalhada.publicada_em, detalhada.contrato_declarado) == (None, None)
    sem_fuso = _dados("detalhe") | {"publishedAt": "2026-11-04T19:55:35"}
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, json=sem_fuso))
    assert detalhada is not None and detalhada.publicada_em is None


@pytest.mark.parametrize(
    "corpo",
    [
        '{"description": ""}',
        '{"description": "  "}',
        '{"description": 3}',
        "{}",
        "[]",
        "não é json",
    ],
)
async def test_detalhar_sem_descricao_devolve_none(corpo: str) -> None:
    vaga = await _vaga_da_lista()
    detalhada, _ = await _detalhar(vaga, httpx.Response(200, text=corpo))
    assert detalhada is None


async def test_detalhar_404_devolve_none_e_outro_erro_sobe() -> None:
    vaga = await _vaga_da_lista()
    detalhada, pedidos = await _detalhar(vaga, httpx.Response(404, text="Not Found"))
    assert (detalhada, len(pedidos)) == (None, 1)
    with pytest.raises(ErroDeRede):
        await _detalhar(vaga, httpx.Response(500))


async def test_detalhar_item_sem_id_ou_de_sitemap_ou_de_tenant_ruim_nao_pede_nada() -> None:
    vaga = await _vaga_da_lista()
    itens: list[base.Item] = [
        VagaColetada(**{**vaga.__dict__, "id_externo": None}),
        VagaColetada(**{**vaga.__dict__, "id_externo": "../x?y#z"}),
        VagaColetada(**{**vaga.__dict__, "escopo": "x.evil.com/#"}),
        base.UrlListada("https://riachuelo.inhire.app/vagas/1"),
    ]
    for item in itens:
        detalhada, pedidos = await _detalhar(item, _json("detalhe"))
        assert (detalhada, pedidos) == (None, [])


@pytest.mark.parametrize(
    ("entrada", "tenant"),
    [
        ("riachuelo", "riachuelo"),
        (" riachuelo ", "riachuelo"),
        ("Riachuelo", "riachuelo"),  # o subdomínio não tem caixa: o resolver normaliza
        ("https://riachuelo.inhire.app", "riachuelo"),
        ("https://riachuelo.inhire.app/", "riachuelo"),
        ("https://Riachuelo.inhire.app/vagas", "riachuelo"),
        (f"https://riachuelo.inhire.app/vagas/{ID_VAGA}", "riachuelo"),
        (f"https://riachuelo.inhire.app/vagas/{ID_VAGA}/analista-de-planejamento", "riachuelo"),
        ("riachuelo.inhire.app/vagas", "riachuelo"),
        ("https://carreiras.inhire.app/vagas?r=linkedin", "carreiras"),
        ("https://meu-tenant-2.inhire.app/portal/vagas", "meu-tenant-2"),
    ],
)
async def test_resolver_aceita_url_e_devolve_o_tenant(
    entrada: str, tenant: str, http_proibido: HttpEducado
) -> None:
    resolvido = await inhire.COLETOR.resolver(entrada, http_proibido)
    assert resolvido == {"identificador": tenant}


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "https://inhire.app/vagas",
        "https://api.inhire.app/job-posts/public/pages",
        "https://www.inhire.com.br/",
        "https://riachuelo.inhire.com.br/vagas",
        "https://riachuelo.inhire.app.evil.com/vagas",
        "https://evil.com/riachuelo.inhire.app",
        "https://jobs.lever.co/riachuelo",
        "https://user@riachuelo.inhire.app/vagas",
        "ftp://riachuelo.inhire.app/vagas",
        "https://www.inhire.app/vagas",
        "https://embed.inhire.app/v1/jobs.js",
        "https://a.b.inhire.app/vagas",
        "ria chuelo",
        "riachuélo",
        "-riachuelo",
        "x" * 64,
    ],
)
async def test_resolver_recusa_o_que_nao_e_tenant(entrada: str, http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await inhire.COLETOR.resolver(entrada, http_proibido)
