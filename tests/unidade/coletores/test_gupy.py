import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, gupy, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio
from jobot.nucleo.url import canonica

pytestmark = pytest.mark.anyio

RAIZ = Path(__file__).resolve().parents[3]
PASTA = RAIZ / "tests" / "fixtures" / "gupy"
EMPRESAS_JSON = RAIZ / "src" / "jobot" / "nucleo" / "dados" / "empresas.json"
API = "https://portal.gupy.io/api/job-search/jobs"
EMPRESA = "empresa:agriness:Agriness"
URL_PAGINA_0 = f"{API}?careerPageName=Agriness&limit=100&offset=0"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str, extensao: str = "json") -> str:
    return (PASTA / f"{caso}.{extensao}").read_text(encoding="utf-8")


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
    escopo: str = EMPRESA,
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
        resultado = await gupy.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


async def _resolver(
    entrada: str, *respostas: httpx.Response | Responder
) -> tuple[dict[str, str], list[httpx.Request]]:
    pedidos: list[httpx.Request] = []
    fila = list(respostas)

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return r if isinstance(r, httpx.Response) else r(pedido)

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(httpx.MockTransport(servidor), relogio, LeitorFixo(), "0.1.0", _sem_dns)
    try:
        resolvido = await gupy.COLETOR.resolver(entrada, cli.escopo())
    finally:
        await cli.fechar()
    return dict(resolvido), pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _vaga_falsa(n: int, host: str = "agriness.gupy.io") -> dict[str, Any]:
    return {
        "id": n,
        "name": f"Vaga {n}",
        "careerPageName": "Agriness",
        "description": "Texto.",
        "jobUrl": f"https://{host}/job/{n}?jobBoardSource=gupy_portal",
        "publishedDate": "2026-11-13T18:15:25.334Z",
        "applicationDeadline": None,
        "workplaceType": "remote",
        "type": "vacancy_type_effective",
        "city": "",
        "state": "",
    }


