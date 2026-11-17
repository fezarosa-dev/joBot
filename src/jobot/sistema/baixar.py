"""Download conferido das ferramentas do joBot (desenho 7; T404; D185.7 e D189).

`httpx` em fluxo para `<destino>.<12 primeiros do sha256>.parcial`, retomado com `Range` (200 no
lugar de 206 recomeça), cortado ao passar do tamanho do manifesto e conferido (tamanho e sha256)
antes do `os.replace`. Sem prazo total: 60 s sem bytes é `sem_rede`, e o `.parcial` fica para a
retomada. Saltos seguidos à mão, no máximo 5, cada um pela regra (só `https`). Uma trava de
arquivo por download: casca, painel e CLI não escrevem o mesmo `.parcial`.
"""

import hashlib
import json
import os
import shutil
import stat
import sys
import tarfile
import threading
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import httpx

from jobot import __version__
from jobot.nucleo.quebra import URL_REPOSITORIO
from jobot.sistema import instancia

# `ocupado`: outro download do mesmo arquivo prende a trava (D189).
Motivo = Literal["sem_rede", "espaco", "arquivo", "cancelado", "ocupado"]

INATIVIDADE_S = 60.0  # proposta do desenho 7
MAX_SALTOS = 5
_FLAGS = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


class FalhaBaixar(Exception):
    """`arquivo` apaga o `.parcial`; os outros motivos o mantêm para a retomada."""

    def __init__(self, motivo: Motivo) -> None:
        super().__init__(motivo)
        self.motivo: Motivo = motivo


def so_https(url: httpx.URL) -> bool:
    return url.scheme == "https"


def cliente_de_download() -> httpx.Client:
    """User agent fixo do joBot (ADR 0005); os saltos ficam com `baixar`; sem prazo total."""
    return httpx.Client(
        headers={"User-Agent": f"joBot/{__version__} (+{URL_REPOSITORIO})"},
        follow_redirects=False,
        timeout=httpx.Timeout(30.0, read=INATIVIDADE_S),
    )


def parcial_de(destino: Path, sha256: str) -> Path:
    return destino.with_name(f"{destino.name}.{sha256[:12]}.parcial")


def _livre(pasta: Path) -> int:
    return shutil.disk_usage(pasta).free


