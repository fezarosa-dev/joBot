import logging
from collections.abc import Sequence
from pathlib import Path

import pytest

from jobot.sistema.segundo_plano_linux import Resultado
from jobot.sistema.tela import VARIAVEIS, ambiente_da_tela


def _nao_roda(comando: Sequence[str]) -> Resultado:
    raise AssertionError(f"não devia rodar {comando}")


class _Executor:
    def __init__(self, saida: str, codigo: int = 0) -> None:
        self.saida = saida
        self.codigo = codigo
        self.chamadas: list[tuple[str, ...]] = []

    def __call__(self, comando: Sequence[str]) -> Resultado:
        self.chamadas.append(tuple(comando))
        return Resultado(self.codigo, self.saida)


def test_variaveis_sao_as_quatro_do_plano() -> None:
    assert VARIAVEIS == ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR")


def test_tela_do_proprio_ambiente_nao_roda_comando(tmp_path: Path) -> None:
    env = {"DISPLAY": ":0", "XDG_RUNTIME_DIR": str(tmp_path), "HOME": "/x"}
    assert ambiente_da_tela(env, _nao_roda) == {
        "DISPLAY": ":0",
        "XDG_RUNTIME_DIR": str(tmp_path),
    }
    assert ambiente_da_tela({"WAYLAND_DISPLAY": "wayland-0"}, _nao_roda) == {
        "WAYLAND_DISPLAY": "wayland-0"
    }


def test_sem_tela_le_o_systemd(tmp_path: Path) -> None:
    auth = tmp_path / "auth"
    auth.write_text("")
    saida = f"PATH=/bin\nDISPLAY=:1\nXAUTHORITY={auth}\nXDG_RUNTIME_DIR={tmp_path}\nHOME=/h\n"
    exec_ = _Executor(saida)
    assert ambiente_da_tela({}, exec_) == {
        "DISPLAY": ":1",
        "XAUTHORITY": str(auth),
        "XDG_RUNTIME_DIR": str(tmp_path),
    }
    assert exec_.chamadas == [("systemctl", "--user", "show-environment")]


def test_no_container_usa_distrobox_host_exec() -> None:
    exec_ = _Executor("DISPLAY=:0\n")
    resultado = ambiente_da_tela({"CONTAINER_ID": "fedora-dev"}, exec_)
    assert resultado == {"DISPLAY": ":0"}
    assert exec_.chamadas[0][0] == "distrobox-host-exec"
    assert exec_.chamadas[0][1:] == ("systemctl", "--user", "show-environment")


def test_valores_fora_do_formato_sao_ignorados(tmp_path: Path) -> None:
    saida = "DISPLAY=;rm\nWAYLAND_DISPLAY=a/b\nXAUTHORITY=relativo\nXDG_RUNTIME_DIR=/nao/existe\n"
    assert ambiente_da_tela({}, _Executor(saida)) == {}
    # controle: valores válidos da mesma forma passam
    saida_boa = f"DISPLAY=host.local:10.0\nWAYLAND_DISPLAY=/run/w0\nXDG_RUNTIME_DIR={tmp_path}\n"
    assert ambiente_da_tela({}, _Executor(saida_boa)) == {
        "DISPLAY": "host.local:10.0",
        "WAYLAND_DISPLAY": "/run/w0",
        "XDG_RUNTIME_DIR": str(tmp_path),
    }
    # DISPLAY inválido no próprio ambiente não vale: cai para o systemd
    exec_ = _Executor("DISPLAY=:2\n")
    assert ambiente_da_tela({"DISPLAY": ";rm"}, exec_) == {"DISPLAY": ":2"}
    assert len(exec_.chamadas) == 1


def test_xauthority_e_xdg_invalidos_caem_mesmo_com_display_valido(tmp_path: Path) -> None:
    # DISPLAY válido: a regra "sem tela => vazio" não mascara a rejeição dos outros campos
    saida = "DISPLAY=:0\nXAUTHORITY=relativo\nXDG_RUNTIME_DIR=/nao/existe\n"
    assert ambiente_da_tela({}, _Executor(saida)) == {"DISPLAY": ":0"}
    saida = f"DISPLAY=:0\nXAUTHORITY={tmp_path}/nao-existe\nWAYLAND_DISPLAY=a/b\n"
    assert ambiente_da_tela({}, _Executor(saida)) == {"DISPLAY": ":0"}
    # o mesmo vale no próprio ambiente (sem rodar comando)
    env = {"DISPLAY": ":0", "XAUTHORITY": "relativo", "XDG_RUNTIME_DIR": "/nao/existe"}
    assert ambiente_da_tela(env, _nao_roda) == {"DISPLAY": ":0"}


def test_segredo_da_saida_nao_vai_ao_log_nem_ao_ambiente(
    caplog: pytest.LogCaptureFixture,
) -> None:
    saida = "SEGREDO=xyz\nTOKEN=SEGREDO\nDISPLAY=:0\nOUTRA=SEGREDO\n"
    with caplog.at_level(logging.DEBUG):
        resultado = ambiente_da_tela({}, _Executor(saida))
    assert resultado == {"DISPLAY": ":0"}
    assert "SEGREDO" not in caplog.text
    assert "SEGREDO" not in resultado.values()
    assert "DISPLAY" in caplog.text


def test_sem_nada_devolve_vazio() -> None:
    assert ambiente_da_tela({}, _Executor("", 1)) == {}
    assert ambiente_da_tela({}, _Executor("", 0)) == {}
    assert ambiente_da_tela({}, _Executor("PATH=/bin\n", 0)) == {}


def test_so_xauthority_ou_xdg_sem_display_devolve_vazio(tmp_path: Path) -> None:
    arq = tmp_path / "auth"
    arq.write_text("")
    assert ambiente_da_tela({}, _Executor(f"XDG_RUNTIME_DIR={tmp_path}\n")) == {}
    assert ambiente_da_tela({}, _Executor(f"XAUTHORITY={arq}\n")) == {}


def test_falha_do_comando_loga_so_o_codigo(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        resultado = ambiente_da_tela({}, _Executor("SEGREDO=xyz\n", 127))
    assert resultado == {}
    assert "127" in caplog.text
    assert "SEGREDO" not in caplog.text


def test_display_com_digito_unicode_e_ignorado() -> None:
    assert ambiente_da_tela({}, _Executor("DISPLAY=:٣\n")) == {}


@pytest.mark.parametrize("nome", [".", ".."])
def test_wayland_display_ponto_e_ignorado(nome: str) -> None:
    assert ambiente_da_tela({}, _Executor(f"WAYLAND_DISPLAY={nome}\n")) == {}


@pytest.mark.parametrize("plataforma", ["win32", "darwin"])
def test_windows_e_mac_tem_a_tela_de_quem_entrou(plataforma: str) -> None:
    # sem DISPLAY nem systemctl: vazio seria "sem tela" e o login nunca abriria
    assert ambiente_da_tela({}, _nao_roda, plataforma=plataforma) == {"JOBOT_TELA": plataforma}


def test_linux_sem_display_segue_sem_tela() -> None:
    assert ambiente_da_tela({}, _Executor("", 1), plataforma="linux") == {}
