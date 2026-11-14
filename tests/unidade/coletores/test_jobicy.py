import copy
import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, jobicy, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "jobicy"
URL = "https://jobicy.com/api/jobs?count=100&geo=brazil"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _json(caso: str, status: int = 200, **cabecalhos: str) -> httpx.Response:
    return httpx.Response(
        status,
        text=_texto(caso),
        headers={"Content-Type": "application/json; charset=utf-8", **cabecalhos},
    )


def _dados(caso: str = "normal") -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_texto(caso))
    return dados


def _pagina(dados: dict[str, Any]) -> httpx.Response:
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
        resultado = await jobicy.COLETOR.coletar("", http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """O `resolver` da Jobicy não faz pedido: qualquer pedido é erro do teste."""

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
    prova: Coletor = jobicy.COLETOR
    assert registro.descobrir()["jobicy"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "A"
    assert prova.intervalo_min == limites.intervalo_min == 60
    assert prova.credito_obrigatorio is True
    assert prova.hosts == ("jobicy.com",)


def test_escopo_unico() -> None:
    empresas = [Empresa(nome="Flex", fonte="jobicy", identificador="flex")]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(jobicy.COLETOR.escopos(ctx)) == [""]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"), _json("vazio"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 2)
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert primeira.fonte == "jobicy" and primeira.escopo == ""
    assert primeira.url == "https://jobicy.com/jobs/155325-senior-software-engineer-observability"
    assert primeira.titulo == "Senior Software Engineer, Observability"
    assert primeira.empresa == "NetBox Labs"
    assert primeira.id_externo == "155325"
    assert primeira.locais == ("LATAM", "USA")
    assert primeira.publicada_em == datetime(2026, 11, 14, 3, 0, 14, tzinfo=UTC)
    assert primeira.descricao_formato == "html"
    assert primeira.descricao.startswith("</p>\n<p>NetBox Labs is seeking")
    assert "&amp;" in primeira.descricao  # HTML de verdade: sem html.unescape
    assert primeira.etiquetas == ("Software Engineering",)
    assert primeira.contrato_declarado == "Full-Time"
    assert primeira.url_candidatura is None
    assert primeira.salario_estruturado == SalarioBruto(
        moeda="USD", minimo_unidades=85000, maximo_unidades=95000, periodo="ano"
    )
    assert vagas[1].locais == ("LATAM", "Canada", "USA")
    assert vagas[1].etiquetas == ("Customer Support & Success",)
    assert vagas[4].locais == ("Brazil",)
    assert vagas[4].salario_estruturado is None  # salaryMin e salaryMax nulos
    assert all(v.url.startswith("https://jobicy.com/jobs/") for v in vagas)
    assert len(pedidos) == 2


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1  # hasMore false: não pede outra página


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["155325"]


@pytest.mark.parametrize(
    "corpo",
    ['{"offers": []}', "[]", '{"jobs": {}}', "isto não é json", '{"jobs": [1, "x"]}'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _dados("vazio") | {"jobs": [copy.deepcopy(_dados()["jobs"][0])]}
    dados["jobs"][0] |= {
        "pubDate": "2026-11-14T03:00:14",  # sem fuso
        "jobGeo": None,
        "jobDescription": None,
        "jobIndustry": "Sales",
        "jobType": None,
        "salaryMin": "muito",
        "salaryMax": None,
        "salaryCurrency": 12,
        "salaryPeriod": ["yearly"],
    }
    resultado, _ = await _coletar(_pagina(dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.locais, vaga.descricao) == (None, (), "")
    assert (vaga.etiquetas, vaga.contrato_declarado) == ((), None)
    assert vaga.salario_estruturado is None


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = _dados("formato_mudou") | {"jobs": copy.deepcopy(_dados()["jobs"][:2])}
    dados["jobs"][1]["url"] = "javascript:alert(1)"
    resultado, _ = await _coletar(_pagina(dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 1


async def test_locais_separa_por_virgula_e_tira_espacos_duplos() -> None:
    dados = _dados("formato_mudou") | {"jobs": [copy.deepcopy(_dados()["jobs"][0])]}
    dados["jobs"][0]["jobGeo"] = " LATAM,  New   York ,, USA , "
    resultado, _ = await _coletar(_pagina(dados))
    assert _vagas(resultado)[0].locais == ("LATAM", "New York", "USA")


@pytest.mark.parametrize(
    ("campos", "esperado"),
    [
        (
            {"salaryPeriod": "yearly"},
            SalarioBruto(moeda="USD", minimo_unidades=85000, maximo_unidades=95000, periodo="ano"),
        ),
        (
            {"salaryPeriod": "monthly"},
            SalarioBruto(moeda="USD", minimo_unidades=85000, maximo_unidades=95000, periodo="mes"),
        ),
        (
            {"salaryPeriod": "weekly"},
            SalarioBruto(
                moeda="USD", minimo_unidades=85000, maximo_unidades=95000, periodo="semana"
            ),
        ),
        (
            {"salaryPeriod": "daily"},
            SalarioBruto(moeda="USD", minimo_unidades=85000, maximo_unidades=95000, periodo="dia"),
        ),
        (
            {"salaryPeriod": "hourly"},
            SalarioBruto(moeda="USD", minimo_unidades=85000, maximo_unidades=95000, periodo="hora"),
        ),
        (
            {"salaryPeriod": "biennial"},
            SalarioBruto(moeda="USD", minimo_unidades=85000, maximo_unidades=95000, periodo=None),
        ),
        (
            {"salaryPeriod": None},
            SalarioBruto(moeda="USD", minimo_unidades=85000, maximo_unidades=95000, periodo=None),
        ),
        (
            {"salaryCurrency": "brl"},
            SalarioBruto(moeda="BRL", minimo_unidades=85000, maximo_unidades=95000, periodo="ano"),
        ),
        (
            {"salaryCurrency": "reais"},
            SalarioBruto(moeda=None, minimo_unidades=85000, maximo_unidades=95000, periodo="ano"),
        ),
        (
            {"salaryMax": None},
            SalarioBruto(moeda="USD", minimo_unidades=85000, maximo_unidades=None, periodo="ano"),
        ),
        (
            {"salaryMin": 0},
            SalarioBruto(moeda="USD", minimo_unidades=None, maximo_unidades=95000, periodo="ano"),
        ),
        ({"salaryMin": -5, "salaryMax": True}, None),
        ({"salaryMin": "85000", "salaryMax": float("nan")}, None),
        ({"salaryMin": 10**400, "salaryMax": -1}, None),  # inteiro além do float: sem OverflowError
        (
            {"salaryMin": 10**400},
            SalarioBruto(moeda="USD", minimo_unidades=None, maximo_unidades=95000, periodo="ano"),
        ),
        (
            {"salaryMin": 1.5},
            SalarioBruto(moeda="USD", minimo_unidades=1.5, maximo_unidades=95000, periodo="ano"),
        ),
    ],
)
async def test_salario_estruturado(campos: dict[str, Any], esperado: SalarioBruto | None) -> None:
    dados = _dados("formato_mudou") | {"jobs": [copy.deepcopy(_dados()["jobs"][0])]}
    dados["jobs"][0] |= campos
    texto = json.dumps(dados, allow_nan=True)  # o NaN vai como `NaN`, que o json do Python lê
    resultado, _ = await _coletar(httpx.Response(200, text=texto))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].salario_estruturado == esperado


async def test_paginacao_segue_o_cursor_ate_hasmore_falso() -> None:
    pagina1 = _dados()
    cursor1 = pagina1["nextCursor"]
    ultima = copy.deepcopy(pagina1["jobs"][4])
    ultima |= {"id": 999, "url": "https://jobicy.com/jobs/999-nova", "jobTitle": "Nova"}
    pagina2 = _dados("vazio") | {"jobs": [ultima], "nextCursor": "cursor-2", "hasMore": True}
    pagina3 = _dados("vazio") | {"jobs": [], "nextCursor": None, "hasMore": False}
    resultado, pedidos = await _coletar(_pagina(pagina1), _pagina(pagina2), _pagina(pagina3))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 3)
    assert [v.id_externo for v in _vagas(resultado)] == [
        "155325",
        "155318",
        "155313",
        "153103",
        "161943",
        "999",
    ]
    assert [dict(p.url.params) for p in pedidos] == [
        {"count": "100", "geo": "brazil"},
        {"count": "100", "geo": "brazil", "cursor": cursor1},
        {"count": "100", "geo": "brazil", "cursor": "cursor-2"},
    ]


async def test_cursor_vencido_no_meio_deixa_parcial() -> None:
    resultado, pedidos = await _coletar(_json("normal"), httpx.Response(400))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(_vagas(resultado)) == 5
    assert len(pedidos) == 2  # 400 não se repete


async def test_cursor_repetido_nao_gira_para_sempre() -> None:
    pagina1 = _dados()
    nova = copy.deepcopy(pagina1["jobs"][0])
    nova |= {"id": 777, "url": "https://jobicy.com/jobs/777-nova", "jobTitle": "Nova"}
    # a página 2 é nova e aponta de volta para o cursor que acabou de ser usado
    pagina2 = _dados("vazio") | {
        "jobs": [nova],
        "nextCursor": pagina1["nextCursor"],
        "hasMore": True,
    }
    resultado, pedidos = await _coletar(_pagina(pagina1), _pagina(pagina2))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(pedidos) == 2
    assert [v.id_externo for v in _vagas(resultado)][-1] == "777"  # a página nova entra
    assert len(_vagas(resultado)) == 6


@pytest.mark.parametrize(
    "corpo",
    ["<html>fora do ar</html>", json.dumps({"vagas": []}), json.dumps({"jobs": [{"x": 1}]})],
    ids=["nao_json", "sem_jobs", "nenhuma_legivel"],
)
async def test_formato_mudou_no_meio_deixa_parcial(corpo: str) -> None:
    resultado, pedidos = await _coletar(_json("normal"), httpx.Response(200, text=corpo))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(_vagas(resultado)) == 5  # as páginas boas já lidas ficam
    assert len(pedidos) == 2


@pytest.mark.parametrize("cursor", [None, "", 7])
async def test_hasmore_sem_cursor_valido_deixa_parcial(cursor: object) -> None:
    dados = _dados() | {"nextCursor": cursor, "hasMore": True}
    resultado, pedidos = await _coletar(_pagina(dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(pedidos) == 1
    assert len(_vagas(resultado)) == 5


async def test_teto_de_paginas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobicy, "_MAX_PAGINAS", 3)
    n = 0

    def sempre_outra(pedido: httpx.Request) -> httpx.Response:
        nonlocal n
        n += 1
        return _pagina(_dados("vazio") | {"nextCursor": f"c{n}", "hasMore": True})

    resultado, pedidos = await _coletar(sempre_outra)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(pedidos) == 3


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

    monkeypatch.setattr(jobicy, "juntar_paginas", espia)
    modificado = "Sat, 14 Nov 2026 06:26:48 GMT"

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-Modified-Since") == modificado:
            return httpx.Response(304, headers={"Last-Modified": modificado})
        resposta = _json("normal")
        resposta.headers["Last-Modified"] = modificado
        return resposta

    leitor = LeitorFixo({URL: Validadores(None, modificado)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-Modified-Since") for p in pedidos] == [modificado]
    assert "If-None-Match" not in pedidos[0].headers
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_pagina_do_cursor_nao_e_condicional() -> None:
    """Só a primeira página leva validador: o cursor vale 24 horas e a URL dele não se repete."""
    modificado = "Sat, 14 Nov 2026 06:26:48 GMT"
    cursor = _dados()["nextCursor"]
    leitor = LeitorFixo(
        {
            URL: Validadores(None, modificado),
            f"{URL}&cursor={cursor}": Validadores(None, modificado),
        }
    )
    _, pedidos = await _coletar(_json("normal"), _json("vazio"), leitor=leitor, condicional=True)
    assert [p.headers.get("If-Modified-Since") for p in pedidos] == [modificado, None]


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
    assert str(pedido.url) == URL
    assert dict(pedido.url.params) == {"count": "100", "geo": "brazil"}


async def test_resolver_recusa_tudo_e_nao_faz_pedido(http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await jobicy.COLETOR.resolver("https://jobicy.com/jobs/155325-x", http_proibido)


async def test_detalhar_nao_tem_o_que_detalhar(http_proibido: HttpEducado) -> None:
    item = VagaColetada(
        fonte="jobicy",
        escopo="",
        url="https://jobicy.com/jobs/1-x",
        titulo="x",
        empresa="y",
        descricao_formato="html",
    )
    assert await jobicy.COLETOR.detalhar(item, http_proibido) is None
