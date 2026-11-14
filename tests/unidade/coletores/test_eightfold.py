import copy
import json
from collections.abc import AsyncIterator, Callable, Sequence, Set
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import eightfold, executor, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, LimiteEscopo, ResultadoEscopo
from jobot.nucleo.coletores.executor import Historico, SaidaEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "eightfold"
ML = "mercadolibre.eightfold.ai"
MICROSOFT = "apply.careers.microsoft.com"
BAYER = "bayer.eightfold.ai"
MERCADO_LIVRE = Empresa(
    nome="Mercado Livre",
    fonte="eightfold",
    identificador=ML,
    parametros={"dominio": "mercadolibre.com", "geracao": "pcsx"},
)
MS = Empresa(
    nome="Microsoft",
    fonte="eightfold",
    identificador=MICROSOFT,
    parametros={"dominio": "microsoft.com", "geracao": "pcsx"},
)
BAYER_V2 = Empresa(
    nome="Bayer",
    fonte="eightfold",
    identificador=BAYER,
    parametros={"dominio": "bayer.com", "geracao": "v2"},
)
TODAS = (MERCADO_LIVRE, MS, BAYER_V2)
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / caso).read_text(encoding="utf-8")


def _json(caso: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status, text=_texto(f"{caso}.json"), headers={"Content-Type": "application/json"}
    )


def _dados(caso: str) -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_texto(f"{caso}.json"))
    return dados


def _pagina(ids: Sequence[int], count: object) -> httpx.Response:
    """Página PCSX com as vagas da fixture, uma por id (ids distintos por página)."""
    dados = _dados("normal_microsoft")
    modelo = dados["data"]["positions"][0]
    dados["data"]["positions"] = [modelo | {"id": i} for i in ids]
    dados["data"]["count"] = count
    return httpx.Response(200, json=dados)


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


def _cliente(servidor: Responder, relogio: Relogio | None = None) -> ClienteEducado:
    return ClienteEducado(
        httpx.MockTransport(servidor),
        relogio or RelogioFalso(),
        LeitorFixo(),
        "0.1.0",
        resolver=_sem_dns,
    )


def _fila(
    respostas: Sequence[httpx.Response | Responder], pedidos: list[httpx.Request]
) -> Responder:
    fila = list(respostas)

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return r if isinstance(r, httpx.Response) else r(pedido)

    return servidor


def _coletor(
    empresas: Sequence[Empresa] = TODAS, paises: Sequence[str] = ("BR",)
) -> eightfold.Eightfold:
    coletor = eightfold.Eightfold()  # instância nova: o cadastro não vaza entre testes
    coletor.escopos(ContextoColeta(empresas=empresas, termos=[], paises=paises))
    return coletor


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = ML,
    empresas: Sequence[Empresa] = TODAS,
    paises: Sequence[str] = ("BR",),
    coletor: eightfold.Eightfold | None = None,
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    """Roda o coletor de verdade sobre o `ClienteEducado` com transporte falso."""
    pedidos: list[httpx.Request] = []
    cli = _cliente(_fila(respostas, pedidos))
    coletor = coletor or _coletor(empresas, paises)
    try:
        resultado = await coletor.coletar(escopo, cli.escopo())
    finally:
        await cli.fechar()
    return resultado, pedidos


async def _detalhar(
    item: VagaColetada, *respostas: httpx.Response | Responder
) -> tuple[VagaColetada | None, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []
    cli = _cliente(_fila(respostas, pedidos))
    try:
        detalhe = await _coletor().detalhar(item, cli.escopo())
    finally:
        await cli.fechar()
    return detalhe, pedidos


async def _resolver(
    entrada: str, *respostas: httpx.Response | Responder
) -> tuple[dict[str, str], list[httpx.Request]]:
    pedidos: list[httpx.Request] = []
    cli = _cliente(_fila(respostas, pedidos))
    try:
        resolvido = dict(await eightfold.COLETOR.resolver(entrada, cli.escopo()))
    finally:
        await cli.fechar()
    return resolvido, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """Para entradas recusadas antes de qualquer pedido: um pedido é erro do teste."""

    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"resolver não devia pedir: {pedido.url}")

    cli = _cliente(recusa)
    try:
        yield cli.escopo()
    finally:
        await cli.fechar()


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _params(pedido: httpx.Request) -> dict[str, str]:
    return dict(pedido.url.params)


