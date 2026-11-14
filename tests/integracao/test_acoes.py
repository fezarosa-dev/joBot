"""Ações da pessoa e histórico em `evento` (desenho 7.6, critério 34; plano T21)."""

import sqlite3
import threading
from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from apoio.relogio import RelogioFalso
from jobot.banco import acoes
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.relogio import Relogio

relogio: Relogio = RelogioFalso()


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    c.execute(
        "INSERT INTO vaga (id, url_hash, titulo, empresa, url, primeira_vista_em,"
        " ultima_vista_em, versao_regras) VALUES (1, 'h1', 't', 'e', 'https://x.test/1',"
        " '2026-11-13', '2026-11-13', 'v1')"
    )
    c.commit()
    yield c
    c.close()


def _eventos(con: sqlite3.Connection) -> list[tuple[str, str | None, str | None, str]]:
    return con.execute("SELECT acao, de, para, criado_em FROM evento ORDER BY id").fetchall()


def _vaga(con: sqlite3.Connection) -> tuple[str, str | None, int]:
    linha = con.execute("SELECT status, status_em, oculta_manual FROM vaga WHERE id=1").fetchone()
    return (linha[0], linha[1], linha[2])


def test_cada_acao_grava_um_evento_com_data(con: sqlite3.Connection) -> None:
    t0 = relogio.agora()
    passos: list[tuple[Callable[[], None], tuple[str, str | None, str | None]]] = [
        (lambda: acoes.mudar_status(con, 1, "salva", t0), ("salvou", "nova", "salva")),
        (
            lambda: acoes.mudar_status(con, 1, "candidatei", t0 + timedelta(hours=1)),
            ("mudou_status", "salva", "candidatei"),
        ),
        (
            lambda: acoes.desfazer_status(con, 1, t0 + timedelta(hours=2)),
            ("desfez", "candidatei", "salva"),
        ),
        (lambda: acoes.ocultar(con, 1, t0 + timedelta(hours=3)), ("ocultou", None, None)),
        (
            lambda: acoes.trazer_de_volta(con, 1, t0 + timedelta(hours=4)),
            ("desfez", None, None),
        ),
        (lambda: acoes.mostrar(con, 1, t0 + timedelta(hours=5)), ("mostrou", None, None)),
    ]
    for i, (agir, esperado) in enumerate(passos):
        agir()
        eventos = _eventos(con)
        assert len(eventos) == i + 1, f"passo {i}: um evento por ação"
        assert eventos[-1][:3] == esperado
        assert eventos[-1][3] == (t0 + timedelta(hours=i)).isoformat()


def test_status_em_acompanha_o_relogio(con: sqlite3.Connection) -> None:
    t0 = relogio.agora()
    acoes.mudar_status(con, 1, "salva", t0)
    assert _vaga(con)[1] == t0.isoformat()
    t1 = t0 + timedelta(hours=1)
    acoes.mudar_status(con, 1, "candidatei", t1)
    assert _vaga(con)[1] == t1.isoformat()
    t2 = t1 + timedelta(hours=1)
    acoes.desfazer_status(con, 1, t2)
    assert _vaga(con)[:2] == ("salva", t2.isoformat())


def test_sem_mudanca_nao_grava_evento_nem_mexe_em_status_em(con: sqlite3.Connection) -> None:
    t0 = relogio.agora()
    acoes.mudar_status(con, 1, "salva", t0)
    acoes.ocultar(con, 1, t0)
    antes = (_eventos(con), _vaga(con))
    depois = t0 + timedelta(hours=1)
    acoes.mudar_status(con, 1, "salva", depois)  # mesmo status
    acoes.ocultar(con, 1, depois)  # já oculta
    assert (_eventos(con), _vaga(con)) == antes
    assert _vaga(con)[1] == t0.isoformat()


def test_transacao_recusa_conexao_ja_em_transacao(con: sqlite3.Connection) -> None:
    con.execute("UPDATE vaga SET titulo='outro' WHERE id=1")  # abre transação do chamador
    assert con.in_transaction
    with pytest.raises(RuntimeError, match="transação"):
        acoes.mudar_status(con, 1, "salva", relogio.agora())
    assert con.in_transaction  # não consolidou nem desfez a do chamador
    con.rollback()
    assert _eventos(con) == []
    assert _vaga(con) == ("nova", None, 0)


def test_candidatei_para_salva_grava_desfez_e_nao_salvou(con: sqlite3.Connection) -> None:
    t0 = relogio.agora()
    voltas: list[Callable[[], None]] = [
        lambda: acoes.mudar_status(con, 1, "salva", t0),
        lambda: acoes.desfazer_status(con, 1, t0),
    ]
    for volta in voltas:
        con.execute("UPDATE vaga SET status='candidatei' WHERE id=1")
        con.commit()
        antes = len(_eventos(con))
        volta()
        novos = _eventos(con)[antes:]
        assert novos == [("desfez", "candidatei", "salva", t0.isoformat())]
    assert all(e[0] != "salvou" for e in _eventos(con))
    assert _vaga(con)[0] == "salva"


