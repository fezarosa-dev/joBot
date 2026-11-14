import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, quickin, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

RAIZ = Path(__file__).resolve().parents[3]
PASTA = RAIZ / "tests" / "fixtures" / "quickin"
CONTA = "626fd30298767e001a4efe9c"
EMPRESA = f"{CONTA}:Connect For People"
API = f"https://api.quickin.io/public/{CONTA}/jobs"
URL_PAGINA_1 = f"{API}?sort=-created_at&page=1"
URL_PAGINA_2 = f"{API}?sort=-created_at&page=2"
PAGINA_DA_EMPRESA = "https://jobs.quickin.io/connectforpeople/jobs"
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
        resultado = await quickin.COLETOR.coletar(escopo, http)
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
        resolvido = await quickin.COLETOR.resolver(entrada, cli.escopo())
    finally:
        await cli.fechar()
    return dict(resolvido), pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _vaga_falsa(n: int) -> dict[str, Any]:
    return {
        "_id": f"{n:024x}",
        "publicate": "published",
        "title": f"Vaga {n}",
        "description": "<p>Texto.</p>",
        "requirements": "",
        "city": "Recife",
        "region": "PE",
        "country": "BR",
        "workplace_type": "remote",
        "created_at": "2026-11-13T18:15:25.334Z",
        "career_url": f"https://jobs.quickin.io/connectforpeople/jobs/{n:024x}",
    }


def _pagina(
    numero: int, quantos: int, *, pages: int | None = 3, limite: int = 30
) -> httpx.Response:
    inicio = (numero - 1) * limite
    corpo: dict[str, Any] = {
        "docs": [_vaga_falsa(n) for n in range(inicio, inicio + quantos)],
        "total": 85,
        "limit": limite,
        "page": numero,
    }
    if pages is not None:
        corpo["pages"] = pages
    return httpx.Response(200, json=corpo)


