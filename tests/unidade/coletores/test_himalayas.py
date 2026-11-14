import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, himalayas, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "himalayas"
BUSCA = "https://himalayas.app/jobs/api/search"
URL_BR = f"{BUSCA}?q=python&country=BR&sort=recent&page=1"
Responder = Callable[[httpx.Request], httpx.Response]
ULTIMA_MODIFICACAO = "Fri, 13 Nov 2026 23:06:49 GMT"


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _dados(caso: str = "normal") -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_texto(caso))
    return dados


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
    escopo: str = "BR|python",
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
        resultado = await himalayas.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"teste não faz pedido: {pedido.url}")

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


def _uma_pagina(**cabecalhos: str) -> httpx.Response:
    """O exemplo `normal` com `totalCount` igual às 20 vagas: a lista termina na página 1."""
    dados = _dados()
    dados["totalCount"] = len(dados["jobs"])
    return httpx.Response(200, json=dados, headers=cabecalhos)


def _pagina(numero: int, total: int = 949) -> httpx.Response:
    """Uma página de 20 vagas a partir do `normal`, com guid próprio por página."""
    dados = _dados()
    for i, job in enumerate(dados["jobs"]):
        job["guid"] = f"https://himalayas.app/companies/x/jobs/p{numero}-{i}"
    dados["totalCount"] = total
    return httpx.Response(200, json=dados)


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = himalayas.COLETOR
    assert registro.descobrir()["himalayas"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "A"
    assert (prova.intervalo_min, prova.max_pedidos, prova.espera_s) == (1440, 30, 2.0)
    assert prova.credito_obrigatorio is True
    assert prova.hosts == ("himalayas.app",)


def test_escopos_um_por_cargo_e_pais() -> None:
    ctx = ContextoColeta(
        empresas=[], termos=["python", " python ", "Data Engineer", ""], paises=["BR", "PT"]
    )
    assert list(himalayas.COLETOR.escopos(ctx)) == [
        "BR|python",
        "BR|Data Engineer",
        "PT|python",
        "PT|Data Engineer",
    ]


def test_escopos_sem_pais_ou_sem_cargo() -> None:
    sem_pais = ContextoColeta(empresas=[], termos=["python"], paises=[])
    assert list(himalayas.COLETOR.escopos(sem_pais)) == ["|python"]
    sem_cargo = ContextoColeta(empresas=[], termos=[], paises=["BR"])
    assert list(himalayas.COLETOR.escopos(sem_cargo)) == []


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_uma_pagina(**{"Last-Modified": ULTIMA_MODIFICACAO}))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    vagas = _vagas(resultado)
    assert len(vagas) == 20
    primeira = vagas[0]
    guid = "https://himalayas.app/companies/lemon-io/jobs/senior-react-full-stack-developer"
    assert primeira.fonte == "himalayas" and primeira.escopo == "BR|python"
    assert primeira.url == primeira.id_externo == guid
    assert primeira.titulo == "Senior React Full-stack Developer"
    assert primeira.empresa == "lemon.io"
    assert primeira.descricao_formato == "html" and primeira.descricao.startswith("<p>")
    assert primeira.publicada_em == datetime(2026, 11, 10, 13, 24, 32, tzinfo=UTC)
    assert primeira.modalidade_declarada == "remote"
    assert primeira.contrato_declarado == "Full Time"
    assert primeira.etiquetas == ("Senior",)
    assert primeira.locais[:3] == ("Albania", "Andorra", "Argentina")
    assert primeira.salario_estruturado is None
    assert all(v.url.startswith("https://") for v in vagas)
    assert len(pedidos) == 1


async def test_url_candidatura_intacta() -> None:
    resultado, _ = await _coletar(_uma_pagina())
    brutos = [j["applicationLink"] for j in _dados()["jobs"]]
    assert [v.url_candidatura for v in _vagas(resultado)] == brutos
    assert brutos[0].endswith("?utm_source=api")  # o parâmetro de rastreio não sai


async def test_pub_date_em_segundos() -> None:
    resultado, _ = await _coletar(_uma_pagina())
    brutos = [j["pubDate"] for j in _dados()["jobs"]]
    esperado = [datetime.fromtimestamp(s, UTC) for s in brutos]
    assert [v.publicada_em for v in _vagas(resultado)] == esperado
    assert esperado[0].year == 2026  # em milissegundos seria o ano 58000


async def test_expiry_date_vira_prazo() -> None:
    resultado, _ = await _coletar(_uma_pagina())
    vagas = _vagas(resultado)
    assert vagas[0].prazo == date(2026, 12, 10)  # expiryDate 1796908875, epoch em segundos
    brutos = [j["expiryDate"] for j in _dados()["jobs"]]
    assert [v.prazo for v in vagas] == [datetime.fromtimestamp(s, UTC).date() for s in brutos]


async def test_salario_estruturado() -> None:
    resultado, _ = await _coletar(_uma_pagina())
    com_faixa = [v for v in _vagas(resultado) if v.salario_estruturado is not None]
    assert [v.salario_estruturado for v in com_faixa] == [
        SalarioBruto(moeda="USD", minimo_unidades=45, maximo_unidades=90, periodo="hora"),
        SalarioBruto(moeda="USD", minimo_unidades=60, maximo_unidades=120, periodo="hora"),
    ]
    assert all(v.salario_texto is None for v in _vagas(resultado))


