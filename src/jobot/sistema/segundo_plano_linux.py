"""Segundo plano no Linux: serviço de usuário do systemd e atalho do menu (desenho 12.5).

Tudo que fala com o sistema passa por `rodar`, o executor de comandos injetado.
"""

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from jobot.nucleo.modelo import Motivo
from jobot.sistema.caso import nome_do_container, prefixo_host

SERVICO = "jobot.service"


@dataclass(frozen=True)
class Resultado:
    codigo: int
    saida: str = ""


Rodar = Callable[[Sequence[str]], Resultado]


@dataclass(frozen=True)
class Caso:
    """Como o joBot roda: direto (`container` None) ou dentro de uma distrobox."""

    python: str
    container: str | None = None
    distrobox_enter: str = "distrobox-enter"


@dataclass(frozen=True)
class Estado:
    habilitado: bool
    ativo: bool


class Recusa(Exception):
    def __init__(self, motivo: Motivo) -> None:
        super().__init__(motivo.chave)
        self.motivo = motivo


_TEXTOS = {
    "segundo_plano.sem_host_exec": "não consegui falar com o sistema de fora: faltam "
    "o distrobox-host-exec ou o distrobox-enter",
    "segundo_plano.systemd_nao_responde": "o systemd do usuário não responde",
    "segundo_plano.home_diferente": "a pasta pessoal do container não é a do sistema",
    "segundo_plano.systemctl_falhou": "o systemctl {comando} falhou: {saida}",
}


def rodar_comando(comando: Sequence[str]) -> Resultado:
    """Executor real: lista de argumentos, sem shell, sem terminal."""
    try:
        feito = subprocess.run(
            list(comando),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Resultado(124)
    except OSError:  # programa que não existe ou não abre
        return Resultado(127)
    return Resultado(feito.returncode, feito.stdout)


# --- texto dos arquivos (funções puras) -------------------------------------------------

_SEGURO = re.compile(r"[A-Za-z0-9_@+=:,./-]+")
_RESERVADOS_DESKTOP = frozenset(" \t\"'\\><~|&;$*?#()`")


def _limpo(texto: str) -> str:
    if any(ord(c) < 32 or ord(c) == 127 for c in texto):  # quebra de linha injetaria chaves
        raise ValueError(f"caractere de controle em {texto!r}")
    return texto


def _aspas_systemd(arg: str) -> str:
    if _SEGURO.fullmatch(_limpo(arg)):
        return arg
    # % e $ são expandidos nas linhas Exec do systemd
    texto = arg.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
    return f'"{texto}"'


def _aspas_desktop(arg: str) -> str:
    texto = _limpo(arg).replace("%", "%%")  # % é código de campo no Exec
    if texto and not _RESERVADOS_DESKTOP & set(texto):
        return texto
    texto = re.sub(r'(["`$\\])', r"\\\1", texto)  # escape do argumento entre aspas
    return '"' + texto.replace("\\", "\\\\") + '"'  # escape de string do arquivo .desktop


def _comando(caso: Caso, acao: str, *, sem_terminal: bool) -> list[str]:
    jobot = [caso.python, "-m", "jobot", acao]
    if caso.container is None:
        return jobot
    entrada = [caso.distrobox_enter, "-n", caso.container]
    return [*entrada, *(["--no-tty"] if sem_terminal else []), "--", *jobot]


def texto_do_servico(caso: Caso) -> str:
    def linha(chave: str, acao: str) -> str:
        args = _comando(caso, acao, sem_terminal=True)
        return f"{chave}=" + " ".join(_aspas_systemd(a) for a in args)

    # dentro da distrobox, parar o serviço só encerra o distrobox-enter: o `sair` encerra o servidor
    parar = [linha("ExecStop", "sair")] if caso.container is not None else []
    return "\n".join(
        [
            "[Unit]",
            "Description=joBot, busca de vagas em fontes públicas",
            "",
            "[Service]",
            linha("ExecStart", "serve"),
            *parar,
            "Restart=on-failure",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )


def texto_do_atalho(caso: Caso) -> str:
    comando = " ".join(_aspas_desktop(a) for a in _comando(caso, "abrir", sem_terminal=False))
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Name=joBot",
            "Comment=Painel local de vagas",
            f"Exec={comando}",
            "Terminal=false",
            "Categories=Office;",
            "",
        ]
    )


# --- sistema ----------------------------------------------------------------------------


