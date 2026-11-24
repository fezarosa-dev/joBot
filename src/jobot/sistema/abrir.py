"""Abrir o painel (aba ou janela do modo app) e encerrar o servidor (desenho 12.6)."""

import http.client
import json
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from jobot.sistema import processo
from jobot.sistema.caso import prefixo_host
from jobot.sistema.instancia import (
    AVISO_CAPTURA,
    pid_do_servidor,
    pid_e_porta_do_servidor,
    porta,
)
from jobot.sistema.sair import CABECALHO as CABECALHO_SAIR
from jobot.sistema.sair import ler_token

_LOG = logging.getLogger(__name__)
_ESPERA_PASSO_S = 0.2
_NAVEGADORES_LINUX = (
    "google-chrome",
    "google-chrome-stable",
    "microsoft-edge",
    "chromium",
    "chromium-browser",
)
_APPS_MAC = ("Google Chrome", "Microsoft Edge", "Chromium")
# `chrome.exe` e `msedge.exe` sob cada pasta de programas (a por usuário é a `LOCALAPPDATA`)
_EXES_WINDOWS = (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe")


def e_o_jobot(porta: int) -> bool:
    """True só se `/saude-local` na porta responde 200 com `{"app": "jobot", ...}`."""
    # HTTPConnection direta: sem proxy do ambiente e sem seguir redirecionamento
    con = http.client.HTTPConnection("127.0.0.1", porta, timeout=1)
    try:
        con.request("GET", "/saude-local")
        resposta = con.getresponse()
        if resposta.status != 200:
            return False
        dados = json.loads(resposta.read(4096))
    except OSError, http.client.HTTPException, ValueError:
        return False
    finally:
        con.close()
    return isinstance(dados, dict) and dados.get("app") == "jobot"


def _porta_ocupada(porta: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def _rodar(comando: Sequence[str]) -> bool:
    try:
        feito = subprocess.run(
            comando,
            check=False,
            timeout=10,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return feito.returncode == 0


def _lancar(comando: Sequence[str]) -> bool:
    """Lança sem esperar: o navegador vive à parte (o `_rodar` o mataria em 10 s)."""
    try:
        subprocess.Popen(
            comando,
            **processo.destacar(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return True


def existe_do_sistema(
    prefixo: Sequence[str],
    *,
    rodar: Callable[[Sequence[str]], bool] = _rodar,
    procurar: Callable[[str], str | None] = shutil.which,
) -> Callable[[str], bool]:
    """Caminho absoluto: o arquivo existe; nome solto: `which` (no host, se há prefixo)."""

    def existe(nome: str) -> bool:
        if os.path.isabs(nome):
            return Path(nome).exists()
        if prefixo:
            return rodar((*prefixo, "which", nome))
        return procurar(nome) is not None

    return existe


# perfil novo não mostra a tela de boas-vindas nem pergunta do navegador padrão antes da janela
_SEM_BOAS_VINDAS = ("--no-first-run", "--no-default-browser-check")


def achar_navegador_do_sistema(
    endereco: str, sistema: str, existe: Callable[[str], bool], prefixo: Sequence[str]
) -> list[str] | None:
    """O comando que abre `--app=<endereço>` no primeiro Chrome, Edge ou Chromium achado."""
    app = f"--app={endereco}"
    if sistema == "darwin":
        # shortcut: só /Applications, não ~/Applications; acrescentar se aparecer quem instala lá
        for nome in _APPS_MAC:
            if existe(f"/Applications/{nome}.app"):
                return ["open", "-na", nome, "--args", app, *_SEM_BOAS_VINDAS]
    elif sistema == "win32":
        pastas = (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        )
        for exe in _EXES_WINDOWS:
            for pasta in filter(None, pastas):
                caminho = f"{pasta}\\{exe}"
                if existe(caminho):
                    return [caminho, app, *_SEM_BOAS_VINDAS]
    else:
        for nome in _NAVEGADORES_LINUX:
            if existe(nome):
                return [*prefixo, nome, app, *_SEM_BOAS_VINDAS]
    return None


def _web(endereco: str) -> bool:
    try:
        return webbrowser.open(endereco)
    except webbrowser.Error:
        return False


def abrir_navegador(
    endereco: str,
    env: Mapping[str, str],
    *,
    rodar: Callable[[Sequence[str]], bool] = _rodar,
    web: Callable[[str], bool] = _web,
) -> bool:
    """Distrobox: `distrobox-host-exec xdg-open` (sem navegador no container); fora: webbrowser."""
    prefixo = prefixo_host(env)
    if prefixo:
        return rodar((*prefixo, "xdg-open", endereco))
    return web(endereco)


def abrir_janela(
    endereco: str,
    env: Mapping[str, str],
    *,
    sistema: str,
    existe: Callable[[str], bool],
    chromium: Callable[[], Path | None],
    pasta_dados: Path,
    lancar: Callable[[Sequence[str]], bool] = _lancar,
) -> bool:
    """Janela do modo app: navegador do sistema, senão o Chromium do joBot, senão uma aba."""
    comando = achar_navegador_do_sistema(endereco, sistema, existe, prefixo_host(env))
    if comando and lancar(comando):
        return True
    try:
        exe = chromium()
    except Exception:  # driver do Playwright que não sobe não pode impedir a aba
        _LOG.debug("Chromium do joBot indisponível", exc_info=True)
        exe = None
    # `janela/` é só desta janela: nunca a pasta do navegador de login (D132)
    perfil = f"--user-data-dir={pasta_dados / 'janela'}"
    if exe and lancar([str(exe), f"--app={endereco}", perfil, *_SEM_BOAS_VINDAS]):
        return True
    return abrir_navegador(endereco, env)


def _esperar(
    pronto: Callable[[], bool],
    esperar_s: float,
    agora: Callable[[], float],
    dormir: Callable[[float], None],
) -> bool:
    """Olha `pronto` a cada passo até dar certo (True) ou vencer o prazo (False)."""
    fim = agora() + esperar_s
    while not pronto():
        if agora() >= fim:
            return False
        dormir(_ESPERA_PASSO_S)
    return True


def abrir_painel(
    env: Mapping[str, str],
    dados: Path,
    *,
    subir: Callable[[], None],
    navegador: Callable[[str, Mapping[str, str]], bool] = abrir_navegador,
    saida: Callable[[str], None] = print,
    esperar_s: float = 15.0,
    agora: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Sobe o servidor se ninguém o prende; só abre o navegador se a porta é mesmo do joBot."""
    # com o servidor no ar vale a porta que ele gravou na trava: o serviço não herda o env do shell
    # PID e porta saem da mesma leitura da trava, senão dois donos diferentes poderiam se misturar
    pid, porta_gravada = pid_e_porta_do_servidor(dados)
    if pid is not None and porta_gravada is None:  # trava sem porta: captura com login no ar
        saida(AVISO_CAPTURA)
        return 1
    p = porta_gravada or porta(env)
    endereco = f"http://127.0.0.1:{p}"
    ocupada = (
        f"A porta {p} está ocupada por outro programa. "
        "Feche-o ou defina JOBOT_PORTA com outra porta."
    )
    if pid is None:
        if _porta_ocupada(p):  # sem servidor nosso, quem escuta ali é alheio (RF3)
            saida(ocupada)
            return 1
        subir()
    if not _esperar(lambda: e_o_jobot(p), esperar_s, agora, dormir):
        saida(
            ocupada
            if _porta_ocupada(p)
            else f"O joBot não respondeu em {p}. Veja o log em {dados / 'logs' / 'jobot.log'}."
        )
        return 1
    # o servidor roda à parte (sessão própria): Ctrl+C no terminal não o encerra
    ja_aberto = "O joBot já estava aberto" if pid is not None else "joBot aberto"
    saida(f"{ja_aberto} em {endereco}. Para sair, use Sair no painel ou rode: jobot sair")
    if not navegador(endereco, env):
        saida(f"Não consegui abrir o navegador. Abra este endereço: {endereco}")
    return 0


def _pedir_sair(porta: int, segredo: str | None) -> str | None:
    """`POST /sair` local com o segredo; None quando o servidor aceitou, senão o aviso."""
    if segredo is None:
        return "Não achei o segredo de parada do joBot (sair.token). Feche-o pela janela."
    con = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
    try:
        con.request("POST", "/sair", headers={CABECALHO_SAIR: segredo})
        status = con.getresponse().status
    except OSError, http.client.HTTPException:
        return f"O joBot não respondeu em {porta}."
    finally:
        con.close()
    return None if status == 200 else f"O joBot recusou o pedido de parada ({status})."


def sair_do_servidor(
    dados: Path,
    *,
    saida: Callable[[str], None] = print,
    esperar_s: float = 10.0,
    plataforma: str = sys.platform,
    agora: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Pede o fim ao servidor da trava (só se ela está presa) e espera a trava soltar.

    No Linux e no Mac, SIGTERM ao PID; no Windows, sem SIGTERM, `POST /sair` com o segredo do
    `sair.token` (desenho 6.1).
    """
    pid, p = pid_e_porta_do_servidor(dados)  # uma leitura só: o PID e a porta são do mesmo dono
    if pid is not None and p is None:  # a trava é da captura, não do servidor: nada de SIGTERM
        saida(AVISO_CAPTURA)
        return 1
    if pid is None:
        saida("O joBot não está rodando.")
        return 0
    if plataforma == "win32":
        assert p is not None  # trava do servidor: com PID e sem porta é a captura, tratada acima
        problema = _pedir_sair(p, ler_token(dados))
        if problema is not None:
            saida(problema)
            return 1
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            saida("O joBot já tinha encerrado.")
            return 0
        except PermissionError:
            saida(f"Sem permissão para encerrar o joBot (PID {pid}).")
            return 1
    if not _esperar(lambda: pid_do_servidor(dados) is None, esperar_s, agora, dormir):
        saida(f"O joBot (PID {pid}) não encerrou em {esperar_s:g} s.")
        return 1
    saida("joBot encerrado.")
    return 0


def subir_servidor(python: str | None = None) -> None:
    """Servidor em processo separado; o comando `serve` é da T48. `python`: o de outro venv (o
    novo, no canal `casca` do `jobot atualizar`); sem ele, o deste processo."""
    subprocess.Popen(
        [python or sys.executable, "-m", "jobot", "serve"],
        **processo.destacar(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
