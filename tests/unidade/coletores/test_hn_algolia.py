import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import hn_algolia, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "hn_algolia"
RAIZ = "https://hn.algolia.com/api/v1"
URL_BUSCA = (
    f"{RAIZ}/search_by_date?query=%22Ask+HN%3A+Who+is+hiring%22"
    "&tags=story%2Cauthor_whoishiring&hitsPerPage=5"
)
URL_TOPICO = f"{RAIZ}/items/50338728"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _dados(caso: str) -> Any:
    return json.loads(_texto(caso))


def _json(caso: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=_texto(caso), headers={"Content-Type": "application/json"})


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    busca: httpx.Response | Responder,
    topico: httpx.Response | Responder | None = None,
    escopo: str = "",
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    """Roda o coletor de verdade sobre o `ClienteEducado`; responde pelo caminho do pedido."""
    pedidos: list[httpx.Request] = []

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        if pedido.url.path.endswith("/search_by_date"):
            alvo = busca
        else:
            assert topico is not None, f"pedido que o teste não esperava: {pedido.url}"
            alvo = topico
        return alvo if isinstance(alvo, httpx.Response) else alvo(pedido)

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(
        httpx.MockTransport(servidor), relogio, LeitorFixo(), "0.1.0", resolver=_sem_dns
    )
    try:
        http: HttpEducado = cli.escopo(condicional=False)
        resultado = await hn_algolia.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _hit(titulo: str, id_: str, em: int) -> dict[str, Any]:
    return {"objectID": id_, "title": titulo, "created_at_i": em}


def _busca(*hits: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"hits": list(hits)})


def _topico(*comentarios: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"id": 50338728, "children": list(comentarios)})


