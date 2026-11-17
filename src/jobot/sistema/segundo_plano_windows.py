"""Segundo plano no Windows: tarefa do Agendador de Tarefas ao entrar (desenho 6.5).

Tudo que fala com o sistema passa por `rodar`, o executor de comandos injetado. O atalho do Menu
Iniciar é do instalador da casca (NSIS), não daqui.
"""

import logging
import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from xml.sax.saxutils import escape

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


def usuario_atual(env: Mapping[str, str]) -> str:
    """`DOMINIO\\usuario` de quem está no Windows, como o Agendador espera no `UserId`."""
    nome = env.get("USERNAME", "")
    dominio = env.get("USERDOMAIN", "")
    return f"{dominio}\\{nome}" if dominio else nome


def xml_da_tarefa(pythonw: str, usuario: str) -> str:
    """A tarefa do Agendador: ao entrar este usuário, sem administrador, no ar sempre.

    O `schtasks /Create /SC ONLOGON` usa os padrões do Agendador: não sobe na bateria, para ao
    passar para a bateria e mata a tarefa depois de 72 h. Aqui os três ficam desligados.
    """
    u, py = escape(usuario), escape(pythonw)
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled><UserId>{u}</UserId></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{u}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{py}</Command><Arguments>-m jobot serve</Arguments></Exec>
  </Actions>
</Task>
"""


def ligar(
    rodar: Rodar,
    *,
    python: str | None = None,
    usuario: str | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    quem = usuario or usuario_atual(os.environ if env is None else env)
    xml = xml_da_tarefa(pythonw(python or _python()), quem)
    # o schtasks lê o /XML em UTF-16; o arquivo só existe durante a chamada
    with tempfile.NamedTemporaryFile("w", encoding="utf-16", suffix=".xml", delete=False) as f:
        f.write(xml)
    try:
        feito = rodar(("schtasks", "/Create", "/TN", TAREFA, "/XML", f.name, "/F"))
    finally:
        Path(f.name).unlink(missing_ok=True)
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
