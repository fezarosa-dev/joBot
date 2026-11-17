"""Comando `jobot atualizar` (plano T85; ADR 0018; D31).

O sistema é falso (`_Sistema` responde a git, uv e systemctl e anota tudo) e o servidor no ar é
simulado com a trava da T43. Os testes de clone usam git de verdade numa pasta temporária, com
remoto local (`file://`), sem rede. `HOME` vai para a pasta temporária: `ligar` e `desligar`
mexem em `~/.config/systemd/user`.
"""

import argparse
import hashlib
import importlib
import io
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path

import httpx
import pytest

from jobot import __version__
from jobot.cli import COMANDOS, main
from jobot.sistema import atualizar as modulo
from jobot.sistema import casca, processo
from jobot.sistema.atualizar import atualizar, tipo_de_instalacao
from jobot.sistema.instancia import Trava
from jobot.sistema.pastas import pasta_do_playwright
from jobot.sistema.segundo_plano_linux import Resultado

PORTA = 47997


@pytest.fixture(autouse=True)
def _casa_falsa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "casa"))
    monkeypatch.delenv("CONTAINER_ID", raising=False)  # sem distrobox-host-exec na frente


def _clone_falso(raiz: Path) -> Path:
    (raiz / ".git").mkdir(parents=True)
    (raiz / "pyproject.toml").write_text("[project]\nname = 'jobot'\n")
    return raiz


class _Sistema:
    """Executor falso: git num clone atrás do remoto, uv e systemctl saudáveis."""

    def __init__(self, registro: list[str], *, plano_ligado: bool = False) -> None:
        self.registro = registro
        self.plano_ligado = plano_ligado
        self.comandos: list[tuple[str, ...]] = []
        self.falha_em: dict[str, Resultado] = {}

    def __call__(self, comando: Sequence[str]) -> Resultado:
        c = tuple(comando)
        self.comandos.append(c)
        nome = self._nome(c)
        self.registro.append(nome)
        if nome in self.falha_em:
            return self.falha_em[nome]
        if nome == "systemctl is-enabled":
            return Resultado(0 if self.plano_ligado else 1)
        if nome == "systemctl enable":
            self.plano_ligado = True
        if nome == "systemctl disable":
            self.plano_ligado = False
        if nome == "git rev-list":
            return Resultado(0, "0\t3\n")
        if nome == "git rev-parse":
            return Resultado(0, "a" * 40 + "\n")
        return Resultado(0)

    @staticmethod
    def _nome(c: tuple[str, ...]) -> str:
        if c[0] == "systemctl":
            return f"systemctl {c[2]}"
        if c[0] == "git":
            assert c[1] == "-C"
            return f"git {c[3]}"
        if c[:2] == ("uv", "tool"):
            return "uv tool"
        if c[0] == "uv":
            return "uv sync"
        raise AssertionError(f"comando inesperado: {c!r}")


def _rodando(dados: Path) -> Trava:
    trava = Trava(dados, PORTA)
    assert trava.pegar()
    return trava


def _falsos(
    registro: list[str], trava: Trava | None, codigo_parar: int = 0
) -> tuple[Callable[[Path], int], Callable[[], None]]:
    def parar(dados: Path) -> int:
        registro.append("parar")
        if codigo_parar == 0 and trava is not None:
            trava.soltar()
        return codigo_parar

    def subir() -> None:
        registro.append("subir")

    return parar, subir


def _resumo(registro: list[str]) -> list[str]:
    """Só os passos que mudam algo, na ordem."""
    passos = {
        "systemctl disable": "desligar",
        "systemctl enable": "ligar",
        "git pull": "pull",
        "uv sync": "sync",
        "uv tool": "upgrade",
        "parar": "parar",
        "subir": "subir",
    }
    return [passos[r] for r in registro if r in passos]


# --- tipo de instalação ------------------------------------------------------------------


def test_detecta_clone_git_uv_tool_e_desconhecida(tmp_path: Path) -> None:
    assert tipo_de_instalacao(_clone_falso(tmp_path / "clone")) == "clone_git"
    worktree = tmp_path / "worktree"  # num worktree o .git é arquivo
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /outro/lugar\n")
    (worktree / "pyproject.toml").write_text("")
    assert tipo_de_instalacao(worktree) == "clone_git"
    ferramenta = tmp_path / "ferramenta"
    ferramenta.mkdir()
    (ferramenta / "uv-receipt.toml").write_text("[tool]\n")
    assert tipo_de_instalacao(ferramenta) == "uv_tool"
    so_git = tmp_path / "so_git"  # .git sem pyproject: não é o clone do joBot
    (so_git / ".git").mkdir(parents=True)
    assert tipo_de_instalacao(so_git) == "desconhecida"
    assert tipo_de_instalacao(tmp_path / "vazia") == "desconhecida"


