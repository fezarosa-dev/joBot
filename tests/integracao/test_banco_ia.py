"""Perfil, `habilidades_vaga`, contagem do dia e `ia_tarefas` no banco (T403; desenho 5.4, 8)."""

import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apoio.semear import inserir_vaga
from jobot.banco import ia, perfil
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir, tem_fts5
from jobot.banco.migrar import migrar

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fuso_local() -> Iterator[None]:
    """Fuso -03 sem depender do tzdata da máquina; desfeito no fim."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TZ", "<-03>3")
        time.tzset()
        yield
    time.tzset()


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    yield c
    c.close()


def _linha(con: sqlite3.Connection, vaga_id: int) -> dict[str, object]:
    cur = con.execute("SELECT * FROM habilidades_vaga WHERE vaga_id = ?", (vaga_id,))
    nomes = [d[0] for d in cur.description]
    linha = cur.fetchone()
    assert linha is not None
    return dict(zip(nomes, linha, strict=True))


def _pede(
    con: sqlite3.Connection,
    vaga_id: int,
    pede: list[str],
    chave: str = "c1",
    backend: str = "local",
    agora: datetime = T0,
) -> None:
    ia.gravar_pede(
        con, vaga_id, chave=chave, pede=pede, backend=backend, modelo="m", versao=1, agora=agora
    )


def _falha(
    con: sqlite3.Connection,
    vaga_id: int,
    chave: str = "c2",
    motivo: str = "formato",
    backend: str = "local",
    agora: datetime = T0,
) -> None:
    ia.gravar_falha(con, vaga_id, chave=chave, motivo=motivo, backend=backend, agora=agora)


# perfil


def test_perfil_salvo_duas_vezes_fica_uma_linha(con: sqlite3.Connection) -> None:
    perfil.gravar_habilidades(con, ["Python", "SQL"], T0)
    perfil.gravar_habilidades(con, ["Rust"], T0 + timedelta(hours=1))
    linhas = con.execute("SELECT id, habilidades, atualizado_em FROM perfil").fetchall()
    assert linhas == [(1, '["Rust"]', (T0 + timedelta(hours=1)).isoformat())]
    assert perfil.habilidades(con) == ["Rust"]


def test_perfil_ausente_le_lista_vazia(con: sqlite3.Connection) -> None:
    assert perfil.habilidades(con) == []
    perfil.gravar_habilidades(con, ["Go"], T0)  # controle: com a linha, a lista volta
    assert perfil.habilidades(con) == ["Go"]


@pytest.mark.parametrize("valor", ["não é json", '{"a": 1}', '["ok", 3]', "null"])
def test_perfil_adulterado_le_so_textos(con: sqlite3.Connection, valor: str) -> None:
    con.execute(
        "INSERT INTO perfil (id, habilidades, atualizado_em) VALUES (1, ?, ?)",
        (valor, T0.isoformat()),
    )
    con.commit()
    assert perfil.habilidades(con) == (["ok"] if valor.startswith("[") else [])


def test_apagar_perfil_apaga_a_linha_e_deixa_habilidades_vaga(con: sqlite3.Connection) -> None:
    vaga_id = inserir_vaga(con)
    _pede(con, vaga_id, ["Python"])
    perfil.gravar_habilidades(con, ["Python"], T0)
    assert con.execute("SELECT count(*) FROM perfil").fetchone()[0] == 1
    perfil.apagar_perfil(con)
    assert con.execute("SELECT count(*) FROM perfil").fetchone()[0] == 0
    assert _linha(con, vaga_id)["pede"] == '["Python"]'  # não depende do perfil (desenho 8)


# habilidades_vaga


def test_pede_gravado_duas_vezes_fica_uma_linha(con: sqlite3.Connection) -> None:
    vaga_id = inserir_vaga(con)
    _pede(con, vaga_id, ["Python"], chave="c1")
    _pede(
        con,
        vaga_id,
        ["Python", "Café"],
        chave="c2",
        backend="anthropic",
        agora=T0 + timedelta(hours=2),
    )
    assert con.execute("SELECT count(*) FROM habilidades_vaga").fetchone()[0] == 1
    linha = _linha(con, vaga_id)
    assert json.loads(str(linha["pede"])) == ["Python", "Café"]
    assert (linha["chave"], linha["backend"], linha["modelo"], linha["versao"]) == (
        "c2",
        "anthropic",
        "m",
        1,
    )
    assert linha["feito_em"] == (T0 + timedelta(hours=2)).isoformat()


def test_falha_nao_apaga_o_pede_anterior(con: sqlite3.Connection) -> None:
    vaga_id = inserir_vaga(con)
    _pede(con, vaga_id, ["Python"], chave="c1")
    _falha(
        con, vaga_id, chave="c2", motivo="contexto", backend="openai", agora=T0 + timedelta(hours=1)
    )
    linha = _linha(con, vaga_id)
    assert (linha["pede"], linha["chave"], linha["backend"], linha["feito_em"]) == (
        '["Python"]',
        "c1",
        "local",
        T0.isoformat(),
    )
    assert (linha["falha"], linha["falha_chave"], linha["falha_backend"]) == (
        "contexto",
        "c2",
        "openai",
    )
    assert linha["falha_em"] == (T0 + timedelta(hours=1)).isoformat()
    assert linha["tentativas"] == 1


def test_tentativas_contam_por_chave(con: sqlite3.Connection) -> None:
    vaga_id = inserir_vaga(con)
    _falha(con, vaga_id, chave="c1")  # sem linha: a falha cria a linha sem `pede`
    assert (_linha(con, vaga_id)["pede"], _linha(con, vaga_id)["tentativas"]) == (None, 1)
    _falha(con, vaga_id, chave="c1", motivo="recusa")
    assert (_linha(con, vaga_id)["falha"], _linha(con, vaga_id)["tentativas"]) == ("recusa", 2)
    _falha(con, vaga_id, chave="c9")  # chave nova recomeça
    assert _linha(con, vaga_id)["tentativas"] == 1
    _pede(con, vaga_id, ["Python"], chave="c9")  # o acerto não mexe na falha
    assert (_linha(con, vaga_id)["falha_chave"], _linha(con, vaga_id)["tentativas"]) == ("c9", 1)


def test_gravar_habilidades_vaga_nao_dispara_gatilho(con: sqlite3.Connection) -> None:
    """(guarda) Nenhum gatilho de `vaga`, de `evento` nem do FTS5 dispara ao gravar."""
    vaga_id = inserir_vaga(con)
    tabelas = ["vaga", "evento", "ocorrencia", "encaixe"] + (["vaga_fts"] if tem_fts5(con) else [])
    antes = {t: con.execute(f"SELECT * FROM {t}").fetchall() for t in tabelas}
    gravacoes: list[Callable[[], None]] = [
        lambda: _pede(con, vaga_id, ["Python"]),
        lambda: _falha(con, vaga_id),
    ]
    for gravar in gravacoes:
        mudancas = con.total_changes
        gravar()
        # total_changes conta as linhas mudadas por gatilhos: 1 é só a da própria gravação
        assert con.total_changes - mudancas == 1
    assert con.execute("SELECT count(*) FROM habilidades_vaga").fetchone()[0] == 1  # controle
    assert {t: con.execute(f"SELECT * FROM {t}").fetchall() for t in tabelas} == antes


# contagem do dia


def test_chamadas_do_dia_contam_cada_chamada_por_backend_e_dia_local(
    con: sqlite3.Connection,
) -> None:
    # agora: 01:00 UTC do dia 18, que é 22:00 do dia 17 no fuso -03
    agora = datetime(2026, 11, 18, 1, 0, tzinfo=UTC)
    vaga = inserir_vaga(con)
    for _ in range(3):
        ia.contar_chamada(con, "openai", agora)
    ia.contar_chamada(con, "local", agora)
    _falha(con, vaga, backend="openai", agora=agora)  # a linha da vaga não conta: só a chamada
    assert ia.chamadas_do_dia(con, "openai", agora) == 3
    assert ia.chamadas_do_dia(con, "local", agora) == 1
    assert ia.chamadas_do_dia(con, "gemini", agora) == 0
    # 00:30 do dia 18 local (03:30 UTC, o mesmo dia 18 em UTC): a contagem recomeça
    amanha = datetime(2026, 11, 18, 3, 30, tzinfo=UTC)
    assert ia.chamadas_do_dia(con, "openai", amanha) == 0
    ia.contar_chamada(con, "openai", amanha)
    assert ia.chamadas_do_dia(con, "openai", amanha) == 1
    assert ia.chamadas_do_dia(con, "local", amanha) == 0


def test_contagem_estragada_na_config_recomeca(con: sqlite3.Connection) -> None:
    for estragado in ("x", {"dia": T0.astimezone().date().isoformat(), "por_backend": "x"}):
        gravar_config(con, "ia_chamadas", estragado)
        assert ia.chamadas_do_dia(con, "openai", T0) == 0
        ia.contar_chamada(con, "openai", T0)
        assert ia.chamadas_do_dia(con, "openai", T0) == 1


# ia_tarefas


@pytest.mark.parametrize("tarefa", ["encaixe", "curriculo", "perguntas", "candidatura"])
def test_ia_tarefas_sem_valor_le_tudo_desligado(con: sqlite3.Connection, tarefa: str) -> None:
    assert ia.tarefa_ia(con, tarefa) == ia.TarefaIA(ligada=False, backend="", modelo="")


def test_ia_tarefas_gravada_le_ligada(con: sqlite3.Connection) -> None:
    gravar_config(
        con, "ia_tarefas", {"encaixe": {"ligada": True, "backend": "local", "modelo": "qwen"}}
    )
    assert ia.tarefa_ia(con, "encaixe") == ia.TarefaIA(ligada=True, backend="local", modelo="qwen")
    assert ia.tarefa_ia(con, "curriculo").ligada is False


def test_ia_manual_liga_sem_modelo(con: sqlite3.Connection) -> None:
    """A IA manual não tem modelo: o joBot não sabe qual chat a pessoa usa (D229.5, D232)."""
    gravar_config(
        con, "ia_tarefas", {"curriculo": {"ligada": True, "backend": "manual", "modelo": ""}}
    )
    assert ia.tarefa_ia(con, "curriculo") == ia.TarefaIA(ligada=True, backend="manual", modelo="")
    # controle: sem modelo, outro backend segue desligado
    gravar_config(
        con, "ia_tarefas", {"curriculo": {"ligada": True, "backend": "local", "modelo": ""}}
    )
    assert ia.tarefa_ia(con, "curriculo").ligada is False


@pytest.mark.parametrize(
    "valor",
    [
        [],
        {"encaixe": "sim"},
        {"encaixe": {"ligada": 1, "backend": "local", "modelo": "qwen"}},
        {"encaixe": {"ligada": True, "backend": "", "modelo": "qwen"}},
        {"encaixe": {"ligada": True, "backend": "local", "modelo": 3}},
        {"encaixe": {"ligada": True, "backend": "local"}},
    ],
)
def test_ia_tarefas_estranha_le_desligada(con: sqlite3.Connection, valor: object) -> None:
    gravar_config(con, "ia_tarefas", valor)
    assert ia.tarefa_ia(con, "encaixe").ligada is False
