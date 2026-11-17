"""Canal `casca` do `jobot atualizar`: o pacote de atualização e o venv novo (plano T331).

Desenho 6.2 e 6.3; D174.3, D174.8, D174.13 e D174.14. Quem instalou pela casca tem
`<dados>/instalacao.json`. A atualização baixa da release `latest` o `SHA256SUMS` e o
`jobot-atualizacao-<versão>-<alvo>.zip` (da tag `v<versão>` achada no `SHA256SUMS`), confere o
pacote contra o `SHA256SUMS` e cada arquivo de dentro contra o `manifesto.json` dele, e monta
`venvs/venv-<versão>` ao lado, offline, com o `uv` da casca. A troca (parar, trocar o ponteiro,
religar) é do `atualizar.py`; aqui fica o que não mexe no servidor.

Formato do pacote (escolha do redator, D174.16, para confirmar): na raiz do `.zip`,
`manifesto.json` (`{"versao": "N.N.N", "arquivos": [{"nome", "tamanho", "sha256"}]}`),
`restricoes.txt` (com hash de tudo, o joBot inclusive), `wheels/*.whl` (a do joBot também) e um
`python/<nome>.tar.gz` (o `install_only` do python-build-standalone). O navegador não vem da
release (D183.24): com o Chromium do Playwright instalado, o venv novo roda o `playwright install`
da versão dele antes da troca (D174.13).
"""

import hashlib
import io
import json
import logging
import os
import platform
import re
import shutil
import sqlite3
import sys
import tarfile
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, BinaryIO

import httpx

from jobot import __version__
from jobot.nucleo.quebra import URL_REPOSITORIO
from jobot.sistema.pastas import pasta_do_playwright
from jobot.sistema.segundo_plano_linux import Resultado, Rodar

log = logging.getLogger(__name__)

ARQUIVO = "instalacao.json"
URL_LATEST = f"{URL_REPOSITORIO}/releases/latest/download"
URL_TAG = f"{URL_REPOSITORIO}/releases/download"
_TETO_SOMAS = 64 * 1024
_TETO_PACOTE = 2 * 1024**3
_BLOCO = 1024 * 1024
_VERSAO = r"[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9}"
_SHA = re.compile(r"[0-9a-f]{64}")
# caminho relativo com barra, sem `..`, sem barra invertida nem dois-pontos (nome do Windows)
_NOME = re.compile(r"[A-Za-z0-9_+][A-Za-z0-9._+-]*(?:/[A-Za-z0-9_+][A-Za-z0-9._+-]*)*")
# alvo = tripla do Rust que a casca usa no nome dos arquivos da release (D174.16)
_ALVOS: Mapping[tuple[str, str], str] = {
    ("linux", "x86_64"): "x86_64-unknown-linux-gnu",
    ("linux", "aarch64"): "aarch64-unknown-linux-gnu",
    ("win32", "amd64"): "x86_64-pc-windows-msvc",
    ("win32", "x86_64"): "x86_64-pc-windows-msvc",
    ("darwin", "arm64"): "aarch64-apple-darwin",
    ("darwin", "x86_64"): "x86_64-apple-darwin",
}


class Falha(Exception):
    """Motivo, para a pessoa, de a atualização não seguir; a instalação atual não mudou."""


@dataclass(frozen=True)
class Preparada:
    """O venv novo montado e provado, ainda sem a troca."""

    versao: str
    venv: Path
    python: Path  # o do venv novo, que sobe o servidor
    jobot: Path  # o executável do venv novo (`segundo-plano ligar`)
    python_novo: Path | None  # a pasta do Python extraída agora (apagada se a troca não sair)
    manifesto: bytes
    navegador_desatualizado: bool


def alvo_atual(plataforma: str = sys.platform, maquina: str | None = None) -> str | None:
    maquina = (maquina if maquina is not None else platform.machine()).lower()
    return _ALVOS.get(("linux" if plataforma.startswith("linux") else plataforma, maquina))


def no_venv(venv: Path, nome: str, plataforma: str = sys.platform) -> Path:
    if plataforma == "win32":
        return venv / "Scripts" / f"{nome}.exe"
    return venv / "bin" / nome


def _interpretador(pasta_python: Path, plataforma: str) -> Path:
    """O `install_only` do python-build-standalone extrai tudo dentro de `python/`."""
    if plataforma == "win32":
        return pasta_python / "python" / "python.exe"
    return pasta_python / "python" / "bin" / "python3"


def tem_instalacao(dados: Path) -> bool:
    return (dados / ARQUIVO).is_file()