def test_evento_na_mesma_transacao(con: sqlite3.Connection) -> None:
    # falha ao gravar o evento: a mudança na vaga também não fica
    con.execute(
        "CREATE TEMP TRIGGER falha_evento BEFORE INSERT ON main.evento"
        " BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    with pytest.raises(sqlite3.DatabaseError):
        acoes.mudar_status(con, 1, "salva", relogio.agora())
    with pytest.raises(sqlite3.DatabaseError):
        acoes.ocultar(con, 1, relogio.agora())
    assert _vaga(con) == ("nova", None, 0)
    con.execute("DROP TRIGGER falha_evento")
    # falha na mudança da vaga: nenhum evento
    con.execute(
        "CREATE TEMP TRIGGER falha_vaga BEFORE UPDATE ON main.vaga"
        " BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    with pytest.raises(sqlite3.DatabaseError):
        acoes.mudar_status(con, 1, "salva", relogio.agora())
    assert _eventos(con) == []
    con.execute("DROP TRIGGER falha_vaga")
    # sucesso: gravado de fato (outra conexão enxerga)
    acoes.mudar_status(con, 1, "salva", relogio.agora())
    outra = sqlite3.connect(con.execute("PRAGMA database_list").fetchone()[2])
    try:
        assert outra.execute("SELECT count(*) FROM evento").fetchone()[0] == 1
    finally:
        outra.close()


def test_correcao_nao_grava_evento(con: sqlite3.Connection) -> None:
    con.execute("UPDATE vaga SET nivel='senior' WHERE id=1")
    con.commit()
    acoes.corrigir(con, 1, "nivel", "junior", "era estágio", relogio.agora())
    assert _eventos(con) == []
    linha = con.execute(
        "SELECT vaga_id, campo, valor_antigo, valor_novo, comentario, criada_em FROM correcao"
    ).fetchall()
    assert linha == [(1, "nivel", "senior", "junior", "era estágio", relogio.agora().isoformat())]
    with pytest.raises(ValueError):
        acoes.corrigir(con, 1, "cor_do_logo", "azul", None, relogio.agora())
    assert con.execute("SELECT count(*) FROM correcao").fetchone()[0] == 1


def test_status_invalido_levanta(con: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        acoes.mudar_status(con, 1, "contratado", relogio.agora())
    with pytest.raises(LookupError):
        acoes.mudar_status(con, 999, "salva", relogio.agora())
    with pytest.raises(ValueError):
        acoes.desfazer_status(con, 1, relogio.agora())  # "nova" não tem anterior
    assert _eventos(con) == []
    assert _vaga(con) == ("nova", None, 0)


def test_oculta_manual_valores(con: sqlite3.Connection) -> None:
    t = relogio.agora()
    assert _vaga(con)[2] == 0  # as regras decidem
    acoes.ocultar(con, 1, t)
    assert _vaga(con)[2] == 1  # à mão
    acoes.trazer_de_volta(con, 1, t)
    assert _vaga(con)[2] == 0
    acoes.mostrar(con, 1, t)
    assert _vaga(con)[2] == -1  # mostrar mesmo assim
    acoes.ocultar(con, 1, t)
    assert _vaga(con)[2] == 1
    with pytest.raises(ValueError):
        acoes.mostrar(con, 1, t)  # ocultada à mão volta por trazer_de_volta
    acoes.trazer_de_volta(con, 1, t)
    with pytest.raises(ValueError):
        acoes.trazer_de_volta(con, 1, t)  # não estava ocultada à mão
    assert [e[0] for e in _eventos(con)] == ["ocultou", "desfez", "mostrou", "ocultou", "desfez"]


def test_estado_lido_dentro_da_transacao(con: sqlite3.Connection) -> None:
    caminho = Path(con.execute("PRAGMA database_list").fetchone()[2])
    outra = abrir(caminho)
    resultado: list[BaseException] = []
    no_begin = threading.Event()

    def acao_concorrente() -> None:
        c = abrir(caminho)
        # o BEGIN do fio chega ao SQLite: a leitura do código antigo já foi feita
        c.set_trace_callback(lambda sql: no_begin.set() if sql.startswith("BEGIN") else None)
        try:
            acoes.mudar_status(c, 1, "salva", relogio.agora())
        except BaseException as e:  # noqa: BLE001 - o teste só confere que não falhou
            resultado.append(e)
        finally:
            c.close()

    try:
        outra.execute("BEGIN IMMEDIATE")  # segura a escrita
        fio = threading.Thread(target=acao_concorrente)
        fio.start()
        assert no_begin.wait(timeout=10)
        outra.execute("UPDATE vaga SET status='candidatei' WHERE id=1")
        outra.commit()
        fio.join(timeout=10)
    finally:
        outra.close()
    assert resultado == []
    # o evento vê o status novo: voltar de candidatei para salva é desfez, não salvou
    assert _eventos(con)[0][:3] == ("desfez", "candidatei", "salva")