# --- registro e escopos ----------------------------------------------------------------------


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = eightfold.COLETOR
    assert registro.descobrir()["eightfold"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "B"
    assert (prova.intervalo_min, prova.max_pedidos, prova.espera_s) == (None, None, 1.0)
    # escopo Microsoft: 1440 min, 5 s e o primeiro 429 encerra só ele (critério 13)
    assert prova.por_escopo[MICROSOFT] == LimiteEscopo(1440, 5.0, True)
    assert set(prova.por_escopo) == {MICROSOFT}


def test_escopos_um_por_empresa_e_o_da_microsoft_e_o_host() -> None:
    repetida = Empresa(nome="ML de novo", fonte="eightfold", identificador=ML)
    ctx = ContextoColeta(empresas=[*TODAS, repetida], termos=["dev"], paises=["BR"])
    escopos = list(eightfold.Eightfold().escopos(ctx))
    assert escopos == [ML, MICROSOFT, BAYER]
    assert MICROSOFT in eightfold.COLETOR.por_escopo  # o executor acha o limite pelo escopo


def test_cadastro_acompanha_o_ultimo_escopos() -> None:
    coletor = eightfold.Eightfold()
    coletor.escopos(ContextoColeta(empresas=[MERCADO_LIVRE], termos=[], paises=[]))
    renomeada = Empresa(
        nome="Meli", fonte="eightfold", identificador=ML, parametros={"dominio": "meli.com"}
    )
    coletor.escopos(ContextoColeta(empresas=[renomeada], termos=[], paises=[]))
    cadastro = coletor._cadastro(ML)
    assert cadastro is not None and (cadastro.nome, cadastro.dominio) == ("Meli", "meli.com")


# --- lista PCSX e v2 --------------------------------------------------------------------------


async def test_normal_pcsx() -> None:
    resultado, pedidos = await _coletar(_json("normal_pcsx"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert (primeira.fonte, primeira.escopo, primeira.empresa) == ("eightfold", ML, "Mercado Livre")
    assert primeira.url == "https://mercadolibre.eightfold.ai/careers/job/43756169"
    assert primeira.titulo.startswith("Executivo Comercial Grandes Contas - Mercado Pago")
    assert primeira.id_externo == "43756169"
    assert primeira.locais == ("Sudeste,Brazil",)
    assert primeira.modalidade_declarada == "onsite"
    assert primeira.publicada_em == datetime(2026, 11, 13, 22, 14, 58, tzinfo=UTC)
    assert primeira.etiquetas == ("Fintech",)
    assert (primeira.descricao, primeira.descricao_formato) == ("", "html")  # vem do detalhar
    assert [v.etiquetas for v in vagas[1:]] == [("Shipping",)] * 4
    assert len(pedidos) == 1


async def test_normal_microsoft() -> None:
    resultado, pedidos = await _coletar(
        _json("normal_microsoft"),
        lambda p: _pagina([], 24),
        escopo=MICROSOFT,
    )
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    vagas = _vagas(resultado)
    assert len(vagas) == 10
    primeira = vagas[0]
    assert primeira.url == "https://apply.careers.microsoft.com/careers/job/1970393557054020"
    assert primeira.titulo == "Area Support Lead - Reactive Support Excellence"
    assert primeira.empresa == "Microsoft"
    assert primeira.publicada_em == datetime(2026, 11, 6, 19, 1, 19, tzinfo=UTC)
    assert vagas[1].locais == (
        "Brazil, Multiple Locations, Multiple Locations",
        "Brazil, São Paulo, São Paulo",
    )
    assert [_params(p)["start"] for p in pedidos] == ["0", "10"]


async def test_normal_v2() -> None:
    resultado, pedidos = await _coletar(_json("normal_v2"), escopo=BAYER)
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert (primeira.escopo, primeira.empresa) == (BAYER, "Bayer")
    assert primeira.url == "https://talent.bayer.com/careers/job/562949978840401"
    assert primeira.titulo == "Líder de Contas - Oncologia / São Paulo / SP"
    assert primeira.id_externo == "562949978840401"
    assert primeira.locais == ("São Paulo,São Paulo,Brazil",)
    assert primeira.modalidade_declarada == "onsite"
    assert primeira.publicada_em == datetime(2026, 10, 29, tzinfo=UTC)
    assert primeira.etiquetas == ("Marketing", "Pharmaceuticals")
    # a lista v2 já traz o texto achatado: entra como texto, sem esperar o detalhar
    assert primeira.descricao_formato == "texto"
    assert primeira.descricao.startswith("| --- | | | Nossa missão")
    assert len(pedidos) == 1


async def test_v2_sem_url_canonica_monta_pelo_host() -> None:
    dados = _dados("normal_v2")
    dados["positions"] = dados["positions"][:2]
    dados["positions"][0]["canonicalPositionUrl"] = "javascript:alert(1)"
    del dados["positions"][1]["canonicalPositionUrl"]
    dados["count"] = 2
    resultado, _ = await _coletar(httpx.Response(200, json=dados), escopo=BAYER)
    assert resultado.estado == "ok"
    assert [v.url for v in _vagas(resultado)] == [
        "https://bayer.eightfold.ai/careers/job/562949978840401",
        "https://bayer.eightfold.ai/careers/job/562949978833215",
    ]


async def test_empresa_sem_cadastro_usa_o_host_e_o_dominio_conhecido() -> None:
    # "testar" pode coletar sem `escopos`; a Microsoft tem domínio conhecido (apêndice 3.3)
    resultado, pedidos = await _coletar(
        _json("normal_microsoft"), lambda p: _pagina([], 24), escopo=MICROSOFT, empresas=()
    )
    assert resultado.estado == "ok"
    assert {v.empresa for v in _vagas(resultado)} == {MICROSOFT}
    assert _params(pedidos[0])["domain"] == "microsoft.com"


async def test_sem_dominio_falhou_sem_pedido() -> None:
    sem = Empresa(nome="Sem", fonte="eightfold", identificador="sem.eightfold.ai")
    resultado, pedidos = await _coletar(_json("vazio"), escopo="sem.eightfold.ai", empresas=[sem])
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.empresa_nao_encontrada"
    assert pedidos == []


@pytest.mark.parametrize("escopo", ["evil.com/x?y", "a@b.eightfold.ai", "x.eightfold.ai:80", ""])
async def test_escopo_que_nao_e_host_nao_vira_pedido(escopo: str) -> None:
    resultado, pedidos = await _coletar(_json("vazio"), escopo=escopo, empresas=())
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.empresa_nao_encontrada")
    assert pedidos == []


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == [
        "43756169",
        "45520477",
        "45520255",
        "45520260",
    ]


@pytest.mark.parametrize(
    "corpo",
    [
        '{"ok": true}',
        '{"data": {"positions": "x"}}',
        '{"data": null}',
        "isto não é json",
        '{"data": {"positions": [1, "x"], "count": 2}}',
        '{"data": {"positions": [{"id": 1}], "count": 1}}',
        "null",
        "[]",
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


@pytest.mark.parametrize("corpo", ['{"positions": "x"}', '{"data": {"positions": []}}', "[]"])
async def test_formato_mudou_v2_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo), escopo=BAYER)
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.formato_mudou")


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _dados("normal_pcsx")
    dados["data"]["positions"] = dados["data"]["positions"][:1]
    dados["data"]["positions"][0] |= {
        "postedTs": "ontem",
        "locations": None,
        "department": 5,
        "workLocationOption": 7,
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.locais, vaga.etiquetas, vaga.modalidade_declarada) == (
        None,
        (),
        (),
        None,
    )


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (10**30, None),
        (-(10**30), None),
        (10**400, None),
        (True, None),
        (float("nan"), None),
        (1.5e30, None),
        ("1794608098", datetime(2026, 11, 13, 22, 14, 58, tzinfo=UTC)),
        (1794608098.0, datetime(2026, 11, 13, 22, 14, 58, tzinfo=UTC)),
    ],
)
async def test_posted_ts_em_segundos_e_fora_de_faixa(valor: object, esperado: object) -> None:
    dados = _dados("normal_pcsx")
    dados["data"]["positions"] = dados["data"]["positions"][:1]
    dados["data"]["positions"][0]["postedTs"] = valor
    resultado, _ = await _coletar(httpx.Response(200, text=json.dumps(dados)))  # NaN passa
    assert resultado.estado == "ok" and _vagas(resultado)[0].publicada_em == esperado


@pytest.mark.parametrize("ident", [True, None, "a/b", "", 1.5, "x" * 101])
async def test_id_estranho_pula_a_vaga(ident: object) -> None:
    dados = _dados("normal_pcsx")
    dados["data"]["positions"][1]["id"] = ident
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 4


async def test_id_em_texto_vale() -> None:
    dados = _dados("normal_pcsx")
    dados["data"]["positions"] = dados["data"]["positions"][:1]
    dados["data"]["positions"][0]["id"] = "43756169"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert [v.id_externo for v in _vagas(resultado)] == ["43756169"]


# --- paginação --------------------------------------------------------------------------------


async def test_paginacao_ate_o_total() -> None:
    resultado, pedidos = await _coletar(
        _pagina(range(1, 11), 24), _pagina(range(11, 21), 24), _pagina(range(21, 25), 24)
    )
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 3)
    assert len(resultado.vagas) == 24
    assert [_params(p)["start"] for p in pedidos] == ["0", "10", "20"]


