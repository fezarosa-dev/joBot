"""Páginas acompanhadas (plano T72; desenho 8.8, DR-18, DR-19, 14.3).

HTTP só por `httpx.MockTransport` e DNS só por resolvedor falso: nenhum teste vai à rede.
"""

import asyncio
import sqlite3
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from jobot.agenda.paginas import executar_paginas
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.paginas import (
    adicionar_pagina,
    desativar_pagina,
    gravar_leitura,
    marcar_vista,
    mudancas,
    paginas,
    remover_pagina,
)
from jobot.cli import servir
from jobot.nucleo.coletores.paginas import (
    ConteudoNaoLido,
    Mudanca,
    Pagina,
    endereco_permitido,
    verificar,
)
from jobot.nucleo.http import ClienteEducado, ErroDeRede, Resolvedor, Validadores
from jobot.nucleo.relogio import Relogio

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("laco_versao_parado")]

PUBLICO = "93.184.215.14"
URL = "https://empresa.example/programa-trainee"
AGORA = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
Responder = Callable[[httpx.Request], httpx.Response]


class _RelogioParado(RelogioFalso):
    """O batimento da execução dorme para sempre: o `dormir` do `RelogioFalso` não solta o laço."""

    async def dormir(self, s: float) -> None:
        self.dormidas.append(s)
        await asyncio.Event().wait()


class _Leitor:
    def ler(self, url: str) -> Validadores | None:
        return None


class _Servidor:
    """Transporte falso: guarda os pedidos e responde em sequência (o último se repete)."""

    def __init__(self, *respostas: httpx.Response | Responder) -> None:
        self.pedidos: list[httpx.Request] = []
        self._respostas = list(respostas) or [httpx.Response(200, text="ok")]

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        r = self._respostas.pop(0) if len(self._respostas) > 1 else self._respostas[0]
        return r if isinstance(r, httpx.Response) else r(pedido)


class _Dns:
    def __init__(self, *enderecos: str) -> None:
        self.enderecos = list(enderecos)
        self.hosts: list[str] = []

    async def __call__(self, host: str) -> list[str]:
        self.hosts.append(host)
        return self.enderecos


def _cliente(srv: _Servidor, dns: Resolvedor | None = None) -> ClienteEducado:
    relogio: Relogio = RelogioFalso(AGORA)
    return ClienteEducado(
        httpx.MockTransport(srv), relogio, _Leitor(), "9.9.9", resolver=dns or _Dns(PUBLICO)
    )


def _pagina(url: str = URL, texto: str | None = None, hash_texto: str | None = None) -> Pagina:
    return Pagina(
        id=1,
        url=url,
        nome="Trainee",
        ativa=True,
        texto=texto,
        hash_texto=hash_texto,
        verificada_em=None,
        mudou_em=None,
        estado=None,
    )


def _html(*paragrafos: str) -> httpx.Response:
    corpo = "".join(f"<p>{p}</p>" for p in paragrafos)
    return httpx.Response(200, html=f"<html><body><script>x=1</script>{corpo}</body></html>")


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    with closing(abrir(caminho)) as c:
        migrar(c, caminho)
        yield c


def _linha(con: sqlite3.Connection, pagina_id: int) -> tuple[str | None, ...]:
    linha = con.execute(
        "SELECT texto, hash_texto, estado, verificada_em, mudou_em FROM pagina_acompanhada"
        " WHERE id=?",
        (pagina_id,),
    ).fetchone()
    assert linha is not None
    return tuple(linha)


# --- endereço permitido (DR-19) -------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/vagas",
        "http://app.localhost/",
        "http://127.0.0.1:8000/x",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://169.254.1.1/",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://empresa.example/",
        "http://intranet/",
        "http://impressora.local/",
        "http://roteador.lan/",
        "http://2130706433/",
        "http://user:senha@empresa.example/",
        "https://",
        "isto não é url",
    ],
)
def test_recusa_endereco_interno(url: str) -> None:
    assert endereco_permitido(url) is False