def _numero_da_pagina(pedido: httpx.Request) -> int:
    return int(pedido.url.params["page"])


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = quickin.COLETOR
    assert registro.descobrir()["quickin"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "B"
    assert (prova.intervalo_min, prova.max_pedidos, prova.espera_s) == (None, None, 1.0)
    assert prova.hosts == ("api.quickin.io",)


def test_escopos_um_por_empresa_com_a_conta_e_o_nome() -> None:
    empresas = [
        Empresa(
            nome="Connect For People",
            fonte="quickin",
            identificador="connectforpeople",
            parametros={"account_id": CONTA},
        ),
        Empresa(
            nome="Quickin",
            fonte="quickin",
            identificador="quickin",
            parametros={"account_id": " 686d6f9812b3d7001359e95c "},
        ),
        Empresa(
            nome="Connect de novo",
            fonte="quickin",
            identificador="connectforpeople",
            parametros={"account_id": CONTA},
        ),
    ]
    ctx = ContextoColeta(empresas=empresas, termos=["dev"], paises=["BR"])
    assert list(quickin.COLETOR.escopos(ctx)) == [
        f"{CONTA}:Connect For People",
        "686d6f9812b3d7001359e95c:Quickin",
    ]


def test_empresa_sem_account_id_valido_nao_vira_escopo() -> None:
    # o coletor nunca adivinha a conta: o slug no lugar do account_id dá 400 na API
    ruins: list[dict[str, str]] = [{}, {"account_id": ""}, {"account_id": "quickin"}]
    ruins += [
        {"account_id": CONTA[:-1]},
        {"account_id": CONTA.upper()},
        {"account_id": CONTA + "0"},
    ]
    empresas = [
        Empresa(nome="Ruim", fonte="quickin", identificador=f"x{i}", parametros=p)
        for i, p in enumerate(ruins)
    ]
    empresas.append(
        Empresa(nome="  ", fonte="quickin", identificador="boa", parametros={"account_id": CONTA})
    )
    ctx = ContextoColeta(empresas=empresas, termos=[], paises=[])
    assert list(quickin.COLETOR.escopos(ctx)) == [f"{CONTA}:boa"]  # sem nome, o identificador


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira, cliente = vagas[0], vagas[4]
    assert primeira.fonte == "quickin" and primeira.escopo == EMPRESA
    assert primeira.url == "https://jobs.quickin.io/connectforpeople/jobs/6af45e2055094e0013d581d3"
    assert primeira.id_externo == "6af45e2055094e0013d581d3"
    assert primeira.titulo == "Gestora Administrativa e Operacional de Clínica Médica"
    assert primeira.empresa == "Connect For People"  # company_id ausente: o nome do cadastro
    assert primeira.descricao_formato == "html"
    assert primeira.descricao.startswith("<p>Na Connect For People, acreditamos")
    assert "Ensino superior completo" in primeira.descricao  # requirements junto
    assert primeira.locais == ("Barreiras, Bahia, BR",)
    assert primeira.modalidade_declarada == "on-site"
    assert primeira.contrato_declarado == "CLT"
    assert primeira.publicada_em == datetime(2026, 11, 11, 12, 22, 56, 448000, tzinfo=UTC)
    assert primeira.etiquetas == ("administrative",)
    assert primeira.url_candidatura is None and primeira.prazo is None
    assert primeira.salario_estruturado is None and primeira.salario_texto is None
    assert cliente.empresa == "Tebinka"  # company_id.name: a vaga é de um cliente da conta
    assert cliente.contrato_declarado is None
    assert vagas[1].descricao.endswith(
        "Premia&ccedil;&otilde;es e plano de patentes.</p>"
    )  # benefits no fim
    assert all(v.url.startswith("https://") for v in vagas)
    assert len(pedidos) == 1


async def test_descricao_junta_description_requirements_e_benefits_nesta_ordem() -> None:
    dados = json.loads(_texto("normal"))
    dados["docs"][0] |= {
        "description": "<p>D</p>",
        "requirements": "<p>R</p>",
        "benefits": "<p>B</p>",
    }
    dados["docs"][1] |= {"description": "<p>D</p>", "requirements": None, "benefits": 7}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    vagas = _vagas(resultado)
    assert vagas[0].descricao.replace("\n", "") == "<p>D</p><p>R</p><p>B</p>"
    assert vagas[1].descricao == "<p>D</p>"


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1  # pages 0 e docs vazio: não pede a página 2


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    # a segunda vaga perdeu o title e a terceira o career_url: ficam as outras três
    assert [v.id_externo for v in _vagas(resultado)] == [
        "6af45e2055094e0013d581d3",
        "6ad60ff5de9944001354c7b4",
        "6ac9a9f3d484c700134585c3",
    ]


@pytest.mark.parametrize(
    "corpo",
    ['{"results": []}', "[]", '{"docs": {}}', "isto não é json", '{"docs": [1, "x"]}'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = json.loads(_texto("normal"))
    dados["docs"][0] |= {
        "created_at": "2026-11-13T18:15:25",  # sem fuso
        "city": None,
        "region": 7,
        "country": None,
        "description": None,
        "requirements": None,
        "benefits": None,
        "workplace_type": None,
        "contract_id": "CLT",
        "company_id": ["Tebinka"],
        "position_category": 3,
        "remuneration": "muito",
        "currency": 9,
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.locais, vaga.descricao) == (None, (), "")
    assert (vaga.modalidade_declarada, vaga.contrato_declarado, vaga.etiquetas) == (None, None, ())
    assert (vaga.empresa, vaga.salario_estruturado) == ("Connect For People", None)


async def test_url_fora_de_http_pula_a_vaga() -> None:
    dados = json.loads(_texto("normal"))
    dados["docs"][1]["career_url"] = "javascript:alert(1)"
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 4


async def test_remuneration_vira_salario_estruturado() -> None:
    dados = json.loads(_texto("normal"))
    dados["docs"][0] |= {"remuneration": 3500, "currency": "BRL", "remuneration_period": "month"}
    dados["docs"][1] |= {"remuneration": 25.5, "currency": "BRL", "remuneration_period": "hour"}
    dados["docs"][2] |= {"remuneration": 3500, "currency": None, "remuneration_period": None}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    vagas = _vagas(resultado)
    assert vagas[0].salario_estruturado == SalarioBruto(
        moeda="BRL", minimo_unidades=3500, maximo_unidades=3500, periodo="mes"
    )
    assert vagas[1].salario_estruturado == SalarioBruto(
        moeda="BRL", minimo_unidades=25.5, maximo_unidades=25.5, periodo="hora"
    )
    assert vagas[2].salario_estruturado == SalarioBruto(
        moeda=None, minimo_unidades=3500, maximo_unidades=3500, periodo=None
    )
    assert vagas[3].salario_estruturado is None  # remuneration ausente (null na captura)


@pytest.mark.parametrize(
    "valor", [0, -1, True, "3500", None, float("inf"), 10**400, [3500], {"valor": 3500}]
)
async def test_remuneration_sem_numero_valido_nao_vira_salario(valor: object) -> None:
    dados = json.loads(_texto("normal"))
    dados["docs"][0] |= {"remuneration": valor, "currency": "BRL", "remuneration_period": "month"}
    corpo = json.dumps(dados).replace("Infinity", "1e999")  # json.dumps aceita inf; a rede, não
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].salario_estruturado is None


@pytest.mark.parametrize(
    ("periodo", "esperado"),
    [
        ("hour", "hora"),
        ("day", "dia"),
        ("week", "semana"),
        ("month", "mes"),
        ("year", "ano"),
        ("quinzena", None),
        (None, None),
    ],
)
async def test_periodo_da_remuneracao(periodo: str | None, esperado: str | None) -> None:
    dados = json.loads(_texto("normal"))
    dados["docs"][0] |= {"remuneration": 10, "currency": "BRL", "remuneration_period": periodo}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    bruto = _vagas(resultado)[0].salario_estruturado
    assert bruto is not None and bruto.periodo == esperado


async def test_paginacao_avanca_ate_pages_de_30_em_30() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = _numero_da_pagina(pedido)
        return _pagina(n, 30 if n < 3 else 25)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 3)
    assert [p.url.params["page"] for p in pedidos] == ["1", "2", "3"]
    assert len(resultado.vagas) == 85
    assert len({v.id_externo for v in _vagas(resultado)}) == 85  # id distinto por página


async def test_paginacao_para_em_pages_mesmo_com_pagina_cheia() -> None:
    # 60 vagas, pages 2: a página 2 está cheia e não há terceira
    def pagina(pedido: httpx.Request) -> httpx.Response:
        return _pagina(_numero_da_pagina(pedido), 30, pages=2)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 60, 2)


