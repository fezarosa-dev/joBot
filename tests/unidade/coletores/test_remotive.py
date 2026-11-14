import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, registro, remotive
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "remotive"
URL = "https://remotive.com/api/remote-jobs"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


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
        resultado = await remotive.COLETOR.coletar("", http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = remotive.COLETOR
    assert registro.descobrir()["remotive"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("remotive.com",)
    assert (prova.intervalo_min, prova.credito_obrigatorio) == (360, True)


def test_escopo_unico() -> None:
    empresas = [Empresa(nome="Vitta", fonte="greenhouse", identificador="vitta")]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(remotive.COLETOR.escopos(ctx)) == [""]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert (
        len(vagas) == 16
    )  # as chaves de texto da raiz ("00-warning", "0-legal-notice") não contam
    primeira = vagas[0]
    assert primeira.fonte == "remotive" and primeira.escopo == ""
    assert (
        primeira.url == "https://remotive.com/remote-jobs/marketing/remote-office-assistant-1680495"
    )
    assert primeira.titulo == "Remote Office Assistant"
    assert primeira.empresa == "Coalition Technologies"  # vem com espaço no fim
    assert primeira.id_externo == "1680495"
    assert primeira.locais == ("Worldwide",)
    assert primeira.publicada_em == datetime(2026, 11, 11, 20, 17, 48, tzinfo=UTC)
    assert primeira.descricao_formato == "html"
    assert primeira.descricao.startswith("<p")
    assert primeira.url_candidatura is None
    assert primeira.prazo is None
    assert primeira.etiquetas[:2] == ("Marketing", "CSS")  # categoria e depois as tags
    assert "wordpress" in primeira.etiquetas
    assert primeira.modalidade_declarada == "remote"
    assert primeira.contrato_declarado == "full_time"
    assert all(v.url.startswith(("https://", "http://")) for v in vagas)
    assert len({v.id_externo for v in vagas}) == 16
    assert len(pedidos) == 1


async def test_salario_em_texto() -> None:
    dados = json.loads(_texto("normal"))
    esperado = {j["id"]: j["salary"] for j in dados["jobs"]}
    resultado, _ = await _coletar(_json("normal"))
    vagas = _vagas(resultado)
    por_id = {v.id_externo: v for v in vagas}
    assert por_id["1680495"].salario_texto == "$35,3k- $52k"  # como veio, sem interpretar
    assert por_id["2091171"].salario_texto == "$14 - $20/hour"
    assert all(v.salario_estruturado is None for v in vagas)
    sem_texto = [i for i, s in esperado.items() if not s]
    assert len(sem_texto) == 5
    assert all(por_id[str(i)].salario_texto is None for i in sem_texto)  # "" = ausente


async def test_publication_date_sem_fuso_vale_utc() -> None:
    dados = json.loads(_texto("normal"))
    dados["jobs"][0]["publication_date"] = "2026-11-11T20:17:48"
    dados["jobs"][1]["publication_date"] = "2026-11-11T18:39:59-03:00"
    dados["jobs"][2]["publication_date"] = "2026-11-11T09:11:58Z"
    dados["jobs"][3]["publication_date"] = "ontem"
    dados["jobs"][4]["publication_date"] = None
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    vagas = _vagas(resultado)
    assert resultado.estado == "ok"
    assert vagas[0].publicada_em == datetime(2026, 11, 11, 20, 17, 48, tzinfo=UTC)
    assert vagas[0].publicada_em is not None and vagas[0].publicada_em.utcoffset() == timedelta(0)
    assert vagas[1].publicada_em == datetime(
        2026, 11, 11, 18, 39, 59, tzinfo=timezone(timedelta(hours=-3))
    )
    assert vagas[2].publicada_em == datetime(2026, 11, 11, 9, 11, 58, tzinfo=UTC)
    assert (vagas[3].publicada_em, vagas[4].publicada_em) == (None, None)


async def test_vazio() -> None:
    resultado, _ = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["1680495"]


@pytest.mark.parametrize(
    "corpo",
    ['{"vagas": []}', "[]", '{"jobs": {}}', "isto não é json", '{"jobs": [1, "x"]}'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = json.loads(_texto("normal"))
    dados["jobs"][0] |= {
        "salary": 35000,
        "candidate_required_location": None,
        "description": None,
        "tags": "excel",
        "category": None,
        "job_type": None,
        "id": None,
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.salario_texto, vaga.locais, vaga.descricao) == (None, (), "")
    assert (vaga.etiquetas, vaga.contrato_declarado, vaga.id_externo) == ((), None, None)


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = json.loads(_texto("normal"))
    dados["jobs"][1]["url"] = "javascript:alert(1)"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 15


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

    monkeypatch.setattr(remotive, "juntar_paginas", espia)
    data = "Fri, 13 Nov 2026 14:44:36 GMT"  # a captura só mostra Last-Modified, sem ETag

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-Modified-Since") == data:
            return httpx.Response(304, headers={"Last-Modified": data})
        return _json("normal", 200, **{"Last-Modified": data})

    leitor = LeitorFixo({URL: Validadores(None, data)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-Modified-Since") for p in pedidos] == [data]
    assert pedidos[0].headers.get("If-None-Match") is None
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
    assert str(pedido.url) == URL
    assert dict(pedido.url.params) == {}  # os filtros da API não mudam a resposta (apêndice 2.2)
