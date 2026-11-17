"""Segredo da parada local (`<dados>/sair.token`, desenho 6.1, T326)."""

import os
import stat
from pathlib import Path

import pytest

from jobot.sistema import sair


def test_grava_o_segredo_0600_e_le_de_volta(tmp_path: Path) -> None:
    velho = os.umask(0o022)  # o 0600 não depende do umask do serve
    try:
        segredo = sair.gravar_token(tmp_path)
    finally:
        os.umask(velho)
    arquivo = tmp_path / sair.NOME
    assert len(segredo) >= 32
    assert arquivo.read_text(encoding="ascii") == segredo
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert sair.ler_token(tmp_path) == segredo
    assert sair.gravar_token(tmp_path) != segredo  # um segredo novo a cada subida


def test_falha_no_replace_mantem_o_antigo_e_tira_o_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    antigo = sair.gravar_token(tmp_path)
    modos: list[int] = []

    def quebra(origem: Path, destino: Path) -> None:
        modos.append(stat.S_IMODE(os.stat(origem).st_mode))
        raise OSError("disco cheio")

    monkeypatch.setattr(os, "replace", quebra)
    velho = os.umask(0o022)
    try:
        with pytest.raises(OSError, match="disco cheio"):
            sair.gravar_token(tmp_path)
    finally:
        os.umask(velho)
    assert modos == [0o600]  # o .tmp já nasce 0600
    assert sair.ler_token(tmp_path) == antigo
    assert sorted(p.name for p in tmp_path.iterdir()) == [sair.NOME]


def test_apagar_tira_o_arquivo_e_sem_arquivo_le_none(tmp_path: Path) -> None:
    sair.gravar_token(tmp_path)
    assert (tmp_path / sair.NOME).exists()
    sair.apagar_token(tmp_path)
    assert not (tmp_path / sair.NOME).exists()
    assert sair.ler_token(tmp_path) is None
    sair.apagar_token(tmp_path)  # já apagado: não levanta
