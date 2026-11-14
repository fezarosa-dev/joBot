import json
from collections.abc import AsyncIterator, Callable, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.coletores.carreiras import amazon
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.relogio import Relogio
from jobot.nucleo.tratamento.locais import ler_locais

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "amazon"
API = "https://www.amazon.jobs/en/search.json"
URL_BR = f"{API}?normalized_country_code%5B%5D=BRA&result_limit=100&offset=0&sort=recent"
Responder = Callable[[httpx.Request], httpx.Response]
ETAG = 'W/"fa2bf45ce41d9979fe74d0af8cf958a1"'


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _dados(caso: str = "normal") -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_texto(caso))
    return dados


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


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = "BR",
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
        resultado = await amazon.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"teste não faz pedido: {pedido.url}")

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


def _uma_pagina(**cabecalhos: str) -> httpx.Response:
    """O exemplo `normal` com `hits` igual às 5 vagas: a lista termina na página 1."""
    dados = _dados()
    dados["hits"] = len(dados["jobs"])
    return httpx.Response(200, json=dados, headers=cabecalhos)


def _pagina(numero: int, hits: int = 406, n: int = 100) -> httpx.Response:
    """Uma página de `n` vagas a partir da primeira do `normal`, com id e caminho próprios."""
    dados = _dados()
    modelo = dados["jobs"][0]
    jobs = []
    for i in range(n):
        job = deepcopy(modelo)
        job["id_icims"] = f"{numero}{i:03d}"
        job["job_path"] = f"/en/jobs/{numero}{i:03d}/vaga-{numero}-{i}"
        jobs.append(job)
    dados |= {"jobs": jobs, "hits": hits}
    return httpx.Response(200, json=dados)


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = amazon.COLETOR
    assert registro.descobrir()["amazon"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "B"
    assert (prova.intervalo_min, prova.max_pedidos, prova.espera_s) == (360, None, 2.0)
    assert prova.credito_obrigatorio is False
    assert prova.hosts == ("www.amazon.jobs",)


def test_escopos_um_por_pais_das_buscas() -> None:
    ctx = ContextoColeta(empresas=[], termos=["python"], paises=["br", "PT", " BR ", "ZZ"])
    # país que a Amazon não tem na tabela do coletor sai: não há como pedir o código de 3 letras
    assert list(amazon.COLETOR.escopos(ctx)) == ["BR", "PT"]


def test_escopos_sem_pais_usa_o_brasil() -> None:
    ctx = ContextoColeta(empresas=[], termos=[], paises=[])
    assert list(amazon.COLETOR.escopos(ctx)) == ["BR"]  # A21


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_uma_pagina(ETag=ETAG))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert primeira.fonte == "amazon" and primeira.escopo == "BR"
    assert primeira.url == "https://www.amazon.jobs/en/jobs/10604187/aws-account-manager-ags"
    assert primeira.id_externo == "10604187"
    assert primeira.titulo == "AWS Account Manager, AGS"
    assert primeira.empresa == "Amazon AWS Services Brazil Ltd"
    assert primeira.descricao_formato == "html"
    bruto = _dados()["jobs"][0]
    assert bruto["description"] in primeira.descricao
    assert bruto["basic_qualifications"] in primeira.descricao
    assert bruto["preferred_qualifications"] in primeira.descricao
    assert primeira.publicada_em == datetime(2026, 11, 13, tzinfo=UTC)
    assert primeira.contrato_declarado == "full-time"
    assert primeira.etiquetas == ("Sales, Advertising, & Account Management", "Tech Sales")
    assert primeira.url_candidatura is None and primeira.salario_estruturado is None
    assert [v.id_externo for v in vagas] == [
        "10604187",
        "10604186",
        "10604193",
        "10604199",
        "10602549",
    ]
    assert all(v.url.startswith("https://www.amazon.jobs/en/jobs/") for v in vagas)
    assert len(pedidos) == 1