async def test_pagina_cheia_com_total_atingido_para() -> None:
    resultado, pedidos = await _coletar(_pagina(range(1, 11), 10), _pagina(range(11, 21), 30))
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 10, 1)


async def test_pagina_vazia_para_mesmo_com_total_absurdo() -> None:
    resultado, pedidos = await _coletar(_pagina(range(1, 11), 10**9), _pagina([], 10**9))
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 10, 2)


@pytest.mark.parametrize("count", [None, "24", True, -1])
async def test_total_estranho_para_pela_pagina_curta(count: object) -> None:
    resultado, pedidos = await _coletar(_pagina(range(1, 11), count), _pagina(range(11, 15), count))
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 14, 2)


async def test_teto_de_paginas_fica_parcial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eightfold, "MAX_PAGINAS", 3)
    contador = iter(range(1, 10**6, 10))

    def sempre_cheia(pedido: httpx.Request) -> httpx.Response:
        inicio = next(contador)
        return _pagina(range(inicio, inicio + 10), 10**6)

    resultado, pedidos = await _coletar(sempre_cheia)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert (len(resultado.vagas), len(pedidos)) == (30, 3)


async def test_pagina_seguinte_ilegivel_guarda_a_lida() -> None:
    resultado, pedidos = await _coletar(
        _pagina(range(1, 11), 24), httpx.Response(200, text="<html>erro</html>")
    )
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert (len(resultado.vagas), len(pedidos)) == (10, 2)


