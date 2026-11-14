import json
import signal
import socket
import subprocess
import sys
import threading
import webbrowser
from argparse import Namespace
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from jobot.sistema import abrir as modulo_abrir
from jobot.sistema import instancia
from jobot.sistema.abrir import (
    abrir_navegador,
    abrir_painel,
    e_o_jobot,
    executar,
    sair_do_servidor,
)
from jobot.sistema.instancia import Trava

JOBOT = json.dumps({"app": "jobot", "versao": "0.1.0"}).encode()


@contextmanager
def _servidor(corpo: bytes = JOBOT, status: int = 200, porta: int = 0) -> Iterator[int]:
    """Servidor local que responde a /saude-local; devolve a porta."""

    class Resposta(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(status if self.path == "/saude-local" else 404)
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Resposta)
    fio = threading.Thread(target=servidor.serve_forever, daemon=True)
    fio.start()
    try:
        yield servidor.server_address[1]
    finally:
        servidor.shutdown()
        servidor.server_close()
        fio.join()


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _Navegador:
    def __init__(self, resultado: bool = True) -> None:
        self.chamadas: list[str] = []
        self.resultado = resultado

    def __call__(self, endereco: str, env: Mapping[str, str]) -> bool:
        self.chamadas.append(endereco)
        return self.resultado


class _Saida:
    def __init__(self) -> None:
        self.linhas: list[str] = []

    def __call__(self, texto: str) -> None:
        self.linhas.append(texto)

    @property
    def texto(self) -> str:
        return "\n".join(self.linhas)


def _nao_sobe() -> None:
    raise AssertionError("não devia subir o servidor")


# --- e_o_jobot ---


def test_e_o_jobot_reconhece_a_resposta_do_jobot() -> None:
    with _servidor() as porta:
        assert e_o_jobot(porta) is True


@pytest.mark.parametrize(
    ("corpo", "status"),
    [
        (b"<html>outro programa</html>", 200),
        (json.dumps({"app": "outro"}).encode(), 200),
        (json.dumps(["jobot"]).encode(), 200),
        (JOBOT, 500),
    ],
)
def test_e_o_jobot_recusa_resposta_de_outro_programa(corpo: bytes, status: int) -> None:
    with _servidor(corpo, status) as porta:
        assert e_o_jobot(porta) is False


def test_e_o_jobot_sem_ninguem_na_porta() -> None:
    assert e_o_jobot(_porta_livre()) is False


# --- abrir ---


def test_abrir_com_servidor_no_ar_so_abre_navegador(tmp_path: Path) -> None:
    navegador, saida = _Navegador(), _Saida()
    with _servidor() as porta:
        trava = Trava(tmp_path, porta)
        assert trava.pegar() is True
        env = {"JOBOT_PORTA": str(porta)}
        codigo = abrir_painel(env, tmp_path, subir=_nao_sobe, navegador=navegador, saida=saida)
        trava.soltar()
    assert codigo == 0
    assert navegador.chamadas == [f"http://127.0.0.1:{porta}"]


def test_abrir_usa_a_porta_gravada_na_trava_e_nao_a_do_ambiente(tmp_path: Path) -> None:
    # o serviço systemd não herda o JOBOT_PORTA do shell do usuário
    navegador, saida = _Navegador(), _Saida()
    with _servidor() as porta:
        trava = Trava(tmp_path, porta)
        assert trava.pegar() is True
        env = {"JOBOT_PORTA": str(_porta_livre())}
        codigo = abrir_painel(env, tmp_path, subir=_nao_sobe, navegador=navegador, saida=saida)
        trava.soltar()
    assert codigo == 0
    assert navegador.chamadas == [f"http://127.0.0.1:{porta}"]


def test_abrir_sem_servidor_sobe_e_abre(tmp_path: Path) -> None:
    navegador, saida = _Navegador(), _Saida()
    porta = _porta_livre()
    subidas: list[int] = []
    pilha: list[Any] = []

    def subir() -> None:
        subidas.append(1)
        contexto = _servidor(porta=porta)
        contexto.__enter__()
        pilha.append(contexto)

    try:
        env = {"JOBOT_PORTA": str(porta)}
        codigo = abrir_painel(env, tmp_path, subir=subir, navegador=navegador, saida=saida)
    finally:
        for contexto in pilha:
            contexto.__exit__(None, None, None)
    assert codigo == 0
    assert subidas == [1]
    assert navegador.chamadas == [f"http://127.0.0.1:{porta}"]


