import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, lever, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "lever"
URL_STARK = "https://api.lever.co/v0/postings/starkbank?mode=json"
STARK = Empresa(nome="Stark Bank", fonte="lever", identificador="starkbank")
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _json(caso: str, status: int = 200, **cabecalhos: str) -> httpx.Response:
    return httpx.Response(
        status, text=_texto(caso), headers={"Content-Type": "application/json", **cabecalhos}
    )


def _normal() -> list[dict[str, Any]]:
    dados: list[dict[str, Any]] = json.loads(_texto("normal"))
    return dados


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = "starkbank",
    empresas: Sequence[Empresa] = (STARK,),
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
    coletor = lever.Lever()  # instância nova: o cadastro de nomes não vaza entre testes
    coletor.escopos(ContextoColeta(empresas=empresas, termos=[], paises=[]))
    try:
        http: HttpEducado = cli.escopo(condicional=condicional)
        resultado = await coletor.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """O `resolver` do Lever só lê o texto: qualquer pedido é erro do teste."""

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
    prova: Coletor = lever.COLETOR
    assert registro.descobrir()["lever"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("api.lever.co",)


def test_escopos_um_por_empresa() -> None:
    empresas = [
        Empresa(nome="Stark Bank", fonte="lever", identificador="starkbank"),
        Empresa(nome="Outra", fonte="lever", identificador="outra"),
        Empresa(nome="Stark de novo", fonte="lever", identificador="starkbank"),
    ]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(lever.Lever().escopos(ctx)) == ["starkbank", "outra"]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 4
    primeira = vagas[0]
    assert primeira.fonte == "lever" and primeira.escopo == "starkbank"
    assert primeira.url == "https://jobs.lever.co/starkbank/36cefa14-d1c1-4723-96d2-97a57ac7580c"
    assert primeira.titulo == "Advogado Pleno"
    assert primeira.id_externo == "36cefa14-d1c1-4723-96d2-97a57ac7580c"
    assert primeira.locais == ("São Paulo, SP",)
    assert primeira.modalidade_declarada == "onsite"
    assert primeira.contrato_declarado is None
    assert primeira.etiquetas == ("Legal",)  # departamento e time iguais não se repetem
    assert vagas[1].etiquetas == ("Legal", "Regulatory")
    assert primeira.descricao_formato == "html"
    assert primeira.salario_estruturado is None and primeira.prazo is None
    assert all(v.url.startswith(("https://", "http://")) for v in vagas)
    assert len(pedidos) == 1


async def test_empresa_vem_do_cadastro() -> None:
    resultado, _ = await _coletar(_json("normal"))
    assert {v.empresa for v in _vagas(resultado)} == {"Stark Bank"}


async def test_empresa_sem_cadastro_usa_o_identificador() -> None:
    # "testar" no painel pode coletar sem passar por `escopos`
    resultado, _ = await _coletar(_json("normal"), empresas=())
    assert {v.empresa for v in _vagas(resultado)} == {"starkbank"}


async def test_nome_da_empresa_acompanha_o_ultimo_cadastro() -> None:
    # o coletor é singleton do registro: renomear ou recadastrar vale sem reiniciar
    coletor = lever.Lever()

    def nomes(*nomes: str) -> ContextoColeta:
        empresas = [Empresa(nome=n, fonte="lever", identificador="starkbank") for n in nomes]
        return ContextoColeta(empresas=empresas, termos=[], paises=[])

    coletor.escopos(nomes("Stark Bank", "Duplicata"))  # na mesma chamada, o primeiro vale
    assert coletor._nomes == {"starkbank": "Stark Bank"}
    coletor.escopos(nomes("Stark"))  # entre chamadas, o último cadastro vale
    assert coletor._nomes == {"starkbank": "Stark"}


async def test_created_at_em_milissegundos() -> None:
    resultado, _ = await _coletar(_json("normal"))
    vagas = _vagas(resultado)
    assert vagas[0].publicada_em == datetime(2026, 9, 23, 17, 32, 9, 312000, tzinfo=UTC)
    assert vagas[2].publicada_em == datetime(2026, 7, 21, 15, 19, 53, 535000, tzinfo=UTC)


async def test_apply_url_vira_url_candidatura() -> None:
    resultado, _ = await _coletar(_json("normal"))
    primeira = _vagas(resultado)[0]
    assert primeira.url_candidatura == f"{primeira.url}/apply"
    dados = _normal()[:2]
    dados[0]["applyUrl"] = "javascript:alert(1)"
    del dados[1]["applyUrl"]
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"  # candidatura fora de http não derruba a vaga
    assert [v.url_candidatura for v in _vagas(resultado)] == [None, None]


async def test_descricao_junta_corpo_listas_e_adicional() -> None:
    dados = _normal()[:1]
    dados[0] |= {
        "description": "<div>Corpo</div>",
        "lists": [
            {"text": "Você irá & fará:", "content": "<li>Um</li><li>Dois</li>"},
            {"text": "Sem itens", "content": ""},
        ],
        "additional": "<div>Benefícios</div>",
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert _vagas(resultado)[0].descricao == (
        "<div>Corpo</div>"
        "<h3>Você irá &amp; fará:</h3><ul><li>Um</li><li>Dois</li></ul>"
        "<div>Benefícios</div>"
    )


async def test_locais_all_locations_ou_location() -> None:
    dados = _normal()[:3]
    dados[0]["categories"] = {"location": "Lisboa", "allLocations": ["Lisboa", "Porto", "Lisboa"]}
    dados[1]["categories"] = {"location": "Recife, PE"}
    dados[2]["categories"] = {"location": "  ", "allLocations": []}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert [v.locais for v in _vagas(resultado)] == [("Lisboa", "Porto"), ("Recife, PE",), ()]


async def test_contrato_declarado_vem_de_commitment() -> None:
    dados = _normal()[:1]
    dados[0]["categories"]["commitment"] = "Full-time"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert _vagas(resultado)[0].contrato_declarado == "Full-time"


async def test_salary_range_vira_salario_estruturado() -> None:
    # nenhuma captura trouxe `salaryRange`: item montado à mão (apêndice 2.4)
    dados = _normal()[:3]
    dados[0]["salaryRange"] = {
        "currency": "BRL",
        "interval": "per-month-salary",
        "min": 8000,
        "max": 12000,
    }
    dados[1]["salaryRange"] = {"currency": "USD", "interval": "per-year-salary", "min": 90000.5}
    dados[2]["salaryRange"] = {"currency": "EUR", "interval": "algo-novo", "min": 1, "max": "x"}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    salarios = [v.salario_estruturado for v in _vagas(resultado)]
    assert salarios == [
        SalarioBruto(moeda="BRL", minimo_unidades=8000, maximo_unidades=12000, periodo="mes"),
        SalarioBruto(moeda="USD", minimo_unidades=90000.5, maximo_unidades=None, periodo="ano"),
        SalarioBruto(moeda="EUR", minimo_unidades=1, maximo_unidades=None, periodo=None),
    ]


@pytest.mark.parametrize(
    "faixa", [None, "x", {}, {"currency": "BRL"}, {"min": None, "max": None}, {"min": True}]
)
async def test_salary_range_sem_valor_nao_vira_salario(faixa: object) -> None:
    dados = _normal()[:1]
    dados[0]["salaryRange"] = faixa
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].salario_estruturado is None


@pytest.mark.parametrize(
    ("intervalo", "periodo"),
    [
        ("per-hour-wage", "hora"),
        ("per-day-salary", "dia"),
        ("per-week-salary", "semana"),
        ("per-month-salary", "mes"),
        ("per-year-salary", "ano"),
        ("one-time-salary", None),
        (None, None),
    ],
)
async def test_intervalo_do_salario(intervalo: str | None, periodo: str | None) -> None:
    dados = _normal()[:1]
    dados[0]["salaryRange"] = {"currency": "BRL", "interval": intervalo, "min": 100}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    bruto = _vagas(resultado)[0].salario_estruturado
    assert bruto is not None and bruto.periodo == periodo


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"), escopo="nubank")
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["36cefa14-d1c1-4723-96d2-97a57ac7580c"]


@pytest.mark.parametrize(
    "corpo",
    [
        '{"ok": true}',
        '{"postings": []}',
        "isto não é json",
        '[1, "x"]',
        '[{"text": "sem endereço"}]',
        "null",
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _normal()[:1]
    dados[0] |= {
        "createdAt": "ontem",
        "categories": None,
        "description": None,
        "opening": None,
        "descriptionBody": None,
        "lists": "x",
        "additional": 5,
        "workplaceType": 7,
        "salaryRange": [1],
        "id": None,
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.locais, vaga.etiquetas) == (None, (), ())
    assert (vaga.descricao, vaga.modalidade_declarada, vaga.id_externo) == ("", None, None)
    assert vaga.salario_estruturado is None


@pytest.mark.parametrize("ms", [10**30, -(10**30), True, 1.5e30])
async def test_created_at_fora_de_faixa_fica_sem_data(ms: object) -> None:
    dados = _normal()[:1]
    dados[0]["createdAt"] = ms
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok" and _vagas(resultado)[0].publicada_em is None


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = _normal()
    dados[1]["hostedUrl"] = "javascript:alert(1)"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 3


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

    monkeypatch.setattr(lever, "juntar_paginas", espia)
    etag = 'W/"10b90-mFVeaQ67RCNiyVVMw6q5ccjjuLg"'

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _json("normal", ETag=etag)

    leitor = LeitorFixo({URL_STARK: Validadores(etag, None)})
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
    assert str(pedido.url) == URL_STARK
    assert dict(pedido.url.params) == {"mode": "json"}  # sem skip nem limit: vem tudo (2.4)


async def test_escopo_estranho_nao_muda_o_caminho() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo="../x?y#z")
    assert [p.url.raw_path for p in pedidos] == [b"/v0/postings/..%2Fx%3Fy%23z?mode=json"]


@pytest.mark.parametrize(
    ("entrada", "site"),
    [
        ("starkbank", "starkbank"),
        (" starkbank ", "starkbank"),
        ("StarkBank", "StarkBank"),  # caixa preservada (D45)
        ("https://jobs.lever.co/starkbank", "starkbank"),
        ("https://jobs.lever.co/starkbank/", "starkbank"),
        ("https://jobs.lever.co/starkbank/36cefa14-d1c1-4723-96d2-97a57ac7580c", "starkbank"),
        ("https://jobs.lever.co/starkbank/36cefa14-d1c1-4723-96d2-97a57ac7580c/apply", "starkbank"),
        ("jobs.lever.co/starkbank", "starkbank"),
        ("https://api.lever.co/v0/postings/starkbank?mode=json", "starkbank"),
    ],
)
async def test_resolver_aceita_url_do_quadro_e_devolve_o_site(
    entrada: str, site: str, http_proibido: HttpEducado
) -> None:
    resolvido = await lever.COLETOR.resolver(entrada, http_proibido)
    assert resolvido == {"identificador": site}


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "https://boards.greenhouse.io/starkbank",
        "https://jobs.eu.lever.co/starkbank",
        "https://api.eu.lever.co/v0/postings/starkbank",
        "https://jobs.lever.co/",
        "https://api.lever.co/v0/postings",
        "https://api.lever.co/v1/postings/starkbank",
        "ftp://jobs.lever.co/starkbank",
        "stark bank",
        "stárkbank",
        "x" * 101,
    ],
)
async def test_resolver_recusa_o_que_nao_e_quadro(entrada: str, http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await lever.COLETOR.resolver(entrada, http_proibido)
