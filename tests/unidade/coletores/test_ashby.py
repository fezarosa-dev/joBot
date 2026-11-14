import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import ashby, base, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import (
    TETO_PADRAO,
    ClienteEducado,
    HttpEducado,
    RespostaGrande,
    Validadores,
)
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "ashby"
URL_BELVO = "https://api.ashbyhq.com/posting-api/job-board/belvo?includeCompensation=true"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _dados(caso: str) -> dict[str, list[dict[str, object]]]:
    carregado: dict[str, list[dict[str, object]]] = json.loads(_texto(caso))
    return carregado


def _json(caso: str, status: int = 200, **cabecalhos: str) -> httpx.Response:
    return httpx.Response(
        status,
        text=_texto(caso),
        headers={"Content-Type": "application/json; charset=utf-8", **cabecalhos},
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
    escopo: str = "belvo",
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
        resultado = await ashby.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """O `resolver` do Ashby só lê o texto: qualquer pedido é erro do teste."""

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


def _cadastrar(nome: str = "Belvo", identificador: str = "belvo") -> None:
    empresas = [Empresa(nome=nome, fonte="ashby", identificador=identificador)]
    ashby.COLETOR.escopos(ContextoColeta(empresas=empresas, termos=[], paises=[]))


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = ashby.COLETOR
    assert registro.descobrir()["ashby"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("api.ashbyhq.com",)


def test_escopos_um_por_empresa() -> None:
    empresas = [
        Empresa(nome="OpenAI", fonte="ashby", identificador="openai"),
        Empresa(nome="Belvo", fonte="ashby", identificador="belvo"),
        Empresa(nome="OpenAI de novo", fonte="ashby", identificador="openai"),
    ]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(ashby.COLETOR.escopos(ctx)) == ["openai", "belvo"]


async def test_normal() -> None:
    _cadastrar()
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 3
    primeira = vagas[0]
    assert primeira.fonte == "ashby" and primeira.escopo == "belvo"
    assert primeira.url == "https://jobs.ashbyhq.com/belvo/5a34dbde-1947-4be7-b048-5acea47b0e86"
    assert primeira.url_candidatura == primeira.url + "/application"
    assert primeira.titulo == "CV for Future Opportunities"
    assert primeira.empresa == "Belvo"
    assert primeira.id_externo == "5a34dbde-1947-4be7-b048-5acea47b0e86"
    assert primeira.locais == ("🇧🇷 Sao Paulo / 🇲🇽 Mexico City / 🇪🇸Barcelona / 🌎Remote",)
    assert primeira.publicada_em == datetime(2021, 6, 7, 10, 41, 2, 331000, tzinfo=UTC)
    assert primeira.modalidade_declarada == "Remote"
    assert primeira.contrato_declarado == "FullTime"
    assert primeira.descricao_formato == "html"
    assert primeira.descricao.startswith('<p style="min-height:1.5em">')
    assert primeira.etiquetas == ("CV",)
    assert (primeira.prazo, primeira.salario_texto, primeira.salario_estruturado) == (
        None,
        None,
        None,
    )
    assert all(v.url.startswith(("https://", "http://")) for v in vagas)
    assert len(pedidos) == 1


async def test_empresa_vem_do_cadastro_e_cai_no_identificador() -> None:
    _cadastrar(nome="Belvo Tecnologia")
    resultado, _ = await _coletar(_json("normal"))
    assert {v.empresa for v in _vagas(resultado)} == {"Belvo Tecnologia"}
    resultado, _ = await _coletar(_json("normal"), escopo="sem-cadastro")
    assert {v.empresa for v in _vagas(resultado)} == {"sem-cadastro"}


async def test_vazio() -> None:
    resultado, _ = await _coletar(_json("vazio"), escopo="supabase")
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["5a34dbde-1947-4be7-b048-5acea47b0e86"]


@pytest.mark.parametrize(
    "corpo",
    ['{"postings": []}', "[]", '{"jobs": {}}', "isto não é json", '{"jobs": [1, "x"]}'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_so_is_listed_verdadeiro_entra() -> None:
    resultado, _ = await _coletar(_json("compensacao"))
    assert (resultado.estado, resultado.motivo) == ("ok", None)  # a não listada não é "pulada"
    assert [v.titulo for v in _vagas(resultado)] == ["Senior Backend Engineer"]


async def test_quadro_so_com_vaga_nao_listada_e_ok_vazio() -> None:
    dados = _dados("compensacao")
    dados["jobs"] = dados["jobs"][1:]
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_is_listed_que_nao_e_booleano_conta_como_formato_mudou() -> None:
    # Se o Ashby renomear o campo, "ok" com zero vagas fecharia todas as vagas da empresa.
    dados = _dados("normal")
    del dados["jobs"][1]["isListed"]
    dados["jobs"][2]["isListed"] = "true"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 1
    for job in dados["jobs"]:
        job.pop("isListed", None)
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_compensacao_vira_salario_texto() -> None:
    resultado, _ = await _coletar(_json("compensacao"))
    assert _vagas(resultado)[0].salario_texto == "$150K - $200K"
    dados = _dados("compensacao")
    comp = dados["jobs"][0]["compensation"]
    assert isinstance(comp, dict)
    comp["scrapeableCompensationSalarySummary"] = None  # cai no resumo do nível
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert _vagas(resultado)[0].salario_texto == "$150K – $200K • Offers Equity"
    comp["compensationTierSummary"] = "  "
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert _vagas(resultado)[0].salario_texto is None


async def test_campos_do_apendice_na_vaga_com_remuneracao() -> None:
    resultado, _ = await _coletar(_json("compensacao"))
    vaga = _vagas(resultado)[0]
    assert vaga.locais == (
        "🇧🇷 Sao Paulo / 🇲🇽 Mexico City / 🇪🇸Barcelona / 🌎Remote",
        "Remote - Brazil",
    )
    assert (vaga.modalidade_declarada, vaga.contrato_declarado) == ("Hybrid", "FullTime")
    assert vaga.etiquetas == ("CV",)  # department e team iguais não repetem


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _dados("normal")
    dados["jobs"][0] |= {
        "publishedAt": "2021-06-07T10:41:02",  # sem fuso
        "location": None,
        "secondaryLocations": "Remote",
        "descriptionHtml": None,
        "descriptionPlain": None,
        "department": 7,
        "team": None,
        "workplaceType": ["Remote"],
        "employmentType": None,
        "compensation": "muito",
        "applyUrl": None,
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.locais, vaga.etiquetas) == (None, (), ())
    assert (vaga.descricao, vaga.salario_texto, vaga.url_candidatura) == ("", None, None)
    assert (vaga.modalidade_declarada, vaga.contrato_declarado) == (None, None)


async def test_sem_descricao_html_usa_o_texto_puro() -> None:
    dados = _dados("normal")
    dados["jobs"][0]["descriptionHtml"] = ""
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    vaga = _vagas(resultado)[0]
    assert vaga.descricao_formato == "texto"
    assert vaga.descricao.strip().startswith("A little bit about us:")


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = _dados("normal")
    dados["jobs"][1]["jobUrl"] = "javascript:alert(1)"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 2


async def test_resposta_de_4_5_mb_passa_no_teto() -> None:
    dados = _dados("normal")
    modelo = dict(dados["jobs"][0])
    modelo["descriptionHtml"] = "<p>" + "x" * 2_100 + "</p>"
    modelo["descriptionPlain"] = "x" * 2_100
    dados["jobs"] = [
        modelo | {"id": f"id-{n}", "jobUrl": f"https://jobs.ashbyhq.com/belvo/id-{n}"}
        for n in range(900)
    ]
    corpo = json.dumps(dados)
    assert 4_400_000 < len(corpo.encode()) < TETO_PADRAO
    resultado, pedidos = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.estado, resultado.motivo, len(resultado.vagas)) == ("ok", None, 900)
    assert len(pedidos) == 1


def _quadro_de(n_vagas: int, tamanho_descricao: int) -> str:
    dados = _dados("normal")
    modelo = dict(dados["jobs"][0])
    modelo["descriptionHtml"] = "x" * tamanho_descricao
    modelo["descriptionPlain"] = "x"
    dados["jobs"] = [
        modelo | {"id": f"id-{n}", "jobUrl": f"https://jobs.ashbyhq.com/belvo/id-{n}"}
        for n in range(n_vagas)
    ]
    return json.dumps(dados)


async def test_quadro_de_15_mb_passa_no_teto_do_ashby() -> None:
    corpo = _quadro_de(2_000, 7_400)  # como o da OpenAI na busca real: acima dos 5 MB padrão
    assert TETO_PADRAO < len(corpo.encode()) < ashby.TETO_QUADRO_BYTES
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.estado, resultado.motivo, len(resultado.vagas)) == ("ok", None, 2_000)


async def test_o_teto_do_ashby_chega_ao_pedido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ashby, "TETO_QUADRO_BYTES", 1024 * 1024)
    corpo = _quadro_de(1, 1024 * 1024 + 1)
    with pytest.raises(RespostaGrande):
        await _coletar(httpx.Response(200, text=corpo))


async def test_404_empresa_nao_encontrada() -> None:
    resposta = httpx.Response(
        404, text=_texto("nao_encontrado"), headers={"Content-Type": "text/plain"}
    )
    resultado, pedidos = await _coletar(resposta, escopo="nao-existe")
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

    monkeypatch.setattr(ashby, "juntar_paginas", espia)
    etag = 'W/"job-board:e337b61ce0b2a9489bf901674658661660393d9a5547cf556d238d3eceab84fd"'

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _json("normal", ETag=etag)

    leitor = LeitorFixo({URL_BELVO: Validadores(etag, None)})
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
    assert str(pedido.url) == URL_BELVO
    assert dict(pedido.url.params) == {"includeCompensation": "true"}


async def test_escopo_estranho_nao_muda_o_caminho() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo="../x?y#z")
    assert [p.url.raw_path for p in pedidos] == [
        b"/posting-api/job-board/..%2Fx%3Fy%23z?includeCompensation=true"
    ]


