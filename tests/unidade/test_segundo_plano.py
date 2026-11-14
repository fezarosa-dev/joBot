import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from jobot.sistema import segundo_plano_linux as sp
from jobot.sistema.segundo_plano_linux import (
    Caso,
    Estado,
    Recusa,
    Resultado,
    criar_atalho,
    desligar,
    executar,
    ligar,
    pode_ligar,
    rodar_comando,
    status,
    texto_do_atalho,
    texto_do_servico,
)

ENTER = "/usr/bin/distrobox-enter"
PY = "/opt/jobot/.venv/bin/python"
DIRETO = Caso(python=PY)
DISTROBOX = Caso(python=PY, container="fedora-dev", distrobox_enter=ENTER)
HOST = ("distrobox-host-exec",)


class Sistema:
    """Executor falso: guarda cada comando e responde como o sistema de fora responderia."""

    def __init__(
        self,
        home: Path,
        *,
        host_exec: bool = True,
        systemd: bool = True,
        home_do_host: Path | None = None,
        habilitado: bool = True,
        ativo: bool = True,
    ) -> None:
        self.chamadas: list[tuple[str, ...]] = []
        self.host_exec = host_exec
        self.systemd = systemd
        self.home_do_host = home_do_host or home
        self.habilitado = habilitado
        self.ativo = ativo

    def __call__(self, comando: Sequence[str]) -> Resultado:
        completo = tuple(comando)
        self.chamadas.append(completo)
        if completo[:1] == HOST:
            if not self.host_exec:
                return Resultado(127)
            completo = completo[1:]
        if completo[:2] == ("sh", "-c"):
            if "distrobox-enter" in completo[2]:
                return Resultado(0, ENTER + "\n")
            return Resultado(0, str(self.home_do_host))
        if completo[:1] == ("systemctl",):
            if "show-environment" in completo:
                return Resultado(0 if self.systemd else 1)
            if "is-enabled" in completo:
                return Resultado(0 if self.habilitado else 1)
            if "is-active" in completo:
                return Resultado(0 if self.ativo else 3)
        return Resultado(0)

    def systemctl(self) -> list[tuple[str, ...]]:
        return [c for c in self.chamadas if "systemctl" in c and "show-environment" not in c]


def _env(home: Path, container: str | None = None) -> dict[str, str]:
    return {"HOME": str(home)} | ({"CONTAINER_ID": container} if container else {})


def _servico(home: Path) -> Path:
    return home / ".config" / "systemd" / "user" / "jobot.service"


def _atalho(home: Path) -> Path:
    return home / ".local" / "share" / "applications" / "jobot.desktop"


def test_servico_direto() -> None:
    linhas = texto_do_servico(DIRETO).splitlines()
    assert f"ExecStart={PY} -m jobot serve" in linhas
    assert "Restart=on-failure" in linhas
    assert "WantedBy=default.target" in linhas
    assert not any(linha.startswith("ExecStop=") for linha in linhas)


def test_servico_no_distrobox() -> None:
    linhas = texto_do_servico(DISTROBOX).splitlines()
    assert f"ExecStart={ENTER} -n fedora-dev --no-tty -- {PY} -m jobot serve" in linhas
    assert f"ExecStop={ENTER} -n fedora-dev --no-tty -- {PY} -m jobot sair" in linhas
    assert "Restart=on-failure" in linhas
    assert "WantedBy=default.target" in linhas


def test_atalho_nos_dois_casos() -> None:
    direto = texto_do_atalho(DIRETO).splitlines()
    assert direto[0] == "[Desktop Entry]"
    assert f"Exec={PY} -m jobot abrir" in direto
    assert "Name=joBot" in direto
    assert "Type=Application" in direto
    assert "Terminal=false" in direto
    dentro = texto_do_atalho(DISTROBOX).splitlines()
    assert f"Exec={ENTER} -n fedora-dev -- {PY} -m jobot abrir" in dentro


def test_caminho_com_espaco_sai_entre_aspas() -> None:
    caso = Caso(python="/home/a b/.venv/bin/python", container="c", distrobox_enter="/o p/enter")
    servico = texto_do_servico(caso).splitlines()
    assert (
        'ExecStart="/o p/enter" -n c --no-tty -- "/home/a b/.venv/bin/python" -m jobot serve'
        in servico
    )
    assert (
        'ExecStop="/o p/enter" -n c --no-tty -- "/home/a b/.venv/bin/python" -m jobot sair'
        in servico
    )
    direto = texto_do_servico(Caso(python="/home/a b/py")).splitlines()
    assert 'ExecStart="/home/a b/py" -m jobot serve' in direto
    atalho = texto_do_atalho(caso).splitlines()
    assert 'Exec="/o p/enter" -n c -- "/home/a b/.venv/bin/python" -m jobot abrir' in atalho


