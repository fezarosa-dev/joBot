# As fixtures `con` e `montagem` vêm da T213: o parâmetro de cada teste as redefine (F811).
# ruff: noqa: F811
"""O detalhe da vaga na execução `login` (T214; D132.19, D132.32).

Os leitores cuja lista não traz a descrição (`lista_tem_descricao` falso) têm a página de cada
vaga aberta depois de gravados os escopos do site, com cache de 30 dias por URL e teto de
`limites.MAX_VAGA` páginas por site. A montagem, o banco e os ajudantes são os da T213.
"""

import sqlite3
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import pytest

from apoio.site_falso import RelogioDoNavegador, SiteFalso
from jobot.banco.execucoes import abrir_execucao, fechar_execucao
from jobot.banco.gravacao import gravar_cache_detalhe
from jobot.banco.gravacao import gravar_escopo as gravar_escopo_do_banco
from jobot.navegador import limites
from jobot.nucleo.coletores.base import ResultadoEscopo
from jobot.nucleo.coletores.executor import SaidaEscopo
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.tratamento.tratar import tratar
from navegador.test_execucao_logada import (
    ANTES,
    INICIO,
    LeitorDeTeste,
    Montagem,
    _ligar,
    _rodar,
    con,  # noqa: F401  (fixture da T213)
    montagem,  # noqa: F401  (fixture da T213)
)

pytestmark = [pytest.mark.tela, pytest.mark.anyio]


@dataclass
class LeitorDeDetalhe(LeitorDeTeste):
    """Leitor cuja lista não traz a descrição; anota as páginas de vaga que `detalhar` recebeu."""

    lista_tem_descricao: bool = False
    sem_detalhe: bool = False  # `detalhar` devolve `None`, como numa vaga que saiu do ar
    abertas: list[str] = field(default_factory=list)

    def detalhar(self, captura: Any, vaga: VagaColetada) -> VagaColetada | None:
        self.abertas.append(urlsplit(vaga.url).path)
        return None if self.sem_detalhe else super().detalhar(captura, vaga)


def _leitor(site: SiteFalso, *escopos: tuple[str, str], **mudancas: Any) -> LeitorDeDetalhe:
    urls = tuple((i, site.url(c)) for i, c in escopos)
    return LeitorDeDetalhe(base=site.url(""), urls=urls, **mudancas)


@pytest.fixture(autouse=True)
def _so_leitura(site: SiteFalso) -> Iterator[None]:
    yield
    assert (site.posts, site.campos_mudados) == (0, 0)


def _semear_com(
    con: sqlite3.Connection,
    quando: datetime,
    fonte: str,
    escopo: str,
    vagas: Mapping[str, str],  # URL -> descrição
) -> None:
    """Uma execução antiga, já fechada, com as vagas dadas (e a descrição que cada uma tem)."""
    execucao_id = abrir_execucao(con, "login", "agenda", quando)
    assert execucao_id is not None
    coletadas = tuple(
        VagaColetada(
            fonte=fonte,
            escopo=escopo,
            url=url,
            titulo="Vaga antiga",
            empresa="Empresa antiga",
            descricao=descricao,
            descricao_formato="texto",
        )
        for url, descricao in vagas.items()
    )
    saida = SaidaEscopo(fonte, escopo, ResultadoEscopo(coletadas, "ok", None, 1), 0, {})
    gravar_escopo_do_banco(con, execucao_id, saida, [tratar(v) for v in coletadas], quando)
    fechar_execucao(con, execucao_id, quando)


def _ocorrencia(con: sqlite3.Connection, fonte: str, url: str) -> int:
    linha = con.execute(
        "SELECT o.id FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id"
        " WHERE o.fonte = ? AND v.url = ?",
        (fonte, url),
    ).fetchone()
    return int(linha[0])


