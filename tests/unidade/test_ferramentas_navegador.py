"""`jobot ferramentas baixar navegador` (T330; D183.24): o `playwright install` de sempre, também
na casca (o joBot não redistribui o navegador), com as linhas JSON que a casca lê; só o teste do
SIGTERM sobe processo de verdade."""

import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

import jobot
import jobot.cli
from apoio.janela_falsa import JanelaFalsa
from jobot.cli import ferramentas
from jobot.navegador.instalador import comando_de_baixar
from jobot.navegador.janela_comum import Janela


def _args() -> argparse.Namespace:
    return argparse.Namespace(comando="ferramentas", acao="baixar", ferramenta="navegador")


def _linhas(saida: str) -> list[dict[str, object]]:
    return [json.loads(linha) for linha in saida.splitlines()]


class _Abrir:
    def __init__(self, codigo: int = 0) -> None:
        self.codigo = codigo
        self.abertos: list[list[str]] = []

    async def __call__(self, argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        self.abertos.append(list(argumentos))
        return JanelaFalsa(ja_saiu=True, codigo=self.codigo)


class _AbrirQueFalha:
    async def __call__(self, argumentos: Sequence[str], ambiente: Mapping[str, str]) -> Janela:
        raise OSError("sem o python")


@pytest.mark.parametrize(("codigo", "fim", "saida"), [(0, "pronto", 0), (1, "falhou", 1)])
def test_chama_o_playwright_install_e_escreve_as_linhas(
    capsys: pytest.CaptureFixture[str], codigo: int, fim: str, saida: int
) -> None:
    abrir = _Abrir(codigo)
    assert ferramentas.baixar_navegador(_args(), abrir=abrir) == saida
    assert abrir.abertos == [comando_de_baixar()]
    # a etapa começa (sem total: o Playwright não diz o tamanho) e a linha final diz o fim
    assert _linhas(capsys.readouterr().out) == [{"etapa": "navegador", "feito": 0}, {"fim": fim}]


def test_instalador_que_nao_abre_falha_com_linha_final(capsys: pytest.CaptureFixture[str]) -> None:
    assert ferramentas.baixar_navegador(_args(), abrir=_AbrirQueFalha()) == 1
    assert _linhas(capsys.readouterr().out)[-1] == {"fim": "falhou"}


def test_sem_arquivo_nem_sha256_na_linha_de_comando() -> None:
    """O caminho do arquivo da release saiu (D183.24): a opção velha é recusada (o argparse
    sai com 2); o controle sem ela chega ao subcomando no teste de baixo."""
    assert jobot.cli.main(["ferramentas", "baixar", "navegador", "--arquivo", "c.tar.gz"]) == 2


def test_main_chega_no_subcomando(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recebidos: list[argparse.Namespace] = []
    # sem isso o executar abre o log na pasta de dados real de quem roda o teste
    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    monkeypatch.setattr(ferramentas, "configurar_log", lambda _dados: None)

    def falso(args: argparse.Namespace, **_: object) -> int:
        recebidos.append(args)
        return 0

    monkeypatch.setattr(ferramentas, "baixar_navegador", falso)
    assert jobot.cli.main(["ferramentas", "baixar", "navegador"]) == 0
    assert [(a.acao, a.ferramenta) for a in recebidos] == [("baixar", "navegador")]


# o subcomando de verdade, com o `playwright install` trocado por um processo que só espera, aberto
# pelo `abrir_instalador` de produção (em sessão própria); o PID dele sai no stderr
_SUBCOMANDO = """
import argparse, sys
from jobot.cli import ferramentas
from jobot.navegador.instalador import abrir_instalador

async def abrir(argumentos, ambiente):
    espera = [sys.executable, "-c", "import time; time.sleep(300)"]
    janela = await abrir_instalador(espera, ambiente)
    print(janela._processo.pid, file=sys.stderr, flush=True)
    return janela

sys.exit(ferramentas.baixar_navegador(argparse.Namespace(), abrir=abrir))
"""


@pytest.mark.skipif(sys.platform == "win32", reason="no Windows quem chama usa o taskkill /T")
def test_sigterm_encerra_o_download_e_sai_com_a_linha_final() -> None:
    """D183.24: a casca cancelando (ou o `jobot atualizar` no prazo) manda SIGTERM; o download,
    em sessão própria, não fica órfão baixando enquanto o desfazer apaga o venv."""
    proc = subprocess.Popen(
        [sys.executable, "-c", _SUBCOMANDO], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )  # fmt: skip
    assert proc.stderr is not None
    neto = int(proc.stderr.readline())
    try:
        proc.send_signal(signal.SIGTERM)
        saida, _ = proc.communicate(timeout=30)
        assert proc.returncode == 1
        assert _linhas(saida) == [{"etapa": "navegador", "feito": 0}, {"fim": "falhou"}]
        with pytest.raises(ProcessLookupError):
            os.kill(neto, 0)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(neto, signal.SIGKILL)
        proc.kill()
        proc.wait()