async def test_paginacao_para_na_pagina_vazia_com_pages_absurdo() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = _numero_da_pagina(pedido)
        return _pagina(n, 30 if n == 1 else 0, pages=10**9)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 30, 2)


@pytest.mark.parametrize("pages", [None, "3", True, 0, -1, 2.5])
async def test_paginacao_sem_pages_valido_para_na_pagina_menor_que_limit(pages: object) -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = _numero_da_pagina(pedido)
        resposta = _pagina(n, 30 if n < 3 else 10, pages=None)
        corpo = json.loads(resposta.text)
        if pages is not None:
            corpo["pages"] = pages
        return httpx.Response(200, json=corpo)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 70, 3)


async def test_paginacao_segue_o_limit_da_resposta() -> None:
    # a API devolveu páginas de 20 mesmo sem `limit` pedido: 20 não é "menor que limit"
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = _numero_da_pagina(pedido)
        return _pagina(n, 20 if n < 3 else 5, pages=None, limite=20)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 45, 3)


async def test_pagina_seguinte_ilegivel_deixa_parcial_com_as_vagas_lidas() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = _numero_da_pagina(pedido)
        return _pagina(n, 30) if n == 1 else httpx.Response(200, text="não é json")

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert (len(resultado.vagas), len(pedidos)) == (30, 2)