async def test_salario_periodo_desconhecido_fica_sem_periodo() -> None:
    dados = _dados()
    dados["jobs"][0] |= {"minSalary": 5000, "maxSalary": None, "salaryPeriod": "quinzenal"}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert _vagas(resultado)[0].salario_estruturado == SalarioBruto(
        moeda="USD", minimo_unidades=5000, maximo_unidades=None, periodo=None
    )


async def test_vazio() -> None:
    resultado, _ = await _coletar(_json("vazio"), escopo="|xyzzyjobot")
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(_vagas(resultado)) == 1


@pytest.mark.parametrize(
    "corpo",
    [
        '{"results": []}',
        "[]",
        '{"jobs": {}, "totalCount": 1}',
        '{"jobs": []}',
        "isto não é json",
        '{"jobs": [1, "x"], "totalCount": 2}',
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_pagina_ilegivel_depois_da_primeira_fica_parcial() -> None:
    resultado, pedidos = await _coletar(_pagina(1), httpx.Response(200, text="<html>"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(_vagas(resultado)) == 20 and len(pedidos) == 2


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = _dados()
    dados["jobs"][0] |= {
        "pubDate": True,
        "expiryDate": "logo",
        "locationRestrictions": None,
        "description": None,
        "seniority": "Senior",
        "employmentType": None,
        "applicationLink": None,
        "minSalary": "muito",
        "maxSalary": -1,
    }
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.prazo, vaga.locais) == (None, None, ())
    assert (vaga.descricao, vaga.etiquetas) == ("", ())
    assert (vaga.contrato_declarado, vaga.url_candidatura, vaga.salario_estruturado) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize("campo", ["guid", "applicationLink"])
async def test_url_fora_de_http_pula_a_vaga(campo: str) -> None:
    dados = _dados()
    dados["jobs"][1][campo] = "javascript:alert(1)"
    dados["totalCount"] = len(dados["jobs"])
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 19


async def test_paginacao_segue_ate_o_total() -> None:
    resultado, pedidos = await _coletar(_pagina(1, 45), _pagina(2, 45), _pagina(3, 45))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 3)
    assert len(_vagas(resultado)) == 60  # a última página repete 20: o total é só o que para
    assert [p.url.params["page"] for p in pedidos] == ["1", "2", "3"]


async def test_paginacao_para_em_pagina_vazia() -> None:
    resultado, pedidos = await _coletar(_pagina(1), _json("vazio"))
    assert (resultado.estado, len(_vagas(resultado)), len(pedidos)) == ("ok", 20, 2)


async def test_31_pedidos_vira_no_limite() -> None:
    contador = iter(range(1, 1000))
    resultado, pedidos = await _coletar(lambda _: _pagina(next(contador)), max_pedidos=30)
    assert (resultado.estado, resultado.motivo) == ("no_limite", "saude.orcamento")
    assert (len(pedidos), resultado.pedidos, len(resultado.vagas)) == (30, 30, 600)


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

    monkeypatch.setattr(himalayas, "juntar_paginas", espia)

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-Modified-Since") == ULTIMA_MODIFICACAO:
            return httpx.Response(304, headers={"Last-Modified": ULTIMA_MODIFICACAO})
        return _uma_pagina(**{"Last-Modified": ULTIMA_MODIFICACAO})

    leitor = LeitorFixo({URL_BR: Validadores(None, ULTIMA_MODIFICACAO)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-Modified-Since") for p in pedidos] == [ULTIMA_MODIFICACAO]
    assert len(paginas) == 1 and paginas[0] is base.SEM_MUDANCA
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "sem_mudanca", None)


async def test_304_depois_de_pagina_nova_fica_parcial() -> None:
    url_p2 = f"{BUSCA}?q=python&country=BR&sort=recent&page=2"

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.params["page"] == "2":
            return httpx.Response(304)
        return _pagina(1)

    leitor = LeitorFixo({url_p2: Validadores(None, ULTIMA_MODIFICACAO)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.listagem_incompleta")
    assert (len(_vagas(resultado)), len(pedidos)) == (20, 2)


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
    assert str(pedido.url) == URL_BR
    assert dict(pedido.url.params) == {
        "q": "python",
        "country": "BR",
        "sort": "recent",
        "page": "1",
    }
    assert "Cookie" not in pedido.headers and "Authorization" not in pedido.headers


async def test_sem_pais_nao_manda_country() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo="|xyzzyjobot")
    assert str(pedidos[0].url) == f"{BUSCA}?q=xyzzyjobot&sort=recent&page=1"


async def test_cargo_com_barra_e_separador_no_escopo() -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo="BR|c|c++ & dados")
    assert dict(pedidos[0].url.params)["q"] == "c|c++ & dados"
    assert dict(pedidos[0].url.params)["country"] == "BR"


async def test_resolver_nao_se_aplica(http_proibido: HttpEducado) -> None:
    with pytest.raises(ValueError):
        await himalayas.COLETOR.resolver("python", http_proibido)


async def test_detalhar_nao_faz_nada(http_proibido: HttpEducado) -> None:
    item = _vagas((await _coletar(_uma_pagina()))[0])[0]
    assert await himalayas.COLETOR.detalhar(item, http_proibido) is None
