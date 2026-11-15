import ast
import logging
import os
from pathlib import Path
from typing import Any

import pytest

from jobot.navegador import abrir, limites
from jobot.navegador.abrir import (
    SemNavegador,
    SemTela,
    abrir_contexto,
    lancador_de_producao,
    navegador_instalado,
)
from jobot.sistema.pastas import PASTA_NAVEGADOR

pytestmark = pytest.mark.anyio

TELA = {"DISPLAY": ":0"}
CONTEXTO = object()


class _Lancador:
    """Guarda os argumentos de cada chamada; falha nas chamadas em `falham`."""

    def __init__(self, falham: tuple[int, ...] = (), erro: Exception | None = None) -> None:
        self.chamadas: list[dict[str, Any]] = []
        self.falham = falham
        self.erro = erro or RuntimeError("falhou")

    async def __call__(self, **argumentos: Any) -> Any:
        self.chamadas.append(argumentos)
        if len(self.chamadas) in self.falham:
            raise self.erro
        return CONTEXTO


class _Chromium:
    def __init__(self, executable_path: str = "") -> None:
        self.executable_path = executable_path
        self.chamadas: list[dict[str, Any]] = []

    async def launch_persistent_context(self, **argumentos: Any) -> Any:
        self.chamadas.append(argumentos)
        return CONTEXTO


class _Playwright:
    def __init__(self, executable_path: str = "") -> None:
        self.chromium = _Chromium(executable_path)


def test_limites_da_pagina_moram_em_limites() -> None:
    raiz = Path(__file__).resolve().parents[2]
    arquivos = [
        *(raiz / "src" / "jobot" / "navegador").glob("*.py"),
        raiz / "scripts" / "capturar_logado.py",
    ]
    nomes = {
        "ESPERA_ASSENTAR_MS",
        "_PASSOS_DEPOIS_DE_ROLAR",
        "PASSOS_DEPOIS_DE_ROLAR",
        "ESPERA_429_S",
        "ESPERAS_LIMITE",
    }
    achados: list[str] = []
    for arquivo in arquivos:
        if arquivo.name == "limites.py":
            continue
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Name) and no.id in nomes:
                achados.append(f"{arquivo.name}:{no.lineno} {no.id}")
            elif isinstance(no, ast.alias) and no.name in nomes:
                achados.append(f"{arquivo.name} import {no.name}")
    assert achados == []
    assert (limites.ESPERA_ASSENTAR_MS, limites.PASSOS_DEPOIS_DE_ROLAR) == (10_000, 5)


def test_limites_valores_do_plano() -> None:
    assert (limites.MAX_LISTA, limites.MAX_VAGA) == (10, 20)
    assert (limites.ESPERA_MIN_S, limites.ESPERA_MAX_S) == (3.0, 8.0)
    assert (limites.ESPERA_CLOUDFLARE_S, limites.ESPERA_TOKEN_S) == (30, 30)
    assert (limites.JANELA_PARADA_S, limites.PRAZO_LOGIN_MANUAL_S) == (900, 600)
    assert limites.MAX_RESPOSTA_BYTES == 5 * 1024 * 1024
    assert limites.MAX_RESPOSTAS == 50


async def test_lancador_de_producao_abre_visivel(tmp_path: Path) -> None:
    pw = _Playwright()
    contexto = await abrir_contexto(tmp_path, TELA, lancador_de_producao(pw, TELA))  # type: ignore[arg-type]
    assert contexto is CONTEXTO
    assert len(pw.chromium.chamadas) == 1
    argumentos = pw.chromium.chamadas[0]
    assert argumentos.get("headless") is False
    assert argumentos["user_data_dir"] == str(tmp_path / PASTA_NAVEGADOR)
    assert "args" not in argumentos
    assert "ignore_default_args" not in argumentos
    assert "--remote-debugging-port" not in repr(argumentos)


async def test_lancador_de_producao_mantem_home_e_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", "/casa/x")
    monkeypatch.setenv("PATH", "/bin:/usr/bin")
    pw = _Playwright()
    await abrir_contexto(tmp_path, {"DISPLAY": ":7"}, lancador_de_producao(pw, {"DISPLAY": ":7"}))  # type: ignore[arg-type]
    assert len(pw.chromium.chamadas) == 1
    env = pw.chromium.chamadas[0]["env"]
    assert env["HOME"] == os.environ["HOME"] == "/casa/x"
    assert env["PATH"] == os.environ["PATH"]
    assert env["DISPLAY"] == ":7"


async def test_chrome_primeiro_depois_chromium(tmp_path: Path) -> None:
    lancador = _Lancador(falham=(1,))
    assert await abrir_contexto(tmp_path, TELA, lancador) is CONTEXTO
    assert len(lancador.chamadas) == 2
    assert lancador.chamadas[0].get("channel") == "chrome"
    assert "channel" not in lancador.chamadas[1]


async def test_chrome_que_abre_nao_tenta_o_chromium(tmp_path: Path) -> None:
    lancador = _Lancador()
    await abrir_contexto(tmp_path, TELA, lancador)
    assert len(lancador.chamadas) == 1


async def test_os_dois_falhando_e_sem_navegador(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    lancador = _Lancador(falham=(1, 2), erro=RuntimeError("SEGREDO do playwright"))
    with caplog.at_level(logging.DEBUG), pytest.raises(SemNavegador) as ex:
        await abrir_contexto(tmp_path, TELA, lancador)
    assert "SEGREDO" not in str(ex.value)
    assert caplog.text.count("SEGREDO") == 1


async def test_sem_tela_nem_chama_o_lancador(tmp_path: Path) -> None:
    lancador = _Lancador()
    with pytest.raises(SemTela):
        await abrir_contexto(tmp_path, {}, lancador)
    assert lancador.chamadas == []


async def test_preferencias_gravadas_antes_de_abrir(tmp_path: Path) -> None:
    visto: list[bool] = []

    async def lancar(**argumentos: Any) -> Any:
        visto.append((Path(argumentos["user_data_dir"]) / "Default" / "Preferences").exists())
        return CONTEXTO

    await abrir_contexto(tmp_path, TELA, lancar)
    assert visto == [True]


async def test_navegador_instalado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chrome = tmp_path / "chrome"
    chromium = tmp_path / "chromium"

    class _Gerenciador:
        async def __aenter__(self) -> _Playwright:
            return _Playwright(str(chromium))

        async def __aexit__(self, *saida: object) -> None:
            return None

    monkeypatch.setattr(abrir, "CAMINHO_CHROME", chrome)
    monkeypatch.setattr(abrir, "async_playwright", _Gerenciador)
    assert await navegador_instalado() is None
    chromium.touch()
    assert await navegador_instalado() == "chromium"
    chrome.touch()
    assert await navegador_instalado() == "chrome"
