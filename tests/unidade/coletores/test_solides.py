import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.coletores.portais import solides
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio
from jobot.nucleo.tratamento.locais import ler_locais

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "solides"
BRT = timezone(timedelta(hours=-3))
DIEFRA = Empresa(nome="Diefra", fonte="solides", identificador="diefra")
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _json(caso: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=_texto(caso), headers={"Content-Type": "application/json"})


def _normal() -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_texto("normal"))
    return dados


def _com(vaga: dict[str, Any] | None = None, **campos: object) -> httpx.Response:
    """Uma página de uma vaga só (a primeira da captura) com os campos trocados."""
    dados = _normal()
    dados["data"] = [(vaga or dados["data"][0]) | campos]
    dados["totalPages"] = 1
    return httpx.Response(200, text=json.dumps(dados))


def _falsa(n: int) -> dict[str, Any]:
    return {"id": n, "title": f"Vaga {n}", "companyName": "DIEFRA", "description": "Texto."}


def _pagina(pagina: int, itens: int, total: object = 10, base: int = 0) -> httpx.Response:
    """Página `pagina` de uma empresa com vagas de ids `base + 1000 * pagina + i`."""
    dados = {
        "totalPages": total,
        "currentPage": pagina,
        "data": [_falsa(base + 1000 * pagina + i) for i in range(itens)],
    }
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
    escopo: str = "diefra",
    leitor: LeitorFixo | None = None,
    condicional: bool = False,
    max_pedidos: int | None = None,
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
        http: HttpEducado = cli.escopo(condicional=condicional, max_pedidos=max_pedidos)
        resultado = await solides.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """O `resolver` da Sólides só lê o texto: qualquer pedido é erro do teste."""

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
    prova: Coletor = solides.COLETOR
    assert registro.descobrir()["solides"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "B"
    assert prova.hosts == ("apigw.solides.com.br",)
    assert (prova.max_pedidos, prova.espera_s) == (None, 1.0)


def test_escopos_um_por_empresa() -> None:
    empresas = [
        Empresa(nome="Diefra", fonte="solides", identificador="diefra"),
        Empresa(nome="Bamex", fonte="solides", identificador="bamex"),
        Empresa(nome="Diefra de novo", fonte="solides", identificador="diefra"),
    ]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(solides.Solides().escopos(ctx)) == ["diefra", "bamex"]


async def test_normal_junta_as_duas_paginas() -> None:
    resultado, pedidos = await _coletar(_json("normal"), _json("pagina_2"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 2)
    assert len(pedidos) == 2
    vagas = _vagas(resultado)
    assert [v.id_externo for v in vagas] == [
        "951514", "948029", "947653", "943486", "944155",
        "920304", "915136", "912210", "911395", "832640",
    ]  # fmt: skip
    primeira = vagas[0]
    assert primeira.fonte == "solides" and primeira.escopo == "diefra"
    assert primeira.titulo == "AUX. CONSERVAÇÃO / GO"
    assert primeira.empresa == "DIEFRA"
    assert primeira.descricao_formato == "html"
    assert primeira.descricao.startswith("<div>") and "BARRO ALTO/GO" in primeira.descricao
    assert primeira.locais == ("Barro Alto, GO",)
    assert primeira.modalidade_declarada == "presencial"
    assert primeira.contrato_declarado == "CLT"
    assert primeira.etiquetas == ("Junior",)
    assert primeira.url_candidatura is None
    assert all(v.titulo and v.descricao for v in vagas)


async def test_link_e_montado_e_redirect_link_e_ignorado() -> None:
    resultado, _ = await _coletar(_json("normal"), _json("pagina_2"))
    vagas = _vagas(resultado)
    assert vagas[0].url == "https://diefra.vagas.solides.com.br/vaga/951514"
    assert all(v.url == f"https://diefra.vagas.solides.com.br/vaga/{v.id_externo}" for v in vagas)
    # a captura traz `redirectLink` quebrado ("https://diefra./vacancies/..."): nunca vira link
    assert not any("redirect" in v.url or "vacancies" in v.url for v in vagas)


async def test_link_usa_o_escopo_em_minusculas() -> None:
    resultado, pedidos = await _coletar(_pagina(1, 1, total=1), escopo="Diefra")
    assert _vagas(resultado)[0].url == "https://diefra.vagas.solides.com.br/vaga/1000"
    assert pedidos[0].url.path == "/jobs/v3/companies/Diefra/vacancies"


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_json("vazio"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert pedido.url.host == "apigw.solides.com.br"
    assert pedido.url.path == "/jobs/v3/companies/diefra/vacancies"
    assert dict(pedido.url.params) == {"page": "1", "take": "25"}


async def test_pagina_avanca_de_um_em_um_ate_total_de_paginas() -> None:
    resultado, pedidos = await _coletar(_json("normal"), _json("pagina_2"))
    assert [dict(p.url.params) for p in pedidos] == [
        {"page": "1", "take": "25"},
        {"page": "2", "take": "25"},
    ]
    assert len(resultado.vagas) == 10


async def test_pagina_vazia_encerra_mesmo_com_total_maior() -> None:
    resultado, pedidos = await _coletar(_pagina(1, 3, total=5), _pagina(2, 0, total=5))
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 3, 2)


async def test_sem_total_e_pagina_cheia_fica_parcial() -> None:
    # sem `totalPages` legível e com a página cheia: não dá para saber se há mais
    resposta = httpx.Response(200, json={"data": [_falsa(i) for i in range(1, 26)]})
    resultado, pedidos = await _coletar(resposta)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert (len(resultado.vagas), len(pedidos)) == (25, 1)


@pytest.mark.parametrize("total", [None, "x", True, -1, 1.5])
async def test_sem_total_e_pagina_curta_termina_ok(total: object) -> None:
    resultado, pedidos = await _coletar(_pagina(1, 2, total=total))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert (len(resultado.vagas), len(pedidos)) == (2, 1)


async def test_teto_de_paginas_fica_parcial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(solides, "MAX_PAGINAS", 3)
    resultado, pedidos = await _coletar(lambda p: _pagina(int(p.url.params["page"]), 25, 10**9))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert (len(resultado.vagas), len(pedidos)) == (75, 3)


async def test_orcamento_de_pedidos_fica_no_limite() -> None:
    resultado, pedidos = await _coletar(
        lambda p: _pagina(int(p.url.params["page"]), 25), max_pedidos=2
    )
    assert (resultado.estado, resultado.motivo) == ("no_limite", "saude.orcamento")
    assert (resultado.pedidos, len(pedidos), len(resultado.vagas)) == (2, 2, 50)


async def test_empresa_sem_nome_na_vaga_usa_o_escopo() -> None:
    resultado, _ = await _coletar(_com(companyName="  "))
    assert _vagas(resultado)[0].empresa == "diefra"


async def test_data_de_criacao_e_meia_noite_de_brasilia() -> None:
    resultado, _ = await _coletar(_json("normal"), _json("pagina_2"))
    vagas = _vagas(resultado)
    assert vagas[0].publicada_em == datetime(2026, 11, 10, tzinfo=BRT)
    assert vagas[9].publicada_em == datetime(2026, 4, 20, tzinfo=BRT)
    assert vagas[0].publicada_em == datetime(2026, 11, 10, 3, tzinfo=UTC)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("2026-11-10T08:30:00Z", datetime(2026, 11, 10, 8, 30, tzinfo=UTC)),
        ("2026-11-10T08:30:00", datetime(2026, 11, 10, 8, 30, tzinfo=BRT)),
        ("ontem", None),
        ("2026-13-45", None),
        (20261110, None),
        (None, None),
    ],
)
async def test_created_at_outros_formatos(valor: object, esperado: datetime | None) -> None:
    resultado, _ = await _coletar(_com(createdAt=valor))
    assert resultado.estado == "ok" and _vagas(resultado)[0].publicada_em == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ({"due": "2026-11-16", "show": False}, date(2026, 11, 16)),
        ({"due": "2026-11-16T23:59:00.000Z"}, date(2026, 11, 16)),
        ({"due": "amanhã"}, None),
        ({"due": None}, None),
        ({}, None),
        ("2026-11-16", None),
        (None, None),
    ],
)
async def test_prazo_vem_de_date_due(valor: object, esperado: date | None) -> None:
    resultado, _ = await _coletar(_com(date=valor))
    assert resultado.estado == "ok" and _vagas(resultado)[0].prazo == esperado


