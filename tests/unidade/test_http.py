import socket
from collections.abc import Callable
from contextlib import aclosing
from datetime import timedelta
from email.utils import format_datetime

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.http import (
    Bloqueio,
    CabecalhoProibido,
    ClienteEducado,
    ErroDeRede,
    HttpDoEscopo,
    HttpEducado,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    Resolvedor,
    RespostaGrande,
    Validadores,
    conferir_dns,
    host_local,
)
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

UA = "joBot/9.9.9 (+https://github.com/fezarosa-dev/joBot)"
MB = 1024 * 1024
Responder = Callable[[httpx.Request], httpx.Response]


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


class Servidor:
    """Transporte falso: guarda os pedidos e responde em sequência (o último se repete)."""

    def __init__(self, *respostas: httpx.Response | Responder) -> None:
        self.pedidos: list[httpx.Request] = []
        self._respostas = list(respostas) or [httpx.Response(200, text="ok")]

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        r = self._respostas.pop(0) if len(self._respostas) > 1 else self._respostas[0]
        return r if isinstance(r, httpx.Response) else r(pedido)


class ResolvedorFalso:
    """DNS falso: devolve sempre os mesmos endereços e guarda os hosts pedidos."""

    def __init__(self, *enderecos: str, erro: Exception | None = None) -> None:
        self.enderecos = list(enderecos)
        self.erro = erro
        self.hosts: list[str] = []

    async def __call__(self, host: str) -> list[str]:
        self.hosts.append(host)
        if self.erro is not None:
            raise self.erro
        return self.enderecos


PUBLICO = "93.184.215.14"


def _cliente(
    servidor: Servidor,
    relogio: RelogioFalso | None = None,
    leitor: LeitorFixo | None = None,
    resolver: Resolvedor | None = None,
) -> tuple[ClienteEducado, RelogioFalso]:
    rel = relogio or RelogioFalso()
    prova: Relogio = rel
    cli = ClienteEducado(
        httpx.MockTransport(servidor),
        prova,
        leitor or LeitorFixo(),
        "9.9.9",
        resolver=resolver or ResolvedorFalso(PUBLICO),  # salto para nome: nunca o DNS de verdade
    )
    return cli, rel


async def test_user_agent_fixo_em_todo_pedido() -> None:
    srv = Servidor(
        httpx.Response(302, headers={"Location": "https://b.example/fim"}),
        httpx.Response(200, text="ok"),
    )
    cli, _ = _cliente(srv)
    http: HttpEducado = cli.escopo()
    await http.pedir("GET", "https://a.example/x")
    await http.pedir("POST", "https://a.example/y", corpo_json={"a": 1})
    async for _ in http.ler_em_fluxo("https://a.example/z", teto_bytes=MB):
        pass
    assert len(srv.pedidos) == 4
    assert [p.headers["User-Agent"] for p in srv.pedidos] == [UA] * 4


async def test_nenhum_pedido_leva_cookie_nem_cabecalho_de_identidade() -> None:
    srv = Servidor(
        httpx.Response(
            302, headers={"Location": "https://b.example/", "Set-Cookie": "sessao=1; Path=/"}
        ),
        httpx.Response(200, headers={"Set-Cookie": "outro=2; Path=/"}, text="ok"),
    )
    cli, _ = _cliente(srv)
    http = cli.escopo()
    await http.pedir("GET", "https://a.example/")
    await http.pedir("GET", "https://b.example/")
    await http.pedir("GET", "https://a.example/")
    for p in srv.pedidos:
        for nome in ("Cookie", "Origin", "Authorization", "Referer"):
            assert nome not in p.headers


