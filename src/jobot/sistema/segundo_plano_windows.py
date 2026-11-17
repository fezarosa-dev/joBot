"""Segundo plano no Windows: tarefa do Agendador de Tarefas ao entrar (desenho 6.5).

Tudo que fala com o sistema passa por `rodar`, o executor de comandos injetado. O atalho do Menu
Iniciar é do instalador da casca (NSIS), não daqui.
"""

import logging
import sys
from pathlib import PureWindowsPath

from jobot.nucleo.modelo import Motivo
from jobot.sistema.segundo_plano_linux import Estado, Recusa, Resultado, Rodar

TAREFA = "joBot"
_LOG = logging.getLogger(__name__)


def _python() -> str:
    return sys.executable


def pythonw(python: str) -> str:
    """O `pythonw.exe` ao lado do `python.exe` do joBot: roda sem janela de console."""
    return str(PureWindowsPath(python).with_name("pythonw.exe"))


def _schtasks(rodar: Rodar, acao: str, *args: str) -> Resultado:
    return rodar(("schtasks", acao, "/TN", TAREFA, *args))


def _falha(acao: str, feito: Resultado) -> Recusa:
    texto = (feito.erro or feito.saida).strip()
    # a saída completa só vai ao log; a tela mostra um texto fixo (como no systemctl, T159)
    _LOG.warning("schtasks %s falhou (código %s): %s", acao, feito.codigo, texto)
    params = {"comando": acao, "saida": texto}
    return Recusa(Motivo(chave="segundo_plano.schtasks_falhou", params=params))


def ligar(rodar: Rodar, *, python: str | None = None) -> None:
    # as aspas em volta do caminho seguem dentro do /TR: a pasta do usuário pode ter espaço
    alvo = f'"{pythonw(python or _python())}" -m jobot serve'
    feito = rodar(("schtasks", "/Create", "/SC", "ONLOGON", "/TN", TAREFA, "/TR", alvo, "/F"))
    if feito.codigo != 0:
        raise _falha("/Create", feito)


def desligar(rodar: Rodar) -> None:
    feito = _schtasks(rodar, "/Delete", "/F")
    # sem tarefa o /Delete falha à toa e desligar também vale; com ela, a falha é real
    if feito.codigo != 0 and _schtasks(rodar, "/Query").codigo == 0:
        raise _falha("/Delete", feito)


def status(rodar: Rodar) -> Estado:
    # ponytail: "rodando" segue o "instalado"; o estado do schtasks vem na língua do sistema
    existe = _schtasks(rodar, "/Query").codigo == 0
    return Estado(habilitado=existe, ativo=existe)
