"""Leitura e busca do painel (desenho 13.3 e 13.4; plano T20)."""

import sqlite3
import time
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from apoio.semear import AGORA, inserir_vaga, semear
from jobot.banco import migrar as modulo_migrar
from jobot.banco.conexao import abrir
from jobot.banco.leitura import Filtros, Pagina, contar_abas, contar_chips, detalhe, listar
from jobot.banco.migrar import migrar

# RF1: nada disso pode virar sintaxe do FTS5 nem do LIKE
SINTAXE = [
    '"',
    '""',
    "*",
    "-",
    ":",
    "(",
    ")",
    "^",
    "+",
    "OR",
    "AND",
    "NOT",
    "NEAR",
    "c++",
    "c#",
    "python OR",
    '"aberto',
    "titulo:python",
    "-python",
    "(python",
    "python*",
    "NEAR(a b)",
    "'",
    "%",
    "_",
    "\\",
    "{titulo}: x",
    "\x00",
    "a\x00",
    "a\x00b",
    '\x00"*',
    "a\ud800",
]


def _banco(caminho: Path) -> sqlite3.Connection:
    con = abrir(caminho)
    migrar(con, caminho)
    return con


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    c = _banco(tmp_path / "jobot.db")
    yield c
    c.close()


@pytest.fixture
def ids(con: sqlite3.Connection) -> dict[str, int]:
    return semear(con)


def _pagina(con: sqlite3.Connection, **campos: Any) -> Pagina:
    return listar(con, Filtros(**campos), AGORA)


def _lista(con: sqlite3.Connection, **campos: Any) -> list[int]:
    return [item.id for item in _pagina(con, **campos).itens]


def _tem_fts(con: sqlite3.Connection) -> bool:
    sql = "SELECT 1 FROM sqlite_master WHERE name = 'vaga_fts'"
    return con.execute(sql).fetchone() is not None


def test_semear_traz_o_conjunto_fechado(tmp_path: Path) -> None:
    caminho = tmp_path / "jobot.db"
    con = _banco(caminho)
    ids = semear(con)
    con.close()
    # outra conexão: só enxerga o que foi commitado
    con = abrir(caminho)

    def um(sql: str, *params: object) -> tuple[object, ...]:
        linha: tuple[object, ...] | None = con.execute(sql, params).fetchone()
        assert linha is not None, sql
        return linha

    assert {
        "usd",
        "brl",
        "himalayas",
        "script",
        "fechada_salva",
        "oculta_regra",
        "oculta_manual",
        "nova",
        "prazo_3_dias",
        "prazo_vencido",
        "trainee",
        "busca",
    } <= ids.keys()
    sql_sal = (
        "SELECT sal_moeda, sal_mensal_min, sal_mensal_min_brl, sal_periodo, sal_cotacao_data"
        " FROM vaga WHERE id = ?"
    )
    assert um(sql_sal, ids["usd"]) == ("USD", 500000, 28250, "mes", "2026-11-13")
    assert um("SELECT venda FROM cotacao WHERE moeda = 'USD' AND data = '2026-11-13'") == ("5.65",)
    moeda, _, brl, _, cotacao = um(sql_sal, ids["brl"])
    assert (moeda, cotacao) == ("BRL", None) and brl is not None
    fonte, url, coletada = um(
        "SELECT fonte, url, json_extract(coletada, '$.url_candidatura') FROM ocorrencia"
        " WHERE vaga_id = ?",
        ids["himalayas"],
    )
    assert fonte == "himalayas" and coletada is not None and coletada != url
    assert "<script>" in str(um("SELECT descricao_texto FROM vaga WHERE id = ?", ids["script"])[0])
    assert um(
        "SELECT status, fechada_em IS NOT NULL FROM vaga WHERE id = ?", ids["fechada_salva"]
    ) == (
        "salva",
        1,
    )
    assert um(
        "SELECT v.oculta_manual, e.oculta_motivo FROM vaga v JOIN encaixe e ON e.vaga_id = v.id"
        " WHERE v.id = ? AND e.busca_id = ?",
        ids["oculta_regra"],
        ids["busca"],
    ) == (0, "modalidade")
    assert um("SELECT oculta_manual FROM vaga WHERE id = ?", ids["oculta_manual"]) == (1,)
    assert um(
        "SELECT status, julianday(?) - julianday(primeira_vista_em) < 3 FROM vaga WHERE id = ?",
        AGORA.isoformat(),
        ids["nova"],
    ) == ("nova", 1)
    assert um("SELECT prazo FROM vaga WHERE id = ?", ids["prazo_3_dias"]) == ("2026-11-16",)
    assert str(um("SELECT prazo FROM vaga WHERE id = ?", ids["prazo_vencido"])[0]) < "2026-11-13"
    assert um("SELECT contrato FROM vaga WHERE id = ?", ids["trainee"]) == ("trainee",)
    assert um("SELECT nome FROM busca WHERE id = ?", ids["busca"]) == ("Python remoto",)
    con.close()


