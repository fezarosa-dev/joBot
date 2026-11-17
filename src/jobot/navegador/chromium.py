"""Chromium de um `chromium-<alvo>.tar.gz` conferido pelo sha256 (T330; D174.2 e D174.12).

Dois caminhos: o arquivo local da instalação pela casca e o mesmo arquivo baixado da release do
joBot da versão instalada, conferido contra o manifesto da instalação (nunca o CDN do Playwright).
Extrai com `tarfile` e `filter="data"` (guarda o `+x` e os symlinks relativos e recusa caminho
para fora) numa pasta temporária dentro do destino; só no fim as pastas vão para o lugar.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx

from jobot.nucleo.quebra import URL_REPOSITORIO

_LOG = logging.getLogger(__name__)

Progresso = Callable[[int, int | None], None]

HEX = re.compile(r"[0-9a-f]{64}")
_NOME = re.compile(r"chromium-[A-Za-z0-9_.-]+\.tar\.gz")
_BLOCO = 1 << 20
_PREFIXO = ".jobot-"


def pasta_do_playwright(ambiente: Mapping[str, str], plataforma: str) -> Path:
    """A pasta que o próprio Playwright usa em cada sistema (e a dele, se a pessoa mudou)."""
    if ambiente.get("PLAYWRIGHT_BROWSERS_PATH"):
        return Path(ambiente["PLAYWRIGHT_BROWSERS_PATH"])
    if plataforma == "win32":
        return Path(ambiente.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / (
            "ms-playwright"
        )
    casa = Path(ambiente["HOME"]) if ambiente.get("HOME") else Path.home()
    if plataforma == "darwin":
        return casa / "Library" / "Caches" / "ms-playwright"
    cache = Path(ambiente["XDG_CACHE_HOME"]) if ambiente.get("XDG_CACHE_HOME") else casa / ".cache"
    return cache / "ms-playwright"


def _sha256(arquivo: Path) -> str:
    soma = hashlib.sha256()
    with arquivo.open("rb") as entrada:
        while bloco := entrada.read(_BLOCO):
            soma.update(bloco)
    return soma.hexdigest()


def extrair(arquivo: Path, sha256: str, destino: Path, progresso: Progresso) -> bool:
    """Confere e extrai; qualquer erro deixa o destino como estava (sem nada pela metade)."""
    if _sha256(arquivo) != sha256:
        _LOG.warning("o sha256 de %s não confere", arquivo.name)
        return False
    destino.mkdir(parents=True, exist_ok=True)
    temporaria = Path(tempfile.mkdtemp(prefix=_PREFIXO, dir=destino))
    try:
        try:
            with tarfile.open(arquivo, "r:gz") as tar:
                membros = tar.getmembers()
                for feito, membro in enumerate(membros, start=1):
                    tar.extract(membro, temporaria, filter="data")
                    progresso(feito, len(membros))
        except tarfile.TarError, OSError:
            _LOG.exception("não deu para extrair %s", arquivo.name)
            return False
        for pasta in temporaria.iterdir():
            alvo = destino / pasta.name
            if alvo.is_dir() and not alvo.is_symlink():
                shutil.rmtree(alvo)  # instalação velha ou pela metade da mesma revisão
            elif alvo.exists() or alvo.is_symlink():
                alvo.unlink()
            os.replace(pasta, alvo)
        return True
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


def _entrada_do_chromium(manifesto: Path) -> tuple[str, int, str] | None:
    try:
        conteudo = json.loads(manifesto.read_text(encoding="utf-8"))
    except OSError, ValueError:
        _LOG.exception("não deu para ler o manifesto %s", manifesto)
        return None
    arquivos = conteudo.get("arquivos") if isinstance(conteudo, dict) else None
    for item in arquivos if isinstance(arquivos, list) else []:
        if not isinstance(item, dict):
            continue
        nome, tamanho, sha256 = item.get("nome"), item.get("tamanho"), item.get("sha256")
        if (
            isinstance(nome, str)
            and _NOME.fullmatch(nome)
            and isinstance(tamanho, int)
            and not isinstance(tamanho, bool)
            and tamanho > 0
            and isinstance(sha256, str)
            and HEX.fullmatch(sha256)
        ):
            return nome, tamanho, sha256
    _LOG.warning("o manifesto %s não lista o Chromium", manifesto)
    return None


def baixar_e_extrair(
    cliente: httpx.Client, manifesto: Path, versao: str, destino: Path, progresso: Progresso
) -> bool:
    """Baixa o Chromium da release `v<versao>` e o extrai se bater com o manifesto."""
    entrada = _entrada_do_chromium(manifesto)
    if entrada is None:
        return False
    nome, tamanho, sha256 = entrada
    url = f"{URL_REPOSITORIO}/releases/download/v{versao}/{nome}"
    destino.mkdir(parents=True, exist_ok=True)
    descritor, caminho = tempfile.mkstemp(prefix=_PREFIXO, suffix=".tar.gz", dir=destino)
    parcial = Path(caminho)
    try:
        with os.fdopen(descritor, "wb") as saida:
            with cliente.stream("GET", url) as resposta:
                if resposta.status_code != 200:
                    _LOG.warning("a release respondeu %s para %s", resposta.status_code, url)
                    return False
                feito = 0
                for bloco in resposta.iter_bytes(_BLOCO):
                    feito += len(bloco)
                    if feito > tamanho:
                        _LOG.warning("%s passou do tamanho do manifesto", nome)
                        return False
                    saida.write(bloco)
                    progresso(feito, tamanho)
        return extrair(parcial, sha256, destino, progresso)
    except httpx.HTTPError, OSError:
        _LOG.exception("não deu para baixar %s", url)
        return False
    finally:
        parcial.unlink(missing_ok=True)
