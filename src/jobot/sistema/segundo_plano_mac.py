"""Segundo plano no Mac: LaunchAgent do launchd ao entrar (desenho 6.5), experimental como o .dmg.

Tudo que fala com o sistema passa por `rodar`, o executor de comandos injetado. O app no
Launchpad é do .dmg da casca, não daqui.
"""

import logging
import os
import plistlib
import sys
from collections.abc import Mapping
from pathlib import Path

from jobot.nucleo.modelo import Motivo
from jobot.sistema.segundo_plano_linux import Estado, Recusa, Resultado, Rodar

ROTULO = "io.github.fezarosa-dev.jobot"
_LOG = logging.getLogger(__name__)


def _python() -> str:
    return sys.executable


def _uid() -> int:
    return os.getuid()


def texto_do_plist(python: str) -> bytes:
    """Sobe ao entrar; o launchd só o refaz se sair com erro (sair normal fica fora)."""
    return plistlib.dumps(
        {
            "Label": ROTULO,
            "ProgramArguments": [python, "-m", "jobot", "serve"],
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
        }
    )


def _arquivo(env: Mapping[str, str] | None) -> Path:
    casa = (os.environ if env is None else env).get("HOME")
    return (Path(casa) if casa else Path.home()) / "Library" / "LaunchAgents" / f"{ROTULO}.plist"


def _launchctl(rodar: Rodar, acao: str, alvo: str, *args: str) -> Resultado:
    return rodar(("launchctl", acao, alvo, *args))


def _servico(uid: int) -> str:
    return f"gui/{uid}/{ROTULO}"


def _falha(acao: str, feito: Resultado) -> Recusa:
    texto = (feito.erro or feito.saida).strip()
    # a saída completa só vai ao log; a tela mostra um texto fixo (como no systemctl, T159)
    _LOG.warning("launchctl %s falhou (código %s): %s", acao, feito.codigo, texto)
    params = {"comando": acao, "saida": texto}
    return Recusa(Motivo(chave="segundo_plano.launchctl_falhou", params=params))


def ligar(
    rodar: Rodar,
    *,
    python: str | None = None,
    uid: int | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    uid = _uid() if uid is None else uid
    arquivo = _arquivo(env)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(texto_do_plist(python or _python()))
    # já carregado: outro bootstrap falharia e um bootout pararia o servidor no ar; o plist novo
    # vale no próximo login
    if _launchctl(rodar, "print", _servico(uid)).codigo == 0:
        return
    feito = _launchctl(rodar, "bootstrap", f"gui/{uid}", str(arquivo))
    if feito.codigo != 0:
        arquivo.unlink(missing_ok=True)  # senão subiria no próximo login com o segundo plano off
        raise _falha("bootstrap", feito)


def desligar(rodar: Rodar, *, uid: int | None = None, env: Mapping[str, str] | None = None) -> None:
    servico = _servico(_uid() if uid is None else uid)
    feito = _launchctl(rodar, "bootout", servico)
    # sem serviço carregado o bootout falha à toa e desligar também vale; com ele, a falha é real
    if feito.codigo != 0 and _launchctl(rodar, "print", servico).codigo == 0:
        raise _falha("bootout", feito)
    _arquivo(env).unlink(missing_ok=True)


def status(rodar: Rodar, *, uid: int | None = None) -> Estado:
    # o `launchctl print` escreve em inglês, sem tradução: dá para ler o estado
    feito = _launchctl(rodar, "print", _servico(_uid() if uid is None else uid))
    carregado = feito.codigo == 0
    return Estado(habilitado=carregado, ativo=carregado and "state = running" in feito.saida)
