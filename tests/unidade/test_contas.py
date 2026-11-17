"""Núcleo das contas: estados, queda e intervalo do "Conferir agora" (plano T269)."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from jobot.nucleo.contas import (
    Sessao,
    estado_na_tela,
    hora_visivel,
    pode_conferir,
    proxima_sessao,
)

AGORA = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def _sessao(
    estado: Any = "conectado",
    motivo: Any = None,
    entrou_em: str | None = None,
    avisado_em: str | None = None,
    conferido_em: str | None = None,
) -> Sessao:
    return Sessao(estado, motivo, conferido_em or AGORA.isoformat(), entrou_em, avisado_em)


def _queda_aberta() -> Sessao:
    conectada, _ = proxima_sessao(None, "conectado", None, AGORA)
    caida, _ = proxima_sessao(conectada, "precisa_entrar", None, AGORA + timedelta(minutes=1))
    return caida


def _recusa(*args: Any) -> bool:
    try:
        proxima_sessao(*args)
    except ValueError:
        return True
    return False


def _recusa_conferir(sessao: Sessao | None, agora: datetime, intervalo_s: int) -> bool:
    try:
        pode_conferir(sessao, agora, intervalo_s)
    except ValueError as erro:
        return str(erro) == "agora precisa ter fuso"
    return False


@pytest.mark.parametrize(
    ("ligado", "sessao", "esperado"),
    [
        (False, None, "desligado"),
        (False, _sessao("conectado", entrou_em="x"), "desligado"),
        (False, _sessao("precisa_entrar"), "desligado"),
        (True, None, "nunca_entrou"),
        (True, _sessao("precisa_entrar"), "nunca_entrou"),
        (True, _sessao("precisa_entrar", entrou_em="x", avisado_em="y"), "precisa_entrar"),
        (True, _sessao("conectado", entrou_em="x"), "conectado"),
        (True, _sessao("nao_conferiu", "sem_rede"), "nao_conferiu"),
        (True, _sessao("nao_conferiu", "sem_rede", entrou_em="x"), "nao_conferiu"),
    ],
)
def test_estado_na_tela_tabela(ligado: bool, sessao: Sessao | None, esperado: str) -> None:
    assert estado_na_tela(ligado, sessao) == esperado


def test_conectado_marca_entrou_e_fecha_queda() -> None:
    depois = AGORA + timedelta(hours=1)
    nova, abriu = proxima_sessao(_queda_aberta(), "conectado", None, depois)
    assert nova.entrou_em == depois.isoformat()
    assert nova.avisado_em is None
    assert nova.conferido_em == depois.isoformat()
    assert abriu is False


def test_queda_abre_uma_vez() -> None:
    passos: list[tuple[Any, Any]] = [
        ("conectado", None),
        ("precisa_entrar", None),
        ("precisa_entrar", None),
        ("nao_conferiu", "sem_rede"),
        ("precisa_entrar", None),
        ("conectado", None),
        ("precisa_entrar", None),
    ]
    sessao: Sessao | None = None
    abriu: list[bool] = []
    quedas: list[bool] = []
    for i, (estado, motivo) in enumerate(passos):
        sessao, abriu_agora = proxima_sessao(sessao, estado, motivo, AGORA + timedelta(minutes=i))
        abriu.append(abriu_agora)
        quedas.append(sessao.queda_aberta)
    assert abriu == [False, True, False, False, False, False, True]
    assert quedas[3] is True  # nao_conferiu no meio não fecha a queda


def test_nunca_entrou_nao_abre_queda() -> None:
    sessao, abriu = proxima_sessao(None, "precisa_entrar", None, AGORA)
    assert abriu is False
    assert sessao.avisado_em is None
    # controle positivo na mesma montagem: quem já entrou abre a queda
    conectada, _ = proxima_sessao(None, "conectado", None, AGORA)
    _, abriu_depois = proxima_sessao(conectada, "precisa_entrar", None, AGORA)
    assert abriu_depois is True


def test_esquecido_zera() -> None:
    caida = _queda_aberta()
    assert caida.queda_aberta is True  # controle
    depois = AGORA + timedelta(hours=2)
    nova, abriu = proxima_sessao(caida, "precisa_entrar", "esquecido", depois)
    assert nova.entrou_em is None
    assert nova.avisado_em is None
    assert nova.conferido_em == depois.isoformat()
    assert abriu is False


def test_hora_visivel() -> None:
    assert hora_visivel("conectado", None) is False
    assert hora_visivel("nunca_entrou", _sessao("precisa_entrar", "esquecido")) is False
    assert hora_visivel("nunca_entrou", _sessao("precisa_entrar")) is False
    assert hora_visivel("desligado", _sessao("conectado", entrou_em="x")) is True
    assert hora_visivel("desligado", _sessao("precisa_entrar", "esquecido")) is False
    assert hora_visivel("conectado", _sessao("conectado", entrou_em="x")) is True


def test_pode_conferir_borda() -> None:
    def com_idade(s: int) -> Sessao:
        return _sessao(conferido_em=(AGORA - timedelta(seconds=s)).isoformat())

    assert pode_conferir(com_idade(599), AGORA, 600) is False
    assert pode_conferir(com_idade(600), AGORA, 600) is True
    assert pode_conferir(com_idade(601), AGORA, 600) is True
    # -03:00 e UTC: conta o instante, não o relógio de parede
    brasilia = timezone(timedelta(hours=-3))
    conferido = (AGORA - timedelta(seconds=599)).astimezone(brasilia)
    assert pode_conferir(_sessao(conferido_em=conferido.isoformat()), AGORA, 600) is False
    conferido = (AGORA - timedelta(seconds=600)).astimezone(brasilia)
    assert pode_conferir(_sessao(conferido_em=conferido.isoformat()), AGORA, 600) is True


def test_pode_conferir_sem_linha_e_esquecido() -> None:
    assert pode_conferir(None, AGORA, 600) is True
    recente = _sessao("precisa_entrar", "esquecido", conferido_em=AGORA.isoformat())
    assert pode_conferir(recente, AGORA, 600) is True


def test_combinacao_invalida_recusa() -> None:
    """Guarda: o valor errado já valida. Mutante: tirar a recusa de nao_conferiu sem motivo."""
    ingenuo = datetime(2026, 11, 16, 12, 0)
    invalidas: list[tuple[Any, ...]] = [
        (None, "conectado", None, ingenuo),
        (None, "conectado", "sem_rede", AGORA),
        (None, "precisa_entrar", "bloqueio", AGORA),
        (None, "conectado", "esquecido", AGORA),
        (None, "nao_conferiu", None, AGORA),
        (None, "nao_conferiu", "esquecido", AGORA),
    ]
    assert [_recusa(*c) for c in invalidas] == [True] * len(invalidas)
    # controle: combinações válidas não recusam
    assert _recusa(None, "nao_conferiu", "sem_rede", AGORA) is False
    assert _recusa(None, "precisa_entrar", "esquecido", AGORA) is False


def test_pode_conferir_ilegivel_libera() -> None:
    """Guarda do ramo R1: tirar o try/except estoura TypeError ou ValueError aqui."""
    assert pode_conferir(_sessao(conferido_em="lixo"), AGORA, 600) is True
    # ISO válido mas sem fuso, recente: a conta com o agora estoura TypeError e libera
    assert pode_conferir(_sessao(conferido_em="2026-11-16T12:00:00"), AGORA, 600) is True
    # controle: ISO recente com fuso continua barrado
    assert pode_conferir(_sessao(conferido_em=AGORA.isoformat()), AGORA, 600) is False


def test_pode_conferir_recusa_agora_sem_fuso() -> None:
    """Erro de quem chama não vira 'sempre libera': recusa como proxima_sessao."""
    ingenuo = datetime(2026, 11, 16, 12, 0)
    assert _recusa_conferir(_sessao(), ingenuo, 600) is True
    assert _recusa_conferir(None, ingenuo, 600) is True
    # controle: agora com fuso não recusa
    assert _recusa_conferir(_sessao(), AGORA, 600) is False
    assert _recusa_conferir(None, AGORA, 600) is False


def test_pode_conferir_conferido_no_futuro_libera() -> None:
    """Relógio adiantado e corrigido: conferência no futuro não barra por horas."""
    futuro = _sessao(conferido_em=(AGORA + timedelta(hours=5)).isoformat())
    assert pode_conferir(futuro, AGORA, 600) is True
    # controle: conferência recente no passado continua barrada
    recente = _sessao(conferido_em=(AGORA - timedelta(seconds=5)).isoformat())
    assert pode_conferir(recente, AGORA, 600) is False
