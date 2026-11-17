import logging
import logging.handlers
import os
import stat
import sys
from collections.abc import Mapping
from pathlib import Path

_LOG = logging.getLogger(__name__)
_MODO_PASTA = 0o700
_MODO_ARQUIVO = 0o600
PASTA_NAVEGADOR = "navegador"
# A pasta da casca no Windows e no Mac (`<dados>/app`, D181.6): Python e venv com o `+x` deles.
PASTA_DA_CASCA = "app"


def pasta_de_dados(env: Mapping[str, str], plataforma: str = sys.platform) -> Path:
    """JOBOT_DADOS vence. Windows: %LOCALAPPDATA%\\joBot (ou ~\\AppData\\Local\\joBot).
    Mac: ~/Library/Application Support/joBot. Linux: $XDG_DATA_HOME/jobot, depois
    ~/.local/share/jobot."""
    if env.get("JOBOT_DADOS"):
        return Path(env["JOBOT_DADOS"])
    if plataforma == "win32":
        if env.get("LOCALAPPDATA"):
            return Path(env["LOCALAPPDATA"]) / "joBot"
        perfil = Path(env["USERPROFILE"]) if env.get("USERPROFILE") else Path.home()
        return perfil / "AppData" / "Local" / "joBot"
    if plataforma == "darwin":
        casa = Path(env["HOME"]) if env.get("HOME") else Path.home()
        return casa / "Library" / "Application Support" / "joBot"
    if env.get("XDG_DATA_HOME"):
        return Path(env["XDG_DATA_HOME"]) / "jobot"
    casa = Path(env["HOME"]) if env.get("HOME") else Path.home()
    return casa / ".local" / "share" / "jobot"


def _fechar(caminho: Path, modo: int) -> bool:
    if caminho.is_symlink():  # não seguir: o alvo pode estar fora da pasta de dados
        return False
    if stat.S_IMODE(caminho.stat().st_mode) == modo:
        return False
    caminho.chmod(modo)
    return True


def pasta_do_playwright(env: Mapping[str, str], plataforma: str = sys.platform) -> Path:
    """A pasta padrão dos navegadores do Playwright (D174.2): `PLAYWRIGHT_BROWSERS_PATH` vence.
    Windows: %LOCALAPPDATA%\\ms-playwright. Mac: ~/Library/Caches/ms-playwright. Linux:
    $XDG_CACHE_HOME/ms-playwright, depois ~/.cache/ms-playwright."""
    if env.get("PLAYWRIGHT_BROWSERS_PATH", "0") != "0":
        return Path(env["PLAYWRIGHT_BROWSERS_PATH"])
    casa = Path(env["HOME"]) if env.get("HOME") else Path.home()
    if plataforma == "win32":
        local = env.get("LOCALAPPDATA")
        return (Path(local) if local else casa / "AppData" / "Local") / "ms-playwright"
    if plataforma == "darwin":
        return casa / "Library" / "Caches" / "ms-playwright"
    cache = Path(env["XDG_CACHE_HOME"]) if env.get("XDG_CACHE_HOME") else casa / ".cache"
    return cache / "ms-playwright"


def preparar_pasta(p: Path) -> None:
    """Cria a pasta com 0700 e fecha pasta e arquivos frouxos (um log por correção)."""
    p.mkdir(mode=_MODO_PASTA, parents=True, exist_ok=True)
    corrigidos = [p] if _fechar(p, _MODO_PASTA) else []
    for dono, pastas, arquivos in os.walk(p):
        for nome in (PASTA_NAVEGADOR, PASTA_DA_CASCA):
            if Path(dono) == p and nome in pastas:
                # perfil do navegador e pasta da casca: só a pasta fecha; o conteúdo é do
                # navegador (e pode ser symlink) ou da casca (executáveis)
                pastas.remove(nome)
                corrigidos += [c] if _fechar(c := p / nome, _MODO_PASTA) else []
        corrigidos += [c for n in pastas if _fechar(c := Path(dono, n), _MODO_PASTA)]
        corrigidos += [c for n in arquivos if _fechar(c := Path(dono, n), _MODO_ARQUIVO)]
    if corrigidos:
        _LOG.warning("permissão frouxa corrigida em %d item(ns) de %s", len(corrigidos), p)


class _LogFechado(logging.handlers.RotatingFileHandler):
    """Arquivo novo (inclusive o da rotação) já nasce 0600, sem depender do umask."""

    def _open(self):  # type: ignore[no-untyped-def]
        fd = os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, _MODO_ARQUIVO)
        return os.fdopen(fd, self.mode, encoding=self.encoding)


def configurar_log(p: Path) -> None:
    pasta = p / "logs"
    pasta.mkdir(mode=_MODO_PASTA, parents=True, exist_ok=True)
    _fechar(pasta, _MODO_PASTA)
    alvo = str(pasta / "jobot.log")
    raiz = logging.getLogger("jobot")
    if any(isinstance(h, _LogFechado) and h.baseFilename == alvo for h in raiz.handlers):
        return
    h = _LogFechado(alvo, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    raiz.addHandler(h)
    raiz.setLevel(logging.INFO)
