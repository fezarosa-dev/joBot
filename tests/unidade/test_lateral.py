"""Quedas da barra lateral da casca, que abre o banco em toda página (E4; T251)."""

from contextlib import closing
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from starlette.datastructures import QueryParams
from starlette.requests import Request

from apoio.relogio import RelogioFalso
from apoio.semear import AGORA, inserir_vaga
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.lateral import Lateral, lateral


def _pedido(banco: Path) -> Request:
    estado = SimpleNamespace(banco=banco, relogio=RelogioFalso())
    return cast(
        Request, SimpleNamespace(app=SimpleNamespace(state=estado), query_params=QueryParams())
    )


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


def test_destaques_n_estragado_nao_derruba_a_lateral(tmp_path: Path) -> None:
    """Guarda (mutante: `ids_destaques` ler `destaques_n` com `json.loads`, sem `try`)."""
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        con.execute(
            "INSERT INTO config (chave, valor) VALUES ('destaques_n', 'nao-json') "
            "ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor"
        )
        for _ in range(12):
            inserir_vaga(con, primeira_vista_em=(AGORA - timedelta(hours=1)).isoformat())
        con.commit()
    # o padrão é 10: com 12 vagas novas, um padrão mutante menor (ex. 1) não passa
    atual = lateral(_pedido(banco))
    assert atual.destaques_ligados is True
    assert atual.contagens["destaques"] == 10