def _descricoes(con: sqlite3.Connection, fonte: str) -> dict[str, str]:
    """Descrição gravada na ocorrência de cada vaga da fonte, por caminho."""
    linhas = con.execute(
        "SELECT v.url, o.coletada FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id"
        " WHERE o.fonte = ?",
        (fonte,),
    ).fetchall()
    return {urlsplit(u).path: VagaColetada.de_json(c).descricao for u, c in linhas}


def _conteudos(con: sqlite3.Connection) -> list[str]:
    return [c for (c,) in con.execute("SELECT conteudo FROM enriquecimento ORDER BY url_hash")]


async def test_so_abre_vaga_sem_descricao_e_sem_detalhe_recente_mais_novas_primeiro(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("x", "/paginada"))  # as vagas 1 a 4
    _ligar(con, leitor)
    # a 1 já tem descrição (a lista vazia não a apaga); a 3 é antiga e a 4 já foi tentada ontem
    antigas = {site.url("/vaga/1"): "Já descrita", site.url("/vaga/3"): "", site.url("/vaga/4"): ""}
    _semear_com(con, ANTES, leitor.chave, "x", antigas)
    gravar_cache_detalhe(
        con,
        _ocorrencia(con, leitor.chave, site.url("/vaga/4")),
        site.url("/vaga/4"),
        None,
        INICIO - timedelta(days=1),
    )
    assert await _rodar(con, [leitor], montagem.deps()) is not None
    # a 2 é a mais nova (vista agora), depois a 3 (vista há três dias)
    assert leitor.abertas == ["/vaga/2", "/vaga/3"]
    assert site.visitas["/vaga/1"] == site.visitas["/vaga/4"] == 0


@pytest.mark.parametrize(
    ("dias", "abertas"),
    [
        pytest.param(29, ["/vaga/1"], id="ha_29_dias"),
        pytest.param(31, ["/vaga/1", "/vaga/2"], id="ha_31_dias"),
    ],
)
async def test_nao_abre_url_detalhada_por_outra_fonte_ha_menos_de_30_dias(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    dias: int,
    abertas: list[str],
) -> None:
    leitor = _leitor(site, ("x", "/lista-html"))  # as vagas 1 e 2
    _ligar(con, leitor)
    url = site.url("/vaga/2")
    _semear_com(con, ANTES, "publica", "geral", {url: ""})
    gravar_cache_detalhe(con, _ocorrencia(con, "publica", url), url, None, INICIO - timedelta(dias))
    assert await _rodar(con, [leitor], montagem.deps()) is not None
    assert leitor.abertas == abertas


@pytest.mark.parametrize("sem_detalhe", [False, True], ids=["com_detalhe", "detalhar_none"])
async def test_cada_pagina_aberta_grava_enriquecimento(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection, sem_detalhe: bool
) -> None:
    leitor = _leitor(site, ("x", "/lista-html"), sem_detalhe=sem_detalhe)
    _ligar(con, leitor)
    assert await _rodar(con, [leitor], montagem.deps()) is not None
    assert leitor.abertas == ["/vaga/1", "/vaga/2"]
    conteudos = _conteudos(con)
    assert len(conteudos) == 2
    if sem_detalhe:
        assert conteudos == ["", ""]
        assert _descricoes(con, leitor.chave) == {"/vaga/1": "", "/vaga/2": ""}
    else:
        assert all(conteudos)
        assert _descricoes(con, leitor.chave) == {
            "/vaga/1": "Descrição da vaga 1",
            "/vaga/2": "Descrição da vaga 2",
        }


