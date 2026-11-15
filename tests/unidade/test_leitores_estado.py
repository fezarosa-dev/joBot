"""Estado do escopo de um leitor com login: a precedência do desenho A4 e o registro (T197)."""

from types import SimpleNamespace
from typing import Any, get_args

import pytest

from jobot.nucleo.leitores import registro
from jobot.nucleo.leitores.base import Leitura, ParadaLogin
from jobot.nucleo.leitores.estado import (
    ORDEM_DAS_PARADAS,
    Desfecho,
    estado_do_escopo,
    parada_mais_forte,
)
from jobot.nucleo.modelo import VagaColetada


def _vaga(n: int) -> VagaColetada:
    return VagaColetada(
        fonte="exemplo_logado",
        escopo="e",
        url=f"https://exemplo.test/vaga/{n}",
        titulo=f"Vaga {n}",
        empresa="Acme",
        descricao_formato="texto",
    )


V1 = _vaga(1)
V2 = _vaga(2)
BOA = Leitura((V1,), 0, False)


def _estado(
    leituras: tuple[Leitura, ...],
    *,
    parada: ParadaLogin | None = None,
    cortada: bool = False,
    tres_ok: bool = False,
) -> Desfecho:
    return estado_do_escopo(leituras, parada=parada, cortada=cortada, tres_ok_com_vagas=tres_ok)


@pytest.mark.parametrize("parada", ["precisa_login", "bloqueio", "captcha"])
def test_parada_sozinha_da_falhou_com_a_chave_dela(parada: ParadaLogin) -> None:
    assert _estado((BOA,), parada=parada) == Desfecho("falhou", f"saude.{parada}", (V1,))


def test_no_limite_da_no_limite_com_parou_429() -> None:
    assert _estado((BOA,), parada="no_limite") == Desfecho("no_limite", "saude.parou_429", (V1,))


def test_ordem_das_paradas_e_a_do_tipo() -> None:
    assert ORDEM_DAS_PARADAS == get_args(ParadaLogin)


@pytest.mark.parametrize(
    ("a", "b", "esperada"),
    [
        ("precisa_login", "bloqueio", "precisa_login"),
        ("bloqueio", "captcha", "bloqueio"),
        ("captcha", "no_limite", "captcha"),
        ("precisa_login", "no_limite", "precisa_login"),
    ],
)
def test_parada_mais_forte(a: ParadaLogin, b: ParadaLogin, esperada: ParadaLogin) -> None:
    assert parada_mais_forte(a, b) == esperada
    assert parada_mais_forte(b, a) == esperada


@pytest.mark.parametrize("parada", ORDEM_DAS_PARADAS)
def test_parada_mais_forte_com_none(parada: ParadaLogin) -> None:
    assert parada_mais_forte(None, parada) == parada
    assert parada_mais_forte(parada, None) == parada
    assert parada_mais_forte(parada, parada) == parada


def test_parada_mais_forte_de_duas_none() -> None:
    assert parada_mais_forte(None, None) is None


def test_parada_vence_o_corte_e_junta_as_vagas_das_paginas() -> None:
    desfecho = _estado((BOA, Leitura((V2,), 0, False)), parada="captcha", cortada=True)
    assert desfecho == Desfecho("falhou", "saude.captcha", (V1, V2))


def test_parada_com_formato_mudou_nao_grava_vaga() -> None:
    desfecho = _estado((BOA, Leitura((), 0, True)), parada="bloqueio")
    assert desfecho == Desfecho("falhou", "saude.bloqueio", ())


def test_formato_mudou_numa_pagina_e_outra_boa() -> None:
    desfecho = _estado((BOA, Leitura((), 0, True)), cortada=True)
    assert desfecho == Desfecho("falhou", "saude.formato_mudou", ())


def test_so_itens_tortos_e_formato_mudou() -> None:
    assert _estado((Leitura((), 3, True),)) == Desfecho("falhou", "saude.formato_mudou", ())


def test_cortada_com_pagina_lida_e_parcial() -> None:
    desfecho = _estado((Leitura((V1,), 1, False),), cortada=True)
    assert desfecho == Desfecho("parcial", "saude.listagem_incompleta", (V1,))


def test_cortada_sem_pagina_lida_e_falhou() -> None:
    assert _estado((), cortada=True) == Desfecho("falhou", "saude.listagem_incompleta", ())


def test_item_torto_ate_o_fim_e_parcial() -> None:
    desfecho = _estado((Leitura((V1,), 2, False),))
    assert desfecho == Desfecho("parcial", "saude.formato_mudou", (V1,))


def test_vazia_com_historico_e_zero_inesperado() -> None:
    desfecho = _estado((Leitura((), 0, False),), tres_ok=True)
    assert desfecho == Desfecho("parcial", "saude.zero_inesperado", ())


def test_vazia_sem_historico_e_ok() -> None:
    assert _estado((Leitura((), 0, False),)) == Desfecho("ok", None, ())


def test_lista_com_vagas_e_ok() -> None:
    assert _estado((BOA, Leitura((V2,), 0, False)), tres_ok=True) == Desfecho("ok", None, (V1, V2))


def _leitor(chave: str) -> Any:
    return SimpleNamespace(chave=chave)


def test_registro_comeca_vazio() -> None:
    assert registro.leitores() == ()


def test_registro_devolve_os_registrados(monkeypatch: pytest.MonkeyPatch) -> None:
    a, b = _leitor("a_logado"), _leitor("b_logado")
    monkeypatch.setattr(registro, "LEITORES", (a, b))
    assert registro.leitores() == (a, b)


def test_registro_recusa_chave_sem_sufixo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registro, "LEITORES", (_leitor("gupy"),))
    with pytest.raises(ValueError, match="gupy"):
        registro.leitores()


def test_registro_recusa_chave_repetida(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registro, "LEITORES", (_leitor("a_logado"), _leitor("a_logado")))
    with pytest.raises(ValueError, match="a_logado"):
        registro.leitores()
