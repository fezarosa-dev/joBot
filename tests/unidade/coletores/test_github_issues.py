import json
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, github_issues, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "github_issues"
ESCOPO = "developersRJ/vagas"
URL = "https://api.github.com/repos/developersRJ/vagas/issues?state=open&per_page=100"
REPOS = [
    "backend-br/vagas",
    "frontendbr/vagas",
    "soujava/vagas-java",
    "remotejobsbr/design-ux-vagas",
    "developersRJ/vagas",
]
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _meta(caso: str) -> Mapping[str, str]:
    meta = json.loads((PASTA / f"{caso}.meta.json").read_text(encoding="utf-8"))
    return dict(meta["cabecalhos"])


def _json(caso: str, status: int = 200, extra: Mapping[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, text=_texto(caso), headers={**_meta(caso), **(extra or {})})


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = ESCOPO,
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
        resultado = await github_issues.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _proxima(caso: str) -> str:
    link = _meta(caso)["Link"]
    return link.split(">")[0].removeprefix("<")


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = github_issues.COLETOR
    assert registro.descobrir()["github_issues"] is prova
    assert registro.limites(prova.chave).leva == prova.leva == "A"
    assert prova.hosts == ("api.github.com",)


def test_escopos_sao_os_cinco_repositorios_e_ignoram_o_contexto() -> None:
    ctx = ContextoColeta(
        empresas=[Empresa(nome="X", fonte="greenhouse", identificador="x")],
        termos=["dev"],
        paises=["BR"],
    )
    assert list(github_issues.COLETOR.escopos(ctx)) == REPOS
    assert list(github_issues.COLETOR.escopos(ContextoColeta((), (), ()))) == REPOS


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert [v.id_externo for v in vagas] == [
        f"developersRJ/vagas#{n}" for n in (519, 518, 517, 516, 515)
    ]
    primeira = vagas[0]
    assert primeira.fonte == "github_issues" and primeira.escopo == ESCOPO
    assert primeira.url == "https://github.com/developersRJ/vagas/issues/519"
    assert primeira.titulo == "[Remoto] Pessoa Engenheira de Software - Principal - RD Station"
    assert primeira.empresa == ESCOPO  # shortcut do coletor, ver duvidas
    assert primeira.descricao_formato == "markdown"
    assert primeira.descricao.startswith("## Nossa empresa\nSomos a [RD Station]")
    assert primeira.etiquetas == ("CLT", "Remoto")
    assert primeira.publicada_em == datetime(2025, 3, 3, 17, 50, 22, tzinfo=UTC)
    assert (primeira.url_candidatura, primeira.prazo, primeira.locais) == (None, None, ())
    assert vagas[2].etiquetas == ("CLT", "Especialista", "Remoto")
    assert all(v.url.startswith("https://github.com/") for v in vagas)
    assert len(pedidos) == 1


async def test_vazio() -> None:
    resultado, _ = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_pull_request_e_descartado() -> None:
    resultado, pedidos = await _coletar(_json("com_pr"), escopo="soujava/vagas-java")
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1
    # misto: uma issue de verdade entre pull requests; o controle positivo é a issue que fica
    issues = json.loads(_texto("normal"))
    prs = json.loads(_texto("com_pr"))
    resultado, _ = await _coletar(httpx.Response(200, json=[*prs[:2], issues[0], *prs[2:]]))
    assert resultado.estado == "ok"
    assert [v.id_externo for v in _vagas(resultado)] == ["developersRJ/vagas#519"]


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["developersRJ/vagas#519"]


@pytest.mark.parametrize(
    "corpo",
    ['{"message": "Not Found"}', "{}", "isto não é json", '[1, "x"]', '[{"number": 1}]'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    dados = json.loads(_texto("normal"))[:1]
    dados[0] |= {"body": None, "created_at": "ontem", "labels": "CLT"}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.descricao, vaga.publicada_em, vaga.etiquetas) == ("", None, ())
    dados[0] |= {"created_at": "2025-03-03T17:50:22", "labels": [{"name": "CLT"}, 1, {"id": 2}]}
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    vaga = _vagas(resultado)[0]
    assert (vaga.publicada_em, vaga.etiquetas) == (None, ("CLT",))


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("html_url", "javascript:alert(1)"), ("number", "519"), ("title", "  ")],
)
async def test_item_ruim_pula_a_vaga_e_deixa_parcial(campo: str, valor: object) -> None:
    dados = json.loads(_texto("normal"))
    dados[1][campo] = valor
    resultado, _ = await _coletar(httpx.Response(200, json=dados))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 4