async def test_prazo_da_captura() -> None:
    resultado, _ = await _coletar(_json("normal"), _json("pagina_2"))
    assert [v.prazo for v in _vagas(resultado)[:2]] == [date(2026, 11, 16), date(2026, 12, 31)]


async def test_salario_da_captura() -> None:
    resultado, _ = await _coletar(_json("normal"), _json("pagina_2"))
    salarios = [v.salario_estruturado for v in _vagas(resultado)]
    # `initialRange: 0` é "sem piso"; `showRangeToApplicant: false` esconde a faixa
    assert salarios[0] == SalarioBruto(moeda="BRL", maximo_unidades=2000)
    assert salarios[2] == SalarioBruto(moeda="BRL", maximo_unidades=3500)
    assert [salarios[i] for i in (1, 3, 4, 5, 6, 7, 8, 9)] == [None] * 8


def _faixa(**campos: object) -> dict[str, object]:
    return {
        "type": "simple",
        "showRangeToApplicant": True,
        "initialRange": 3000,
        "finalRange": 5000,
        "negotiable": False,
    } | campos


@pytest.mark.parametrize(
    ("salario", "esperado"),
    [
        (_faixa(), SalarioBruto(moeda="BRL", minimo_unidades=3000, maximo_unidades=5000)),
        (_faixa(finalRange=None), SalarioBruto(moeda="BRL", minimo_unidades=3000)),
        (_faixa(initialRange=None), SalarioBruto(moeda="BRL", maximo_unidades=5000)),
        (
            _faixa(initialRange=1500.5),
            SalarioBruto(moeda="BRL", minimo_unidades=1500.5, maximo_unidades=5000),
        ),
        (_faixa(negotiable=True), None),
        (_faixa(showRangeToApplicant=False), None),
        (_faixa(initialRange=0, finalRange=0), None),
        (_faixa(initialRange=None, finalRange=None), None),
        (_faixa(initialRange=-1, finalRange=-5), None),
        (_faixa(initialRange=True, finalRange=True), None),
        (_faixa(initialRange="3000", finalRange="5000"), None),
        (_faixa(initialRange=10**400, finalRange=-(10**400)), None),
        (_faixa(initialRange=float("nan"), finalRange=float("inf")), None),
        ({}, None),
        ([1], None),
        ("x", None),
        (None, None),
    ],
)
async def test_salario_faixa(salario: object, esperado: SalarioBruto | None) -> None:
    resultado, _ = await _coletar(_com(salary=salario))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].salario_estruturado == esperado