def _pagina(inicio: int, quantos: int, limite: int = 100) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": [_vaga_falsa(n) for n in range(inicio, inicio + quantos)],
            "pagination": {"total": 100, "limit": limite, "offset": inicio},
        },
    )


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = gupy.COLETOR
    assert registro.descobrir()["gupy"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "A"
    assert (prova.max_pedidos, prova.espera_s) == (30, 2.0) == (limites.max_pedidos, 2.0)
    assert prova.hosts == ("portal.gupy.io",)


def test_escopos_por_empresa_e_por_cargo() -> None:
    empresas = [
        Empresa(nome="Agriness", fonte="gupy", identificador="agriness"),
        Empresa(
            nome="Beep Saúde",
            fonte="gupy",
            identificador="beepsaude",
            parametros={"careerPageName": "Beep Saúde "},
        ),
        Empresa(nome="Agriness de novo", fonte="gupy", identificador="agriness"),
        Empresa(
            nome="Sem nome",
            fonte="gupy",
            identificador="x",
            parametros={"careerPageName": "  "},
        ),
    ]
    ctx = ContextoColeta(empresas=empresas, termos=["Dev", " Dev ", "", "dados: BI"], paises=["BR"])
    assert list(gupy.COLETOR.escopos(ctx)) == [
        "empresa:agriness:Agriness",
        "empresa:beepsaude:Beep Saúde",
        "empresa:x:Sem nome",
        "cargo:Dev",
        "cargo:dados: BI",
    ]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 4
    primeira, talentos = vagas[0], vagas[2]
    assert primeira.fonte == "gupy" and primeira.escopo == EMPRESA
    assert primeira.url == (
        "https://agriness.gupy.io/job/eyJqb2JJZCI6MTI4OTA2ODQsInNvdXJjZSI6Imd1cHlfcG9ydGFsIn0="
        "?jobBoardSource=gupy_portal"
    )
    assert primeira.titulo == "Desenvolvedor(a) Backend Sênior | Python, PostgreSQL e Kafka"
    assert primeira.empresa == "Agriness"
    assert primeira.id_externo == "12890684"
    assert primeira.descricao_formato == "texto"
    assert primeira.descricao.startswith("Na Agriness, nossos sistemas")
    assert primeira.locais == ()
    assert primeira.modalidade_declarada == "remote"
    assert primeira.contrato_declarado == "vacancy_type_effective"
    assert primeira.publicada_em == datetime(2026, 11, 13, 18, 15, 25, 334000, tzinfo=UTC)
    assert primeira.prazo == date(2027, 1, 12)
    assert primeira.url_candidatura is None and primeira.salario_texto is None
    assert talentos.titulo == "Banco de Talentos - Exclusivo Para Pessoas Com Deficiência"
    assert talentos.locais == ("Florianópolis, Santa Catarina",)
    assert talentos.contrato_declarado == "vacancy_type_talent_pool"
    assert talentos.prazo is None
    assert all(v.url.startswith("https://") for v in vagas)
    assert len(pedidos) == 1


async def test_job_board_source_sai_da_canonica() -> None:
    resultado, _ = await _coletar(_json("normal"))
    for vaga in _vagas(resultado):
        assert "jobBoardSource" in vaga.url  # o coletor não mexe na URL
        assert "jobboardsource" not in canonica(vaga.url).lower()


async def test_vazio() -> None:
    resultado, _ = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_vaga_de_outro_host_e_descartada() -> None:
    # Hapvida usa o nome genérico "Página de Carreira": a API devolve vaga de outras empresas
    dados = json.loads(_texto("normal"))
    dados["data"][1]["jobUrl"] = "https://outra.gupy.io/job/abc?jobBoardSource=gupy_portal"
    dados["data"][2]["jobUrl"] = "https://agriness.gupy.io.evil.com/job/abc"
    dados["data"][3]["jobUrl"] = "https://AGRINESS.gupy.io/job/abc"  # a caixa do host não conta
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert [v.id_externo for v in _vagas(resultado)] == ["12890684", "1125876"]


async def test_cargo_nao_filtra_por_host() -> None:
    dados = json.loads(_texto("normal"))
    dados["data"][1]["jobUrl"] = "https://outra.gupy.io/job/abc?jobBoardSource=gupy_portal"
    resultado, pedidos = await _coletar(httpx.Response(200, json=dados), escopo="cargo:python")
    assert len(_vagas(resultado)) == 4
    assert dict(pedidos[0].url.params) == {"jobName": "python", "limit": "100", "offset": "0"}


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["7781687"]


@pytest.mark.parametrize(
    "corpo",
    ['{"results": []}', "[]", '{"data": {}}', "isto não é json", '{"data": [1, "x"]}'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = json.loads(_texto("normal"))
    dados["data"][0] |= {
        "publishedDate": "2026-11-13T18:15:25",  # sem fuso
        "applicationDeadline": "logo",
        "city": None,
        "state": 7,
        "description": None,
        "workplaceType": None,
        "type": 3,
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.prazo, vaga.locais, vaga.descricao) == (None, None, (), "")
    assert (vaga.modalidade_declarada, vaga.contrato_declarado) == (None, None)


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = json.loads(_texto("normal"))
    dados["data"][1]["jobUrl"] = "javascript:alert(1)"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 3


async def test_paginacao_avanca_ate_pagina_menor_que_limit() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        offset = int(pedido.url.params["offset"])
        return _pagina(offset, 100 if offset < 200 else 37)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 3)
    assert [p.url.params["offset"] for p in pedidos] == ["0", "100", "200"]
    assert {p.url.params["limit"] for p in pedidos} == {"100"}
    assert len(resultado.vagas) == 237


async def test_paginacao_para_na_pagina_vazia() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        offset = int(pedido.url.params["offset"])
        return _pagina(offset, 100) if offset == 0 else _json("vazio")

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 100, 2)


async def test_paginacao_segue_o_limit_da_resposta() -> None:
    # a API devolveu páginas de 50 mesmo com limit=100 pedido: 50 não é "menor que limit"
    def pagina(pedido: httpx.Request) -> httpx.Response:
        offset = int(pedido.url.params["offset"])
        return _pagina(offset, 50 if offset < 100 else 10, limite=50)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, len(resultado.vagas)) == ("ok", 110)
    assert [p.url.params["offset"] for p in pedidos] == ["0", "50", "100"]


