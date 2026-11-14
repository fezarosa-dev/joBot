import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo, UrlListada
from jobot.nucleo.coletores.portais import super_estagios
from jobot.nucleo.http import (
    Bloqueio,
    ClienteEducado,
    ErroDeRede,
    HttpEducado,
    LimiteAtingido,
    RespostaGrande,
    Validadores,
)
from jobot.nucleo.modelo import Empresa, SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "super_estagios"
URL_SITEMAP = "https://www.superestagios.com.br/sitemap_vagas.php"
URL_VAGA = "https://www.superestagios.com.br/vaga/329131"
BRASILIA = timezone(timedelta(hours=-3))
Responder = Callable[[httpx.Request], httpx.Response]
_JSON_LD = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.DOTALL)


def _texto(caso: str) -> str:
    extensao = "xml" if caso.startswith("sitemap") else "html"
    return (PASTA / f"{caso}.{extensao}").read_text(encoding="utf-8")


def _resposta(caso_ou_texto: str, status: int = 200) -> httpx.Response:
    texto = caso_ou_texto
    if caso_ou_texto in ("sitemap", "sitemap_vazio", "sitemap_formato_mudou", "vaga"):
        texto = _texto(caso_ou_texto)
    tipo = "application/xml" if texto.lstrip().startswith("<?xml") else "text/html"
    return httpx.Response(status, text=texto, headers={"Content-Type": f"{tipo}; charset=utf-8"})


def _sitemap(*entradas: str, raiz: str = "urlset") -> str:
    """Um sitemap com o namespace do protocolo; cada entrada é o miolo de um `<url>`."""
    urls = "".join(f"<url>{e}</url>" for e in entradas)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<{raiz} xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</{raiz}>'
    )


def _entrada(id_: int | str, lastmod: str | None = "2026-11-13") -> str:
    data = "" if lastmod is None else f"<lastmod>{lastmod}</lastmod>"
    return f"<loc>https://www.superestagios.com.br/vaga/{id_}</loc>{data}"


def _json_ld() -> dict[str, object]:
    achado = _JSON_LD.search(_texto("vaga"))
    assert achado is not None
    dados: dict[str, object] = json.loads(achado[2])
    return dados


def _pagina(ld: object, *, tabela: bool = True) -> str:
    """A página da vaga do exemplo com outro JSON-LD (e, se pedido, sem a tabela de rótulos)."""
    html = _JSON_LD.sub(lambda m: m[1] + json.dumps(ld, ensure_ascii=False) + m[3], _texto("vaga"))
    if not tabela:
        html = re.sub(r"<table.*?</table>", "", html, flags=re.DOTALL)
    return html


def _ld(**mudancas: object) -> dict[str, object]:
    """O JSON-LD do exemplo com campos trocados; valor `None` tira o campo."""
    dados = _json_ld()
    for campo, valor in mudancas.items():
        if valor is None:
            dados.pop(campo, None)
        else:
            dados[campo] = valor
    return dados


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _rodar[T](
    chamar: Callable[[HttpEducado], Awaitable[T]],
    *respostas: httpx.Response | Responder,
    leitor: LeitorFixo | None = None,
    condicional: bool = False,
) -> tuple[T, list[httpx.Request]]:
    """Roda sobre o `ClienteEducado` de verdade com transporte falso; devolve o que `chamar` deu."""
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
        resultado = await chamar(http)
    finally:
        await cli.fechar()
    return resultado, pedidos


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = "",
    leitor: LeitorFixo | None = None,
    condicional: bool = False,
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    async def chamar(http: HttpEducado) -> ResultadoEscopo:
        return await super_estagios.COLETOR.coletar(escopo, http)

    return await _rodar(chamar, *respostas, leitor=leitor, condicional=condicional)


async def _detalhar(
    item: UrlListada | VagaColetada, *respostas: httpx.Response | Responder
) -> tuple[VagaColetada | None, list[httpx.Request]]:
    async def chamar(http: HttpEducado) -> VagaColetada | None:
        return await super_estagios.COLETOR.detalhar(item, http)

    return await _rodar(chamar, *respostas)


def _urls(resultado: ResultadoEscopo) -> list[UrlListada]:
    urls = [v for v in resultado.vagas if isinstance(v, UrlListada)]
    assert len(urls) == len(resultado.vagas)  # a fonte de sitemap nunca devolve VagaColetada
    return urls


def _item(url: str = URL_VAGA) -> UrlListada:
    return UrlListada(url, datetime(2026, 11, 13, tzinfo=BRASILIA))