def test_caracteres_especiais_sao_escapados() -> None:
    # systemd expande % e $ nas linhas Exec; o .desktop trata % como código de campo
    estranho = Caso(python='/a "b"/p%d/$x/py')
    assert 'ExecStart="/a \\"b\\"/p%%d/$$x/py" -m jobot serve' in texto_do_servico(estranho)
    assert 'Exec="/a \\\\"b\\\\"/p%%d/\\\\$x/py" -m jobot abrir' in texto_do_atalho(estranho)


def test_quebra_de_linha_no_caminho_nao_injeta_chave() -> None:
    ruim = Caso(python="/x\nExecStartPre=/bin/ruim")
    with pytest.raises(ValueError):
        texto_do_servico(ruim)
    with pytest.raises(ValueError):
        texto_do_atalho(ruim)


def test_servico_direto_liga_pelo_systemctl_do_proprio_sistema(tmp_path: Path) -> None:
    rodar = Sistema(tmp_path)
    ligar(rodar, env=_env(tmp_path))
    assert rodar.systemctl() == [
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable", "--now", "jobot.service"),
    ]
    assert f"ExecStart={sys.executable} -m jobot serve" in _servico(tmp_path).read_text("utf-8")
    assert _atalho(tmp_path).is_file()


def test_systemctl_passa_pelo_host_no_distrobox(tmp_path: Path) -> None:
    rodar = Sistema(tmp_path)
    ligar(rodar, env=_env(tmp_path, "fedora-dev"))
    assert rodar.systemctl() == [
        (*HOST, "systemctl", "--user", "daemon-reload"),
        (*HOST, "systemctl", "--user", "enable", "--now", "jobot.service"),
    ]
    # o caminho do distrobox-enter vem do sistema de fora, não é fixo
    texto = _servico(tmp_path).read_text("utf-8")
    assert f"ExecStart={ENTER} -n fedora-dev --no-tty -- {sys.executable} -m jobot serve" in texto
    assert f"ExecStop={ENTER} -n fedora-dev --no-tty -- {sys.executable} -m jobot sair" in texto
    assert f"Exec={ENTER} -n fedora-dev -- {sys.executable}" in _atalho(tmp_path).read_text("utf-8")


def test_desligar_desabilita_e_apaga_o_arquivo(tmp_path: Path) -> None:
    env = _env(tmp_path, "fedora-dev")
    rodar = Sistema(tmp_path)
    ligar(rodar, env=env)
    rodar.chamadas.clear()
    desligar(rodar, env=env)
    assert (*HOST, "systemctl", "--user", "disable", "--now", "jobot.service") in rodar.chamadas
    assert not _servico(tmp_path).exists()
    assert _atalho(tmp_path).is_file()  # o atalho não depende do segundo plano (DR-37)
    desligar(rodar, env=env)  # de novo, sem arquivo: não quebra


@pytest.mark.parametrize(
    ("falha", "chave"),
    [
        ({"host_exec": False}, "segundo_plano.sem_host_exec"),
        ({"systemd": False}, "segundo_plano.systemd_nao_responde"),
        ({"home_do_host": Path("/outra/casa")}, "segundo_plano.home_diferente"),
    ],
)
def test_recusa(tmp_path: Path, falha: dict[str, object], chave: str) -> None:
    env = _env(tmp_path, "fedora-dev")
    rodar = Sistema(tmp_path, **falha)  # type: ignore[arg-type]
    motivo = pode_ligar(env, rodar)
    assert motivo is not None
    assert motivo.chave == chave
    with pytest.raises(Recusa) as erro:
        ligar(rodar, env=env)
    assert erro.value.motivo.chave == chave
    assert not _servico(tmp_path).exists()
    assert not any("enable" in c for c in rodar.chamadas)


def test_recusa_systemd_fora_do_distrobox(tmp_path: Path) -> None:
    motivo = pode_ligar(_env(tmp_path), Sistema(tmp_path, systemd=False))
    assert motivo is not None
    assert motivo.chave == "segundo_plano.systemd_nao_responde"