@pytest.mark.parametrize(
    "nome", ["Origin", "Cookie", "Authorization", "Referer", "User-Agent", "user-agent", "X-Outro"]
)
async def test_cabecalho_proibido(nome: str) -> None:
    srv = Servidor()
    cli, _ = _cliente(srv)
    http = cli.escopo()
    with pytest.raises(CabecalhoProibido):
        await http.pedir("GET", "https://a.example/", cabecalhos={nome: "x"})
    with pytest.raises(CabecalhoProibido):
        async for _ in http.ler_em_fluxo(
            "https://a.example/", teto_bytes=MB, cabecalhos={nome: "x"}
        ):
            pass
    assert srv.pedidos == []
    aceitos = {
        "Accept": "application/json",
        "Accept-Language": "pt-BR",
        "Content-Type": "application/json",
        "Range": "bytes=0-9",
        "X-Tenant": "acme",
    }
    await http.pedir("GET", "https://a.example/", cabecalhos=aceitos)
    assert all(srv.pedidos[0].headers[k] == v for k, v in aceitos.items())


async def test_espera_minima_por_host() -> None:
    srv = Servidor()
    cli, rel = _cliente(srv)
    http = cli.escopo()
    await http.pedir("GET", "https://a.example/1")
    await http.pedir("GET", "https://a.example/2")
    assert sum(rel.dormidas) >= 1.0

    cli, rel = _cliente(Servidor())
    http = cli.escopo(espera_s=2)
    await http.pedir("GET", "https://a.example/1")
    await http.pedir("GET", "https://a.example/2")
    assert sum(rel.dormidas) >= 2.0

    cli, rel = _cliente(Servidor())
    http = cli.escopo()
    await http.pedir("GET", "https://a.example/1")
    await http.pedir("GET", "https://b.example/1")
    assert rel.dormidas == []


def _data_http(rel: RelogioFalso, segundos: int) -> str:
    return format_datetime(rel.agora() + timedelta(seconds=segundos), usegmt=True)


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("forma", ["segundos", "data"])
async def test_429_com_retry_after(status: int, forma: str) -> None:
    rel = RelogioFalso()
    valor = "45" if forma == "segundos" else _data_http(rel, 45)
    srv = Servidor(httpx.Response(status, headers={"Retry-After": valor}), httpx.Response(200))
    cli, _ = _cliente(srv, rel)
    resposta = await cli.escopo().pedir("GET", "https://a.example/")
    assert resposta.status == 200
    assert rel.dormidas == [45]
    assert len(srv.pedidos) == 2

    rel = RelogioFalso()
    valor = "601" if forma == "segundos" else _data_http(rel, 601)
    srv = Servidor(httpx.Response(status, headers={"Retry-After": valor}))
    cli, _ = _cliente(srv, rel)
    with pytest.raises(LimiteAtingido):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert rel.dormidas == []
    assert len(srv.pedidos) == 1


@pytest.mark.parametrize("status", [429, 503])
async def test_429_sem_retry_after(status: int) -> None:
    srv = Servidor(httpx.Response(status))
    cli, rel = _cliente(srv)
    http = cli.escopo()
    with pytest.raises(LimiteAtingido):
        await http.pedir("GET", "https://a.example/")
    assert rel.dormidas == [30, 60, 120]
    assert len(srv.pedidos) == 4
    assert http.pedidos == 4


@pytest.mark.parametrize("nome", ["x-ratelimit-remaining", "X-RateLimit-Remaining"])
async def test_429_com_cota_zero_sem_retry_after_nao_espera(nome: str) -> None:
    cota = {nome: "0", "x-ratelimit-limit": "60"}
    srv = Servidor(httpx.Response(429, headers=cota))
    cli, rel = _cliente(srv)
    http = cli.escopo()
    with pytest.raises(LimiteAtingido) as limite:
        await http.pedir("GET", "https://a.example/")
    assert rel.dormidas == []
    assert len(srv.pedidos) == 1 and http.pedidos == 1
    assert limite.value.cabecalhos["x-ratelimit-remaining"] == "0"


