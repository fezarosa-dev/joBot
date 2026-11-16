"""Quedas da barra lateral da casca, que abre o banco em toda página (E4; T251)."""

from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from starlette.requests import Request

from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.lateral import Lateral, lateral


def _pedido(banco: Path) -> Request:
    return cast(Request, SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(banco=banco))))


def test_sem_banco_nao_cria_o_arquivo(tmp_path: Path) -> None:
    """Guarda (mutante: tirar o `banco.exists()` de `lateral`)."""
    banco = tmp_path / "jobot.db"
    assert lateral(_pedido(banco)) == Lateral(True, 0, None)
    assert not banco.exists()


def test_destaques_ligados_estragado_volta_ao_padrao(tmp_path: Path) -> None:
    """Guarda (mutante: ler `destaques_ligados` com `json.loads` em vez de `ler_config`)."""
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        con.execute(
            "INSERT INTO config (chave, valor) VALUES ('destaques_ligados', 'nao-json') "
            "ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor"
        )
        con.commit()
    assert lateral(_pedido(banco)).destaques_ligados is True
