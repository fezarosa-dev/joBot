"""O `llama-server` do modelo local (desenho 7; T408; D194).

Sobe sob demanda, uma instância por joBot, em `127.0.0.1` numa porta livre, com uma chave nova por
subida que vai pelo ambiente (`LLAMA_API_KEY`), nunca pelo argv (o `ps` mostra o argv a todos).
Espera `GET /health` até 120 s, e só enquanto o filho segue vivo: filho morto é
`programa_ausente`, sem pedido a outro processo que tenha a porta. PID, porta e programa ficam em
`<dados>/ferramentas/llama.json`, para a subida seguinte encerrar a sobra de uma que morreu.

Opções conferidas em 2026-11-17 no código da tag `b12359` (`common/arg.cpp`,
https://github.com/ggml-org/llama.cpp/blob/b12359/common/arg.cpp): `--no-slots`, `--no-webui`,
`-rea/--reasoning on|off|auto`, `--sleep-idle-seconds` (-1 desliga; 0 é recusado), `-ngl`,
`-np`, `-c`, `--api-key` com o ambiente `LLAMA_API_KEY` e `--api-key-file`. O argv vence o
ambiente, mas as `LLAMA_ARG_*` da pessoa que o argv não cita valeriam: o ambiente do filho vai
sem nenhuma `LLAMA_*`. `/health` é público (sem chave) e responde 503 enquanto o modelo carrega
(`tools/server/server.cpp` e `server-http.cpp` da mesma tag). A amostragem vai no pedido
(temperatura e `seed` do cliente, T405), não no argv.
"""

import contextlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal, Protocol, cast

import httpx

from jobot.sistema import processo
from jobot.sistema.pastas import PASTA_FERRAMENTAS

ESPERA_S = 120.0  # desenho 7: espera `/health` até 120 s
SONO_S = 0.5
CONTEXTO = 8192
OCIOSO_S = 600  # o `llama-server` descarrega o modelo depois de 10 min parado
_FLAGS = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
_SEM_JANELA: dict[str, Any] = {"creationflags": 0x08000000} if sys.platform == "win32" else {}

# Os nomes são os de `nucleo.ia.Motivo`: quem chama (agenda, cli) traduz para `Falha`.
Motivo = Literal["programa_ausente", "tempo_esgotado"]


class FalhaLlama(Exception):
    def __init__(self, motivo: Motivo) -> None:
        super().__init__(motivo)
        self.motivo: Motivo = motivo


class Filho(Protocol):
    @property
    def pid(self) -> int: ...
    def poll(self) -> int | None: ...


def argv_do_servidor(programa: Path, modelo: Path, porta: int) -> list[str]:
    return [
        str(programa),
        "-m",
        str(modelo),
        "--host",
        "127.0.0.1",
        "--port",
        str(porta),
        "-c",
        str(CONTEXTO),
        "-np",
        "1",
        "-ngl",
        "0",
        "--no-webui",
        "--no-slots",
        "--reasoning",
        "off",
        "--sleep-idle-seconds",
        str(OCIOSO_S),
    ]


def ambiente(chave: str, base: Mapping[str, str] = os.environ) -> dict[str, str]:
    env = {k: v for k, v in base.items() if not k.upper().startswith("LLAMA_")}
    env["LLAMA_API_KEY"] = chave
    return env


def porta_livre() -> int:
    # ponytail: a porta pode ser tomada entre fechar e o filho abrir; aí o filho morre e é
    # `programa_ausente` (o `/health` só vale com o filho vivo)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta: int = s.getsockname()[1]
        return porta


def _lancar(argv: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        argv,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **processo.destacar(),
    )


def _encerrar_arvore(filho: Filho) -> None:
    processo.encerrar_arvore(cast("subprocess.Popen[Any]", filho))


def comando_de(pid: int) -> str:
    """A linha de comando do PID (`ps`) ou a linha do `tasklist` no Windows; erro: vazio."""
    if sys.platform == "win32":
        args = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
    else:
        args = ["ps", "-ww", "-o", "command=", "-p", str(pid)]  # -ww: sem cortar a linha
    try:
        feito = subprocess.run(args, capture_output=True, text=True, check=False, **_SEM_JANELA)
    except OSError:
        return ""
    return str(feito.stdout)