async def test_modalidade_vem_de_job_type_ou_de_home_office() -> None:
    assert (
        _vagas((await _coletar(_com(jobType="hibrido", homeOffice=True)))[0])[
            0
        ].modalidade_declarada
        == "hibrido"
    )
    assert (
        _vagas((await _coletar(_com(jobType=None, homeOffice=True)))[0])[0].modalidade_declarada
        == "remoto"
    )
    for estranho in ({"jobType": None, "homeOffice": False}, {"jobType": 7, "homeOffice": "x"}):
        vaga = _vagas((await _coletar(_com(**estranho)))[0])[0]
        assert vaga.modalidade_declarada is None


async def test_contrato_so_quando_ha_um_tipo() -> None:
    um = [{"id": 1, "name": " PJ ", "level": None}]
    dois = [{"id": 1, "name": "PJ"}, {"id": 2, "name": "CLT"}]
    assert (
        _vagas((await _coletar(_com(recruitmentContractType=um)))[0])[0].contrato_declarado == "PJ"
    )
    for valor in (dois, [], None, "CLT", [{"id": 1}], [None]):
        vaga = _vagas((await _coletar(_com(recruitmentContractType=valor)))[0])[0]
        assert vaga.contrato_declarado is None


async def test_etiquetas_sao_as_senioridades_sem_repeticao() -> None:
    nomes = [{"name": "Pleno"}, {"name": " Sênior "}, {"name": "Pleno"}, {"name": ""}, None, {}]
    resultado, _ = await _coletar(_com(seniority=nomes))
    assert _vagas(resultado)[0].etiquetas == ("Pleno", "Sênior")
    for estranho in (None, "x", 5):
        assert _vagas((await _coletar(_com(seniority=estranho)))[0])[0].etiquetas == ()


@pytest.mark.parametrize(
    ("cidade", "estado", "locais"),
    [
        ({"name": "Barro Alto"}, {"code": "GO"}, ("Barro Alto, GO",)),
        ({"name": "Belo Horizonte"}, None, ("Belo Horizonte",)),
        ({"name": "Belo Horizonte"}, {"name": "Minas Gerais"}, ("Belo Horizonte",)),
        (None, {"code": "MG"}, ()),
        (None, None, ()),
        ("x", 5, ()),
    ],
)
async def test_locais_cidade_e_uf(cidade: object, estado: object, locais: tuple[str, ...]) -> None:
    resultado, _ = await _coletar(_com(city=cidade, state=estado))
    assert _vagas(resultado)[0].locais == locais


_PORTUGAL = {"name": "Portugal", "code": "PT"}
_BRASIL = {"name": "Brasil", "code": "BR"}