async def test_429_com_cota_sobrando_ou_com_retry_after_segue_as_esperas() -> None:
    # Controles: só "429 + cota zero + sem Retry-After" pula as esperas.
    srv = Servidor(httpx.Response(429, headers={"x-ratelimit-remaining": "12"}))
    cli, rel = _cliente(srv)
    with pytest.raises(LimiteAtingido):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert rel.dormidas == [30, 60, 120]

    srv = Servidor(
        httpx.Response(429, headers={"x-ratelimit-remaining": "0", "Retry-After": "45"}),
        httpx.Response(200),
    )
    cli, rel = _cliente(srv)
    assert (await cli.escopo().pedir("GET", "https://a.example/")).status == 200
    assert rel.dormidas == [45]

    srv = Servidor(httpx.Response(503, headers={"x-ratelimit-remaining": "0"}))
    cli, rel = _cliente(srv)
    with pytest.raises(LimiteAtingido):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert rel.dormidas == [30, 60, 120]


@pytest.mark.parametrize("invalido", ["logo", "", "12abc", "-5"])
async def test_429_com_cota_zero_e_retry_after_invalido_para_na_hora(invalido: str) -> None:
    # Retry-After presente mas que não é número nem data HTTP vale como ausente (T99).
    cabecalhos = {"x-ratelimit-remaining": "0", "Retry-After": invalido}
    srv = Servidor(httpx.Response(429, headers=cabecalhos))
    cli, rel = _cliente(srv)
    with pytest.raises(LimiteAtingido):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert rel.dormidas == []
    assert len(srv.pedidos) == 1


async def test_para_no_429_um_pedido_sem_espera() -> None:
    srv = Servidor(httpx.Response(429, headers={"Retry-After": "5"}))
    cli, rel = _cliente(srv)
    with pytest.raises(Parou429):
        await cli.escopo(para_no_429=True).pedir("GET", "https://a.example/")
    assert len(srv.pedidos) == 1
    assert rel.dormidas == []


@pytest.mark.parametrize("status", [500, 502, 504])
async def test_5xx_duas_tentativas(status: int) -> None:
    srv = Servidor(httpx.Response(status))
    cli, rel = _cliente(srv)
    with pytest.raises(ErroDeRede):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert len(srv.pedidos) == 3
    assert rel.dormidas == [2, 4]

    srv = Servidor(httpx.Response(status), httpx.Response(200, text="ok"))
    cli, _ = _cliente(srv)
    assert (await cli.escopo().pedir("GET", "https://a.example/")).texto == "ok"
    assert len(srv.pedidos) == 2


async def test_erro_de_rede_duas_tentativas() -> None:
    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("caiu", request=pedido)

    srv = Servidor(cai)
    cli, rel = _cliente(srv)
    with pytest.raises(ErroDeRede):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert len(srv.pedidos) == 3
    assert rel.dormidas == [2, 4]


@pytest.mark.parametrize("status", [401, 403])
async def test_401_403_sao_bloqueio_sem_repetir(status: int) -> None:
    srv = Servidor(httpx.Response(status))
    cli, rel = _cliente(srv)
    with pytest.raises(Bloqueio):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert len(srv.pedidos) == 1
    assert rel.dormidas == []


async def test_bloqueio_leva_os_cabecalhos_da_resposta() -> None:
    cota = {"x-ratelimit-remaining": "0", "x-ratelimit-limit": "60"}
    cli, _ = _cliente(Servidor(httpx.Response(403, headers=cota)))
    with pytest.raises(Bloqueio) as bloqueio:
        await cli.escopo().pedir("GET", "https://a.example/")
    assert hasattr(bloqueio.value, "cabecalhos"), "o Bloqueio não traz os cabeçalhos"
    assert bloqueio.value.cabecalhos.get("X-RateLimit-Remaining") == "0"

    cli, _ = _cliente(Servidor(httpx.Response(429, headers=cota)))
    with pytest.raises(LimiteAtingido) as limite:
        await cli.escopo().pedir("GET", "https://a.example/")
    assert limite.value.cabecalhos.get("x-ratelimit-remaining") == "0"

    # Quem já cria as exceções só com a mensagem continua funcionando, com cabeçalhos vazios.
    assert dict(Bloqueio("x").cabecalhos) == {} and str(LimiteAtingido("y")) == "y"
    assert dict(LimiteAtingido().cabecalhos) == {}