async def test_locais_vem_do_texto_json_de_locations() -> None:
    resultado, _ = await _coletar(_uma_pagina())
    vagas = _vagas(resultado)
    assert vagas[0].locais == ("Sao Paulo, SP, Brazil",)
    assert vagas[4].locais == ("Nova Santa Rita, RS, Brazil",)
    local = ler_locais(vagas[4].locais)[0]
    assert (local.cidade, local.uf, local.pais) == ("Nova Santa Rita", "RS", "BR")


async def test_varias_locations_e_texto_que_nao_e_json() -> None:
    dados = _dados()
    primeiro = json.loads(dados["jobs"][0]["locations"][0])
    outro = primeiro | {"normalizedCityName": "Campinas", "region": "SP"}
    dados["jobs"][0]["locations"] = [
        json.dumps(primeiro),
        json.dumps(outro),
        "isto não é json",
        "[1, 2]",
        json.dumps(primeiro),
    ]
    dados["hits"] = len(dados["jobs"])
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].locais == ("Sao Paulo, SP, Brazil", "Campinas, SP, Brazil")


async def test_modalidade_pelo_type_de_locations() -> None:
    dados = _dados()
    base_loc = json.loads(dados["jobs"][0]["locations"][0])
    tipos = {1: ["VIRTUAL"], 2: ["ONSITE", "VIRTUAL"], 3: []}
    for i, tipo in tipos.items():
        dados["jobs"][i]["locations"] = [json.dumps(base_loc | {"type": t}) for t in tipo]
    dados["hits"] = len(dados["jobs"])
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    modalidades = [v.modalidade_declarada for v in _vagas(resultado)]
    assert modalidades == ["ONSITE", "VIRTUAL", None, None, "ONSITE"]


async def test_link_so_com_o_host_fixo_e_caminho_valido() -> None:
    dados = _dados()
    dados["jobs"][0]["job_path"] = "//evil.example/x"
    dados["jobs"][1]["job_path"] = "https://evil.example/x"
    dados["jobs"][2]["job_path"] = "/en/jobs/10604193/ok?x=1#y"
    dados["jobs"][3]["job_path"] = ""
    dados["hits"] = len(dados["jobs"])
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["10602549"]


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("November 13, 2026", datetime(2026, 11, 13, tzinfo=UTC)),
        ("January 5, 2027", datetime(2027, 1, 5, tzinfo=UTC)),
        ("February 30, 2026", None),
        ("13 de novembro de 2026", None),
        ("2026-11-13", None),
        (None, None),
        (20261113, None),
    ],
)
async def test_posted_date_em_ingles(bruto: object, esperado: datetime | None) -> None:
    dados = _dados()
    dados["jobs"][0]["posted_date"] = bruto
    dados["hits"] = len(dados["jobs"])
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].publicada_em == esperado


async def test_vazio() -> None:
    resultado, _ = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(_vagas(resultado)) == 1


async def test_erro_declarado_pela_api_falhou() -> None:
    resultado, _ = await _coletar(_json("erro_limite"))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