def _endereco(**campos: object) -> dict[str, Any]:
    """O `address` da primeira vaga da captura (país Brasil) com os campos trocados."""
    endereco: dict[str, Any] = _normal()["data"][0]["address"]
    return endereco | campos


@pytest.mark.parametrize(
    ("campos", "locais"),
    [
        ({"address": _endereco(country=_PORTUGAL)}, ("Barro Alto, GO, Portugal",)),
        ({"address": _endereco(country={"name": "Portugal"})}, ("Barro Alto, GO, Portugal",)),
        ({"address": _endereco(country=_BRASIL)}, ("Barro Alto, GO",)),
        ({"address": _endereco(country={"name": "Brazil"})}, ("Barro Alto, GO",)),
        ({"address": _endereco(country=None)}, ("Barro Alto, GO",)),
        ({"address": _endereco(country="Portugal")}, ("Barro Alto, GO",)),
        ({"address": None}, ("Barro Alto, GO",)),
        (
            {
                "city": None,
                "state": None,
                "address": _endereco(country=_PORTUGAL, foreignCity="Lisboa"),
            },
            ("Lisboa, Portugal",),
        ),
        (
            {
                "city": None,
                "state": None,
                "address": _endereco(country=_PORTUGAL, foreignCity="Porto", foreignState="Norte"),
            },
            ("Porto, Norte, Portugal",),
        ),
        (
            {
                "city": None,
                "state": None,
                "address": _endereco(
                    country={"name": "Estados Unidos", "code": "US"},
                    foreignCity={"name": "Boston"},
                    foreignState={"name": "MA"},
                ),
            },
            ("Boston, MA, Estados Unidos",),
        ),
        ({"city": None, "state": None, "address": _endereco(foreignCity="Lisboa")}, ("Lisboa",)),
        ({"city": None, "state": None, "address": _endereco(country=_PORTUGAL)}, ("Portugal",)),
        ({"city": None, "state": None, "address": _endereco()}, ()),
    ],
)
async def test_pais_e_cidade_de_fora_do_address(
    campos: dict[str, Any], locais: tuple[str, ...]
) -> None:
    resultado, _ = await _coletar(_com(**campos))
    assert _vagas(resultado)[0].locais == locais


@pytest.mark.parametrize(
    ("cidade", "uf", "pais", "esperado"),
    [
        ("Lisboa", None, "Portugal", "PT"),
        ("Boston", "MA", "Estados Unidos", "US"),
        ("Austin", None, "United States", "US"),
        # shortcut: só país que está em _PAISES sai do Brasil; país fora da tabela (Angola) fica sem
        # país e estado de fora com sigla de UF (MA) vira BR; melhorar com tabela de países maior.
        ("Luanda", None, "Angola", None),
        ("Maputo", "MA", "Moçambique", "BR"),
    ],
)
def test_texto_do_local_de_fora_e_lido_com_o_pais(
    cidade: str, uf: str | None, pais: str, esperado: str | None
) -> None:
    code = {"Portugal": "PT", "Estados Unidos": "US", "United States": "US"}.get(pais, "XX")
    job: dict[str, object] = {
        "city": {"name": cidade},
        "state": {"code": uf} if uf else None,
        "address": {"country": {"name": pais, "code": code}},
    }
    (texto,) = solides._local(job)
    assert ler_locais([texto])[0].pais == esperado


async def test_id_texto_e_aceito_e_escapado_no_link() -> None:
    resultado, _ = await _coletar(_com(id="a b/1"))
    vaga = _vagas(resultado)[0]
    assert (vaga.id_externo, vaga.url) == (
        "a b/1",
        "https://diefra.vagas.solides.com.br/vaga/a%20b%2F1",
    )


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"), escopo="bamex")
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, pedidos = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["951514"]
    assert len(pedidos) == 1


