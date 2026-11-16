"""Leitura e busca do painel (desenho 13.3 e 13.4; plano T20)."""

import ast
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from apoio.semear import AGORA, inserir_vaga, semear
from jobot.banco import acoes
from jobot.banco import migrar as modulo_migrar
from jobot.banco.conexao import abrir
from jobot.banco.leitura import (
    Filtros,
    Pagina,
    contar_abas,
    contar_chips,
    contar_fora_do_salario,
    detalhe,
    listar,
    tem_vaga,
)
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


@pytest.fixture(params=["fts", "like"])
def con_modo(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[sqlite3.Connection]:
    """Banco limpo com FTS5 e sem ele (o mesmo `monkeypatch` de `test_sem_fts5_usa_like`)."""
    if request.param == "like":
        monkeypatch.setattr(modulo_migrar, "tem_fts5", lambda con: False)
    c = _banco(tmp_path / "jobot.db")
    assert _tem_fts(c) == (request.param == "fts")
    yield c
    c.close()


def test_excluir_tira_vaga_com_a_palavra_no_titulo_empresa_ou_descricao(
    con_modo: sqlite3.Connection,
) -> None:
    c = con_modo
    no_titulo = inserir_vaga(c, titulo="Analista Cobol", empresa="Alfa", descricao_texto="x")
    na_empresa = inserir_vaga(c, titulo="Analista", empresa="Cobol SA", descricao_texto="x")
    na_descricao = inserir_vaga(c, titulo="Analista", empresa="Beta", descricao_texto="usa cobol")
    controle = inserir_vaga(c, titulo="Analista Python", empresa="Gama", descricao_texto="x")
    assert set(_lista(c)) == {no_titulo, na_empresa, na_descricao, controle}
    assert _lista(c, excluir="cobol") == [controle]


def test_excluir_duas_palavras_e_ou(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    inserir_vaga(c, titulo="Analista Cobol", descricao_texto="x")
    inserir_vaga(c, titulo="Analista Fortran", descricao_texto="x")
    controle = inserir_vaga(c, titulo="Analista Python", descricao_texto="x")
    assert _lista(c, excluir="cobol fortran") == [controle]


def test_excluir_com_sintaxe_nunca_levanta(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    ids = semear(c)
    todas = set(_lista(c))
    assert ids["script"] in todas
    for termo in [*SINTAXE, '"', "%", "_", "\x00", "\ud800"]:
        pagina = _pagina(c, excluir=termo)
        assert isinstance(pagina.itens, tuple), termo
    # % e _ são texto, não curinga: nenhuma vaga tem a palavra
    assert set(_lista(c, excluir="%")) == todas
    assert set(_lista(c, excluir="_")) == todas


def test_excluir_so_pontuacao_nao_filtra(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    semear(c)
    assert _lista(c, excluir="!!! ...") == _lista(c)
    assert len(_lista(c)) > 0


def test_q_e_excluir_juntos(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    certa = inserir_vaga(c, titulo="Dev Python", descricao_texto="flask")
    inserir_vaga(c, titulo="Dev Python", descricao_texto="django")
    inserir_vaga(c, titulo="Dev Java", descricao_texto="flask")
    assert _lista(c, q="python", excluir="django") == [certa]


def test_cidade_contem_sem_acento_e_sem_caixa(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    sp = inserir_vaga(c, cidade="São Paulo", uf="SP")
    inserir_vaga(c, cidade="Curitiba", uf="PR")
    assert _lista(c, cidade="sao") == [sp]
    assert _lista(c, cidade="PAULO") == [sp]
    assert _lista(c, cidade="rio") == []


def test_cidade_e_empresa_tratam_curinga_como_texto(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    cem = inserir_vaga(c, empresa="100% Remoto", cidade="Rio_Claro")
    inserir_vaga(c, empresa="Acme", cidade="Rio Preto")
    assert _lista(c, empresa="%") == [cem]
    assert _lista(c, empresa="_") == []
    assert _lista(c, cidade="_") == [cem]
    assert _lista(c, cidade="o_c") == [cem]
    assert _lista(c, cidade="%") == []


def test_cidade_com_local_sem_cidade_nao_levanta(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    vaga = inserir_vaga(c, uf="SP")
    assert _lista(c) == [vaga]
    assert _lista(c, cidade="sao") == []


def test_cidade_com_dois_locais_casa_o_que_tem_cidade(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    vaga = inserir_vaga(c, uf="RJ")
    c.execute(
        "INSERT INTO local_vaga (vaga_id, cidade, uf, pais) VALUES (?, 'São Paulo', 'SP', 'BR')",
        (vaga,),
    )
    c.commit()
    assert _lista(c, cidade="sao paulo") == [vaga]


def test_empresa_sem_acento_e_sem_caixa(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    agil = inserir_vaga(c, empresa="Ágil Soluções")
    inserir_vaga(c, empresa="Acme")
    assert _lista(c, empresa="AGIL") == [agil]
    assert _lista(c, empresa="ágil") == [agil]


def test_cidade_e_empresa_so_com_marca_combinante_nao_filtram(
    con_modo: sqlite3.Connection,
) -> None:
    c = con_modo
    inserir_vaga(c, empresa="Acme", cidade="Recife")
    inserir_vaga(c, empresa="Beta", uf="SP")
    inserir_vaga(c, empresa="Gama")  # sem local
    todas = _lista(c)
    assert len(todas) == 3
    # a marca sozinha some na normalização: virava LIKE '%%' e exigia um local
    assert _lista(c, cidade="\u0301") == todas
    assert _lista(c, empresa="\u0301") == todas


def test_excluir_com_porcento_nos_dois_modos(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    com = inserir_vaga(c, titulo="Bônus de 100% remoto", descricao_texto="x")
    controle = inserir_vaga(c, titulo="Dev Python", descricao_texto="x")
    assert set(_lista(c)) == {com, controle}
    assert _lista(c, excluir="100%") == [controle]


def _vaga_ha(
    c: sqlite3.Connection, *, publicada: timedelta | None, vista: timedelta, **campos: Any
) -> int:
    """Vaga publicada (ou só vista) há tanto tempo, contado de `AGORA`."""
    return inserir_vaga(
        c,
        publicada_em=None if publicada is None else (AGORA - publicada).isoformat(),
        primeira_vista_em=(AGORA - vista).isoformat(),
        **campos,
    )


def test_publicada_24h_borda(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    dentro = _vaga_ha(c, publicada=timedelta(hours=23), vista=timedelta(days=5))
    _vaga_ha(c, publicada=timedelta(hours=25), vista=timedelta(days=5))
    assert _lista(c, publicada="24h") == [dentro]


def test_publicada_sem_data_usa_primeira_vista(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    recente = _vaga_ha(c, publicada=None, vista=timedelta(hours=2))
    _vaga_ha(c, publicada=None, vista=timedelta(days=3))
    assert _lista(c, publicada="24h") == [recente]


def test_publicada_7d_e_30d(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    horas = _vaga_ha(c, publicada=timedelta(hours=2), vista=timedelta(hours=2))
    dias = _vaga_ha(c, publicada=timedelta(days=3), vista=timedelta(days=3))
    velha = _vaga_ha(c, publicada=timedelta(days=20), vista=timedelta(days=20))
    assert set(_lista(c, publicada="7d")) == {horas, dias}
    assert set(_lista(c, publicada="30d")) == {horas, dias, velha}
    # valor fora de PUBLICADA não filtra
    assert set(_lista(c, publicada="1a")) == {horas, dias, velha}


def test_contar_publicada_soma_sobrepostos_com_outro_filtro(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    _vaga_ha(c, publicada=timedelta(hours=2), vista=timedelta(hours=2), modalidade="remoto")
    _vaga_ha(c, publicada=timedelta(days=3), vista=timedelta(days=3), modalidade="remoto")
    _vaga_ha(c, publicada=timedelta(days=20), vista=timedelta(days=20), modalidade="remoto")
    _vaga_ha(c, publicada=timedelta(hours=2), vista=timedelta(hours=2), modalidade="presencial")
    chips = contar_chips(c, Filtros(modalidade="remoto"), AGORA)
    assert chips["publicada"] == {"24h": 1, "7d": 2, "30d": 3}
    # a contagem ignora o próprio filtro: com "24h" escolhido, os três números não mudam
    chips = contar_chips(c, Filtros(modalidade="remoto", publicada="24h"), AGORA)
    assert chips["publicada"] == {"24h": 1, "7d": 2, "30d": 3}
    # sem nenhuma vaga na aba, os três continuam existindo, em zero
    vazio = contar_chips(c, Filtros(aba="salvas"), AGORA)
    assert vazio["publicada"] == {"24h": 0, "7d": 0, "30d": 0}


def test_pais_filtra_por_local_vaga(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    inserir_vaga(c, pais="BR")
    pt = inserir_vaga(c, pais="PT")
    inserir_vaga(c)  # sem local
    assert _lista(c, pais="PT") == [pt]


def test_contar_pais_considera_outros_filtros(con_modo: sqlite3.Connection) -> None:
    c = con_modo
    inserir_vaga(c, pais="PT", modalidade="remoto")
    inserir_vaga(c, pais="BR", modalidade="remoto")
    inserir_vaga(c, pais="BR", modalidade="presencial")
    chips = contar_chips(c, Filtros(modalidade="remoto"), AGORA)
    assert chips["pais"] == {"PT": 1, "BR": 1}
    # o chip do país ignora o filtro dele mesmo
    chips = contar_chips(c, Filtros(modalidade="remoto", pais="PT"), AGORA)
    assert chips["pais"] == {"PT": 1, "BR": 1}


def _paga(
    c: sqlite3.Connection,
    moeda: str = "BRL",
    minimo: int | None = None,
    maximo: int | None = None,
    periodo: str = "mes",
    **campos: Any,
) -> int:
    """Vaga com salário: `minimo` e `maximo` em unidades inteiras da moeda, por `periodo`.

    As colunas `_brl` vão direto em `campos`; sem elas ficam nulas (sem valor convertido).
    """
    fator = {"hora": 160, "dia": 21, "mes": 1, "ano": 1 / 12}[periodo]
    mensal = None if minimo is None else round(minimo * 100 * fator)
    return inserir_vaga(
        c,
        sal_moeda=moeda,
        sal_min=None if minimo is None else minimo * 100,
        sal_max=None if maximo is None else maximo * 100,
        sal_periodo=periodo,
        sal_mensal_min=mensal,
        **campos,
    )


def test_salario_sobreposicao_de_faixas(con: sqlite3.Connection) -> None:
    v = _paga(con, minimo=5000, maximo=8000, sal_mensal_min_brl=5000, sal_mensal_max_brl=8000)
    assert _lista(con, sal_de_brl=7000, sal_ate_brl=10000) == [v]
    assert _lista(con, sal_de_brl=1000, sal_ate_brl=5000) == [v]
    assert _lista(con, sal_de_brl=9000, sal_ate_brl=10000) == []


def test_salario_so_com_minimo_ou_so_com_maximo(con: sqlite3.Connection) -> None:
    so_min = _paga(con, minimo=6000, sal_mensal_min_brl=6000)
    so_max = inserir_vaga(
        con, sal_moeda="BRL", sal_max=800000, sal_periodo="mes", sal_mensal_max_brl=8000
    )
    assert so_min in _lista(con, sal_de_brl=6000)
    assert so_max in _lista(con, sal_ate_brl=8000)
    assert so_max in _lista(con, sal_de_brl=8000)
    assert so_max not in _lista(con, sal_de_brl=8001)


def test_salario_implausivel_fica_fora_e_conta_como_sem_salario(con: sqlite3.Connection) -> None:
    _paga(
        con,
        minimo=5000,
        maximo=8000,
        sal_mensal_min_brl=5000,
        sal_mensal_max_brl=8000,
        sal_plausivel=0,
    )
    assert _lista(con, sal_de_brl=1000, sal_ate_brl=10000) == []
    assert contar_fora_do_salario(con, Filtros(sal_de_brl=1000, sal_ate_brl=10000), AGORA)[0] == 1


def test_sem_salario_fica_fora_e_volta_com_sem_salario(con: sqlite3.Connection) -> None:
    sem = inserir_vaga(con)
    com = _paga(con, minimo=5000, maximo=8000, sal_mensal_min_brl=5000, sal_mensal_max_brl=8000)
    assert _lista(con, sal_de_brl=1) == [com]
    assert set(_lista(con, sal_de_brl=1, sem_salario=True)) == {sem, com}


def test_salario_na_moeda_com_conversao_desligada(con: sqlite3.Connection) -> None:
    mes = _paga(con, "USD", 5000, 8000, "mes")
    hora = inserir_vaga(con, sal_moeda="USD", sal_max=5000, sal_periodo="hora")  # 800.000 por mês
    ano = inserir_vaga(con, sal_moeda="USD", sal_max=9600000, sal_periodo="ano")
    fora = inserir_vaga(con, sal_moeda="USD", sal_max=5000, sal_periodo="mes")
    _paga(con, "EUR", 5000, 8000, "mes")
    f = {"sal_moeda": "USD", "sal_de_centavos": 700000, "sal_ate_centavos": 1000000}
    assert set(_lista(con, **f)) == {mes, hora, ano}
    assert fora not in _lista(con, **f)


def test_sem_salario_no_modo_na_moeda_nao_traz_outras_moedas(con: sqlite3.Connection) -> None:
    sem = inserir_vaga(con)
    _paga(con, "USD", 1000, 2000, "mes")  # USD fora da faixa
    _paga(con, "EUR", 5000, 8000, "mes")
    f = {"sal_moeda": "USD", "sal_de_centavos": 700000, "sal_ate_centavos": 1000000}
    assert _lista(con, **f, sem_salario=True) == [sem]


def test_contagem_dos_avisos_nao_mistura(con: sqlite3.Connection) -> None:
    _paga(con, "USD", 5000, 8000)  # _brl nulo: com salário e sem valor convertido
    inserir_vaga(con)  # sem salário
    inserir_vaga(con, modalidade="presencial")
    _paga(con, "USD", 5000, 8000, modalidade="presencial")
    f = Filtros(sal_de_brl=1)
    assert contar_fora_do_salario(con, f, AGORA) == (2, 2)
    assert contar_fora_do_salario(con, replace(f, modalidade="remoto"), AGORA) == (1, 1)


def test_sem_salario_ligado_zera_a_contagem_de_fora(con: sqlite3.Connection) -> None:
    inserir_vaga(con)
    _paga(con, "USD", 5000, 8000)
    assert contar_fora_do_salario(con, Filtros(sal_de_brl=1), AGORA) == (1, 1)
    assert contar_fora_do_salario(con, Filtros(sal_de_brl=1, sem_salario=True), AGORA) == (0, 1)


def test_salario_no_teto_nao_estoura(con: sqlite3.Connection) -> None:
    _paga(con, minimo=5000, maximo=8000, sal_mensal_min_brl=5000, sal_mensal_max_brl=8000)
    teto = 2**63 - 1
    assert _lista(con, sal_de_brl=teto) == []
    assert _lista(con, sal_moeda="BRL", sal_de_centavos=teto) == []
    assert contar_fora_do_salario(con, Filtros(sal_de_brl=teto), AGORA) == (0, 0)


def test_so_o_ate_exclui(con: sqlite3.Connection) -> None:
    reais = _paga(con, minimo=5000, maximo=8000, sal_mensal_min_brl=5000, sal_mensal_max_brl=8000)
    usd = _paga(con, "USD", 5000, 8000)
    assert _lista(con, sal_ate_brl=4000) == []
    assert _lista(con, sal_ate_brl=5000) == [reais]
    f = {"sal_moeda": "USD", "sal_ate_centavos": 400000}
    assert _lista(con, **f) == []
    assert _lista(con, sal_moeda="USD", sal_ate_centavos=500000) == [usd]


def test_salario_implausivel_na_moeda_fica_fora_e_volta_com_sem_salario(
    con: sqlite3.Connection,
) -> None:
    v = _paga(con, "USD", 5000, 8000, sal_plausivel=0)
    f = {"sal_moeda": "USD", "sal_de_centavos": 400000, "sal_ate_centavos": 1000000}
    assert _lista(con, **f) == []
    assert _lista(con, **f, sem_salario=True) == [v]


def test_maximo_mensal_usa_o_fator_do_periodo(con: sqlite3.Connection) -> None:
    dia = inserir_vaga(con, sal_moeda="USD", sal_max=10000, sal_periodo="dia")  # 210.000 por mês
    semana = inserir_vaga(con, sal_moeda="USD", sal_max=10000, sal_periodo="semana")  # 43.300
    so_min = inserir_vaga(
        con, sal_moeda="USD", sal_min=300000, sal_periodo="mes", sal_mensal_min=300000
    )
    sem_periodo = inserir_vaga(con, sal_moeda="USD", sal_max=10000, sal_periodo="turno")

    def casa(de: int, ate: int) -> set[int]:
        f = {"sal_moeda": "USD", "sal_de_centavos": de, "sal_ate_centavos": ate}
        return set(_lista(con, **f))

    assert casa(210000, 210000) == {dia}
    assert casa(43300, 43300) == {semana}
    assert casa(300000, 300000) == {so_min}
    assert sem_periodo not in casa(0, 2**62)


def test_contar_fora_do_salario_sem_filtro_de_salario_da_zero(con: sqlite3.Connection) -> None:
    inserir_vaga(con)
    _paga(con, "USD", 5000, 8000)
    assert contar_fora_do_salario(con, Filtros(), AGORA) == (0, 0)
    assert contar_fora_do_salario(con, Filtros(modalidade="remoto"), AGORA) == (0, 0)


def test_contar_fora_do_salario_na_moeda_nao_conta_o_sem_valor(con: sqlite3.Connection) -> None:
    _paga(con, "EUR", 5000, 8000)  # _brl nulo
    f = Filtros(sal_moeda="USD", sal_de_centavos=1)
    assert contar_fora_do_salario(con, f, AGORA)[1] == 0
    assert contar_fora_do_salario(con, Filtros(sal_de_brl=1), AGORA)[1] == 1


def test_sem_salario_so_pela_ausencia_de_minimo_e_maximo(con: sqlite3.Connection) -> None:
    inserir_vaga(con, sal_moeda="USD", sal_periodo="mes")  # moeda sem valor nenhum
    assert contar_fora_do_salario(con, Filtros(sal_de_brl=1), AGORA) == (1, 0)


def test_status_em_na_listagem(con: sqlite3.Connection) -> None:
    vaga = inserir_vaga(con, status="nova")
    quando = datetime(2026, 11, 13, 10, 30, tzinfo=UTC)
    acoes.mudar_status(con, vaga, "salva", quando)
    item = next(i for i in _pagina(con, aba="salvas").itens if i.id == vaga)
    assert item.status_em == quando.isoformat()
    d = detalhe(con, vaga, None, AGORA)
    assert d is not None and d.status_em == quando.isoformat()


def test_tem_vaga(con: sqlite3.Connection) -> None:
    assert tem_vaga(con) is False  # guarda: o banco vazio nasce verde
    inserir_vaga(con, oculta_manual=1, fechada_em="2026-11-01T00:00:00+00:00")
    assert tem_vaga(con) is True


def test_degrau_definido_uma_vez() -> None:
    pasta = Path(__file__).parents[2] / "src" / "jobot" / "banco"
    definem: list[str] = []
    for arquivo in sorted(pasta.glob("*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            alvos = no.targets if isinstance(no, ast.Assign) else []
            if isinstance(no, ast.AnnAssign):
                alvos = [no.target]
            nomes = [a.id for a in alvos if isinstance(a, ast.Name)]
            assert "_DEGRAU" not in nomes, f"{arquivo.name} define _DEGRAU"
            if "DEGRAU" in nomes:
                definem.append(arquivo.name)
    assert len(definem) == 1, definem
