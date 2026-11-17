"""Estado do escopo de um leitor com login: a precedência do desenho A4, pura."""

from collections.abc import Sequence
from dataclasses import dataclass

from jobot.nucleo.coletores.base import Estado
from jobot.nucleo.leitores.base import Leitura, ParadaLogin
from jobot.nucleo.modelo import VagaColetada

ORDEM_DAS_PARADAS: tuple[ParadaLogin, ...] = ("precisa_login", "bloqueio", "captcha", "no_limite")


@dataclass(frozen=True)
class Desfecho:
    estado: Estado
    motivo: str | None
    vagas: tuple[VagaColetada, ...]  # as que valem gravar neste escopo


def parada_mais_forte(a: ParadaLogin | None, b: ParadaLogin | None) -> ParadaLogin | None:
    """A parada que vem antes na `ORDEM_DAS_PARADAS`; `None` perde para qualquer uma."""
    achadas = [p for p in (a, b) if p is not None]
    return min(achadas, key=ORDEM_DAS_PARADAS.index) if achadas else None


def estado_do_escopo(
    leituras: Sequence[Leitura],
    *,
    parada: ParadaLogin | None,
    cortada: bool,
    tres_ok_com_vagas: bool,
) -> Desfecho:
    """Precedência do desenho A4: parada > formato_mudou > cortada > pulados > zero inesperado > ok.

    `vagas` é o que vale gravar: tudo que foi lido, menos quando alguma página perdeu o formato.
    """
    formato_mudou = any(leitura.formato_mudou for leitura in leituras)
    vagas = () if formato_mudou else tuple(v for leitura in leituras for v in leitura.vagas)
    if parada == "no_limite":
        return Desfecho("no_limite", "saude.parou_429", vagas)
    if parada is not None:
        return Desfecho("falhou", f"saude.{parada}", vagas)
    if formato_mudou:
        return Desfecho("falhou", "saude.formato_mudou", ())
    if cortada:
        estado: Estado = "parcial" if leituras else "falhou"
        return Desfecho(estado, "saude.listagem_incompleta", vagas)
    if any(leitura.pulados for leitura in leituras):
        return Desfecho("parcial", "saude.formato_mudou", vagas)
    if not vagas and tres_ok_com_vagas:
        return Desfecho("parcial", "saude.zero_inesperado", ())
    return Desfecho("ok", None, vagas)