def _comentario(id_: int, texto: str | None) -> dict[str, Any]:
    return {
        "id": id_,
        "type": "comment",
        "text": texto,
        "created_at": "2026-11-02T16:01:43.000Z",
        "children": [],
    }


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = hn_algolia.COLETOR
    assert registro.descobrir()["hn_algolia"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("hn.algolia.com",)


def test_escopo_unico_sem_empresa() -> None:
    ctx = ContextoColeta(empresas=[], termos=["dev"], paises=["BR"])
    assert list(hn_algolia.COLETOR.escopos(ctx)) == [""]
    com_empresa = Empresa(nome="X", fonte="hn_algolia", identificador="x")
    ctx = ContextoColeta(empresas=[com_empresa], termos=[], paises=[])
    assert list(hn_algolia.COLETOR.escopos(ctx)) == [""]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("busca_topico"), _json("topico"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 2)
    vagas = _vagas(resultado)
    esperados = [str(c["id"]) for c in _dados("topico")["children"]]
    assert [v.id_externo for v in vagas] == esperados
    assert len(vagas) == 5
    primeira = vagas[0]
    assert primeira.fonte == "hn_algolia" and primeira.escopo == ""
    assert primeira.url == "https://news.ycombinator.com/item?id=50338732"
    assert primeira.empresa == "Simple Analytics"
    assert primeira.titulo == "DevOps Engineer"
    assert primeira.publicada_em == datetime(2026, 11, 2, 16, 1, 43, tzinfo=UTC)
    assert primeira.descricao_formato == "html"
    assert primeira.descricao == _dados("topico")["children"][0]["text"]
    assert primeira.url_candidatura is None
    assert all(v.url.startswith("https://news.ycombinator.com/item?id=") for v in vagas)
    assert [(p.method, str(p.url)) for p in pedidos] == [("GET", URL_BUSCA), ("GET", URL_TOPICO)]


async def test_primeira_linha_vira_empresa_e_cargo() -> None:
    resultado, _ = await _coletar(_json("busca_topico"), _json("topico"))
    lidas = [(v.empresa, v.titulo) for v in _vagas(resultado)]
    assert lidas[1] == ("Synteq", "Growth Lead & Systems Administrator")  # &amp; decodificado
    assert lidas[2] == (
        "University of Cambridge, University of Manchester",
        "PhD in AI / Earth Observation / Environmental Science",  # &#x2F; decodificado
    )
    assert lidas[3] == ("Open Education Applications / Neon", "Senior Frontend Engineer")


async def test_primeira_linha_fora_do_costume_guarda_o_texto_inteiro() -> None:
    """Sem cargo na segunda posição (ou sem `|`), o título é a linha toda e a descrição fica."""
    shepherd = _dados("topico")["children"][4]["text"]
    simples = "Trabalhamos com Python e SQLite em Curitiba<p>Venha conversar."
    resultado, _ = await _coletar(
        _busca(_hit("Ask HN: Who is hiring? (November 2026)", "50338728", 1)),
        _topico(_comentario(1, shepherd), _comentario(2, simples)),
    )
    assert resultado.estado == "ok"
    shep, sem_barra = _vagas(resultado)
    assert shep.empresa == "Shepherd (Series B)"
    assert shep.titulo == "Shepherd (Series B) | ONSITE | San Francisco, CA"
    assert shep.descricao == shepherd
    assert sem_barra.empresa == "Trabalhamos com Python e SQLite em Curitiba"
    assert sem_barra.titulo == sem_barra.empresa
    assert sem_barra.descricao == simples


async def test_so_filhos_de_primeiro_nivel() -> None:
    dados = _dados("topico")
    resposta = httpx.Response(200, json=dados)
    aninhados = {
        filho["id"] for c in dados["children"] for filho in c["children"]
    }  # respostas aos comentários
    assert aninhados  # a captura tem resposta aninhada: sem isso o teste não prova nada
    resultado, _ = await _coletar(_json("busca_topico"), resposta)
    ids = {int(v.id_externo or 0) for v in _vagas(resultado)}
    assert ids == {c["id"] for c in dados["children"]}
    assert ids.isdisjoint(aninhados)


async def test_nao_guarda_o_autor() -> None:
    dados = _dados("topico")
    for c in dados["children"]:
        c["author"] = "zz_autor_do_comentario"
    resultado, _ = await _coletar(_json("busca_topico"), httpx.Response(200, json=dados))
    vagas = _vagas(resultado)
    assert vagas
    assert all("zz_autor_do_comentario" not in repr(asdict(v)) for v in vagas)
    assert all("zz_autor_do_comentario" not in v.para_json() for v in vagas)


async def test_nenhum_pedido_a_news_ycombinator() -> None:
    dados = _dados("busca_topico")
    for h in dados["hits"]:
        h["url"] = f"https://news.ycombinator.com/item?id={h['objectID']}"  # só um link
    _, pedidos = await _coletar(httpx.Response(200, json=dados), _json("topico"))
    assert [p.url.host for p in pedidos] == ["hn.algolia.com", "hn.algolia.com"]


async def test_acha_o_topico_pelo_titulo_e_pega_o_mais_novo() -> None:
    busca = _busca(
        _hit("Ask HN: Who wants to be hired? (November 2026)", "111", 900),
        _hit("Ask HN: Freelancer? Seeking freelancer? (November 2026)", "222", 800),
        _hit("Re: Ask HN: Who is hiring? (November 2026)", "333", 700),
        _hit("Ask HN: Who is hiring (sem interrogação)", "444", 650),
        _hit("Ask HN: Who is hiring? (October 2026)", "555", 100),
        _hit("Ask HN: Who is hiring? (November 2026)", "50338728", 500),
        _hit("Ask HN: Who is hiring? (September 2026)", "666", 50),
    )
    resultado, pedidos = await _coletar(busca, _json("topico"))
    assert resultado.estado == "ok"
    assert [p.url.path for p in pedidos] == [
        "/api/v1/search_by_date",
        "/api/v1/items/50338728",
    ]


async def test_id_do_topico_fora_do_padrao_nao_vira_caminho() -> None:
    busca = _busca(
        _hit("Ask HN: Who is hiring? (November 2026)", "50338728/../../x?y#z", 900),
        _hit("Ask HN: Who is hiring? (October 2026)", "49922569", 100),
    )
    _, pedidos = await _coletar(busca, _json("topico"))
    assert [p.url.path for p in pedidos][1] == "/api/v1/items/49922569"


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert (resultado.pedidos, len(pedidos)) == (1, 1)  # sem tópico, sem segundo pedido


@pytest.mark.parametrize(
    "corpo",
    [
        '{"nada": 1}',
        '{"hits": {}}',
        "[]",
        "isto não é json",
        '{"hits": [1, "x"]}',
        json.dumps({"hits": [_hit("Ask HN: Who wants to be hired?", "111", 900)]}),
        json.dumps({"hits": [{"title": "Ask HN: Who is hiring?"}]}),
    ],
)
async def test_busca_sem_topico_legivel_falhou(corpo: str) -> None:
    resultado, pedidos = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("busca_topico"), _json("topico_formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["50338732"]


@pytest.mark.parametrize(
    "corpo",
    [
        '{"id": 50338728}',
        '{"children": {}}',
        "[]",
        "isto não é json",
        '{"children": [1, "x"]}',
        '{"children": [{"id": 1, "body": "Empresa | Cargo"}]}',
    ],
)
async def test_topico_sem_comentario_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(_json("busca_topico"), httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_topico_sem_comentarios_e_ok_vazio() -> None:
    resultado, _ = await _coletar(_json("busca_topico"), _topico())
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_comentario_apagado_nao_marca_formato_mudou() -> None:
    """Comentário apagado chega sem texto: não é quebra de formato, e a lista fica "ok"."""
    resultado, _ = await _coletar(
        _json("busca_topico"),
        _topico(_comentario(1, "Acme | Dev | REMOTE"), _comentario(2, None), _comentario(3, "")),
    )
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert [v.id_externo for v in _vagas(resultado)] == ["1"]


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    comentario = _comentario(7, "Acme | Dev | REMOTE")
    comentario["created_at"] = "ontem"
    sem_data = _comentario(8, "Beta | Dev")
    del sem_data["created_at"]
    sem_fuso = _comentario(9, "Gama | Dev")
    sem_fuso["created_at"] = "2026-11-02T16:01:43"
    resultado, _ = await _coletar(_json("busca_topico"), _topico(comentario, sem_data, sem_fuso))
    assert resultado.estado == "ok"
    assert [v.publicada_em for v in _vagas(resultado)] == [None, None, None]


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


async def test_erro_no_segundo_pedido_nao_deixa_lista_parcial() -> None:
    resultado, pedidos = await _coletar(_json("busca_topico"), httpx.Response(404))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.erro_de_rede"
    assert len(pedidos) == 2


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_json("busca_topico"), _json("topico"))
    busca, topico = pedidos
    assert (busca.method, str(busca.url)) == ("GET", URL_BUSCA)
    assert dict(busca.url.params) == {
        "query": '"Ask HN: Who is hiring"',
        "tags": "story,author_whoishiring",
        "hitsPerPage": "5",
    }
    assert (topico.method, str(topico.url)) == ("GET", URL_TOPICO)
    assert not topico.url.params


async def test_sem_validadores_nao_ha_pedido_condicional() -> None:
    """A captura não mostrou ETag nem Last-Modified: o coletor não pede 304."""
    resultado, pedidos = await _coletar(_json("busca_topico"), _json("topico"))
    assert resultado.estado == "ok"
    assert all("If-None-Match" not in p.headers for p in pedidos)
    assert all("If-Modified-Since" not in p.headers for p in pedidos)
