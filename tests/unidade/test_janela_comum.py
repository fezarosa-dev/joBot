"""Janela comum do login (T232; D136.1 a D136.8): sem navegador, com a janela falsa."""

import asyncio
import contextlib
import logging
import os
import socket
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from apoio.cofre_falso import CofreFalso
from apoio.janela_falsa import JanelaFalsa
from apoio.site_falso import LeitorFalso
from jobot.navegador import limites
from jobot.navegador.execucao import Dependencias
from jobot.navegador.janela_comum import (
    Janela,
    JanelaComum,
    argumentos_da_janela,
    esperar_fechar,
    perfil_em_uso,
)
from jobot.navegador.login_manual import fazer_login
from jobot.navegador.perfil import pasta_do_perfil
from jobot.sistema.cofre import Cofre

pytestmark = pytest.mark.anyio

LEITOR = LeitorFalso(base="https://site.test")


class ExcecaoDoTeste(Exception):
    """Para o `fazer_login` logo depois de abrir a janela, antes da conferência."""


def _janela(
    falsa: JanelaFalsa,
    abertas: list[Sequence[str]],
    envs: list[Mapping[str, str]] | None = None,
    caminho: Path | None = Path("/x/chrome"),
) -> JanelaComum:
    async def achar() -> Path | None:
        return caminho

    async def abrir(argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        abertas.append(argumentos)
        if envs is not None:
            envs.append(ambiente)
        return falsa

    return JanelaComum(caminho=achar, abrir=abrir)


def _deps(dados: Path, lancados: list[dict[str, Any]], ambiente: Mapping[str, str]) -> Dependencias:
    async def lancar(**argumentos: Any) -> Any:
        lancados.append(argumentos)  # sem raise: o `abrir_contexto` viraria `sem_navegador`
        return object()

    return Dependencias(
        dados=dados,
        lancar=lancar,
        ambiente=lambda: ambiente,
        politica=lambda leitor: lambda url: True,
        sortear=lambda: limites.ESPERA_MIN_S,
        cofre=Cofre(dados, CofreFalso()),
        avisar=lambda titulo, frase: None,
    )


# ------------------------------------------------------------------ argumentos e trava


def test_argumentos_da_janela_sem_automacao() -> None:
    assert argumentos_da_janela(
        Path("/x/chrome"), Path("/d/navegador"), "https://site.test/login"
    ) == [
        "/x/chrome",
        "--user-data-dir=/d/navegador",
        "--password-store=basic",
        "--no-first-run",
        "--no-default-browser-check",
        "https://site.test/login",
    ]


def _pid_morto() -> int:
    processo = subprocess.Popen(["true"])
    processo.wait()
    return processo.pid


@pytest.mark.parametrize(
    ("alvo", "esperado", "log"),
    [
        pytest.param(None, False, None, id="sem-link"),
        pytest.param("vivo", True, None, id="mesma-maquina-vivo"),
        pytest.param("morto", False, None, id="mesma-maquina-morto"),
        pytest.param("outra-maquina-1", True, "outra máquina", id="outra-maquina"),
        pytest.param("arquivo", True, "não se lê", id="arquivo-comum"),
        pytest.param("semhifen", True, "alvo torto", id="sem-hifen"),
        pytest.param("pid-abc", True, "alvo torto", id="pid-nao-numero"),
    ],
)
def test_perfil_em_uso_le_o_singleton_lock(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    alvo: str | None,
    esperado: bool,
    log: str | None,
) -> None:
    trava = tmp_path / "SingletonLock"
    maquina = socket.gethostname()
    match alvo:
        case None:
            pass
        case "vivo":
            os.symlink(f"{maquina}-{os.getpid()}", trava)
        case "morto":
            os.symlink(f"{maquina}-{_pid_morto()}", trava)
        case "arquivo":
            trava.write_text("não é link")  # o `os.readlink` dá OSError(EINVAL)
        case "pid-abc":
            os.symlink(f"{maquina}-abc", trava)
        case _:
            os.symlink(alvo, trava)
    with caplog.at_level(logging.DEBUG):
        assert perfil_em_uso(tmp_path) is esperado
    if log is not None:
        assert log in caplog.text


# ------------------------------------------------------------------ espera e sinais


async def test_janela_que_fecha_no_prazo_nao_recebe_sinal() -> None:
    j = JanelaFalsa(ja_saiu=True)
    assert await esperar_fechar(j) is True
    assert j.sinais == []


@pytest.mark.parametrize(
    ("sai_no", "sinais"), [("kill", ["terminate", "kill"]), ("terminate", ["terminate"])]
)
async def test_janela_que_nao_fecha_recebe_terminate_e_depois_kill(
    monkeypatch: pytest.MonkeyPatch, sai_no: str, sinais: list[str]
) -> None:
    monkeypatch.setattr(limites, "PRAZO_LOGIN_MANUAL_S", 0)
    monkeypatch.setattr(limites, "ESPERA_SAIR_JANELA_S", 0)
    j = JanelaFalsa(sai_no=sai_no)
    assert await esperar_fechar(j) is False
    assert j.sinais == sinais


@pytest.mark.parametrize(
    ("sumiu", "sinais"), [("terminate", ["terminate"]), ("kill", ["terminate", "kill"])]
)
async def test_janela_que_some_antes_do_sinal_nao_estoura(
    monkeypatch: pytest.MonkeyPatch, sumiu: str, sinais: list[str]
) -> None:
    monkeypatch.setattr(limites, "PRAZO_LOGIN_MANUAL_S", 0)
    monkeypatch.setattr(limites, "ESPERA_SAIR_JANELA_S", 0)
    j = JanelaFalsa(sumiu=sumiu)
    try:
        fechou: bool | str = await esperar_fechar(j)
    except ProcessLookupError:
        fechou = "estourou"
    assert fechou is False
    assert j.sinais == sinais


async def test_janela_que_sai_com_erro_vai_ao_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert await esperar_fechar(JanelaFalsa(ja_saiu=True, codigo=3)) is True
    assert "saiu com o código 3" in caplog.text
    assert "/x/chrome" not in caplog.text


async def test_janela_que_sai_com_zero_nao_vai_ao_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert await esperar_fechar(JanelaFalsa(ja_saiu=True)) is True
    assert caplog.text == ""


async def test_erro_na_espera_fecha_a_janela() -> None:
    j = JanelaFalsa(erro=OSError("falhou"), sai_no="terminate")
    with pytest.raises(OSError, match="falhou"):
        await esperar_fechar(j)
    assert j.sinais == ["terminate"]


# ------------------------------------------------------------------ fazer login


async def test_login_sem_tela_nao_abre_janela(tmp_path: Path) -> None:
    abertas: list[Sequence[str]] = []
    lancados: list[dict[str, Any]] = []
    janela = _janela(JanelaFalsa(ja_saiu=True), abertas)
    assert await fazer_login(LEITOR, _deps(tmp_path, lancados, {}), janela) == "sem_tela"
    assert abertas == []
    assert lancados == []


async def test_login_sem_navegador(tmp_path: Path) -> None:
    abertas: list[Sequence[str]] = []
    lancados: list[dict[str, Any]] = []
    janela = _janela(JanelaFalsa(ja_saiu=True), abertas, caminho=None)
    deps = _deps(tmp_path, lancados, {"DISPLAY": ":0"})
    assert await fazer_login(LEITOR, deps, janela) == "sem_navegador"
    assert abertas == []
    assert lancados == []


async def test_login_com_perfil_em_uso_nao_abre_janela(tmp_path: Path) -> None:
    os.symlink(f"{socket.gethostname()}-{os.getpid()}", pasta_do_perfil(tmp_path) / "SingletonLock")
    abertas: list[Sequence[str]] = []
    lancados: list[dict[str, Any]] = []
    janela = _janela(JanelaFalsa(ja_saiu=True), abertas)
    deps = _deps(tmp_path, lancados, {"DISPLAY": ":0"})
    assert await fazer_login(LEITOR, deps, janela) == "em_uso"
    assert abertas == []
    assert lancados == []


async def test_janela_comum_recebe_o_ambiente_do_navegador(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEGREDO_DO_TESTE", "x")
    monkeypatch.setenv("HOME", "/x/casa")  # uma de `VARIAVEIS_DO_NAVEGADOR`: tem de passar
    monkeypatch.setenv("DISPLAY", ":99")  # a tela validada (`:7`) vence a do processo
    abertas: list[Sequence[str]] = []
    envs: list[Mapping[str, str]] = []
    janela = _janela(JanelaFalsa(erro=ExcecaoDoTeste(), sai_no="terminate"), abertas, envs)
    deps = _deps(tmp_path, [], {"DISPLAY": ":7"})
    with contextlib.suppress(ExcecaoDoTeste):
        await fazer_login(LEITOR, deps, janela)
    assert len(envs) == 1
    assert "SEGREDO_DO_TESTE" not in envs[0]
    assert envs[0].get("HOME") == "/x/casa"
    assert envs[0]["DISPLAY"] == ":7"


@pytest.mark.parametrize("url", ["--remote-debugging-port=9222", "javascript:alert(1)"])
async def test_login_recusa_url_que_nao_e_http(tmp_path: Path, url: str) -> None:
    abertas: list[Sequence[str]] = []
    lancados: list[dict[str, Any]] = []
    # se a janela abrir, o `wait()` levanta `ExcecaoDoTeste` e para antes da conferência
    janela = _janela(JanelaFalsa(erro=ExcecaoDoTeste(), sai_no="terminate"), abertas)
    deps = _deps(tmp_path, lancados, {"DISPLAY": ":0"})
    leitor = LeitorFalso(base="https://site.test", url_login=url)
    recusou = False
    try:
        await fazer_login(leitor, deps, janela)
    except ValueError:
        recusou = True
    except ExcecaoDoTeste:
        pass
    assert abertas == []
    assert lancados == []
    assert recusou


async def test_cancelar_o_login_fecha_a_janela_comum(tmp_path: Path) -> None:
    abertas: list[Sequence[str]] = []
    j = JanelaFalsa(sai_no="terminate")  # o `terminate()` solta o `wait()`: sem tempo real
    deps = _deps(tmp_path, [], {"DISPLAY": ":0"})
    tarefa = asyncio.create_task(fazer_login(LEITOR, deps, _janela(j, abertas)))
    for _ in range(1000):
        if abertas or tarefa.done():
            break
        await asyncio.sleep(0)
    assert abertas
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa
    assert j.sinais[0] == "terminate"
