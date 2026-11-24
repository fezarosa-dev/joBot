"""Download conferido (T404; desenho 7): servidor em thread em 127.0.0.1, relógio injetado."""

import errno
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import threading
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from jobot import __version__
from jobot.nucleo.quebra import URL_REPOSITORIO
from jobot.sistema import instancia
from jobot.sistema.baixar import (
    INATIVIDADE_S,
    FalhaBaixar,
    baixar,
    cliente_de_download,
    extrair,
    parcial_de,
    so_https,
    tornar_executavel,
)

CORPO = bytes(range(256)) * 400  # 100 KiB
SHA = hashlib.sha256(CORPO).hexdigest()

Rota = Callable[[BaseHTTPRequestHandler], None]


@dataclass
class Servidor:
    porta: int
    rotas: dict[str, Rota] = field(default_factory=dict)
    pedidos: list[tuple[str, str | None]] = field(default_factory=list)

    def url(self, caminho: str) -> str:
        return f"http://127.0.0.1:{self.porta}{caminho}"


@pytest.fixture
def servidor() -> Iterator[Servidor]:
    estado = Servidor(0)

    class Resposta(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            estado.pedidos.append((self.path, self.headers.get("Range")))
            estado.rotas[self.path](self)

        def log_message(self, *args: object) -> None:
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Resposta)
    estado.porta = http.server_address[1]
    fio = threading.Thread(target=http.serve_forever, args=(0.01,), daemon=True)
    fio.start()
    try:
        yield estado
    finally:
        http.shutdown()
        http.server_close()
        fio.join()


def arquivo(corpo: bytes = CORPO, *, aceita_range: bool = True) -> Rota:
    def rota(h: BaseHTTPRequestHandler) -> None:
        pedido = h.headers.get("Range")
        if pedido and aceita_range:
            inicio = int(pedido.removeprefix("bytes=").split("-")[0])
            h.send_response(206)
            h.send_header("Content-Range", f"bytes {inicio}-{len(corpo) - 1}/{len(corpo)}")
            parte = corpo[inicio:]
        else:
            h.send_response(200)
            parte = corpo
        h.send_header("Content-Length", str(len(parte)))
        h.end_headers()
        h.wfile.write(parte)

    return rota


def salto(para: str) -> Rota:
    def rota(h: BaseHTTPRequestHandler) -> None:
        h.send_response(302)
        h.send_header("Location", para)
        h.send_header("Content-Length", "0")
        h.end_headers()

    return rota


@pytest.fixture
def cliente() -> Iterator[httpx.Client]:
    with httpx.Client(follow_redirects=False) as c:
        yield c


def _baixar(servidor: Servidor, cliente: httpx.Client, destino: Path, **kw: object) -> None:
    opcoes: dict[str, object] = {
        "tamanho": len(CORPO),
        "sha256": SHA,
        "cliente": cliente,
        "livre": lambda p: 1 << 40,
        "aceita_url": lambda u: True,
    }
    opcoes.update(kw)
    baixar(servidor.url("/f"), destino, **opcoes)  # type: ignore[arg-type]


def _motivo(funcao: Callable[[], None]) -> str:
    with pytest.raises(FalhaBaixar) as erro:
        funcao()
    return erro.value.motivo


# --- baixar e conferir ---------------------------------------------------------------------


def test_baixa_e_confere(servidor: Servidor, cliente: httpx.Client, tmp_path: Path) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "modelos" / "m.gguf"
    _baixar(servidor, cliente, destino)
    assert destino.exists()
    assert destino.read_bytes() == CORPO
    assert not parcial_de(destino, SHA).exists()
    assert servidor.pedidos == [("/f", None)]


def test_parcial_tem_o_sha_no_nome(tmp_path: Path) -> None:
    assert parcial_de(tmp_path / "m.gguf", SHA) == tmp_path / f"m.gguf.{SHA[:12]}.parcial"


