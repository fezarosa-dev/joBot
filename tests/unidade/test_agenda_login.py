"""Hora da leitura com login (plano T206; desenho A6)."""

import os
import time as relogio_do_sistema
from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta, timezone

import pytest

from jobot.agenda.agendador import o_que_roda
from jobot.agenda.login import (
    INTERVALO_MINIMO,
    JANELA_HORARIO,
    Login,
    login_vencido,
    pode_ler_agora,
)
from jobot.banco.execucoes import Tipo

BRT = timezone(timedelta(hours=-3))
HORARIOS = (time(9), time(18))
ONTEM_18H = datetime(2026, 11, 14, 18, 0, tzinfo=BRT)


@pytest.fixture(autouse=True)
def fuso_local() -> Iterator[None]:
    antes = os.environ.get("TZ")
    os.environ["TZ"] = "America/Sao_Paulo"
    relogio_do_sistema.tzset()
    yield
    if antes is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = antes
    relogio_do_sistema.tzset()


def _dia15(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 11, 15, hora, minuto, tzinfo=BRT)


def _vence(agora: datetime, ultima: datetime | None) -> bool:
    return login_vencido(agora, HORARIOS, ultima)


def test_valores_do_plano() -> None:
    assert JANELA_HORARIO == timedelta(minutes=15)
    assert INTERVALO_MINIMO == timedelta(hours=4)


def test_vence_as_9h() -> None:
    assert _vence(_dia15(9), ONTEM_18H)
    assert _vence(_dia15(9), None)


def test_nao_vence_as_9h05_com_leitura_as_9h01() -> None:
    assert not _vence(_dia15(9, 5), _dia15(9, 1))


def test_vence_as_9h14() -> None:
    assert _vence(_dia15(9, 14), ONTEM_18H)


def test_nao_vence_as_9h16_sem_leitura_desde_ontem() -> None:
    assert not _vence(_dia15(9, 16), ONTEM_18H)
    assert not _vence(_dia15(9, 15), ONTEM_18H)  # a janela é aberta no fim


def test_fechou_o_navegador_as_9h02_nao_reabre_as_9h03() -> None:
    # a leitura das 9h começou às 9h00 e a pessoa fechou às 9h02 (interrompida conta)
    assert not _vence(_dia15(9, 3), _dia15(9))


def test_erro_as_9h01_nao_repete_na_janela() -> None:
    for minuto in range(2, 15):
        assert not _vence(_dia15(9, minuto), _dia15(9))


def test_perdeu_as_9h_ligou_as_15h() -> None:
    assert not _vence(_dia15(15), ONTEM_18H)
    assert _vence(_dia15(18), _dia15(14))
    assert not _vence(_dia15(18), _dia15(15, 30))
    assert _vence(datetime(2026, 11, 16, 9, 0, tzinfo=BRT), _dia15(15, 30))


def test_buscar_agora_as_16h_pula_as_18h() -> None:
    assert pode_ler_agora(_dia15(16), _dia15(9))
    assert not _vence(_dia15(18), _dia15(16))
    assert not _vence(_dia15(18, 5), _dia15(16))
    assert _vence(datetime(2026, 11, 16, 9, 0, tzinfo=BRT), _dia15(16))


def test_ligou_as_20h_depois_de_perder_as_duas() -> None:
    assert not _vence(_dia15(20), ONTEM_18H)
    assert _vence(datetime(2026, 11, 16, 9, 0, tzinfo=BRT), ONTEM_18H)


def test_ultima_no_futuro_nao_trava() -> None:
    assert _vence(_dia15(9), datetime(2026, 11, 16, 9, 0, tzinfo=BRT))


def test_fora_de_utc_usa_o_dia_local() -> None:
    # 23:10 de 15/11 em São Paulo é 02:10 de 16/11 em UTC
    assert login_vencido(datetime(2026, 11, 16, 2, 10, tzinfo=UTC), [time(23)], None)
    assert not login_vencido(datetime(2026, 11, 16, 0, 30, tzinfo=BRT), [time(23)], None)
    # o horário de ontem, no dia local, ainda vale logo depois da meia-noite
    assert login_vencido(datetime(2026, 11, 16, 0, 5, tzinfo=BRT), [time(23, 55)], None)


@pytest.mark.parametrize(
    ("ultima", "pode"),
    [
        (None, True),
        (_dia15(12, 1), True),  # no futuro: relógio voltou
        (_dia15(12) - timedelta(hours=3, minutes=59), False),
        (_dia15(12) - timedelta(hours=4), True),
    ],
    ids=["nula", "futuro", "3h59", "4h00"],
)
def test_pode_ler_agora(ultima: datetime | None, pode: bool) -> None:
    assert pode_ler_agora(_dia15(12), ultima) is pode


AGORA = _dia15(9)
RECENTE = AGORA - timedelta(minutes=1)
INICIOU = AGORA - timedelta(hours=1)
LIGADOS = {"busca": True, "descoberta": True, "paginas": True}
VENCIDO = Login(HORARIOS, ONTEM_18H)


def _roda(
    login: Login | None,
    *,
    interruptores: dict[str, bool] = LIGADOS,
    iniciou_em: datetime = INICIOU,
    busca: datetime | None = RECENTE,
) -> list[Tipo]:
    return o_que_roda(AGORA, busca, RECENTE, RECENTE, iniciou_em, interruptores, login=login)


def test_o_que_roda_sem_login_fica_igual() -> None:
    assert o_que_roda(AGORA, None, None, None, INICIOU, LIGADOS) == [
        "busca",
        "descoberta",
        "paginas",
    ]
    assert _roda(None, busca=None) == ["busca"]


def test_o_que_roda_com_login_vencido_poe_login_por_ultimo() -> None:
    assert _roda(VENCIDO, busca=None) == ["busca", "login"]
    assert _roda(VENCIDO) == ["login"]
    assert _roda(Login(HORARIOS, _dia15(9))) == []  # já leu às 9h


def test_login_nao_roda_nos_primeiros_60_s() -> None:
    assert _roda(VENCIDO, iniciou_em=AGORA - timedelta(seconds=59)) == []
    assert _roda(VENCIDO, iniciou_em=AGORA - timedelta(seconds=60)) == ["login"]


def test_login_desligado_pelo_interruptor() -> None:
    assert _roda(VENCIDO, interruptores={**LIGADOS, "login": False}) == []
    assert _roda(VENCIDO, interruptores={**LIGADOS, "login": True}) == ["login"]


def test_sem_site_ligado_nao_roda() -> None:
    assert _roda(None) == []
