"""Segundo plano no Windows (Agendador de Tarefas) e a função única que escolhe pelo sistema."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from apoio.segundo_plano_falso import FalsoAgendador, FalsoSistema
from jobot.sistema import segundo_plano, segundo_plano_linux, segundo_plano_windows
from jobot.sistema.segundo_plano_linux import Estado, Recusa, Resultado

PY = r"C:\Users\Ana Maria\AppData\Roaming\uv\tools\jobot\Scripts\python.exe"
PYW = r"C:\Users\Ana Maria\AppData\Roaming\uv\tools\jobot\Scripts\pythonw.exe"
USUARIO = r"CASA\Ana Maria"


def _criar(xml: str) -> tuple[str, ...]:
    return ("schtasks", "/Create", "/TN", "joBot", "/XML", xml, "/F")


APAGAR = ("schtasks", "/Delete", "/TN", "joBot", "/F")
CONSULTAR = ("schtasks", "/Query", "/TN", "joBot")


def test_pythonw_fica_ao_lado_do_python_do_jobot() -> None:
    assert segundo_plano_windows.pythonw(PY) == PYW


def test_ligar_cria_a_tarefa_pelo_xml_e_apaga_o_arquivo() -> None:
    agendador = FalsoAgendador()
    segundo_plano_windows.ligar(agendador, python=PY, usuario=USUARIO)
    (comando,) = agendador.chamadas
    assert comando == _criar(comando[5])
    assert agendador.existe
    assert agendador.xml == segundo_plano_windows.xml_da_tarefa(PYW, USUARIO)
    assert not Path(comando[5]).exists()


def test_xml_da_tarefa_fica_no_ar_na_bateria_e_sem_limite() -> None:
    raiz = ET.fromstring(segundo_plano_windows.xml_da_tarefa(PYW, USUARIO).encode("utf-16"))
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

    def texto(caminho: str) -> str | None:
        return raiz.findtext(caminho, namespaces=ns)

    assert texto("t:Triggers/t:LogonTrigger/t:UserId") == USUARIO
    assert texto("t:Principals/t:Principal/t:UserId") == USUARIO
    assert texto("t:Principals/t:Principal/t:LogonType") == "InteractiveToken"
    assert texto("t:Settings/t:DisallowStartIfOnBatteries") == "false"
    assert texto("t:Settings/t:StopIfGoingOnBatteries") == "false"
    assert texto("t:Settings/t:ExecutionTimeLimit") == "PT0S"
    assert texto("t:Settings/t:MultipleInstancesPolicy") == "IgnoreNew"
    assert texto("t:Actions/t:Exec/t:Command") == PYW
    assert texto("t:Actions/t:Exec/t:Arguments") == "-m jobot serve"


def test_xml_da_tarefa_escapa_o_caminho() -> None:
    xml = segundo_plano_windows.xml_da_tarefa(r"C:\A&B <x>\pythonw.exe", USUARIO)
    assert (
        ET.fromstring(xml.encode("utf-16")).findtext(
            ".//{http://schemas.microsoft.com/windows/2004/02/mit/task}Command"
        )
        == r"C:\A&B <x>\pythonw.exe"
    )


@pytest.mark.parametrize(
    ("env", "esperado"),
    [({"USERDOMAIN": "CASA", "USERNAME": "Ana"}, r"CASA\Ana"), ({"USERNAME": "Ana"}, "Ana")],
)
def test_usuario_atual(env: dict[str, str], esperado: str) -> None:
    assert segundo_plano_windows.usuario_atual(env) == esperado


def test_ligar_recusado_diz_o_comando_e_guarda_a_saida_so_nos_params() -> None:
    agendador = FalsoAgendador()
    agendador.falha_em["/Create"] = Resultado(1, erro="Acesso negado.")
    with pytest.raises(Recusa) as recusa:
        segundo_plano_windows.ligar(agendador, python=PY, usuario=USUARIO)
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
    [("linux", True), ("win32", True), ("darwin", True), ("freebsd14", False)],
)
def test_suportado_pelo_sistema(plataforma: str, esperado: bool) -> None:
    assert segundo_plano.suportado(plataforma) is esperado


def test_no_windows_a_funcao_unica_usa_o_agendador(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(segundo_plano_windows, "_python", lambda: PY)
    agendador = FalsoAgendador()
    segundo_plano.ligar(agendador, env={"USERNAME": "Ana"}, plataforma="win32")
    assert segundo_plano.status(agendador, env={}, plataforma="win32") == Estado(True, True)
    segundo_plano.criar_atalho(agendador, env={}, plataforma="win32")  # o NSIS já cria
    segundo_plano.desligar(agendador, env={}, plataforma="win32")
    criar = agendador.chamadas[0]
    assert agendador.chamadas == [_criar(criar[5]), CONSULTAR, APAGAR]
    assert "<UserId>Ana</UserId>" in agendador.xml


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
