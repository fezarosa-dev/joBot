import json
import os
import signal
import socket
import subprocess
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from apoio.filho_com_trava import filho_com_trava
from apoio.llama_falso import RelogioSincrono
from jobot.sistema import abrir as modulo_abrir
from jobot.sistema import instancia, sair
from jobot.sistema.abrir import (
    _lancar,
    abrir_janela,
    abrir_navegador,
    abrir_painel,
    e_o_jobot,
    existe_do_sistema,
    sair_do_servidor,
)
from jobot.sistema.instancia import Trava
from jobot.sistema.pastas import PASTA_NAVEGADOR

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


def test_abrir_sem_servidor_diz_o_endereco_e_como_sair(tmp_path: Path) -> None:
    navegador, saida = _Navegador(), _Saida()
    porta = _porta_livre()
    pilha: list[Any] = []

    def subir() -> None:
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
    assert saida.linhas == [
        f"joBot aberto em http://127.0.0.1:{porta}. Para sair, use Sair no painel "
        "ou rode: jobot sair"
    ]


def test_abrir_com_servidor_no_ar_diz_que_ja_estava_aberto(tmp_path: Path) -> None:
    navegador, saida = _Navegador(), _Saida()
    with _servidor() as porta:
        trava = Trava(tmp_path, porta)
        assert trava.pegar() is True
        codigo = abrir_painel(
            {"JOBOT_PORTA": str(porta)}, tmp_path, subir=_nao_sobe, navegador=navegador, saida=saida
        )
        trava.soltar()
    assert codigo == 0
    assert saida.linhas == [
        f"O joBot já estava aberto em http://127.0.0.1:{porta}. Para sair, use Sair no painel "
        "ou rode: jobot sair"
    ]


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
    navegador, saida, relogio = _Navegador(), _Saida(), RelogioSincrono()
    porta = _porta_livre()
    env = {"JOBOT_PORTA": str(porta)}
    codigo = abrir_painel(
        env,
        tmp_path,
        subir=lambda: None,
        navegador=navegador,
        saida=saida,
        esperar_s=1,
        agora=relogio.agora,
        dormir=relogio.dormir,
    )
    assert relogio.t >= 1  # esperou o prazo inteiro no relógio falso, sem tempo real
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
    navegador, saida, relogio = _Navegador(), _Saida(), RelogioSincrono()
    with _servidor(b"<html>outro programa</html>") as porta:
        trava = Trava(tmp_path, porta)
        if com_trava:  # PID guardado, mas a porta responde outra coisa
            assert trava.pegar() is True
        env = {"JOBOT_PORTA": str(porta)}
        codigo = abrir_painel(
            env,
            tmp_path,
            subir=_nao_sobe,
            navegador=navegador,
            saida=saida,
            esperar_s=1,
            agora=relogio.agora,
            dormir=relogio.dormir,
        )
        trava.soltar()
    assert (relogio.t >= 1) is com_trava  # sem trava, a porta alheia recusa antes de esperar
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


# --- janela do modo app (T267) ---

ENDERECO = "http://127.0.0.1:47615"
ARG_APP = f"--app={ENDERECO}"
SEM_BOAS_VINDAS = ["--no-first-run", "--no-default-browser-check"]


class _Lancador:
    def __init__(self, resultado: bool = True) -> None:
        self.comandos: list[list[str]] = []
        self.resultado = resultado

    def __call__(self, comando: Sequence[str]) -> bool:
        self.comandos.append(list(comando))
        return self.resultado


