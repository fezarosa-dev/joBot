"""Ciclo de vida das ocorrências (desenho 10.2). Função pura: decide o que muda, não grava."""

from collections.abc import Sequence, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

JANELA_PARCIAL = timedelta(days=30)


@dataclass(frozen=True, kw_only=True)
class OcorrenciaAberta:
    url_hash: str
    ultima_vista_em: datetime
    sumiu_em: datetime | None


@dataclass(frozen=True, kw_only=True)
class MudancasCiclo:
    sumiram: tuple[str, ...]
    reviram: tuple[str, ...]
    tocar: tuple[str, ...]


def aplicar_ciclo(
    abertas: Sequence[OcorrenciaAberta], vistas: Set[str], estado: str, agora: datetime
) -> MudancasCiclo:
    """`abertas` traz as ocorrências do escopo, inclusive as já sumidas (para poder reaparecer)."""
    if estado == "sem_mudanca":
        return MudancasCiclo(
            sumiram=(),
            reviram=(),
            tocar=tuple(o.url_hash for o in abertas if o.sumiu_em is None),
        )
    if estado not in ("ok", "parcial"):  # falhou, desligada, no_limite: nada muda
        return MudancasCiclo(sumiram=(), reviram=(), tocar=())

    def some(o: OcorrenciaAberta) -> bool:
        return estado == "ok" or agora - o.ultima_vista_em > JANELA_PARCIAL

    return MudancasCiclo(
        sumiram=tuple(
            o.url_hash
            for o in abertas
            if o.sumiu_em is None and o.url_hash not in vistas and some(o)
        ),
        reviram=tuple(
            o.url_hash for o in abertas if o.sumiu_em is not None and o.url_hash in vistas
        ),
        tocar=(),
    )


def vaga_fechada(ocorrencias: Sequence[OcorrenciaAberta]) -> bool:
    """Fecha quando todas as ocorrências sumiram; vaga sem ocorrência não conta como fechada."""
    return bool(ocorrencias) and all(o.sumiu_em is not None for o in ocorrencias)