def e_o_nosso(saida: str, programa: Path, porta: int, plataforma: str = sys.platform) -> bool:
    """O PID do `llama.json` ainda é o nosso `llama-server` (PID reusado não é encerrado)? No
    Windows o `tasklist` só dá o nome da imagem."""
    if plataforma == "win32":
        return saida.startswith(f'"{programa.name}",')
    linha = saida.strip()
    return linha.startswith(f"{programa} ") and f" --port {porta} " in f"{linha} "


class _Orfao:
    """Sobra de uma subida anterior: só o PID, sem a alça do `Popen`."""

    def __init__(self, pid: int) -> None:
        self.pid = pid

    def terminate(self) -> None:
        os.kill(self.pid, signal.SIGTERM)

    def kill(self) -> None:
        os.kill(self.pid, getattr(signal, "SIGKILL", signal.SIGTERM))


def _encerrar_pid(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        processo.encerrar_grupo(_Orfao(pid))


class Llama:
    """Uma instância do `llama-server`; `subir` devolve `(endereço /v1, chave)` e `encerrar` a
    derruba (o fim do servidor do joBot chama `encerrar`)."""

    def __init__(
        self,
        dados: Path,
        programa: Path,
        modelo: Path,
        *,
        lancar: Callable[[list[str], dict[str, str]], Filho] = _lancar,
        encerrar: Callable[[Filho], None] = _encerrar_arvore,
        porta_livre: Callable[[], int] = porta_livre,
        agora: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
        comando_de: Callable[[int], str] = comando_de,
        encerrar_pid: Callable[[int], None] = _encerrar_pid,
    ) -> None:
        self._registro = dados / PASTA_FERRAMENTAS / "llama.json"
        self._programa = programa
        self._modelo = modelo
        self._lancar = lancar
        self._encerrar = encerrar
        self._porta_livre = porta_livre
        self._agora = agora
        self._dormir = dormir
        self._comando_de = comando_de
        self._encerrar_pid = encerrar_pid
        self._trava = threading.Lock()
        self._filho: Filho | None = None
        self._pronto = ("", "")

    def subir(self) -> tuple[str, str]:
        with self._trava:
            if self._filho is not None and self._filho.poll() is None:
                return self._pronto
            self._filho = None
            self._encerrar_sobra()
            porta = self._porta_livre()
            chave = secrets.token_urlsafe(32)
            argv = argv_do_servidor(self._programa, self._modelo, porta)
            try:
                filho = self._lancar(argv, ambiente(chave))
            except OSError:
                raise FalhaLlama("programa_ausente") from None
            try:
                self._gravar(filho.pid, porta)
                self._esperar(filho, porta)
            except BaseException:
                self._encerrar(filho)
                self._registro.unlink(missing_ok=True)
                raise
            self._filho = filho
            self._pronto = (f"http://127.0.0.1:{porta}/v1", chave)
            return self._pronto

    def encerrar(self) -> None:
        with self._trava:
            if self._filho is not None:
                self._encerrar(self._filho)
                self._filho = None
            self._registro.unlink(missing_ok=True)

    def _esperar(self, filho: Filho, porta: int) -> None:
        inicio = self._agora()
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=2.0) as cliente:
            while True:
                if filho.poll() is not None:
                    raise FalhaLlama("programa_ausente")
                with contextlib.suppress(httpx.HTTPError):
                    if cliente.get(f"http://127.0.0.1:{porta}/health").status_code == 200:
                        if filho.poll() is not None:  # o 200 veio de outro na porta
                            raise FalhaLlama("programa_ausente")
                        return
                if self._agora() - inicio >= ESPERA_S:
                    raise FalhaLlama("tempo_esgotado")
                self._dormir(SONO_S)

    def _gravar(self, pid: int, porta: int) -> None:
        self._registro.parent.mkdir(parents=True, exist_ok=True)
        texto = json.dumps({"pid": pid, "porta": porta, "programa": str(self._programa)})
        temporario = self._registro.with_name("llama.json.tmp")
        temporario.unlink(missing_ok=True)
        fd = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _FLAGS, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texto)
        os.replace(temporario, self._registro)

    def _encerrar_sobra(self) -> None:
        try:
            sobra = json.loads(self._registro.read_text(encoding="utf-8"))
            pid, porta, programa = int(sobra["pid"]), int(sobra["porta"]), Path(sobra["programa"])
        except OSError, ValueError, TypeError, KeyError:
            return  # sem registro ou estragado: nada a encerrar
        if pid > 0 and e_o_nosso(self._comando_de(pid), programa, porta):
            self._encerrar_pid(pid)
        self._registro.unlink(missing_ok=True)
