from collections.abc import Mapping, Sequence

from jobot.nucleo.modelo import VagaTratada


def agrupar(vs: Sequence[VagaTratada]) -> Mapping[str, list[VagaTratada]]:
    """Agrupa pelo hash da URL canônica (DR-59: só a URL conta, título e empresa não)."""
    grupos: dict[str, list[VagaTratada]] = {}
    for v in vs:
        grupos.setdefault(v.url_hash, []).append(v)
    return grupos
