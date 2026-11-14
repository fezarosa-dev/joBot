from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import registro
from jobot.nucleo.coletores.base import (
    SEM_MUDANCA,
    Coletor,
    ContextoColeta,
    ResultadoEscopo,
    UrlListada,
)
from jobot.nucleo.coletores.portais import abler
from jobot.nucleo.http import Bloqueio, ClienteEducado, HttpEducado, LeitorValidadores, Validadores
from jobot.nucleo.modelo import Empresa, SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "abler"
SITEMAP = "https://candidatos.abler.com.br/sitemap.xml"
VAGA = "https://candidatos.abler.com.br/vagas/estagio-em-rh-recrutamento-e-selecao-927222"
NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
Responder = Callable[[httpx.Request], httpx.Response]


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return None


class LeitorComEtag:
    """Guardou um ETag para qualquer URL: um coletor que pedisse condicional o mandaria."""

    def ler(self, url: str) -> Validadores | None:
        return Validadores(etag='"v1"', last_modified="Sat, 01 Nov 2026 00:00:00 GMT")


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


def _texto(arquivo: str) -> str:
    return (PASTA / arquivo).read_text(encoding="utf-8")


def _xml(corpo: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=corpo, headers={"Content-Type": "application/xml"})


def _html(corpo: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=corpo, headers={"Content-Type": "text/html"})