@pytest.mark.parametrize(
    "corpo",
    [
        '{"results": []}',
        "[]",
        '{"jobs": {}, "hits": 1}',
        '{"jobs": [], "hits": true}',
        '{"jobs": [], "hits": "0"}',
        '{"jobs": []}',
        '{"jobs": [], "hits": 0, "error": "algo deu errado"}',
        "isto não é json",
        '{"jobs": [1, "x"], "hits": 2}',
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_pagina_ilegivel_depois_da_primeira_fica_parcial() -> None:
    resultado, pedidos = await _coletar(_pagina(1), httpx.Response(200, text="<html>"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(_vagas(resultado)) == 100 and len(pedidos) == 2


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _dados()
    dados["jobs"][0] |= {
        "description": None,
        "basic_qualifications": 7,
        "preferred_qualifications": None,
        "locations": None,
        "job_schedule_type": None,
        "job_category": True,
        "job_family": None,
        "posted_date": None,
    }
    dados["hits"] = len(dados["jobs"])
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.descricao, vaga.etiquetas, vaga.locais) == ("", (), ())
    assert (vaga.modalidade_declarada, vaga.contrato_declarado, vaga.publicada_em) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize("campo", ["id_icims", "title", "company_name", "job_path"])
async def test_campo_obrigatorio_ausente_pula_a_vaga(campo: str) -> None:
    dados = _dados()
    dados["jobs"][1][campo] = None
    dados["hits"] = len(dados["jobs"])
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 4


async def test_id_booleano_nao_vale() -> None:
    dados = _dados()
    dados["jobs"][1]["id_icims"] = True
    dados["hits"] = len(dados["jobs"])
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, len(resultado.vagas)) == ("parcial", 4)


async def test_paginacao_segue_ate_o_total() -> None:
    resultado, pedidos = await _coletar(_pagina(1, 250), _pagina(2, 250), _pagina(3, 250, n=50))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 3)
    assert len(_vagas(resultado)) == 250
    assert [p.url.params["offset"] for p in pedidos] == ["0", "100", "200"]


async def test_paginacao_para_em_pagina_vazia_e_avisa_que_faltou() -> None:
    resultado, pedidos = await _coletar(_pagina(1, 406), _json("vazio"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.listagem_incompleta")
    assert (len(_vagas(resultado)), len(pedidos)) == (100, 2)


async def test_teto_de_paginas_vira_parcial_limite_atingido() -> None:
    contador = iter(range(1, 1000))
    resultado, pedidos = await _coletar(lambda _: _pagina(next(contador), hits=100_000))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert len(pedidos) == amazon.MAX_PAGINAS == resultado.pedidos
    assert len(resultado.vagas) == 100 * amazon.MAX_PAGINAS


async def test_sem_max_pedidos_o_orcamento_nao_corta() -> None:
    resultado, _ = await _coletar(_pagina(1, 250), _pagina(2, 250), _pagina(3, 250, n=50))
    assert resultado.estado == "ok"
    assert amazon.COLETOR.max_pedidos is None


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


async def test_erro_depois_da_primeira_pagina_fica_parcial() -> None:
    resultado, _ = await _coletar(_pagina(1), httpx.Response(500))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(_vagas(resultado)) == 100


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


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

    monkeypatch.setattr(amazon, "juntar_paginas", espia)

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == ETAG:
            return httpx.Response(304, headers={"ETag": ETAG})
        return _uma_pagina(ETag=ETAG)

    leitor = LeitorFixo({URL_BR: Validadores(ETAG, None)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-None-Match") for p in pedidos] == [ETAG]
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_304_depois_de_pagina_nova_fica_parcial() -> None:
    url_p2 = f"{API}?normalized_country_code%5B%5D=BRA&result_limit=100&offset=100&sort=recent"

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.params["offset"] == "100":
            return httpx.Response(304)
        return _pagina(1)

    leitor = LeitorFixo({url_p2: Validadores(ETAG, None)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.listagem_incompleta")
    assert (len(_vagas(resultado)), len(pedidos)) == (100, 2)


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo="PT")
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert pedido.url.host == "www.amazon.jobs" and pedido.url.path == "/en/search.json"
    assert pedido.url.params.get_list("normalized_country_code[]") == ["PRT"]
    assert dict(pedido.url.params) == {
        "normalized_country_code[]": "PRT",
        "result_limit": "100",
        "offset": "0",
        "sort": "recent",
    }
    assert "Cookie" not in pedido.headers and "Authorization" not in pedido.headers


async def test_url_do_pedido_do_brasil() -> None:
    _, pedidos = await _coletar(_json("vazio"))
    assert str(pedidos[0].url) == URL_BR


async def test_escopo_que_nao_e_nosso_levanta() -> None:
    with pytest.raises(ValueError):
        await _coletar(_json("vazio"), escopo="Brazil")


async def test_resolver_nao_se_aplica(http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await amazon.COLETOR.resolver("amazon", http_proibido)


async def test_detalhar_nao_faz_nada(http_proibido: HttpEducado) -> None:
    item = _vagas((await _coletar(_uma_pagina()))[0])[0]
    assert await amazon.COLETOR.detalhar(item, http_proibido) is None