def test_abas(con: sqlite3.Connection, ids: dict[str, int]) -> None:
    b = ids["busca"]
    visiveis = {ids[n] for n in ("usd", "brl", "himalayas", "script", "nova", "prazo_3_dias")}
    visiveis.add(ids["trainee"])
    assert set(_lista(con, aba="todas", busca_id=b)) == visiveis
    assert _lista(con, aba="novas", busca_id=b) == [ids["nova"]]
    # prazo em 3 dias entra; prazo vencido sai de todas as listas
    assert _lista(con, aba="fecham_logo", busca_id=b) == [ids["prazo_3_dias"]]
    assert _lista(con, aba="programas", busca_id=b) == [ids["trainee"]]
    salvas = _pagina(con, aba="salvas", busca_id=b).itens
    assert [(i.id, i.fechada) for i in salvas] == [(ids["fechada_salva"], True)]
    ocultas = {i.id: i.oculta_motivo for i in _pagina(con, aba="ocultas", busca_id=b).itens}
    assert ocultas == {ids["oculta_regra"]: "modalidade", ids["oculta_manual"]: "manual"}
    assert contar_abas(con, b, AGORA) == {
        "todas": 7,
        "novas": 1,
        "fecham_logo": 1,
        "salvas": 1,
        "candidatei": 0,
        "programas": 1,
        "ocultas": 2,
    }
    chips = contar_chips(con, Filtros(aba="ocultas", busca_id=b), AGORA)
    assert chips["motivo"] == {"modalidade": 1, "manual": 1}

    # candidatei: fechada continua, com selo (DR-24)
    con.execute(
        "UPDATE vaga SET status = 'entrevista', fechada_em = ? WHERE id = ?",
        (AGORA.isoformat(), ids["brl"]),
    )
    candidatei = _pagina(con, aba="candidatei", busca_id=b).itens
    assert [(i.id, i.fechada, i.status) for i in candidatei] == [(ids["brl"], True, "entrevista")]
    assert ids["brl"] not in _lista(con, aba="todas", busca_id=b)

    # DP2: -1 ("mostrar mesmo assim") vence a regra
    con.execute("UPDATE vaga SET oculta_manual = -1 WHERE id = ?", (ids["oculta_regra"],))
    assert ids["oculta_regra"] in _lista(con, aba="todas", busca_id=b)
    assert ids["oculta_regra"] not in _lista(con, aba="ocultas", busca_id=b)

    # Novas: só status nova; vista há mais de 72 h sai
    con.execute("UPDATE vaga SET status = 'salva' WHERE id = ?", (ids["nova"],))
    assert _lista(con, aba="novas", busca_id=b) == []
    velha = (AGORA - timedelta(hours=73)).isoformat()
    con.execute(
        "UPDATE vaga SET status = 'nova', primeira_vista_em = ? WHERE id = ?", (velha, ids["nova"])
    )
    assert _lista(con, aba="novas", busca_id=b) == []


def test_chips_contam_com_os_outros_filtros(con: sqlite3.Connection, ids: dict[str, int]) -> None:
    b = ids["busca"]
    f = Filtros(busca_id=b, modalidade="presencial")
    chips = contar_chips(con, f, AGORA)
    # o chip da própria dimensão ignora o filtro dela; os outros respeitam
    assert chips.get("modalidade") == {"remoto": 4, "presencial": 2, "hibrido": 1}
    assert chips["uf"] == {"SP": 2}
    assert chips["contrato"] == {"clt": 1, "trainee": 1}
    assert chips["fonte"] == {"remotive": 2}
    assert chips["encaixe"] == {"medio": 1, "fraco": 1}

    f = Filtros(busca_id=b, uf="RJ", q="python")
    chips = contar_chips(con, f, AGORA)
    assert chips["area"] == {"dados": 1}
    assert chips["uf"] == {"RJ": 1, "SP": 1}

    # cada contagem bate com a lista filtrada por aquele valor
    for f in (Filtros(busca_id=b), Filtros(busca_id=b, modalidade="remoto", area="tecnologia")):
        for dim, valores in contar_chips(con, f, AGORA).items():
            for valor, n in valores.items():
                so_um: dict[str, Any] = {dim: valor}
                filtrada = listar(con, replace(f, **so_um), AGORA)
                assert len(filtrada.itens) == n, (dim, valor)


def test_ordens(con: sqlite3.Connection, ids: dict[str, int]) -> None:
    b = ids["busca"]

    def ordem(nome: str) -> list[str]:
        nomes = {v: k for k, v in ids.items() if k != "busca"}
        return [nomes[i] for i in _lista(con, busca_id=b, ordem=nome)]

    assert ordem("encaixe") == [
        "usd",
        "nova",
        "himalayas",
        "prazo_3_dias",
        "brl",
        "script",
        "trainee",
    ]
    assert _lista(con, busca_id=b) == _lista(con, busca_id=b, ordem="encaixe")
    assert ordem("recentes") == [
        "nova",
        "usd",
        "brl",
        "himalayas",
        "script",
        "prazo_3_dias",
        "trainee",
    ]
    assert ordem("prazo")[:2] == ["prazo_3_dias", "trainee"]
    # salário em reais; o implausível (script) não sobe para o topo
    assert ordem("salario")[:2] == ["usd", "brl"]
    assert "script" not in ordem("salario")[:2]
    # A–Z sem ligar para acento nem caixa
    assert ordem("empresa") == [
        "brl",
        "himalayas",
        "script",
        "nova",
        "prazo_3_dias",
        "trainee",
        "usd",
    ]
    # sem busca escolhida, a ordem padrão cai em mais recentes
    assert _lista(con) == _lista(con, ordem="recentes")


