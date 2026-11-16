"""Gravação do estado das contas no banco (plano T270, E1 e E2)."""

import sqlite3
from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import semear
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.sessoes import gravar_sessao, ler_sessao, ler_sessoes
from jobot.nucleo.contas import Sessao

SITE = "linkedin_logado"
ARQUIVO = Path(__file__).resolve().parents[2] / "src" / "jobot" / "banco" / "sessoes.py"


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    semear(c)
    yield c
    c.close()


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso()


def _passo(relogio: RelogioFalso) -> Any:
    relogio._agora += timedelta(minutes=1)
    return relogio.agora()


def _linha(con: sqlite3.Connection, tabela: str, chave: str) -> tuple[Any, ...] | None:
    coluna = {"sessao_site": "fonte", "sessao_conta": "conta"}[tabela]
    linha: tuple[Any, ...] | None = con.execute(
        f"SELECT estado, motivo, conferido_em, entrou_em, avisado_em FROM {tabela}"
        f" WHERE {coluna} = ?",
        (chave,),
    ).fetchone()
    return linha


def _recusa(funcao: Callable[..., Any], *args: Any) -> bool:
    try:
        funcao(*args)
    except sqlite3.IntegrityError:
        return True
    return False


def test_duas_gravacoes_uma_linha(con: sqlite3.Connection, relogio: RelogioFalso) -> None:
    gravar_sessao(con, "site", SITE, "conectado", None, relogio.agora())
    depois = _passo(relogio)
    gravar_sessao(con, "site", SITE, "nao_conferiu", "sem_rede", depois)
    assert con.execute("SELECT COUNT(*) FROM sessao_site").fetchone() == (1,)
    linha = _linha(con, "sessao_site", SITE)
    assert linha is not None
    assert linha[:3] == ("nao_conferiu", "sem_rede", depois.isoformat())


def test_devolve_abriu_uma_vez(con: sqlite3.Connection, relogio: RelogioFalso) -> None:
    passos: list[tuple[Any, Any]] = [
        ("conectado", None),
        ("precisa_entrar", None),
        ("precisa_entrar", None),
        ("nao_conferiu", "sem_rede"),
        ("precisa_entrar", None),
        ("conectado", None),
        ("precisa_entrar", None),
    ]
    abriu = []
    for estado, motivo in passos:
        abriu.append(gravar_sessao(con, "site", SITE, estado, motivo, _passo(relogio)))
    assert abriu == [False, True, False, False, False, False, True]
    linha = _linha(con, "sessao_site", SITE)
    assert linha is not None
    assert linha[4] is not None  # avisado_em da queda aberta


def test_entrou_mantido_em_precisa_e_nao_conferiu(
    con: sqlite3.Connection, relogio: RelogioFalso
) -> None:
    primeira = relogio.agora()
    gravar_sessao(con, "site", SITE, "conectado", None, primeira)
    gravar_sessao(con, "site", SITE, "precisa_entrar", None, _passo(relogio))
    linha = _linha(con, "sessao_site", SITE)
    assert linha is not None and linha[3] == primeira.isoformat()
    gravar_sessao(con, "site", SITE, "nao_conferiu", "sem_rede", _passo(relogio))
    linha = _linha(con, "sessao_site", SITE)
    assert linha is not None and linha[3] == primeira.isoformat()


def test_esquecer_zera_e_grava_hora(con: sqlite3.Connection, relogio: RelogioFalso) -> None:
    gravar_sessao(con, "site", SITE, "conectado", None, relogio.agora())
    gravar_sessao(con, "site", SITE, "precisa_entrar", None, _passo(relogio))
    antes = _linha(con, "sessao_site", SITE)
    assert antes is not None and antes[3] is not None and antes[4] is not None  # queda aberta
    agora = _passo(relogio)
    gravar_sessao(con, "site", SITE, "precisa_entrar", "esquecido", agora)
    assert _linha(con, "sessao_site", SITE) == (
        "precisa_entrar",
        "esquecido",
        agora.isoformat(),
        None,
        None,
    )


def test_motivo_fora_da_conta_desfaz(con: sqlite3.Connection, relogio: RelogioFalso) -> None:
    gravar_sessao(con, "conta", "gmail", "conectado", None, relogio.agora())
    primeira = _linha(con, "sessao_conta", "gmail")
    assert primeira is not None
    assert _recusa(gravar_sessao, con, "conta", "gmail", "nao_conferiu", "desafio", _passo(relogio))
    assert _linha(con, "sessao_conta", "gmail") == primeira
    assert con.in_transaction is False


def test_ler_sessao_devolve_a_linha(con: sqlite3.Connection, relogio: RelogioFalso) -> None:
    hora = relogio.agora().isoformat()
    gravar_sessao(con, "site", SITE, "conectado", None, relogio.agora())
    assert ler_sessao(con, "site", SITE) == Sessao("conectado", None, hora, hora, None)
    assert ler_sessao(con, "conta", "gmail") is None


def test_ler_sessoes_por_tipo(con: sqlite3.Connection, relogio: RelogioFalso) -> None:
    hora = relogio.agora().isoformat()
    gravar_sessao(con, "site", SITE, "conectado", None, relogio.agora())
    gravar_sessao(con, "conta", "gmail", "conectado", None, relogio.agora())
    esperada = Sessao("conectado", None, hora, hora, None)
    assert list(ler_sessoes(con, "site")) == [SITE]
    assert list(ler_sessoes(con, "conta")) == ["gmail"]
    # valores: `ler_sessoes` monta a `Sessao` por caminho próprio
    assert ler_sessoes(con, "site")[SITE] == esperada == ler_sessao(con, "site", SITE)
    assert ler_sessoes(con, "conta")["gmail"] == esperada == ler_sessao(con, "conta", "gmail")


def test_sem_insert_or_replace() -> None:
    # mutante: `INSERT OR REPLACE` no lugar do `ON CONFLICT`
    texto = ARQUIVO.read_text(encoding="utf-8").upper()
    assert "ON CONFLICT" in texto
    assert "OR REPLACE" not in texto
    assert "REPLACE INTO" not in texto


def test_abre_begin_immediate_e_confirma(con: sqlite3.Connection, relogio: RelogioFalso) -> None:
    # mutante: sem o `BEGIN IMMEDIATE` a leitura e a escrita não ficam sob o mesmo bloqueio
    visto: list[str] = []
    con.set_trace_callback(visto.append)
    gravar_sessao(con, "site", SITE, "conectado", None, relogio.agora())
    con.set_trace_callback(None)
    assert visto[0] == "BEGIN IMMEDIATE"
    assert con.in_transaction is False


def test_transacao_de_quem_chamou_fica_com_ele(
    con: sqlite3.Connection, relogio: RelogioFalso
) -> None:
    # mutante: `commit` ou `rollback` mesmo sem ter aberto a transação
    con.execute("BEGIN IMMEDIATE")
    gravar_sessao(con, "site", SITE, "conectado", None, relogio.agora())
    assert con.in_transaction is True
    con.rollback()
    assert ler_sessao(con, "site", SITE) is None
