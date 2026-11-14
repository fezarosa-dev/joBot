"""Comando `jobot atualizar` (plano T85; ADR 0018; D31).

O sistema é falso (`_Sistema` responde a git, uv e systemctl e anota tudo) e o servidor no ar é
simulado com a trava da T43. Os testes de clone usam git de verdade numa pasta temporária, com
remoto local (`file://`), sem rede. `HOME` vai para a pasta temporária: `ligar` e `desligar`
mexem em `~/.config/systemd/user`.
"""

import argparse
import importlib
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from jobot.cli import COMANDOS
from jobot.sistema import atualizar as modulo
from jobot.sistema.atualizar import atualizar, tipo_de_instalacao
from jobot.sistema.instancia import Trava
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