def test_pagina_de_50(con: sqlite3.Connection) -> None:
    for n in range(51):
        inserir_vaga(con, titulo=f"Vaga {n}")
    primeira = _pagina(con)
    segunda = _pagina(con, pagina=2)
    assert (len(primeira.itens), primeira.tem_mais) == (50, True)
    assert (len(segunda.itens), segunda.tem_mais) == (1, False)
    todas = {i.id for i in primeira.itens} | {i.id for i in segunda.itens}
    assert len(todas) == 51
    assert _pagina(con, pagina=3).itens == ()


def test_busca_sem_acento_acha_com_acento(con: sqlite3.Connection, ids: dict[str, int]) -> None:
    assert _tem_fts(con)
    for termo in ("integracao", "INTEGRAÇÃO", "Integra", "engenheira integração"):
        assert _lista(con, q=termo) == [ids["nova"]], termo
    assert _lista(con, q="agil") == [ids["brl"]]


@pytest.mark.parametrize("termo", SINTAXE)
def test_busca_trata_sintaxe_fts_como_texto(
    con: sqlite3.Connection, ids: dict[str, int], termo: str
) -> None:
    assert _tem_fts(con)
    pagina = _pagina(con, q=termo, busca_id=ids["busca"])
    assert isinstance(pagina.itens, tuple)
    contar_chips(con, Filtros(q=termo), AGORA)
    if termo in ("c++", "c#"):
        assert ids["script"] in [i.id for i in pagina.itens]


def test_sem_fts5_usa_like(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_migrar, "tem_fts5", lambda con: False)
    con = _banco(tmp_path / "jobot.db")
    assert not _tem_fts(con)
    ids = semear(con)
    assert _lista(con, q="integracao") == [ids["nova"]]
    assert _lista(con, q="INTEGRAÇÃO agil") == []
    assert ids["script"] in _lista(con, q="c++")
    # % e _ são texto, não curinga do LIKE: sem escape, os dois achariam vagas
    assert _lista(con, q="a%b") == []
    assert _lista(con, q="a_s") == []
    for termo in SINTAXE:
        _pagina(con, q=termo)
    con.close()


def test_detalhe_traz_fontes_e_url_candidatura(
    con: sqlite3.Connection, ids: dict[str, int]
) -> None:
    b = ids["busca"]
    d = detalhe(con, ids["himalayas"], b)
    assert d is not None
    assert [f.fonte for f in d.fontes] == ["himalayas"]
    assert d.url_candidatura == "https://himalayas.app/companies/beta/jobs/42/apply"
    assert d.url_candidatura != d.fontes[0].url
    usd = detalhe(con, ids["usd"], b)
    assert usd is not None
    assert (usd.sal_mensal_min_brl, usd.sal_cotacao_venda) == (28250, "5.65")
    assert usd.nota == 90 and usd.motivos[0].chave == "encaixe.cargo_no_titulo"
    # vaga fechada: todas as ocorrências sumiram, mas o "via <fonte>" fica
    fechada = detalhe(con, ids["fechada_salva"], b)
    assert fechada is not None and fechada.fechada and fechada.fontes
    assert detalhe(con, 999_999, b) is None


@pytest.fixture
def fuso_brasilia(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_hoje_e_o_dia_local(con: sqlite3.Connection, fuso_brasilia: None) -> None:
    # 01:30 UTC de 13/11 ainda é 22:30 de 12/11 em Brasília: prazo de 12/11 não venceu
    agora = datetime(2026, 11, 13, 1, 30, tzinfo=UTC)
    hoje = inserir_vaga(con, prazo="2026-11-12")
    dia_7 = inserir_vaga(con, prazo="2026-11-19")
    dia_8 = inserir_vaga(con, prazo="2026-11-20")
    assert {i.id for i in listar(con, Filtros(), agora).itens} == {hoje, dia_7, dia_8}
    assert [i.id for i in listar(con, Filtros(aba="fecham_logo"), agora).itens] == [hoje, dia_7]
    d = detalhe(con, hoje, None, agora)
    assert d is not None and not d.fechada and d.fecha_logo


def test_recentes_usa_a_data_de_publicacao(con: sqlite3.Connection) -> None:
    vista = (AGORA - timedelta(days=5)).isoformat()
    velha = inserir_vaga(con, primeira_vista_em=(AGORA - timedelta(days=1)).isoformat())
    publicada = inserir_vaga(con, primeira_vista_em=vista, publicada_em=AGORA.isoformat())
    assert _lista(con, ordem="recentes") == [publicada, velha]
