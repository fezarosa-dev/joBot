"""Prova do `uv tool install` com hash nas dependências (T322, desenho 6.2, risco 2).

Script de quem contribui e do CI: usa rede e o `uv` do sistema, fora do pacote `jobot`.
Monta a wheel e o `restricoes.txt` (do `uv.lock`, com hashes) e instala o joBot em pastas
temporárias (`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_PYTHON_INSTALL_DIR`, `UV_CACHE_DIR`), sem
tocar nas pastas do usuário. Depois repete com o hash de uma dependência adulterado e diz se o
`uv` recusou. Se não recusar com `--constraints`, tenta `--with-requirements` com
`UV_REQUIRE_HASHES=1` (o `uv tool install` não tem `--require-hashes`).

Uso: `uv run python scripts/provar_uv.py` na raiz do repositório. Sai com 0 se algum caminho
exigiu o hash, 1 se nenhum exigiu, 2 se a prova é inválida (a instalação boa falhou, ou o
`uv pip install --require-hashes` aceitou o arquivo adulterado).
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_HASH = re.compile(r"(--hash=sha256:)[0-9a-f]{64}")


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


def main() -> int:
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
        if not _instalar(base, "constraints-ruim", ["--constraints", str(ruins), str(roda)], {}):
            print("resultado: --constraints EXIGE o hash das dependências")
            return 0
        print("resultado: --constraints NÃO exige o hash das dependências")

        exigir = {"UV_REQUIRE_HASHES": "1"}
        bom = _instalar(base, "with-req-bom", ["--with-requirements", str(boas), str(roda)], exigir)
        ruim = _instalar(
            base, "with-req-ruim", ["--with-requirements", str(ruins), str(roda)], exigir
        )
        if bom and not ruim:
            print("resultado: --with-requirements + UV_REQUIRE_HASHES=1 EXIGE o hash")
            return 0
        print("resultado: nenhum caminho exigiu o hash (limite: só a wheel e os pinos ==)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
