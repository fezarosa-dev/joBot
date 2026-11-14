import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, recrutei, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "recrutei"
URL_UCM = "https://api.recrutei.com.br/api/v2/vacancies/per-departments/ucm-business-solutions"
LINK_160532 = (
    "https://jobs.recrutei.com.br/ucm-business-solutions/vacancy/"
    "160532-manufacturing-it-project-coordinator-mes"
)
UCM = Empresa(nome="UCM", fonte="recrutei", identificador="ucm-business-solutions")
CHAVE = "SENTINELA-chave-embutida-no-site-0123456789"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str, ext: str = "json") -> str:
    return (PASTA / f"{caso}.{ext}").read_text(encoding="utf-8")


def _lista(caso: str, status: int = 202, **cabecalhos: str) -> httpx.Response:
    return httpx.Response(
        status, text=_texto(caso), headers={"Content-Type": "application/json", **cabecalhos}
    )


def _pagina(caso: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status, text=_texto(caso, "html"), headers={"Content-Type": "text/html; charset=utf-8"}
    )


def _normal() -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_texto("normal"))
    return dados


def _itens(dados: dict[str, Any]) -> list[dict[str, Any]]:
    """Os itens de todos os departamentos, na ordem."""
    return [i for d in dados["data"]["vacancies"] for i in d["items"]]


def _resposta(dados: object, status: int = 202) -> httpx.Response:
    return httpx.Response(status, json=dados)


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


def _cliente(servidor: Responder) -> ClienteEducado:
    relogio: Relogio = RelogioFalso()
    return ClienteEducado(
        httpx.MockTransport(servidor), relogio, LeitorFixo(), "0.1.0", resolver=_sem_dns
    )


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = "ucm-business-solutions",
    empresas: Sequence[Empresa] = (UCM,),
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    """Roda o coletor de verdade sobre o `ClienteEducado` com transporte falso."""
    pedidos: list[httpx.Request] = []
    fila = list(respostas)

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return r if isinstance(r, httpx.Response) else r(pedido)

    cli = _cliente(servidor)
    coletor = recrutei.Recrutei()
    coletor.escopos(ContextoColeta(empresas=empresas, termos=[], paises=[]))
    try:
        http: HttpEducado = cli.escopo()
        resultado = await coletor.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


async def _detalhar(
    item: object, *respostas: httpx.Response | Responder
) -> tuple[VagaColetada | None, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []
    fila = list(respostas)

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return r if isinstance(r, httpx.Response) else r(pedido)

    cli = _cliente(servidor)
    try:
        http: HttpEducado = cli.escopo()
        vaga = await recrutei.Recrutei().detalhar(item, http)  # type: ignore[arg-type]
    finally:
        await cli.fechar()
    return vaga, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """O `resolver` só lê o texto: qualquer pedido é erro do teste."""

    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"resolver não faz pedido: {pedido.url}")

    cli = _cliente(recusa)
    try:
        yield cli.escopo()
    finally:
        await cli.fechar()


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _html(vacancy: object, extra: dict[str, Any] | None = None) -> httpx.Response:
    retorno = {"vacancy": vacancy, "error": False, **(extra or {})}
    dados = {"props": {"pageProps": {"retorno": retorno}}}
    corpo = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(dados)}</script>'
    return httpx.Response(200, text=corpo, headers={"Content-Type": "text/html"})


