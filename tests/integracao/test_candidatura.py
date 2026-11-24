"""Abertura da candidatura, respostas e Desfazer (plano T281, desenho 5.5 e 5.6)."""

import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from apoio.semear import inserir_vaga
from jobot.banco import acoes
from jobot.banco.conexao import abrir
from jobot.banco.leitura import Pergunta, abertura_da_candidatura, perguntas_pendentes
from jobot.banco.migrar import migrar

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
BRASILIA = timezone(timedelta(hours=-3))


def _quando(n: int) -> datetime:
    return T0 + timedelta(hours=n)


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


def _vaga(con: sqlite3.Connection, status: str = "salva") -> int:
    return inserir_vaga(con, status=status)


def _aberta(con: sqlite3.Connection, status: str = "salva", hora: int = 0) -> int:
    vaga_id = _vaga(con, status)
    assert acoes.abriu_candidatura(con, vaga_id, _quando(hora)) is True
    return vaga_id


def _status(con: sqlite3.Connection, vaga_id: int) -> str:
    status: str = con.execute("SELECT status FROM vaga WHERE id = ?", (vaga_id,)).fetchone()[0]
    return status


def _perguntar(con: sqlite3.Connection, vaga_id: int) -> int | None:
    linha = con.execute(
        "SELECT perguntar FROM candidatura WHERE vaga_id = ?", (vaga_id,)
    ).fetchone()
    return None if linha is None else int(linha[0])


def _eventos(con: sqlite3.Connection, vaga_id: int) -> list[tuple[str, str | None, str | None]]:
    return con.execute(
        "SELECT acao, de, para FROM evento WHERE vaga_id = ? ORDER BY id", (vaga_id,)
    ).fetchall()


def _recusa(acao: Callable[[], object], erro: type[Exception]) -> bool:
    """Verdadeiro se a ação lança `erro`."""
    try:
        acao()
    except erro:
        return True
    return False


# Abertura


def test_abriu_grava_e_reabre_pergunta(con: sqlite3.Connection) -> None:
    v = _vaga(con)
    assert acoes.abriu_candidatura(con, v, _quando(0)) is True
    assert abertura_da_candidatura(con, v) == _quando(0).isoformat()
    assert _perguntar(con, v) == 1
    assert acoes.responder_candidatura(con, v, False, _quando(1)) is None
    assert _perguntar(con, v) == 0
    assert acoes.abriu_candidatura(con, v, _quando(2)) is True
    assert abertura_da_candidatura(con, v) == _quando(2).isoformat()
    assert _perguntar(con, v) == 1


def test_abriu_com_candidatei_nao_grava(con: sqlite3.Connection) -> None:
    candidatei = _vaga(con, "candidatei")
    salva = _vaga(con, "salva")
    assert acoes.abriu_candidatura(con, salva, _quando(0)) is True  # controle positivo
    assert acoes.abriu_candidatura(con, candidatei, _quando(0)) is False
    assert _perguntar(con, candidatei) is None


def test_abriu_vaga_inexistente_lookuperror(con: sqlite3.Connection) -> None:
    assert _recusa(lambda: acoes.abriu_candidatura(con, 999, _quando(0)), LookupError) is True


# Respostas


def test_responder_sim_muda_status_e_fecha_pergunta(con: sqlite3.Connection) -> None:
    v = _aberta(con)
    acoes.responder_candidatura(con, v, True, _quando(1))
    assert _status(con, v) == "candidatei"
    assert _perguntar(con, v) == 0


def test_responder_sim_grava_evento_mudou_status(con: sqlite3.Connection) -> None:
    v = _aberta(con, "salva")
    acoes.responder_candidatura(con, v, True, _quando(1))
    assert _eventos(con, v) == [("mudou_status", "salva", "candidatei")]
    assert (
        con.execute(
            "SELECT criado_em FROM evento WHERE vaga_id = ? ORDER BY id DESC", (v,)
        ).fetchone()[0]
        == _quando(1).isoformat()
    )


def test_responder_sim_devolve_o_status_de_antes(con: sqlite3.Connection) -> None:
    nova = _aberta(con, "nova")
    salva = _aberta(con, "salva")
    assert acoes.responder_candidatura(con, nova, True, _quando(1)) == "nova"
    assert acoes.responder_candidatura(con, salva, True, _quando(1)) == "salva"


def test_responder_ainda_nao_so_fecha(con: sqlite3.Connection) -> None:
    v = _aberta(con, "salva")
    assert acoes.responder_candidatura(con, v, False, _quando(1)) is None
    assert _perguntar(con, v) == 0
    assert _status(con, v) == "salva"
    assert _eventos(con, v) == []


