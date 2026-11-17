"""Segundo plano no Mac (LaunchAgent do launchd) e a função única no Mac."""

import plistlib
from pathlib import Path

import pytest

from apoio.segundo_plano_falso import FalsoLaunchctl
from jobot.sistema import segundo_plano, segundo_plano_mac
from jobot.sistema.segundo_plano_linux import Estado, Recusa, Resultado

PY = "/Users/ana/.local/share/uv/tools/jobot/bin/python"
ROTULO = "io.github.fezarosa-dev.jobot"
SERVICO = f"gui/501/{ROTULO}"


def _plist(casa: Path) -> Path:
    return casa / "Library" / "LaunchAgents" / f"{ROTULO}.plist"


def _ligar(launchctl: FalsoLaunchctl, casa: Path) -> None:
    segundo_plano_mac.ligar(launchctl, python=PY, uid=501, env={"HOME": str(casa)})


def test_plist_sobe_ao_entrar_e_so_volta_se_falhar() -> None:
    plist = plistlib.loads(segundo_plano_mac.texto_do_plist(PY))
    assert plist == {
        "Label": ROTULO,
        "ProgramArguments": [PY, "-m", "jobot", "serve"],
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
    }


def test_ligar_grava_o_plist_e_faz_bootstrap(tmp_path: Path) -> None:
    launchctl = FalsoLaunchctl()
    _ligar(launchctl, tmp_path)
    arquivo = _plist(tmp_path)
    assert launchctl.chamadas == [
        ("launchctl", "print", SERVICO),
        ("launchctl", "bootstrap", "gui/501", str(arquivo)),
    ]
    assert launchctl.plist == arquivo.read_bytes() == segundo_plano_mac.texto_do_plist(PY)


def test_ligar_ja_carregado_so_regrava_o_plist(tmp_path: Path) -> None:
    """Outro bootstrap falharia ("already loaded"); bootout pararia o servidor que está no ar."""
    launchctl = FalsoLaunchctl(carregado=True)
    _ligar(launchctl, tmp_path)
    assert launchctl.chamadas == [("launchctl", "print", SERVICO)]
    assert _plist(tmp_path).read_bytes() == segundo_plano_mac.texto_do_plist(PY)


def test_ligar_recusado_apaga_o_plist_e_guarda_a_saida_so_nos_params(tmp_path: Path) -> None:
    launchctl = FalsoLaunchctl()
    launchctl.falha_em["bootstrap"] = Resultado(5, erro="Bootstrap failed: 5: Input/output error")
    with pytest.raises(Recusa) as recusa:
        _ligar(launchctl, tmp_path)
    motivo = recusa.value.motivo
    assert motivo.chave == "segundo_plano.launchctl_falhou"
    assert motivo.params == {
        "comando": "bootstrap",
        "saida": "Bootstrap failed: 5: Input/output error",
    }
    assert not _plist(tmp_path).exists()  # senão subiria no próximo login com o segundo plano off


def test_desligar_faz_bootout_e_apaga_o_plist(tmp_path: Path) -> None:
    launchctl = FalsoLaunchctl()
    _ligar(launchctl, tmp_path)
    launchctl.chamadas.clear()
    segundo_plano_mac.desligar(launchctl, uid=501, env={"HOME": str(tmp_path)})
    assert launchctl.chamadas == [("launchctl", "bootout", SERVICO)]
    assert not launchctl.carregado
    assert not _plist(tmp_path).exists()


def test_desligar_sem_servico_vale(tmp_path: Path) -> None:
    launchctl = FalsoLaunchctl(carregado=False)
    _plist(tmp_path).parent.mkdir(parents=True)
    _plist(tmp_path).write_bytes(b"velho")
    segundo_plano_mac.desligar(launchctl, uid=501, env={"HOME": str(tmp_path)})
    assert launchctl.chamadas == [
        ("launchctl", "bootout", SERVICO),
        ("launchctl", "print", SERVICO),
    ]
    assert not _plist(tmp_path).exists()


def test_desligar_com_servico_que_nao_sai_recusa_e_guarda_o_plist(tmp_path: Path) -> None:
    launchctl = FalsoLaunchctl()
    _ligar(launchctl, tmp_path)
    launchctl.falha_em["bootout"] = Resultado(1, erro="Boot-out failed: 1: Operation not permitted")
    with pytest.raises(Recusa) as recusa:
        segundo_plano_mac.desligar(launchctl, uid=501, env={"HOME": str(tmp_path)})
    assert recusa.value.motivo.params["comando"] == "bootout"
    assert _plist(tmp_path).exists()


@pytest.mark.parametrize(
    ("carregado", "rodando", "esperado"),
    [
        (True, True, Estado(True, True)),
        (True, False, Estado(True, False)),
        (False, True, Estado(False, False)),
    ],
)
def test_status_le_o_launchctl_print(carregado: bool, rodando: bool, esperado: Estado) -> None:
    launchctl = FalsoLaunchctl(carregado=carregado, rodando=rodando)
    assert segundo_plano_mac.status(launchctl, uid=501) == esperado
    assert launchctl.chamadas == [("launchctl", "print", SERVICO)]


def test_no_mac_a_funcao_unica_usa_o_launchd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(segundo_plano_mac, "_python", lambda: PY)
    monkeypatch.setattr(segundo_plano_mac, "_uid", lambda: 501)
    launchctl = FalsoLaunchctl()
    env = {"HOME": str(tmp_path)}
    assert segundo_plano.suportado("darwin")
    segundo_plano.ligar(launchctl, env=env, plataforma="darwin")
    assert segundo_plano.status(launchctl, env=env, plataforma="darwin") == Estado(True, True)
    segundo_plano.criar_atalho(launchctl, env=env, plataforma="darwin")  # o .dmg já põe o app
    segundo_plano.desligar(launchctl, env=env, plataforma="darwin")
    assert [c[1] for c in launchctl.chamadas] == ["print", "bootstrap", "print", "bootout"]
    assert not _plist(tmp_path).exists()