def test_recusa_instalacao_desconhecida(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registro: list[str] = []
    rodar = _Sistema(registro)
    parar, subir = _falsos(registro, None)
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    assert atualizar(rodar, tmp_path, parar=parar, subir=subir, raiz=vazia) == 1
    assert registro == []
    erro = capsys.readouterr().err
    assert "uv tool upgrade jobot" in erro
    assert "git pull --ff-only" in erro


# --- ordem de parar, atualizar e religar --------------------------------------------------


@pytest.mark.parametrize(
    ("plano_ligado", "servidor_rodando", "esperado"),
    [
        (True, False, ["desligar", "pull", "sync", "ligar"]),
        (True, True, ["desligar", "parar", "pull", "sync", "ligar"]),
        (False, True, ["parar", "pull", "sync", "subir"]),
        (False, False, ["pull", "sync"]),
    ],
    ids=["plano", "plano_e_servidor_que_nao_caiu", "so_servidor", "nada"],
)
def test_ordem_para_o_servidor_e_o_segundo_plano_antes_e_religa_depois(
    tmp_path: Path, plano_ligado: bool, servidor_rodando: bool, esperado: list[str]
) -> None:
    registro: list[str] = []
    rodar = _Sistema(registro, plano_ligado=plano_ligado)
    trava = _rodando(tmp_path) if servidor_rodando else None
    parar, subir = _falsos(registro, trava)
    try:
        codigo = atualizar(
            rodar, tmp_path, parar=parar, subir=subir, raiz=_clone_falso(tmp_path / "c")
        )
    finally:
        if trava is not None:
            trava.soltar()
    assert codigo == 0
    assert _resumo(registro) == esperado


def test_uv_tool_atualiza_com_uv_tool_upgrade(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registro: list[str] = []
    rodar = _Sistema(registro, plano_ligado=True)
    parar, subir = _falsos(registro, None)
    ferramenta = tmp_path / "ferramenta"
    ferramenta.mkdir()
    (ferramenta / "uv-receipt.toml").write_text("")
    assert atualizar(rodar, tmp_path, parar=parar, subir=subir, raiz=ferramenta) == 0
    assert _resumo(registro) == ["desligar", "upgrade", "ligar"]
    assert ("uv", "tool", "upgrade", "jobot") in rodar.comandos
    assert not any(c[0] == "git" for c in rodar.comandos)
    assert "https://github.com/fezarosa-dev/joBot/releases" in capsys.readouterr().out


def test_falha_na_atualizacao_religa_o_que_parou_e_sai_com_1(tmp_path: Path) -> None:
    registro: list[str] = []
    rodar = _Sistema(registro, plano_ligado=True)
    rodar.falha_em["uv sync"] = Resultado(1, erro="uv.lock desatualizado")
    parar, subir = _falsos(registro, None)
    codigo = atualizar(rodar, tmp_path, parar=parar, subir=subir, raiz=_clone_falso(tmp_path / "c"))
    assert codigo == 1
    assert _resumo(registro) == ["desligar", "pull", "sync", "ligar"]


def test_falha_na_atualizacao_religa_o_servidor_e_sai_com_1(tmp_path: Path) -> None:
    registro: list[str] = []
    rodar = _Sistema(registro)
    rodar.falha_em["git pull"] = Resultado(1, erro="não é fast-forward")
    trava = _rodando(tmp_path)
    parar, subir = _falsos(registro, trava)
    try:
        codigo = atualizar(
            rodar, tmp_path, parar=parar, subir=subir, raiz=_clone_falso(tmp_path / "c")
        )
    finally:
        trava.soltar()
    assert codigo == 1
    assert _resumo(registro) == ["parar", "pull", "subir"]


def test_servidor_que_nao_encerra_nao_atualiza_religa_e_sai_com_1(tmp_path: Path) -> None:
    registro: list[str] = []
    rodar = _Sistema(registro, plano_ligado=True)
    trava = _rodando(tmp_path)  # o desligar não derruba este servidor
    parar, subir = _falsos(registro, trava, codigo_parar=1)
    try:
        codigo = atualizar(
            rodar, tmp_path, parar=parar, subir=subir, raiz=_clone_falso(tmp_path / "c")
        )
    finally:
        trava.soltar()
    assert codigo == 1
    assert _resumo(registro) == ["desligar", "parar", "ligar"]


def test_ja_atualizado_nao_para_nada(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registro: list[str] = []
    rodar = _Sistema(registro, plano_ligado=True)
    rodar.falha_em["git rev-list"] = Resultado(0, "0\t0\n")
    parar, subir = _falsos(registro, None)
    codigo = atualizar(rodar, tmp_path, parar=parar, subir=subir, raiz=_clone_falso(tmp_path / "c"))
    assert codigo == 0
    assert _resumo(registro) == []
    assert "versão mais nova" in capsys.readouterr().out


def test_comandos_sao_listas_nunca_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registro: list[str] = []
    rodar = _Sistema(registro, plano_ligado=True)
    trava = _rodando(tmp_path)
    parar, subir = _falsos(registro, trava)
    try:
        assert (
            atualizar(rodar, tmp_path, parar=parar, subir=subir, raiz=_clone_falso(tmp_path / "c"))
            == 0
        )
    finally:
        trava.soltar()
    assert rodar.comandos
    for comando in rodar.comandos:
        assert all(isinstance(parte, str) for parte in comando)
        assert comando[0] in {"git", "uv", "systemctl"}
        assert comando[:2] != ("sh", "-c")
    # o executor real passa a lista ao subprocess, sem shell
    visto: list[Mapping[str, object]] = []

    def run_falso(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        visto.append({"args": args, **kwargs})
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run_falso)
    assert modulo.rodar_atualizacao(["git", "-C", "/x", "status"]).codigo == 0
    assert visto[0]["args"] == ["git", "-C", "/x", "status"]
    assert visto[0].get("shell", False) is False


def test_todo_comando_da_tabela_resolve() -> None:
    assert "atualizar" in COMANDOS
    assert COMANDOS["atualizar"] == "jobot.cli.atualizar"
    for nome, caminho in COMANDOS.items():
        assert callable(getattr(importlib.import_module(caminho), "executar", None)), nome


def test_executar_chama_atualizar_com_a_pasta_de_dados(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jobot.cli import atualizar as cli_atualizar

    chamadas: list[Path] = []

    def falso(rodar: object, dados: Path, **_: object) -> int:
        chamadas.append(dados)
        return 7

    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    monkeypatch.setattr(cli_atualizar, "atualizar", falso)
    assert cli_atualizar.executar(argparse.Namespace(comando="atualizar")) == 7
    assert chamadas == [tmp_path]


# --- git de verdade numa pasta temporária ------------------------------------------------


def _git(pasta: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "teste",
        "GIT_AUTHOR_EMAIL": "teste@exemplo.invalid",
        "GIT_COMMITTER_NAME": "teste",
        "GIT_COMMITTER_EMAIL": "teste@exemplo.invalid",
    }
    feito = subprocess.run(
        ["git", "-C", str(pasta), *args], env=env, capture_output=True, text=True, check=True
    )
    return feito.stdout


@pytest.fixture
def repos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Remoto com um commit e um clone dele; o remoto ganha depois uma linha no CHANGELOG."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    remoto = tmp_path / "remoto"
    remoto.mkdir()
    _git(remoto, "init", "-q", "-b", "main")
    (remoto / "pyproject.toml").write_text("[project]\nname = 'jobot'\n")
    (remoto / "CHANGELOG.md").write_text("# Changelog\n\n## [0.1.0]\n\n- Primeira versão.\n")
    _git(remoto, "add", ".")
    _git(remoto, "commit", "-q", "-m", "inicio")
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", remoto.as_uri(), str(clone)], check=True, capture_output=True
    )
    (remoto / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.2.0]\n\n- Conserto da Remotive.\n\n## [0.1.0]\n\n- Primeira versão.\n"
    )
    _git(remoto, "commit", "-q", "-am", "nova versao")
    return remoto, clone


def _rodar_git_de_verdade(registro: list[str]) -> Callable[[Sequence[str]], Resultado]:
    falso = _Sistema(registro)

    def rodar(comando: Sequence[str]) -> Resultado:
        if comando[0] == "git":
            registro.append(_Sistema._nome(tuple(comando)))
            return modulo.rodar_atualizacao(comando)
        return falso(comando)

    return rodar


def test_mostra_as_linhas_novas_do_changelog(
    tmp_path: Path, repos: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, clone = repos
    registro: list[str] = []
    parar, subir = _falsos(registro, None)
    codigo = atualizar(
        _rodar_git_de_verdade(registro), tmp_path, parar=parar, subir=subir, raiz=clone
    )
    assert codigo == 0, capsys.readouterr().err
    assert "Conserto da Remotive" in (clone / "CHANGELOG.md").read_text()  # puxou
    saida = capsys.readouterr().out
    assert "- Conserto da Remotive." in saida
    assert "## [0.2.0]" in saida
    assert "Primeira versão" not in saida  # linha que já existia não é novidade
    assert "+++" not in saida


def test_recusa_com_mudanca_local_antes_de_tocar_em_qualquer_coisa(
    tmp_path: Path, repos: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, clone = repos
    (clone / "CHANGELOG.md").write_text("mexido à mão\n")
    registro: list[str] = []
    parar, subir = _falsos(registro, None)
    codigo = atualizar(
        _rodar_git_de_verdade(registro), tmp_path, parar=parar, subir=subir, raiz=clone
    )
    assert codigo == 1
    assert registro == ["git status"]  # nem fetch, nem systemctl, nem parar
    assert (clone / "CHANGELOG.md").read_text() == "mexido à mão\n"
    assert "mudanças locais" in capsys.readouterr().err


def test_recusa_branch_divergente(
    tmp_path: Path, repos: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, clone = repos
    (clone / "LOCAL.md").write_text("commit só daqui\n")
    _git(clone, "add", "LOCAL.md")
    _git(clone, "commit", "-q", "-m", "local")
    antes = _git(clone, "rev-parse", "HEAD")
    registro: list[str] = []
    parar, subir = _falsos(registro, None)
    codigo = atualizar(
        _rodar_git_de_verdade(registro), tmp_path, parar=parar, subir=subir, raiz=clone
    )
    assert codigo == 1
    assert _resumo(registro) == []  # nada parado, nada puxado
    assert not any(r.startswith("systemctl") for r in registro)
    assert _git(clone, "rev-parse", "HEAD") == antes
    assert "divergiu" in capsys.readouterr().err


def test_desligar_recusado_nao_repete_a_saida_do_systemctl_no_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # sem nenhum handler (como no terminal), o logging imprimiria o aviso cru no stderr (T159)
    monkeypatch.setattr(logging.getLogger("jobot"), "handlers", [])
    monkeypatch.setattr(logging.root, "handlers", [])
    servico = tmp_path / "casa" / ".config" / "systemd" / "user" / "jobot.service"
    servico.parent.mkdir(parents=True)
    servico.write_text("[Service]\n")
    registro: list[str] = []
    rodar = _Sistema(registro, plano_ligado=True)
    rodar.falha_em["systemctl disable"] = Resultado(1, erro="Failed to connect to bus")
    parar, subir = _falsos(registro, None)
    codigo = atualizar(rodar, tmp_path, parar=parar, subir=subir, raiz=_clone_falso(tmp_path / "c"))
    assert codigo == 1
    assert capsys.readouterr().err.count("Failed to connect to bus") == 1


# --- captura de exemplos com login: trava presa sem porta (T220) ---


def test_atualizar_com_captura_recusa_e_nao_sobe_servidor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    trava = Trava(tmp_path, 0)  # o capturar_logado.py segura a trava sem porta
    assert trava.pegar()
    registro: list[str] = []
    rodar = _Sistema(registro)
    parar, subir = _falsos(registro, None)
    try:
        codigo = atualizar(
            rodar, tmp_path, parar=parar, subir=subir, raiz=_clone_falso(tmp_path / "clone")
        )
    finally:
        trava.soltar()
    assert codigo == 1
    assert registro == []  # nem parar, nem subir, nem git ou systemctl
    assert (
        "Uma captura de exemplos com login está em andamento. "
        "Encerre-a no terminal dela e tente de novo."
    ) in capsys.readouterr().err


# --- canal casca (T331; desenho 6.3; D174.3, D174.8, D174.13 e D174.14) -------------------

VERSAO = "9.9.9"
ALVO = casca.alvo_atual() or "x86_64-unknown-linux-gnu"
PACOTE = f"jobot-atualizacao-{VERSAO}-{ALVO}.zip"
CHROMIUM = f"chromium-{ALVO}.tar.gz"
TAG = f"https://github.com/fezarosa-dev/joBot/releases/download/v{VERSAO}"
SOMAS = "https://github.com/fezarosa-dev/joBot/releases/latest/download/SHA256SUMS"
PYTHON_TAR = "python/cpython-3.14.9-install_only.tar.gz"


def _sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _tar(arquivos: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for nome, conteudo in arquivos.items():
            info = tarfile.TarInfo(nome)
            info.size = len(conteudo)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(conteudo))
    return buffer.getvalue()


def _manifesto(arquivos: Mapping[str, bytes], **trocar: str) -> dict[str, object]:
    itens = [
        {"nome": n, "tamanho": len(c), "sha256": trocar.get(n, _sha(c))}
        for n, c in arquivos.items()
    ]
    return {"versao": VERSAO, "arquivos": itens}


CHROMIUM_NOVO = _tar({"chrome-linux/chrome": b"chrome novo"})


def _pacote(
    *, trocar: Mapping[str, str] | None = None, extra: Mapping[str, bytes] | None = None
) -> bytes:
    """O `.zip` da release: o manifesto lista o Chromium sem ele estar dentro (D174.8)."""
    dentro = {
        "restricoes.txt": (
            f"dep==1 --hash=sha256:{'0' * 64}\n"
            f"jobot=={VERSAO} --hash=sha256:{_sha(b'wheel do jobot')}\n"
        ).encode(),
        f"wheels/jobot-{VERSAO}-py3-none-any.whl": b"wheel do jobot",
        "wheels/dep-1-py3-none-any.whl": b"wheel da dep",
        PYTHON_TAR: _tar({"python/bin/python3": b"#!python"}),
    }
    manifesto = _manifesto({**dentro, CHROMIUM: CHROMIUM_NOVO}, **(trocar or {}))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifesto.json", json.dumps(manifesto))
        for nome, conteudo in {**dentro, **(extra or {})}.items():
            zf.writestr(nome, conteudo)
    return buffer.getvalue()


class _Release:
    """O GitHub falso por `httpx.MockTransport`: só as URLs da release, nada de rede."""

    def __init__(self, pacote: bytes, *, versao: str = VERSAO, sha: str | None = None) -> None:
        self.pacote = pacote
        self.urls: dict[str, bytes] = {
            SOMAS: f"{sha or _sha(pacote)}  jobot-atualizacao-{versao}-{ALVO}.zip\n".encode(),
            f"{TAG}/{PACOTE}": pacote,
            f"{TAG}/{CHROMIUM}": CHROMIUM_NOVO,
        }
        self.pedidos: list[str] = []
        self.cliente = httpx.Client(transport=httpx.MockTransport(self._responder))

    def _responder(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        self.pedidos.append(url)
        if url in self.urls:
            return httpx.Response(200, content=self.urls[url])
        return httpx.Response(404)


class _Casca:
    """Executor falso do canal casca: uv, o jobot do venv novo e o systemctl."""

    def __init__(self, registro: list[str], *, plano_ligado: bool = False) -> None:
        self.registro = registro
        self.plano_ligado = plano_ligado
        self.comandos: list[tuple[str, ...]] = []
        self.falha_em: dict[str, Resultado] = {}
        self.versao_nova = VERSAO

    def __call__(self, comando: Sequence[str]) -> Resultado:
        c = tuple(comando)
        self.comandos.append(c)
        if c[0] == "systemctl":
            nome = f"systemctl {c[2]}"
        else:
            nome = f"{Path(c[0]).stem} {c[1]}"
        self.registro.append(nome)
        if nome in self.falha_em:
            return self.falha_em[nome]
        if nome == "systemctl is-enabled":
            return Resultado(0 if self.plano_ligado else 1)
        if nome == "systemctl disable":
            self.plano_ligado = False
        if nome == "uv venv":
            venv = Path(c[-1])
            (venv / "bin").mkdir(parents=True)
            python = Path(c[c.index("--python") + 1])
            (venv / "pyvenv.cfg").write_text(f"home = {python.parent}\n")
        if nome == "jobot --version":
            return Resultado(0, f"jobot {self.versao_nova}\n")
        return Resultado(0)


def _venv(pasta: Path, versao: str, python: str) -> Path:
    venv = pasta / "venvs" / f"venv-{versao}"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text(f"home = {pasta / 'python' / python / 'python' / 'bin'}\n")
    (pasta / "python" / python / "python" / "bin").mkdir(parents=True, exist_ok=True)
    return venv


def _instalada(dados: Path, *, chromium_sha: str = "a" * 64) -> Path:
    """Instalação da casca na 0.3.0, com a 0.2.0 de anterior e a 0.1.0 que sobrou."""
    pasta = dados / "app"
    atual = _venv(pasta, "0.3.0", "cpython-velho")
    anterior = _venv(pasta, "0.2.0", "cpython-mais-velho")
    _venv(pasta, "0.1.0", "cpython-mais-velho")
    (pasta / "python" / "cpython-sem-uso").mkdir()
    for versao in ("0.1.0", "0.2.0", "0.3.0"):
        itens = [{"nome": CHROMIUM, "tamanho": 1, "sha256": chromium_sha}]
        (pasta / f"manifesto-{versao}.json").write_text(
            json.dumps({"versao": versao, "arquivos": itens})
        )
    casca.gravar_instalacao(
        dados,
        {
            "canal": "casca",
            "pasta": str(pasta),
            "uv": str(pasta / "bin" / "uv"),
            "venv": str(atual),
            "anterior": str(anterior),
            "manifesto": str(pasta / "manifesto-0.3.0.json"),
            "manifesto_anterior": str(pasta / "manifesto-0.2.0.json"),
        },
    )
    return pasta


@pytest.fixture
def sem_playwright(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)  # no Windows, a pasta vem da casa falsa


def _no_venv(venv: Path, nome: str) -> Path:
    """O executável do venv, escrito à mão para o teste não usar o `casca.no_venv`."""
    return venv / "Scripts" / f"{nome}.exe" if sys.platform == "win32" else venv / "bin" / nome


def _com_chromium(tmp_path: Path) -> None:
    (pasta_do_playwright(os.environ) / "chromium-1187").mkdir(parents=True)


def _atualizar_casca(
    dados: Path, release: _Release, rodar: _Casca, registro: list[str], trava: Trava | None = None
) -> int:
    parar, subir = _falsos(registro, trava)
    return atualizar(
        rodar,
        dados,
        parar=parar,
        subir=subir,
        subir_em=lambda python: registro.append(f"subir_em {python}"),
        cliente=release.cliente,
        raiz=dados / "nao_e_clone",
    )


def test_instalacao_json_da_tipo_casca(tmp_path: Path) -> None:
    raiz = _clone_falso(tmp_path / "clone")
    assert tipo_de_instalacao(raiz, tmp_path) == "clone_git"
    _instalada(tmp_path)
    assert tipo_de_instalacao(raiz, tmp_path) == "casca"


def test_casca_monta_o_venv_novo_prova_e_so_entao_troca(
    tmp_path: Path, sem_playwright: None, capsys: pytest.CaptureFixture[str]
) -> None:
    pasta = _instalada(tmp_path)
    registro: list[str] = []
    rodar = _Casca(registro, plano_ligado=True)
    release = _Release(_pacote())
    trava = _rodando(tmp_path)
    try:
        assert _atualizar_casca(tmp_path, release, rodar, registro, trava) == 0
    finally:
        trava.soltar()
    novo = pasta / "venvs" / f"venv-{VERSAO}"
    # a prova vem antes de parar qualquer coisa; o segundo plano é refeito pelo joBot novo
    passos = [r for r in registro if r.split()[0] in ("uv", "jobot", "parar") or "disable" in r]
    assert passos == [
        "uv venv", "uv pip", "jobot --version", "systemctl disable", "parar", "jobot segundo-plano",
    ]  # fmt: skip
    assert release.pedidos == [SOMAS, f"{TAG}/{PACOTE}"]  # sem Chromium instalado, não baixa
    uv = str(pasta / "bin" / "uv")
    venv_cmd = next(c for c in rodar.comandos if c[:2] == (uv, "venv"))
    extraido = pasta / "python" / "cpython-3.14.9-install_only" / "python"
    windows = sys.platform == "win32"
    python_novo = extraido / "python.exe" if windows else extraido / "bin" / "python3"
    assert venv_cmd[venv_cmd.index("--python") + 1] == str(python_novo)
    assert "--offline" in venv_cmd and venv_cmd[-1] == str(novo)
    pip = next(c for c in rodar.comandos if c[:2] == (uv, "pip"))
    for opcao in ("--offline", "--no-index", "--require-hashes"):
        assert opcao in pip
    assert pip[pip.index("--python") + 1] == str(_no_venv(novo, "python"))
    assert Path(pip[pip.index("--find-links") + 1]).name == "wheels"
    # no --require-hashes todo requisito precisa de hash: o joBot vem pelo restricoes.txt
    assert pip[-2:][0] == "-r" and Path(pip[-1]).name == "restricoes.txt"
    assert not any(a.endswith(".whl") for a in pip)
    assert (str(_no_venv(novo, "jobot")), "--version") in rodar.comandos
    assert (str(_no_venv(novo, "jobot")), "segundo-plano", "ligar") in rodar.comandos
    instalacao = casca.ler_instalacao(tmp_path)
    assert instalacao["venv"] == str(novo)
    assert instalacao["anterior"] == str(pasta / "venvs" / "venv-0.3.0")
    assert instalacao["manifesto"] == str(pasta / f"manifesto-{VERSAO}.json")
    assert instalacao["manifesto_anterior"] == str(pasta / "manifesto-0.3.0.json")
    assert instalacao["user_version"] == 0 and instalacao["navegador_desatualizado"] is False
    gravado = json.loads((pasta / f"manifesto-{VERSAO}.json").read_text())
    assert CHROMIUM in [i["nome"] for i in gravado["arquivos"]]  # listado sem estar no pacote
    # fica o atual e o anterior; vão os mais velhos, o Python sem uso e o que sobrou do download
    assert sorted(p.name for p in (pasta / "venvs").iterdir()) == ["venv-0.3.0", f"venv-{VERSAO}"]
    assert sorted(p.name for p in (pasta / "python").iterdir()) == [
        "cpython-3.14.9-install_only", "cpython-velho",
    ]  # fmt: skip
    assert sorted(p.name for p in pasta.glob("manifesto-*")) == [
        "manifesto-0.3.0.json", f"manifesto-{VERSAO}.json",
    ]  # fmt: skip
    assert not list(pasta.glob("baixando-*"))
    assert VERSAO in capsys.readouterr().out


def test_casca_sem_plano_sobe_o_servidor_do_venv_novo(tmp_path: Path, sem_playwright: None) -> None:
    pasta = _instalada(tmp_path)
    registro: list[str] = []
    trava = _rodando(tmp_path)
    try:
        assert (
            _atualizar_casca(tmp_path, _Release(_pacote()), _Casca(registro), registro, trava) == 0
        )
    finally:
        trava.soltar()
    assert registro[-1] == f"subir_em {_no_venv(pasta / 'venvs' / f'venv-{VERSAO}', 'python')}"
    assert "subir" not in registro and "jobot segundo-plano" not in registro


def _intacta(tmp_path: Path, pasta: Path, antes: bytes, registro: list[str]) -> None:
    assert (tmp_path / casca.ARQUIVO).read_bytes() == antes
    assert not (pasta / "venvs" / f"venv-{VERSAO}").exists()
    assert not (pasta / "python" / "cpython-3.14.9-install_only").exists()
    assert not list(pasta.glob("baixando-*")) and not (pasta / f"manifesto-{VERSAO}.json").exists()
    assert "parar" not in registro and "systemctl disable" not in registro
    assert sorted(p.name for p in (pasta / "venvs").iterdir()) == [
        "venv-0.1.0",
        "venv-0.2.0",
        "venv-0.3.0",
    ]


@pytest.mark.parametrize(
    ("release", "mensagem"),
    [
        (lambda: _Release(_pacote(), sha="b" * 64), "SHA256SUMS"),
        (
            lambda: _Release(_pacote(trocar={"wheels/dep-1-py3-none-any.whl": "c" * 64})),
            "wheels/dep",
        ),
        (lambda: _Release(_pacote(extra={"intruso.py": b"x"})), "intruso.py"),
    ],
    ids=["pacote", "arquivo_de_dentro", "fora_do_manifesto"],
)
def test_casca_que_nao_confere_nao_muda_nada(
    tmp_path: Path,
    sem_playwright: None,
    capsys: pytest.CaptureFixture[str],
    release: Callable[[], _Release],
    mensagem: str,
) -> None:
    pasta = _instalada(tmp_path)
    antes = (tmp_path / casca.ARQUIVO).read_bytes()
    registro: list[str] = []
    rodar = _Casca(registro)
    assert _atualizar_casca(tmp_path, release(), rodar, registro) == 1
    _intacta(tmp_path, pasta, antes, registro)
    assert not any(r.startswith("uv ") for r in registro)
    assert mensagem in capsys.readouterr().err


@pytest.mark.parametrize("falha", ["uv pip", "jobot --version", "versao_errada"])
def test_casca_prova_que_falha_apaga_o_venv_novo(
    tmp_path: Path, sem_playwright: None, capsys: pytest.CaptureFixture[str], falha: str
) -> None:
    pasta = _instalada(tmp_path)
    antes = (tmp_path / casca.ARQUIVO).read_bytes()
    registro: list[str] = []
    rodar = _Casca(registro)
    if falha == "versao_errada":
        rodar.versao_nova = "0.3.0"
    else:
        rodar.falha_em[falha] = Resultado(1, erro="quebrou")
    assert _atualizar_casca(tmp_path, _Release(_pacote()), rodar, registro) == 1
    assert "uv venv" in registro  # chegou a montar
    _intacta(tmp_path, pasta, antes, registro)
    assert "nada mudou" in capsys.readouterr().err.lower()


def test_casca_ja_na_mais_nova_nao_baixa_o_pacote(tmp_path: Path, sem_playwright: None) -> None:
    pasta = _instalada(tmp_path)
    antes = (tmp_path / casca.ARQUIVO).read_bytes()
    registro: list[str] = []
    atual = re.match(r"[0-9]+\.[0-9]+\.[0-9]+", __version__)
    assert atual is not None
    release = _Release(_pacote(), versao=atual[0])
    assert _atualizar_casca(tmp_path, release, _Casca(registro), registro) == 0
    assert release.pedidos == [SOMAS]
    _intacta(tmp_path, pasta, antes, registro)


def test_casca_baixa_o_chromium_novo_antes_da_troca(tmp_path: Path, sem_playwright: None) -> None:
    pasta = _instalada(tmp_path)
    _com_chromium(tmp_path)
    registro: list[str] = []
    rodar = _Casca(registro, plano_ligado=True)
    release = _Release(_pacote())
    assert _atualizar_casca(tmp_path, release, rodar, registro) == 0
    assert release.pedidos == [SOMAS, f"{TAG}/{PACOTE}", f"{TAG}/{CHROMIUM}"]
    baixar = next(c for c in rodar.comandos if c[1:4] == ("ferramentas", "baixar", "navegador"))
    assert baixar[0] == str(_no_venv(pasta / "venvs" / f"venv-{VERSAO}", "jobot"))
    assert Path(baixar[baixar.index("--arquivo") + 1]).name == CHROMIUM
    assert baixar[baixar.index("--sha256") + 1] == _sha(CHROMIUM_NOVO)
    # depois da prova do venv novo e antes de parar qualquer coisa
    assert registro.index("jobot --version") < registro.index("jobot ferramentas")
    assert registro.index("jobot ferramentas") < registro.index("systemctl disable")
    assert casca.ler_instalacao(tmp_path)["navegador_desatualizado"] is False


def test_casca_com_o_mesmo_chromium_nao_baixa(tmp_path: Path, sem_playwright: None) -> None:
    _instalada(tmp_path, chromium_sha=_sha(CHROMIUM_NOVO))
    _com_chromium(tmp_path)
    registro: list[str] = []
    release = _Release(_pacote())
    assert _atualizar_casca(tmp_path, release, _Casca(registro), registro) == 0
    assert release.pedidos == [SOMAS, f"{TAG}/{PACOTE}"]
    assert "jobot ferramentas" not in registro


@pytest.mark.parametrize("como", ["download", "instalar"])
def test_casca_chromium_que_falha_troca_e_marca_desatualizado(
    tmp_path: Path, sem_playwright: None, como: str
) -> None:
    pasta = _instalada(tmp_path)
    _com_chromium(tmp_path)
    registro: list[str] = []
    rodar = _Casca(registro)
    release = _Release(_pacote())
    if como == "download":
        del release.urls[f"{TAG}/{CHROMIUM}"]
    else:
        rodar.falha_em["jobot ferramentas"] = Resultado(1, erro="não extraiu")
    assert _atualizar_casca(tmp_path, release, rodar, registro) == 0
    instalacao = casca.ler_instalacao(tmp_path)
    assert instalacao["venv"] == str(pasta / "venvs" / f"venv-{VERSAO}")
    assert instalacao["navegador_desatualizado"] is True
    assert casca.navegador_desatualizado(tmp_path)


def _banco(dados: Path, versao: int) -> None:
    con = sqlite3.connect(dados / "jobot.db")
    try:
        con.execute(f"PRAGMA user_version = {versao:d}")
    finally:
        con.close()


def test_troca_grava_o_user_version_e_voltar_troca_o_ponteiro(
    tmp_path: Path, sem_playwright: None
) -> None:
    pasta = _instalada(tmp_path)
    _banco(tmp_path, 41)
    registro: list[str] = []
    assert _atualizar_casca(tmp_path, _Release(_pacote()), _Casca(registro), registro) == 0
    assert casca.ler_instalacao(tmp_path)["user_version"] == 41
    casca.voltar_a_anterior(tmp_path)
    instalacao = casca.ler_instalacao(tmp_path)
    assert instalacao["venv"] == str(pasta / "venvs" / "venv-0.3.0")
    assert instalacao["anterior"] == str(pasta / "venvs" / f"venv-{VERSAO}")
    assert instalacao["manifesto"] == str(pasta / "manifesto-0.3.0.json")
    assert instalacao["manifesto_anterior"] == str(pasta / f"manifesto-{VERSAO}.json")


def test_voltar_com_o_banco_migrado_recusa_e_nada_muda(
    tmp_path: Path, sem_playwright: None
) -> None:
    _instalada(tmp_path)
    _banco(tmp_path, 41)
    registro: list[str] = []
    assert _atualizar_casca(tmp_path, _Release(_pacote()), _Casca(registro), registro) == 0
    _banco(tmp_path, 42)  # o joBot novo migrou ao abrir
    antes = (tmp_path / casca.ARQUIVO).read_bytes()
    with pytest.raises(casca.Falha, match="41 virou 42"):
        casca.voltar_a_anterior(tmp_path)
    assert (tmp_path / casca.ARQUIVO).read_bytes() == antes


def test_voltar_sem_anterior_recusa(tmp_path: Path) -> None:
    _instalada(tmp_path)
    instalacao = casca.ler_instalacao(tmp_path)
    instalacao["anterior"] = None
    casca.gravar_instalacao(tmp_path, instalacao)
    with pytest.raises(casca.Falha, match="Não há versão anterior"):
        casca.voltar_a_anterior(tmp_path)


def test_casca_banco_danificado_na_troca_religa_e_nada_muda(
    tmp_path: Path, sem_playwright: None, capsys: pytest.CaptureFixture[str]
) -> None:
    pasta = _instalada(tmp_path)
    (tmp_path / "jobot.db").write_bytes(b"nao e sqlite" * 400)
    antes = (tmp_path / casca.ARQUIVO).read_bytes()
    registro: list[str] = []
    rodar = _Casca(registro, plano_ligado=True)
    assert _atualizar_casca(tmp_path, _Release(_pacote()), rodar, registro) == 1
    assert (tmp_path / casca.ARQUIVO).read_bytes() == antes
    assert not (pasta / f"manifesto-{VERSAO}.json").exists()
    assert not (pasta / "venvs" / f"venv-{VERSAO}").exists()
    # religa a versão de antes, pelo systemctl, não pelo joBot novo
    assert registro.index("systemctl disable") < registro.index("systemctl enable")
    assert "jobot segundo-plano" not in registro
    assert "nada mudou" in capsys.readouterr().err.lower()


def test_casca_erro_de_disco_no_download_nao_muda_nada(
    tmp_path: Path, sem_playwright: None, capsys: pytest.CaptureFixture[str]
) -> None:
    pasta = _instalada(tmp_path)
    antes = (tmp_path / casca.ARQUIVO).read_bytes()
    release = _Release(_pacote())

    def cheio() -> Iterator[bytes]:
        yield b"comeco"
        raise OSError(28, "No space left on device")

    def responder(pedido: httpx.Request) -> httpx.Response:
        if str(pedido.url) == f"{TAG}/{PACOTE}":
            return httpx.Response(200, content=cheio())
        return release._responder(pedido)

    release.cliente = httpx.Client(transport=httpx.MockTransport(responder))
    registro: list[str] = []
    assert _atualizar_casca(tmp_path, release, _Casca(registro), registro) == 1
    _intacta(tmp_path, pasta, antes, registro)
    erro = capsys.readouterr().err
    assert "No space left" in erro and "nada mudou" in erro.lower()


def test_casca_pyvenv_ilegivel_nao_apaga_python(tmp_path: Path, sem_playwright: None) -> None:
    pasta = _instalada(tmp_path)
    (pasta / "venvs" / "venv-0.3.0" / "pyvenv.cfg").unlink()  # na dúvida, fica (D174.18)
    registro: list[str] = []
    assert _atualizar_casca(tmp_path, _Release(_pacote()), _Casca(registro), registro) == 0
    assert (pasta / "python" / "cpython-sem-uso").is_dir()


def test_casca_manifesto_antigo_ilegivel_baixa_o_chromium(
    tmp_path: Path, sem_playwright: None
) -> None:
    pasta = _instalada(tmp_path, chromium_sha=_sha(CHROMIUM_NOVO))  # o mesmo, se lido
    (pasta / "manifesto-0.3.0.json").write_text("{lixo")  # ilegível conta como diferente (D174.20)
    _com_chromium(tmp_path)
    registro: list[str] = []
    release = _Release(_pacote())
    assert _atualizar_casca(tmp_path, release, _Casca(registro), registro) == 0
    assert f"{TAG}/{CHROMIUM}" in release.pedidos and "jobot ferramentas" in registro


def test_jobot_version_diz_a_versao(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out == f"jobot {__version__}\n"


@pytest.mark.parametrize(
    ("plataforma", "env", "esperado"),
    [
        ("linux", {"HOME": "/c"}, "/c/.cache/ms-playwright"),
        ("linux", {"HOME": "/c", "XDG_CACHE_HOME": "/x"}, "/x/ms-playwright"),
        ("linux", {"HOME": "/c", "PLAYWRIGHT_BROWSERS_PATH": "/p"}, "/p"),
        ("linux", {"HOME": "/c", "PLAYWRIGHT_BROWSERS_PATH": "0"}, "/c/.cache/ms-playwright"),
        ("darwin", {"HOME": "/c"}, "/c/Library/Caches/ms-playwright"),
        ("win32", {"HOME": "/c", "LOCALAPPDATA": "/l"}, "/l/ms-playwright"),
    ],
)
def test_pasta_do_playwright(plataforma: str, env: dict[str, str], esperado: str) -> None:
    assert pasta_do_playwright(env, plataforma) == Path(esperado)


def test_lancar_atualizacao_roda_destacado_com_a_pasta_e_o_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T332: o painel dispara o `jobot atualizar` num grupo próprio, porque ele para o servidor
    que o chamou; a saída vai para `logs/atualizar.log` (0600), que a tela cita se demorar."""
    chamadas: list[tuple[list[str], dict[str, object]]] = []

    def popen(comando: list[str], **kwargs: object) -> str:
        arquivo = kwargs["stdout"]
        assert hasattr(arquivo, "write")
        arquivo.write(b"saida\n")
        chamadas.append((comando, kwargs))
        return "processo"

    monkeypatch.setattr(subprocess, "Popen", popen)
    feito: object = modulo.lancar_atualizacao(
        tmp_path, {"PATH": "/usr/bin", "JOBOT_DADOS": "/outra"}, cgroup=tmp_path / "sem-cgroup"
    )
    assert feito == "processo"
    [(comando, kwargs)] = chamadas
    assert comando == [sys.executable, "-m", "jobot", "atualizar"]
    assert kwargs["env"] == {"PATH": "/usr/bin", "JOBOT_DADOS": str(tmp_path)}
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.STDOUT
    assert {k: kwargs[k] for k in processo.destacar()} == processo.destacar()
    log = tmp_path / "logs" / "atualizar.log"
    assert log.read_bytes() == b"saida\n"
    if sys.platform != "win32":  # modo do POSIX
        assert log.stat().st_mode & 0o777 == 0o600
    # a segunda vez acrescenta, não apaga o que a primeira deixou
    modulo.lancar_atualizacao(tmp_path, {}, cgroup=tmp_path / "sem-cgroup")
    assert log.read_bytes() == b"saida\nsaida\n"


@pytest.mark.parametrize(
    ("linha", "sob_o_servico"),
    [
        ("0::/user.slice/user-1000.slice/user@1000.service/app.slice/jobot.service\n", True),
        ("0::/user.slice/user-1000.slice/session-2.scope\n", False),
        ("0::/\n", False),  # na distrobox: o cgroup do contêiner; o `sair` para o servidor
    ],
)
def test_lancar_atualizacao_sai_do_cgroup_do_servico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, linha: str, sob_o_servico: bool
) -> None:
    """Revisão da T332: sob o jobot.service, o `systemctl --user disable --now` do `desligar()`
    mata o cgroup inteiro, e o `jobot atualizar` filho do servidor morreria junto. Sob o serviço,
    ele vai num scope próprio do systemd-run; fora dele, o comando fica como está."""
    comandos: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda comando, **_: comandos.append(comando))
    cgroup = tmp_path / "cgroup"
    cgroup.write_text(linha)
    modulo.lancar_atualizacao(tmp_path, {}, cgroup=cgroup)
    jobot = [sys.executable, "-m", "jobot", "atualizar"]
    prefixo = ["systemd-run", "--user", "--scope", "--collect", "--quiet", "--unit"]
    if sob_o_servico:
        assert comandos == [[*prefixo, "jobot-atualizar", "--", *jobot]]
    else:
        assert comandos == [jobot]
