"""Comandos `abrir` e `sair` (desenho 12.6)."""

import argparse
import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from jobot.sistema.caso import prefixo_host
from jobot.sistema.instancia import pid_do_servidor, pid_e_porta_do_servidor, porta
from jobot.sistema.pastas import pasta_de_dados

_ESPERA_PASSO_S = 0.2


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


def _esperar_jobot(porta: int, esperar_s: float) -> bool:
    fim = time.monotonic() + esperar_s
    while not e_o_jobot(porta):
        if time.monotonic() >= fim:
            return False
        time.sleep(_ESPERA_PASSO_S)
    return True


def abrir_painel(
    env: Mapping[str, str],
    dados: Path,
    *,
    subir: Callable[[], None],
    navegador: Callable[[str, Mapping[str, str]], bool] = abrir_navegador,
    saida: Callable[[str], None] = print,
    esperar_s: float = 15.0,
) -> int:
    """Sobe o servidor se ninguém o prende; só abre o navegador se a porta é mesmo do joBot."""
    # com o servidor no ar vale a porta que ele gravou na trava: o serviço não herda o env do shell
    # PID e porta saem da mesma leitura da trava, senão dois donos diferentes poderiam se misturar
    pid, porta_gravada = pid_e_porta_do_servidor(dados)
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
    if not _esperar_jobot(p, esperar_s):
        saida(
            ocupada
            if _porta_ocupada(p)
            else f"O joBot não respondeu em {p}. Veja o log em {dados / 'logs' / 'jobot.log'}."
        )
        return 1
    if not navegador(endereco, env):
        saida(f"Não consegui abrir o navegador. Abra este endereço: {endereco}")
    return 0


def sair_do_servidor(
    dados: Path, *, saida: Callable[[str], None] = print, esperar_s: float = 10.0
) -> int:
    """SIGTERM ao PID da trava (só se ela está presa) e espera a trava soltar."""
    pid = pid_do_servidor(dados)
    if pid is None:
        saida("O joBot não está rodando.")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        saida("O joBot já tinha encerrado.")
        return 0
    except PermissionError:
        saida(f"Sem permissão para encerrar o joBot (PID {pid}).")
        return 1
    fim = time.monotonic() + esperar_s
    while pid_do_servidor(dados) is not None:
        if time.monotonic() >= fim:
            saida(f"O joBot (PID {pid}) não encerrou em {esperar_s:g} s.")
            return 1
        time.sleep(_ESPERA_PASSO_S)
    saida("joBot encerrado.")
    return 0


def subir_servidor() -> None:
    """Servidor em processo separado; o comando `serve` é da T48."""
    subprocess.Popen(
        [sys.executable, "-m", "jobot", "serve"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def executar(args: argparse.Namespace) -> int:
    env = os.environ
    dados = pasta_de_dados(env)
    try:
        if getattr(args, "comando", "abrir") == "sair":
            return sair_do_servidor(dados)
        return abrir_painel(env, dados, subir=subir_servidor)
    except OSError as erro:  # ex.: o Python que sobe o servidor não existe mais
        print(f"Não consegui concluir o comando: {erro}", file=sys.stderr)
        return 1
