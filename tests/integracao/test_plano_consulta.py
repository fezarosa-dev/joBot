"""Os filtros da 0.2.0 usam os índices da migração 0005 (T162, T170).

Confere o plano do SQLite (`EXPLAIN QUERY PLAN`) da consulta que `listar` executa. Não mede
tempo: tempo é instável no CI; quem mede é `scripts/medir_filtros.py`.
"""

import re
import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from apoio.semear import AGORA, inserir_vaga
from jobot.banco.leitura import Filtros, sql_de_listar
from jobot.banco.migrar import migrar

_UFS = ("SP", "RJ", "MG", "PR", "RS")


@pytest.fixture
def con() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys=ON")
    migrar(con, Path(":memory:"))
    for i in range(300):
        com_salario = i % 3 != 0
        inserir_vaga(
            con,
            uf=_UFS[i % len(_UFS)],
            pais="BR" if i % 10 else "US",
            cidade=f"Cidade {i % 40}",
            publicada_em=(AGORA - timedelta(days=i % 60)).isoformat(),
            sal_moeda="BRL" if com_salario else None,
            sal_min=(300000 + i * 1000) if com_salario else None,
            sal_periodo="mes" if com_salario else None,
            sal_mensal_min_brl=(3000 + i * 10) if com_salario else None,
            sal_mensal_max_brl=(4000 + i * 10) if com_salario else None,
            sal_plausivel=1 if com_salario else None,
        )
    yield con
    con.close()


def _plano(con: sqlite3.Connection, f: Filtros) -> str:
    sql, params = sql_de_listar(con, f, AGORA)
    linhas = con.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    return "\n".join(str(linha[3]) for linha in linhas)


def test_plano_pais_usa_local_vaga_pais(con: sqlite3.Connection) -> None:
    plano = _plano(con, Filtros(pais="US"))
    assert re.search(r"l EXISTS USING (COVERING )?INDEX local_vaga_pais", plano), plano


def test_plano_uf_e_cidade_usam_local_vaga_vaga(con: sqlite3.Connection) -> None:
    # "EXISTS" separa o filtro da subconsulta `locais` das colunas, que sempre usa o índice
    assert "l EXISTS USING INDEX local_vaga_vaga" in _plano(con, Filtros(uf="SP"))
    assert "l EXISTS USING INDEX local_vaga_vaga" in _plano(con, Filtros(cidade="Cidade 3"))


def test_plano_publicada_usa_o_indice_da_data(con: sqlite3.Connection) -> None:
    plano = _plano(con, Filtros(publicada="7d"))
    assert "USING INDEX vaga_publicada_ou_vista" in plano


@pytest.mark.parametrize(
    "filtros",
    [
        Filtros(sal_de_brl=5000),
        Filtros(sal_ate_brl=5000),
        Filtros(sal_de_brl=4000, sal_ate_brl=6000),
    ],
    ids=["so_de", "so_ate", "os_dois"],
)
def test_plano_salario_usa_indice(con: sqlite3.Connection, filtros: Filtros) -> None:
    plano = _plano(con, filtros)
    assert "vaga_sal_baixo_brl" in plano or "vaga_sal_alto_brl" in plano