async def test_teto_de_5_mb() -> None:
    cli, _ = _cliente(Servidor(httpx.Response(200, content=b"x" * 5 * MB)))
    assert len((await cli.escopo().pedir("GET", "https://a.example/")).texto) == 5 * MB

    cli, _ = _cliente(Servidor(httpx.Response(200, content=b"x" * (5 * MB + 1))))
    with pytest.raises(RespostaGrande):
        await cli.escopo().pedir("GET", "https://a.example/")


async def test_fluxo_com_teto_proprio() -> None:
    corpo = b"x" * (6 * MB)
    cli, _ = _cliente(Servidor(httpx.Response(200, content=corpo)))
    http = cli.escopo()
    with pytest.raises(RespostaGrande):
        await http.pedir("GET", "https://a.example/feed")
    lido = b"".join(
        [p async for p in http.ler_em_fluxo("https://a.example/feed", teto_bytes=32 * MB)]
    )
    assert lido == corpo
    with pytest.raises(RespostaGrande):
        async for _ in http.ler_em_fluxo("https://a.example/feed", teto_bytes=MB):
            pass


async def test_condicional() -> None:
    url = "https://a.example/vagas?p=1"
    leitor = LeitorFixo(
        {url: Validadores(etag='"v1"', last_modified="Tue, 10 Nov 2026 10:00:00 GMT")}
    )
    srv = Servidor(
        httpx.Response(304),
        httpx.Response(
            200, headers={"ETag": '"v2"', "Last-Modified": "Fri, 13 Nov 2026"}, text="{}"
        ),
    )
    cli, _ = _cliente(srv, leitor=leitor)
    http = cli.escopo()
    r = await http.pedir("GET", "https://a.example/vagas", params={"p": "1"}, condicional=True)
    assert r.status == 304
    assert srv.pedidos[0].headers.get("If-None-Match") == '"v1"'
    assert srv.pedidos[0].headers.get("If-Modified-Since") == "Tue, 10 Nov 2026 10:00:00 GMT"
    assert http.validadores_novos == {}

    r = await http.pedir("GET", "https://a.example/vagas", params={"p": "1"}, condicional=True)
    assert r.status == 200
    assert http.validadores_novos == {
        url: Validadores(etag='"v2"', last_modified="Fri, 13 Nov 2026")
    }
    assert leitor.guardados[url].etag == '"v1"'  # o cliente só lê; quem grava é o executor

    await http.pedir("GET", "https://a.example/outra", condicional=False)
    assert "If-None-Match" not in srv.pedidos[-1].headers


async def test_condicional_desligado_nao_envia() -> None:
    url = "https://a.example/vagas"
    leitor = LeitorFixo({url: Validadores(etag='"v1"', last_modified="Tue, 10 Nov 2026")})
    srv = Servidor()
    cli, _ = _cliente(srv, leitor=leitor)
    await cli.escopo().pedir("GET", url, condicional=True)
    assert srv.pedidos[0].headers.get("If-None-Match") == '"v1"'  # controle: ligado envia
    await cli.escopo(condicional=False).pedir("GET", url, condicional=True)
    assert "If-None-Match" not in srv.pedidos[1].headers
    assert "If-Modified-Since" not in srv.pedidos[1].headers


async def test_orcamento() -> None:
    srv = Servidor()
    cli, _ = _cliente(srv)
    http: HttpDoEscopo = cli.escopo(max_pedidos=2)
    await http.pedir("GET", "https://a.example/1")
    await http.pedir("GET", "https://a.example/2")
    with pytest.raises(OrcamentoGasto):
        await http.pedir("GET", "https://a.example/3")
    assert len(srv.pedidos) == 2
    assert http.pedidos == 2


def _cadeia(saltos: int) -> Responder:
    def responde(pedido: httpx.Request) -> httpx.Response:
        n = int(pedido.url.path.strip("/") or 0)
        if n < saltos:
            return httpx.Response(301, headers={"Location": f"https://a.example/{n + 1}"})
        return httpx.Response(200, text="fim")

    return responde