def _sitemap(*entradas: tuple[str, str | None]) -> str:
    urls = "".join(
        f"<url><loc>{loc}</loc>" + (f"<lastmod>{data}</lastmod>" if data else "") + "</url>"
        for loc, data in entradas
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="{NS}">{urls}</urlset>'


def _pagina(vaga: str, *, args: str = '"Empresa X",null', params: str = "a,b") -> str:
    """Página com `window.__NUXT__` na forma do site: função com variáveis e argumentos."""
    estado = f"state:{{candidate:{{vacancy:{{vacancy:{vaga}}}}}}}"
    script = f"window.__NUXT__=(function({params}){{return {{{estado}}}}}({args}));"
    return (
        f"<!DOCTYPE html><html><body><div id=__nuxt></div><script>{script}</script></body></html>"
    )


async def _rodar(
    respostas: list[httpx.Response | Responder],
    acao: Callable[[HttpEducado], object],
    *,
    leitor: LeitorValidadores | None = None,
    condicional: bool = True,
) -> tuple[object, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []
    fila = list(respostas)

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return r if isinstance(r, httpx.Response) else r(pedido)

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(
        httpx.MockTransport(servidor), relogio, leitor or LeitorFixo(), "0.1.0", _sem_dns
    )
    try:
        http: HttpEducado = cli.escopo(espera_s=abler.COLETOR.espera_s, condicional=condicional)
        resultado = await acao(http)  # type: ignore[misc]
    finally:
        await cli.fechar()
    return resultado, pedidos


async def _coletar(
    *respostas: httpx.Response | Responder,
    leitor: LeitorValidadores | None = None,
    condicional: bool = True,
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    resultado, pedidos = await _rodar(
        list(respostas),
        lambda http: abler.COLETOR.coletar("", http),
        leitor=leitor,
        condicional=condicional,
    )
    assert isinstance(resultado, ResultadoEscopo)
    return resultado, pedidos


async def _detalhar(
    *respostas: httpx.Response | Responder, url: str = VAGA
) -> tuple[VagaColetada | None, list[httpx.Request]]:
    item = UrlListada(url, datetime(2026, 11, 13, 20, 24, 24, tzinfo=UTC))
    resultado, pedidos = await _rodar(
        list(respostas), lambda http: abler.COLETOR.detalhar(item, http)
    )
    assert resultado is None or isinstance(resultado, VagaColetada)
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    """Qualquer pedido é erro do teste."""

    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não faz pedido: {pedido.url}")

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(httpx.MockTransport(recusa), relogio, LeitorFixo(), "0.1.0", _sem_dns)
    try:
        yield cli.escopo()
    finally:
        await cli.fechar()


def _urls(resultado: ResultadoEscopo) -> list[UrlListada]:
    urls = [v for v in resultado.vagas if isinstance(v, UrlListada)]
    assert len(urls) == len(resultado.vagas)
    return urls


# ---- contrato e escopos --------------------------------------------------------------------


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = abler.COLETOR
    assert registro.descobrir()["abler"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "B"
    assert prova.intervalo_min == limites.intervalo_min
    assert prova.max_pedidos == limites.max_pedidos
    assert prova.espera_s == limites.espera_s == 2.0  # DP7
    assert prova.credito_obrigatorio is False
    assert prova.hosts == ("candidatos.abler.com.br",)


def test_escopo_unico() -> None:
    empresas = [Empresa(nome="X", fonte="abler", identificador="x")]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(abler.COLETOR.escopos(ctx)) == [""]


async def test_resolver_recusa_tudo_e_nao_faz_pedido(http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await abler.COLETOR.resolver("https://candidatos.abler.com.br/vagas/x-1", http_proibido)


# ---- coletar: o sitemap --------------------------------------------------------------------


async def test_normal() -> None:
    resultado, _ = await _coletar(_xml(_texto("normal.xml")))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    urls = _urls(resultado)
    # a primeira <url> do sitemap é a página da lista (/vagas/), não uma vaga: fica de fora
    assert [u.url for u in urls] == [
        "https://candidatos.abler.com.br/vagas/00072-auxiliar-operacional-654143",
        "https://candidatos.abler.com.br/vagas/001-analista-de-dp-3621",
        "https://candidatos.abler.com.br/vagas/001-assistente-de-dp-756928",
        "https://candidatos.abler.com.br/vagas/001-auxiliar-administrativo-oportunidade-exclusiva-pcd-463026",
    ]
    assert urls[0].atualizada_em == datetime(2026, 10, 29, 8, 2, 35, tzinfo=UTC)
    # sem filtro de data: a de agosto sai também (o filtro de 30 dias é do executor, T16)
    assert urls[3].atualizada_em == datetime(2026, 8, 12, 12, 33, 48, tzinfo=UTC)


async def test_vazio() -> None:
    resultado, _ = await _coletar(_xml(_texto("vazio.xml")))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_xml(_texto("formato_mudou.xml")))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


@pytest.mark.parametrize(
    "corpo",
    ["<html><body>manutenção</body></html>", "não é xml", "", "<urlset><url>"],
)
async def test_resposta_que_nao_e_sitemap_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(_xml(corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_url_sem_loc_e_pulada_e_deixa_parcial() -> None:
    boa = "https://candidatos.abler.com.br/vagas/dev-1"
    corpo = _sitemap((boa, "2026-11-13T20:22:08+00:00")).replace(
        "</urlset>",
        "<url><lastmod>2026-11-13T20:22:08+00:00</lastmod></url><url><loc> </loc></url></urlset>",
    )
    resultado, _ = await _coletar(_xml(corpo))
    assert [u.url for u in _urls(resultado)] == [boa]
    # nunca "ok": "ok" fecharia a vaga que ficou de fora
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")


@pytest.mark.parametrize(
    "entradas",
    [
        "<url><lastmod>2026-11-13T20:22:08+00:00</lastmod></url>",
        "<url><loc> </loc></url><url></url>",
        # a página da lista não é vaga: sobra só a <url> sem <loc>
        "<url><loc>https://candidatos.abler.com.br/vagas</loc></url><url><loc></loc></url>",
    ],
)
async def test_abler_sitemap_sem_loc_falhou(entradas: str) -> None:
    # nenhuma <url> deu vaga: "parcial" vazio deixaria o escopo como se a lista tivesse saído
    corpo = _sitemap().replace("</urlset>", entradas + "</urlset>")
    resultado, _ = await _coletar(_xml(corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_url_de_host_local_e_pulada_e_contada() -> None:
    # decisão 19: a UrlListada recusa host local; o item é pulado e conta como sem detalhe
    boa = "https://candidatos.abler.com.br/vagas/dev-1"
    corpo = _sitemap(("http://127.0.0.1/x", "2026-11-13T20:22:08+00:00"), (boa, None))
    resultado, pedidos = await _coletar(_xml(corpo))
    assert [u.url for u in _urls(resultado)] == [boa]
    assert (resultado.estado, resultado.motivo) == ("ok", "saude.sem_detalhe_n:1")
    assert [str(p.url) for p in pedidos] == [SITEMAP]  # nenhum pedido à local


async def test_url_de_outro_lugar_e_pulada_e_contada() -> None:
    boa = "https://candidatos.abler.com.br/vagas/dev-1"
    corpo = _sitemap(
        ("https://outro.exemplo.com/vagas/dev-2", None),
        ("javascript:alert(1)", None),
        ("https://candidatos.abler.com.br/empresas/x-3", None),
        ("https://candidatos.abler.com.br/vagas/dev-4/candidatar", None),
        ("https://candidatos.abler.com.br/vagas/dev-5?x=1", None),
        ("https://user@candidatos.abler.com.br/vagas/dev-6", None),
        (boa, None),
    )
    resultado, _ = await _coletar(_xml(corpo))
    assert [u.url for u in _urls(resultado)] == [boa]
    assert (resultado.estado, resultado.motivo) == ("ok", "saude.sem_detalhe_n:6")


async def test_sitemap_so_com_urls_recusadas_falhou() -> None:
    # "ok" vazio fecharia todas as vagas da fonte: se nenhuma <url> vira vaga, o formato mudou
    corpo = _sitemap(
        ("https://candidatos.abler.com.br/empresas/x", None),
        ("https://candidatos.abler.com.br/empresas/y", None),
        ("https://candidatos.abler.com.br/vagas/dev-1?x=1", None),
    )
    resultado, _ = await _coletar(_xml(corpo))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == (
        (),
        "falhou",
        "saude.formato_mudou",
    )


@pytest.mark.parametrize(
    ("lastmod", "esperado"),
    [
        ("2026-11-13T20:22:08+00:00", datetime(2026, 11, 13, 20, 22, 8, tzinfo=UTC)),
        (
            "2026-11-13T17:22:08-03:00",
            datetime(2026, 11, 13, 17, 22, 8, tzinfo=timezone(timedelta(hours=-3))),
        ),
        ("2026-11-13", datetime(2026, 11, 13, tzinfo=UTC)),  # só a data: meia-noite UTC
        ("2026-11-13T20:22:08", datetime(2026, 11, 13, 20, 22, 8, tzinfo=UTC)),  # sem fuso
        ("ontem", None),
        (None, None),
    ],
)
async def test_lastmod(lastmod: str | None, esperado: datetime | None) -> None:
    corpo = _sitemap(("https://candidatos.abler.com.br/vagas/dev-1", lastmod))
    resultado, _ = await _coletar(_xml(corpo))
    assert resultado.estado == "ok"
    assert _urls(resultado)[0].atualizada_em == esperado


async def test_sitemap_inteiro_de_14_mil_urls_dentro_do_teto() -> None:
    # 3,6 MB como o real: cabe no teto de 5 MB e sai inteiro, com as antigas também
    entrada = (
        "<url><loc>https://candidatos.abler.com.br/vagas/auxiliar-de-servicos-gerais-com-experiencia-em-limpeza-e-conservacao-{n}</loc>"
        "<lastmod>{ano}-10-29T08:02:35+00:00</lastmod><changefreq>weekly</changefreq>"
        "<priority>0.70</priority></url>\n"
    )
    urls = "".join(
        "        " + entrada.format(n=n, ano=2022 if n % 2 else 2026) for n in range(14292)
    )
    corpo = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="{NS}">\n{urls}</urlset>'
    assert 3_400_000 < len(corpo.encode()) < 5 * 1024 * 1024
    resultado, pedidos = await _coletar(_xml(corpo))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert len(_urls(resultado)) == 14292
    assert len(pedidos) == 1


async def test_429_e_erro_de_rede() -> None:
    resultado, _ = await _coletar(httpx.Response(429))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.limite_atingido"
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
    _, pedidos = await _coletar(_xml(_texto("vazio.xml")))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert str(pedido.url) == SITEMAP
    assert pedido.headers["User-Agent"].startswith("joBot/")
    for nome in ("Cookie", "Origin", "Referer", "Authorization"):
        assert nome not in pedido.headers


async def test_sem_validador_na_resposta_nunca_e_304() -> None:
    # a captura não mostrou ETag nem Last-Modified no sitemap: o coletor não pede condicional e
    # nunca devolve SEM_MUDANCA. O leitor guarda um ETag e o servidor responde 304 a quem o
    # mandar: pedir condicional deixa o teste vermelho.
    def servidor(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") or pedido.headers.get("If-Modified-Since"):
            return httpx.Response(304)
        return _xml(_texto("normal.xml"))

    resultado, pedidos = await _coletar(servidor, leitor=LeitorComEtag(), condicional=True)
    assert resultado.estado == "ok" and resultado.vagas
    assert resultado.vagas is not SEM_MUDANCA
    assert pedidos[0].headers.get("If-None-Match") is None
    assert pedidos[0].headers.get("If-Modified-Since") is None


# ---- detalhar: window.__NUXT__ lido como texto ---------------------------------------------


async def test_detalhar_normal() -> None:
    vaga, pedidos = await _detalhar(_html(_texto("vaga.html")))
    assert vaga is not None
    assert vaga.fonte == "abler" and vaga.escopo == ""
    assert vaga.url == VAGA  # a URL do sitemap é a chave (a ocorrência casa com ela)
    assert vaga.titulo == "Estágio em RH (Recrutamento e Seleção)"
    assert vaga.empresa == "GC Talentos"
    assert vaga.id_externo == "404752"
    assert vaga.locais == ("Curitiba, PR",)
    assert vaga.modalidade_declarada == "hibrida"
    assert vaga.contrato_declarado == "estagiario"
    assert vaga.salario_estruturado == SalarioBruto(
        moeda="BRL", minimo_unidades=1200, maximo_unidades=1200
    )
    assert vaga.publicada_em == datetime(
        2026, 11, 13, 17, 24, 6, 914000, tzinfo=timezone(timedelta(hours=-3))
    )
    assert vaga.prazo is None  # closeOn: void 0
    assert vaga.etiquetas == ("Estagiário",)
    assert vaga.descricao_formato == "html"
    assert "<ul><li> Apoiar nos processos de recrutamento" in vaga.descricao
    assert "Cursando Superior em Recursos Humanos." in vaga.descricao  # mandatoryRequirements
    # description e roleDescription vêm iguais: o texto entra uma vez só
    assert vaga.descricao.count("Apoiar nos processos de recrutamento") == 1
    assert vaga.url_candidatura is None
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert (pedido.method, str(pedido.url)) == ("GET", VAGA)
    for nome in ("Cookie", "Origin", "Referer", "Authorization", "If-None-Match"):
        assert nome not in pedido.headers


async def test_nenhum_pedido_a_hulk_smash() -> None:
    # a página traz `apiBaseURL` da API hulk-smash; o coletor nunca a chama (recusa por origem)
    pagina = _texto("vaga.html")
    assert "hulk-smash.abler.com.br" in pagina
    _, pedidos_lista = await _coletar(_xml(_texto("normal.xml")))
    _, pedidos_vaga = await _detalhar(_html(pagina))
    hosts = {p.url.host for p in pedidos_lista + pedidos_vaga}
    assert hosts == {"candidatos.abler.com.br"}


async def test_cookie_da_pagina_nao_volta() -> None:
    resposta = _html(_texto("vaga.html"))
    resposta.headers["Set-Cookie"] = "__pgt=abc; Path=/"
    pedidos: list[httpx.Request] = []

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return resposta

    async def dois(http: HttpEducado) -> None:
        for _ in range(2):
            await abler.COLETOR.detalhar(UrlListada(VAGA), http)

    await _rodar([servidor], dois)
    assert len(pedidos) == 2
    assert all("Cookie" not in p.headers for p in pedidos)


async def test_variaveis_e_escapes_do_empacotador() -> None:
    vaga, _ = await _detalhar(
        _html(
            _pagina(
                r'{id:"7",title:"Dev/Ops \"Sr\" \x41 \u{1F600} 😀",'
                r"companyName:a,cityAndState:'Rio - RJ',salaryValue:b,workTypes:[{id:c}]}",
                args='"Empresa X",3500.5,"remota"',
                params="a,b,c",
            )
        )
    )
    assert vaga is not None
    assert vaga.titulo == 'Dev/Ops "Sr" A \U0001f600 \U0001f600'
    assert vaga.empresa == "Empresa X"
    assert vaga.id_externo == "7"
    assert vaga.locais == ("Rio - RJ",)
    assert vaga.modalidade_declarada == "remota"
    assert vaga.salario_estruturado == SalarioBruto(
        moeda="BRL", minimo_unidades=3500.5, maximo_unidades=3500.5
    )


async def test_estado_sem_funcao_tambem_e_lido() -> None:
    estado = '{state:{candidate:{vacancy:{vacancy:{title:"Dev","companyName":"Y"}}}}}'
    pagina = f"<html><body><script>window.__NUXT__={estado};</script></body></html>"
    vaga, _ = await _detalhar(_html(pagina))
    assert vaga is not None and (vaga.titulo, vaga.empresa) == ("Dev", "Y")


async def test_campo_que_precisaria_executar_sai_sem_ele() -> None:
    # nada é executado: valor que é chamada, conta ou `new` fica de fora, e a vaga sai sem ele
    vaga, _ = await _detalhar(
        _html(
            _pagina(
                '{title:"Dev",companyName:"Y",salaryValue:Math.max(1,b),'
                'publishedAt:new Date("2026-01-01"),closeOn:a+"x",'
                'description:"<p>ok, {x}</p>",levelOfInterests:[{name:(function(){return 1})()}]}'
            )
        )
    )
    assert vaga is not None
    assert (vaga.titulo, vaga.empresa) == ("Dev", "Y")
    assert vaga.salario_estruturado is None
    assert vaga.publicada_em is None
    assert vaga.prazo is None
    assert vaga.descricao == "<p>ok, {x}</p>"
    assert vaga.etiquetas == ()


@pytest.mark.parametrize(
    "vaga",
    [
        '{companyName:"Y"}',
        '{title:"Dev"}',
        '{title:"  ",companyName:"Y"}',
        '{title:"Dev",companyName:void 0}',
        '{title:"Dev",companyName:b}',  # b é null
        '{title:"Dev",companyName:a+b}',  # precisaria executar
        '{title:"Dev",companyName:z}',  # variável que não existe
        '{title:1,companyName:"Y"}',
        "a",  # vacancy é a string "Empresa X", não objeto
        "b",  # vacancy null: vaga removida
    ],
)
async def test_detalhe_sem_titulo_ou_empresa_e_none(vaga: str) -> None:
    resultado, _ = await _detalhar(_html(_pagina(vaga)))
    assert resultado is None


@pytest.mark.parametrize(
    "pagina",
    [
        "<html><body>sem estado</body></html>",
        "<html><body><script>window.__NUXT__=(function(a){return {state:{}}}(1));</script>",
        "<html><body><script>window.__NUXT__=(function(a){return {state:{candidate:",
        "<html><body><script>window.__NUXT__=JSON.parse('{}');</script>",
        "<script>window.__NUXT__=(function(a){return {state:{candidate:{vacancy:{vacancy:"
        + "[" * 5000
        + "]" * 5000
        + "}}}}}(1));</script>",
        # prefixos unários encadeados também param no limite de fundo
        "<script>window.__NUXT__=(function(a){return {state:{candidate:{vacancy:{vacancy:"
        + "!" * 5000
        + "0}}}}}(1));</script>",
        "<script>window.__NUXT__=(function(a){return {state:{candidate:{vacancy:{vacancy:"
        + "void " * 5000
        + "0}}}}}(1));</script>",
    ],
)
async def test_pagina_sem_estado_legivel_e_none_sem_excecao(pagina: str) -> None:
    resultado, _ = await _detalhar(_html(pagina))
    assert resultado is None


@pytest.mark.parametrize(
    ("campo", "esperado"),
    [
        ("salaryValue:0", None),
        ("salaryValue:!0", None),
        ("salaryValue:-5", None),
        ("salaryValue:1e400", None),
        ('salaryValue:"1200"', None),
        ("salaryValue:1200,initialSalaryRange:1000,finalSalaryRange:2000", (1000, 2000)),
        ("initialSalaryRange:1000", (1000, None)),
    ],
)
async def test_salario(campo: str, esperado: tuple[int, int | None] | None) -> None:
    vaga, _ = await _detalhar(_html(_pagina(f'{{title:"Dev",companyName:"Y",{campo}}}')))
    assert vaga is not None
    if esperado is None:
        assert vaga.salario_estruturado is None
    else:
        assert vaga.salario_estruturado == SalarioBruto(
            moeda="BRL", minimo_unidades=esperado[0], maximo_unidades=esperado[1]
        )


async def test_campos_opcionais() -> None:
    vaga, _ = await _detalhar(
        _html(
            _pagina(
                '{title:"Dev",companyName:"Y",closeOn:"2026-12-01",workTypes:[{id:"hibrida"},'
                '{id:"remota"}],address:{cityName:"",stateAbbr:"SP"},cityAndState:"Santos - SP",'
                'levelOfInterests:[{name:"Júnior"},{name:"Júnior"},{name:7},"x"],id:!1,'
                'contractingRegime:"clt",publishedAt:"amanhã"}'
            )
        )
    )
    assert vaga is not None
    assert vaga.prazo is not None and vaga.prazo.isoformat() == "2026-12-01"
    assert vaga.modalidade_declarada is None  # duas modalidades: não escolhe
    assert vaga.locais == ("Santos - SP",)  # sem cidade no endereço: o texto da fonte
    assert vaga.etiquetas == ("Júnior",)
    assert vaga.id_externo is None  # booleano não é id
    assert vaga.contrato_declarado == "clt"
    assert vaga.publicada_em is None


async def test_detalhar_404_e_none() -> None:
    vaga, pedidos = await _detalhar(httpx.Response(404))
    assert vaga is None
    assert len(pedidos) == 1


async def test_detalhar_bloqueio_sobe() -> None:
    # 403 para os detalhes da fonte nesta execução (o executor trata `Bloqueio`)
    with pytest.raises(Bloqueio):
        await _detalhar(httpx.Response(403))


@pytest.mark.parametrize(
    "url",
    [
        "https://outro.exemplo.com/vagas/dev-1",
        "https://candidatos.abler.com.br/empresas/dev-1",
        "https://hulk-smash.abler.com.br/api/candidate/v2/vacancies",
    ],
)
async def test_detalhar_url_estranha_nao_faz_pedido(url: str, http_proibido: HttpEducado) -> None:
    assert await abler.COLETOR.detalhar(UrlListada(url), http_proibido) is None


async def test_detalhar_vaga_coletada_nao_faz_pedido(http_proibido: HttpEducado) -> None:
    vaga = VagaColetada(
        fonte="abler", escopo="", url=VAGA, titulo="x", empresa="y", descricao_formato="html"
    )
    assert await abler.COLETOR.detalhar(vaga, http_proibido) is None
