"""Descoberta de empresas pelo índice bruto do Common Crawl (plano T71; desenho 8.7; apêndice 5).

O índice falso fica em `fixtures/common_crawl`: um `cluster.idx` de 8 blocos e dois arquivos
`cdx-*.gz` com os blocos gzip um atrás do outro, no formato real. O servidor falso serve só o
pedaço do `Range`, como o `data.commoncrawl.org`. Os ATS respondem pelo Greenhouse e pela Gupy
(só `beta`, com o nome da página diferente do subdomínio); Lever e Ashby devolvem 404.
"""

import json
import sqlite3
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.agenda.descoberta import CHAVE_INDICE, executar_descoberta
from jobot.banco.cadastros import (
    adicionar_empresa,
    empresas,
    gravar_config,
    remover_empresa,
    semear,
)
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.sugeridas import aprovar, descartar, gravar_sugestoes, sugeridas
from jobot.nucleo.coletores import descoberta_cc
from jobot.nucleo.coletores.descoberta_cc import Sugestao, indice_mais_novo, sugerir
from jobot.nucleo.http import (
    ClienteEducado,
    LimiteAtingido,
    OrcamentoGasto,
    RespostaGrande,
    Validadores,
)
from jobot.nucleo.modelo import Empresa

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[1] / "fixtures" / "common_crawl"
INDICE = "CC-MAIN-2026-43"
DADOS = f"https://data.commoncrawl.org/cc-index/collections/{INDICE}/indexes/"
TITULO = "Pessoa Desenvolvedora Python"
# alfa em São Paulo, delta só em Berlim, epsilon remota; os outros quadros dão 404
QUADROS = {
    "alfa": ("São Paulo, SP", TITULO),
    "delta": ("Berlin, Germany", TITULO),
    "epsilon": ("Remote", f"{TITULO} (Remote)"),  # a modalidade sai do título (rótulos 10.4)
}
GUPY_NOME = "Beta Tech"  # o publicationName da página de beta.gupy.io: a API casa com caixa exata
GUPY_PAGINA = (
    '<script id="__NEXT_DATA__" type="application/json">'
    '{"props":{"pageProps":{"careerPage":{"publicationName":"Beta Tech "}}}}</script>'
)


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


@dataclass
class Servidor:
    """Common Crawl e ATS falsos; guarda cada pedido com a hora do relógio."""

    relogio: RelogioFalso
    collinfo: bytes = (PASTA / "collinfo.json").read_bytes()
    status_cc: int = 200  # 503 faz o Common Crawl recusar tudo
    pedaco: int = 64  # o cluster.idx chega em pedaços deste tamanho
    pedidos: list[tuple[httpx.Request, datetime]] = field(default_factory=list)
    pedacos_lidos: int = 0

    def urls(self, host: str) -> list[str]:
        return [str(p.url) for p, _ in self.pedidos if p.url.host == host]

    async def _cluster(self) -> AsyncIterator[bytes]:
        corpo = (PASTA / "cluster.idx").read_bytes()
        for i in range(0, len(corpo), self.pedaco):
            self.pedacos_lidos += 1
            yield corpo[i : i + self.pedaco]

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append((pedido, self.relogio.agora()))
        host, caminho = pedido.url.host, pedido.url.path
        if host.endswith("commoncrawl.org") and self.status_cc != 200:
            return httpx.Response(self.status_cc)
        if host == "index.commoncrawl.org" and caminho == "/collinfo.json":
            return httpx.Response(200, content=self.collinfo)
        if host == "data.commoncrawl.org" and caminho.endswith("/cluster.idx"):
            return httpx.Response(200, content=self._cluster())
        if host == "data.commoncrawl.org" and caminho.endswith(".gz"):
            inicio, fim = pedido.headers["Range"].removeprefix("bytes=").split("-")
            corpo = (PASTA / caminho.rsplit("/", 1)[1]).read_bytes()
            return httpx.Response(206, content=corpo[int(inicio) : int(fim) + 1])
        if host == "boards-api.greenhouse.io":
            token = caminho.split("/")[3]
            if token not in QUADROS:
                return httpx.Response(404, json={"status": 404, "error": "Job not found"})
            local, titulo = QUADROS[token]
            vaga = {
                "id": 1,
                "title": titulo,
                "company_name": token.title(),
                "absolute_url": f"https://job-boards.greenhouse.io/{token}/jobs/1",
                "location": {"name": local},
                "content": "",
            }
            return httpx.Response(200, json={"jobs": [vaga], "meta": {"total": 1}})
        if host == "beta.gupy.io" and caminho == "/":
            return httpx.Response(200, text=GUPY_PAGINA)
        if host == "portal.gupy.io":
            vagas = []
            if pedido.url.params.get("careerPageName") == GUPY_NOME:
                vagas = [
                    {
                        "id": 7,
                        "name": TITULO,
                        "careerPageName": GUPY_NOME,
                        "jobUrl": "https://beta.gupy.io/job/7?jobBoardSource=gupy_portal",
                        "city": "Florianópolis",
                        "state": "Santa Catarina",
                        "workplaceType": "on-site",
                        "description": "",
                    }
                ]
            return httpx.Response(200, json={"data": vagas, "pagination": {"limit": 100}})
        return httpx.Response(404)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    with closing(abrir(caminho)) as c:
        migrar(c, caminho)
        semear(c)
        yield c


