"""Migração 0014 (D234, decidido pelo dono): pergunta sugerida pela candidatura espera o aceite.

A coluna `sugerida` de `pergunta_perfil` marca a pergunta que a IA sugeriu ao preparar uma
candidatura e que a pessoa ainda não aceitou: ela fica fora de `perfil.perguntas` (e, por isso,
do questionário e de todo pedido à IA) até o aceite. No máximo `TETO_SUGERIDAS` esperam; a mais
velha sai. As linhas de antes da 0014 nascem aceitas.
"""

import shutil
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from jobot.banco import perfil
from jobot.banco.conexao import abrir
from jobot.banco.migrar import MIGRACOES, migrar

ARQUIVO = MIGRACOES / "0014_pergunta_sugerida.sql"
T0 = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
AGORA = T0.isoformat()


def _arquivo_da_0014() -> Path:
    """Afirma que o arquivo existe: o vermelho é por asserção, não por I/O."""
    assert ARQUIVO.exists()
    return ARQUIVO


@pytest.fixture
def antes(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Path, Path]]:
    """Banco nas versões 0001 a 0013, mais a pasta onde a 0014 entra."""
    _arquivo_da_0014()
    pasta = tmp_path / "ate_a_decima_terceira"
    pasta.mkdir()
    for arquivo in sorted(MIGRACOES.glob("*.sql"))[:13]:
        shutil.copy(arquivo, pasta)
    caminho = tmp_path / "jobot.db"
    con = abrir(caminho)
    assert migrar(con, caminho, pasta) == 13
    yield con, caminho, pasta
    con.close()


def _aplicar_0014(con: sqlite3.Connection, caminho: Path, pasta: Path) -> None:
    shutil.copy(_arquivo_da_0014(), pasta)
    assert migrar(con, caminho, pasta) == 14


@pytest.fixture
def con(antes: tuple[sqlite3.Connection, Path, Path]) -> sqlite3.Connection:
    """Banco só até a 0014: migrações novas não mudam o que se confere."""
    c, caminho, pasta = antes
    _aplicar_0014(c, caminho, pasta)
    return c


def _recusa(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> bool:
    con.execute("SAVEPOINT t")
    try:
        con.execute(sql, params)
    except sqlite3.IntegrityError:
        return True
    finally:
        con.execute("ROLLBACK TO t")
        con.execute("RELEASE t")
    return False


def _conta(con: sqlite3.Connection, tabela: str) -> int:
    return int(con.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0])


def _chaves(lista: list[perfil.PerguntaPerfil]) -> list[str]:
    return [p.chave for p in lista]


# esquema


def test_versao_sobe_para_14(con: sqlite3.Connection) -> None:
    assert con.execute("PRAGMA user_version").fetchone()[0] == 14


def test_sugerida_nasce_0_e_so_aceita_0_ou_1(con: sqlite3.Connection) -> None:
    colunas = {
        nome: (tipo, nulo, padrao)
        for _, nome, tipo, nulo, padrao, _ in con.execute("PRAGMA table_info(pergunta_perfil)")
    }
    assert colunas["sugerida"] == ("INTEGER", 1, "0")
    sql = (
        "INSERT INTO pergunta_perfil (chave, pergunta, origem, criada_em, sugerida)"
        " VALUES ('a', 'p?', 'ia', ?, ?)"
    )
    assert _recusa(con, sql, (AGORA, 0)) is False
    assert _recusa(con, sql, (AGORA, 1)) is False
    assert _recusa(con, sql, (AGORA, 2)) is True
    assert _recusa(con, sql, (AGORA, None)) is True


def test_antes_as_perguntas_ficam_aceitas(antes: tuple[sqlite3.Connection, Path, Path]) -> None:
    con, caminho, pasta = antes
    con.execute(
        "INSERT INTO pergunta_perfil (chave, pergunta, origem, criada_em, resposta)"
        " VALUES ('ia:bi', 'Usa BI?', 'ia', ?, 'Sim')",
        (AGORA,),
    )
    con.commit()
    _aplicar_0014(con, caminho, pasta)
    assert perfil.perguntas(con) == [
        perfil.PerguntaPerfil(chave="ia:bi", pergunta="Usa BI?", origem="ia", resposta="Sim")
    ]
    assert perfil.perguntas(con, sugeridas=True) == []


# gravar, aceitar e descartar (`banco/perfil.py`)


def test_pergunta_sugerida_de_novo_nao_apaga_a_resposta(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "ia:docker", "Já usou Docker?", "ia", T0, por_que="A vaga pede.")
    perfil.responder_pergunta(con, "ia:docker", "Sim, dois anos.", T0 + timedelta(hours=1))
    perfil.gravar_pergunta(
        con, "ia:docker", "Você já usou Docker?", "ia", T0 + timedelta(hours=2), por_que="Outra."
    )
    assert _conta(con, "pergunta_perfil") == 1
    assert perfil.perguntas(con) == [
        perfil.PerguntaPerfil(
            chave="ia:docker",
            pergunta="Você já usou Docker?",
            origem="ia",
            por_que="Outra.",
            resposta="Sim, dois anos.",
        )
    ]
    respondida = con.execute("SELECT criada_em, respondida_em FROM pergunta_perfil").fetchone()
    assert respondida == (T0.isoformat(), (T0 + timedelta(hours=1)).isoformat())


