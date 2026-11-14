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
from jobot.nucleo.coletores.portais import cia_de_talentos
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "cia_de_talentos"
URL = "https://vagas.ciadetalentos.com.br/applicant/rest/applicant/authentication/filter"
HOJE = date(2026, 11, 13)  # o dia local em São Paulo do instante fixo abaixo
Responder = Callable[[httpx.Request], httpx.Response]


def _fuso(monkeypatch: pytest.MonkeyPatch, nome: str) -> None:
    monkeypatch.setenv("TZ", nome)
    time.tzset()


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Relógio do coletor parado em 2026-11-13 12:00 UTC, com o fuso de São Paulo (DP8)."""
    _fuso(monkeypatch, "America/Sao_Paulo")
    monkeypatch.setattr(cia_de_talentos, "_agora", lambda: datetime(2026, 11, 13, 12, tzinfo=UTC))
    yield
    monkeypatch.undo()
    time.tzset()


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _json(caso: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=_texto(caso), headers={"Content-Type": "application/json"})


def _lista(caso: str = "normal") -> list[dict[str, Any]]:
    dados: list[dict[str, Any]] = json.loads(_texto(caso))
    return dados


def _com(**campos: Any) -> list[dict[str, Any]]:
    """O primeiro programa do normal, com os campos trocados."""
    return [copy.deepcopy(_lista()[0]) | campos]


def _resposta(dados: object) -> httpx.Response:
    return httpx.Response(200, text=json.dumps(dados, allow_nan=True))


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
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
        httpx.MockTransport(servidor), relogio, LeitorFixo(), "0.1.0", resolver=_sem_dns
    )
    try:
        http: HttpEducado = cli.escopo()
        resultado = await cia_de_talentos.COLETOR.coletar("", http)
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
    prova: Coletor = cia_de_talentos.COLETOR
    assert registro.descobrir()["cia_de_talentos"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "B"
    assert prova.intervalo_min == limites.intervalo_min is None
    assert prova.espera_s == limites.espera_s
    assert prova.credito_obrigatorio is False
    assert prova.hosts == ("vagas.ciadetalentos.com.br",)


def test_escopo_unico() -> None:
    empresas = [Empresa(nome="Flex", fonte="cia_de_talentos", identificador="flex")]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(cia_de_talentos.COLETOR.escopos(ctx)) == [""]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    assert len(pedidos) == 1
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert primeira.fonte == "cia_de_talentos" and primeira.escopo == ""
    assert primeira.id_externo == "3206"
    assert primeira.titulo == "Programa de Estágio EssilorLuxottica 2027/2028"
    assert primeira.empresa == "EssilorLuxottica"
    assert primeira.url == "https://marketing.ciadetalentos.com/4xS2kfj"
    assert primeira.url_candidatura == (
        "https://www.atsglobe.com/candidate-ui/#/login/candidacy-registration/3206"
    )
    assert primeira.descricao_formato == "html"
    assert primeira.descricao == ""  # sem texto e com área "Diversas"
    assert primeira.locais == ()  # "Localidade: Diversas" não é lugar
    assert primeira.contrato_declarado == "estágio"
    assert primeira.etiquetas == ("Estágio Superior",)
    assert primeira.prazo == date(2026, 11, 15)
    assert primeira.publicada_em is None and primeira.salario_estruturado is None
    assert primeira.modalidade_declarada is None
    segunda = vagas[1]
    assert segunda.descricao.startswith("<!DOCTYPE html>")
    assert "Minera&ccedil;&atilde;o" in segunda.descricao  # HTML de verdade: sem unescape
    assert [v.id_externo for v in vagas] == ["3206", "3207", "3170", "182", "3092"]
    assert [v.prazo for v in vagas] == [
        date(2026, 11, 15),
        date(2026, 11, 16),
        date(2026, 11, 16),
        date(2026, 11, 22),
        date(2027, 2, 28),
    ]
    assert vagas[3].url == vagas[3].url_candidatura == "https://marketing.ciadetalentos.com/4805pzw"
    assert vagas[3].contrato_declarado == "estágio" and vagas[3].etiquetas == ()  # hiringType nulo
    assert vagas[4].contrato_declarado is None  # id 13 ("Ensino Médio") não é estágio nem trainee
    assert vagas[4].etiquetas == ("Ensino Médio",)
    assert all(v.url.startswith("https://") for v in vagas)


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    # shortcut na fonte: a contagem não vai no motivo (D45)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["3206"]


@pytest.mark.parametrize(
    "corpo",
    ['{"itens": []}', "{}", "null", '"texto"', "isto não é json", '[1, "x"]', '[{"x": 1}]'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


@pytest.mark.parametrize(
    "campos",
    [
        {"opportunityName": "  "},
        {"opportunityName": None},
        {"companyName": ""},
        {"opportunityHotsiteUrl": None, "opportunityInscriptionUrl": None},
        {"opportunityHotsiteUrl": "javascript:alert(1)", "opportunityInscriptionUrl": "ftp://x"},
    ],
)
async def test_programa_sem_campo_obrigatorio_e_pulado(campos: dict[str, Any]) -> None:
    dados = _com() + _com(**campos)
    resultado, _ = await _coletar(_resposta(dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 1


async def test_endereco_cai_para_a_inscricao_e_candidatura_ruim_some() -> None:
    sem_hotsite = _com(opportunityHotsiteUrl=None)
    resultado, _ = await _coletar(_resposta(sem_hotsite))
    vaga = _uma(resultado)
    assert vaga.url == vaga.url_candidatura == sem_hotsite[0]["opportunityInscriptionUrl"]
    candidatura_ruim = _com(opportunityInscriptionUrl="javascript:alert(1)")
    resultado, _ = await _coletar(_resposta(candidatura_ruim))
    assert resultado.estado == "ok"  # a vaga fica: só a candidatura inválida é descartada
    vaga = _uma(resultado)
    assert vaga.url == "https://marketing.ciadetalentos.com/4xS2kfj"
    assert vaga.url_candidatura is None


async def test_campo_opcional_estranho_nao_derruba_o_programa() -> None:
    dados = _com(
        opportunityDescription=5,
        opportunityLocations=7,
        opportunityAreas={"a": 1},
        hiringType=["x"],
        hiringTypeId="abc",
        countFinishDays="muitos",
        opportunityId=None,
        opportunityInscriptionUrl=12,
    )
    resultado, _ = await _coletar(_resposta(dados))
    assert resultado.estado == "ok"
    vaga = _uma(resultado)
    assert (vaga.descricao, vaga.locais, vaga.etiquetas) == ("", (), ())
    assert (vaga.contrato_declarado, vaga.prazo) == (None, None)
    assert (vaga.id_externo, vaga.url_candidatura) == (None, None)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(3206, "3206"), ("77", "77"), ("", None), (True, None), (1.5, None), (None, None)],
)
async def test_id_externo(valor: object, esperado: str | None) -> None:
    resultado, _ = await _coletar(_resposta(_com(opportunityId=valor)))
    assert _uma(resultado).id_externo == esperado


@pytest.mark.parametrize(
    ("tipo", "contrato"),
    [
        (1, "trainee"),
        (2, "estágio"),
        (3, "estágio"),
        ("1", "trainee"),
        ("3", "estágio"),
        (13, None),
        (4, None),
        (True, None),
        ("x", None),
        (None, None),
    ],
)
async def test_tipo_de_contratacao_pelo_id(tipo: object, contrato: str | None) -> None:
    resultado, _ = await _coletar(_resposta(_com(hiringTypeId=tipo)))
    assert _uma(resultado).contrato_declarado == contrato


@pytest.mark.parametrize(
    ("dias", "prazo"),
    [
        (0, HOJE),
        (2, date(2026, 11, 15)),
        ("5", date(2026, 11, 18)),
        (-1, date(2026, 11, 12)),  # o site mostra "Encerrada": o dia passado é o certo
        (None, None),
        ("cinco", None),
        (True, None),
        (2.0, date(2026, 11, 15)),  # a fonte às vezes manda o inteiro como float
        (2.5, None),
        (float("inf"), None),
        (1e300, None),  # inteiro como float, mas estoura a data
        (10**9, None),  # estoura a data
        (10**400, None),  # estoura o int do C
        ("9" * 400, None),
    ],
)
async def test_prazo_e_hoje_mais_count_finish_days(dias: object, prazo: date | None) -> None:
    resultado, _ = await _coletar(_resposta(_com(countFinishDays=dias)))
    assert _uma(resultado).prazo == prazo


async def test_prazo_ignora_days_remaining_for_inscription() -> None:
    dados = _com(daysRemainingForInscription="Encerra hoje", daysForInscription=0)
    resultado, _ = await _coletar(_resposta(dados))
    assert _uma(resultado).prazo == date(2026, 11, 15)  # countFinishDays é 2


async def test_prazo_usa_o_dia_local_nao_o_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    # 02:00Z de 14/11 ainda é 13/11 em São Paulo: hoje = 13, prazo = 13 + 2
    monkeypatch.setattr(cia_de_talentos, "_agora", lambda: datetime(2026, 11, 14, 2, tzinfo=UTC))
    resultado, _ = await _coletar(_resposta(_com()))
    assert _uma(resultado).prazo == date(2026, 11, 15)
    _fuso(monkeypatch, "UTC")  # controle: em UTC o mesmo instante já é dia 14
    resultado, _ = await _coletar(_resposta(_com()))
    assert _uma(resultado).prazo == date(2026, 11, 16)


@pytest.mark.parametrize(
    ("local", "esperado"),
    [
        ("Localidade: Diversas", ()),
        ("Localidade: São Paulo - SP", ("São Paulo - SP",)),
        ("localidade:Curitiba", ("Curitiba",)),
        ("Belo Horizonte", ("Belo Horizonte",)),
        (
            ["São Paulo - SP", "Localidade: Rio de Janeiro", "Diversas", 3, " "],
            ("São Paulo - SP", "Rio de Janeiro"),
        ),
        ("", ()),
        (None, ()),
    ],
)
async def test_locais(local: object, esperado: tuple[str, ...]) -> None:
    resultado, _ = await _coletar(_resposta(_com(opportunityLocations=local)))
    assert _uma(resultado).locais == esperado


async def test_area_entra_na_descricao_escapada() -> None:
    dados = _com(opportunityAreas="Área: Tecnologia & Dados", opportunityDescription="<p>Oi</p>")
    resultado, _ = await _coletar(_resposta(dados))
    assert _uma(resultado).descricao == "<p>Oi</p>\n<p>Área: Tecnologia &amp; Dados</p>"
    resultado, _ = await _coletar(_resposta(_com(opportunityAreas="Tecnologia")))
    assert _uma(resultado).descricao == "<p>Área: Tecnologia</p>"


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
    assert pedido.method == "POST"
    assert str(pedido.url) == URL
    assert json.loads(pedido.content) == {"locale": "pt"}
    assert pedido.headers["Content-Type"].startswith("application/json")
    assert pedido.headers["Accept"] == "application/json"
    assert pedido.headers["User-Agent"].startswith("joBot/")
    for nome in ("Cookie", "Origin", "Referer", "Authorization", "If-None-Match"):
        assert nome not in pedido.headers
    assert "If-Modified-Since" not in pedido.headers  # sem validador: a resposta é no-store


async def test_cookie_do_balanceador_nao_volta() -> None:
    """A resposta grava cookie do balanceador; o joBot não o devolve (nenhum pedido leva Cookie)."""
    pedidos: list[httpx.Request] = []

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        resposta = _json("vazio")
        resposta.headers["Set-Cookie"] = "AWSALBTG=abc; Path=/"
        return resposta

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(
        httpx.MockTransport(servidor), relogio, LeitorFixo(), "0.1.0", resolver=_sem_dns
    )
    try:
        for _ in range(2):  # o mesmo cliente: o segundo pedido é o que levaria o cookie
            await cia_de_talentos.COLETOR.coletar("", cli.escopo())
    finally:
        await cli.fechar()
    assert len(pedidos) == 2
    assert all("Cookie" not in p.headers for p in pedidos)


async def test_resolver_recusa_tudo_e_nao_faz_pedido(http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await cia_de_talentos.COLETOR.resolver(
            "https://vagas.ciadetalentos.com.br/x", http_proibido
        )


async def test_detalhar_nao_tem_o_que_detalhar(http_proibido: HttpEducado) -> None:
    item = VagaColetada(
        fonte="cia_de_talentos",
        escopo="",
        url="https://marketing.ciadetalentos.com/x",
        titulo="x",
        empresa="y",
        descricao_formato="html",
    )
    assert await cia_de_talentos.COLETOR.detalhar(item, http_proibido) is None