@pytest.fixture
def fuso_local() -> Iterator[None]:
    """Fuso -03 sem depender do tzdata da máquina; desfeito no fim."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TZ", "<-03>3")
        time.tzset()
        yield
    time.tzset()


def _cliente(servidor: Servidor) -> ClienteEducado:
    return ClienteEducado(
        httpx.MockTransport(servidor), servidor.relogio, LeitorFixo(), "0.1.0", resolver=_sem_dns
    )


async def _descobrir(
    con: sqlite3.Connection, inicio: datetime | None = None, **opcoes: object
) -> Servidor:
    relogio = RelogioFalso(inicio)
    servidor = Servidor(relogio, **opcoes)  # type: ignore[arg-type]
    cliente = _cliente(servidor)
    try:
        await executar_descoberta(con, cliente, relogio)
    finally:
        await cliente.fechar()
    return servidor


async def _sugerir(servidor: Servidor) -> list[Sugestao]:
    cliente = _cliente(servidor)
    try:
        return await sugerir(cliente, await indice_mais_novo(cliente))
    finally:
        await cliente.fechar()


def _estados(con: sqlite3.Connection) -> list[str]:
    return [e for (e,) in con.execute("SELECT estado FROM execucao WHERE tipo = 'descoberta'")]


async def test_so_roda_com_indice_novo(con: sqlite3.Connection) -> None:
    primeira = await _descobrir(con)
    assert primeira.urls("data.commoncrawl.org")[0] == DADOS + "cluster.idx"
    assert con.execute("SELECT valor FROM config WHERE chave = ?", (CHAVE_INDICE,)).fetchone() == (
        json.dumps(INDICE),
    )

    mesma = await _descobrir(con)
    assert mesma.urls("index.commoncrawl.org") == ["https://index.commoncrawl.org/collinfo.json"]
    assert mesma.urls("data.commoncrawl.org") == []  # índice já processado: nada a baixar

    lista = json.loads(primeira.collinfo)
    lista.insert(0, {"id": "CC-MAIN-2026-47", "name": "Novembro 2026 Index"})
    nova = await _descobrir(con, collinfo=json.dumps(lista).encode())
    assert nova.urls("data.commoncrawl.org")[0] == DADOS.replace(INDICE, "CC-MAIN-2026-47") + (
        "cluster.idx"
    )
    assert _estados(con) == ["concluida", "concluida", "concluida"]

    gravar_config(con, "descoberta_cc_ligada", False)
    desligada = await _descobrir(con, datetime(2026, 11, 20, 12, 0, tzinfo=UTC))
    assert desligada.pedidos == []


async def test_cluster_idx_em_fluxo_com_teto_de_128_mb(monkeypatch: pytest.MonkeyPatch) -> None:
    assert descoberta_cc.TETO_CLUSTER == 128 * 1024 * 1024
    servidor = Servidor(RelogioFalso(), pedaco=16)
    assert len(await _sugerir(servidor)) > 0
    total = servidor.pedacos_lidos
    assert total > 1  # leu pedaço por pedaço, sem pedir o arquivo de uma vez

    monkeypatch.setattr(descoberta_cc, "TETO_CLUSTER", 100)
    curto = Servidor(RelogioFalso(), pedaco=16)
    with pytest.raises(RespostaGrande):
        await _sugerir(curto)
    assert curto.pedacos_lidos < total  # parou no teto, sem ler o resto


async def test_blocos_por_range() -> None:
    servidor = Servidor(RelogioFalso())
    await _sugerir(servidor)
    blocos = [
        (str(p.url), p.headers["Range"])
        for p, _ in servidor.pedidos
        if p.url.host == "data.commoncrawl.org" and p.url.path.endswith(".gz")
    ]
    assert blocos == [
        (DADOS + "cdx-00000.gz", "bytes=0-252"),
        (DADOS + "cdx-00000.gz", "bytes=253-520"),
        (DADOS + "cdx-00000.gz", "bytes=731-966"),  # o anterior ao primeiro do greenhouse
        (DADOS + "cdx-00001.gz", "bytes=0-367"),
        (DADOS + "cdx-00001.gz", "bytes=368-591"),
    ]


async def test_prefixos_dos_quatro_ats() -> None:
    achadas = await _sugerir(Servidor(RelogioFalso()))
    assert {(s.fonte, s.identificador) for s in achadas} == {
        ("lever", "acme"),
        ("lever", "Beta"),
        ("ashby", "Gama"),
        ("greenhouse", "alfa"),
        ("greenhouse", "delta"),
        ("greenhouse", "epsilon"),
        ("greenhouse", "zeta"),
        ("gupy", "acme"),
        ("gupy", "beta"),
    }
    lever_beta = next(s for s in achadas if s.identificador == "Beta")
    assert lever_beta.url_exemplo.startswith("https://jobs.lever.co/Beta/")


async def test_10_s_entre_pedidos() -> None:
    servidor = Servidor(RelogioFalso())
    await _sugerir(servidor)
    horas = [t for p, t in servidor.pedidos if p.url.host == "data.commoncrawl.org"]
    assert len(horas) == 6  # cluster.idx e cinco blocos
    assert all((b - a).total_seconds() >= 10 for a, b in zip(horas, horas[1:], strict=False))


async def test_503_para_ate_o_dia_seguinte(con: sqlite3.Connection, fuso_local: None) -> None:
    # 02:00 UTC do dia 14 ainda é 23:00 do dia 13 em -03
    relogio = RelogioFalso(datetime(2026, 11, 14, 2, 0, tzinfo=UTC))
    parada = Servidor(relogio, status_cc=503)
    cliente = _cliente(parada)
    try:
        with pytest.raises((LimiteAtingido, OrcamentoGasto)):
            await executar_descoberta(con, cliente, relogio)
    finally:
        await cliente.fechar()
    assert len(parada.pedidos) == 2  # um pedido e uma nova tentativa, nada mais
    assert _estados(con) == ["interrompida"]

    mesma_noite = await _descobrir(con, datetime(2026, 11, 14, 2, 30, tzinfo=UTC))
    assert mesma_noite.pedidos == []  # o laço chama de novo, mas o dia local ainda é 13

    dia_seguinte = await _descobrir(con, datetime(2026, 11, 14, 4, 0, tzinfo=UTC))
    assert dia_seguinte.urls("index.commoncrawl.org")  # 01:00 do dia 14: volta a pedir
    assert _estados(con) == ["interrompida", "concluida"]


async def test_so_sugere_com_vaga_no_brasil_ou_remota(con: sqlite3.Connection) -> None:
    servidor = await _descobrir(con)
    assert sorted((s.fonte, s.identificador) for s in sugeridas(con)) == [
        ("greenhouse", "alfa"),
        ("greenhouse", "epsilon"),
        ("gupy", "beta"),
    ]
    # a Gupy é testada pelo nome lido na página, sem os espaços das pontas e com a caixa exata
    nomes = [p.url.params.get("careerPageName") for p, _ in servidor.pedidos]
    assert [n for n in nomes if n] == [GUPY_NOME]


async def test_aprovar_cria_empresa_com_origem_descoberta(con: sqlite3.Connection) -> None:
    await _descobrir(con)
    por_nome = {s.identificador: s for s in sugeridas(con)}
    alfa, epsilon, beta = por_nome["alfa"], por_nome["epsilon"], por_nome["beta"]
    empresa_id = aprovar(con, alfa.id)
    nova = next(e for e in empresas(con) if e.id == empresa_id)
    assert (nova.fonte, nova.identificador, nova.origem) == ("greenhouse", "alfa", "descoberta")
    descartar(con, epsilon.id)
    descartar(con, beta.id)
    assert sugeridas(con) == []
    with pytest.raises(LookupError):
        aprovar(con, epsilon.id)  # descartada não volta
    with pytest.raises(LookupError):
        descartar(con, alfa.id)


async def test_nao_sugere_empresa_ja_cadastrada(con: sqlite3.Connection) -> None:
    agora = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    alfa = adicionar_empresa(
        con, Empresa(nome="Alfa", fonte="greenhouse", identificador="ALFA", origem="pessoa")
    )
    remover_empresa(con, alfa, agora)  # removida também conta como cadastrada
    servidor = await _descobrir(con)
    assert not any("/boards/alfa/" in u.lower() for u in servidor.urls("boards-api.greenhouse.io"))
    assert [s.identificador for s in sugeridas(con)] == ["epsilon", "beta"]
    repetida = Sugestao("greenhouse", "Epsilon", "https://boards.greenhouse.io/Epsilon")
    assert (
        gravar_sugestoes(con, [repetida, Sugestao("greenhouse", "alfa", "https://x.io/")], agora)
        == 0
    )


def _empresa(con: sqlite3.Connection, fonte: str, identificador: str) -> list[tuple[object, ...]]:
    return con.execute(
        "SELECT id, nome, identificador, parametros, removida_em, origem FROM empresa"
        " WHERE fonte = ? AND lower(identificador) = lower(?)",
        (fonte, identificador),
    ).fetchall()


def test_aprovar_nao_sobrescreve_empresa_cadastrada_depois(con: sqlite3.Connection) -> None:
    agora = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    novas = [
        Sugestao("greenhouse", "alfa", "https://boards.greenhouse.io/alfa"),
        Sugestao("gupy", "beta", "https://beta.gupy.io/"),
    ]
    assert gravar_sugestoes(con, novas, agora) == 2
    alfa_s, beta_s = sugeridas(con)
    # depois da sugestão a pessoa cadastra Alfa (outra caixa) e cadastra e remove beta
    alfa = adicionar_empresa(
        con,
        Empresa(nome="Alfa Curada", fonte="greenhouse", identificador="Alfa", origem="pessoa"),
    )
    beta = adicionar_empresa(
        con,
        Empresa(
            nome="Beta Tech",
            fonte="gupy",
            identificador="beta",
            parametros={"careerPageName": "Beta Tech"},
            origem="pessoa",
        ),
    )
    remover_empresa(con, beta, agora)
    antes = _empresa(con, "greenhouse", "alfa") + _empresa(con, "gupy", "beta")
    total = con.execute("SELECT count(*) FROM empresa").fetchone()

    assert aprovar(con, alfa_s.id) == alfa
    assert aprovar(con, beta_s.id, nome="beta") == beta
    assert _empresa(con, "greenhouse", "alfa") + _empresa(con, "gupy", "beta") == antes
    assert con.execute("SELECT count(*) FROM empresa").fetchone() == total  # sem linha nova
    assert [e for (e,) in con.execute("SELECT estado FROM empresa_sugerida")] == [
        "aprovada",
        "aprovada",
    ]


def test_aprovar_contra_descartar_le_dentro_da_transacao(con: sqlite3.Connection) -> None:
    agora = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    gravar_sugestoes(con, [Sugestao("greenhouse", "alfa", "https://x.io/alfa")], agora)
    (sugestao,) = sugeridas(con)
    caminho = Path(con.execute("PRAGMA database_list").fetchone()[2])
    outra = abrir(caminho)
    outra.execute("PRAGMA busy_timeout=0")
    erros: list[BaseException] = []
    no_begin = threading.Event()

    def aprovar_concorrente() -> None:
        c = abrir(caminho)
        # o BEGIN do fio chega ao SQLite: o código sem trava já leu a sugestão pendente
        c.set_trace_callback(lambda sql: no_begin.set() if sql.startswith("BEGIN") else None)
        try:
            aprovar(c, sugestao.id)
        except BaseException as e:  # noqa: BLE001 - o teste confere o erro na lista
            erros.append(e)
        finally:
            c.close()

    fio = threading.Thread(target=aprovar_concorrente)
    try:
        outra.execute("BEGIN IMMEDIATE")  # segura a escrita
        fio.start()
        assert no_begin.wait(timeout=10)
        descartar_sql = "UPDATE empresa_sugerida SET estado = 'descartada' WHERE id = ?"
        outra.execute(descartar_sql, (sugestao.id,))
        outra.commit()
        fio.join(timeout=10)
    finally:
        outra.close()
    assert not fio.is_alive()
    assert [type(e) for e in erros] == [LookupError]  # a sugestão já foi descartada
    assert _empresa(con, "greenhouse", "alfa") == []
    assert con.execute("SELECT estado FROM empresa_sugerida").fetchall() == [("descartada",)]
