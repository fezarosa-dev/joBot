"""Segundo plano no Windows (Agendador de Tarefas) e a função única que escolhe pelo sistema."""

from pathlib import Path

import pytest

from apoio.segundo_plano_falso import FalsoAgendador, FalsoSistema
from jobot.sistema import segundo_plano, segundo_plano_linux, segundo_plano_windows
from jobot.sistema.segundo_plano_linux import Estado, Recusa, Resultado

PY = r"C:\Users\Ana Maria\AppData\Roaming\uv\tools\jobot\Scripts\python.exe"
PYW = r"C:\Users\Ana Maria\AppData\Roaming\uv\tools\jobot\Scripts\pythonw.exe"
CRIAR = (
    "schtasks",
    "/Create",
    "/SC",
    "ONLOGON",
    "/TN",
    "joBot",
    "/TR",
    f'"{PYW}" -m jobot serve',
    "/F",
)
APAGAR = ("schtasks", "/Delete", "/TN", "joBot", "/F")
CONSULTAR = ("schtasks", "/Query", "/TN", "joBot")


def test_pythonw_fica_ao_lado_do_python_do_jobot() -> None:
    assert segundo_plano_windows.pythonw(PY) == PYW


def test_ligar_cria_a_tarefa_ao_entrar_com_o_pythonw() -> None:
    agendador = FalsoAgendador()
    segundo_plano_windows.ligar(agendador, python=PY)
    assert agendador.chamadas == [CRIAR]
    assert agendador.existe


def test_ligar_recusado_diz_o_comando_e_guarda_a_saida_so_nos_params() -> None:
    agendador = FalsoAgendador()
    agendador.falha_em["/Create"] = Resultado(1, erro="Acesso negado.")
    with pytest.raises(Recusa) as recusa:
        segundo_plano_windows.ligar(agendador, python=PY)
    motivo = recusa.value.motivo
    assert motivo.chave == "segundo_plano.schtasks_falhou"
    assert motivo.params == {"comando": "/Create", "saida": "Acesso negado."}


def test_desligar_apaga_a_tarefa() -> None:
    agendador = FalsoAgendador(existe=True)
    segundo_plano_windows.desligar(agendador)
    assert agendador.chamadas == [APAGAR]
    assert not agendador.existe


def test_desligar_sem_tarefa_vale() -> None:
    agendador = FalsoAgendador(existe=False)
    segundo_plano_windows.desligar(agendador)  # o /Delete falha à toa
    assert agendador.chamadas == [APAGAR, CONSULTAR]


def test_desligar_com_tarefa_que_nao_sai_e_recusa() -> None:
    agendador = FalsoAgendador(existe=True)
    agendador.falha_em["/Delete"] = Resultado(1, erro="Acesso negado.")
    with pytest.raises(Recusa) as recusa:
        segundo_plano_windows.desligar(agendador)
    assert recusa.value.motivo.params["comando"] == "/Delete"


@pytest.mark.parametrize("existe", [True, False])
def test_status_consulta_a_tarefa(existe: bool) -> None:
    agendador = FalsoAgendador(existe=existe)
    assert segundo_plano_windows.status(agendador) == Estado(habilitado=existe, ativo=existe)
    assert agendador.chamadas == [CONSULTAR]


# --- a função única ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("plataforma", "esperado"),
    [("linux", True), ("win32", True), ("darwin", False), ("freebsd14", False)],
)
def test_suportado_pelo_sistema(plataforma: str, esperado: bool) -> None:
    assert segundo_plano.suportado(plataforma) is esperado


def test_no_windows_a_funcao_unica_usa_o_agendador(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(segundo_plano_windows, "_python", lambda: PY)
    agendador = FalsoAgendador()
    segundo_plano.ligar(agendador, env={}, plataforma="win32")
    assert segundo_plano.status(agendador, env={}, plataforma="win32") == Estado(True, True)
    segundo_plano.criar_atalho(agendador, env={}, plataforma="win32")  # o NSIS já cria
    segundo_plano.desligar(agendador, env={}, plataforma="win32")
    assert agendador.chamadas == [CRIAR, CONSULTAR, APAGAR]


def test_no_linux_a_funcao_unica_usa_o_systemd(tmp_path: Path) -> None:
    sistema = FalsoSistema()
    env = {"HOME": str(tmp_path)}
    segundo_plano.ligar(sistema, env=env, plataforma="linux")
    assert ("enable", "--now", segundo_plano_linux.SERVICO) in sistema.systemctl()
    assert segundo_plano.status(sistema, env=env, plataforma="linux") == Estado(True, True)
    segundo_plano.desligar(sistema, env=env, plataforma="linux")
    assert ("disable", "--now", segundo_plano_linux.SERVICO) in sistema.systemctl()
    segundo_plano.criar_atalho(sistema, env=env, plataforma="linux")
    assert (tmp_path / ".local" / "share" / "applications" / "jobot.desktop").exists()


def test_fora_dos_sistemas_nada_e_chamado() -> None:
    agendador = FalsoAgendador()
    segundo_plano.desligar(agendador, env={}, plataforma="freebsd14")
    segundo_plano.criar_atalho(agendador, env={}, plataforma="freebsd14")
    assert segundo_plano.status(agendador, env={}, plataforma="freebsd14") == Estado(False, False)
    with pytest.raises(ValueError, match="freebsd14"):
        segundo_plano.ligar(agendador, env={}, plataforma="freebsd14")
    assert agendador.chamadas == []
