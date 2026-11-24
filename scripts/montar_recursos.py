"""Monta os recursos do instalador da casca e o pacote de atualização (T339; desenho 8;
D174.1, D174.16 e D181.5).

Script do CI (`.github/workflows/pacotes.yml`), fora do pacote `jobot`. Quatro comandos:

- `restricoes --dependencias D --wheel W --saida R`: o `restricoes.txt` da release, o
  `uv export` com hash de toda dependência mais a linha `jobot==<versão> --hash=sha256:<sha>`.
- `recursos --alvo A --wheel W --restricoes R --rodas DIR --saida S --pacotes DIR`: baixa o
  `uv`, o texto das licenças dele e o Python da versão do `desktop/uv.meta.json` e confere o
  sha256 de cada um; monta em `S` o `bin/uv.tar` (o `uv` num tar sem compressão), as
  `licencas/uv/`, o `python/<tag>/<arquivo>` (o espelho que o `uv python install --mirror`
  lê), as `wheels/` (as do alvo, já baixadas com `--require-hashes`, e a do joBot) e o
  `restricoes.txt`, e por fim o `manifesto.json`, cujo sha256 sai no stdout (o
  `JOBOT_MANIFESTO_SHA256` do build). Em `DIR` grava o `jobot-atualizacao-<versão>-<alvo>.zip`.
  O navegador não entra: o joBot não redistribui o Chrome for Testing que o Playwright baixa
  (D183.24).
- `exes --recursos S --instalacao I`: todo `.exe` que a instalação no Windows vai ter, um por
  linha, para a fumaça sem rede criar as regras de firewall antes do `/S`.
- `ferramentas --saida DIR`: baixa e confere, pelo `desktop/appimage.meta.json`, o AppRun, o
  linuxdeploy e o plugin dele que o Tauri usa no AppImage, e os põe no cache que o bundler lê
  antes de baixar (D183.21).
"""

import argparse
import configparser
import hashlib
import json
import shutil
import stat
import sys
import tarfile
import tomllib
import urllib.request
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from provar_uv import linha_do_jobot

RAIZ = Path(__file__).resolve().parents[1]
META = RAIZ / "desktop" / "uv.meta.json"
APPIMAGE = RAIZ / "desktop" / "appimage.meta.json"
MANIFESTO = "manifesto.json"
_BLOCO = 1 << 20


def endereco_do_uv(meta: Mapping[str, Any], alvo: str) -> tuple[str, str]:
    """(URL, sha256) do arquivo do `uv` daquele alvo."""
    uv = meta["uv"]
    extensao = "zip" if "windows" in alvo else "tar.gz"
    url = f"https://github.com/astral-sh/uv/releases/download/{uv['versao']}/uv-{alvo}.{extensao}"
    return url, uv["sha256"][alvo]


def endereco_do_python(meta: Mapping[str, Any], alvo: str) -> tuple[str, str, str]:
    """(URL, nome do arquivo, sha256) do Python do python-build-standalone daquele alvo."""
    py = meta["python"]
    nome = f"cpython-{py['versao']}+{py['tag']}-{alvo}-install_only_stripped.tar.gz"
    base = "https://github.com/astral-sh/python-build-standalone/releases/download"
    return f"{base}/{py['tag']}/{nome.replace('+', '%2B')}", nome, py["sha256"][alvo]


