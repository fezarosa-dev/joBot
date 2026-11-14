import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import registro, remoteok
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "remoteok"
URL_API = "https://remoteok.com/api"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


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
        resultado = await remoteok.COLETOR.coletar("", http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """O `resolver` do RemoteOK não faz pedido: qualquer um é erro do teste."""

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


def _unica(resultado: ResultadoEscopo) -> VagaColetada:
    vagas = _vagas(resultado)
    assert len(vagas) == 1, resultado
    return vagas[0]


def _com_vaga(**campos: object) -> httpx.Response:
    """Lista de um elemento legal e uma vaga do `normal`, com `campos` trocados."""
    dados = json.loads(_texto("normal"))
    dados[1] |= campos
    return httpx.Response(200, json=dados[:2])


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = remoteok.COLETOR
    assert registro.descobrir()["remoteok"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("remoteok.com",)
    assert (prova.intervalo_min, prova.credito_obrigatorio) == (360, True)


def test_escopo_unico() -> None:
    ctx = ContextoColeta(empresas=[], termos=["dev"], paises=["BR"])
    assert list(remoteok.COLETOR.escopos(ctx)) == [""]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    # o primeiro elemento da lista (`legal`) não é vaga
    assert [v.id_externo for v in vagas] == ["1137793", "1137792", "1137791", "1137719"]
    primeira = vagas[0]
    assert primeira.fonte == "remoteok" and primeira.escopo == ""
    assert primeira.url == (
        "https://remoteOK.com/remote-jobs/remote-software-engineer-ai-tooling-supabase-1137793"
    )
    assert primeira.url_candidatura == primeira.url
    assert primeira.titulo == "Software Engineer AI Tooling"
    assert primeira.empresa == "Supabase"
    assert primeira.descricao_formato == "html"
    assert primeira.descricao.startswith("<h2><strong>About Supabase</strong></h2>")
    assert primeira.locais == ()
    assert primeira.publicada_em == datetime(2026, 11, 13, 0, 0, 15, tzinfo=UTC)
    assert primeira.etiquetas[:3] == ("dev", "design", "front end")
    assert primeira.salario_estruturado is None and primeira.salario_texto is None
    assert vagas[2].empresa == "AMBOSS" and vagas[2].locais == ("New York",)
    assert all(v.url.startswith(("https://", "http://")) for v in vagas)
    assert len(pedidos) == 1


async def test_modalidade_declarada_e_remote() -> None:
    resultado, _ = await _coletar(_json("normal"))
    vagas = _vagas(resultado)
    assert len(vagas) == 4
    assert [v.modalidade_declarada for v in vagas] == ["remote"] * 4


async def test_vazio() -> None:
    # só o elemento legal: nenhuma vaga, mas a lista veio
    resultado, _ = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    # shortcut: sem contagem de pulados no motivo (D45); trocar quando a sessão decidir
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["1137793"]


@pytest.mark.parametrize(
    "corpo",
    [
        "[]",
        '{"jobs": []}',
        "isto não é json",
        '[{"legal": "x"}, 1, "x"]',
        '[{"legal": "x"}, {"id": "1"}]',
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_utf8_forcado_sem_charset_no_content_type() -> None:
    dados = json.loads(_texto("normal"))[:2]
    dados[1] |= {"position": "Engenheiro de Software Sênior", "company": "Açaí & Cia"}
    corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    for tipo in ("application/json", "text/html"):
        resultado, _ = await _coletar(
            httpx.Response(200, content=corpo, headers={"Content-Type": tipo})
        )
        vaga = _unica(resultado)
        assert (vaga.titulo, vaga.empresa) == ("Engenheiro de Software Sênior", "Açaí & Cia")


async def test_id_e_epoch_chegam_como_texto() -> None:
    resultado, _ = await _coletar(_com_vaga(id="AbC-9", epoch="1794528015", date="logo", slug="x"))
    vaga = _unica(resultado)
    assert vaga.id_externo == "AbC-9"  # caixa preservada (D45)
    assert vaga.publicada_em == datetime(2026, 11, 13, 0, 0, 15, tzinfo=UTC)


async def test_data_iso_com_fuso_ganha_do_epoch() -> None:
    resultado, _ = await _coletar(_com_vaga(date="2026-11-13T09:00:00-03:00", epoch=1))
    publicada = _unica(resultado).publicada_em
    assert publicada == datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    assert publicada is not None and publicada.utcoffset() == timedelta(hours=-3)


@pytest.mark.parametrize(
    "campos",
    [
        {"date": "2026-11-13T09:00:00", "epoch": 1794528015},  # sem fuso: cai no epoch
        {"date": None, "epoch": 1794528015},
        {"date": "x", "epoch": "1794528015"},
    ],
)
async def test_data_invalida_cai_no_epoch(campos: dict[str, object]) -> None:
    resultado, _ = await _coletar(_com_vaga(**campos))
    assert _unica(resultado).publicada_em == datetime(2026, 11, 13, 0, 0, 15, tzinfo=UTC)


@pytest.mark.parametrize(
    "campos",
    [
        {"date": None, "epoch": None},
        {"date": "x", "epoch": "ontem"},
        {"date": "x", "epoch": 10**30},
        {"date": "x", "epoch": True},
    ],
)
async def test_sem_data_legivel_fica_sem_data(campos: dict[str, object]) -> None:
    resultado, _ = await _coletar(_com_vaga(**campos))
    assert resultado.estado == "ok"
    assert _unica(resultado).publicada_em is None


@pytest.mark.parametrize(
    ("minimo", "maximo", "esperado"),
    [
        (
            60000,
            90000,
            SalarioBruto(
                moeda="USD", minimo_unidades=60000.0, maximo_unidades=90000.0, periodo="ano"
            ),
        ),
        (
            0,
            90000,
            SalarioBruto(moeda="USD", minimo_unidades=None, maximo_unidades=90000.0, periodo="ano"),
        ),
        (
            60000,
            0,
            SalarioBruto(moeda="USD", minimo_unidades=60000.0, maximo_unidades=None, periodo="ano"),
        ),
        (
            "60000",
            "90000.5",
            SalarioBruto(
                moeda="USD", minimo_unidades=60000.0, maximo_unidades=90000.5, periodo="ano"
            ),
        ),
        (0, 0, None),  # 0 quer dizer ausente
        (None, None, None),
        ("abc", -5, None),
        (True, "nan", None),
    ],
)
async def test_salario_zero_e_ausente(
    minimo: object, maximo: object, esperado: SalarioBruto | None
) -> None:
    resultado, _ = await _coletar(_com_vaga(salary_min=minimo, salary_max=maximo))
    assert _unica(resultado).salario_estruturado == esperado


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    resultado, _ = await _coletar(
        _com_vaga(location=None, description=None, tags="dev", apply_url="javascript:alert(1)")
    )
    assert resultado.estado == "ok"
    vaga = _unica(resultado)
    assert (vaga.locais, vaga.descricao, vaga.etiquetas) == ((), "", ())
    assert vaga.url_candidatura is None


async def test_url_candidatura_vai_sem_mudanca() -> None:
    destino = "https://remoteOK.com/l/1137793?utm_source=x&ref=Abc#topo"
    resultado, _ = await _coletar(_com_vaga(apply_url=destino))
    assert _unica(resultado).url_candidatura == destino


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = json.loads(_texto("normal"))
    dados[2]["url"] = "javascript:alert(1)"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["1137793", "1137791", "1137719"]


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


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_json("vazio"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert str(pedido.url) == URL_API
    assert dict(pedido.url.params) == {}


async def test_sem_validadores_nao_pede_condicional() -> None:
    # a captura não trouxe ETag nem Last-Modified: o coletor não pede 304 (sem `test_304`)
    leitor = LeitorFixo({URL_API: Validadores('"x"', "Sat, 14 Nov 2026 06:00:00 GMT")})
    _, pedidos = await _coletar(_json("vazio"), leitor=leitor, condicional=True)
    assert len(pedidos) == 1
    assert "If-None-Match" not in pedidos[0].headers
    assert "If-Modified-Since" not in pedidos[0].headers


async def test_resolver_recusa_tudo(http_proibido: HttpEducado) -> None:
    # fonte de lista única: não há identificador nem endereço para colar
    for entrada in ("", "remoteok", "https://remoteok.com/remote-jobs/x-1"):
        with pytest.raises(ValueError):
            await remoteok.COLETOR.resolver(entrada, http_proibido)
