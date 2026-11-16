"""Instalador do navegador (T240; D137.1 a D137.3 e D137.13): sem rede, com processos falsos."""

import asyncio
import logging
import os
import signal
import sys
from asyncio.subprocess import DEVNULL
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from apoio.janela_falsa import JanelaFalsa
from jobot.navegador import limites
from jobot.navegador.abrir import VARIAVEIS_DO_NAVEGADOR
from jobot.navegador.instalador import (
    abrir_instalador,
    ambiente_de_instalar,
    baixar_chromium,
    comando_de_baixar,
    comando_de_remover,
    remover_chromium,
)
from jobot.navegador.janela_comum import Janela, encerrar

pytestmark = pytest.mark.anyio


class _Abrir:
    """O `abrir` falso: guarda `(argv, env)` em `abertos` e devolve a janela falsa."""

    def __init__(self, janela: JanelaFalsa, erro: Exception | None = None) -> None:
        self.janela = janela
        self.erro = erro
        self.abertos: list[tuple[Sequence[str], Mapping[str, str]]] = []

    async def __call__(self, argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        if self.erro is not None:
            raise self.erro
        self.abertos.append((list(argumentos), dict(ambiente)))
        return self.janela


class _Processo:
    """`Process` falso: `wait()` preso num `Event` (ou na hora); `kill()` também o solta."""

    pid = 4242

    def __init__(self, *, ja_saiu: bool = False) -> None:
        self.saiu = asyncio.Event()
        if ja_saiu:
            self.saiu.set()

    async def wait(self) -> int:
        await self.saiu.wait()
        return 0

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        self.saiu.set()


def _montar(
    monkeypatch: pytest.MonkeyPatch, processo: _Processo, erro_killpg: bool = False
) -> tuple[dict[str, Any], list[tuple[int, int]]]:
    kwargs: dict[str, Any] = {}
    killpg: list[tuple[int, int]] = []

    async def criar(*argumentos: str, **nomeados: Any) -> _Processo:
        kwargs.update(nomeados)
        return processo

    def killpg_falso(pid: int, sinal: int) -> None:
        killpg.append((pid, sinal))
        if sinal == signal.SIGKILL:
            processo.saiu.set()
        if erro_killpg:
            raise ProcessLookupError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", criar)
    monkeypatch.setattr(os, "killpg", killpg_falso)
    return kwargs, killpg


async def _esperar_abrir(abrir: _Abrir, tarefa: asyncio.Task[Any]) -> None:
    for _ in range(1000):
        if abrir.abertos or tarefa.done():
            break
        await asyncio.sleep(0)


# ------------------------------------------------------------------ comandos e ambiente


def test_comando_de_baixar() -> None:
    assert comando_de_baixar() == [
        sys.executable,
        "-P",
        "-m",
        "playwright",
        "install",
        "--no-shell",
        "chromium",
    ]
    assert "--with-deps" not in comando_de_baixar()


def test_comando_de_remover() -> None:
    assert comando_de_remover() == [sys.executable, "-P", "-m", "playwright", "uninstall"]
    assert "--all" not in comando_de_remover()


def test_ambiente_de_instalar_sem_segredo(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in VARIAVEIS_DO_NAVEGADOR:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("SEGREDO_DO_TESTE", "segredo")
    monkeypatch.setenv("HOME", "/casa")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "/navegadores")
    monkeypatch.setenv("DISPLAY", ":7")
    amb = ambiente_de_instalar()
    assert amb.get("PLAYWRIGHT_BROWSERS_PATH") == "/navegadores"
    assert amb.get("HOME") == "/casa"
    assert "SEGREDO_DO_TESTE" not in amb
    assert "DISPLAY" not in amb


# ------------------------------------------------------------------ grupo de processos


async def test_instalador_abre_em_grupo_proprio(monkeypatch: pytest.MonkeyPatch) -> None:
    kwargs, killpg = _montar(monkeypatch, _Processo())
    monkeypatch.setattr(limites, "ESPERA_SAIR_JANELA_S", 0)
    janela = await abrir_instalador(["x"], {})
    assert kwargs.get("start_new_session") is True
    assert "shell" not in kwargs
    assert (kwargs.get("stdout"), kwargs.get("stderr")) == (DEVNULL, DEVNULL)
    async with asyncio.timeout(5):  # rede de segurança: travar vira falha, não suíte pendurada
        await encerrar(janela)
    assert killpg == [(4242, signal.SIGTERM), (4242, signal.SIGKILL), (4242, signal.SIGKILL)]


@pytest.mark.parametrize("erro_killpg", [False, True], ids=["grupo-vivo", "grupo-sumiu"])
async def test_wait_manda_killpg_final_ao_grupo(
    monkeypatch: pytest.MonkeyPatch, erro_killpg: bool
) -> None:
    _, killpg = _montar(monkeypatch, _Processo(ja_saiu=True), erro_killpg)
    janela = await abrir_instalador(["x"], {})
    assert await janela.wait() == 0
    assert killpg == [(4242, signal.SIGKILL)]


# ------------------------------------------------------------------ baixar


async def test_baixar_pronto_com_codigo_zero() -> None:
    abrir = _Abrir(JanelaFalsa(ja_saiu=True))
    resultado = await baixar_chromium(abrir)
    assert len(abrir.abertos) == 1
    assert abrir.abertos[0][0] == comando_de_baixar()
    assert resultado == "pronto"


async def test_baixar_falhou_com_codigo_diferente_de_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    abrir = _Abrir(JanelaFalsa(ja_saiu=True, codigo=1))
    with caplog.at_level(logging.WARNING, logger="jobot.navegador.instalador"):
        assert await baixar_chromium(abrir) == "falhou"
    assert any(
        r.args and 1 in r.args for r in caplog.records if r.name == "jobot.navegador.instalador"
    )


async def test_abrir_que_levanta_oserror_da_falhou() -> None:
    abrir = _Abrir(JanelaFalsa(ja_saiu=True), erro=OSError("sem python"))
    assert await baixar_chromium(abrir) == "falhou"


async def test_prazo_estourado_encerra_e_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limites, "PRAZO_BAIXAR_S", 0)
    monkeypatch.setattr(limites, "ESPERA_SAIR_JANELA_S", 0)
    j = JanelaFalsa()  # o `wait()` só volta depois do `kill()`
    assert await baixar_chromium(_Abrir(j)) == "falhou"
    assert j.sinais == ["terminate", "kill"]


async def test_cancelar_encerra_o_processo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limites, "ESPERA_SAIR_JANELA_S", 0)
    j = JanelaFalsa()
    abrir = _Abrir(j)
    tarefa = asyncio.create_task(baixar_chromium(abrir))
    await _esperar_abrir(abrir, tarefa)
    assert abrir.abertos
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa
    assert j.sinais == ["terminate", "kill"]


# ------------------------------------------------------------------ remover


async def test_remover_pronto_com_codigo_zero() -> None:
    abrir = _Abrir(JanelaFalsa(ja_saiu=True))
    resultado = await remover_chromium(abrir)
    assert len(abrir.abertos) == 1
    assert abrir.abertos[0][0] == comando_de_remover()
    assert resultado == "pronto"


async def test_cancelar_remover_nao_sinaliza(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limites, "ESPERA_SAIR_JANELA_S", 0)
    j = JanelaFalsa()
    abrir = _Abrir(j)
    tarefa = asyncio.create_task(remover_chromium(abrir))
    await _esperar_abrir(abrir, tarefa)
    assert abrir.abertos
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa
    assert j.sinais == []
