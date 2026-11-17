"""Cartões de saúde e próxima busca fora de `rotas/`, sem cópia (E4; T283)."""

import ast
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jobot.agenda.agendador import INTERVALOS
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao
from jobot.banco.migrar import migrar
from jobot.painel.saude_das_fontes import proxima_busca

PAINEL = Path(__file__).resolve().parents[2] / "src/jobot/painel"
NOVE = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as conexao:
        migrar(conexao, banco)
        yield conexao


def _busca_completa(con: sqlite3.Connection, inicio: datetime) -> None:
    id_ = abrir_execucao(con, "busca", "agenda", inicio)
    assert id_ is not None
    fechar_execucao(con, id_, inicio + timedelta(minutes=5))


@pytest.mark.usefixtures("fuso_de_sao_paulo")
def test_proxima_busca_tres_horas_depois(con: sqlite3.Connection) -> None:
    _busca_completa(con, NOVE)
    proxima = proxima_busca(con, NOVE + timedelta(hours=1))
    assert proxima == NOVE + timedelta(hours=3)
    assert proxima is not None
    assert proxima.utcoffset() == timedelta(hours=-3)  # no fuso local, não em UTC


def test_proxima_com_relogio_que_voltou(con: sqlite3.Connection) -> None:
    _busca_completa(con, NOVE)
    assert proxima_busca(con, NOVE - timedelta(hours=1)) is None
    # controle: com `agora` depois do início, a mesma montagem dá a hora
    assert proxima_busca(con, NOVE + timedelta(minutes=1)) == NOVE + INTERVALOS["busca"]


def test_sem_busca_completa_none(con: sqlite3.Connection) -> None:
    assert proxima_busca(con, NOVE) is None


def _definicoes(nome: str) -> list[str]:
    """Onde `nome` é definido como função em `painel/`, fora de `rotas/`."""
    return [
        f"{caminho.relative_to(PAINEL)}"
        for caminho in PAINEL.rglob("*.py")
        if "rotas" not in caminho.relative_to(PAINEL).parts
        for n in ast.walk(ast.parse(caminho.read_text(encoding="utf-8")))
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == nome
    ]


def test_definidos_uma_vez() -> None:
    assert _definicoes("cartoes") == ["saude_das_fontes.py"]
    assert _definicoes("proxima_busca") == ["saude_das_fontes.py"]
    assert _definicoes("contas_em_queda") == ["consultas.py"]
    for rota in (PAINEL / "rotas").glob("*.py"):
        nomes = {
            n.name
            for n in ast.walk(ast.parse(rota.read_text(encoding="utf-8")))
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        assert not nomes & {"_cartoes", "cartoes", "contas_em_queda", "proxima_busca"}, rota.name


def _importados(caminho: Path) -> set[str]:
    nomes: set[str] = set()
    for n in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            nomes |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            nomes |= {n.module, *(f"{n.module}.{a.name}" for a in n.names)}
    return {m for m in nomes if m.startswith("jobot.painel.rotas")}


def test_saude_nao_importa_rotas() -> None:
    assert _importados(PAINEL / "saude_das_fontes.py") == set()
    assert _importados(PAINEL / "consultas.py") == set()
