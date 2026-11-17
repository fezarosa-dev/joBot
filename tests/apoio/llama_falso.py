"""`llama-server` falso para `test_llama.py`: um servidor HTTP em thread em `127.0.0.1` (não um
processo), o filho falso que o lançador devolve e um relógio síncrono sem tempo real."""

import threading
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ServidorLlamaFalso:
    """`/health` responde `saude` (o último código se repete); `/v1/models` pede
    `Authorization: Bearer <chave>`, com a chave que o lançador falso leu do ambiente."""

    def __init__(self, saude: Sequence[int] = (200,)) -> None:
        self.saude = list(saude)
        self.chave: str | None = None
        self.caminhos: list[str] = []
        falso = self

        class _Tratador(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                falso.caminhos.append(self.path)
                if self.path == "/health":
                    codigo = falso.saude.pop(0) if len(falso.saude) > 1 else falso.saude[0]
                elif self.path == "/v1/models":
                    certa = falso.chave is not None and (
                        self.headers.get("Authorization") == f"Bearer {falso.chave}"
                    )
                    codigo = 200 if certa else 401
                else:
                    codigo = 404
                self.send_response(codigo)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args: object) -> None:
                pass

        self._http = ThreadingHTTPServer(("127.0.0.1", 0), _Tratador)
        self.porta: int = self._http.server_address[1]
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._thread.start()

    def fechar(self) -> None:
        self._http.shutdown()
        self._http.server_close()


class FilhoFalso:
    """O `Popen` do `llama-server`: vivo nas `vivo_por` primeiras perguntas (`None`: sempre);
    `vivo_por=0` é o filho que morreu antes da porta."""

    def __init__(self, pid: int, *, vivo_por: int | None = None) -> None:
        self.pid = pid
        self.vivo_por = vivo_por
        self.returncode: int | None = None

    def poll(self) -> int | None:
        if self.vivo_por is not None:
            if self.vivo_por <= 0:
                self.returncode = 1
            self.vivo_por -= 1
        return self.returncode


class LancadorFalso:
    """Grava o argv e o ambiente de cada subida e dá ao servidor falso a chave do caminho
    escolhido (`LLAMA_API_KEY` no ambiente)."""

    def __init__(self, servidor: ServidorLlamaFalso, *, vivo_por: int | None = None) -> None:
        self.servidor = servidor
        self.vivo_por = vivo_por
        self.subidas: list[tuple[list[str], dict[str, str]]] = []
        self.filhos: list[FilhoFalso] = []

    def __call__(self, argv: Sequence[str], env: Mapping[str, str]) -> FilhoFalso:
        self.subidas.append((list(argv), dict(env)))
        self.servidor.chave = env.get("LLAMA_API_KEY")
        filho = FilhoFalso(40000 + len(self.subidas), vivo_por=self.vivo_por)
        self.filhos.append(filho)
        return filho


class RelogioSincrono:
    """`agora` em segundos; `dormir` só avança a hora."""

    def __init__(self) -> None:
        self.t = 0.0

    def agora(self) -> float:
        return self.t

    def dormir(self, s: float) -> None:
        self.t += s