async def test_redirecionamento() -> None:
    cli, _ = _cliente(Servidor(_cadeia(5)))
    assert (await cli.escopo().pedir("GET", "https://a.example/0")).texto == "fim"

    srv = Servidor(_cadeia(6))
    cli, _ = _cliente(srv)
    with pytest.raises(ErroDeRede):
        await cli.escopo().pedir("GET", "https://a.example/0")

    for destino in ("ftp://a.example/x", "file:///etc/passwd", "javascript:alert(1)"):
        srv = Servidor(httpx.Response(302, headers={"Location": destino}))
        cli, _ = _cliente(srv)
        with pytest.raises(ErroDeRede):
            await cli.escopo().pedir("GET", "https://a.example/")
        assert len(srv.pedidos) == 1


async def test_redirecionamento_segue_ritmo_e_orcamento() -> None:
    # Cada salto é um pedido de rede: espera o mínimo por host e conta no orçamento.
    srv = Servidor(_cadeia(1))
    cli, rel = _cliente(srv)
    http = cli.escopo(espera_s=3)
    assert (await http.pedir("GET", "https://a.example/0")).texto == "fim"
    assert len(srv.pedidos) == 2
    assert http.pedidos == 2
    assert sum(rel.dormidas) >= 3

    srv = Servidor(_cadeia(1))
    cli, _ = _cliente(srv)
    http = cli.escopo(max_pedidos=1)
    with pytest.raises(OrcamentoGasto):
        await http.pedir("GET", "https://a.example/0")
    assert len(srv.pedidos) == 1


async def test_url_malformada_vira_erro_de_rede() -> None:
    srv = Servidor()
    cli, _ = _cliente(srv)
    http = cli.escopo()
    for chamada in ("pedir", "fluxo"):
        try:
            if chamada == "pedir":
                await http.pedir("GET", "http://[::1/")
            else:
                async for _ in http.ler_em_fluxo("http://[::1/", teto_bytes=MB):
                    pass
        except ErroDeRede:
            continue
        except httpx.InvalidURL as erro:  # fora das 7 exceções do contrato
            pytest.fail(f"{chamada}: URL malformada escapou: {erro!r}")
        pytest.fail(f"{chamada}: URL malformada não deu erro")
    assert srv.pedidos == []


async def test_salto_para_outra_origem_tira_cabecalhos_do_chamador() -> None:
    url = "https://a.example/x"
    leitor = LeitorFixo({url: Validadores(etag='"v1"', last_modified="Tue, 10 Nov 2026")})
    srv = Servidor(
        httpx.Response(302, headers={"Location": "https://a.example/y"}),
        httpx.Response(302, headers={"Location": "https://b.example/z"}),
        httpx.Response(200, text="ok"),
    )
    cli, _ = _cliente(srv, leitor=leitor)
    await cli.escopo(condicional=True).pedir(
        "GET", url, cabecalhos={"X-Tenant": "acme", "Accept": "text/html"}, condicional=True
    )
    mesma, outra = srv.pedidos[1].headers, srv.pedidos[2].headers
    assert mesma["X-Tenant"] == "acme"
    assert mesma["If-None-Match"] == '"v1"'
    for nome in ("X-Tenant", "If-None-Match", "If-Modified-Since"):
        assert nome not in outra
    assert outra["Accept"] == "text/html"


async def test_charset_desconhecido_vira_utf8() -> None:
    srv = Servidor(
        httpx.Response(
            200,
            content="vaga ação".encode(),
            headers={"Content-Type": "text/html; charset=utf8mb4"},
        )
    )
    cli, _ = _cliente(srv)
    try:
        r = await cli.escopo().pedir("GET", "https://a.example/")
    except LookupError as erro:  # fora das 7 exceções do contrato
        pytest.fail(f"charset desconhecido escapou: {erro!r}")
    assert r.texto == "vaga ação"