@pytest.mark.parametrize(
    ("entrada", "nome"),
    [
        ("belvo", "belvo"),
        (" belvo ", "belvo"),
        ("Belvo", "Belvo"),  # a caixa é preservada (D45): o resolver não normaliza
        ("https://jobs.ashbyhq.com/belvo", "belvo"),
        ("https://jobs.ashbyhq.com/belvo/", "belvo"),
        ("https://jobs.ashbyhq.com/Belvo/5a34dbde-1947-4be7-b048-5acea47b0e86", "Belvo"),
        (
            "https://jobs.ashbyhq.com/belvo/5a34dbde-1947-4be7-b048-5acea47b0e86/application",
            "belvo",
        ),
        ("jobs.ashbyhq.com/belvo", "belvo"),
        ("https://jobs.ashbyhq.com/belvo/embed", "belvo"),
        ("https://api.ashbyhq.com/posting-api/job-board/belvo?includeCompensation=true", "belvo"),
    ],
)
async def test_resolver_aceita_url_do_quadro_e_devolve_o_nome(
    entrada: str, nome: str, http_proibido: HttpEducado
) -> None:
    resolvido = await ashby.COLETOR.resolver(entrada, http_proibido)
    assert resolvido == {"identificador": nome}


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "https://boards.greenhouse.io/belvo",
        "https://jobs.eu.ashbyhq.com/belvo",
        "https://jobs.ashbyhq.com/",
        "https://api.ashbyhq.com/posting-api/job-board/",
        "https://api.ashbyhq.com/outra/rota/belvo",
        "ftp://jobs.ashbyhq.com/belvo",
        "bel vo",
        "bélvo",
        "x" * 101,
    ],
)
async def test_resolver_recusa_o_que_nao_e_quadro(entrada: str, http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await ashby.COLETOR.resolver(entrada, http_proibido)
