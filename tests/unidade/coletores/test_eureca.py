import copy
import json
import time
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.coletores.portais import eureca
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "eureca"
API = "https://candidate-api.eureca.me/opportunities"
LINK = "https://app.eureca.me/vagas/"
Responder = Callable[[httpx.Request], httpx.Response]


def _fuso(monkeypatch: pytest.MonkeyPatch, nome: str) -> None:
    monkeypatch.setenv("TZ", nome)
    time.tzset()


@pytest.fixture(autouse=True)
def fuso_de_sao_paulo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """O prazo é o dia local (DP8): os testes rodam no fuso de São Paulo."""
    _fuso(monkeypatch, "America/Sao_Paulo")
    yield
    monkeypatch.undo()
    time.tzset()


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _json(caso: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=_texto(caso), headers={"Content-Type": "application/json"})


def _dados(caso: str = "normal") -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_texto(caso))
    return dados


def _com(**campos: Any) -> dict[str, Any]:
    """Página com o primeiro item do normal, com os campos trocados (total 1)."""
    pagina = _dados()
    pagina["items"] = [copy.deepcopy(pagina["items"][0]) | campos]
    pagina["total"] = 1
    return pagina


def _resposta(dados: object) -> httpx.Response:
    return httpx.Response(200, text=json.dumps(dados, allow_nan=True))


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return None