async def test_31o_pedido_fica_no_limite() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        return _pagina(int(pedido.url.params["offset"]), 100)

    resultado, pedidos = await _coletar(pagina, max_pedidos=30)
    assert (resultado.estado, resultado.motivo) == ("no_limite", "saude.orcamento")
    assert (resultado.pedidos, len(pedidos)) == (30, 30)
    assert len(resultado.vagas) == 3000


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

    monkeypatch.setattr(gupy, "juntar_paginas", espia)
    etag = '"15yfvsdfch46os"'

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _json("normal", ETag=etag)

    leitor = LeitorFixo({URL_PAGINA_0: Validadores(etag, None)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-None-Match") for p in pedidos] == [etag]
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_so_a_primeira_pagina_leva_pedido_condicional() -> None:
    etag = '"x"'
    leitor = LeitorFixo(
        {
            URL_PAGINA_0: Validadores(etag, None),
            URL_PAGINA_0.replace("offset=0", "offset=100"): Validadores(etag, None),
        }
    )

    def pagina(pedido: httpx.Request) -> httpx.Response:
        offset = int(pedido.url.params["offset"])
        return _pagina(offset, 100 if offset == 0 else 5)

    resultado, pedidos = await _coletar(pagina, leitor=leitor, condicional=True)
    assert resultado.estado == "ok"
    assert [p.headers.get("If-None-Match") for p in pedidos] == [etag, None]


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
    assert str(pedido.url) == URL_PAGINA_0
    assert dict(pedido.url.params) == {"careerPageName": "Agriness", "limit": "100", "offset": "0"}


async def test_nome_de_exibicao_vai_como_esta() -> None:
    # a API casa o nome com a caixa exata (Agriness dá 4, agriness dá 0): nada de minúsculas
    _, pedidos = await _coletar(
        _json("vazio"), escopo="empresa:ihara:IHARA - Agricultura é a nossa vida"
    )
    assert pedidos[0].url.params["careerPageName"] == "IHARA - Agricultura é a nossa vida"
    _, pedidos = await _coletar(_json("vazio"), escopo="empresa:spdmpaisfor:SPDM/PAIS")
    assert pedidos[0].url.params["careerPageName"] == "SPDM/PAIS"
    # o `:` dentro do nome não confunde o identificador
    _, pedidos = await _coletar(_json("vazio"), escopo="empresa:x:A: B")
    assert pedidos[0].url.params["careerPageName"] == "A: B"


@pytest.mark.parametrize("escopo", ["", "agriness", "empresa:agriness", "empresa::Agriness", "x:y"])
async def test_escopo_que_nao_e_do_coletor_levanta(escopo: str) -> None:
    with pytest.raises(ValueError):
        await _coletar(_json("vazio"), escopo=escopo)


@pytest.mark.parametrize(
    "entrada",
    [
        "agriness",
        " Agriness ",
        "AGRINESS",
        "agriness.gupy.io",
        "https://agriness.gupy.io/",
        "https://agriness.gupy.io",
        "http://Agriness.gupy.io/job/eyJ?jobBoardSource=gupy_portal",
    ],
)
async def test_resolver_le_o_publication_name_da_pagina(entrada: str) -> None:
    pagina = httpx.Response(200, text=_texto("pagina_carreira", "html"))
    resolvido, pedidos = await _resolver(entrada, pagina)
    # name é "Agriness - Trabalhe conosco"; vale o publicationName, sem o espaço do fim
    assert resolvido == {"identificador": "agriness", "careerPageName": "Agriness"}
    assert [(p.method, str(p.url)) for p in pedidos] == [("GET", "https://agriness.gupy.io/")]


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "   ",
        "portal",
        "www",
        "https://portal.gupy.io/",
        "https://agriness.gupy.io.evil.com/",
        "https://agriness.gupy.io@evil.com/",
        "https://evil.com/agriness.gupy.io",
        "https://jobs.lever.co/agriness",
        "https://a.b.gupy.io/",
        "ftp://agriness.gupy.io/",
        "agri ness",
        "agríness",
        "x" * 64,
    ],
)
async def test_resolver_recusa_o_que_nao_e_da_gupy_sem_fazer_pedido(entrada: str) -> None:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"resolver não faz pedido: {pedido.url}")

    with pytest.raises(ValueError):
        await _resolver(entrada, recusa)


def _pagina_com(next_data: str) -> httpx.Response:
    return httpx.Response(
        200,
        text=f'<html><body><script id="__NEXT_DATA__" type="application/json">{next_data}'
        "</script></body></html>",
    )


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, text="<html><body>sem dados</body></html>"),
        httpx.Response(200, text='<script id="outro">{}</script>'),
        _pagina_com("não é json"),
        _pagina_com("[]"),
        _pagina_com("{}"),
        _pagina_com('{"props": {"pageProps": {}}}'),
        _pagina_com('{"props": {"pageProps": {"careerPage": {"name": "Agriness"}}}}'),
        _pagina_com('{"props": {"pageProps": {"careerPage": {"publicationName": "  "}}}}'),
        _pagina_com('{"props": {"pageProps": {"careerPage": {"publicationName": 7}}}}'),
        httpx.Response(404, text="não achei"),
    ],
)
async def test_resolver_pagina_sem_publication_name_levanta(resposta: httpx.Response) -> None:
    with pytest.raises(ValueError):
        await _resolver("agriness", resposta)


NOVE = {
    "porto": "Porto",
    "vempracbc": "CBC",
    "beepsaude": "Beep Saúde",
    "hapvidandi": "Página de Carreira",
    "spdmpaisfor": "SPDM/PAIS",
    "afyamedicina": "Carreira Médica na Afya",
    "cnaidiomas": "CNA Idiomas",
    "ihara": "IHARA - Agricultura é a nossa vida",
    "ourofinoagro": "Vem ser Ourofino Agrociência!",
}


def test_empresas_json_traz_o_career_page_name_das_nove() -> None:
    lista = json.loads(EMPRESAS_JSON.read_text(encoding="utf-8"))["empresas"]
    gupy_ = {e["identificador"]: e["parametros"] for e in lista if e["fonte"] == "gupy"}
    assert len(gupy_) == 28
    assert {i: p for i, p in gupy_.items() if p} == {
        i: {"careerPageName": n} for i, n in NOVE.items()
    }