def test_retoma_o_parcial_com_range(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    parcial_de(destino, SHA).write_bytes(CORPO[:1000])
    _baixar(servidor, cliente, destino)
    assert servidor.pedidos == [("/f", "bytes=1000-")]
    assert destino.read_bytes() == CORPO


def test_200_a_um_range_recomeca(servidor: Servidor, cliente: httpx.Client, tmp_path: Path) -> None:
    servidor.rotas["/f"] = arquivo(aceita_range=False)
    destino = tmp_path / "m.gguf"
    parcial_de(destino, SHA).write_bytes(CORPO[:1000])
    _baixar(servidor, cliente, destino)
    assert servidor.pedidos == [("/f", "bytes=1000-")]
    assert destino.read_bytes() == CORPO


def test_sha_errado_apaga_o_parcial(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = arquivo(CORPO[:-1] + b"\x00")
    destino = tmp_path / "m.gguf"
    assert _motivo(lambda: _baixar(servidor, cliente, destino)) == "arquivo"
    assert not parcial_de(destino, SHA).exists()
    assert not destino.exists()


def test_so_troca_depois_de_conferir(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    # (guarda) o arquivo errado nunca chega ao destino, nem por um instante que deixe sobra;
    # controle: o certo chega
    servidor.rotas["/f"] = arquivo(CORPO[:-1] + b"\x00")
    servidor.rotas["/certo"] = arquivo()
    destino = tmp_path / "m.gguf"
    destino.write_bytes(b"versao velha")
    assert _motivo(lambda: _baixar(servidor, cliente, destino)) == "arquivo"
    assert destino.read_bytes() == b"versao velha"
    baixar(
        servidor.url("/certo"),
        destino,
        tamanho=len(CORPO),
        sha256=SHA,
        cliente=cliente,
        livre=lambda p: 1 << 40,
        aceita_url=lambda u: True,
    )
    assert destino.read_bytes() == CORPO


def test_corpo_maior_que_o_tamanho_e_cortado(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = arquivo(CORPO + b"x" * 5000)
    destino = tmp_path / "m.gguf"
    linhas: list[str] = []
    motivo = _motivo(lambda: _baixar(servidor, cliente, destino, progresso=linhas.append))
    assert motivo == "arquivo"
    assert linhas
    assert max(json.loads(linha)["feito"] for linha in linhas) <= len(CORPO)
    assert not parcial_de(destino, SHA).exists()
    assert not destino.exists()


def test_sem_espaco_antes_de_baixar(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    vistos: list[Path] = []

    def livre(p: Path) -> int:
        vistos.append(p)
        return len(CORPO) - 1

    assert _motivo(lambda: _baixar(servidor, cliente, destino, livre=livre)) == "espaco"
    assert vistos == [tmp_path]
    assert servidor.pedidos == []
    # controle: com o parcial já pela metade, o que falta cabe
    parcial_de(destino, SHA).write_bytes(CORPO[:10])
    _baixar(servidor, cliente, destino, livre=livre)
    assert destino.read_bytes() == CORPO


def test_60_s_sem_bytes_e_sem_rede_e_mantem_o_parcial(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    horas = iter([0.0, 61.0])
    motivo = _motivo(lambda: _baixar(servidor, cliente, destino, agora=lambda: next(horas)))
    assert motivo == "sem_rede"
    assert parcial_de(destino, SHA).exists()
    guardado = parcial_de(destino, SHA).read_bytes()
    assert guardado
    assert CORPO.startswith(guardado)
    assert not destino.exists()
    # controle: 60 s cravados ainda não é inatividade
    horas_ok = iter([0.0] + [60.0 * n for n in range(1, 10_000)])
    _baixar(servidor, cliente, destino, agora=lambda: next(horas_ok))
    assert destino.read_bytes() == CORPO


def test_cliente_de_download_tem_prazo_de_leitura_ua_e_nao_segue_saltos() -> None:
    # (guarda) o silêncio total só acaba pelo prazo de leitura: `read=None` prende para sempre
    with cliente_de_download() as c:
        assert INATIVIDADE_S == 60.0
        assert c.timeout.read == INATIVIDADE_S
        assert c.follow_redirects is False
        assert c.headers["User-Agent"] == f"joBot/{__version__} (+{URL_REPOSITORIO})"


class _ParaNoMeio(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield CORPO[:1000]
        raise httpx.ReadTimeout("parado")


def test_silencio_no_meio_e_sem_rede_e_mantem_o_parcial(tmp_path: Path) -> None:
    # o `ReadTimeout` é o que o prazo de leitura de `cliente_de_download` levanta
    def responde(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=_ParaNoMeio())

    destino = tmp_path / "m.gguf"
    with httpx.Client(transport=httpx.MockTransport(responde)) as c:
        motivo = _motivo(
            lambda: baixar(
                "https://x.test/f",
                destino,
                tamanho=len(CORPO),
                sha256=SHA,
                cliente=c,
                livre=lambda p: 1 << 40,
            )
        )
    assert motivo == "sem_rede"
    assert parcial_de(destino, SHA).read_bytes() == CORPO[:1000]


def test_corpo_curto_sem_erro_e_sem_rede_e_mantem_o_parcial(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    def curto(h: BaseHTTPRequestHandler) -> None:  # sem Content-Length: o fim é o fechamento
        h.send_response(200)
        h.end_headers()
        h.wfile.write(CORPO[:1000])

    servidor.rotas["/f"] = curto
    destino = tmp_path / "m.gguf"
    assert _motivo(lambda: _baixar(servidor, cliente, destino)) == "sem_rede"
    assert parcial_de(destino, SHA).read_bytes() == CORPO[:1000]
    assert not destino.exists()
    # controle: a retomada completa
    servidor.rotas["/f"] = arquivo()
    _baixar(servidor, cliente, destino)
    assert destino.read_bytes() == CORPO


@pytest.mark.parametrize(
    ("numero", "esperado", "fica"), [(errno.ENOSPC, "espaco", True), (errno.EIO, "arquivo", False)]
)
def test_erro_de_disco_no_meio_fica_nos_motivos(
    servidor: Servidor,
    cliente: httpx.Client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    numero: int,
    esperado: str,
    fica: bool,
) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    original = Path.open

    class Cheio:
        def __init__(self, real: io.IOBase) -> None:
            self.real = real

        def __enter__(self) -> Cheio:
            return self

        def __exit__(self, *erro: object) -> None:
            self.real.close()

        def write(self, bloco: bytes) -> int:
            raise OSError(numero, os.strerror(numero))

    def abre(self: Path, mode: str = "r", *args: object, **kw: object) -> object:
        real = original(self, mode, *args, **kw)  # type: ignore[call-overload]
        return Cheio(real) if self.name.endswith(".parcial") and "b" in mode else real

    monkeypatch.setattr(Path, "open", abre)
    with pytest.raises((FalhaBaixar, OSError)) as erro:  # o velho deixava sair o `OSError`
        _baixar(servidor, cliente, destino)
    assert getattr(erro.value, "motivo", None) == esperado
    assert parcial_de(destino, SHA).exists() is fica
    assert not destino.exists()


def test_progresso_que_quebra_no_meio_mantem_o_parcial(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    """O servidor do painel morreu: o `print` do andamento levanta `BrokenPipeError`, que não é
    erro do disco e não apaga o que já veio (D223.1)."""
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    linhas: list[str] = []

    def progresso(linha: str) -> None:
        if linhas:
            raise BrokenPipeError(errno.EPIPE, os.strerror(errno.EPIPE))
        linhas.append(linha)  # a primeira, antes do pedido, passa

    with pytest.raises((BrokenPipeError, FalhaBaixar)) as erro:  # o velho virava `arquivo`
        _baixar(servidor, cliente, destino, progresso=progresso)
    assert parcial_de(destino, SHA).exists()
    assert parcial_de(destino, SHA).stat().st_size > 0
    assert isinstance(erro.value, BrokenPipeError)
    assert not destino.exists()


def test_erro_de_conexao_e_sem_rede(tmp_path: Path) -> None:
    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("parado", request=pedido)

    with httpx.Client(transport=httpx.MockTransport(cai)) as c:
        motivo = _motivo(
            lambda: baixar(
                "https://x.test/f",
                tmp_path / "m",
                tamanho=1,
                sha256=SHA,
                cliente=c,
                livre=lambda p: 1 << 40,
            )
        )
    assert motivo == "sem_rede"


def test_http_404_e_sem_rede(servidor: Servidor, cliente: httpx.Client, tmp_path: Path) -> None:
    def nao_tem(h: BaseHTTPRequestHandler) -> None:
        h.send_error(404)

    servidor.rotas["/f"] = nao_tem
    assert _motivo(lambda: _baixar(servidor, cliente, tmp_path / "m")) == "sem_rede"


def test_cancelar_mantem_o_parcial(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    parcial_de(destino, SHA).write_bytes(CORPO[:1000])
    cancelar = threading.Event()
    cancelar.set()
    assert _motivo(lambda: _baixar(servidor, cliente, destino, cancelar=cancelar)) == "cancelado"
    assert servidor.pedidos == []  # já marcado: nenhum pedido à rede
    assert parcial_de(destino, SHA).exists()
    assert parcial_de(destino, SHA).read_bytes()[:1000] == CORPO[:1000]
    assert not destino.exists()


# --- saltos --------------------------------------------------------------------------------


def test_url_inicial_http_recusada(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    motivo = _motivo(lambda: _baixar(servidor, cliente, destino, aceita_url=so_https))
    assert motivo == "sem_rede"
    assert servidor.pedidos == []
    # controle: com a regra que aceita o `http` local, baixa
    _baixar(servidor, cliente, destino)
    assert destino.read_bytes() == CORPO


def test_salto_recusado_mesmo_com_cliente_que_segue_saltos(
    servidor: Servidor, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = salto("/b")
    servidor.rotas["/b"] = arquivo()
    destino = tmp_path / "m.gguf"
    with httpx.Client(follow_redirects=True) as segue:
        motivo = _motivo(
            lambda: _baixar(servidor, segue, destino, aceita_url=lambda u: u.path == "/f")
        )
        assert motivo == "sem_rede"
        assert [p for p, _ in servidor.pedidos] == ["/f"]
        # controle: com a regra que aceita o salto, ele é seguido
        _baixar(servidor, segue, destino)
    assert destino.read_bytes() == CORPO


def test_so_https_aceita_https() -> None:
    assert so_https(httpx.URL("https://github.com/x"))
    assert not so_https(httpx.URL("http://github.com/x"))


def _cadeia(servidor: Servidor, n: int) -> None:
    for i in range(n):
        servidor.rotas["/f" if i == 0 else f"/s{i}"] = salto(f"/s{i + 1}")
    servidor.rotas["/f" if n == 0 else f"/s{n}"] = arquivo()


def test_cinco_saltos_passam(servidor: Servidor, cliente: httpx.Client, tmp_path: Path) -> None:
    _cadeia(servidor, 5)
    destino = tmp_path / "m.gguf"
    parcial_de(destino, SHA).write_bytes(CORPO[:10])
    _baixar(servidor, cliente, destino)
    assert destino.exists()
    assert destino.read_bytes() == CORPO
    assert len(servidor.pedidos) == 6
    assert {r for _, r in servidor.pedidos} == {"bytes=10-"}  # o Range segue os saltos


def test_seis_saltos_recusados(servidor: Servidor, cliente: httpx.Client, tmp_path: Path) -> None:
    _cadeia(servidor, 6)
    assert _motivo(lambda: _baixar(servidor, cliente, tmp_path / "m")) == "sem_rede"
    assert len(servidor.pedidos) == 6


# --- trava e progresso ---------------------------------------------------------------------


def test_trava_tomada_recusa(servidor: Servidor, cliente: httpx.Client, tmp_path: Path) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    trava = parcial_de(destino, SHA).with_suffix(".trava")
    fd = os.open(trava, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        assert instancia.prender(fd, compartilhada=False)
        assert _motivo(lambda: _baixar(servidor, cliente, destino)) == "ocupado"
        assert servidor.pedidos == []
    finally:
        instancia.fechar_trava(fd)
    # controle: solta a trava, o download anda
    _baixar(servidor, cliente, destino)
    assert destino.read_bytes() == CORPO


def test_progresso_em_linhas_json(
    servidor: Servidor, cliente: httpx.Client, tmp_path: Path
) -> None:
    servidor.rotas["/f"] = arquivo()
    destino = tmp_path / "m.gguf"
    parcial_de(destino, SHA).write_bytes(CORPO[:1000])
    linhas: list[str] = []
    _baixar(servidor, cliente, destino, progresso=linhas.append)
    lidas = [json.loads(linha) for linha in linhas]
    assert len(lidas) >= 2
    assert lidas[0] == {"etapa": "ia_local", "feito": 1000, "total": len(CORPO)}
    assert lidas[-1] == {"etapa": "ia_local", "feito": len(CORPO), "total": len(CORPO)}
    feitos = [linha["feito"] for linha in lidas]
    assert feitos == sorted(feitos)
    assert all("\n" not in linha for linha in linhas)


# --- extrair e +x --------------------------------------------------------------------------


def _tar(destino: Path, membros: dict[str, bytes]) -> Path:
    with tarfile.open(destino, "w:gz") as tf:
        for nome, conteudo in membros.items():
            info = tarfile.TarInfo(nome)
            info.size = len(conteudo)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(conteudo))
    return destino


def _zip(destino: Path, membros: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(destino, "w") as zf:
        for nome, conteudo in membros.items():
            zf.writestr(nome, conteudo)
    return destino


def test_extrai_tar_gz(tmp_path: Path) -> None:
    pacote = _tar(tmp_path / "l.tar.gz", {"build/bin/llama-server": b"ELF"})
    extrair(pacote, tmp_path / "llama")
    programa = tmp_path / "llama" / "build" / "bin" / "llama-server"
    assert programa.exists()
    assert programa.read_bytes() == b"ELF"


def test_tar_gz_com_caminho_para_fora_recusado(tmp_path: Path) -> None:
    pacote = _tar(tmp_path / "l.tar.gz", {"../fora.txt": b"x"})
    (tmp_path / "llama").mkdir()
    assert _motivo(lambda: extrair(pacote, tmp_path / "llama")) == "arquivo"
    assert not (tmp_path / "fora.txt").exists()


def test_extrai_zip(tmp_path: Path) -> None:
    pacote = _zip(tmp_path / "l.zip", {"llama-server.exe": b"MZ", "ggml.dll": b"MZ"})
    extrair(pacote, tmp_path / "llama")
    assert (tmp_path / "llama" / "llama-server.exe").exists()
    assert (tmp_path / "llama" / "llama-server.exe").read_bytes() == b"MZ"


@pytest.mark.parametrize("nome", ["../fora.txt", "a/../../fora.txt", "/abs/fora.txt"])
def test_zip_com_caminho_para_fora_recusado(tmp_path: Path, nome: str) -> None:
    pacote = _zip(tmp_path / "l.zip", {"bom.txt": b"x", nome: b"x"})
    (tmp_path / "llama").mkdir()
    assert _motivo(lambda: extrair(pacote, tmp_path / "llama")) == "arquivo"
    assert list((tmp_path / "llama").iterdir()) == []  # nada sai antes da conferência
    assert not (tmp_path / "fora.txt").exists()


def test_zip_danificado_e_arquivo(tmp_path: Path) -> None:
    pacote = tmp_path / "l.zip"
    pacote.write_bytes(b"nao e zip")
    assert _motivo(lambda: extrair(pacote, tmp_path / "llama")) == "arquivo"


@pytest.mark.skipif(sys.platform == "win32", reason="modo do POSIX")
@pytest.mark.parametrize("plataforma", ["linux", "darwin"])
def test_chmod_mais_x_no_linux_e_no_mac(tmp_path: Path, plataforma: str) -> None:
    programa = tmp_path / "llama-server"
    programa.write_bytes(b"ELF")
    programa.chmod(0o600)
    tornar_executavel(programa, plataforma)
    assert stat.S_IMODE(programa.stat().st_mode) == 0o700


@pytest.mark.skipif(sys.platform == "win32", reason="modo do POSIX")
def test_sem_chmod_no_windows(tmp_path: Path) -> None:
    programa = tmp_path / "llama-server.exe"
    programa.write_bytes(b"MZ")
    programa.chmod(0o600)
    tornar_executavel(programa, "win32")
    assert stat.S_IMODE(programa.stat().st_mode) == 0o600