@pytest.mark.parametrize("status", [400, 404])
async def test_404_ou_400_na_pagina_seguinte_deixa_parcial_com_as_vagas_lidas(status: int) -> None:
    # só na página 1 o 400/404 quer dizer "conta não encontrada": depois, o lido vale
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = _numero_da_pagina(pedido)
        return _pagina(n, 30) if n == 1 else httpx.Response(status, text="{}")

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert (len(resultado.vagas), len(pedidos)) == (30, 2)


async def test_teto_de_paginas_deixa_parcial_e_nao_pendura() -> None:
    # pages absurdo e páginas cheias sem fim: o teto local é quem para (nunca "ok")
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = _numero_da_pagina(pedido)
        assert n <= quickin._MAX_PAGINAS, "passou do teto de páginas"
        return _pagina(n, 30, pages=10**6)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert (resultado.pedidos, len(pedidos)) == (quickin._MAX_PAGINAS, quickin._MAX_PAGINAS)
    assert len(resultado.vagas) == 30 * quickin._MAX_PAGINAS


async def test_orcamento_de_pedidos_deixa_no_limite_e_nao_perde_o_lido() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        return _pagina(_numero_da_pagina(pedido), 30, pages=10**6)

    resultado, pedidos = await _coletar(pagina, max_pedidos=3)
    assert (resultado.estado, resultado.motivo) == ("no_limite", "saude.orcamento")
    assert (resultado.pedidos, len(pedidos), len(resultado.vagas)) == (3, 3, 90)


async def test_404_ou_400_conta_nao_encontrada() -> None:
    # o slug no lugar do account_id dá 400 (captura de 2026-11-13); a conta apagada, 404
    for status in (400, 404):
        resultado, pedidos = await _coletar(httpx.Response(status, text=_texto("nao_encontrado")))
        assert (resultado.vagas, resultado.estado) == ((), "falhou")
        assert resultado.motivo == "saude.empresa_nao_encontrada"
        assert len(pedidos) == 1


async def test_nao_encontrado_da_captura_real() -> None:
    resultado, _ = await _coletar(_json("nao_encontrado", status=400))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.empresa_nao_encontrada")


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

    monkeypatch.setattr(quickin, "juntar_paginas", espia)
    etag = 'W/"19f8a-8RLFu+Wl86e6OxAvEWPJVFYLjGE"'

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _json("normal", ETag=etag)

    leitor = LeitorFixo({URL_PAGINA_1: Validadores(etag, None)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-None-Match") for p in pedidos] == [etag]
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_so_a_primeira_pagina_leva_pedido_condicional() -> None:
    etag = '"x"'
    leitor = LeitorFixo(
        {URL_PAGINA_1: Validadores(etag, None), URL_PAGINA_2: Validadores(etag, None)}
    )

    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = _numero_da_pagina(pedido)
        return _pagina(n, 30 if n == 1 else 5, pages=2)

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
    assert str(pedido.url) == URL_PAGINA_1
    assert dict(pedido.url.params) == {"sort": "-created_at", "page": "1"}
    for nome in ("origin", "cookie", "authorization", "referer"):
        assert nome not in pedido.headers


async def test_nome_com_dois_pontos_nao_confunde_a_conta() -> None:
    resultado, pedidos = await _coletar(_json("vazio"), escopo=f"{CONTA}:A: B")
    assert resultado.estado == "ok"
    assert pedidos[0].url.path == f"/public/{CONTA}/jobs"
    dados = json.loads(_texto("normal"))
    for doc in dados["docs"]:
        doc.pop("company_id", None)
    resultado, _ = await _coletar(httpx.Response(200, json=dados), escopo=f"{CONTA}:A: B")
    assert {v.empresa for v in _vagas(resultado)} == {"A: B"}


@pytest.mark.parametrize(
    "escopo",
    [
        "",
        CONTA,
        f"{CONTA}:",
        f"{CONTA}:   ",
        f":{CONTA}",
        "quickin:Quickin",
        f"{CONTA[:-1]}:Quickin",
        f"{CONTA.upper()}:Quickin",
        f"../{CONTA}:Quickin",
    ],
)
async def test_escopo_que_nao_e_do_coletor_levanta_sem_pedido(escopo: str) -> None:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"escopo inválido não faz pedido: {pedido.url}")

    with pytest.raises(ValueError):
        await _coletar(recusa, escopo=escopo)


async def test_detalhar_nao_faz_nada_porque_a_lista_ja_traz_a_descricao() -> None:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"detalhar não faz pedido: {pedido.url}")

    cli = ClienteEducado(
        httpx.MockTransport(recusa), RelogioFalso(), LeitorFixo(), "0.1.0", _sem_dns
    )
    try:
        vaga = VagaColetada(
            fonte="quickin", escopo=EMPRESA, url="https://jobs.quickin.io/a/jobs/1", titulo="T",
            empresa="E", descricao_formato="html",
        )  # fmt: skip
        assert await quickin.COLETOR.detalhar(vaga, cli.escopo()) is None
    finally:
        await cli.fechar()