async def _item_160532() -> VagaColetada:
    resultado, _ = await _coletar(_lista("normal"))
    return next(v for v in _vagas(resultado) if v.id_externo == "160532")


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = recrutei.COLETOR
    assert registro.descobrir()["recrutei"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "B"
    assert prova.hosts == ("api.recrutei.com.br", "jobs.recrutei.com.br")
    assert (prova.espera_s, prova.max_pedidos, prova.intervalo_min) == (1.0, None, None)


def test_escopos_um_por_empresa() -> None:
    empresas = [
        Empresa(nome="UCM", fonte="recrutei", identificador="ucm-business-solutions"),
        Empresa(nome="Outra", fonte="recrutei", identificador="outra"),
        Empresa(nome="UCM de novo", fonte="recrutei", identificador="ucm-business-solutions"),
    ]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(recrutei.Recrutei().escopos(ctx)) == ["ucm-business-solutions", "outra"]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_lista("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert [v.id_externo for v in vagas] == [
        "52155", "143244", "160532", "163703", "165514", "161801", "164508",
    ]  # fmt: skip
    primeira = vagas[0]
    assert primeira.fonte == "recrutei" and primeira.escopo == "ucm-business-solutions"
    assert primeira.empresa == "UCM Business Solutions"  # vem da própria vaga, não do cadastro
    assert primeira.titulo == "Banco de Talentos"
    assert primeira.url == (
        "https://jobs.recrutei.com.br/ucm-business-solutions/vacancy/52155-banco-de-talentos"
    )
    assert primeira.locais == ("São Bernardo do Campo, SP, Brasil",)
    assert primeira.modalidade_declarada == "hibrido"
    assert primeira.contrato_declarado is None  # "Não informado"
    assert primeira.salario_texto == "A combinar"
    assert primeira.etiquetas == ("Tecnologia da Informação",)
    assert (primeira.descricao, primeira.descricao_formato) == ("", "html")  # vem no detalhe
    assert primeira.publicada_em is None and primeira.url_candidatura is None
    assert vagas[2].contrato_declarado == "PJ ou Cooperado/Associado"
    assert vagas[2].modalidade_declarada == "presencial"
    assert vagas[5].locais == ()  # "Não informado"
    assert vagas[6].etiquetas == ("Operacional",)
    assert len(pedidos) == 1


async def test_salario_em_texto_e_cliente_na_captura_da_daguilar() -> None:
    # o recorte da captura tem 6 das 7 vagas (a redução cortou 1): a trava do total pega
    resultado, _ = await _coletar(_lista("daguilar"), escopo="daguilar-consultoria-rh")
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.listagem_incompleta")
    vagas = _vagas(resultado)
    assert len(vagas) == 6
    assert {v.empresa for v in vagas} == {"DAGUILAR CONSULTORIA RH"}
    assert vagas[0].salario_texto == "R$ 1.780,00 p/ Mês"
    assert vagas[3].contrato_declarado == "Pessoa Jurídica"
    assert vagas[1].locais == ()


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_lista("vazio"), escopo="empresa-sem-vagas")
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    # 2 de 7 itens ilegíveis (sem título; sem company_name): as 5 legíveis saem, parcial
    resultado, _ = await _coletar(_lista("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == [
        "52155", "163703", "165514", "161801", "164508",
    ]  # fmt: skip


@pytest.mark.parametrize(
    "corpo",
    [
        '{"ok": true}',
        "isto não é json",
        "[]",
        "null",
        '{"data": {"total": 1, "vacancies": "x"}}',
        '{"data": {"vacancies": []}}',  # sem `total`: não dá para saber se veio inteira
        '{"data": {"total": "1", "vacancies": []}}',
        '{"data": {"total": true, "vacancies": []}}',
        '{"data": {"total": 1, "vacancies": [{"department": "A", "items": "x"}]}}',
        '{"data": {"total": 1, "vacancies": [{"department": "A", "items": [{"id": 1}]}]}}',
        '{"data": {"total": 1, "vacancies": [1]}}',
        '{"data": {"total": 3, "vacancies": []}}',  # diz ter vagas e não traz nenhuma
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(202, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_total_maior_que_os_itens_e_listagem_incompleta() -> None:
    dados = _normal()
    dados["data"]["total"] = 8
    resultado, _ = await _coletar(_resposta(dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.listagem_incompleta")
    assert len(resultado.vagas) == 7


async def test_total_menor_que_os_itens_nao_derruba() -> None:
    dados = _normal()
    dados["data"]["total"] = 3
    resultado, _ = await _coletar(_resposta(dados))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert len(resultado.vagas) == 7


async def test_status_200_tambem_serve() -> None:
    resultado, _ = await _coletar(_lista("normal", status=200))
    assert resultado.estado == "ok" and len(resultado.vagas) == 7


@pytest.mark.parametrize(
    ("remote", "modalidade"),
    [
        (0, "presencial"),
        (1, "remoto"),
        (2, "presencial ou remoto"),
        (3, "hibrido"),
        (4, None),
        (-1, None),
        (None, None),
        ("1", None),
        (True, None),
        (1.0, None),
    ],
)
async def test_campo_remote(remote: object, modalidade: str | None) -> None:
    # 0 é confirmado (captura); 1, 2 e 3 seguem a ordem do site e estão por confirmar
    dados = _normal()
    dados["data"]["vacancies"][0]["items"][0]["remote"] = remote
    resultado, _ = await _coletar(_resposta(dados))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].modalidade_declarada == modalidade


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _normal()
    dados["data"]["vacancies"][0]["items"][0] |= {
        "location": 5,
        "salary": None,
        "regime": 5,
        "department": None,
        "remote": "x",
    }
    resultado, _ = await _coletar(_resposta(dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.locais, vaga.salario_texto, vaga.contrato_declarado) == ((), None, None)
    # o departamento da vaga não lido não tira o do grupo em que ela veio
    assert (vaga.etiquetas, vaga.modalidade_declarada) == (("Tecnologia da Informação",), None)


async def test_id_ausente_ou_estranho_fica_sem_id_externo() -> None:
    dados = _normal()
    itens = dados["data"]["vacancies"][0]["items"]
    itens[0]["id"] = None
    itens[1]["id"] = True
    del itens[2]["id"]
    resultado, _ = await _coletar(_resposta(dados))
    assert resultado.estado == "ok"
    assert [v.id_externo for v in _vagas(resultado)[:4]] == [None, None, None, "163703"]


async def test_location_lista_vira_um_local_e_texto_vira_vazio() -> None:
    dados = _normal()
    itens = dados["data"]["vacancies"][0]["items"]
    itens[0]["location"] = ["Recife", "PE", "Brasil"]
    itens[1]["location"] = ["Lisboa", "", None, "Portugal"]
    itens[2]["location"] = "Não informado"
    itens[3]["location"] = []
    resultado, _ = await _coletar(_resposta(dados))
    assert [v.locais for v in _vagas(resultado)[:4]] == [
        ("Recife, PE, Brasil",),
        ("Lisboa, Portugal",),
        (),
        (),
    ]


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = _normal()
    dados["data"]["vacancies"][0]["items"][1]["public_link"] = "javascript:alert(1)"
    resultado, _ = await _coletar(_resposta(dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 6


async def test_404_empresa_nao_encontrada() -> None:
    resultado, pedidos = await _coletar(_lista("nao_encontrado", 404), escopo="nao-existe")
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
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_304_vira_sem_mudanca_pela_identidade(monkeypatch: pytest.MonkeyPatch) -> None:
    # POST não manda validador, mas um 304 de um intermediário não pode virar lista vazia "ok"
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

    monkeypatch.setattr(recrutei, "juntar_paginas", espia)
    resultado, _ = await _coletar(httpx.Response(304))
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_pedido_da_lista_e_post_com_corpo_vazio() -> None:
    _, pedidos = await _coletar(_lista("vazio"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "POST"
    assert str(pedido.url) == URL_UCM
    assert pedido.content == b"{}"
    assert pedido.headers["Content-Type"].startswith("application/json")


async def test_escopo_estranho_nao_muda_o_caminho() -> None:
    _, pedidos = await _coletar(_lista("vazio"), escopo="../x?y#z")
    assert [p.url.raw_path for p in pedidos] == [
        b"/api/v2/vacancies/per-departments/..%2Fx%3Fy%23z"
    ]


async def test_chave_embutida_no_site_nunca_sai() -> None:
    """A chave da API antiga está no site (apêndice 3.1): nenhum pedido a leva, de nenhum jeito."""
    lista = _normal()
    lista["api_key"] = CHAVE  # mesmo que a resposta a repita, o coletor não a usa
    pagina = _html(
        {"id": 160532, "description": "<p>Texto</p>", "published_at": "05/10/2026 09:45:05"},
        {"apiKey": CHAVE, "token": CHAVE},
    )
    pagina = httpx.Response(
        200,
        text=pagina.text + f'<script>window.__CHAVE__ = "{CHAVE}"</script>',
        headers={"Content-Type": "text/html"},
    )
    resultado, p_lista = await _coletar(_resposta(lista))
    item = next(v for v in _vagas(resultado) if v.id_externo == "160532")
    vaga, p_detalhe = await _detalhar(item, pagina)
    assert vaga is not None and CHAVE not in vaga.para_json()
    pedidos = p_lista + p_detalhe
    assert [p.method for p in pedidos] == ["POST", "GET"]
    for pedido in pedidos:
        visto = [str(pedido.url), pedido.content.decode(), *pedido.headers.keys()]
        visto += list(pedido.headers.values())
        assert not [v for v in visto if CHAVE in v], pedido.url
        nomes = {n.lower() for n in pedido.headers}
        assert not {"authorization", "x-api-key", "api-key", "token", "cookie"} & nomes
    assert p_detalhe[0].content == b""


async def test_detalhar_completa_a_vaga_da_lista() -> None:
    item = await _item_160532()
    vaga, pedidos = await _detalhar(item, _pagina("detalhe"))
    assert vaga is not None
    assert [(p.method, str(p.url)) for p in pedidos] == [("GET", LINK_160532)]
    assert vaga.url == item.url  # a URL é a chave da vaga
    assert vaga.descricao_formato == "html"
    assert vaga.descricao.startswith("<p>Zona Oeste de São Paulo/SP<br>")
    assert vaga.etiquetas == (
        "Tecnologia da Informação",
        "Manufatura",
        "Tecnologia",
        "Fábrica",
        "Coordenação",
        "Impressoras Zebra",
        "Balanças",
        "Sistemas MES",
    )
    # o resto vem da lista, sem mudança
    assert (vaga.titulo, vaga.empresa, vaga.id_externo) == (
        item.titulo, item.empresa, item.id_externo,
    )  # fmt: skip
    assert (vaga.locais, vaga.modalidade_declarada) == (item.locais, "presencial")
    assert (vaga.contrato_declarado, vaga.salario_texto) == (
        "PJ ou Cooperado/Associado",
        "A combinar",
    )


async def test_published_at_e_horario_de_brasilia() -> None:
    item = await _item_160532()
    vaga, _ = await _detalhar(item, _pagina("detalhe"))
    assert vaga is not None
    assert vaga.publicada_em == datetime(
        2026, 10, 5, 9, 45, 5, tzinfo=timezone(timedelta(hours=-3))
    )


async def test_detalhar_junta_beneficios_prazo_e_trata_data_ruim() -> None:
    item = await _item_160532()
    base_vaga = {"id": 160532, "description": "<p>Corpo</p>"}
    vaga, _ = await _detalhar(
        item,
        _html(
            base_vaga
            | {
                "benefits": "<ul><li>VR</li></ul>",
                "skills": " a , b,, a ",
                "expired_at": "31/12/2026 23:59:59",
                "published_at": "ontem",
            }
        ),
    )
    assert vaga is not None
    assert vaga.descricao == "<p>Corpo</p><h2>Benefícios</h2><ul><li>VR</li></ul>"
    assert vaga.etiquetas == ("Tecnologia da Informação", "a", "b")
    assert vaga.prazo == date(2026, 12, 31)
    assert vaga.publicada_em is None  # data ilegível não derruba a descrição


@pytest.mark.parametrize("data", ["", "31/02/2026 10:00:00", "2026-10-05", "05/10/2026", 5, None])
async def test_published_at_estranho_fica_sem_data(data: object) -> None:
    item = await _item_160532()
    vaga, _ = await _detalhar(item, _html({"description": "<p>x</p>", "published_at": data}))
    assert vaga is not None and vaga.publicada_em is None


async def test_detalhar_vaga_encerrada_devolve_none() -> None:
    item = await _item_160532()
    vaga, pedidos = await _detalhar(item, _pagina("detalhe_encerrada"))
    assert vaga is None and len(pedidos) == 1


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(404),
        httpx.Response(200, text="<html>sem dados</html>"),
        httpx.Response(200, text='<script id="__NEXT_DATA__" type="application/json">{x</script>'),
        httpx.Response(200, text='<script id="__NEXT_DATA__" type="application/json">[1]</script>'),
        _html(None),
        _html({"id": 1}),
        _html({"description": "   "}),
        _html({"description": 5}),
        _html({"description": "<p>x</p>"}, {"error": True}),
    ],
)
async def test_detalhar_sem_o_que_acrescentar_devolve_none(resposta: httpx.Response) -> None:
    item = await _item_160532()
    vaga, _ = await _detalhar(item, resposta)
    assert vaga is None


async def test_detalhar_429_sobe_para_o_executor() -> None:
    from jobot.nucleo.http import LimiteAtingido

    item = await _item_160532()
    with pytest.raises(LimiteAtingido):
        await _detalhar(item, httpx.Response(429))


@pytest.mark.parametrize(
    "url",
    [
        "https://exemplo.com/vaga/1",
        "http://127.0.0.1/vaga/1",
        "https://jobs.recrutei.com.br.exemplo.com/x/vacancy/1-a",
        "http://jobs.recrutei.com.br/x/vacancy/1-a",
        "https://api.recrutei.com.br/x",
    ],
)
async def test_detalhar_so_busca_no_host_das_vagas(url: str) -> None:
    item = await _item_160532()
    fora = VagaColetada(**{**item.__dict__, "url": url})
    vaga, pedidos = await _detalhar(fora, _pagina("detalhe"))
    assert vaga is None and pedidos == []


async def test_detalhar_ignora_o_que_nao_e_vaga_coletada() -> None:
    vaga, pedidos = await _detalhar(
        "https://jobs.recrutei.com.br/x/vacancy/1-a", _pagina("detalhe")
    )
    assert vaga is None and pedidos == []


@pytest.mark.parametrize(
    ("entrada", "label"),
    [
        ("ucm-business-solutions", "ucm-business-solutions"),
        (" ucm-business-solutions ", "ucm-business-solutions"),
        ("UCM-Business", "UCM-Business"),  # caixa como veio
        ("https://jobs.recrutei.com.br/ucm-business-solutions", "ucm-business-solutions"),
        ("https://jobs.recrutei.com.br/ucm-business-solutions/", "ucm-business-solutions"),
        ("jobs.recrutei.com.br/ucm-business-solutions", "ucm-business-solutions"),
        (f"{LINK_160532}", "ucm-business-solutions"),
        (
            "https://api.recrutei.com.br/api/v2/vacancies/per-departments/ucm-business-solutions",
            "ucm-business-solutions",
        ),
    ],
)
async def test_resolver_aceita_label_ou_endereco_e_nao_faz_pedido(
    entrada: str, label: str, http_proibido: HttpEducado
) -> None:
    assert await recrutei.COLETOR.resolver(entrada, http_proibido) == {"identificador": label}


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "https://jobs.lever.co/ucm",
        "https://recrutei.com.br/ucm",
        "https://jobs.recrutei.com.br/",
        "https://api.recrutei.com.br/api/v2/vacancies/per-departments",
        "https://api.recrutei.com.br/api/v1/vacancies/per-departments/ucm",
        "ftp://jobs.recrutei.com.br/ucm",
        "ucm business",
        "ucmé",
        "x" * 101,
    ],
)
async def test_resolver_recusa_o_que_nao_e_quadro(entrada: str, http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await recrutei.COLETOR.resolver(entrada, http_proibido)