async def test_post_nao_e_condicional_nem_guarda_validadores() -> None:
    url = "https://a.example/busca"
    leitor = LeitorFixo({url: Validadores(etag='"v1"', last_modified="Tue, 10 Nov 2026")})
    srv = Servidor(httpx.Response(200, headers={"ETag": '"v2"'}, json={}))
    cli, _ = _cliente(srv, leitor=leitor)
    http = cli.escopo()
    await http.pedir("POST", url, corpo_json={"pagina": 2}, condicional=True)
    assert "If-None-Match" not in srv.pedidos[0].headers
    assert "If-Modified-Since" not in srv.pedidos[0].headers
    assert http.validadores_novos == {}


async def test_tempos() -> None:
    srv = Servidor()
    cli, _ = _cliente(srv)
    await cli.escopo().pedir("GET", "https://a.example/")
    tempos = srv.pedidos[0].extensions["timeout"]
    assert tempos["connect"] == 10
    assert tempos["read"] == 30


async def test_resposta_json_e_cabecalhos() -> None:
    srv = Servidor(httpx.Response(202, json={"vagas": [1]}, headers={"X-Total": "1"}))
    cli, _ = _cliente(srv)
    r = await cli.escopo().pedir("POST", "https://a.example/", corpo_json={"q": "dev"})
    assert r.status == 202
    assert r.json() == {"vagas": [1]}
    assert r.cabecalhos["x-total"] == "1"
    assert srv.pedidos[0].content == b'{"q":"dev"}'
    await cli.fechar()


async def test_resposta_grande_nao_grava_validador() -> None:
    corpo = b"x" * (5 * MB + 1)
    cli, _ = _cliente(Servidor(httpx.Response(200, headers={"ETag": '"v2"'}, content=corpo)))
    http = cli.escopo()
    with pytest.raises(RespostaGrande):
        await http.pedir("GET", "https://a.example/")
    assert http.validadores_novos == {}


async def test_fluxo_so_grava_validador_quando_lido_ate_o_fim() -> None:
    url = "https://a.example/feed"
    cli, _ = _cliente(Servidor(httpx.Response(200, headers={"ETag": '"v2"'}, content=b"abc")))
    http = cli.escopo()
    async with aclosing(http.ler_em_fluxo(url, teto_bytes=MB)) as fluxo:
        async for _ in fluxo:
            break
    assert http.validadores_novos == {}

    async for _ in http.ler_em_fluxo(url, teto_bytes=MB):
        pass
    assert http.validadores_novos == {url: Validadores(etag='"v2"', last_modified=None)}


async def test_erro_de_rede_leva_o_status() -> None:
    cli, _ = _cliente(Servidor(httpx.Response(404)))
    with pytest.raises(ErroDeRede) as erro:
        await cli.escopo().pedir("GET", "https://a.example/")
    assert getattr(erro.value, "status", "sem status") == 404

    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("caiu", request=pedido)

    cli, _ = _cliente(Servidor(cai))
    with pytest.raises(ErroDeRede) as erro:
        await cli.escopo().pedir("GET", "https://a.example/")
    assert getattr(erro.value, "status", "sem status") is None


async def test_parou429_guarda_os_cabecalhos() -> None:
    srv = Servidor(httpx.Response(429, headers={"Retry-After": "120"}))
    cli, _ = _cliente(srv)
    with pytest.raises(Parou429) as info:
        await cli.escopo(para_no_429=True).pedir("GET", "https://a.example/")
    assert getattr(info.value, "cabecalhos", {}).get("retry-after") == "120"
    assert "Retry-After 120" in str(info.value)


async def test_para_no_429_nao_vale_para_503() -> None:
    srv = Servidor(httpx.Response(503, headers={"Retry-After": "5"}), httpx.Response(200))
    cli, rel = _cliente(srv)
    try:
        status: int | None = (
            await cli.escopo(para_no_429=True).pedir("GET", "https://a.example/")
        ).status
    except Parou429:
        status = None  # o 503 não para o escopo
    assert status == 200
    assert rel.dormidas == [5]
    assert len(srv.pedidos) == 2