def test_pode_ligar_quando_tudo_responde(tmp_path: Path) -> None:
    assert pode_ligar(_env(tmp_path), Sistema(tmp_path)) is None
    assert pode_ligar(_env(tmp_path, "fedora-dev"), Sistema(tmp_path)) is None


def test_home_com_link_simbolico_e_a_mesma(tmp_path: Path) -> None:
    # Silverblue: /home é link para /var/home; o container pode ver um ou outro
    real = tmp_path / "var" / "home" / "ana"
    real.mkdir(parents=True)
    atalho = tmp_path / "home"
    atalho.symlink_to(tmp_path / "var" / "home")
    env = _env(atalho / "ana", "fedora-dev")
    assert pode_ligar(env, Sistema(real, home_do_host=real)) is None


def test_systemctl_que_falha_vira_recusa(tmp_path: Path) -> None:
    class Quebrado(Sistema):
        def __call__(self, comando: Sequence[str]) -> Resultado:
            resposta = super().__call__(comando)
            if "enable" in comando:
                return Resultado(1, "Failed to enable\n")
            return resposta

    with pytest.raises(Recusa) as erro:
        ligar(Quebrado(tmp_path), env=_env(tmp_path))
    assert erro.value.motivo.chave == "segundo_plano.systemctl_falhou"
    assert erro.value.motivo.params["saida"] == "Failed to enable"


def test_atalho_criado_mesmo_com_segundo_plano_desligado(tmp_path: Path) -> None:
    rodar = Sistema(tmp_path)
    criar_atalho(rodar, env=_env(tmp_path, "fedora-dev"))
    assert f"Exec={ENTER} -n fedora-dev -- {sys.executable} -m jobot abrir" in _atalho(
        tmp_path
    ).read_text("utf-8")
    assert not _servico(tmp_path).exists()
    assert rodar.systemctl() == []
    criar_atalho(rodar, env=_env(tmp_path, "fedora-dev"))  # repetir só reescreve


def test_atalho_sem_host_exec_usa_o_nome_simples(tmp_path: Path) -> None:
    criar_atalho(Sistema(tmp_path, host_exec=False), env=_env(tmp_path, "fedora-dev"))
    texto = _atalho(tmp_path).read_text("utf-8")
    assert f"Exec=distrobox-enter -n fedora-dev -- {sys.executable} -m jobot abrir" in texto


def test_status(tmp_path: Path) -> None:
    env = _env(tmp_path, "fedora-dev")
    assert status(Sistema(tmp_path), env=env) == Estado(habilitado=True, ativo=True)
    assert status(Sistema(tmp_path, habilitado=False, ativo=False), env=env) == Estado(
        habilitado=False, ativo=False
    )
    rodar = Sistema(tmp_path)
    status(rodar, env=env)
    assert (*HOST, "systemctl", "--user", "is-enabled", "jobot.service") in rodar.chamadas
    assert (*HOST, "systemctl", "--user", "is-active", "jobot.service") in rodar.chamadas


def test_rodar_comando_real_usa_lista_de_argumentos() -> None:
    ok = rodar_comando([sys.executable, "-c", "import sys; print(sys.argv[1])", "a b; c"])
    assert ok == Resultado(0, "a b; c\n")
    assert rodar_comando([sys.executable, "-c", "raise SystemExit(3)"]).codigo == 3
    assert rodar_comando(["/nao/existe/jobot-teste"]).codigo == 127


def _rodar_com(monkeypatch: pytest.MonkeyPatch, rodar: Sistema) -> None:
    monkeypatch.setattr(sp, "rodar_comando", rodar)


def test_executar_status_e_ligar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CONTAINER_ID", raising=False)
    _rodar_com(monkeypatch, Sistema(tmp_path))
    assert executar(argparse.Namespace(acao="ligar")) == 0
    assert _servico(tmp_path).is_file()
    capsys.readouterr()
    assert executar(argparse.Namespace(acao="status")) == 0
    assert "segundo plano: ligado" in capsys.readouterr().out
    assert executar(argparse.Namespace(acao="desligar")) == 0
    assert not _servico(tmp_path).exists()


def test_executar_recusa_sai_com_1_e_diz_o_motivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CONTAINER_ID", raising=False)
    _rodar_com(monkeypatch, Sistema(tmp_path, systemd=False))
    assert executar(argparse.Namespace(acao="ligar")) == 1
    assert "systemd" in capsys.readouterr().err
    assert not _servico(tmp_path).exists()
