"""Horários de parede da leitura com login (plano T204; D132.48)."""

from datetime import time

import pytest

from jobot.nucleo.horarios import horarios_validos

_CHAVE = "configuracoes.sites_com_login.horarios."


def test_horarios_validos_aceita_o_padrao() -> None:
    assert horarios_validos(["09:00", "18:00"]) == (time(9), time(18))


def test_horarios_validos_ordena() -> None:
    assert horarios_validos(["18:30", "06:00", "12:15"]) == (time(6), time(12, 15), time(18, 30))


def test_horarios_validos_aceita_um_e_quatro() -> None:
    assert horarios_validos(["23:59"]) == (time(23, 59),)
    assert len(horarios_validos(["00:00", "06:00", "12:00", "18:00"])) == 4


@pytest.mark.parametrize(
    ("valor", "chave"),
    [
        (["9:00"], "formato"),
        (["25:00"], "formato"),
        (["09:60"], "formato"),
        ([900], "formato"),
        ("09:00", "formato"),
        (None, "formato"),
        ([], "formato"),
        (["0\u0669:0\u0660"], "formato"),  # dígito que não é ASCII
        (["09:00", "09:00"], "repetido"),
        (["09:00", "11:00", "13:00", "15:00", "17:00"], "muitos"),
        (["09:00", "12:00"], "perto"),
        (["22:00", "01:00"], "perto"),  # 3 h passando a meia-noite
    ],
)
def test_horarios_tortos_recusados(valor: object, chave: str) -> None:
    with pytest.raises(ValueError, match=_CHAVE + chave) as erro:
        horarios_validos(valor)
    assert erro.value.args[0] == _CHAVE + chave


def test_horarios_na_borda_de_4_h_passam() -> None:
    assert horarios_validos(["22:00", "02:00"]) == (time(2), time(22))
    assert horarios_validos(["09:00", "13:00"]) == (time(9), time(13))