def test_abrir_sem_servidor_que_nunca_responde_falha_sem_navegador(tmp_path: Path) -> None:
    navegador, saida = _Navegador(), _Saida()
    porta = _porta_livre()
    env = {"JOBOT_PORTA": str(porta)}
    codigo = abrir_painel(
        env, tmp_path, subir=lambda: None, navegador=navegador, saida=saida, esperar_s=0.3
    )
    assert codigo != 0
    assert navegador.chamadas == []
    assert saida.linhas


def test_sem_navegador_mostra_o_endereco(tmp_path: Path) -> None:
    navegador, saida = _Navegador(resultado=False), _Saida()
    with _servidor() as porta:
        trava = Trava(tmp_path, porta)
        assert trava.pegar() is True
        env = {"JOBOT_PORTA": str(porta)}
        codigo = abrir_painel(env, tmp_path, subir=_nao_sobe, navegador=navegador, saida=saida)
        trava.soltar()
    assert codigo == 0  # o painel está no ar: só falta o navegador
    assert f"http://127.0.0.1:{porta}" in saida.texto


@pytest.mark.parametrize("com_trava", [False, True])
def test_porta_de_outro_programa_nao_abre_navegador(tmp_path: Path, com_trava: bool) -> None:
    navegador, saida = _Navegador(), _Saida()
    with _servidor(b"<html>outro programa</html>") as porta:
        trava = Trava(tmp_path, porta)
        if com_trava:  # PID guardado, mas a porta responde outra coisa
            assert trava.pegar() is True
        env = {"JOBOT_PORTA": str(porta)}
        codigo = abrir_painel(
            env, tmp_path, subir=_nao_sobe, navegador=navegador, saida=saida, esperar_s=0.3
        )
        trava.soltar()
    assert codigo != 0
    assert navegador.chamadas == []
    assert str(porta) in saida.texto
    assert "JOBOT_PORTA" in saida.texto