def _ambiente(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _casa(env: Mapping[str, str]) -> Path:
    return Path(env["HOME"]) if env.get("HOME") else Path.home()


def _arquivo_do_servico(env: Mapping[str, str]) -> Path:
    return _casa(env) / ".config" / "systemd" / "user" / SERVICO


def _arquivo_do_atalho(env: Mapping[str, str]) -> Path:
    return _casa(env) / ".local" / "share" / "applications" / "jobot.desktop"


def _systemctl(env: Mapping[str, str], rodar: Rodar, *args: str) -> Resultado:
    return rodar((*prefixo_host(env), "systemctl", "--user", *args))


def _no_host(env: Mapping[str, str], rodar: Rodar, script: str) -> Resultado:
    return rodar((*prefixo_host(env), "sh", "-c", script))


def _distrobox_enter(env: Mapping[str, str], rodar: Rodar) -> str | None:
    achado = _no_host(env, rodar, "command -v distrobox-enter")
    return (achado.saida.strip() or None) if achado.codigo == 0 else None


def _mesma_pasta(a: Path, b: Path) -> bool:
    # no Silverblue /home é link para /var/home: compara o destino, não o texto
    return a == b or (a.exists() and b.exists() and a.samefile(b))


def _caso(env: Mapping[str, str], rodar: Rodar) -> Caso:
    container = nome_do_container(env)
    enter = (_distrobox_enter(env, rodar) if container else None) or "distrobox-enter"
    return Caso(python=sys.executable, container=container, distrobox_enter=enter)


def pode_ligar(env: Mapping[str, str], rodar: Rodar) -> Motivo | None:
    """None se dá para ligar; senão o motivo da recusa (chave de i18n)."""
    dentro = bool(prefixo_host(env))
    if dentro and _distrobox_enter(env, rodar) is None:
        return Motivo(chave="segundo_plano.sem_host_exec")
    if _systemctl(env, rodar, "show-environment").codigo != 0:
        return Motivo(chave="segundo_plano.systemd_nao_responde")
    if dentro:
        casa_do_host = _no_host(env, rodar, 'printf %s "$HOME"')
        fora = casa_do_host.saida.strip()
        if casa_do_host.codigo != 0 or not fora or not _mesma_pasta(_casa(env), Path(fora)):
            return Motivo(chave="segundo_plano.home_diferente")
    return None


def _gravar_atalho(env: Mapping[str, str], caso: Caso) -> None:
    arquivo = _arquivo_do_atalho(env)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto_do_atalho(caso), encoding="utf-8")


def criar_atalho(rodar: Rodar, *, env: Mapping[str, str] | None = None) -> None:
    """Cria o atalho do menu; vale mesmo com o segundo plano desligado (DR-37)."""
    env = _ambiente(env)
    _gravar_atalho(env, _caso(env, rodar))


def ligar(rodar: Rodar, *, env: Mapping[str, str] | None = None) -> None:
    env = _ambiente(env)
    motivo = pode_ligar(env, rodar)
    if motivo is not None:
        raise Recusa(motivo)
    caso = _caso(env, rodar)
    arquivo = _arquivo_do_servico(env)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto_do_servico(caso), encoding="utf-8")
    _gravar_atalho(env, caso)
    for args in (("daemon-reload",), ("enable", "--now", SERVICO)):
        feito = _systemctl(env, rodar, *args)
        if feito.codigo != 0:
            params = {"comando": " ".join(args), "saida": feito.saida.strip()}
            raise Recusa(Motivo(chave="segundo_plano.systemctl_falhou", params=params))


def desligar(rodar: Rodar, *, env: Mapping[str, str] | None = None) -> None:
    env = _ambiente(env)
    _systemctl(env, rodar, "disable", "--now", SERVICO)  # sem serviço instalado também vale
    _arquivo_do_servico(env).unlink(missing_ok=True)
    _systemctl(env, rodar, "daemon-reload")


def status(rodar: Rodar, *, env: Mapping[str, str] | None = None) -> Estado:
    env = _ambiente(env)
    return Estado(
        habilitado=_systemctl(env, rodar, "is-enabled", SERVICO).codigo == 0,
        ativo=_systemctl(env, rodar, "is-active", SERVICO).codigo == 0,
    )


def executar(args: argparse.Namespace) -> int:
    try:
        if args.acao == "ligar":
            ligar(rodar_comando)
            print("segundo plano ligado")
        elif args.acao == "desligar":
            desligar(rodar_comando)
            print("segundo plano desligado")
        else:
            estado = status(rodar_comando)
            print(f"segundo plano: {'ligado' if estado.habilitado else 'desligado'}")
            print(f"rodando: {'sim' if estado.ativo else 'não'}")
    except Recusa as recusa:
        motivo = recusa.motivo
        texto = _TEXTOS.get(motivo.chave, motivo.chave).format(**motivo.params)
        print(texto, file=sys.stderr)
        return 1
    return 0