@pytest.mark.parametrize(
    "url", [URL, "http://empresa.example/vagas?x=1", "https://[2606:2800:21f:cb07::1]/"]
)
def test_aceita_endereco_publico(url: str) -> None:
    assert endereco_permitido(url) is True


def test_adicionar_pagina_recusa_endereco_interno(con: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        adicionar_pagina(con, "http://192.168.1.1/", "Roteador")
    assert con.execute("SELECT count(*) FROM pagina_acompanhada").fetchone()[0] == 0


async def test_verificar_recusa_endereco_interno_antes_do_pedido() -> None:
    srv = _Servidor()
    with pytest.raises(ValueError):
        await verificar(_cliente(srv).escopo(), _pagina("http://10.0.0.1/"), resolver=_Dns())
    assert srv.pedidos == []


async def test_nome_que_resolve_para_endereco_interno_recusado() -> None:
    srv = _Servidor()
    dns = _Dns("10.0.0.7")
    with pytest.raises(ErroDeRede):
        await verificar(_cliente(srv).escopo(), _pagina(), resolver=dns)
    assert dns.hosts == ["empresa.example"]
    assert srv.pedidos == []


@pytest.mark.parametrize("enderecos", [["isto-nao-e-ip"], [PUBLICO, ""]])
async def test_pagina_que_resolve_para_texto_que_nao_e_ip_e_recusada(enderecos: list[str]) -> None:
    # a mesma regra do salto do cliente (T111, D72): o que não é IP global é recusado
    srv = _Servidor()
    dns = _Dns(*enderecos)
    with pytest.raises(ErroDeRede):
        await verificar(_cliente(srv).escopo(), _pagina(), resolver=dns)
    assert dns.hosts == ["empresa.example"]
    assert srv.pedidos == []


@pytest.mark.parametrize(
    "destino", ["http://127.0.0.1:8000/admin", "http://192.168.0.1/", "http://interno.example/"]
)
async def test_redirecionamento_para_endereco_interno_recusado(destino: str) -> None:
    srv = _Servidor(httpx.Response(302, headers={"Location": destino}), _html("segredo"))

    async def dns_do_cliente(host: str) -> list[str]:
        return ["10.0.0.1"] if host == "interno.example" else [PUBLICO]

    cliente = _cliente(srv, dns_do_cliente)
    with pytest.raises(ErroDeRede):
        await verificar(cliente.escopo(), _pagina(), resolver=_Dns(PUBLICO))
    assert [str(p.url) for p in srv.pedidos] == [URL]  # o salto nunca sai


# --- mudança de texto -----------------------------------------------------------------------


async def test_mesmo_texto_nao_gera_mudanca(con: sqlite3.Connection) -> None:
    pagina_id = adicionar_pagina(con, URL, "Trainee")
    srv = _Servidor(_html("Inscrições em março"))
    cliente = _cliente(srv)
    for _ in range(2):
        assert await executar_paginas(con, cliente, _RelogioParado(AGORA), resolver=_Dns(PUBLICO))
    assert len(srv.pedidos) == 2
    texto, hash_texto, estado, verificada_em, mudou_em = _linha(con, pagina_id)
    assert texto == "Inscrições em março"  # texto puro: sem tag nem script (14.3)
    assert hash_texto and estado == "ok" and verificada_em is not None
    assert mudou_em is None
    assert mudancas(con) == []
    todas = paginas(con)
    assert len(todas) == 1
    pagina = todas[0]
    assert await verificar(cliente.escopo(), pagina, resolver=_Dns(PUBLICO)) is None


async def test_texto_diferente_grava_diferenca(con: sqlite3.Connection) -> None:
    pagina_id = adicionar_pagina(con, URL, "Trainee")
    srv = _Servidor(
        _html("Programa 2026", "Inscrições fechadas"),
        _html("Programa 2026", "Inscrições abertas até 30/11"),
    )
    cliente = _cliente(srv)
    await executar_paginas(con, cliente, _RelogioParado(AGORA), resolver=_Dns(PUBLICO))
    depois = AGORA + timedelta(days=1)
    await executar_paginas(con, cliente, _RelogioParado(depois), resolver=_Dns(PUBLICO))
    lista = mudancas(con)
    assert len(lista) == 1
    mudanca = lista[0]
    assert mudanca.pagina_id == pagina_id and mudanca.nome == "Trainee" and not mudanca.vista
    assert mudanca.detectada_em == depois
    assert "-Inscrições fechadas" in mudanca.diferenca.splitlines()
    assert "+Inscrições abertas até 30/11" in mudanca.diferenca.splitlines()
    assert " Programa 2026" in mudanca.diferenca.splitlines()  # contexto do difflib
    texto, _, estado, _, mudou_em = _linha(con, pagina_id)
    assert texto == "Programa 2026\nInscrições abertas até 30/11"
    assert estado == "ok" and mudou_em == depois.isoformat()
    marcar_vista(con, mudanca.id)
    assert mudancas(con)[0].vista


async def test_falha_de_rede_marca_estado_sem_apagar_o_texto(con: sqlite3.Connection) -> None:
    quebrada = adicionar_pagina(con, URL, "Trainee")
    outra = adicionar_pagina(con, "https://outra.example/estagio", "Estágio")
    rede_caiu = False

    def responder(pedido: httpx.Request) -> httpx.Response:
        if rede_caiu and pedido.url.host == "empresa.example":
            raise httpx.ConnectError("rede caiu", request=pedido)
        return _html(f"texto de {pedido.url.host}")

    cliente = _cliente(_Servidor(responder))
    await executar_paginas(con, cliente, _RelogioParado(AGORA), resolver=_Dns(PUBLICO))
    antes = _linha(con, quebrada)
    rede_caiu = True
    depois = AGORA + timedelta(days=1)
    await executar_paginas(con, cliente, _RelogioParado(depois), resolver=_Dns(PUBLICO))
    texto, hash_texto, estado, verificada_em, _ = _linha(con, quebrada)
    assert estado == "falhou"
    assert (texto, hash_texto, verificada_em) == (antes[0], antes[1], antes[3])
    assert texto == "texto de empresa.example"
    assert _linha(con, outra)[2] == "ok"  # a falha de uma não afeta as outras
    assert _linha(con, outra)[3] == depois.isoformat()
    assert mudancas(con) == []


# --- Content-Type (D72) ---------------------------------------------------------------------


def _com_tipo(
    tipo: str | None, corpo: bytes = b"<p>Inscri\xc3\xa7\xc3\xb5es abertas</p>"
) -> httpx.Response:
    return httpx.Response(
        200, content=corpo, headers={} if tipo is None else {"Content-Type": tipo}
    )


@pytest.mark.parametrize(
    "tipo",
    [
        "text/html",
        "text/html; charset=utf-8",
        "Text/HTML; Charset=UTF-8",
        "text/plain",
        "application/xhtml+xml",
        None,
    ],
)
async def test_tipo_de_texto_segue_como_html(con: sqlite3.Connection, tipo: str | None) -> None:
    # sem Content-Type não há "outro tipo": segue como hoje (o navegador também lê como texto)
    pagina_id = adicionar_pagina(con, URL, "Trainee")
    cliente = _cliente(_Servidor(_com_tipo(tipo)))
    await executar_paginas(con, cliente, _RelogioParado(AGORA), resolver=_Dns(PUBLICO))
    texto, _, estado, _, _ = _linha(con, pagina_id)
    assert (texto, estado) == ("Inscrições abertas", "ok")


@pytest.mark.parametrize(
    "tipo", ["application/pdf", "image/png", "application/octet-stream", "application/json"]
)
async def test_pagina_com_tipo_que_nao_e_texto_nao_grava_mudanca_e_fica_falhou(
    con: sqlite3.Connection, tipo: str
) -> None:
    pagina_id = adicionar_pagina(con, URL, "Trainee")
    cliente = _cliente(_Servidor(_html("Programa 2026"), _com_tipo(tipo, b"%PDF-1.7 ...")))
    await executar_paginas(con, cliente, _RelogioParado(AGORA), resolver=_Dns(PUBLICO))
    antes = _linha(con, pagina_id)
    depois = AGORA + timedelta(days=1)
    await executar_paginas(con, cliente, _RelogioParado(depois), resolver=_Dns(PUBLICO))
    texto, hash_texto, estado, verificada_em, mudou_em = _linha(con, pagina_id)
    assert estado == "falhou"
    assert (texto, hash_texto, verificada_em, mudou_em) == (
        antes[0],
        antes[1],
        antes[3],
        antes[4],
    )
    assert texto == "Programa 2026"
    assert mudancas(con) == []


async def test_primeira_leitura_de_pdf_fica_falhou_sem_texto(con: sqlite3.Connection) -> None:
    pagina_id = adicionar_pagina(con, URL, "Trainee")
    cliente = _cliente(_Servidor(_com_tipo("application/pdf", b"%PDF-1.7 ...")))
    await executar_paginas(con, cliente, _RelogioParado(AGORA), resolver=_Dns(PUBLICO))
    assert _linha(con, pagina_id) == (None, None, "falhou", None, None)
    assert mudancas(con) == []


async def test_verificar_recusa_tipo_que_nao_e_texto_e_diz_qual() -> None:
    with pytest.raises(ConteudoNaoLido, match="application/pdf"):
        await verificar(
            _cliente(_Servidor(_com_tipo("application/pdf"))).escopo(),
            _pagina(),
            resolver=_Dns(PUBLICO),
        )


# --- batimento (D72) ------------------------------------------------------------------------


class _RelogioDeBatimento(RelogioFalso):
    """Cada `dormir` espera um tique do teste e então anda `s` segundos."""

    def __init__(self, inicio: datetime) -> None:
        super().__init__(inicio)
        self.tiques: asyncio.Queue[None] = asyncio.Queue()

    async def dormir(self, s: float) -> None:
        await self.tiques.get()
        await super().dormir(s)


async def test_execucao_de_paginas_bate_o_batimento(con: sqlite3.Connection) -> None:
    adicionar_pagina(con, URL, "Trainee")
    relogio = _RelogioDeBatimento(AGORA)
    comecou, liberar = asyncio.Event(), asyncio.Event()

    async def segurar(pedido: httpx.Request) -> httpx.Response:
        comecou.set()
        await liberar.wait()
        return _html("Programa 2026")

    def batimento() -> str | None:
        linha = con.execute("SELECT batimento_em FROM execucao WHERE estado = 'rodando'").fetchone()
        return None if linha is None else str(linha[0])

    async def esperar(condicao: Callable[[], bool]) -> None:
        for _ in range(1000):
            if condicao():
                return
            await asyncio.sleep(0)
        raise AssertionError("condição não chegou")

    cliente = ClienteEducado(
        httpx.MockTransport(segurar),
        RelogioFalso(AGORA),
        _Leitor(),
        "9.9.9",
        resolver=_Dns(PUBLICO),
    )
    tarefa = asyncio.create_task(executar_paginas(con, cliente, relogio, resolver=_Dns(PUBLICO)))
    await asyncio.wait_for(comecou.wait(), 5)
    assert batimento() == AGORA.isoformat()
    for n in (1, 2):
        relogio.tiques.put_nowait(None)
        esperado = (AGORA + timedelta(seconds=30 * n)).isoformat()
        await esperar(lambda esperado=esperado: batimento() == esperado)  # type: ignore[misc]
    liberar.set()
    execucao_id = await tarefa

    assert relogio.dormidas == [30.0, 30.0]
    linha = con.execute(
        "SELECT estado, batimento_em FROM execucao WHERE id = ?", (execucao_id,)
    ).fetchone()
    assert tuple(linha) == ("concluida", (AGORA + timedelta(seconds=60)).isoformat())


async def test_erro_fora_da_leitura_interrompe_e_cancela_o_batimento(
    con: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    adicionar_pagina(con, URL, "Trainee")
    from jobot.agenda import paginas as agenda_paginas

    def quebrar(*_: object) -> None:
        raise sqlite3.OperationalError("banco travou")

    monkeypatch.setattr(agenda_paginas, "gravar_leitura", quebrar)
    relogio = _RelogioParado(AGORA)
    antes = len(asyncio.all_tasks())
    with pytest.raises(sqlite3.OperationalError):
        await executar_paginas(
            con, _cliente(_Servidor(_html("x"))), relogio, resolver=_Dns(PUBLICO)
        )
    assert con.execute("SELECT estado FROM execucao").fetchone()[0] == "interrompida"
    assert len(asyncio.all_tasks()) == antes  # o batimento foi cancelado e aguardado


# --- desativar e remover (T112, D72) --------------------------------------------------------


async def test_pagina_desativada_nao_e_verificada(con: sqlite3.Connection) -> None:
    desligada = adicionar_pagina(con, URL, "Trainee")
    ligada = adicionar_pagina(con, "https://outra.example/estagio", "Estágio")
    desativar_pagina(con, desligada)
    srv = _Servidor(_html("texto"))
    await executar_paginas(con, _cliente(srv), _RelogioParado(AGORA), resolver=_Dns(PUBLICO))
    assert [p.url.host for p in srv.pedidos] == ["outra.example"]
    assert _linha(con, desligada) == (None, None, None, None, None)
    assert _linha(con, ligada)[2] == "ok"
    assert {p.id: p.ativa for p in paginas(con)} == {desligada: False, ligada: True}


def test_adicionar_de_novo_reativa_a_pagina_desativada(con: sqlite3.Connection) -> None:
    id_ = adicionar_pagina(con, URL, "Trainee")
    desativar_pagina(con, id_)
    assert [p.ativa for p in paginas(con)] == [False]
    assert adicionar_pagina(con, URL, "Trainee") == id_
    assert [p.ativa for p in paginas(con)] == [True]


async def test_remover_pagina_apaga_as_mudancas_dela(con: sqlite3.Connection) -> None:
    removida = adicionar_pagina(con, URL, "Trainee")
    mantida = adicionar_pagina(con, "https://outra.example/estagio", "Estágio")
    for n, quando in enumerate((AGORA, AGORA + timedelta(days=1)), start=1):
        for id_ in (removida, mantida):
            gravar_leitura(
                con, id_, Mudanca(f"v{n}", f"h{n}", None if n == 1 else "-v1\n+v2"), quando
            )
    assert len(mudancas(con)) == 2

    remover_pagina(con, removida)

    assert [p.id for p in paginas(con)] == [mantida]
    assert [m.pagina_id for m in mudancas(con)] == [mantida]  # a da outra página fica
    assert con.execute(
        "SELECT count(*) FROM mudanca_pagina WHERE pagina_id = ?", (removida,)
    ).fetchone() == (0,)


def test_desativar_e_remover_pagina_inexistente(con: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        desativar_pagina(con, 99)
    with pytest.raises(LookupError):
        remover_pagina(con, 99)


# --- banco ----------------------------------------------------------------------------------


def test_gravar_leitura_e_atomica(con: sqlite3.Connection) -> None:
    pagina_id = adicionar_pagina(con, URL, "Trainee")
    gravar_leitura(con, pagina_id, Mudanca("antes", "h1", None), AGORA)
    con.execute(
        "CREATE TRIGGER quebra BEFORE INSERT ON mudanca_pagina BEGIN SELECT RAISE(ABORT, 'x'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        gravar_leitura(con, pagina_id, Mudanca("depois", "h2", "-antes\n+depois"), AGORA)
    assert _linha(con, pagina_id)[:2] == ("antes", "h1")  # o texto e a diferença saem juntos


def test_marcar_vista_inexistente(con: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        marcar_vista(con, 999)


def test_adicionar_pagina_repetida_atualiza_nome(con: sqlite3.Connection) -> None:
    primeiro = adicionar_pagina(con, URL, "Trainee")
    assert adicionar_pagina(con, URL, "Trainee 2027") == primeiro
    todas = paginas(con)
    assert len(todas) == 1
    pagina = todas[0]
    assert pagina.nome == "Trainee 2027" and pagina.ativa


# --- servidor -------------------------------------------------------------------------------


def test_servir_liga_a_tarefa_paginas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[sqlite3.Connection, ClienteEducado]] = []
    vistas: list[set[str]] = []

    async def executar_falso(
        con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio
    ) -> None:
        chamadas.append((con, cliente))

    async def laco_falso(
        tarefas: Mapping[str, Callable[[], Awaitable[None]]],
        estado: object,
        relogio: Relogio,
        *,
        travas: Mapping[str, asyncio.Lock] | None = None,
    ) -> None:
        vistas.append(set(tarefas))
        if "paginas" in tarefas:
            await tarefas["paginas"]()
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "executar_paginas", executar_falso, raising=False)
    monkeypatch.setattr(servir, "laco", laco_falso)
    app, _ = servir.montar(tmp_path, 47999, relogio=RelogioFalso(AGORA))
    with TestClient(app, base_url="http://127.0.0.1:47999"):
        for _ in range(500):
            if vistas:
                break
            time.sleep(0.01)
        cliente = app.state.cliente
    assert vistas and "paginas" in vistas[0]
    assert len(chamadas) == 1
    con, recebido = chamadas[0]
    assert isinstance(con, sqlite3.Connection) and recebido is cliente


def test_tarefa_paginas_usa_conexao_propria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # T111, D72: a conexão de `executar_paginas` é aberta pela tarefa e fechada ao fim dela;
    # nunca a da leitura dos validadores, nem a de outra tarefa, nem a da volta anterior
    recebidas: dict[str, list[sqlite3.Connection]] = {
        "paginas": [],
        "busca": [],
        "descoberta": [],
        "leitura": [],
    }
    terminou: list[bool] = []

    async def paginas_falso(
        con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio
    ) -> None:
        recebidas["paginas"].append(con)

    async def busca_falsa(
        con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio, motivo: str
    ) -> None:
        recebidas["busca"].append(con)

    async def descoberta_falsa(
        con: sqlite3.Connection, cliente: ClienteEducado, relogio: Relogio
    ) -> None:
        recebidas["descoberta"].append(con)

    class _Validadores(_Leitor):
        def __init__(self, con: sqlite3.Connection) -> None:
            recebidas["leitura"].append(con)

    async def laco_falso(
        tarefas: Mapping[str, Callable[[], Awaitable[None]]],
        estado: object,
        relogio: Relogio,
        *,
        travas: Mapping[str, asyncio.Lock] | None = None,
    ) -> None:
        for nome in ("paginas", "busca", "descoberta", "paginas"):
            await tarefas[nome]()
        terminou.append(True)
        await asyncio.Event().wait()

    monkeypatch.setattr(servir, "executar_paginas", paginas_falso)
    monkeypatch.setattr(servir, "executar_busca", busca_falsa)
    monkeypatch.setattr(servir, "executar_descoberta", descoberta_falsa)
    monkeypatch.setattr(servir, "ValidadoresDoBanco", _Validadores)
    monkeypatch.setattr(servir, "laco", laco_falso)
    app, _ = servir.montar(tmp_path, 47999, relogio=RelogioFalso(AGORA))
    with TestClient(app, base_url="http://127.0.0.1:47999"):
        for _ in range(500):
            if terminou:
                break
            time.sleep(0.01)
        assert terminou
        primeira, segunda = recebidas["paginas"]
        outras = recebidas["busca"] + recebidas["descoberta"] + recebidas["leitura"]
        assert len(outras) == 3
        assert primeira is not segunda
        assert all(p is not o for p in (primeira, segunda) for o in outras)
        for con in (primeira, segunda):  # fechada pela própria tarefa, com a agenda ainda viva
            with pytest.raises(sqlite3.ProgrammingError):
                con.execute("SELECT 1")
