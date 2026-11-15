"""Pasta e preferências do perfil do navegador (D132.3, D132.43).

O perfil guarda cookies de sessão: nunca vai ao log, e o conteúdo do arquivo de
preferências também não.
"""

import json
import logging
import os
import shutil
from pathlib import Path

from jobot.sistema.pastas import PASTA_NAVEGADOR

_LOG = logging.getLogger(__name__)

# Chaves do Chromium que desligam o gerenciador de senhas e o preenchimento automático.
PREFERENCIAS: dict[str, object] = {
    "credentials_enable_service": False,
    "profile": {"password_manager_enabled": False},
    "autofill": {"profile_enabled": False},
}


def _sem_symlink(caminho: Path) -> None:
    if caminho.is_symlink():  # o alvo pode estar fora da pasta de dados
        raise OSError(f"{caminho.name} é um link simbólico; recusado")


def pasta_do_perfil(dados: Path) -> Path:
    """`<dados>/navegador/`, criada 0700; recusa symlink."""
    pasta = dados / PASTA_NAVEGADOR
    _sem_symlink(pasta)
    pasta.mkdir(mode=0o700, parents=True, exist_ok=True)
    pasta.chmod(0o700)
    return pasta


def _lido(arquivo: Path) -> tuple[dict[str, object], bool]:
    """Conteúdo atual e se ele estava ilegível (será reescrito)."""
    try:
        # O_NOFOLLOW fecha a janela entre o is_symlink e a leitura
        fd = os.open(arquivo, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return {}, False
    with os.fdopen(fd, "rb") as entrada:
        bruto = entrada.read()
    try:
        atual = json.loads(bruto.decode("utf-8"))
    except ValueError, RecursionError:  # JSON torto, não UTF-8 ou fundo demais
        atual = None
    if isinstance(atual, dict):
        return atual, False
    return {}, True


def _junta(atual: dict[str, object]) -> dict[str, object]:
    junto = dict(atual)
    for chave, valor in PREFERENCIAS.items():
        if isinstance(valor, dict):
            bloco = atual.get(chave)
            junto[chave] = {**(bloco if isinstance(bloco, dict) else {}), **valor}
        else:
            junto[chave] = valor
    return junto


def preparar_preferencias(perfil: Path) -> None:
    """Grava as três chaves em `Default/Preferences`, mantendo o resto do arquivo.

    `perfil` deve vir de `pasta_do_perfil`: só `Default/` é criada aqui (0700).
    """
    pasta = perfil / "Default"
    arquivo = pasta / "Preferences"
    _sem_symlink(pasta)
    pasta.mkdir(mode=0o700, parents=True, exist_ok=True)
    _sem_symlink(arquivo)
    atual, ilegivel = _lido(arquivo)
    dados = json.dumps(_junta(atual)).encode("utf-8")
    tmp = pasta / "Preferences.tmp"
    tmp.unlink(missing_ok=True)  # sobra de queda; unlink não segue symlink
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as saida:
            os.fchmod(fd, 0o600)  # o umask não pode apertar o 0600
            saida.write(dados)
            saida.flush()
            os.fsync(fd)
        os.replace(tmp, arquivo)
        if ilegivel:
            _LOG.warning(
                "preferências do perfil ilegíveis: arquivo reescrito só com as chaves do joBot"
            )
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def apagar_perfil(dados: Path) -> None:
    """Apaga a pasta do perfil inteira; recusa symlink; sem perfil, não faz nada."""
    pasta = dados / PASTA_NAVEGADOR
    _sem_symlink(pasta)
    if pasta.exists():
        shutil.rmtree(pasta)
