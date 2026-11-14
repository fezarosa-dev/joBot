import argparse
import ast
import socket
import sys
import types
from pathlib import Path

import pytest

from jobot import cli

RAIZ = Path(__file__).resolve().parents[2]


def _servidor(familia: socket.AddressFamily, endereco: str) -> socket.socket:
    servidor = socket.socket(familia, socket.SOCK_STREAM)
    servidor.bind((endereco, 0))
    servidor.listen(1)
    return servidor


def test_rede_externa_bloqueada() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as externo:
        externo.settimeout(1)
        try:
            externo.connect(("93.184.216.34", 80))
        except RuntimeError as erro:
            assert "rede bloqueada" in str(erro)
        except OSError as erro:
            pytest.fail(f"a conexão externa não foi bloqueada: {erro!r}")
        else:
            pytest.fail("a conexão externa não foi bloqueada")

    for familia, endereco in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            servidor = _servidor(familia, endereco)
        except OSError:
            continue  # a máquina não tem esse loopback
        with servidor, socket.socket(familia, socket.SOCK_STREAM) as cliente:
            cliente.settimeout(1)
            cliente.connect(servidor.getsockname()[:2])


def test_dados_locais_no_gitignore() -> None:
    arquivo = RAIZ / ".gitignore"
    linhas = arquivo.read_text(encoding="utf-8").splitlines() if arquivo.exists() else []
    assert "dados_locais/" in [linha.strip() for linha in linhas]


def test_nenhum_teste_le_yaml() -> None:
    importados: list[str] = []
    for arquivo in (RAIZ / "tests").rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Import):
                importados += [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.module:
                importados.append(no.module)
    ruins = [m for m in importados if m.split(".")[0] in {"yaml", "ruamel"}]
    arquivos = [p.name for ext in ("*.yaml", "*.yml") for p in (RAIZ / "tests").rglob(ext)]
    assert ruins == []
    assert arquivos == []


def test_tabela_de_comandos() -> None:
    assert dict(cli.COMANDOS) == {
        "abrir": "jobot.sistema.abrir",
        "sair": "jobot.sistema.abrir",
        "segundo-plano": "jobot.sistema.segundo_plano_linux",
        "serve": "jobot.cli.servir",
        "buscar": "jobot.cli.buscar",
        "avaliar-rotulos": "jobot.cli.avaliar_rotulos",
    }


def test_comando_desconhecido_sai_com_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["nao-existe"]) == 2
    assert "nao-existe" in capsys.readouterr().err


def _falso(monkeypatch: pytest.MonkeyPatch, nome: str) -> list[argparse.Namespace]:
    chamadas: list[argparse.Namespace] = []
    modulo = types.ModuleType(nome)

    def executar(args: argparse.Namespace) -> int:
        chamadas.append(args)
        return 7

    modulo.executar = executar  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, nome, modulo)
    return chamadas


def test_sem_comando_equivale_a_abrir(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas = _falso(monkeypatch, "jobot.sistema.abrir")
    assert cli.main([]) == 7
    assert cli.main(["abrir"]) == 7
    assert len(chamadas) == 2
    assert vars(chamadas[0]) == vars(chamadas[1])
    assert chamadas[0].comando == "abrir"