async def test_erro_de_rede_na_pagina_seguinte_guarda_a_lida() -> None:
    resultado, pedidos = await _coletar(_pagina(range(1, 11), 24), httpx.Response(404))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert (len(resultado.vagas), len(pedidos)) == (10, 2)


# --- países das buscas (DR-53) ----------------------------------------------------------------


async def test_um_pedido_por_pais_das_buscas_sem_repetir_vaga() -> None:
    resultado, pedidos = await _coletar(_json("normal_pcsx"), paises=("BR", " pt ", "XX", "BR"))
    assert [_params(p)["location"] for p in pedidos] == ["Brazil", "Portugal"]
    assert resultado.estado == "ok"
    assert len(resultado.vagas) == 5  # a mesma vaga nos dois países entra uma vez


async def test_sem_paises_nas_buscas_busca_no_brasil() -> None:
    # o "testar" do painel chega sem países; sem filtro a API devolveria o mundo todo
    _, pedidos = await _coletar(_json("vazio"), paises=())
    assert [_params(p)["location"] for p in pedidos] == ["Brazil"]


@pytest.mark.parametrize("paises", [("XX",), ("JP", " xx ")])
async def test_so_paises_fora_do_mapa_nao_pede_nada(paises: tuple[str, ...]) -> None:
    ctx = ContextoColeta(empresas=TODAS, termos=["dev"], paises=paises)
    assert list(eightfold.Eightfold().escopos(ctx)) == []  # DR-53: não cai para o Brasil
    resultado, pedidos = await _coletar(_json("vazio"), paises=paises)
    assert (resultado.vagas, resultado.estado, len(pedidos)) == ((), "ok", 0)


