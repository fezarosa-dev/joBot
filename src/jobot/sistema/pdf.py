"""Leitura do currículo em PDF num processo filho (desenho 8 da fase 4; T435; D231).

O `pypdf` roda num filho (`python -P -m jobot.sistema.pdf`): uma thread não para um PDF
patológico, e o filho se encerra com `encerrar_arvore` passado o prazo de `PRAZO_S`. O PDF vai
pela entrada padrão e o texto volta em JSON pela saída: nada passa pelo disco, nem na pasta de
dados nem num temporário nosso. Lê até `MAX_PAGINAS`. Só este módulo importa o `pypdf`
(`test_camadas.py`). Os avisos (`Aviso`) têm texto em `configuracoes.perfil.curriculo.aviso.*`.
"""

import faulthandler
import io
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast, get_args

from jobot.sistema import processo

TETO_BYTES = 5 * 1024 * 1024  # o pedido inteiro, pelo `Content-Length` (desenho 8)
MAX_PAGINAS = 20
PRAZO_S = 30.0
TETO_TEXTO = 200_000  # caracteres que voltam do filho (o maior uso do desenho é 40000)
_FATIA_S = 0.25  # cada espera do `communicate`; o prazo conta pelo relógio injetado

Aviso = Literal["nao_pdf", "senha", "protegido", "corrompido", "so_imagem", "prazo"]
_AVISOS: tuple[str, ...] = get_args(Aviso)


@dataclass(frozen=True)
class Lido:
    texto: str
    paginas: int  # lidas
    total: int  # do arquivo


class AvisoPdf(Exception):
    def __init__(self, aviso: Aviso) -> None:
        super().__init__(aviso)
        self.aviso: Aviso = aviso


class Filho(Protocol):
    @property
    def pid(self) -> int: ...
    @property
    def returncode(self) -> int | None: ...
    def communicate(
        self, input: bytes | None = None, timeout: float | None = None
    ) -> tuple[bytes, Any]: ...


def ler_bytes(dados: bytes) -> dict[str, object]:
    """Roda no filho: o texto das primeiras páginas ou `{"aviso": ...}`."""
    import pypdf  # só no filho: o servidor não carrega o pypdf
    from pypdf.errors import DependencyError

    if b"%PDF-" not in dados[:1024]:  # o cabeçalho pode vir depois de lixo, até 1 KiB
        return {"aviso": "nao_pdf"}
    try:
        leitor = pypdf.PdfReader(io.BytesIO(dados))
        if leitor.is_encrypted and leitor.decrypt("") == pypdf.PasswordType.NOT_DECRYPTED:
            return {"aviso": "senha"}
        total = len(leitor.pages)
        paginas = [leitor.pages[i].extract_text() for i in range(min(total, MAX_PAGINAS))]
    except DependencyError:  # AES sem o `cryptography` (fora do Linux; D231.1)
        return {"aviso": "protegido"}
    except Exception:  # pypdf, recursão, memória: o PDF não se lê
        return {"aviso": "corrompido"}
    texto = "\n".join(paginas).strip()[:TETO_TEXTO]
    if not texto:
        return {"aviso": "so_imagem"}
    texto = texto.encode("utf-8", "replace").decode("utf-8")  # surrogate solto vira "?"
    return {"texto": texto, "paginas": len(paginas), "total": total}


def _lancar() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-P", "-m", "jobot.sistema.pdf"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # o pypdf avisa no log; não é da pessoa
        **processo.destacar(),
    )


def _encerrar(filho: Filho) -> None:
    processo.encerrar_arvore(cast("subprocess.Popen[Any]", filho))


def ler(
    dados: bytes,
    *,
    lancar: Callable[[], Filho] = _lancar,
    agora: Callable[[], float] = time.monotonic,
) -> Lido:
    """Lê o PDF no filho; `AvisoPdf` quando não dá (o motivo em `aviso`)."""
    filho = lancar()
    inicio = agora()
    entrada: bytes | None = dados
    try:
        while True:
            try:
                saida, _ = filho.communicate(entrada, timeout=_FATIA_S)
                break
            except subprocess.TimeoutExpired:
                entrada = None  # o PDF já foi; as esperas seguintes só leem a saída
                if agora() - inicio >= PRAZO_S:
                    raise AvisoPdf("prazo") from None
    except BaseException:  # prazo, Ctrl+C, cancelamento: o filho não fica para trás
        _encerrar(filho)
        raise
    return _resultado(saida, filho.returncode)


def _resultado(saida: bytes, codigo: int | None) -> Lido:
    try:
        resposta = json.loads(saida) if codigo == 0 else None
    except ValueError:
        resposta = None
    if isinstance(resposta, dict):
        aviso = resposta.get("aviso")
        if aviso in _AVISOS:
            raise AvisoPdf(cast(Aviso, aviso))
        texto, paginas, total = (resposta.get(k) for k in ("texto", "paginas", "total"))
        if isinstance(texto, str) and type(paginas) is int and type(total) is int:
            return Lido(texto=texto, paginas=paginas, total=total)
    raise AvisoPdf("corrompido")


def main() -> None:
    # vigia em C, fora do GIL: se o servidor morre sem levar o filho, ele sai mesmo assim
    faulthandler.dump_traceback_later(PRAZO_S + 5, exit=True)
    sys.stdout.write(json.dumps(ler_bytes(sys.stdin.buffer.read())))


if __name__ == "__main__":
    main()