@pytest.mark.parametrize(
    "corpo",
    [
        '{"ok": true}',
        '{"data": "x"}',
        '{"data": {"a": 1}}',
        '{"data": [1, "x"]}',
        '{"data": [{"title": "sem id"}]}',
        '{"data": [{"id": 1}]}',
        '{"data": [{"id": true, "title": "id booleano"}]}',
        '{"data": [{"id": 1.5, "title": "id fracionado"}]}',
        "isto não é json",
        "[]",
        "null",
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    resultado, _ = await _coletar(
        _com(
            createdAt=5,
            date="x",
            salary=[1],
            jobType=7,
            homeOffice="x",
            city=None,
            state=[],
            seniority="x",
            recruitmentContractType=None,
            description=None,
            companyName=None,
        )
    )
    assert resultado.estado == "ok"
    v = _vagas(resultado)[0]
    assert (v.publicada_em, v.prazo, v.salario_estruturado) == (None, None, None)
    assert (v.modalidade_declarada, v.contrato_declarado) == (None, None)
    assert (v.locais, v.etiquetas, v.descricao, v.empresa) == ((), (), "", "diefra")


async def test_vaga_sem_titulo_ou_id_pula_e_deixa_parcial() -> None:
    dados = _normal()
    dados["data"][1].pop("title")
    dados["data"][2]["id"] = None
    resultado, _ = await _coletar(httpx.Response(200, json=dados | {"totalPages": 1}))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 3


@pytest.mark.parametrize("escopo", ["../x?y#z", "evil.com/#", "", "a b", "-a", "x" * 64, "dié"])
async def test_escopo_que_nao_e_slug_falha_sem_pedido(escopo: str) -> None:
    resultado, pedidos = await _coletar(_json("normal"), escopo=escopo)
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.empresa_nao_encontrada"
    assert (resultado.pedidos, pedidos) == (0, [])


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


async def test_erro_na_segunda_pagina_mantem_a_primeira() -> None:
    resultado, _ = await _coletar(_json("normal"), httpx.Response(500))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(resultado.vagas) == 5


async def test_404_na_segunda_pagina_mantem_a_primeira_e_fica_parcial() -> None:
    resultado, pedidos = await _coletar(_json("normal"), _json("nao_encontrado", 404))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(resultado.vagas) == 5
    assert len(pedidos) == 2


async def test_pagina_2_ilegivel_mantem_a_primeira() -> None:
    resultado, _ = await _coletar(_json("normal"), httpx.Response(200, text="isto não é json"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 5


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_nunca_pede_condicional() -> None:
    # sem ETag nem Last-Modified nas respostas da API: o coletor não manda validador
    url = "https://apigw.solides.com.br/jobs/v3/companies/diefra/vacancies?page=1&take=25"
    leitor = LeitorFixo({url: Validadores('"x"', "Mon, 02 Nov 2026 10:00:00 GMT")})
    _, pedidos = await _coletar(_json("vazio"), leitor=leitor, condicional=True)
    assert "If-None-Match" not in pedidos[0].headers
    assert "If-Modified-Since" not in pedidos[0].headers


async def test_detalhar_nao_faz_nada(http_proibido: HttpEducado) -> None:
    resultado, _ = await _coletar(_json("normal"), _json("pagina_2"))
    assert await solides.COLETOR.detalhar(resultado.vagas[0], http_proibido) is None


@pytest.mark.parametrize(
    ("entrada", "slug"),
    [
        ("diefra", "diefra"),
        (" Diefra ", "diefra"),  # caixa baixa: o slug é subdomínio (D45)
        ("https://diefra.vagas.solides.com.br", "diefra"),
        ("https://DIEFRA.vagas.solides.com.br/", "diefra"),
        ("https://diefra.vagas.solides.com.br/vaga/951514", "diefra"),
        ("diefra.vagas.solides.com.br", "diefra"),
        ("http://bamex.vagas.solides.com.br/vaga/1?x=2", "bamex"),
        (
            "https://apigw.solides.com.br/jobs/v3/companies/diefra/vacancies?page=1&take=25",
            "diefra",
        ),
        ("https://apigw.solides.com.br/jobs/v3/companies/Diefra", "diefra"),
    ],
)
async def test_resolver_aceita_url_do_quadro_e_devolve_o_slug(
    entrada: str, slug: str, http_proibido: HttpEducado
) -> None:
    resolvido = await solides.COLETOR.resolver(entrada, http_proibido)
    assert resolvido == {"identificador": slug}


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "https://vagas.solides.com.br",
        "https://vagas.solides.com.br/vaga/1",
        "https://a.b.vagas.solides.com.br/",
        "https://diefra.gupy.io",
        "https://solides.com.br/diefra",
        "https://diefra.vagas.solides.com.br.evil.com/",
        "https://diefra.vagas.solides.com.br@evil.com/",
        "ftp://diefra.vagas.solides.com.br",
        "https://apigw.solides.com.br/jobs/v3/companies",
        "https://apigw.solides.com.br/jobs/v2/companies/diefra",
        "https://apigw.solides.com.br/outra/coisa",
        "dief ra",
        "diéfra",
        "-diefra",
        "x" * 64,
    ],
)
async def test_resolver_recusa_o_que_nao_e_quadro(entrada: str, http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await solides.COLETOR.resolver(entrada, http_proibido)