@pytest.mark.parametrize(
    "destino",
    [
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://169.254.169.254/",
        "http://10.0.0.1/",
        "http://192.168.0.1/",
        "http://localhost/",
        # IPv4 em forma curta, decimal e hexa: o httpx não normaliza, o getaddrinfo resolve
        "http://127.1/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://0/",
        "http://100.64.0.1/",  # CGNAT (Tailscale)
    ],
)
async def test_redirecionamento_de_host_publico_para_local_e_recusado(destino: str) -> None:
    srv = Servidor(httpx.Response(302, headers={"Location": destino}), httpx.Response(200))
    cli, _ = _cliente(srv)
    with pytest.raises(ErroDeRede):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert len(srv.pedidos) == 1


async def test_redirecionamento_dentro_do_host_local_segue() -> None:
    srv = Servidor(
        httpx.Response(302, headers={"Location": "http://127.0.0.1/b"}),
        httpx.Response(200, text="ok"),
    )
    cli, _ = _cliente(srv)
    assert (await cli.escopo().pedir("GET", "http://127.0.0.1/a")).texto == "ok"
    assert len(srv.pedidos) == 2


@pytest.mark.parametrize("destino", ["http://[::7f00:1]/", "http://[64:ff9b::7f00:1]/"])
async def test_redirecionamento_para_ipv6_que_embute_ipv4_local_recusado(destino: str) -> None:
    srv = Servidor(httpx.Response(302, headers={"Location": destino}), httpx.Response(200))
    cli, _ = _cliente(srv)
    with pytest.raises(ErroDeRede):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert len(srv.pedidos) == 1


async def test_redirecionamento_para_ipv6_que_embute_ipv4_publico_segue() -> None:
    srv = Servidor(
        httpx.Response(302, headers={"Location": "http://[64:ff9b::808:808]/"}),
        httpx.Response(200, text="ok"),
    )
    cli, _ = _cliente(srv)
    assert (await cli.escopo().pedir("GET", "https://a.example/")).texto == "ok"
    assert len(srv.pedidos) == 2


async def test_protocolo_ler_em_fluxo_aceita_aclosing() -> None:
    # o Protocol anuncia AsyncGenerator: o mypy strict recusa `aclosing` num AsyncIterator
    cli, _ = _cliente(Servidor(httpx.Response(200, content=b"ok")))
    http: HttpEducado = cli.escopo()
    async with aclosing(http.ler_em_fluxo("https://a.example/x", teto_bytes=MB)) as fluxo:
        assert [p async for p in fluxo] == [b"ok"]


def _salto_para(destino: str) -> Servidor:
    return Servidor(
        httpx.Response(302, headers={"Location": destino}), httpx.Response(200, text="ok")
    )


@pytest.mark.parametrize(
    "enderecos",
    [
        ["10.0.0.5"],
        [PUBLICO, "127.0.0.1"],  # basta um endereço local
        ["::1"],
        ["::ffff:127.0.0.1"],
        ["64:ff9b::a00:1"],  # NAT64 com 10.0.0.1 dentro
        ["::7f00:1"],  # IPv4 compatível com 127.0.0.1 dentro
        ["fe80::1%eth0"],  # link-local com zona, como o getaddrinfo devolve
        ["100.64.0.1"],
    ],
)
async def test_redirecionamento_para_nome_que_resolve_local_recusado(enderecos: list[str]) -> None:
    srv = _salto_para("http://interno.example/admin")
    dns = ResolvedorFalso(*enderecos)
    cli, _ = _cliente(srv, resolver=dns)
    with pytest.raises(ErroDeRede, match="host local"):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert dns.hosts == ["interno.example"]
    assert len(srv.pedidos) == 1


@pytest.mark.parametrize("enderecos", [[], ["isto-nao-e-ip"]])
async def test_resolvedor_sem_endereco_valido_recusa(enderecos: list[str]) -> None:
    srv = _salto_para("http://b.example/")
    cli, _ = _cliente(srv, resolver=ResolvedorFalso(*enderecos))
    with pytest.raises(ErroDeRede):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert len(srv.pedidos) == 1


