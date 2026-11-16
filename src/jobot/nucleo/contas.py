"""Estado do login de cada conta: queda, tela e intervalo (puro, sem relógio próprio)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, get_args

EstadoSessao = Literal["conectado", "precisa_entrar", "nao_conferiu"]
MotivoSessao = Literal[
    "sem_rede",
    "desafio",
    "bloqueio",
    "no_limite",
    "sem_tela",
    "sem_navegador",
    "em_uso",
    "erro",
    "esquecido",
]
NaTela = Literal["desligado", "nunca_entrou", "conectado", "precisa_entrar", "nao_conferiu"]

ESTADOS: Final = get_args(EstadoSessao)
MOTIVOS: Final = get_args(MotivoSessao)
NA_TELA: Final = get_args(NaTela)
MOTIVOS_CONTA: Final = frozenset({"sem_rede", "bloqueio", "erro", "esquecido"})


@dataclass(frozen=True)
class Sessao:
    estado: EstadoSessao
    motivo: MotivoSessao | None
    conferido_em: str
    entrou_em: str | None
    avisado_em: str | None

    @property
    def queda_aberta(self) -> bool:
        return self.entrou_em is not None and self.avisado_em is not None


def _exigir_fuso(agora: datetime) -> None:
    if agora.utcoffset() is None:
        raise ValueError("agora precisa ter fuso")


def _validar(estado: EstadoSessao, motivo: MotivoSessao | None, agora: datetime) -> None:
    _exigir_fuso(agora)
    if estado in ("conectado", "precisa_entrar") and motivo not in (None, "esquecido"):
        raise ValueError("motivo não vale para este estado")
    if motivo == "esquecido" and estado != "precisa_entrar":
        raise ValueError("esquecido só vale com precisa_entrar")
    if estado == "nao_conferiu" and motivo in (None, "esquecido"):
        raise ValueError("nao_conferiu pede um motivo")


def proxima_sessao(
    antiga: Sessao | None,
    estado: EstadoSessao,
    motivo: MotivoSessao | None,
    agora: datetime,
) -> tuple[Sessao, bool]:
    """Nova linha da sessão e se esta gravação abriu a queda."""
    _validar(estado, motivo, agora)
    entrou = antiga.entrou_em if antiga else None
    avisado = antiga.avisado_em if antiga else None
    abriu = False
    if motivo == "esquecido":
        entrou = avisado = None
    elif estado == "conectado":
        entrou, avisado = agora.isoformat(), None
    elif estado == "precisa_entrar" and entrou is not None and avisado is None:
        avisado, abriu = agora.isoformat(), True
    return Sessao(estado, motivo, agora.isoformat(), entrou, avisado), abriu


def estado_na_tela(ligado: bool, sessao: Sessao | None) -> NaTela:
    if not ligado:
        return "desligado"
    if sessao is None or (sessao.estado == "precisa_entrar" and sessao.entrou_em is None):
        return "nunca_entrou"
    return sessao.estado


def hora_visivel(na_tela: NaTela, sessao: Sessao | None) -> bool:
    """Sem linha, esquecido ou nunca entrou: sem hora (E19)."""
    return sessao is not None and sessao.motivo != "esquecido" and na_tela != "nunca_entrou"


def pode_conferir(sessao: Sessao | None, agora: datetime, intervalo_s: int) -> bool:
    """A borda libera; esquecer não é conferência, data ilegível ou no futuro libera."""
    _exigir_fuso(agora)
    if sessao is None or sessao.motivo == "esquecido":
        return True
    try:
        passou = (agora - datetime.fromisoformat(sessao.conferido_em)).total_seconds()
    except ValueError, TypeError:
        return True
    return passou < 0 or passou >= intervalo_s