def test_responder_duas_vezes_nao_muda_nada(con: sqlite3.Connection) -> None:
    v = _aberta(con, "salva")
    assert acoes.responder_candidatura(con, v, True, _quando(1)) == "salva"  # controle
    eventos = _eventos(con, v)
    assert acoes.responder_candidatura(con, v, True, _quando(2)) is None
    assert _eventos(con, v) == eventos
    assert _status(con, v) == "candidatei"


def test_responder_sim_depois_de_ainda_nao_nao_muda(con: sqlite3.Connection) -> None:
    # a vaga continua salva: só o `perguntar = 0` impede o Sim velho de valer
    v = _aberta(con, "salva")
    assert acoes.responder_candidatura(con, v, False, _quando(1)) is None
    assert acoes.responder_candidatura(con, v, True, _quando(2)) is None
    assert _status(con, v) == "salva"
    assert _eventos(con, v) == []


# Pendentes


def _titulo_empresa(con: sqlite3.Connection, vaga_id: int) -> tuple[str, str]:
    linha = con.execute("SELECT titulo, empresa FROM vaga WHERE id = ?", (vaga_id,)).fetchone()
    return linha[0], linha[1]


def test_pendentes_so_nova_e_salva(con: sqlite3.Connection) -> None:
    salva = _aberta(con, "salva", 0)
    candidatei = _aberta(con, "salva", 1)
    acoes.mudar_status(con, candidatei, "candidatei", _quando(2))  # `perguntar` continua 1
    assert _perguntar(con, candidatei) == 1
    titulo, empresa = _titulo_empresa(con, salva)
    assert perguntas_pendentes(con, 10) == (
        [Pergunta(salva, titulo, empresa, _quando(0).isoformat(), "salva")],
        1,
    )


def test_pendentes_sem_oculta_a_mao(con: sqlite3.Connection) -> None:
    oculta = _aberta(con, "salva", 0)
    mostrada = _aberta(con, "salva", 1)
    sem_nada = _aberta(con, "nova", 2)
    acoes.ocultar(con, oculta, _quando(3))  # 1: à mão
    acoes.mostrar(con, mostrada, _quando(3))  # -1: mostrar mesmo assim
    lista, total = perguntas_pendentes(con, 10)
    assert [p.vaga_id for p in lista] == [sem_nada, mostrada]
    assert total == 2


def test_pendentes_mais_recente_primeiro(con: sqlite3.Connection) -> None:
    # 10:00 em -03:00 é 13:00 em UTC: mais recente que 12:30 UTC, ao contrário da ordem do texto
    depois = _vaga(con)
    antes = _vaga(con)
    assert acoes.abriu_candidatura(con, depois, datetime(2026, 11, 16, 10, 0, tzinfo=BRASILIA))
    assert acoes.abriu_candidatura(con, antes, datetime(2026, 11, 16, 12, 30, tzinfo=UTC))
    lista, total = perguntas_pendentes(con, 10)
    assert [p.vaga_id for p in lista] == [depois, antes]
    assert [p.abriu_em for p in lista] == ["2026-11-16T10:00:00-03:00", "2026-11-16T12:30:00+00:00"]
    assert total == 2


def test_pendentes_limite_e_total(con: sqlite3.Connection) -> None:
    ids = [_aberta(con, "salva", n) for n in range(3)]
    lista, total = perguntas_pendentes(con, 2)
    assert [p.vaga_id for p in lista] == [ids[2], ids[1]]
    assert total == 3


def test_abertura_da_candidatura(con: sqlite3.Connection) -> None:
    aberta = _aberta(con, "salva", 0)
    outra = _vaga(con)
    assert abertura_da_candidatura(con, aberta) == _quando(0).isoformat()
    assert abertura_da_candidatura(con, outra) is None


# Desfazer


def test_desfazer_volta_e_grava_desfez(con: sqlite3.Connection) -> None:
    v = _aberta(con, "salva")
    acoes.responder_candidatura(con, v, True, _quando(1))
    assert acoes.desfazer_candidatura(con, v, _quando(2)) is True
    assert _status(con, v) == "salva"
    assert _eventos(con, v)[-1] == ("desfez", "candidatei", "salva")


def test_desfazer_volta_ao_de_do_ultimo_evento(con: sqlite3.Connection) -> None:
    v = _aberta(con, "nova")
    acoes.responder_candidatura(con, v, True, _quando(1))
    assert acoes.desfazer_candidatura(con, v, _quando(2)) is True
    assert _status(con, v) == "nova"  # não `salva`, o anterior do fluxo
    assert _eventos(con, v)[-1] == ("desfez", "candidatei", "nova")


def test_desfazer_so_com_status_candidatei(con: sqlite3.Connection) -> None:
    controle = _aberta(con, "salva", 0)
    v = _aberta(con, "salva", 0)
    acoes.responder_candidatura(con, controle, True, _quando(1))
    acoes.responder_candidatura(con, v, True, _quando(1))
    acoes.mudar_status(con, v, "entrevista", _quando(2))
    assert acoes.desfazer_candidatura(con, controle, _quando(3)) is True
    eventos = _eventos(con, v)
    assert acoes.desfazer_candidatura(con, v, _quando(3)) is False
    assert _status(con, v) == "entrevista"
    assert _eventos(con, v) == eventos