class LeitorComEtag:
    """Devolve validador: se o coletor pedisse condicional, o pedido levaria `If-None-Match`."""

    def ler(self, url: str) -> Validadores | None:
        return Validadores(etag='"abc"', last_modified="Fri, 13 Nov 2026 23:17:26 GMT")


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
    leitor: LeitorFixo | LeitorComEtag | None = None,
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
        http: HttpEducado = cli.escopo()
        resultado = await eureca.COLETOR.coletar("", http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """`resolver` e `detalhar` não fazem pedido: qualquer pedido é erro do teste."""

    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não faz pedido: {pedido.url}")

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


def _uma(resultado: ResultadoEscopo) -> VagaColetada:
    vagas = _vagas(resultado)
    assert len(vagas) == 1
    return vagas[0]


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = eureca.COLETOR
    assert registro.descobrir()["eureca"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "B"
    assert prova.intervalo_min == limites.intervalo_min is None
    assert prova.max_pedidos == limites.max_pedidos
    assert prova.espera_s == limites.espera_s == 2.0  # DP7: nunca abaixo de 2 s
    assert prova.credito_obrigatorio is False
    assert prova.hosts == ("candidate-api.eureca.me",)  # o link da vaga não é pedido


def test_escopo_unico() -> None:
    empresas = [Empresa(nome="Motiva", fonte="eureca", identificador="motiva")]
    ctx = ContextoColeta(empresas=empresas, termos=["estágio"], paises=["BR"])
    assert list(eureca.COLETOR.escopos(ctx)) == [""]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert len(pedidos) == 1
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert primeira.fonte == "eureca" and primeira.escopo == ""
    assert primeira.id_externo == "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d"
    assert primeira.url == LINK + "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d"
    assert primeira.url_candidatura is None
    assert primeira.titulo == "Estágio em Manutenção Metrô Bahia"
    assert primeira.empresa == "Motiva"
    assert primeira.descricao_formato == "html"
    assert primeira.descricao.startswith("<p>Na Motiva, você vai apoiar")
    assert primeira.locais == ("Salvador, BA",)
    assert primeira.modalidade_declarada == "presencial"
    assert primeira.contrato_declarado == "internship"
    assert primeira.salario_estruturado is None  # `salary` veio null
    assert primeira.publicada_em == datetime(2026, 11, 10, 13, 2, 42, 445557, tzinfo=UTC)
    assert primeira.prazo == date(2026, 12, 31)  # 2027-01-01T02:59Z é 23:59 de 31/12 em SP
    assert [v.id_externo for v in vagas] == [
        "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d",
        "019fdbd4-afee-720d-a537-cf5b8c58aa24",
        "019fb485-61f9-7547-8e74-f1e545482984",
        "019faf1c-93a5-734e-80da-2eec12520618",
        "01a1651d-aeac-76d3-bb14-fb23c977f554",
    ]
    assert vagas[1].locais == ()  # cidade e estado nulos
    assert vagas[1].salario_estruturado is None  # display "undisclosed"
    assert vagas[2].salario_estruturado == SalarioBruto(
        moeda="BRL", minimo_unidades=1900, maximo_unidades=2200
    )
    assert vagas[3].modalidade_declarada == "remoto"
    assert vagas[3].prazo == date(2030, 7, 31)
    assert all(v.url.startswith("https://") for v in vagas)


async def test_normal_reduzido_declara_mais_do_que_trouxe() -> None:
    """O exemplo reduzido traz 5 de 8: a lista não veio inteira, então é parcial (D45 à parte)."""
    resultado, _ = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == (
        "parcial",
        "saude.listagem_incompleta",
        1,
    )


async def test_normal_com_total_igual_ao_lido_e_ok() -> None:
    pagina = _dados()
    pagina["total"] = len(pagina["items"])  # como se a resposta viesse inteira
    resultado, _ = await _coletar(_resposta(pagina))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert len(resultado.vagas) == 5


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    # shortcut na fonte: a contagem não vai no motivo (D45)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == [
        "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d",
        "019faf1c-93a5-734e-80da-2eec12520618",
        "01a1651d-aeac-76d3-bb14-fb23c977f554",
    ]


@pytest.mark.parametrize(
    "corpo",
    [
        '{"items": {}, "total": 0}',
        '{"total": 0}',
        '{"items": [], "total": "0"}',
        '{"items": [], "total": true}',
        '{"items": []}',
        "{}",
        "[]",
        "null",
        '"texto"',
        "isto não é json",
        '{"items": [1, "x"], "total": 2}',
        '{"items": [{"x": 1}], "total": 1}',
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


@pytest.mark.parametrize(
    "campos",
    [
        {"name": "  "},
        {"name": None},
        {"companyName": ""},
        {"companyName": 3},
        {"id": None},
        {"id": True},
        {"id": 12},
        {"id": ""},
        {"id": "../../x"},
        {"id": "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d/../x"},
        {"id": "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d?x=1"},
        {"id": "01a1c58d-bb0f-7b43-be36-3d4ed6cb728"},  # um dígito a menos
        {"id": "0１a1c58d-bb0f-7b43-be36-3d4ed6cb728d"},  # dígito fora do ASCII
    ],
)
async def test_item_sem_campo_obrigatorio_e_pulado(campos: dict[str, Any]) -> None:
    pagina = _com()
    pagina["items"] += _com(**campos)["items"]
    pagina["total"] = 2
    resultado, _ = await _coletar(_resposta(pagina))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 1


async def test_link_da_vaga_pelo_id_em_minusculas() -> None:
    resultado, _ = await _coletar(_resposta(_com(id="  01A1C58D-BB0F-7B43-BE36-3D4ED6CB728D ")))
    vaga = _uma(resultado)
    assert vaga.url == LINK + "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d"
    assert vaga.id_externo == "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _com(
        description=5,
        cityName=["x"],
        stateAcronym=7,
        workModel={"a": 1},
        contractTypeKey=True,
        salary="R$ 1.900",
        publishedAt=12,
        createdAt=None,
        endApplying="amanhã",
    )
    resultado, _ = await _coletar(_resposta(dados))
    assert resultado.estado == "ok"
    vaga = _uma(resultado)
    assert (vaga.descricao, vaga.locais) == ("", ())
    assert (vaga.modalidade_declarada, vaga.contrato_declarado) == (None, None)
    assert (vaga.salario_estruturado, vaga.publicada_em, vaga.prazo) == (None, None, None)


@pytest.mark.parametrize(
    ("cidade", "estado", "locais"),
    [
        ("Salvador", "BA", ("Salvador, BA",)),
        (" Jundiaí ", " SP ", ("Jundiaí, SP",)),
        ("Salvador", None, ("Salvador",)),
        (None, "BA", ("BA",)),
        (None, None, ()),
        ("", " ", ()),
    ],
)
async def test_locais(cidade: object, estado: object, locais: tuple[str, ...]) -> None:
    resultado, _ = await _coletar(_resposta(_com(cityName=cidade, stateAcronym=estado)))
    assert _uma(resultado).locais == locais


@pytest.mark.parametrize(
    ("salario", "esperado"),
    [
        (
            {"display": "range", "minCents": 190000, "maxCents": 220000},
            SalarioBruto(moeda="BRL", minimo_unidades=1900, maximo_unidades=2200),
        ),
        (
            {"display": "range", "minCents": None, "maxCents": 150050},
            SalarioBruto(moeda="BRL", minimo_unidades=None, maximo_unidades=1500.5),
        ),
        (
            {"display": "fixed", "minCents": 180000, "maxCents": 180000},
            SalarioBruto(moeda="BRL", minimo_unidades=1800, maximo_unidades=1800),
        ),
        ({"display": "undisclosed", "minCents": 190000, "maxCents": 220000}, None),
        ({"display": "undisclosed", "minCents": None, "maxCents": None}, None),
        ({"display": "range", "minCents": None, "maxCents": None}, None),
        ({"display": "range", "minCents": 0, "maxCents": -5}, None),
        ({"display": "range", "minCents": True, "maxCents": "220000"}, None),
        ({"display": "range", "minCents": 1900.5, "maxCents": float("nan")}, None),
        ({"display": "range", "minCents": 10**400, "maxCents": None}, None),
        (None, None),
        ("1900", None),
    ],
)
async def test_salario_em_centavos_vira_reais(salario: object, esperado: object) -> None:
    resultado, _ = await _coletar(_resposta(_com(salary=salario)))
    assert _uma(resultado).salario_estruturado == esperado


@pytest.mark.parametrize(
    ("publicada", "criada", "esperado"),
    [
        (
            "2026-11-12T10:00:00.000Z",
            "2026-11-10 13:02:42+00",
            datetime(2026, 11, 12, 10, tzinfo=UTC),
        ),
        (None, "2026-11-10 13:02:42+00", datetime(2026, 11, 10, 13, 2, 42, tzinfo=UTC)),
        ("lixo", "2026-11-10 13:02:42+00", datetime(2026, 11, 10, 13, 2, 42, tzinfo=UTC)),
        (None, "2026-11-10 13:02:42", None),  # sem fuso não vale
        (None, None, None),
    ],
)
async def test_publicada_em(publicada: object, criada: object, esperado: datetime | None) -> None:
    resultado, _ = await _coletar(_resposta(_com(publishedAt=publicada, createdAt=criada)))
    assert _uma(resultado).publicada_em == esperado


async def test_prazo_usa_o_dia_local_nao_o_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    resultado, _ = await _coletar(_resposta(_com(endApplying="2027-01-01T02:59:00.000Z")))
    assert _uma(resultado).prazo == date(2026, 12, 31)
    _fuso(monkeypatch, "UTC")  # controle: em UTC o mesmo instante já é dia 1º
    resultado, _ = await _coletar(_resposta(_com(endApplying="2027-01-01T02:59:00.000Z")))
    assert _uma(resultado).prazo == date(2027, 1, 1)


async def test_prazo_sem_fuso_nao_vale() -> None:
    resultado, _ = await _coletar(_resposta(_com(endApplying="2027-01-01T02:59:00")))
    assert _uma(resultado).prazo is None


def _pagina_1_de_5() -> dict[str, Any]:
    pagina = _dados()
    pagina["pageSize"] = 5  # como a página 1 do pedido real com pageSize=5
    return pagina


async def test_paginacao() -> None:
    resultado, pedidos = await _coletar(_resposta(_pagina_1_de_5()), _json("pagina_2"))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert len(pedidos) == 2
    assert [dict(p.url.params) for p in pedidos] == [
        {"page": "1", "pageSize": "200"},
        {"page": "2", "pageSize": "200"},
    ]
    assert len(_vagas(resultado)) == 8  # 5 + 3, o total declarado
    assert _vagas(resultado)[-1].id_externo == "01a090e2-7159-704d-a347-5e78fc9e5ab2"


async def test_paginacao_para_quando_o_total_foi_atingido() -> None:
    pagina = _pagina_1_de_5()
    pagina["total"] = 5  # página cheia, mas o total já veio
    resultado, pedidos = await _coletar(_resposta(pagina))
    assert (resultado.estado, len(pedidos), len(resultado.vagas)) == ("ok", 1, 5)


async def test_paginacao_pagina_seguinte_ilegivel_mantem_a_primeira() -> None:
    resultado, pedidos = await _coletar(
        _resposta(_pagina_1_de_5()), httpx.Response(200, text="<html>manutenção</html>")
    )
    assert len(pedidos) == 2
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 5


async def test_paginacao_erro_de_rede_na_segunda_mantem_a_primeira() -> None:
    resultado, _ = await _coletar(_resposta(_pagina_1_de_5()), httpx.Response(500))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(resultado.vagas) == 5


async def test_paginacao_para_no_teto() -> None:
    modelo = _dados()["items"][0]
    contagem = 0

    def sem_fim(pedido: httpx.Request) -> httpx.Response:
        nonlocal contagem
        contagem += 1
        assert contagem <= eureca.MAX_PAGINAS  # sem teto, a mutação falha aqui, sem travar
        itens = [modelo | {"id": f"00000000-0000-0000-{contagem:04x}-{i:012x}"} for i in range(2)]
        return _resposta({"items": itens, "total": 10**6, "page": contagem, "pageSize": 2})

    resultado, pedidos = await _coletar(sem_fim)
    assert len(pedidos) == eureca.MAX_PAGINAS
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert len(resultado.vagas) == 2 * eureca.MAX_PAGINAS


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
    resultado, pedidos = await _coletar(httpx.Response(401))  # a API pede login: bloqueio
    assert (resultado.estado, resultado.motivo, len(pedidos)) == ("falhou", "saude.bloqueio", 1)


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_json("vazio"), leitor=LeitorComEtag())
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert f"{pedido.url.scheme}://{pedido.url.host}{pedido.url.path}" == API
    assert dict(pedido.url.params) == {"page": "1", "pageSize": "200"}
    assert pedido.headers["Accept"] == "application/json"
    assert pedido.headers["User-Agent"].startswith("joBot/")
    for nome in ("Cookie", "Origin", "Referer", "Authorization"):
        assert nome not in pedido.headers
    # a API não manda ETag nem Last-Modified: o coletor nunca pede condicional
    assert "If-None-Match" not in pedido.headers
    assert "If-Modified-Since" not in pedido.headers


async def test_resolver_recusa_tudo_e_nao_faz_pedido(http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError, match="identificador"):
        await eureca.COLETOR.resolver("https://app.eureca.me/vagas/x", http_proibido)


async def test_detalhar_nao_tem_o_que_detalhar(http_proibido: HttpEducado) -> None:
    item = VagaColetada(
        fonte="eureca",
        escopo="",
        url=LINK + "01a1c58d-bb0f-7b43-be36-3d4ed6cb728d",
        titulo="x",
        empresa="y",
        descricao_formato="html",
    )
    assert await eureca.COLETOR.detalhar(item, http_proibido) is None