async def test_redirecionamento_para_nome_publico_segue() -> None:
    srv = _salto_para("https://b.example/fim")
    dns = ResolvedorFalso(PUBLICO, "2606:2800:21f:cb07:6820:80da:af6b:8b2c")
    cli, _ = _cliente(srv, resolver=dns)
    assert (await cli.escopo().pedir("GET", "https://a.example/")).texto == "ok"
    assert dns.hosts == ["b.example"]
    assert len(srv.pedidos) == 2


@pytest.mark.parametrize("erro", [socket.gaierror(-2, "Name or service not known"), OSError("x")])
async def test_resolvedor_falhando_vira_erro_de_rede(erro: Exception) -> None:
    srv = _salto_para("https://b.example/fim")
    dns = ResolvedorFalso(erro=erro)
    cli, _ = _cliente(srv, resolver=dns)
    with pytest.raises(ErroDeRede) as recebido:
        await cli.escopo().pedir("GET", "https://a.example/")
    assert dns.hosts == ["b.example"]
    assert recebido.value.__cause__ is erro
    assert len(srv.pedidos) == 1


@pytest.mark.parametrize(
    "destino", [f"http://{PUBLICO}/x", "http://[2606:2800:21f:cb07:6820:80da:af6b:8b2c]/x", "/x"]
)
async def test_salto_para_ip_literal_nao_chama_resolvedor(destino: str) -> None:
    srv = _salto_para(destino)
    dns = ResolvedorFalso("127.0.0.1")  # se fosse chamado, recusaria
    cli, _ = _cliente(srv, resolver=dns)
    assert (await cli.escopo().pedir("GET", "https://a.example/")).texto == "ok"
    assert dns.hosts == []
    assert len(srv.pedidos) == 2


async def test_salto_de_origem_local_nao_chama_resolvedor() -> None:
    srv = _salto_para("http://servico.lan/b")
    dns = ResolvedorFalso("10.0.0.5")
    cli, _ = _cliente(srv, resolver=dns)
    assert (await cli.escopo().pedir("GET", "http://127.0.0.1/a")).texto == "ok"
    assert dns.hosts == []


async def test_resolvedor_padrao_usa_getaddrinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: list[object] = []

    def getaddrinfo(host: object, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
        pedidos.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    srv = _salto_para("http://interno.example/")
    cli = ClienteEducado(httpx.MockTransport(srv), RelogioFalso(), LeitorFixo(), "9.9.9")
    with pytest.raises(ErroDeRede, match="host local"):
        await cli.escopo().pedir("GET", "https://a.example/")
    assert pedidos == ["interno.example"]


@pytest.mark.parametrize(
    ("host", "local"),
    [("127.0.0.1", True), ("LOCALHOST.", True), ("0x7f000001", True), ("::1", True)]
    + [("::ffff:10.0.0.1", True), (PUBLICO, False), ("a.example", False)],
)
def test_host_local_publico(host: str, local: bool) -> None:
    assert host_local(host) is local


@pytest.mark.parametrize(
    "enderecos",
    [[], ["isto-nao-e-ip"], [PUBLICO, ""], ["10.0.0.5"], [PUBLICO, "::ffff:127.0.0.1"]],
)
async def test_conferir_dns_recusa_o_que_nao_e_ip_global(enderecos: list[str]) -> None:
    dns = ResolvedorFalso(*enderecos)
    with pytest.raises(ErroDeRede, match="host local"):
        await conferir_dns("b.example", dns)
    assert dns.hosts == ["b.example"]


async def test_conferir_dns_aceita_ip_global() -> None:
    dns = ResolvedorFalso(PUBLICO, "2606:2800:21f:cb07:6820:80da:af6b:8b2c")
    await conferir_dns("b.example", dns)
    assert dns.hosts == ["b.example"]


async def test_conferir_dns_falha_do_resolvedor_vira_erro_de_rede() -> None:
    erro = socket.gaierror(-2, "Name or service not known")
    with pytest.raises(ErroDeRede) as recebido:
        await conferir_dns("b.example", ResolvedorFalso(erro=erro))
    assert recebido.value.__cause__ is erro