# --- erros ------------------------------------------------------------------------------------


async def test_404_empresa_nao_encontrada() -> None:
    resultado, pedidos = await _coletar(_json("nao_encontrado", 404))
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


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(_json("pcsx_desligado", 403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


# --- endereço e parâmetros --------------------------------------------------------------------


async def test_endereco_e_parametros_pcsx() -> None:
    _, pedidos = await _coletar(_json("vazio"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert (pedido.url.scheme, pedido.url.host, pedido.url.path) == (
        "https",
        ML,
        "/api/pcsx/search",
    )
    assert _params(pedido) == {
        "domain": "mercadolibre.com",
        "query": "",
        "location": "Brazil",
        "start": "0",
        "sort_by": "timestamp",
    }


async def test_endereco_e_parametros_v2() -> None:
    dados = _dados("normal_v2") | {"positions": [], "count": 0}
    _, pedidos = await _coletar(httpx.Response(200, json=dados), escopo=BAYER)
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert (pedido.url.host, pedido.url.path) == (BAYER, "/api/apply/v2/jobs")
    assert _params(pedido) == {
        "domain": "bayer.com",
        "start": "0",
        "num": "10",
        "location": "Brazil",
        "sort_by": "timestamp",
    }


async def test_microsoft_nunca_manda_work_site() -> None:
    _, pedidos = await _coletar(
        _json("normal_microsoft"), lambda p: _pagina([], 24), escopo=MICROSOFT
    )
    assert len(pedidos) == 2
    for pedido in pedidos:
        assert pedido.url.host == MICROSOFT
        assert "work_site" not in _params(pedido)
        assert "work_site" not in str(pedido.url)


# --- detalhar ---------------------------------------------------------------------------------


async def _primeira(caso: str, escopo: str) -> VagaColetada:
    resultado, _ = await _coletar(_json(caso), escopo=escopo)
    return _vagas(resultado)[0]


async def test_detalhar_pcsx() -> None:
    item = await _primeira("normal_pcsx", ML)
    detalhe, pedidos = await _detalhar(item, _json("detalhe_pcsx"))
    assert detalhe is not None
    assert detalhe.descricao.startswith("<p>No Mercado Livre estamos democratizando")
    assert detalhe.descricao_formato == "html"
    assert detalhe.url == item.url and detalhe.titulo == item.titulo  # a URL é a chave
    assert len(pedidos) == 1
    assert (pedidos[0].url.host, pedidos[0].url.path) == (ML, "/api/pcsx/position_details")
    assert _params(pedidos[0]) == {
        "position_id": "43756169",
        "domain": "mercadolibre.com",
        "hl": "pt-BR",
    }


async def test_detalhar_v2() -> None:
    item = await _primeira("normal_v2", BAYER)
    detalhe, pedidos = await _detalhar(item, _json("detalhe_v2"))
    assert detalhe is not None
    assert detalhe.descricao.startswith('<table style="width: 970.0px;"')
    assert detalhe.descricao_formato == "html"
    assert (pedidos[0].url.host, pedidos[0].url.path) == (
        BAYER,
        "/api/apply/v2/jobs/562949978840401",
    )
    assert _params(pedidos[0]) == {"domain": "bayer.com"}


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(404),
        httpx.Response(200, text='{"data": {}}'),
        httpx.Response(200, text='{"data": {"jobDescription": "  "}}'),
        httpx.Response(200, text="não é json"),
        httpx.Response(200, text="[]"),
    ],
)
async def test_detalhar_sem_descricao_devolve_none(resposta: httpx.Response) -> None:
    item = await _primeira("normal_pcsx", ML)
    detalhe, pedidos = await _detalhar(item, resposta)
    assert detalhe is None and len(pedidos) == 1


async def test_detalhar_sem_id_ou_sem_dominio_nao_pede() -> None:
    item = await _primeira("normal_pcsx", ML)
    for estranho in (
        item.__class__(**(vars(item) | {"id_externo": None})),
        item.__class__(**(vars(item) | {"id_externo": "../x"})),
        item.__class__(**(vars(item) | {"escopo": "sem.eightfold.ai"})),
        item.__class__(**(vars(item) | {"escopo": "evil.com/x"})),
    ):
        detalhe, pedidos = await _detalhar(estranho, _json("detalhe_pcsx"))
        assert (detalhe, pedidos) == (None, [])


# --- resolver ---------------------------------------------------------------------------------


async def test_resolver_pcsx_com_dominio_no_endereco() -> None:
    resolvido, pedidos = await _resolver(
        "https://mercadolibre.eightfold.ai/careers?domain=mercadolibre.com&start=0",
        _json("normal_pcsx"),
    )
    assert resolvido == {"identificador": ML, "dominio": "mercadolibre.com", "geracao": "pcsx"}
    assert [p.url.path for p in pedidos] == ["/api/pcsx/search"]


async def test_resolver_acha_o_dominio_no_robots() -> None:
    def servidor(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/robots.txt":
            return httpx.Response(200, text=_texto("robots_mercadolibre.txt"))
        return _json("normal_pcsx")

    resolvido, pedidos = await _resolver(" MercadoLibre.eightfold.ai ", servidor)
    assert resolvido == {"identificador": ML, "dominio": "mercadolibre.com", "geracao": "pcsx"}
    assert [p.url.path for p in pedidos] == ["/robots.txt", "/api/pcsx/search"]
    assert _params(pedidos[1])["domain"] == "mercadolibre.com"


async def test_resolver_usa_v2_quando_pcsx_esta_desligado() -> None:
    def servidor(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/api/pcsx/search":
            return _json("pcsx_desligado", 403)
        return _json("normal_v2")

    resolvido, pedidos = await _resolver("bayer.eightfold.ai/careers?domain=bayer.com", servidor)
    assert resolvido == {"identificador": BAYER, "dominio": "bayer.com", "geracao": "v2"}
    assert [p.url.path for p in pedidos] == ["/api/pcsx/search", "/api/apply/v2/jobs"]


async def test_resolver_microsoft_tem_dominio_conhecido() -> None:
    resolvido, pedidos = await _resolver(
        "https://apply.careers.microsoft.com/careers/job/1970393557054020",
        _json("normal_microsoft"),
    )
    assert resolvido == {"identificador": MICROSOFT, "dominio": "microsoft.com", "geracao": "pcsx"}
    assert [p.url.path for p in pedidos] == ["/api/pcsx/search"]  # sem robots
    assert "work_site" not in _params(pedidos[0])


@pytest.mark.parametrize(
    "respostas",
    [
        (httpx.Response(403), httpx.Response(403)),
        (httpx.Response(200, text="<html>não é Eightfold</html>"),),
        (httpx.Response(404),),
    ],
)
async def test_resolver_recusa_o_que_nao_e_quadro_eightfold(
    respostas: tuple[httpx.Response, ...],
) -> None:
    with pytest.raises(ValueError):
        await _resolver("https://exemplo.eightfold.ai/?domain=exemplo.com", *respostas)


@pytest.mark.parametrize("robots", [httpx.Response(404), httpx.Response(200, text="User-agent: *")])
async def test_resolver_sem_dominio_recusa(robots: httpx.Response) -> None:
    with pytest.raises(ValueError):
        await _resolver("https://jobs.exemplo.com/careers", robots)


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "ftp://x.eightfold.ai/?domain=x.com",
        "http://127.0.0.1/?domain=x.com",
        "http://localhost/?domain=x.com",
        "https://user@x.eightfold.ai/?domain=x.com",
        "https://x.eightfold.ai:8443/?domain=x.com",
        "https://x.eightfold.ai/?domain=a/b",
        "https://x.eightfold.ai/?domain=a b",
        "sem ponto",
    ],
)
async def test_resolver_recusa_antes_de_pedir(entrada: str, http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await eightfold.COLETOR.resolver(entrada, http_proibido)


# --- critério 13: o 429 da Microsoft encerra só ela ------------------------------------------


class HistoricoVazio:
    """Nenhuma execução anterior: todo escopo está vencido e nada é conhecido."""

    def ultimo_inicio_com_pedido(self, fonte: str, escopo: str | None) -> datetime | None:
        return None

    def tres_ultimas_ok_trouxeram_vagas(self, fonte: str, escopo: str) -> bool:
        return False

    def tem_ocorrencia_aberta(self, fonte: str, escopo: str) -> bool:
        return False

    def ultima_coleta(self, fonte: str, escopo: str) -> datetime | None:
        return None

    def urls_conhecidas(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        return set()

    def detalhe_recente(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        return set()


async def test_429_da_microsoft_encerra_so_ela_e_as_outras_terminam() -> None:
    pedidos: list[httpx.Request] = []

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        if pedido.url.host == MICROSOFT:
            return httpx.Response(
                429, text=_texto("limite_microsoft.html"), headers={"Content-Type": "text/html"}
            )
        if pedido.url.host == BAYER:
            return _json("normal_v2")
        return _json("normal_pcsx")

    relogio = RelogioFalso()
    cli = _cliente(servidor, relogio)
    saidas: list[SaidaEscopo] = []

    async def guardar(saida: SaidaEscopo) -> None:
        saidas.append(saida)

    historico: Historico = HistoricoVazio()
    coletor: Coletor = copy.copy(eightfold.COLETOR)
    try:
        await executor.rodar(
            {"eightfold": coletor},
            ContextoColeta(empresas=TODAS, termos=("dev",), paises=("BR",)),
            cli,
            historico,
            relogio,
            ligadas={"eightfold"},
            ao_terminar_escopo=guardar,
        )
    finally:
        await cli.fechar()
    estados = {s.escopo: (s.resultado.estado, s.resultado.motivo) for s in saidas}
    assert estados == {
        MICROSOFT: ("no_limite", "saude.parou_429"),
        ML: ("ok", None),
        BAYER: ("ok", None),
    }
    microsoft = next(s for s in saidas if s.escopo == MICROSOFT)
    assert microsoft.resultado.pedidos == 1
    assert [p.url.host for p in pedidos].count(MICROSOFT) == 1  # sem nova tentativa
    assert 30.0 not in relogio.dormidas  # o 429 não espera
    assert len(next(s for s in saidas if s.escopo == ML).resultado.vagas) == 5
    assert len(next(s for s in saidas if s.escopo == BAYER).resultado.vagas) == 5


async def test_microsoft_espera_5_s_entre_paginas_via_executor() -> None:
    respostas = [_pagina(range(1, 11), 15), _pagina(range(11, 16), 15)]

    def servidor(pedido: httpx.Request) -> httpx.Response:
        assert pedido.url.host == MICROSOFT
        return respostas.pop(0)

    relogio = RelogioFalso()
    cli = _cliente(servidor, relogio)
    saidas: list[SaidaEscopo] = []

    async def guardar(saida: SaidaEscopo) -> None:
        saidas.append(saida)

    try:
        await executor.rodar(
            {"eightfold": copy.copy(eightfold.COLETOR)},
            ContextoColeta(empresas=(MS,), termos=("dev",), paises=("BR",)),
            cli,
            HistoricoVazio(),
            relogio,
            ligadas={"eightfold"},
            ao_terminar_escopo=guardar,
        )
    finally:
        await cli.fechar()
    assert [(s.escopo, s.resultado.estado, s.resultado.pedidos) for s in saidas] == [
        (MICROSOFT, "ok", 2)
    ]
    assert 5.0 in relogio.dormidas and 1.0 not in relogio.dormidas  # ritmo do escopo, não da fonte