@pytest.mark.parametrize(
    "entrada",
    [
        "connectforpeople",
        " connectforpeople ",
        "jobs.quickin.io/connectforpeople",
        "https://jobs.quickin.io/connectforpeople/jobs",
        "https://jobs.quickin.io/connectforpeople",
        "https://jobs.quickin.io/connectforpeople/",
        "http://JOBS.quickin.io/connectforpeople/jobs/6af45e2055094e0013d581d3",
        "https://jobs.quickin.io/connectforpeople/apply?job_id=6af45e2055094e0013d581d3",
    ],
)
async def test_resolver_le_o_account_id_do_nuxt_data(entrada: str) -> None:
    pagina = httpx.Response(200, text=_texto("pagina_empresa", "html"))
    resolvido, pedidos = await _resolver(entrada, pagina)
    assert resolvido == {"identificador": "connectforpeople", "account_id": CONTA}
    assert [(p.method, str(p.url)) for p in pedidos] == [("GET", PAGINA_DA_EMPRESA)]


async def test_resolver_guarda_a_caixa_do_slug_e_confere_com_a_pagina() -> None:
    # a página diz `connectforpeople`; um slug digitado em outra caixa é o mesmo site
    pagina = httpx.Response(200, text=_texto("pagina_empresa", "html"))
    resolvido, pedidos = await _resolver("ConnectForPeople", pagina)
    assert resolvido["identificador"] == "connectforpeople"
    assert str(pedidos[0].url) == "https://jobs.quickin.io/ConnectForPeople/jobs"


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "   ",
        "https://jobs.quickin.io/",
        "https://jobs.quickin.io",
        "https://jobs.quickin.io.evil.com/connectforpeople/jobs",
        "https://jobs.quickin.io@evil.com/connectforpeople/jobs",
        "https://evil.com/jobs.quickin.io/connectforpeople",
        "https://api.quickin.io/public/626fd30298767e001a4efe9c/jobs",
        "https://www.quickin.io/connectforpeople",
        "https://jobs.gupy.io/connectforpeople",
        "ftp://jobs.quickin.io/connectforpeople/jobs",
        "connect for people",
        "connectfôrpeople",
        "../connectforpeople",
        "connectforpeople/jobs",
        "x" * 101,
    ],
)
async def test_resolver_recusa_o_que_nao_e_do_quickin_sem_fazer_pedido(entrada: str) -> None:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"resolver não faz pedido: {pedido.url}")

    with pytest.raises(ValueError):
        await _resolver(entrada, recusa)


