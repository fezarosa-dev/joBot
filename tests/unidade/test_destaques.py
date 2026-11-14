from datetime import UTC, datetime, timedelta

from jobot.nucleo.destaques import Candidata, destaques

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


def _c(
    vaga_id: int,
    empresa: str = "Acme",
    nota: int | None = 50,
    publicada_em: datetime | None = None,
    vista_ha: timedelta = timedelta(hours=1),
) -> Candidata:
    return Candidata(
        vaga_id=vaga_id,
        empresa=empresa,
        nota=nota,
        publicada_em=publicada_em,
        primeira_vista_em=AGORA - vista_ha,
    )


def _ids(cs: list[Candidata]) -> list[int]:
    return [c.vaga_id for c in cs]


def test_destaques() -> None:
    # só as vistas pela primeira vez nas últimas 24 h
    cs = [
        _c(1, "A"),
        _c(2, "B", vista_ha=timedelta(hours=24)),
        _c(3, "C", vista_ha=timedelta(hours=25)),
    ]
    assert _ids(destaques(cs, AGORA)) == [1, 2]

    # uma por empresa: a de maior nota (empresa comparada sem acento nem caixa)
    cs = [_c(1, "Acme", 40), _c(2, "ACME", 80), _c(3, "Árvore", 10), _c(4, "arvore", 5)]
    assert _ids(destaques(cs, AGORA)) == [2, 3]

    # ordem: nota e depois publicação mais recente
    d1, d2 = AGORA - timedelta(days=3), AGORA - timedelta(days=1)
    cs = [_c(1, "A", 60, d1), _c(2, "B", 90, d1), _c(3, "C", 60, d2), _c(4, "D", 60, None)]
    assert _ids(destaques(cs, AGORA)) == [2, 3, 1, 4]

    # no máximo n (10 por padrão)
    cs = [_c(i, f"E{i}", i) for i in range(1, 16)]
    assert len(destaques(cs, AGORA)) == 10
    assert _ids(destaques(cs, AGORA, n=3)) == [15, 14, 13]

    assert destaques([], AGORA) == []


def test_destaques_sem_nota_ordena_por_data() -> None:
    d = [AGORA - timedelta(days=i) for i in (5, 1, 3)]
    cs = [_c(1, "A", None, d[0]), _c(2, "B", None, d[1]), _c(3, "C", None, d[2])]
    assert _ids(destaques(cs, AGORA)) == [2, 3, 1]
    # mistura: com nota vem antes de sem nota
    cs = [_c(1, "A", None, d[1]), _c(2, "B", 5, d[0])]
    assert _ids(destaques(cs, AGORA)) == [2, 1]


def test_destaques_relogio_atrasado_conta_como_recente() -> None:
    futura = Candidata(
        vaga_id=1,
        empresa="A",
        nota=1,
        publicada_em=None,
        primeira_vista_em=AGORA + timedelta(hours=2),
    )
    assert _ids(destaques([futura], AGORA)) == [1]
