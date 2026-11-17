"""Prova do `uv` com hash nas dependências (T322, D173, desenho 6.2, risco 2).

Script de quem contribui e do CI: usa rede e o `uv` do sistema, fora do pacote `jobot`.
Monta a wheel e o `restricoes.txt` (do `uv.lock`, com hashes) e instala o joBot em pastas
temporárias (`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_PYTHON_INSTALL_DIR`, `UV_CACHE_DIR`), sem
tocar nas pastas do usuário. Depois repete com o hash de uma dependência adulterado e diz se o
`uv` recusou. Se não recusar com `--constraints`, tenta `--with-requirements` com
`UV_REQUIRE_HASHES=1` (o `uv tool install` não tem `--require-hashes`).

Depois prova o caminho da D173 (T338): baixa as wheels só binárias do `restricoes.txt` (pelo
`pip download --require-hashes`, que o `uv` não tem), põe a wheel do joBot junto com a linha
`jobot==<versão> --hash=...` e instala num `uv venv` com `uv pip install --offline --no-index
--find-links <wheels> --require-hashes`; o arquivo bom tem de instalar (e o `jobot --version`
responder) e o adulterado tem de ser recusado.

Uso: `uv run python scripts/provar_uv.py` na raiz do repositório. O resultado do `uv tool` sai
só no texto; o código de saída é o da D173: 0 se o caminho dela vale, 2 se não vale ou se a
prova é inválida (a instalação boa falhou, ou o `uv pip install --require-hashes` aceitou o
arquivo adulterado).
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HASH = re.compile(r"(--hash=sha256:)[0-9a-f]{64}")
# O `pip` só baixa as wheels (o `uv` não tem `download`); versão fixa para a prova se repetir.
_PIP = "pip==26.2"


def adulterar(texto: str) -> tuple[str, str]:
    """Troca todos os hashes do primeiro pacote sem marcador; devolve (texto, pacote)."""
    linhas = texto.splitlines(keepends=True)
    alvo = ""
    for i, linha in enumerate(linhas):
        if alvo:
            if not linha[:1].isspace():
                break
            linhas[i] = _HASH.sub(r"\g<1>" + "0" * 64, linha)
        elif linha[:1].isalnum() and ";" not in linha and "==" in linha:
            alvo = linha.split("==")[0]
            linhas[i] = _HASH.sub(r"\g<1>" + "0" * 64, linha)
    if not alvo:
        raise SystemExit("nenhum pacote para adulterar no restricoes.txt")
    return "".join(linhas), alvo


def linha_do_jobot(roda: Path) -> str:
    """A linha do joBot no `restricoes.txt` da D173 (D174.16): versão e sha256 da wheel."""
    versao = roda.name.split("-")[1]
    sha = hashlib.sha256(roda.read_bytes()).hexdigest()
    return f"jobot=={versao} --hash=sha256:{sha}\n"


def comando_offline(venv: Path, rodas: Path, restricoes: Path) -> list[str]:
    """O `uv pip install` da D173: sem índice, só da pasta de wheels, com hash de tudo."""
    return [
        "uv",
        "pip",
        "install",
        "--python",
        str(venv),
        "--offline",
        "--no-index",
        "--find-links",
        str(rodas),
        "--require-hashes",
        "-r",
        str(restricoes),
    ]


def _rodar(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, env=env, capture_output=True, text=True, check=False)


def _instalar(base: Path, nome: str, args: list[str], extra: dict[str, str]) -> bool:
    pasta = base / nome
    env = os.environ | extra
    for var in ("UV_TOOL_DIR", "UV_TOOL_BIN_DIR", "UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR"):
        env[var] = str(pasta / var.lower())
    r = _rodar(["uv", "tool", "install", "--python", "3.14", *args], env)
    print(f"[{nome}] {'passou' if r.returncode == 0 else 'falhou'} (código {r.returncode})")
    if r.returncode:
        print("  " + "\n  ".join(r.stderr.strip().splitlines()[-4:]))
    return r.returncode == 0


def _pip_recusa(base: Path, restricoes: Path) -> bool:
    """Controle: num venv temporário, `uv pip --require-hashes` tem de recusar o arquivo."""
    venv = base / "venv-controle"
    pasta = base / "controle"
    env = os.environ | {
        v: str(pasta / v.lower()) for v in ("UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR")
    }
    subprocess.run(["uv", "venv", "--python", "3.14", str(venv)], env=env, check=True)
    args = ["uv", "pip", "install", "--python", str(venv), "--require-hashes", "-r"]
    return _rodar([*args, str(restricoes)], env).returncode != 0


def _python_do_venv(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _provar_d173(base: Path, roda: Path, boas: Path, ruins: Path) -> bool:
    """Instala offline do arquivo bom (tem de passar) e do adulterado (tem de ser recusado)."""
    pasta = base / "d173"
    env = os.environ | {
        v: str(pasta / v.lower()) for v in ("UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR")
    }
    rodas = pasta / "wheels"
    baixar = ["uvx", "--python", "3.14", _PIP, "download", "--only-binary=:all:"]
    baixar += ["--require-hashes", "-r", str(boas), "-d", str(rodas)]
    subprocess.run(baixar, env=env, check=True, stdout=subprocess.DEVNULL)
    shutil.copy2(roda, rodas / roda.name)
    linha = linha_do_jobot(roda)
    resultado = {}
    for nome, origem in (("bom", boas), ("ruim", ruins)):
        restricoes = pasta / f"restricoes-{nome}.txt"
        restricoes.write_text(origem.read_text(encoding="utf-8") + linha, encoding="utf-8")
        venv = pasta / f"venv-{nome}"
        subprocess.run(["uv", "venv", "--python", "3.14", str(venv)], env=env, check=True)
        r = _rodar(comando_offline(venv, rodas, restricoes), env)
        estado = "passou" if r.returncode == 0 else "falhou"
        print(f"[d173-{nome}] {estado} (código {r.returncode})")
        if r.returncode:
            print("  " + "\n  ".join(r.stderr.strip().splitlines()[-4:]))
        # O ruim só conta como recusa se o motivo for o hash, não outra falha qualquer.
        resultado[nome] = r.returncode == 0 or (nome == "ruim" and "hash" not in r.stderr.lower())
        if nome == "bom" and resultado[nome]:
            versao = _rodar([str(_python_do_venv(venv)), "-m", "jobot", "--version"], env)
            print(f"  jobot --version: {versao.stdout.strip()} (código {versao.returncode})")
            resultado[nome] = versao.returncode == 0
    return resultado["bom"] and not resultado["ruim"]


def main() -> int:
    try:
        return _main()
    except subprocess.CalledProcessError as erro:
        print(f"prova inválida: falhou {' '.join(map(str, erro.cmd))} (código {erro.returncode})")
        return 2


def _main() -> int:
    print(_rodar(["uv", "--version"], dict(os.environ)).stdout.strip())
    with tempfile.TemporaryDirectory(prefix="provar_uv_") as tmp:
        base = Path(tmp)
        env = dict(os.environ)
        dist = base / "dist"
        subprocess.run(["uv", "build", "--wheel", "--out-dir", str(dist)], env=env, check=True)
        roda = next(dist.glob("*.whl"))
        boas = base / "restricoes.txt"
        subprocess.run(
            ["uv", "export", "--locked", "--no-dev", "--no-emit-project"]
            + ["--format", "requirements-txt", "--output-file", str(boas)],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        texto, pacote = adulterar(boas.read_text(encoding="utf-8"))
        ruins = base / "restricoes-adulteradas.txt"
        ruins.write_text(texto, encoding="utf-8")
        print(f"hash adulterado em: {pacote}")
        if not _pip_recusa(base, ruins):
            print("prova inválida: uv pip --require-hashes aceitou o arquivo adulterado")
            return 2
        print("controle: uv pip install --require-hashes recusa o arquivo adulterado")

        if not _instalar(base, "constraints-bom", ["--constraints", str(boas), str(roda)], {}):
            return 2
        if _instalar(base, "constraints-ruim", ["--constraints", str(ruins), str(roda)], {}):
            print("resultado: --constraints NÃO exige o hash das dependências")
            exigir = {"UV_REQUIRE_HASHES": "1"}
            args = ["--with-requirements", str(boas), str(roda)]
            bom = _instalar(base, "with-req-bom", args, exigir)
            args = ["--with-requirements", str(ruins), str(roda)]
            ruim = _instalar(base, "with-req-ruim", args, exigir)
            exige = bom and not ruim
            estado = "EXIGE" if exige else "NÃO exige"
            print(f"resultado: --with-requirements + UV_REQUIRE_HASHES=1 {estado} o hash")
        else:
            print("resultado: --constraints EXIGE o hash das dependências")

        if _provar_d173(base, roda, boas, ruins):
            print("resultado D173: --offline --require-hashes instala e recusa o adulterado")
            return 0
        print("resultado D173: o caminho NÃO vale")
        return 2


if __name__ == "__main__":
    sys.exit(main())