def licencas_do_uv(meta: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """(URL, nome, sha256) do texto de cada licença do `uv` (MIT e Apache-2.0), da tag da versão."""
    uv = meta["uv"]
    base = f"https://raw.githubusercontent.com/astral-sh/uv/{uv['versao']}"
    return [(f"{base}/{nome}", nome, sha) for nome, sha in sorted(uv["licencas"].items())]


def _sha256(arquivo: Path) -> str:
    soma = hashlib.sha256()
    with arquivo.open("rb") as f:
        while bloco := f.read(_BLOCO):
            soma.update(bloco)
    return soma.hexdigest()


def baixar(url: str, destino: Path, sha256: str) -> None:
    """Baixa e confere; sha256 diferente apaga o arquivo e para o build."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resposta, destino.open("wb") as saida:
        shutil.copyfileobj(resposta, saida, _BLOCO)
    achado = _sha256(destino)
    if achado != sha256:
        destino.unlink()
        raise SystemExit(f"o sha256 de {url} não confere: {achado}, esperado {sha256}")


def restricoes(dependencias: Path, roda: Path, saida: Path) -> None:
    texto = dependencias.read_text(encoding="utf-8")
    if not texto.endswith("\n"):
        texto += "\n"
    saida.write_text(texto + linha_do_jobot(roda), encoding="utf-8")


def extrair_uv(arquivo: Path, pasta: Path) -> Path:
    """Tira só o `uv` (`uv.exe`) do arquivo da release do `uv`, com o bit de execução."""
    pasta.mkdir(parents=True, exist_ok=True)
    if arquivo.name.endswith(".zip"):
        with zipfile.ZipFile(arquivo) as z:
            membro = next(n for n in z.namelist() if n.rsplit("/", 1)[-1] == "uv.exe")
            dados = z.read(membro)
            destino = pasta / "uv.exe"
    else:
        with tarfile.open(arquivo, "r:gz") as tar:
            info = next(t for t in tar.getmembers() if t.isfile() and t.name.endswith("/uv"))
            leitor = tar.extractfile(info)
            assert leitor is not None
            dados = leitor.read()
            destino = pasta / "uv"
    destino.write_bytes(dados)
    destino.chmod(destino.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return destino


def _tar_do_uv(binario: Path, destino: Path) -> None:
    """O `uv` num tar ustar sem compressão: o linuxdeploy do AppImage reescreve o rpath de todo
    ELF em `usr/lib`, e um `uv` solto deixaria de bater com o manifesto (D183)."""
    destino.parent.mkdir(parents=True)
    with tarfile.open(destino, "w", format=tarfile.USTAR_FORMAT) as tar:
        info = tar.gettarinfo(binario, arcname=binario.name)
        info.mode, info.uid, info.gid, info.uname, info.gname = 0o755, 0, 0, "", ""
        with binario.open("rb") as f:
            tar.addfile(info, f)
    shutil.rmtree(binario.parent)


def _entradas(raiz: Path, nomes: list[str]) -> list[dict[str, object]]:
    return [
        {"nome": n, "tamanho": (raiz / n).stat().st_size, "sha256": _sha256(raiz / n)}
        for n in sorted(nomes)
    ]


def _json(versao: str, arquivos: list[dict[str, object]]) -> bytes:
    conteudo = {"versao": versao, "arquivos": arquivos}
    return (json.dumps(conteudo, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def montar(
    *,
    saida: Path,
    versao: str,
    uv: Path,
    python: Path,
    tag: str,
    rodas: Path,
    roda: Path,
    restricoes: Path,
    licencas: list[Path],
    alvo: str,
) -> str:
    """Recursos completos em `saida` (apagada antes: arquivo fora do manifesto recusa tudo);
    devolve o sha256 do `manifesto.json`."""
    shutil.rmtree(saida, ignore_errors=True)
    saida.mkdir(parents=True)
    _tar_do_uv(extrair_uv(uv, saida / "tmp-uv"), saida / "bin" / "uv.tar")
    (saida / "licencas" / "uv").mkdir(parents=True)
    for licenca in licencas:
        shutil.copyfile(licenca, saida / "licencas" / "uv" / licenca.name)
    (saida / "python" / tag).mkdir(parents=True)
    shutil.copyfile(python, saida / "python" / tag / python.name)
    (saida / "wheels").mkdir()
    for whl in [*rodas.glob("*.whl"), roda]:
        shutil.copyfile(whl, saida / "wheels" / whl.name)
    shutil.copyfile(restricoes, saida / "restricoes.txt")
    nomes = [p.relative_to(saida).as_posix() for p in saida.rglob("*") if p.is_file()]
    bruto = _json(versao, _entradas(saida, nomes))
    (saida / MANIFESTO).write_bytes(bruto)
    return hashlib.sha256(bruto).hexdigest()


def pacote_de_atualizacao(recursos: Path, pasta: Path, versao: str, alvo: str) -> Path:
    """O `jobot-atualizacao-<versão>-<alvo>.zip` que o canal `casca` lê (D174.16): o Python em
    `python/<arquivo>`, as wheels e o `restricoes.txt`."""
    lista = json.loads((recursos / MANIFESTO).read_bytes())["arquivos"]
    dentro: dict[str, Path] = {}
    for entrada in lista:
        nome = entrada["nome"]
        if nome.startswith("python/"):
            dentro[f"python/{nome.rsplit('/', 1)[-1]}"] = recursos / nome
        elif nome.startswith("wheels/") or nome == "restricoes.txt":
            dentro[nome] = recursos / nome
    arquivos = [
        {"nome": n, "tamanho": c.stat().st_size, "sha256": _sha256(c)} for n, c in dentro.items()
    ]
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"jobot-atualizacao-{versao}-{alvo}.zip"
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr(MANIFESTO, _json(versao, sorted(arquivos, key=lambda e: str(e["nome"]))))
        for nome, caminho in sorted(dentro.items()):
            z.write(caminho, nome)
    return destino


def _scripts_da_roda(roda: Path) -> tuple[list[str], list[str]]:
    """(scripts de console e de janela, `.exe` de dentro) de uma wheel."""
    with zipfile.ZipFile(roda) as z:
        nomes = z.namelist()
        scripts: list[str] = []
        for nome in nomes:
            if nome.endswith(".dist-info/entry_points.txt"):
                ini = configparser.ConfigParser(delimiters=("=",), interpolation=None)
                ini.read_string(z.read(nome).decode("utf-8"))
                for secao in ("console_scripts", "gui_scripts"):
                    scripts += list(ini[secao]) if ini.has_section(secao) else []
    return scripts, [n for n in nomes if n.lower().endswith(".exe")]


def exes_do_windows(recursos: Path, instalacao: str, versao: str) -> list[str]:
    """Todo `.exe` da instalação no Windows (desenho 6.2 e 10): a casca e o desinstalador, o
    `uv` dos recursos e o copiado, o Python e o venv (com os scripts e os `.exe` das wheels, como
    o `node.exe` do driver). O Chromium vem depois, da internet (D183.24)."""
    manifesto = json.loads((recursos / MANIFESTO).read_bytes())["arquivos"]
    nomes = [e["nome"] for e in manifesto]
    casca = f"{instalacao}\\app"
    venv = f"{casca}\\venvs\\venv-{versao}"
    exes = [f"{instalacao}\\jobot-app.exe", f"{instalacao}\\uninstall.exe", f"{casca}\\bin\\uv.exe"]
    exes += [
        f"{instalacao}\\recursos\\" + n.replace("/", "\\") for n in nomes if n.endswith(".exe")
    ]
    scripts = ["python", "pythonw", "jobot"]
    for nome in nomes:
        arquivo = recursos / nome
        if nome.startswith("python/"):
            versao_py = arquivo.name.removeprefix("cpython-").split("+")[0]
            pasta = f"{casca}\\python\\cpython-{versao_py}-windows-x86_64-none"
            with tarfile.open(arquivo) as tar:
                for t in tar.getnames():
                    if t.lower().endswith(".exe"):
                        exes.append(pasta + "\\" + t.removeprefix("python/").replace("/", "\\"))
        elif nome.startswith("wheels/"):
            seus, de_dentro = _scripts_da_roda(arquivo)
            scripts += seus
            exes += [f"{venv}\\Lib\\site-packages\\" + n.replace("/", "\\") for n in de_dentro]
    exes += [f"{venv}\\Scripts\\{s}.exe" for s in scripts]
    return list(dict.fromkeys(exes))


def ferramentas(meta: Mapping[str, Mapping[str, str]], pasta: Path) -> None:
    """Cada ferramenta do AppImage em `pasta/<nome>`, conferida e com o bit de execução."""
    for nome, ferramenta in meta.items():
        destino = pasta / nome
        baixar(ferramenta["url"], destino, ferramenta["sha256"])
        destino.chmod(0o755)


def _versao() -> str:
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    return str(projeto["project"]["version"])


def main(argv: list[str]) -> None:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    comandos = analisador.add_subparsers(dest="comando", required=True)
    r = comandos.add_parser("restricoes")
    r.add_argument("--dependencias", type=Path, required=True)
    r.add_argument("--wheel", type=Path, required=True)
    r.add_argument("--saida", type=Path, required=True)
    m = comandos.add_parser("recursos")
    for nome in ("wheel", "restricoes", "rodas", "saida", "pacotes"):
        m.add_argument(f"--{nome}", type=Path, required=True)
    m.add_argument("--alvo", required=True)
    e = comandos.add_parser("exes")
    e.add_argument("--recursos", type=Path, required=True)
    e.add_argument("--instalacao", required=True)
    f = comandos.add_parser("ferramentas")
    f.add_argument("--saida", type=Path, required=True)
    args = analisador.parse_args(argv)

    if args.comando == "restricoes":
        restricoes(args.dependencias, args.wheel, args.saida)
    elif args.comando == "ferramentas":
        ferramentas(json.loads(APPIMAGE.read_text(encoding="utf-8")), args.saida)
    elif args.comando == "exes":
        print("\n".join(exes_do_windows(args.recursos, args.instalacao, _versao())))
    else:
        meta = json.loads(META.read_text(encoding="utf-8"))
        baixados = args.pacotes / "baixados"
        url, sha = endereco_do_uv(meta, args.alvo)
        uv = baixados / url.rsplit("/", 1)[-1]
        baixar(url, uv, sha)
        url, nome, sha = endereco_do_python(meta, args.alvo)
        python = baixados / nome
        baixar(url, python, sha)
        licencas = []
        for url, nome, sha in licencas_do_uv(meta):
            licencas.append(baixados / "licencas" / nome)
            baixar(url, licencas[-1], sha)
        versao = _versao()
        sha_manifesto = montar(
            saida=args.saida,
            versao=versao,
            uv=uv,
            python=python,
            tag=meta["python"]["tag"],
            rodas=args.rodas,
            roda=args.wheel,
            restricoes=args.restricoes,
            licencas=licencas,
        )
        shutil.rmtree(baixados)
        pacote_de_atualizacao(args.saida, args.pacotes, versao, args.alvo)
        print(sha_manifesto)


if __name__ == "__main__":
    main(sys.argv[1:])
