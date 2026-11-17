"""Segredo da parada local: `<dados>/sair.token` (desenho 6.1, T326).

O `serve` grava um segredo novo a cada subida e o apaga no fim; o `POST /sair` aceita o
cabeçalho `X-Jobot-Sair` com ele, só de `127.0.0.1`, no lugar do CSRF. É o caminho do
`jobot sair` no Windows, onde não há SIGTERM. O segredo nunca vai ao log nem a mensagem.
"""

import os
import secrets
from pathlib import Path

NOME = "sair.token"
CABECALHO = "X-Jobot-Sair"
_ABRIR_TMP = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_BINARY", 0)
)


def gravar_token(dados: Path) -> str:
    """Segredo novo num `.tmp` 0600, trocado por `os.replace` (queda não deixa meio arquivo)."""
    segredo = secrets.token_urlsafe(32)
    caminho = dados / NOME
    tmp = caminho.with_name(NOME + ".tmp")
    tmp.unlink(missing_ok=True)  # resto de queda anterior
    fd = os.open(tmp, _ABRIR_TMP, 0o600)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(segredo.encode("ascii"))
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(tmp, caminho)
    except BaseException:  # também Ctrl+C: o .tmp leva o segredo e não pode ficar
        tmp.unlink(missing_ok=True)
        raise
    return segredo


def ler_token(dados: Path) -> str | None:
    """O segredo gravado pelo `serve`; sem arquivo (ou ilegível), None."""
    try:
        segredo = (dados / NOME).read_text(encoding="ascii").strip()
    except OSError, UnicodeDecodeError:
        return None
    return segredo or None


def apagar_token(dados: Path) -> None:
    (dados / NOME).unlink(missing_ok=True)
    (dados / (NOME + ".tmp")).unlink(missing_ok=True)