def ler_instalacao(dados: Path) -> dict[str, Any]:
    """O `instalacao.json` conferido; `Falha` se falta campo ou está danificado."""
    try:
        conteudo = json.loads((dados / ARQUIVO).read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise Falha(
            f"Não consegui ler {dados / ARQUIVO} ({erro}). Instale o joBot de novo pelo instalador."
        ) from erro
    obrigatorios = ("pasta", "uv", "venv", "manifesto")
    if (
        not isinstance(conteudo, dict)
        or conteudo.get("canal") != "casca"
        or not all(isinstance(conteudo.get(c), str) and conteudo[c] for c in obrigatorios)
    ):
        raise Falha(
            f"O arquivo {dados / ARQUIVO} não é o que o instalador grava. "
            "Instale o joBot de novo pelo instalador."
        )
    return conteudo


def gravar_instalacao(dados: Path, conteudo: Mapping[str, Any]) -> None:
    _gravar(dados / ARQUIVO, json.dumps(conteudo, ensure_ascii=False, indent=2).encode())


def _gravar(destino: Path, conteudo: bytes) -> None:
    """`.tmp` com `O_EXCL` e 0600 na mesma pasta, `fsync` e `os.replace` (atômico)."""
    tmp = destino.with_name(f"{destino.name}.tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(tmp, destino)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def navegador_desatualizado(dados: Path) -> bool:
    """A marca da D174.13 (para a tela Ferramentas); sem instalação pela casca, `False`."""
    try:
        return (
            tem_instalacao(dados) and ler_instalacao(dados).get("navegador_desatualizado") is True
        )
    except Falha:
        return False


def tirar_marca_do_navegador(dados: Path) -> None:
    """Depois de baixar o navegador de novo; sem instalação pela casca, nada a fazer."""
    if not navegador_desatualizado(dados):
        return
    conteudo = ler_instalacao(dados)
    conteudo["navegador_desatualizado"] = False
    gravar_instalacao(dados, conteudo)


def versao_do_banco(dados: Path) -> int:
    """`PRAGMA user_version` do `jobot.db`, só lendo; sem banco, 0; `Falha` se não lê."""
    banco = dados / "jobot.db"
    if not banco.is_file():
        return 0
    try:
        con = sqlite3.connect(f"{banco.resolve().as_uri()}?mode=ro", uri=True)
        try:
            versao: int = con.execute("PRAGMA user_version").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error as erro:
        raise Falha(f"Não consegui ler o banco {banco} ({erro}); nada mudou.") from erro
    return versao


def voltar_a_anterior(dados: Path) -> None:
    """Troca o ponteiro de volta para o venv anterior (D174.3 e D174.14); `Falha` se não dá.

    Só troca o `instalacao.json`: quem chama para e religa o servidor. Recusa se o banco já
    foi migrado pela versão nova (o `user_version` mudou desde a troca), porque o joBot velho
    não abriria o esquema novo e a cópia `.antes-vN` perderia as vagas coletadas depois.
    """
    conteudo = ler_instalacao(dados)
    anterior, manifesto = conteudo.get("anterior"), conteudo.get("manifesto_anterior")
    if not isinstance(anterior, str) or not anterior or not Path(anterior).is_dir():
        raise Falha("Não há versão anterior guardada para voltar.")
    gravada = conteudo.get("user_version")
    atual = versao_do_banco(dados)
    if gravada != atual:
        raise Falha(
            f"O banco já foi atualizado pela versão nova (esquema {gravada} virou {atual}); "
            "a versão anterior não o abre. Nada mudou."
        )
    conteudo["venv"], conteudo["anterior"] = anterior, conteudo["venv"]
    if isinstance(manifesto, str) and manifesto:
        conteudo["manifesto"], conteudo["manifesto_anterior"] = manifesto, conteudo["manifesto"]
    gravar_instalacao(dados, conteudo)


# --- baixar e conferir --------------------------------------------------------------------


def cliente_de_download() -> httpx.Client:
    """Cliente real: user agent fixo do joBot (ADR 0005), segue o salto do GitHub para o CDN."""
    return httpx.Client(
        headers={"User-Agent": f"joBot/{__version__} (+{URL_REPOSITORIO})"},
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, read=120.0),
    )


def _baixar(cliente: httpx.Client, url: str, destino: BinaryIO, teto: int) -> str:
    """Escreve o corpo em `destino` e devolve o sha256; `Falha` sem 200 ou acima do teto."""
    soma = hashlib.sha256()
    lidos = 0
    try:
        with cliente.stream("GET", url) as resposta:
            if resposta.status_code != 200:
                raise Falha(f"Não consegui baixar {url} (HTTP {resposta.status_code}).")
            for bloco in resposta.iter_bytes(_BLOCO):
                lidos += len(bloco)
                if lidos > teto:
                    raise Falha(f"{url} é maior que o esperado; nada mudou.")
                soma.update(bloco)
                destino.write(bloco)
    except httpx.HTTPError as erro:
        raise Falha(
            f"Não consegui baixar {url} ({erro}). Confira a internet e tente de novo."
        ) from erro
    return soma.hexdigest()


def _versao(texto: str) -> tuple[int, ...]:
    return tuple(int(parte) for parte in texto.split("."))


def _achar_pacote(somas: str, alvo: str) -> tuple[str, str, str]:
    """(versão, nome do pacote, sha256) no `SHA256SUMS`; `Falha` sem pacote para o alvo."""
    padrao = re.compile(rf"jobot-atualizacao-({_VERSAO})-{re.escape(alvo)}\.zip")
    for linha in somas.splitlines():
        partes = linha.split()
        if len(partes) != 2 or not _SHA.fullmatch(partes[0]):
            continue
        nome = partes[1].removeprefix("*")
        if achado := padrao.fullmatch(nome):
            return achado[1], nome, partes[0]
    raise Falha(f"A versão mais nova não tem pacote de atualização para {alvo}.")


def _ler_manifesto(conteudo: bytes, versao: str) -> dict[str, tuple[int, str]]:
    """{nome: (tamanho, sha256)}; `Falha` se o formato ou a versão não batem."""
    try:
        dados = json.loads(conteudo)
    except ValueError as erro:
        raise Falha("O manifesto do pacote de atualização está danificado; nada mudou.") from erro
    arquivos = dados.get("arquivos") if isinstance(dados, dict) else None
    if (
        not isinstance(dados, dict)
        or dados.get("versao") != versao
        or not isinstance(arquivos, list)
    ):
        raise Falha("O manifesto do pacote de atualização não é desta versão; nada mudou.")
    lidos: dict[str, tuple[int, str]] = {}
    for item in arquivos:
        nome = item.get("nome") if isinstance(item, dict) else None
        tamanho = item.get("tamanho") if isinstance(item, dict) else None
        sha = item.get("sha256") if isinstance(item, dict) else None
        if (
            not isinstance(nome, str)
            or not _NOME.fullmatch(nome)
            or ".." in nome.split("/")
            or nome in lidos
            or isinstance(tamanho, bool)
            or not isinstance(tamanho, int)
            or tamanho < 0
            or not isinstance(sha, str)
            or not _SHA.fullmatch(sha)
        ):
            raise Falha("O manifesto do pacote de atualização está danificado; nada mudou.")
        lidos[nome] = (tamanho, sha)
    return lidos


def _extrair_pacote(
    pacote: Path, destino: Path, versao: str
) -> tuple[dict[str, tuple[int, str]], bytes]:
    """Extrai o `.zip` conferindo cada arquivo contra o manifesto de dentro."""
    try:
        with zipfile.ZipFile(pacote) as zf:
            try:
                bruto = zf.read("manifesto.json")
            except KeyError as erro:
                raise Falha("O pacote de atualização não tem manifesto; nada mudou.") from erro
            manifesto = _ler_manifesto(bruto, versao)
            vistos: set[str] = set()
            for info in zf.infolist():
                if info.is_dir() or info.filename == "manifesto.json":
                    continue
                if info.filename not in manifesto:
                    raise Falha(f"O pacote traz {info.filename!r}, fora do manifesto; nada mudou.")
                tamanho, sha = manifesto[info.filename]
                alvo = destino / info.filename
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as entrada, alvo.open("wb") as saida:
                    if _copiar(entrada, saida, tamanho) != sha:
                        raise Falha(
                            f"O arquivo {info.filename} do pacote não confere com o manifesto; "
                            "nada mudou."
                        )
                vistos.add(info.filename)
    except (zipfile.BadZipFile, OSError) as erro:
        raise Falha(f"Não consegui abrir o pacote de atualização ({erro}); nada mudou.") from erro
    faltam = [n for n in manifesto if n not in vistos]
    if faltam:
        raise Falha(f"Falta no pacote de atualização: {', '.join(sorted(faltam))}; nada mudou.")
    return manifesto, bruto


def _copiar(entrada: IO[bytes], saida: IO[bytes], tamanho: int) -> str | None:
    """Copia até `tamanho` bytes; `None` se o tamanho não bate (zip-bomba inclusive)."""
    soma = hashlib.sha256()
    lidos = 0
    while bloco := entrada.read(_BLOCO):
        lidos += len(bloco)
        if lidos > tamanho:
            return None
        soma.update(bloco)
        saida.write(bloco)
    return soma.hexdigest() if lidos == tamanho else None


def _um(manifesto: Iterable[str], padrao: str, o_que: str) -> str:
    achados = [n for n in manifesto if re.fullmatch(padrao, n)]
    if len(achados) != 1:
        raise Falha(f"O pacote de atualização não traz {o_que}; nada mudou.")
    return achados[0]


# --- montar o venv novo --------------------------------------------------------------------


def _apagar(caminho: Path) -> None:
    try:
        if caminho.is_symlink() or caminho.is_file():
            caminho.unlink()
        elif caminho.is_dir():
            shutil.rmtree(caminho)
    except OSError:
        log.warning("não consegui apagar %s", caminho, exc_info=True)


def descartar(preparada: Preparada) -> None:
    """Desfaz o que `preparar` montou (a troca não saiu)."""
    _apagar(preparada.venv)
    if preparada.python_novo is not None:
        _apagar(preparada.python_novo)


def _python(pasta: Path, tar: Path, plataforma: str) -> tuple[Path, Path | None]:
    """A pasta do Python do pacote em `<pasta>/python/`; extrai só se ainda não existe."""
    destino = pasta / "python" / tar.name.removesuffix(".tar.gz")
    if destino.is_dir():
        return _interpretador(destino, plataforma), None
    tmp = destino.with_name(f".{destino.name}.tmp")
    _apagar(tmp)
    try:
        with tarfile.open(tar, "r:gz") as arquivo:
            arquivo.extractall(tmp, filter="data")
        tmp.rename(destino)
    except (tarfile.TarError, OSError) as erro:
        _apagar(tmp)
        raise Falha(f"Não consegui preparar o Python novo ({erro}); nada mudou.") from erro
    return _interpretador(destino, plataforma), destino


def _rodou(rodar: Rodar, comando: list[str]) -> Resultado:
    feito = rodar(comando)
    if feito.codigo != 0:
        texto = (feito.erro or feito.saida).strip()
        raise Falha(f"Falhou: {' '.join(comando)}: {texto}. Nada mudou.")
    return feito


def _navegador(rodar: Rodar, jobot: Path, env: Mapping[str, str], plataforma: str) -> bool:
    """D174.13 e D183.24: com o Chromium do Playwright na pasta, o `jobot ferramentas baixar
    navegador` do venv novo roda o `playwright install` da versão nova antes da troca (nada baixa
    se a revisão é a mesma); devolve `True` se ficou desatualizado."""
    pasta = pasta_do_playwright(env, plataforma)
    if not (pasta.is_dir() and any(p.name.startswith("chromium") for p in pasta.iterdir())):
        return False
    feito = rodar([str(jobot), "ferramentas", "baixar", "navegador"])
    if feito.codigo != 0:
        log.warning("o navegador novo não instalou: %s", (feito.erro or feito.saida).strip())
        return True
    return False


def preparar(
    rodar: Rodar,
    instalacao: Mapping[str, Any],
    cliente: httpx.Client,
    *,
    env: Mapping[str, str] = os.environ,
    plataforma: str = sys.platform,
    maquina: str | None = None,
) -> Preparada | None:
    """Baixa, confere e monta o venv novo; `None` se já está na mais nova, `Falha` se não deu.

    Qualquer falha apaga o que foi montado: a instalação atual fica como estava.
    """
    alvo = alvo_atual(plataforma, maquina)
    if alvo is None:
        raise Falha("Este sistema não tem pacote de atualização; baixe o instalador novo.")
    pasta = Path(instalacao["pasta"])
    uv = instalacao["uv"]
    somas = io.BytesIO()
    _baixar(cliente, f"{URL_LATEST}/SHA256SUMS", somas, _TETO_SOMAS)
    versao, nome, sha = _achar_pacote(somas.getvalue().decode("utf-8", "replace"), alvo)
    atual = re.match(_VERSAO, __version__)
    if atual is not None and _versao(versao) <= _versao(atual[0]):
        return None
    temp = pasta / f"baixando-{versao}"
    _apagar(temp)
    venv = pasta / "venvs" / f"venv-{versao}"
    python_novo: Path | None = None
    try:
        (temp / "pacote").mkdir(parents=True)
        pacote = temp / nome
        with pacote.open("wb") as saida:
            baixado = _baixar(cliente, f"{URL_TAG}/v{versao}/{nome}", saida, _TETO_PACOTE)
        if baixado != sha:
            raise Falha("O pacote baixado não confere com o SHA256SUMS da release; nada mudou.")
        manifesto, bruto = _extrair_pacote(pacote, temp / "pacote", versao)
        _um(manifesto, rf"wheels/jobot-{re.escape(versao)}-[^/]+\.whl", "a wheel do joBot")
        tar = _um(manifesto, r"python/[^/]+\.tar\.gz", "o Python")
        _um(manifesto, r"restricoes\.txt", "o restricoes.txt")
        interpretador, python_novo = _python(pasta, temp / "pacote" / tar, plataforma)
        _apagar(venv)  # sobra de uma tentativa que caiu no meio
        cache = str(pasta / "cache")
        _rodou(
            rodar,
            [
                uv,
                "venv",
                "--offline",
                "--cache-dir",
                cache,
                "--python",
                str(interpretador),
                str(venv),
            ],
        )
        python = no_venv(venv, "python", plataforma)
        _rodou(
            rodar,
            [
                uv, "pip", "install", "--offline", "--cache-dir", cache,
                "--python", str(python), "--no-index",
                "--find-links", str(temp / "pacote" / "wheels"),
                "--require-hashes", "-r", str(temp / "pacote" / "restricoes.txt"),
            ],
        )  # fmt: skip
        jobot = no_venv(venv, "jobot", plataforma)
        prova = _rodou(rodar, [str(jobot), "--version"])
        if prova.saida.strip() != f"jobot {versao}":
            raise Falha(
                f"O joBot novo não respondeu com a versão {versao} ({prova.saida.strip()!r}); "
                "nada mudou."
            )
        desatualizado = _navegador(rodar, jobot, env, plataforma)
    except BaseException as erro:
        _apagar(venv)
        if python_novo is not None:
            _apagar(python_novo)
        if isinstance(erro, OSError):  # disco cheio, sem permissão: a pessoa lê, não traceback
            raise Falha(f"Não consegui preparar a versão {versao} ({erro}); nada mudou.") from erro
        raise
    finally:
        _apagar(temp)
    return Preparada(versao, venv, python, jobot, python_novo, bruto, desatualizado)


def trocar(dados: Path, instalacao: Mapping[str, Any], nova: Preparada) -> dict[str, Any]:
    """Grava o manifesto novo e troca `venv` e `anterior` no `instalacao.json` (atômico).

    Lê o banco antes de gravar: `Falha` dele não deixa nada para trás.
    """
    pasta = Path(instalacao["pasta"])
    user_version = versao_do_banco(dados)
    manifesto = pasta / f"manifesto-{nova.versao}.json"
    _gravar(manifesto, nova.manifesto)
    conteudo = dict(instalacao)
    conteudo.update(
        venv=str(nova.venv),
        anterior=instalacao["venv"],
        manifesto=str(manifesto),
        manifesto_anterior=instalacao["manifesto"],
        user_version=user_version,
        navegador_desatualizado=nova.navegador_desatualizado,
    )
    gravar_instalacao(dados, conteudo)
    return conteudo


def _home_do_venv(venv: Path) -> Path | None:
    try:
        for linha in (venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
            chave, _, valor = linha.partition("=")
            if chave.strip() == "home":
                return Path(valor.strip())
    except OSError:
        pass
    return None


def limpar(instalacao: Mapping[str, Any]) -> None:
    """Apaga venvs, Pythons e manifestos que não são do atual nem do anterior."""
    pasta = Path(instalacao["pasta"])
    ficam = {Path(v) for v in (instalacao["venv"], instalacao.get("anterior")) if v}
    for venv in (pasta / "venvs").glob("venv-*"):
        if venv not in ficam:
            _apagar(venv)
    homes = [_home_do_venv(v) for v in ficam]
    pythons = [] if None in homes else list((pasta / "python").glob("*"))  # na dúvida, fica
    for python in pythons:
        if not any(h is not None and h.is_relative_to(python) for h in homes):
            _apagar(python)
    manifestos = {
        Path(m) for m in (instalacao["manifesto"], instalacao.get("manifesto_anterior")) if m
    }
    for manifesto in pasta.glob("manifesto-*.json"):
        if manifesto not in manifestos:
            _apagar(manifesto)