async def test_teto_de_20_vagas_e_o_resto_volta_depois(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # teto menor, a mesma regra: cada página aberta custa ~0,6 s reais (o valor 20 se prende
    # em tests/unidade/test_navegador_abrir.py)
    monkeypatch.setattr(limites, "MAX_VAGA", 3)
    leitor = _leitor(site, ("x", "/lista-5"))
    _ligar(con, leitor)
    assert await _rodar(con, [leitor], montagem.deps()) is not None
    assert len(leitor.abertas) == 3  # o teto
    assert len(_conteudos(con)) == 3
    primeiras = set(leitor.abertas)
    relogio = RelogioDoNavegador(INICIO + timedelta(hours=4))
    assert await _rodar(con, [leitor], montagem.deps(), relogio) is not None
    segundas = leitor.abertas[3:]
    assert len(segundas) == 2
    assert not primeiras & set(segundas)
    assert len(_conteudos(con)) == 5


async def test_espera_antes_das_paginas_de_vaga(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("x", "/lista-html"))
    _ligar(con, leitor)
    sorteios = iter([3.5, 4.5, 5.5, 6.5])
    relogio = RelogioDoNavegador()
    assert await _rodar(con, [leitor], montagem.deps(lambda: next(sorteios)), relogio) is not None
    assert leitor.abertas == ["/vaga/1", "/vaga/2"]
    # a entrada não espera; a lista e cada uma das duas vagas esperam um sorteio
    assert relogio.dormidas == [3.5, 4.5, 5.5]


async def test_descricao_antiga_fica_depois_de_nova_leitura_da_lista(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("x", "/lista-html"))
    _ligar(con, leitor)
    assert await _rodar(con, [leitor], montagem.deps()) is not None
    descritas = {"/vaga/1": "Descrição da vaga 1", "/vaga/2": "Descrição da vaga 2"}
    assert _descricoes(con, leitor.chave) == descritas
    relogio = RelogioDoNavegador(INICIO + timedelta(hours=4))
    assert await _rodar(con, [leitor], montagem.deps(), relogio) is not None
    assert site.visitas["/lista-html"] == 2  # a lista foi lida de novo, sem descrição
    assert _descricoes(con, leitor.chave) == descritas
    assert leitor.abertas == ["/vaga/1", "/vaga/2"]  # e nenhuma vaga foi aberta outra vez


async def test_lista_com_descricao_nao_abre_vaga(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    com_descricao = _leitor(site, ("x", "/lista-html"), lista_tem_descricao=True)
    controle = _leitor(site, ("y", "/quatro?q=a&p=4"), chave="outro_logado")  # só a vaga 40
    _ligar(con, com_descricao, controle)
    assert await _rodar(con, [com_descricao, controle], montagem.deps()) is not None
    assert controle.abertas == ["/vaga/40"]
    assert com_descricao.abertas == []
    assert site.visitas["/vaga/1"] == site.visitas["/vaga/2"] == 0


async def test_so_abre_vaga_dos_escopos_lidos_agora(
    site: SiteFalso,
    montagem: Montagem,
    con: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limites, "MAX_LISTA", 2)  # a entrada e um escopo
    leitor = _leitor(site, ("a", "/lista-html"), ("c", "/paginada"))
    _ligar(con, leitor)
    _semear_com(con, ANTES, leitor.chave, "c", {site.url("/vaga/99"): ""})  # "c" fica sem ler
    assert await _rodar(con, [leitor], montagem.deps()) is not None
    assert leitor.abertas == ["/vaga/1", "/vaga/2"]
    assert site.visitas["/vaga/99"] == 0


async def test_vaga_em_dois_escopos_abre_uma_pagina_so(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    leitor = _leitor(site, ("a", "/lista-html?q=a"), ("b", "/lista-html?q=b"))
    _ligar(con, leitor)
    assert await _rodar(con, [leitor], montagem.deps()) is not None
    assert sorted(leitor.abertas) == ["/vaga/1", "/vaga/2"]


async def test_site_que_parou_no_meio_nao_abre_vaga(
    site: SiteFalso, montagem: Montagem, con: sqlite3.Connection
) -> None:
    parado = _leitor(site, ("a", "/lista-e-login"))  # a segunda página é a de login
    controle = _leitor(site, ("b", "/quatro?q=a&p=4"), chave="outro_logado")  # só a vaga 40
    _ligar(con, parado, controle)
    assert await _rodar(con, [parado, controle], montagem.deps()) is not None
    assert parado.abertas == []
    assert site.visitas["/vaga/1"] == site.visitas["/vaga/2"] == 0
    assert controle.abertas == ["/vaga/40"]