def test_abrir_le_a_trava_uma_so_vez(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # PID e porta saem da mesma leitura: duas aberturas poderiam ver donos diferentes
    aberturas: list[int] = []
    original = instancia._abrir

    def contando(dados: Path, flags: int) -> int:
        aberturas.append(flags)
        return original(dados, flags)

    navegador, saida = _Navegador(), _Saida()
    with _servidor() as porta:
        trava = Trava(tmp_path, porta)
        assert trava.pegar() is True
        monkeypatch.setattr(instancia, "_abrir", contando)
        codigo = abrir_painel({}, tmp_path, subir=_nao_sobe, navegador=navegador, saida=saida)
        trava.soltar()
    assert codigo == 0
    assert len(aberturas) == 1


def test_executar_abrir_com_porta_alheia_nao_sobe_nem_abre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subidas: list[int] = []
    navegadores: list[str] = []

    # o default de abrir_painel guarda abrir_navegador: o ponto de corte é o webbrowser
    def subir() -> None:
        subidas.append(1)

    def abre(url: str, *args: object, **kwargs: object) -> bool:
        navegadores.append(url)
        return True

    monkeypatch.setattr(modulo_abrir, "_subir_servidor", subir)
    monkeypatch.setattr(webbrowser, "open", abre)
    with _servidor(b"outro") as porta:
        monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
        monkeypatch.setenv("JOBOT_PORTA", str(porta))
        monkeypatch.delenv("CONTAINER_ID", raising=False)
        assert executar(Namespace(comando="abrir")) != 0
    assert subidas == []
    assert navegadores == []


def test_executar_abrir_que_nao_consegue_subir_diz_numa_linha_e_sai_com_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    monkeypatch.setenv("JOBOT_PORTA", str(_porta_livre()))
    monkeypatch.delenv("CONTAINER_ID", raising=False)
    monkeypatch.setattr(sys, "executable", "/nao/existe/python-do-jobot")
    erro: OSError | None = None
    codigo = None
    try:
        codigo = executar(Namespace(comando="abrir"))
    except OSError as exc:
        erro = exc
    assert erro is None, f"OSError vazou: {erro!r}"
    assert codigo == 1
    linhas = capsys.readouterr().err.strip().splitlines()
    assert len(linhas) == 1
    assert "Traceback" not in linhas[0]


# --- abrir_navegador ---


def test_no_distrobox_usa_xdg_open_pelo_host() -> None:
    comandos: list[Sequence[str]] = []

    def rodar(comando: Sequence[str]) -> bool:
        comandos.append(comando)
        return True

    def web(endereco: str) -> bool:
        raise AssertionError("no distrobox não usa webbrowser")

    env = {"CONTAINER_ID": "fedora-dev"}
    assert abrir_navegador("http://127.0.0.1:47615", env, rodar=rodar, web=web) is True
    assert comandos == [("distrobox-host-exec", "xdg-open", "http://127.0.0.1:47615")]


def test_no_distrobox_sem_xdg_open_devolve_false() -> None:
    assert (
        abrir_navegador("http://127.0.0.1:1", {"CONTAINER_ID": "x"}, rodar=lambda c: False) is False
    )


def test_fora_do_distrobox_usa_webbrowser() -> None:
    abertos: list[str] = []

    def web(endereco: str) -> bool:
        abertos.append(endereco)
        return True

    def rodar(comando: Sequence[str]) -> bool:
        raise AssertionError("fora do distrobox não roda xdg-open")

    assert abrir_navegador("http://127.0.0.1:1", {}, rodar=rodar, web=web) is True
    assert abertos == ["http://127.0.0.1:1"]
    assert abrir_navegador("http://127.0.0.1:1", {}, rodar=rodar, web=lambda e: False) is False


# --- sair ---

_FILHO = (
    "import signal, sys, time\n"
    "from pathlib import Path\n"
    "from jobot.sistema.instancia import Trava\n"
    "if sys.argv[2] == 'ignora':\n"
    "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "assert Trava(Path(sys.argv[1]), 1234).pegar()\n"
    "print('pronto', flush=True)\n"
    "time.sleep(60)\n"
)


@contextmanager
def _filho_com_trava(dados: Path, modo: str = "morre") -> Iterator[subprocess.Popen[str]]:
    filho = subprocess.Popen(
        [sys.executable, "-c", _FILHO, str(dados), modo],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert filho.stdout is not None
        assert filho.stdout.readline().strip() == "pronto"
        yield filho
    finally:
        filho.kill()
        filho.wait()


def test_sair_manda_sigterm_ao_pid_da_trava(tmp_path: Path) -> None:
    saida = _Saida()
    with _filho_com_trava(tmp_path) as filho:
        assert sair_do_servidor(tmp_path, saida=saida, esperar_s=5) == 0
        assert filho.wait(timeout=5) == -signal.SIGTERM
    assert saida.linhas


def test_sair_avisa_quando_o_servidor_nao_encerra(tmp_path: Path) -> None:
    saida = _Saida()
    with _filho_com_trava(tmp_path, "ignora") as filho:
        assert sair_do_servidor(tmp_path, saida=saida, esperar_s=0.5) != 0
        assert filho.poll() is None
    assert saida.linhas


def test_sair_sem_servidor_avisa_e_sai_com_0(tmp_path: Path) -> None:
    saida = _Saida()
    assert sair_do_servidor(tmp_path, saida=saida) == 0
    assert saida.linhas


def test_sair_nao_sinaliza_pid_velho_sem_trava_presa(tmp_path: Path) -> None:
    saida = _Saida()
    inocente = subprocess.Popen(["sleep", "60"])
    try:
        (tmp_path / "jobot.lock").write_text(f"{inocente.pid}\n47615\n")
        assert sair_do_servidor(tmp_path, saida=saida, esperar_s=0.5) == 0
        assert inocente.poll() is None  # ninguém prende a trava: o PID é velho
    finally:
        inocente.kill()
        inocente.wait()


def test_executar_sair_usa_a_pasta_de_dados_do_ambiente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JOBOT_DADOS", str(tmp_path))
    with _filho_com_trava(tmp_path) as filho:
        assert executar(Namespace(comando="sair")) == 0
        assert filho.wait(timeout=5) == -signal.SIGTERM
