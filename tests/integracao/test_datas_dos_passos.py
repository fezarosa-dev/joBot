"""Datas dos passos da vaga, lidas do histórico em `evento` (plano T282, desenho 5.4)."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jobot.banco import acoes
from jobot.banco.conexao import abrir
from jobot.banco.leitura import PASSOS, datas_dos_passos
from jobot.banco.migrar import migrar

T0 = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def _quando(n: int) -> datetime:
    return T0 + timedelta(hours=n)


def _iso(n: int) -> str:
    return _quando(n).isoformat()


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    c.execute(
        "INSERT INTO vaga (id, url_hash, titulo, empresa, url, primeira_vista_em,"
        " ultima_vista_em, versao_regras) VALUES (1, 'h1', 't', 'e', 'https://x.test/1',"
        " '2026-11-09', '2026-11-09', 'v1')"
    )
    c.commit()
    yield c
    c.close()


def _passos(con: sqlite3.Connection, *etapas: tuple[str, int]) -> None:
    """Cada etapa é (status novo, hora): o relógio avança a cada ação."""
    for status, hora in etapas:
        acoes.mudar_status(con, 1, status, _quando(hora))


def test_passos_em_ordem(con: sqlite3.Connection) -> None:
    _passos(con, ("salva", 1), ("candidatei", 2), ("entrevista", 3))
    datas = datas_dos_passos(con, 1)
    assert list(datas.items()) == [
        ("salva", _iso(1)),
        ("candidatei", _iso(2)),
        ("entrevista", _iso(3)),
    ]


def test_passos_segue_a_ordem_de_passos() -> None:
    assert PASSOS == ("salva", "candidatei", "entrevista", "oferta", "recusada")


def test_passo_pulado_sem_data(con: sqlite3.Connection) -> None:
    _passos(con, ("candidatei", 1))
    assert datas_dos_passos(con, 1) == {"candidatei": _iso(1)}


def test_desfeito_fica_fora(con: sqlite3.Connection) -> None:
    _passos(con, ("salva", 1), ("candidatei", 2))
    acoes.desfazer_status(con, 1, _quando(3))
    assert datas_dos_passos(con, 1) == {"salva": _iso(1)}


def test_desfeito_e_refeito_vale_o_mais_novo(con: sqlite3.Connection) -> None:
    _passos(con, ("salva", 1), ("candidatei", 2))
    acoes.desfazer_status(con, 1, _quando(3))
    _passos(con, ("candidatei", 4))
    assert datas_dos_passos(con, 1) == {"salva": _iso(1), "candidatei": _iso(4)}


def test_salva_por_salvou(con: sqlite3.Connection) -> None:
    _passos(con, ("salva", 5))
    assert con.execute("SELECT acao FROM evento").fetchall() == [("salvou",)]
    assert datas_dos_passos(con, 1) == {"salva": _iso(5)}


def test_oferta_e_recusada_depois_de_entrevista(con: sqlite3.Connection) -> None:
    _passos(con, ("salva", 1), ("candidatei", 2), ("entrevista", 3), ("oferta", 4))
    assert datas_dos_passos(con, 1) == {
        "salva": _iso(1),
        "candidatei": _iso(2),
        "entrevista": _iso(3),
        "oferta": _iso(4),
    }


def test_oferta_depois_recusada(con: sqlite3.Connection) -> None:
    _passos(con, ("salva", 1), ("candidatei", 2), ("entrevista", 3), ("oferta", 4))
    _passos(con, ("recusada", 5))
    datas = datas_dos_passos(con, 1)
    assert datas.get("recusada") == _iso(5)
    assert "oferta" not in datas
    assert list(datas) == ["salva", "candidatei", "entrevista", "recusada"]


def test_instante_mais_novo_vale_pelo_instante_nao_pelo_texto(con: sqlite3.Connection) -> None:
    # o texto "…T01:00:00+00:00" é maior que "…T23:00:00-03:00" na ordem de texto, e menor no tempo
    con.execute("UPDATE vaga SET status = 'candidatei' WHERE id = 1")
    for criado_em in ("2026-11-11T01:00:00+00:00", "2026-11-10T23:00:00-03:00"):
        con.execute(
            "INSERT INTO evento (vaga_id, acao, de, para, criado_em)"
            " VALUES (1, 'mudou_status', 'salva', 'candidatei', ?)",
            (criado_em,),
        )
    con.commit()
    # 23:00-03:00 de 10/11 é 02:00 UTC de 11/11: mais novo que 01:00 UTC
    assert datas_dos_passos(con, 1) == {"candidatei": "2026-11-10T23:00:00-03:00"}


def test_mesmo_instante_vale_o_evento_de_id_maior(con: sqlite3.Connection) -> None:
    # dois textos para o mesmo instante: só o desempate por id decide
    con.execute("UPDATE vaga SET status = 'candidatei' WHERE id = 1")
    for criado_em in ("2026-11-10T12:00:00+00:00", "2026-11-10T09:00:00-03:00"):
        con.execute(
            "INSERT INTO evento (vaga_id, acao, de, para, criado_em)"
            " VALUES (1, 'mudou_status', 'salva', 'candidatei', ?)",
            (criado_em,),
        )
    con.commit()
    assert datas_dos_passos(con, 1) == {"candidatei": "2026-11-10T09:00:00-03:00"}


def test_vaga_sem_evento_nao_tem_data(con: sqlite3.Connection) -> None:
    assert datas_dos_passos(con, 1) == {}