class _Cenario:
    """Abre a janela com `existe`, `chromium` e o lançador injetados; guarda o que foi chamado."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        presentes: Sequence[str] = (),
        chromium: Path | None = None,
        lancar_ok: bool = True,
    ) -> None:
        self.lancador = _Lancador(lancar_ok)
        self.presentes = set(presentes)
        self.chromium_pedido = 0
        self._chromium = chromium
        self.abas: list[str] = []

        def aba(endereco: str, env: Mapping[str, str]) -> bool:
            self.abas.append(endereco)
            return True

        monkeypatch.setattr(modulo_abrir, "abrir_navegador", aba)

    def _chromium_do_jobot(self) -> Path | None:
        self.chromium_pedido += 1
        return self._chromium

    def abrir(
        self,
        *,
        env: Mapping[str, str] | None = None,
        sistema: str = "linux",
        pasta: Path = Path("/dados"),
    ) -> bool:
        return abrir_janela(
            ENDERECO,
            env or {},
            sistema=sistema,
            existe=self.presentes.__contains__,
            chromium=self._chromium_do_jobot,
            pasta_dados=pasta,
            lancar=self.lancador,
        )


def test_chrome_do_sistema_abre_com_app(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _Cenario(monkeypatch, presentes=["google-chrome"])
    assert c.abrir() is True
    assert c.lancador.comandos == [["google-chrome", ARG_APP, *SEM_BOAS_VINDAS]]
    assert c.abas == []


def test_ordem_do_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _Cenario(monkeypatch, presentes=["chromium", "microsoft-edge", "google-chrome-stable"])
    assert c.abrir() is True
    assert c.lancador.comandos == [["google-chrome-stable", ARG_APP, *SEM_BOAS_VINDAS]]


def test_so_chromium_do_jobot_usa_perfil_da_janela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe = tmp_path / "chromium"
    c = _Cenario(monkeypatch, chromium=exe)
    assert c.abrir(pasta=tmp_path) is True
    assert len(c.lancador.comandos) == 1
    comando = c.lancador.comandos[0]
    assert comando[0] == str(exe)
    assert ARG_APP in comando
    assert all(a in comando for a in SEM_BOAS_VINDAS)
    perfil = [a for a in comando if a.startswith("--user-data-dir=")]
    assert perfil == [f"--user-data-dir={tmp_path / 'janela'}"]
    assert perfil[0] != f"--user-data-dir={tmp_path / PASTA_NAVEGADOR}"
    assert c.abas == []


def test_nada_achado_cai_na_aba(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _Cenario(monkeypatch)
    assert c.abrir() is True
    assert c.lancador.comandos == []
    assert c.abas == [ENDERECO]


def test_chromium_nao_e_chamado_quando_o_sistema_tem_navegador(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = _Cenario(monkeypatch, presentes=["chromium"], chromium=tmp_path / "chromium")
    assert c.abrir() is True
    assert c.chromium_pedido == 0


def test_lancador_que_falha_cai_na_aba(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c = _Cenario(monkeypatch, presentes=["chromium"], lancar_ok=False)
    assert c.abrir() is True
    assert c.abas == [ENDERECO]


def test_chromium_que_explode_cai_na_aba(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _Cenario(monkeypatch)

    def explode() -> Path | None:
        raise RuntimeError("driver do Playwright não subiu")

    monkeypatch.setattr(c, "_chromium_do_jobot", explode)
    assert c.abrir() is True
    assert c.abas == [ENDERECO]


def test_mac_usa_open_na(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _Cenario(monkeypatch, presentes=["/Applications/Microsoft Edge.app"])
    assert c.abrir(sistema="darwin") is True
    assert c.lancador.comandos == [
        ["open", "-na", "Microsoft Edge", "--args", ARG_APP, *SEM_BOAS_VINDAS]
    ]


def test_windows_acha_chrome_e_depois_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ProgramFiles", r"C:\Programas")
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    edge = r"C:\Programas\Microsoft\Edge\Application\msedge.exe"
    c = _Cenario(monkeypatch, presentes=[edge])
    assert c.abrir(sistema="win32") is True
    assert c.lancador.comandos == [[edge, ARG_APP, *SEM_BOAS_VINDAS]]
    chrome = r"C:\Programas\Google\Chrome\Application\chrome.exe"
    c = _Cenario(monkeypatch, presentes=[edge, chrome])
    assert c.abrir(sistema="win32") is True
    assert c.lancador.comandos == [[chrome, ARG_APP, *SEM_BOAS_VINDAS]]


def test_distrobox_usa_o_prefixo(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _Cenario(monkeypatch, presentes=["chromium"])
    assert c.abrir(env={"CONTAINER_ID": "fedora-dev"}) is True
    assert c.lancador.comandos == [["distrobox-host-exec", "chromium", ARG_APP, *SEM_BOAS_VINDAS]]


def test_existe_sem_prefixo_usa_o_path() -> None:
    def rodar(comando: Sequence[str]) -> bool:
        raise AssertionError("sem prefixo não roda `which`")

    existe = existe_do_sistema((), rodar=rodar, procurar=lambda nome: "/usr/bin/x")
    assert existe("chromium") is True
    assert existe_do_sistema((), rodar=rodar, procurar=lambda nome: None)("chromium") is False


def test_existe_com_prefixo_pergunta_ao_host() -> None:
    perguntas: list[Sequence[str]] = []

    def rodar(comando: Sequence[str]) -> bool:
        perguntas.append(comando)
        return comando[-1] == "chromium"

    def procurar(nome: str) -> str | None:
        raise AssertionError("com prefixo quem procura é o host")

    existe = existe_do_sistema(("distrobox-host-exec",), rodar=rodar, procurar=procurar)
    assert existe("chromium") is True
    assert existe("google-chrome") is False
    assert perguntas[0] == ("distrobox-host-exec", "which", "chromium")


def test_existe_com_caminho_olha_o_arquivo(tmp_path: Path) -> None:
    arquivo = tmp_path / "chrome.exe"
    arquivo.touch()
    existe = existe_do_sistema((), procurar=lambda nome: None)
    assert existe(str(arquivo)) is True
    assert existe(str(tmp_path / "outro.exe")) is False


def test_lancador_nao_espera_o_navegador(monkeypatch: pytest.MonkeyPatch) -> None:
    class Falso:
        criados: list[tuple[Sequence[str], dict[str, Any]]] = []
        esperou = False
        falha: OSError | None = None

        def __init__(self, comando: Sequence[str], **kwargs: Any) -> None:
            self.args = comando
            if Falso.falha is not None:
                raise Falso.falha
            Falso.criados.append((comando, kwargs))

        def __enter__(self) -> Falso:
            return self

        def __exit__(self, *saida: object) -> None:
            return None

        def wait(self, *args: Any, **kwargs: Any) -> int:
            Falso.esperou = True
            return 0

        def communicate(self, *args: Any, **kwargs: Any) -> tuple[None, None]:
            Falso.esperou = True
            return None, None

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(subprocess, "Popen", Falso)
    assert _lancar(["chrome"]) is True
    assert Falso.esperou is False
    assert len(Falso.criados) == 1
    comando, kwargs = Falso.criados[0]
    assert list(comando) == ["chrome"]
    assert kwargs["start_new_session"] is True
    for saida in ("stdin", "stdout", "stderr"):
        assert kwargs[saida] == subprocess.DEVNULL
    Falso.falha = OSError("não existe")
    assert _lancar(["chrome"]) is False


# --- sair ---


def test_sair_manda_sigterm_ao_pid_da_trava(tmp_path: Path) -> None:
    saida = _Saida()
    with filho_com_trava(tmp_path) as filho:
        assert sair_do_servidor(tmp_path, saida=saida, esperar_s=5) == 0
        assert filho.wait(timeout=5) == -signal.SIGTERM
    assert saida.linhas


def test_sair_avisa_quando_o_servidor_nao_encerra(tmp_path: Path) -> None:
    saida, relogio = _Saida(), RelogioSincrono()
    with filho_com_trava(tmp_path, "ignora") as filho:
        codigo = sair_do_servidor(
            tmp_path, saida=saida, esperar_s=1, agora=relogio.agora, dormir=relogio.dormir
        )
        assert codigo != 0
        assert relogio.t >= 1  # o prazo correu no relógio falso, sem tempo real
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


@contextmanager
def _servidor_sair(status: int, ao_pedir: Callable[[], None]) -> Iterator[tuple[int, list[str]]]:
    """Servidor local que responde ao POST /sair; devolve a porta e os segredos recebidos."""
    recebidos: list[str] = []

    class Resposta(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            recebidos.append(f"{self.path} {self.headers.get(sair.CABECALHO)}")
            ao_pedir()
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Resposta)
    fio = threading.Thread(target=servidor.serve_forever, daemon=True)
    fio.start()
    try:
        yield servidor.server_address[1], recebidos
    finally:
        servidor.shutdown()
        servidor.server_close()
        fio.join()


def _sem_kill(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    sinais: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sinal: sinais.append((pid, sinal)))
    return sinais


def test_sair_no_windows_pede_pelo_http_com_o_segredo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sinais = _sem_kill(monkeypatch)
    segredo = sair.gravar_token(tmp_path)
    saida = _Saida()
    trava: list[Trava] = []
    with _servidor_sair(200, lambda: trava[0].soltar()) as (p, recebidos):
        trava.append(Trava(tmp_path, p))
        assert trava[0].pegar() is True
        try:
            codigo = sair_do_servidor(tmp_path, saida=saida, esperar_s=5, plataforma="win32")
        finally:
            trava[0].soltar()
    assert codigo == 0
    assert recebidos == [f"/sair {segredo}"]
    assert sinais == []  # nada de SIGTERM no Windows
    assert saida.linhas == ["joBot encerrado."]


def test_sair_no_windows_com_segredo_recusado_avisa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sinais = _sem_kill(monkeypatch)
    segredo = sair.gravar_token(tmp_path)
    saida = _Saida()
    with _servidor_sair(403, lambda: None) as (p, recebidos):
        trava = Trava(tmp_path, p)
        assert trava.pegar() is True
        try:
            codigo = sair_do_servidor(tmp_path, saida=saida, esperar_s=5, plataforma="win32")
        finally:
            trava.soltar()
    assert codigo == 1
    assert recebidos == [f"/sair {segredo}"]
    assert sinais == []
    assert saida.linhas and "403" in saida.texto
    assert segredo not in saida.texto  # o segredo não vai à mensagem


def test_sair_no_windows_sem_o_arquivo_do_segredo_avisa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sinais = _sem_kill(monkeypatch)
    saida = _Saida()
    with _servidor_sair(200, lambda: None) as (p, recebidos):
        trava = Trava(tmp_path, p)
        assert trava.pegar() is True
        try:
            codigo = sair_do_servidor(tmp_path, saida=saida, esperar_s=5, plataforma="win32")
        finally:
            trava.soltar()
    assert codigo == 1
    assert recebidos == []
    assert sinais == []
    assert saida.linhas


@pytest.mark.parametrize("plataforma", ["linux", "darwin"])
def test_sair_no_posix_continua_no_sigterm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plataforma: str
) -> None:
    sair.gravar_token(tmp_path)  # mesmo com o segredo no disco, o POSIX não usa o HTTP
    saida = _Saida()
    sinais: list[tuple[int, int]] = []
    with _servidor_sair(200, lambda: None) as (p, recebidos):
        trava = Trava(tmp_path, p)
        assert trava.pegar() is True

        def kill(pid: int, sinal: int) -> None:
            sinais.append((pid, sinal))
            trava.soltar()

        monkeypatch.setattr(os, "kill", kill)
        try:
            codigo = sair_do_servidor(tmp_path, saida=saida, esperar_s=5, plataforma=plataforma)
        finally:
            trava.soltar()
    assert codigo == 0
    assert sinais == [(os.getpid(), signal.SIGTERM)]
    assert recebidos == []


# --- captura de exemplos com login: trava presa sem porta (T220) ---

AVISO_CAPTURA = (
    "Uma captura de exemplos com login está em andamento. "
    "Encerre-a no terminal dela e tente de novo."
)


def _captura(dados: Path) -> Trava:
    trava = Trava(dados, 0)  # o capturar_logado.py não serve nada: porta 0
    assert trava.pegar() is True
    return trava


def test_sair_nao_mata_a_captura(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sinais: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sinal: sinais.append((pid, sinal)))
    saida = _Saida()
    trava = _captura(tmp_path)
    try:
        codigo = sair_do_servidor(tmp_path, saida=saida, esperar_s=0)
    finally:
        trava.soltar()
    assert sinais == []
    assert codigo == 1
    assert saida.linhas == [AVISO_CAPTURA]


def test_abrir_com_captura_avisa_na_hora(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def nao_consulta(porta: int) -> bool:
        raise AssertionError("não devia consultar a porta")

    monkeypatch.setattr(modulo_abrir, "e_o_jobot", nao_consulta)
    navegador, saida = _Navegador(), _Saida()
    trava = _captura(tmp_path)
    try:
        codigo = abrir_painel({}, tmp_path, subir=_nao_sobe, navegador=navegador, saida=saida)
    finally:
        trava.soltar()
    assert codigo == 1
    assert navegador.chamadas == []
    assert saida.linhas == [AVISO_CAPTURA]