def test_desfazer_com_relogio_que_voltou_nao_tira_da_entrevista(con: sqlite3.Connection) -> None:
    controle = _aberta(con, "salva", 0)
    v = _aberta(con, "salva", 0)
    acoes.responder_candidatura(con, controle, True, _quando(2))
    acoes.responder_candidatura(con, v, True, _quando(2))
    # o relógio voltou: a entrevista tem instante menor que o do Sim
    acoes.mudar_status(con, v, "entrevista", _quando(1))
    assert acoes.desfazer_candidatura(con, controle, _quando(3)) is True
    eventos = _eventos(con, v)
    assert acoes.desfazer_candidatura(con, v, _quando(3)) is False
    assert _status(con, v) == "entrevista"
    assert _eventos(con, v) == eventos


def test_desfazer_depois_de_desfez_nao_muda(con: sqlite3.Connection) -> None:
    v = _aberta(con, "salva")
    acoes.responder_candidatura(con, v, True, _quando(1))
    acoes.mudar_status(con, v, "entrevista", _quando(2))
    acoes.desfazer_status(con, v, _quando(3))  # volta a candidatei com `desfez`
    assert _status(con, v) == "candidatei"
    eventos = _eventos(con, v)
    assert acoes.desfazer_candidatura(con, v, _quando(4)) is False
    assert _status(con, v) == "candidatei"
    assert _eventos(con, v) == eventos


def test_desfazer_com_relogio_que_volta(con: sqlite3.Connection) -> None:
    """O último evento de status é o último gravado (id), não o de maior instante (D151)."""
    v = _aberta(con, "salva")
    acoes.responder_candidatura(con, v, True, _quando(5))
    acoes.mudar_status(con, v, "entrevista", _quando(1))  # relógio voltou
    acoes.desfazer_status(con, v, _quando(2))  # volta a candidatei com `desfez`
    assert _status(con, v) == "candidatei"
    eventos = _eventos(con, v)
    assert acoes.desfazer_candidatura(con, v, _quando(6)) is False
    assert _status(con, v) == "candidatei"
    assert _eventos(con, v) == eventos


def test_desfazer_ignora_desfez_da_ocultacao(con: sqlite3.Connection) -> None:
    v = _aberta(con, "salva")
    acoes.responder_candidatura(con, v, True, _quando(1))
    acoes.ocultar(con, v, _quando(2))
    acoes.trazer_de_volta(con, v, _quando(3))  # `desfez` sem `de` nem `para`
    assert _eventos(con, v)[-1] == ("desfez", None, None)
    assert acoes.desfazer_candidatura(con, v, _quando(4)) is True
    assert _status(con, v) == "salva"
    assert _eventos(con, v)[-1] == ("desfez", "candidatei", "salva")


def test_desfazer_nao_reabre_pergunta(con: sqlite3.Connection) -> None:
    v = _aberta(con, "salva")
    acoes.responder_candidatura(con, v, True, _quando(1))
    acoes.desfazer_candidatura(con, v, _quando(2))
    assert _status(con, v) == "salva"
    assert perguntas_pendentes(con, 10) == ([], 0)
    assert _perguntar(con, v) == 0


# Corrida


def test_responder_le_dentro_da_transacao(con: sqlite3.Connection) -> None:
    v = _aberta(con, "salva")
    caminho = Path(con.execute("PRAGMA database_list").fetchone()[2])
    outra = abrir(caminho)
    resultado: list[object] = []
    no_begin = threading.Event()

    def resposta_concorrente() -> None:
        c = abrir(caminho)
        # o BEGIN do fio chega ao SQLite antes da leitura de `perguntar`
        c.set_trace_callback(lambda sql: no_begin.set() if sql.startswith("BEGIN") else None)
        try:
            resultado.append(acoes.responder_candidatura(c, v, True, _quando(2)))
        except BaseException as e:  # noqa: BLE001 - o teste confere que não falhou
            resultado.append(e)
        finally:
            c.close()

    try:
        outra.execute("BEGIN IMMEDIATE")  # outra aba responde primeiro
        fio = threading.Thread(target=resposta_concorrente)
        fio.start()
        assert no_begin.wait(timeout=10)
        outra.execute("UPDATE candidatura SET perguntar = 0 WHERE vaga_id = ?", (v,))
        outra.commit()
        fio.join(timeout=10)
    finally:
        outra.close()
    assert resultado == [None]  # viu a pergunta já respondida
    assert _status(con, v) == "salva"
    assert [e[0] for e in _eventos(con, v)] == []