def baixar(
    url: str,
    destino: Path,
    *,
    tamanho: int,
    sha256: str,
    cliente: httpx.Client,
    progresso: Callable[[str], None] = lambda linha: None,
    etapa: str = "ia_local",
    cancelar: threading.Event | None = None,
    agora: Callable[[], float] = time.monotonic,
    livre: Callable[[Path], int] = _livre,
    aceita_salto: Callable[[httpx.URL], bool] = so_https,
) -> None:
    """Baixa `url` em `destino` só se tamanho e sha256 baterem; senão `FalhaBaixar`.

    `progresso` recebe linhas JSON `{"etapa", "feito", "total"}` (o protocolo do navegador)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = parcial_de(destino, sha256)
    fd = os.open(parcial.with_suffix(".trava"), os.O_RDWR | os.O_CREAT | _FLAGS, 0o600)
    if not instancia.prender(fd, compartilhada=False):
        os.close(fd)
        raise FalhaBaixar("ocupado")
    try:
        ja = parcial.stat().st_size if parcial.exists() else 0
        if ja > tamanho:
            parcial.unlink()
            ja = 0
        if livre(destino.parent) < tamanho - ja:
            raise FalhaBaixar("espaco")
        avisar = _avisador(progresso, etapa, tamanho)
        avisar(ja)
        if ja < tamanho:
            cabecalhos = {"Accept-Encoding": "identity"}  # bytes crus: o sha256 é do arquivo
            if ja:
                cabecalhos["Range"] = f"bytes={ja}-"
            pedido = cliente.build_request("GET", url, headers=cabecalhos)
            _receber(cliente, pedido, parcial, ja, tamanho, avisar, cancelar, agora, aceita_salto)
        if parcial.stat().st_size != tamanho or _sha256(parcial) != sha256:
            raise FalhaBaixar("arquivo")
        os.replace(parcial, destino)  # só depois de conferido
    except FalhaBaixar as falha:
        if falha.motivo == "arquivo":
            parcial.unlink(missing_ok=True)
        raise
    finally:
        instancia.fechar_trava(fd)


def _avisador(progresso: Callable[[str], None], etapa: str, total: int) -> Callable[[int], None]:
    """Uma linha a cada ponto percentual, e sempre a primeira e a do fim."""
    ultimo: list[int] = []

    def avisar(feito: int) -> None:
        ponto = feito * 100 // max(total, 1)
        if not ultimo or ponto != ultimo[0] or feito == total:
            ultimo[:] = [ponto]
            progresso(json.dumps({"etapa": etapa, "feito": feito, "total": total}))

    return avisar


def _abrir(
    cliente: httpx.Client, pedido: httpx.Request, aceita_salto: Callable[[httpx.URL], bool]
) -> httpx.Response:
    for _ in range(MAX_SALTOS + 1):
        resposta = cliente.send(pedido, stream=True)
        proximo = resposta.next_request
        if proximo is None:
            return resposta
        resposta.close()
        if not aceita_salto(proximo.url):
            raise FalhaBaixar("sem_rede")
        pedido = proximo
    raise FalhaBaixar("sem_rede")


def _receber(
    cliente: httpx.Client,
    pedido: httpx.Request,
    parcial: Path,
    ja: int,
    tamanho: int,
    avisar: Callable[[int], None],
    cancelar: threading.Event | None,
    agora: Callable[[], float],
    aceita_salto: Callable[[httpx.URL], bool],
) -> None:
    try:
        resposta = _abrir(cliente, pedido, aceita_salto)
        try:
            if resposta.status_code == 206 and ja:
                modo, feito = "ab", ja
            elif resposta.status_code == 200:
                modo, feito = "wb", 0  # o servidor ignorou o `Range`: recomeça
            else:
                raise FalhaBaixar("sem_rede")
            with parcial.open(modo) as saida:
                ultimo = agora()
                for bloco in resposta.iter_raw():
                    feito += len(bloco)
                    if feito > tamanho:
                        raise FalhaBaixar("arquivo")
                    saida.write(bloco)
                    avisar(feito)
                    if cancelar is not None and cancelar.is_set():
                        raise FalhaBaixar("cancelado")
                    momento = agora()
                    if momento - ultimo > INATIVIDADE_S:
                        raise FalhaBaixar("sem_rede")
                    ultimo = momento

        finally:
            resposta.close()
    except httpx.HTTPError as erro:
        raise FalhaBaixar("sem_rede") from erro


def _sha256(caminho: Path) -> str:
    with caminho.open("rb") as entrada:
        return hashlib.file_digest(entrada, "sha256").hexdigest()


def extrair(arquivo: Path, pasta: Path) -> None:
    """`.zip` com `zipfile`, recusando membro fora da pasta antes de extrair qualquer um;
    o resto como `.tar.gz` com `filter="data"`. Danificado ou fora: `arquivo`."""
    try:
        if arquivo.name.endswith(".zip"):
            with zipfile.ZipFile(arquivo) as zf:
                raiz = pasta.resolve()
                for nome in zf.namelist():
                    if not (raiz / nome).resolve().is_relative_to(raiz):
                        raise FalhaBaixar("arquivo")
                zf.extractall(pasta)
        else:
            with tarfile.open(arquivo, "r:gz") as tf:
                tf.extractall(pasta, filter="data")
    except (tarfile.TarError, zipfile.BadZipFile, OSError) as erro:
        raise FalhaBaixar("arquivo") from erro


def tornar_executavel(caminho: Path, plataforma: str = sys.platform) -> None:
    """`chmod +x` (só o dono) no Linux e no Mac; o `zipfile` não guarda o modo."""
    if plataforma != "win32":
        caminho.chmod(stat.S_IMODE(caminho.stat().st_mode) | stat.S_IXUSR)