async def _vaga(html: str) -> VagaColetada:
    vaga, _ = await _detalhar(_item(), _resposta(html))
    assert vaga is not None
    return vaga


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = super_estagios.COLETOR
    assert registro.descobrir()["super_estagios"] is prova
    limites = registro.limites("super_estagios")
    assert limites.leva == prova.leva == "B"
    assert prova.hosts == ("www.superestagios.com.br",)
    assert (prova.intervalo_min, prova.max_pedidos) == (limites.intervalo_min, limites.max_pedidos)
    assert (prova.espera_s, prova.credito_obrigatorio) == (limites.espera_s, False)
    assert prova.por_escopo == limites.por_escopo


def test_escopo_unico() -> None:
    empresas = [Empresa(nome="Vitta", fonte="greenhouse", identificador="vitta")]
    assert list(super_estagios.COLETOR.escopos(ContextoColeta(empresas, ["dev"], ["BR"]))) == [""]
    assert list(super_estagios.COLETOR.escopos(ContextoColeta((), (), ()))) == [""]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_resposta("sitemap"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    urls = _urls(resultado)
    assert [u.url for u in urls] == [
        f"https://www.superestagios.com.br/vaga/{n}"
        for n in (329124, 329125, 329126, 329130, 329131)
    ]
    # `lastmod` só com data: vale a meia-noite de Brasília (o `validThrough` do site é -03:00)
    assert urls[0].atualizada_em == datetime(2026, 11, 12, tzinfo=BRASILIA)
    assert urls[4].atualizada_em == datetime(2026, 11, 13, tzinfo=BRASILIA)
    assert all(u.url.startswith("https://") for u in urls)
    assert len(pedidos) == 1


async def test_sitemap_com_namespace_do_protocolo() -> None:
    corpo = _sitemap(_entrada(1), _entrada(2, "2026-11-12"))
    resultado, _ = await _coletar(_resposta(corpo))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert [u.url[-1] for u in _urls(resultado)] == ["1", "2"]


async def test_devolve_todas_as_urls_sem_filtrar_por_data() -> None:
    """O filtro de 30 dias é do executor (DR-70): o coletor devolve a URL velha e a sem data."""
    corpo = _sitemap(_entrada(1, "2020-01-01"), _entrada(2, None), _entrada(3, "2026-11-13"))
    resultado, _ = await _coletar(_resposta(corpo))
    urls = _urls(resultado)
    assert [u.url[-1] for u in urls] == ["1", "2", "3"]
    assert urls[0].atualizada_em == datetime(2020, 1, 1, tzinfo=BRASILIA)
    assert urls[1].atualizada_em is None


@pytest.mark.parametrize(
    ("lastmod", "esperado"),
    [
        ("2026-11-13T10:00:00+00:00", datetime(2026, 11, 13, 10, tzinfo=UTC)),
        ("2026-11-13T10:00:00Z", datetime(2026, 11, 13, 10, tzinfo=UTC)),
        ("2026-11-13T10:00:00", datetime(2026, 11, 13, 10, tzinfo=BRASILIA)),
        ("ontem", None),
        ("", None),
        ("2026-13-45", None),
    ],
)
async def test_lastmod_com_fuso_ou_sem_data(lastmod: str, esperado: datetime | None) -> None:
    resultado, _ = await _coletar(_resposta(_sitemap(_entrada(1, lastmod))))
    (url,) = _urls(resultado)
    assert url.atualizada_em == esperado
    assert resultado.estado == "ok"  # data ruim não pula a URL: o executor trata como sem data


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_resposta("sitemap_vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_resposta("sitemap_formato_mudou"))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


@pytest.mark.parametrize(
    "corpo",
    [
        "",
        "<html><body>manutenção</body></html>",
        "isto não é XML",
        _sitemap(_entrada(1), raiz="sitemapindex"),  # índice de sitemaps: o coletor não o segue
        _sitemap("<loc></loc>", "<changefreq>daily</changefreq>"),  # nenhuma entrada com endereço
    ],
)
async def test_formato_mudou_sem_url_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(_resposta(corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_entrada_sem_endereco_deixa_parcial_nunca_ok() -> None:
    """Item pulado deixa "parcial": "ok" fecharia a vaga que ficou de fora."""
    corpo = _sitemap(_entrada(1), "<lastmod>2026-11-13</lastmod>", _entrada(2))
    resultado, _ = await _coletar(_resposta(corpo))
    assert [u.url[-1] for u in _urls(resultado)] == ["1", "2"]
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")


async def test_url_de_host_local_e_pulada_e_contada() -> None:
    corpo = _sitemap("<loc>http://127.0.0.1/x</loc>", _entrada(329131))
    resultado, pedidos = await _coletar(_resposta(corpo))
    assert [u.url for u in _urls(resultado)] == [URL_VAGA]  # só a boa sai em `vagas`
    assert (resultado.estado, resultado.motivo) == ("ok", "saude.sem_detalhe_n:1")
    assert [str(p.url) for p in pedidos] == [URL_SITEMAP]  # nenhum pedido à URL local
    assert resultado.pedidos == 1


@pytest.mark.parametrize(
    "loc",
    [
        "http://localhost/vaga/1",
        "http://[::1]/vaga/1",
        "http://192.168.0.10/vaga/1",
        "https://exemplo.test/vaga/1",  # host que não é do site: o sitemap é dado de terceiro
        "https://www.superestagios.com.br.exemplo.test/vaga/1",
        "https://www.superestagios.com.br/vagas/belem",  # página de listagem, não de vaga
        "https://www.superestagios.com.br/vaga/abc",
        "https://www.superestagios.com.br/vaga/1/extra",
        "ftp://www.superestagios.com.br/vaga/1",
        "javascript:alert(1)",
    ],
)
async def test_url_que_nao_e_vaga_do_site_e_pulada_e_contada(loc: str) -> None:
    corpo = _sitemap(f"<loc>{loc}</loc>", _entrada(7))
    resultado, pedidos = await _coletar(_resposta(corpo))
    assert [u.url[-1] for u in _urls(resultado)] == ["7"]
    assert (resultado.estado, resultado.motivo) == ("ok", "saude.sem_detalhe_n:1")
    assert len(pedidos) == 1


async def test_sitemap_so_com_url_recusada_e_formato_mudou() -> None:
    corpo = _sitemap("<loc>http://127.0.0.1/x</loc>", "<loc>https://exemplo.test/vaga/1</loc>")
    resultado, _ = await _coletar(_resposta(corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


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


async def test_sitemap_acima_do_teto_de_5_mb_sobe_resposta_grande() -> None:
    enorme = _sitemap(*(_entrada(n) for n in range(150_000)))
    assert len(enorme.encode()) > 5 * 1024 * 1024
    with pytest.raises(RespostaGrande):
        await _coletar(_resposta(enorme))


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_resposta("sitemap_vazio"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert str(pedido.url) == URL_SITEMAP
    assert dict(pedido.url.params) == {}


async def test_sem_pedido_condicional() -> None:
    """A conferência só viu `cache-control` no sitemap, sem `ETag` nem `Last-Modified`."""
    leitor = LeitorFixo({URL_SITEMAP: Validadores('"v1"', "Fri, 13 Nov 2026 14:44:36 GMT")})
    _, pedidos = await _coletar(_resposta("sitemap"), leitor=leitor, condicional=True)
    assert len(pedidos) == 1
    assert pedidos[0].headers.get("If-None-Match") is None
    assert pedidos[0].headers.get("If-Modified-Since") is None


async def test_detalhar_normal() -> None:
    vaga, pedidos = await _detalhar(_item(), _resposta("vaga"))
    assert vaga is not None
    assert (vaga.fonte, vaga.escopo, vaga.id_externo) == ("super_estagios", "", "329131")
    assert vaga.url == URL_VAGA  # o da URL listada: é por ele que o executor acha a vaga de novo
    assert vaga.titulo == "Estágio em FISIOTERAPIA"
    assert vaga.empresa == "CONFIDENCIAL"
    assert vaga.locais == ("Belém, PA",)
    assert vaga.contrato_declarado == "INTERN"
    assert vaga.salario_estruturado == SalarioBruto(
        moeda="BRL", minimo_unidades=350, maximo_unidades=None, periodo="mes"
    )
    assert vaga.publicada_em == datetime(2026, 11, 13, tzinfo=BRASILIA)
    assert vaga.prazo == date(2026, 12, 13)
    assert vaga.descricao_formato == "texto"
    assert vaga.descricao.startswith(
        "Atividades a serem desenvolvidas: Acompanhamento e auxílio nos atendimentos"
    )
    for trecho in (
        "Requisito: A partir do 5º período",
        "Nível: Superior",
        "Cursos: FISIOTERAPIA",
        "Período: Vespertino e Noturno - 6 horas diárias",
        "Horário: Das 14:00 até 20:00",
        "Valor da bolsa: R$ 350,00",
        "Valor do auxilio transporte: R$ 50,00 mês",
        "Informações adicionais: Não possui informações adicionais.",
    ):
        assert trecho in vaga.descricao
    assert "Benefícios" not in vaga.descricao  # a linha veio vazia
    assert "Número da vaga" not in vaga.descricao and "Quantidade" not in vaga.descricao
    assert vaga.modalidade_declarada is None and vaga.url_candidatura is None
    assert [(p.method, str(p.url), dict(p.url.params)) for p in pedidos] == [("GET", URL_VAGA, {})]


async def test_detalhar_sem_tabela_usa_a_descricao_do_json_ld() -> None:
    vaga = await _vaga(_pagina(_json_ld(), tabela=False))
    assert vaga.titulo == "Estágio em FISIOTERAPIA"
    assert vaga.descricao == _json_ld()["description"]


@pytest.mark.parametrize(
    "mudancas",
    [
        {"title": None},
        {"title": ""},
        {"title": "   "},
        {"title": 12},
        {"hiringOrganization": None},
        {"hiringOrganization": {"@type": "Organization"}},
        {"hiringOrganization": {"name": "  "}},
        {"hiringOrganization": {"name": None}},
        {"hiringOrganization": "CONFIDENCIAL"},
    ],
)
async def test_detalhar_sem_titulo_ou_empresa_devolve_none(mudancas: dict[str, object]) -> None:
    vaga, pedidos = await _detalhar(_item(), _resposta(_pagina(_ld(**mudancas))))
    assert vaga is None
    assert len(pedidos) == 1


@pytest.mark.parametrize(
    "html",
    [
        "",
        "<html><body>Vaga encerrada</body></html>",
        '<script type="application/ld+json">{não é json</script>',
        '<script type="application/ld+json">[1, "x", null]</script>',
        '<script type="application/ld+json">{"@type": "Organization", "name": "X"}</script>',
    ],
)
async def test_detalhar_sem_json_ld_de_vaga_devolve_none(html: str) -> None:
    vaga, _ = await _detalhar(_item(), _resposta(html))
    assert vaga is None


async def test_detalhar_json_ld_em_lista_ou_graph() -> None:
    em_lista = await _vaga(_pagina([{"@type": "WebSite"}, _json_ld()]))
    assert em_lista.titulo == "Estágio em FISIOTERAPIA"
    em_graph = await _vaga(_pagina({"@graph": [{"@type": "WebSite"}, _json_ld()]}))
    assert em_graph.empresa == "CONFIDENCIAL"
    tipos = await _vaga(_pagina(_ld(**{"@type": ["Thing", "JobPosting"]})))
    assert tipos.titulo == "Estágio em FISIOTERAPIA"


async def test_detalhar_ignora_o_endereco_que_a_pagina_diz() -> None:
    """O JSON-LD é dado de terceiro: o link da vaga é o da URL listada, nunca o do JSON-LD."""
    ld = _ld(url="https://exemplo.test/outra", identifier={"value": "999"})
    vaga = await _vaga(_pagina(ld))
    assert vaga.url == URL_VAGA


async def test_detalhar_identificador_cai_para_o_numero_da_url() -> None:
    sem_id = await _vaga(_pagina(_ld(identifier=None)))
    assert sem_id.id_externo == "329131"
    numero = await _vaga(_pagina(_ld(identifier={"value": 329131})))
    assert numero.id_externo == "329131"
    em_branco = await _vaga(_pagina(_ld(identifier={"value": "  "})))
    assert em_branco.id_externo == "329131"


async def test_detalhar_campos_opcionais_estranhos_nao_derrubam_a_vaga() -> None:
    ld = _ld(
        baseSalary="a combinar",
        datePosted="ontem",
        validThrough=["2026-12-13"],
        jobLocation=7,
        employmentType={"x": 1},
    )
    vaga = await _vaga(_pagina(ld, tabela=False))
    assert vaga.titulo == "Estágio em FISIOTERAPIA"
    assert vaga.salario_estruturado is None
    assert (vaga.publicada_em, vaga.prazo) == (None, None)
    assert vaga.locais == ()
    assert vaga.contrato_declarado is None


async def test_detalhar_datas_com_hora_e_fuso() -> None:
    ld = _ld(datePosted="2026-11-13T09:30:00+00:00", validThrough="2026-12-13")
    vaga = await _vaga(_pagina(ld))
    assert vaga.publicada_em == datetime(2026, 11, 13, 9, 30, tzinfo=UTC)
    assert vaga.prazo == date(2026, 12, 13)
    sem_fuso = await _vaga(_pagina(_ld(datePosted="2026-11-13T09:30:00")))
    assert sem_fuso.publicada_em == datetime(2026, 11, 13, 9, 30, tzinfo=BRASILIA)


async def test_detalhar_local_em_lista_e_so_a_cidade() -> None:
    lugar = {"address": {"addressLocality": "Belém", "addressRegion": "PA"}}
    so_cidade = {"address": {"addressLocality": "Recife"}}
    vaga = await _vaga(_pagina(_ld(jobLocation=[lugar, so_cidade, {"address": {}}, lugar])))
    assert vaga.locais == ("Belém, PA", "Recife")


def _salario(valor: object, unidade: object = "MONTH", moeda: object = "BRL") -> dict[str, object]:
    return {
        "currency": moeda,
        "value": {"unitText": unidade} | (valor if isinstance(valor, dict) else {"value": valor}),
    }


@pytest.mark.parametrize(
    ("base", "esperado"),
    [
        (_salario(350.5), SalarioBruto(moeda="BRL", minimo_unidades=350.5, periodo="mes")),
        (
            _salario({"minValue": 10, "maxValue": 12}, "HOUR"),
            SalarioBruto(moeda="BRL", minimo_unidades=10, maximo_unidades=12, periodo="hora"),
        ),
        (_salario(5, "DAY"), SalarioBruto(moeda="BRL", minimo_unidades=5, periodo="dia")),
        (_salario(5, "WEEK"), SalarioBruto(moeda="BRL", minimo_unidades=5, periodo="semana")),
        (_salario(5, "YEAR"), SalarioBruto(moeda="BRL", minimo_unidades=5, periodo="ano")),
        (_salario(500, "FORTNIGHT"), SalarioBruto(moeda="BRL", minimo_unidades=500)),
        (_salario(500, "MONTH", None), SalarioBruto(minimo_unidades=500, periodo="mes")),
        (_salario(0), None),
        (_salario(-1), None),
        (_salario(True), None),
        (_salario("350"), None),
        (_salario(float("inf")), None),
        ({"currency": "BRL"}, None),
        ([1, 2], None),
    ],
)
async def test_detalhar_salario(base: object, esperado: SalarioBruto | None) -> None:
    vaga = await _vaga(_pagina(_ld(baseSalary=base), tabela=False))
    assert vaga.salario_estruturado == esperado


@pytest.mark.parametrize("status", [404, 410])
async def test_detalhar_vaga_que_saiu_do_ar_devolve_none(status: int) -> None:
    """A URL segue no sitemap em cache: `None` a guarda 30 dias, sem repetir o 404."""
    vaga, pedidos = await _detalhar(_item(), httpx.Response(status, text="não encontrada"))
    assert vaga is None
    assert len(pedidos) == 1


async def test_detalhar_erros_de_rede_e_de_limite_sobem_para_o_executor() -> None:
    with pytest.raises(Bloqueio):
        await _detalhar(_item(), httpx.Response(403))
    with pytest.raises(LimiteAtingido):
        await _detalhar(_item(), httpx.Response(429))
    with pytest.raises(ErroDeRede) as erro:
        await _detalhar(_item(), httpx.Response(500))
    assert erro.value.status == 500


@pytest.mark.parametrize(
    "url",
    [
        "https://exemplo.test/vaga/1",
        "https://www.superestagios.com.br/vagas/belem",
        "https://www.superestagios.com.br/vaga/abc",
    ],
)
async def test_detalhar_nao_pede_url_que_nao_e_vaga_do_site(url: str) -> None:
    def nao_pede(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"pediu {pedido.url}")

    vaga, pedidos = await _detalhar(UrlListada(url), nao_pede)
    assert (vaga, pedidos) == (None, [])


async def test_detalhar_de_vaga_ja_pronta_nao_pede() -> None:
    def nao_pede(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"pediu {pedido.url}")

    pronta = await _vaga(_texto("vaga"))
    assert await _detalhar(pronta, nao_pede) == (None, [])


async def test_resolver() -> None:
    class SemRede:
        async def pedir(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("não pede")

    with pytest.raises(ValueError):
        await super_estagios.COLETOR.resolver("329131", SemRede())  # type: ignore[arg-type]