async def test_paginacao_segue_o_link_como_vier() -> None:
    proxima = _proxima("paginacao_1")
    assert (
        "/repositories/70816214/issues" in proxima
    )  # não é o /repos/<owner>/<repo> que o coletor monta
    resultado, pedidos = await _coletar(_json("paginacao_1"), _json("paginacao_2"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 2)
    assert [v.id_externo for v in _vagas(resultado)] == [
        f"developersRJ/vagas#{n}" for n in (519, 518, 517, 516, 515)
    ]
    assert [str(p.url) for p in pedidos] == [URL, proxima]
    assert all(p.method == "GET" for p in pedidos)


async def test_paginacao_so_a_primeira_pagina_e_condicional() -> None:
    etag = 'W/"abc"'
    leitor = LeitorFixo(
        {URL: Validadores(etag, None), _proxima("paginacao_1"): Validadores('W/"zzz"', None)}
    )
    _, pedidos = await _coletar(
        _json("paginacao_1"), _json("paginacao_2"), leitor=leitor, condicional=True
    )
    assert [p.headers.get("If-None-Match") for p in pedidos] == [etag, None]


@pytest.mark.parametrize(
    "destino",
    [
        "https://evil.test/repositories/1/issues?page=2",
        "http://api.github.com/repositories/1/issues?page=2",
        "https://api.github.com.evil.test/repositories/1/issues?page=2",
        "https://api.github.com@evil.test/repositories/1/issues?page=2",
        "https://127.0.0.1/repositories/1/issues?page=2",
    ],
)
async def test_link_para_fora_da_api_nao_e_seguido(destino: str) -> None:
    primeira = _json("paginacao_1", extra={"Link": f'<{destino}>; rel="next"'})
    resultado, pedidos = await _coletar(primeira, _json("paginacao_2"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(resultado.vagas) == 3 and len(pedidos) == 1


async def test_link_que_volta_para_uma_pagina_ja_lida_nao_gira_em_circulo() -> None:
    proxima = _proxima("paginacao_1")
    laco = _json("paginacao_2", extra={"Link": f'<{proxima}>; rel="next"'})
    resultado, pedidos = await _coletar(_json("paginacao_1"), laco)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert len(pedidos) == 2


async def test_teto_de_paginas_para_com_parcial() -> None:
    n = 0

    def infinita(pedido: httpx.Request) -> httpx.Response:
        nonlocal n
        n += 1
        link = f'<https://api.github.com/repositories/1/issues?page={n + 1}>; rel="next"'
        return httpx.Response(200, text="[]", headers={"Link": link})

    resultado, pedidos = await _coletar(infinita)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert len(pedidos) == github_issues._MAX_PAGINAS


async def test_link_com_outras_relacoes_e_sem_next_termina() -> None:
    resultado, pedidos = await _coletar(_json("paginacao_2"))
    assert resultado.estado == "ok" and len(pedidos) == 1


async def test_cota_acabou_no_meio_da_lista_e_no_limite() -> None:
    primeira = _json("paginacao_1", extra={"x-ratelimit-remaining": "0", "x-ratelimit-limit": "60"})
    resultado, pedidos = await _coletar(primeira, _json("paginacao_2"))
    assert (resultado.estado, resultado.motivo) == ("no_limite", "saude.cota")
    assert len(resultado.vagas) == 3 and len(pedidos) == 1


async def test_cota_a_zero_na_ultima_pagina_nao_atrapalha() -> None:
    ultima = _json("paginacao_2", extra={"x-ratelimit-remaining": "0"})
    resultado, _ = await _coletar(ultima)
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    sobra = _json("paginacao_1", extra={"x-ratelimit-remaining": "17"})
    resultado, pedidos = await _coletar(sobra, _json("paginacao_2"))
    assert (resultado.estado, len(pedidos)) == ("ok", 2)


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

    monkeypatch.setattr(github_issues, "juntar_paginas", espia)
    etag = _meta("normal")["ETag"]

    def responde(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return _json("normal")

    leitor = LeitorFixo({URL: Validadores(etag, None)})
    resultado, pedidos = await _coletar(responde, leitor=leitor, condicional=True)
    assert [p.headers.get("If-None-Match") for p in pedidos] == [etag]
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
    assert dict(pedido.url.params) == {"state": "open", "per_page": "100"}
    assert not {"authorization", "cookie", "origin", "referer"} & set(pedido.headers)


@pytest.mark.parametrize(
    "escopo", ["", "vagas", "../x", "a/..", "a/b/c", "a b/c", "a/b?c#d", "a/%2e%2e"]
)
async def test_escopo_estranho_e_recusado_sem_pedido(escopo: str) -> None:
    pedidos: list[httpx.Request] = []

    def anota(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return httpx.Response(200, text="[]")

    with pytest.raises(ValueError):
        await _coletar(anota, escopo=escopo)
    assert pedidos == []


async def test_caixa_do_repositorio_e_preservada() -> None:
    resultado, pedidos = await _coletar(_json("vazio"), escopo="frontendbr/vagas")
    assert resultado.estado == "ok"
    assert pedidos[0].url.path == "/repos/frontendbr/vagas/issues"
    resultado, _ = await _coletar(_json("normal"), escopo="DevelopersRJ/Vagas")
    assert _vagas(resultado)[0].id_externo == "DevelopersRJ/Vagas#519"


async def test_detalhar_e_resolver(http_proibido: HttpEducado) -> None:
    assert (
        await github_issues.COLETOR.detalhar(
            VagaColetada(
                fonte="github_issues",
                escopo=ESCOPO,
                url="https://github.com/a/b/issues/1",
                titulo="t",
                empresa="e",
                descricao_formato="markdown",
            ),
            http_proibido,
        )
        is None
    )
    with pytest.raises(ValueError):
        await github_issues.COLETOR.resolver("developersRJ/vagas", http_proibido)


@pytest.fixture
async def http_proibido() -> AsyncIterator[HttpEducado]:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não faz pedido: {pedido.url}")

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(httpx.MockTransport(recusa), relogio, LeitorFixo(), "0.1.0", _sem_dns)
    try:
        yield cli.escopo()
    finally:
        await cli.fechar()