def test_pergunta_sugerida_de_novo_troca_a_origem(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "base:links", "Seus links?", "base", T0)
    perfil.gravar_pergunta(con, "base:links", "Seus links?", "ia", T0 + timedelta(hours=1))
    assert [p.origem for p in perfil.perguntas(con)] == ["ia"]


def test_responder_pergunta_so_grava_na_chave_pedida(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "ia:docker", "Já usou Docker?", "ia", T0)
    perfil.gravar_pergunta(con, "base:links", "Seus links?", "base", T0)
    perfil.responder_pergunta(con, "ia:docker", "Sim.", T0 + timedelta(hours=1))
    linhas = con.execute(
        "SELECT chave, resposta, respondida_em FROM pergunta_perfil ORDER BY id"
    ).fetchall()
    assert linhas == [
        ("ia:docker", "Sim.", (T0 + timedelta(hours=1)).isoformat()),
        ("base:links", None, None),
    ]


def test_responder_pergunta_que_nao_existe_nao_cria(con: sqlite3.Connection) -> None:
    perfil.responder_pergunta(con, "nao:existe", "x", T0)
    assert _conta(con, "pergunta_perfil") == 0
    perfil.gravar_pergunta(con, "base:links", "Seus links?", "base", T0)  # controle
    perfil.responder_pergunta(con, "base:links", "https://a.test", T0)
    assert [p.resposta for p in perfil.perguntas(con)] == ["https://a.test"]


def test_sugerida_fica_fora_das_perguntas_ate_o_aceite(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "ia:bi", "Usa BI?", "ia", T0)  # controle: aceita
    perfil.gravar_pergunta(con, "ia:k8s", "Usa Kubernetes?", "ia", T0, sugerida=True)
    assert _chaves(perfil.perguntas(con)) == ["ia:bi"]
    assert _chaves(perfil.perguntas(con, sugeridas=True)) == ["ia:k8s"]
    perfil.aceitar_pergunta(con, "ia:k8s")
    assert _chaves(perfil.perguntas(con)) == ["ia:bi", "ia:k8s"]
    assert perfil.perguntas(con, sugeridas=True) == []


def test_descartar_apaga_so_a_sugerida(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "ia:bi", "Usa BI?", "ia", T0)
    perfil.gravar_pergunta(con, "ia:k8s", "Usa Kubernetes?", "ia", T0, sugerida=True)
    perfil.descartar_pergunta(con, "ia:bi")  # a aceita não sai por aqui
    perfil.descartar_pergunta(con, "ia:k8s")
    assert con.execute("SELECT chave FROM pergunta_perfil").fetchall() == [("ia:bi",)]


def test_sugerir_de_novo_nao_desfaz_o_aceite(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "ia:bi", "Usa BI?", "ia", T0)
    perfil.gravar_pergunta(con, "ia:bi", "Você usa BI?", "ia", T0, sugerida=True)
    assert _chaves(perfil.perguntas(con)) == ["ia:bi"]
    assert perfil.perguntas(con, sugeridas=True) == []


def test_pedir_sem_sugerir_aceita_a_que_esperava(con: sqlite3.Connection) -> None:
    # o questionário (a pessoa pediu as perguntas) traz a mesma que a candidatura sugeriu
    perfil.gravar_pergunta(con, "ia:bi", "Usa BI?", "ia", T0, sugerida=True)
    perfil.gravar_pergunta(con, "ia:bi", "Usa BI?", "ia", T0)
    assert _chaves(perfil.perguntas(con)) == ["ia:bi"]


def test_no_teto_de_sugeridas_a_mais_velha_sai(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "ia:aceita", "Aceita?", "ia", T0)  # aceita não conta nem sai
    for n in range(perfil.TETO_SUGERIDAS + 2):
        perfil.gravar_pergunta(con, f"ia:{n}", f"Pergunta {n}?", "ia", T0, sugerida=True)
    sugeridas = _chaves(perfil.perguntas(con, sugeridas=True))
    assert len(sugeridas) == perfil.TETO_SUGERIDAS
    assert sugeridas[0] == "ia:2" and sugeridas[-1] == f"ia:{perfil.TETO_SUGERIDAS + 1}"
    assert _chaves(perfil.perguntas(con)) == ["ia:aceita"]


def test_apagar_perfil_leva_as_sugeridas(con: sqlite3.Connection) -> None:
    perfil.gravar_pergunta(con, "ia:k8s", "Usa Kubernetes?", "ia", T0, sugerida=True)
    assert perfil.existe(con) is True
    perfil.apagar_perfil(con)
    assert _conta(con, "pergunta_perfil") == 0
