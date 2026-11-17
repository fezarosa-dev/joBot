import ast
import logging
import os
from pathlib import Path
from typing import Any

import playwright
import pytest

from jobot.navegador import abrir, limites
from jobot.navegador.abrir import (
    SemNavegador,
    SemTela,
    abrir_contexto,
    caminho_do_navegador,
    chromium_do_jobot,
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


async def test_lancador_de_producao_passa_so_o_ambiente_do_navegador(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # lista literal: iterar `abrir.VARIAVEIS_DO_NAVEGADOR` daria AttributeError no vermelho
    nomes = (
        "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LANGUAGE", "TMPDIR",
        "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_DATA_DIRS",
        "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR", "SEGREDO_DO_TESTE",
    )  # fmt: skip
    for nome in nomes:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("HOME", "/casa/x")
    monkeypatch.setenv("PATH", "/bin:/usr/bin")
    monkeypatch.setenv("LANG", "pt_BR.UTF-8")
    monkeypatch.setenv("SEGREDO_DO_TESTE", "x")
    monkeypatch.setenv("DISPLAY", ":99")
    pw = _Playwright()
    await abrir_contexto(tmp_path, {"DISPLAY": ":7"}, lancador_de_producao(pw, {"DISPLAY": ":7"}))  # type: ignore[arg-type]
    assert len(pw.chromium.chamadas) == 1
    env = pw.chromium.chamadas[0]["env"]
    assert "SEGREDO_DO_TESTE" not in env
    assert env == {
        "HOME": "/casa/x",
        "PATH": "/bin:/usr/bin",
        "LANG": "pt_BR.UTF-8",
        "DISPLAY": ":7",
    }


async def test_chrome_primeiro_depois_chromium(tmp_path: Path) -> None:
    lancador = _Lancador(falham=(1,))
    assert await abrir_contexto(tmp_path, TELA, lancador) is CONTEXTO
    assert len(lancador.chamadas) == 2
    assert lancador.chamadas[0].get("channel") == "chrome"
    assert "channel" not in lancador.chamadas[1]


async def test_contexto_sem_downloads_nem_service_workers(tmp_path: Path) -> None:
    lancador = _Lancador(falham=(1,))
    await abrir_contexto(tmp_path, TELA, lancador)
    assert len(lancador.chamadas) == 2
    for chamada in lancador.chamadas:
        assert chamada.get("accept_downloads") is False
        assert chamada.get("service_workers") == "block"


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


def _chromium_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, criar: bool) -> Path:
    """O executável no lugar onde o Playwright o põe (`chromium-<n>/chrome-linux64/chrome`)."""
    executavel = tmp_path / "chromium-1" / "chrome-linux64" / "chrome"
    executavel.parent.mkdir(parents=True)
    if criar:
        executavel.touch()

    class _Gerenciador:
        async def __aenter__(self) -> _Playwright:
            return _Playwright(str(executavel))

        async def __aexit__(self, *saida: object) -> None:
            return None

    monkeypatch.setattr(abrir, "async_playwright", _Gerenciador)
    return executavel


@pytest.mark.parametrize("com_marca", [False, True], ids=["sem-marca", "com-marca"])
async def test_chromium_sem_marca_de_instalacao_nao_conta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, com_marca: bool
) -> None:
    monkeypatch.setattr(abrir, "CAMINHO_CHROME", tmp_path / "nao-existe")
    executavel = _chromium_falso(tmp_path, monkeypatch, criar=True)
    if com_marca:
        (tmp_path / "chromium-1" / "INSTALLATION_COMPLETE").touch()
    # um download cortado deixa o executável sem a marca: não passa por instalado (D137.6)
    assert await caminho_do_navegador() == (executavel if com_marca else None)


async def test_navegador_instalado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chrome = tmp_path / "chrome"
    chromium = _chromium_falso(tmp_path, monkeypatch, criar=False)
    monkeypatch.setattr(abrir, "CAMINHO_CHROME", chrome)
    assert await navegador_instalado() is None
    chromium.touch()
    (chromium.parents[1] / "INSTALLATION_COMPLETE").touch()
    assert await navegador_instalado() == "chromium"
    chrome.touch()
    assert await navegador_instalado() == "chrome"


async def test_caminho_do_navegador_prefere_o_chrome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arquivo_existente = tmp_path / "chrome"
    arquivo_existente.touch()

    def explode() -> Any:
        raise AssertionError("com o Chrome no lugar, o driver do Playwright não sobe")

    monkeypatch.setattr(abrir, "CAMINHO_CHROME", arquivo_existente)
    monkeypatch.setattr(abrir, "async_playwright", explode)
    assert await caminho_do_navegador() == arquivo_existente


async def test_chromium_do_jobot_sem_arquivo_da_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _chromium_falso(tmp_path, monkeypatch, criar=False)
    assert await chromium_do_jobot() is None


async def test_chromium_do_jobot_ignora_o_chrome_do_sistema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chrome = tmp_path / "chrome"
    chrome.touch()
    monkeypatch.setattr(abrir, "CAMINHO_CHROME", chrome)
    chromium = _chromium_falso(tmp_path, monkeypatch, criar=False)
    assert await chromium_do_jobot() is None
    chromium.touch()
    (chromium.parents[1] / "INSTALLATION_COMPLETE").touch()
    assert await chromium_do_jobot() == chromium


def _core_bundle() -> Path:
    return Path(playwright.__file__).parent / "driver" / "package" / "lib" / "coreBundle.js"


def test_password_store_basic_vem_do_playwright() -> None:
    # a janela automática lê os cookies v10 da janela comum só com esta opção (D136.9)
    arquivo = _core_bundle()
    assert arquivo.exists(), "o Playwright mudou o pacote: ache onde ficam os chromiumSwitches"
    assert "--password-store=basic" in arquivo.read_text(encoding="utf-8")
