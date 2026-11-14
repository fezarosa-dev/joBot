from dataclasses import replace
from datetime import UTC, datetime, timedelta

from jobot.nucleo.tratamento.ciclo_de_vida import (
    MudancasCiclo,
    OcorrenciaAberta,
    aplicar_ciclo,
    vaga_fechada,
)

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


def _oc(url_hash: str, dias_sem_ver: int = 0, *, sumida: bool = False) -> OcorrenciaAberta:
    vista = AGORA - timedelta(days=dias_sem_ver)
    return OcorrenciaAberta(
        url_hash=url_hash, ultima_vista_em=vista, sumiu_em=vista if sumida else None
    )


def test_ok_marca_sumida() -> None:
    abertas = [_oc("a"), _oc("b"), _oc("c", sumida=True)]
    r = aplicar_ciclo(abertas, {"a"}, "ok", AGORA)
    assert r == MudancasCiclo(sumiram=("b",), reviram=(), tocar=())


def test_parcial_so_marca_com_mais_de_30_dias() -> None:
    abertas = [_oc("recente", 30), _oc("velha", 31), _oc("vista", 90)]
    r = aplicar_ciclo(abertas, {"vista"}, "parcial", AGORA)
    assert r.sumiram == ("velha",)
    assert r.tocar == ()


def test_sem_mudanca_toca_todas_e_nao_marca_nenhuma() -> None:
    abertas = [_oc("a", 5), _oc("b", 40), _oc("c", sumida=True)]
    r = aplicar_ciclo(abertas, set(), "sem_mudanca", AGORA)
    assert r.sumiram == ()
    assert r.reviram == ()
    assert r.tocar == ("a", "b")


def test_falhou_desligada_no_limite_nao_mudam_nada() -> None:
    abertas = [_oc("a", 5), _oc("b", 40), _oc("c", sumida=True)]
    for estado in ("falhou", "desligada", "no_limite"):
        assert aplicar_ciclo(abertas, {"a", "c"}, estado, AGORA) == MudancasCiclo(
            sumiram=(), reviram=(), tocar=()
        )


def test_reaparecer_limpa_sumiu_em() -> None:
    abertas = [_oc("a", sumida=True), _oc("b", sumida=True)]
    for estado in ("ok", "parcial"):
        r = aplicar_ciclo(abertas, {"a"}, estado, AGORA)
        assert r.reviram == ("a",)
        assert r.sumiram == ()


def test_fecha_so_quando_todas_sumiram() -> None:
    a = _oc("a", sumida=True)
    b = _oc("b")
    assert vaga_fechada([a, b]) is False
    assert vaga_fechada([a, replace(b, sumiu_em=AGORA)]) is True
    assert vaga_fechada([]) is False
