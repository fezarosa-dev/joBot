"""Os filtros da 0.2.0 usam os índices das migrações 0005 e 0006 (T162, T170, T192).

Confere o plano do SQLite (`EXPLAIN QUERY PLAN`) da consulta que `listar` executa. Não mede
tempo: tempo é instável no CI; quem mede é `scripts/medir_filtros.py`.
"""

import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from apoio.semear import AGORA, inserir_vaga
from jobot.banco.leitura import Filtros, contar_chips, sql_de_listar
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
    # sem o filtro o índice não aparece; o texto do EXISTS muda com a versão do SQLite
    assert "local_vaga_pais" not in _plano(con, Filtros())
    assert "local_vaga_pais" in _plano(con, Filtros(pais="US"))


def test_plano_uf_e_cidade_usam_local_vaga_vaga(con: sqlite3.Connection) -> None:
    # a subconsulta `locais` das colunas já cita o índice: o filtro tem de citá-lo mais uma vez
    sem = _plano(con, Filtros()).count("local_vaga_vaga")
    assert sem > 0
    assert _plano(con, Filtros(uf="SP")).count("local_vaga_vaga") > sem
    assert _plano(con, Filtros(cidade="Cidade 3")).count("local_vaga_vaga") > sem


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


def _plano_do_chip_de_fonte(con: sqlite3.Connection) -> str:
    """O plano da consulta do chip de fonte, tirada do que `contar_chips` executa de verdade."""
    vistas: list[str] = []
    con.set_trace_callback(vistas.append)  # o SQL já vem com os parâmetros no lugar
    try:
        contar_chips(con, Filtros(), AGORA)
    finally:
        con.set_trace_callback(None)
    sql = next(s for s in vistas if "JOIN ocorrencia" in s and "GROUP BY" in s)
    return "\n".join(str(linha[3]) for linha in con.execute(f"EXPLAIN QUERY PLAN {sql}"))


def test_plano_chip_de_fonte_usa_o_indice(con: sqlite3.Connection) -> None:
    # o SQLite do CI é mais velho: compara com o plano sem o índice, nunca o texto do nó
    assert "ocorrencia_fonte_vaga" in _plano_do_chip_de_fonte(con)
    con.execute("DROP INDEX ocorrencia_fonte_vaga")  # prova por mutação
    assert "ocorrencia_fonte_vaga" not in _plano_do_chip_de_fonte(con)