def _nuxt(dados: object, *, id_: str = "__NUXT_DATA__") -> httpx.Response:
    texto = dados if isinstance(dados, str) else json.dumps(dados)
    return httpx.Response(
        200,
        text=f'<html><body><script type="application/json" id="{id_}">{texto}</script></body>',
    )


def _site(**campos: object) -> list[object]:
    """Um `__NUXT_DATA__` mínimo no formato devalue, com os campos dados em `site`."""
    chaves = {nome: 6 + i for i, nome in enumerate(campos)}
    return [["ShallowReactive", 1], {"pinia": 2}, ["Reactive", 3], {"careerSite": 4},
            {"site": 5}, chaves, *campos.values()]  # fmt: skip


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, text="<html><body>sem dados</body></html>"),
        httpx.Response(200, text='<script id="outro">[]</script>'),
        _nuxt("não é json"),
        _nuxt([]),
        _nuxt({}),
        _nuxt("[0]"),
        _nuxt([["ShallowReactive", 99]]),
        _nuxt([["ShallowReactive", 0]]),  # ciclo
        _nuxt([["ShallowReactive", 1], {"pinia": -1}]),
        _nuxt([["ShallowReactive", 1], {"pinia": True}]),
        _nuxt(_site(slug="connectforpeople")),  # sem account_id
        _nuxt(_site(slug="connectforpeople", account_id="")),
        _nuxt(_site(slug="connectforpeople", account_id="quickin")),
        _nuxt(_site(slug="connectforpeople", account_id=CONTA[:-1])),
        _nuxt(_site(slug="connectforpeople", account_id=CONTA.upper())),
        _nuxt(_site(slug="connectforpeople", account_id=CONTA + "0")),
        _nuxt(_site(slug="connectforpeople", account_id=7)),
        _nuxt(_site(slug="connectforpeople", account_id=None)),
        _nuxt(_site(slug="outraempresa", account_id=CONTA)),  # a página é de outro slug
        _nuxt(_site(account_id=CONTA, name="Sem slug")),
        _nuxt(_site(slug="connectforpeople", account_id=CONTA), id_="__NEXT_DATA__"),
        httpx.Response(404, text="não achei"),
    ],
)
async def test_resolver_pagina_sem_account_id_valido_levanta(resposta: httpx.Response) -> None:
    with pytest.raises(ValueError):
        await _resolver("connectforpeople", resposta)


async def test_resolver_aceita_nuxt_data_so_com_o_necessario() -> None:
    resolvido, _ = await _resolver(
        "connectforpeople", _nuxt(_site(slug="connectforpeople", account_id=CONTA))
    )
    assert resolvido == {"identificador": "connectforpeople", "account_id": CONTA}


async def test_resolver_nao_executa_nada_da_pagina() -> None:
    # texto de página é dado: script ao redor do bloco e valor estranho dentro dele não rodam
    pagina = _nuxt(_site(slug="connectforpeople", account_id=CONTA))
    corpo = pagina.text.replace(
        "<body>", "<body><script>throw new Error('x')</script><!-- __import__('os') -->"
    )
    resolvido, _ = await _resolver("connectforpeople", httpx.Response(200, text=corpo))
    assert resolvido["account_id"] == CONTA


async def test_resolver_erro_de_rede_que_nao_e_404_sobe() -> None:
    from jobot.nucleo.http import ErroDeRede

    with pytest.raises(ErroDeRede):
        await _resolver("connectforpeople", httpx.Response(500))


def test_empresas_json_nao_tem_quickin_ainda_ou_traz_a_conta() -> None:
    lista = json.loads(
        (RAIZ / "src" / "jobot" / "nucleo" / "dados" / "empresas.json").read_text(encoding="utf-8")
    )["empresas"]
    for e in lista:
        if e["fonte"] == "quickin":
            assert set(e["parametros"]) == {"account_id"}
            assert len(e["parametros"]["account_id"]) == 24
