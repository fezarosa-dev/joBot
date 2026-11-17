"""Prende o `release.yml`, o `pacotes.yml` (por texto), o `desktop/uv.meta.json` e o
`scripts/montar_recursos.py`, que monta os recursos do instalador e o pacote de atualização
(T339; desenho 8 e 10; D174.1, D174.4 e D174.16)."""

import hashlib
import importlib.util
import io
import json
import os
import re
import stat
import sys
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FLUXOS = RAIZ / ".github" / "workflows"
RELEASE = FLUXOS / "release.yml"
PACOTES = FLUXOS / "pacotes.yml"
META = RAIZ / "desktop" / "uv.meta.json"
ALVOS = [
    "x86_64-unknown-linux-gnu",
    "x86_64-pc-windows-msvc",
    "aarch64-apple-darwin",
    "x86_64-apple-darwin",
]
HEX = re.compile(r"[0-9a-f]{64}")


def _codigo(caminho: Path) -> str:
    # Os comentários do topo citam o que é proibido: só o código conta.
    bruto = caminho.read_text(encoding="utf-8")
    return "\n".join(x for x in bruto.splitlines() if not x.lstrip().startswith("#"))


def _secao(texto: str, chave: str) -> list[str]:
    linhas = texto.splitlines()
    corpo = []
    for linha in linhas[linhas.index(f"{chave}:") + 1 :]:
        if linha and not linha.startswith(" "):
            break
        if linha.strip():
            corpo.append(linha.strip())
    return corpo


def _job(caminho: Path, nome: str) -> str:
    linhas = _codigo(caminho).splitlines()
    inicio = linhas.index(f"  {nome}:") + 1
    corpo = []
    for linha in linhas[inicio:]:
        if re.match(r"  \S", linha) or (linha and not linha.startswith(" ")):
            break
        corpo.append(linha)
    return "\n".join(corpo)


def _jobs(caminho: Path) -> list[str]:
    return re.findall(r"^  (\w+):$", _codigo(caminho).split("\njobs:\n", 1)[1], re.MULTILINE)


def test_release_so_por_tag_ou_a_mao_e_so_o_publicar_escreve() -> None:
    texto = _codigo(RELEASE)
    assert _secao(texto, "on") == ["push:", "tags: ['v*']", "workflow_dispatch:"]
    assert "pull_request" not in texto
    assert _secao(texto, "permissions") == ["contents: read"]
    assert texto.count("contents: write") == 1
    assert "contents: write" in _job(RELEASE, "publicar")
    assert set(re.findall(r"secrets\.\w+", texto)) == {"secrets.GITHUB_TOKEN"}


def test_sem_escrita_no_que_roda_em_pr_e_no_pacotes() -> None:
    # o wiki.yml (só na main) também escreve; o que roda em PR e o pacotes.yml nunca
    for fluxo in FLUXOS.glob("*.yml"):
        texto = _codigo(fluxo)
        if "pull_request" in texto or fluxo == PACOTES:
            assert "contents: write" not in texto, fluxo.name


def test_actions_fixadas_por_hash_com_versao() -> None:
    for fluxo in (RELEASE, PACOTES):
        texto = fluxo.read_text(encoding="utf-8")
        usos = re.findall(r"^\s*(?:- )?uses: (\S+(?: # \S+)?)$", texto, re.MULTILINE)
        assert usos, fluxo.name
        for uso in usos:
            if uso.startswith("./"):
                continue
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+", uso), uso


def test_release_monta_pelo_pacotes_e_publica_so_na_tag() -> None:
    assert _jobs(RELEASE) == ["pacotes", "publicar"]
    assert "uses: ./.github/workflows/pacotes.yml" in _job(RELEASE, "pacotes")
    publicar = _job(RELEASE, "publicar")
    assert "needs: pacotes" in publicar
    assert "if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')" in publicar
    assert "gh release create" in publicar
    assert "--draft" not in publicar and "--prerelease" not in publicar
    assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in publicar
    assert "sha256sum" in publicar and "SHA256SUMS" in publicar
    for anexo in (
        "*-setup.exe",
        "*.dmg",
        "*.deb",
        "*.rpm",
        "*.AppImage",
        "jobot-atualizacao-*.zip",
        "chromium-*.tar.gz",
        "jobot-*.whl",
        "restricoes.txt",
    ):
        assert anexo in publicar, anexo
    assert "CHANGELOG.md" in publicar and "CHANGELOG.en.md" in publicar


def test_pacotes_so_chamado_e_sem_escrita() -> None:
    texto = _codigo(PACOTES)
    assert _secao(texto, "on") == ["workflow_call:"]
    assert _secao(texto, "permissions") == ["contents: read"]
    assert _jobs(PACOTES) == ["wheel", "casca"]
    for nome in _jobs(PACOTES):
        assert "timeout-minutes:" in _job(PACOTES, nome), nome


def test_job_wheel_gera_a_wheel_e_o_restricoes_com_hash() -> None:
    texto = _job(PACOTES, "wheel")
    assert "uv build --wheel" in texto
    assert "uv export --locked --no-dev --no-emit-project --format requirements-txt" in texto
    assert "scripts/montar_recursos.py restricoes" in texto
    # na tag, a versão do pyproject tem de ser a da tag
    assert "GITHUB_REF_NAME" in texto


def test_job_casca_monta_os_recursos_e_compila_com_o_sha_do_manifesto() -> None:
    texto = _job(PACOTES, "casca")
    for alvo, runner in (
        ("x86_64-unknown-linux-gnu", "ubuntu-22.04"),
        ("x86_64-pc-windows-msvc", "windows-latest"),
        ("aarch64-apple-darwin", "macos-latest"),
        ("x86_64-apple-darwin", "macos-15-intel"),
    ):
        assert re.search(rf"os: {runner}\n\s+alvo: {alvo}\n", texto), alvo
    for passo in (
        "PLAYWRIGHT_BROWSERS_PATH",
        "playwright install chromium",
        "pip==26.2 download --only-binary=:all: --require-hashes",
        "scripts/montar_recursos.py recursos",
        'echo "JOBOT_MANIFESTO_SHA256=',
        "cargo install tauri-cli --version =2.12.4 --locked",
        "cargo tauri build",
        "actions/upload-artifact@",
    ):
        assert passo in texto, passo


def test_fumaca_sem_rede_no_linux_no_windows_e_no_mac() -> None:
    texto = _job(PACOTES, "casca")
    # Linux: imagem com as bibliotecas do .deb e do Chromium, e o .deb e o AppImage sem rede
    for passo in (
        "ubuntu:22.04",
        "dpkg-deb -f",
        "apt-get satisfy",
        "install-deps chromium",
        "docker run --rm --network none",
        "dpkg -i",
        "APPIMAGE_EXTRACT_AND_RUN=1",
    ):
        assert passo in texto, passo
    # Windows: regras de saída por caminho antes do /S, conferência de todo .exe, desinstalar
    for passo in (
        "New-NetFirewallRule -Direction Outbound -Action Block -Program",
        "scripts/montar_recursos.py exes",
        "'/S'",
        "sem regra",
        "uninstall.exe",
    ):
        assert passo in texto, passo
    assert texto.index("New-NetFirewallRule") < texto.index("'/S'")
    # Mac: o .app de dentro do .dmg
    assert "hdiutil attach" in texto
    assert texto.count("--verificar") >= 4


def test_casca_do_tauri_gera_os_pacotes_e_o_mac_assina_ad_hoc() -> None:
    conf = json.loads((RAIZ / "desktop" / "tauri.conf.json").read_text(encoding="utf-8"))
    assert conf["bundle"]["active"] is True
    assert conf["bundle"]["resources"] == {"recursos/": "recursos/"}
    mac = json.loads((RAIZ / "desktop" / "tauri.macos.conf.json").read_text(encoding="utf-8"))
    assert mac["bundle"]["macOS"]["signingIdentity"] == "-"


def test_uv_meta_fixa_versao_e_sha_por_alvo() -> None:
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d+\.\d+\.\d+", meta["uv"]["versao"])
    assert re.fullmatch(r"3\.14\.\d+", meta["python"]["versao"])
    assert re.fullmatch(r"\d{8}", meta["python"]["tag"])
    for chave in ("uv", "python"):
        assert sorted(meta[chave]["sha256"]) == sorted(ALVOS), chave
        for sha in meta[chave]["sha256"].values():
            assert HEX.fullmatch(sha), sha


# --- scripts/montar_recursos.py ---


def _script() -> ModuleType:
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        caminho = RAIZ / "scripts" / "montar_recursos.py"
        spec = importlib.util.spec_from_file_location("montar_recursos", caminho)
        assert spec is not None and spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo
    finally:
        sys.path.remove(str(RAIZ / "scripts"))


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def test_enderecos_saem_do_meta() -> None:
    m = _script()
    meta = json.loads(META.read_text(encoding="utf-8"))
    v, tag = meta["python"]["versao"], meta["python"]["tag"]
    url, sha = m.endereco_do_uv(meta, "x86_64-pc-windows-msvc")
    versao_uv = meta["uv"]["versao"]
    assert url == (
        f"https://github.com/astral-sh/uv/releases/download/{versao_uv}/"
        "uv-x86_64-pc-windows-msvc.zip"
    )
    assert sha == meta["uv"]["sha256"]["x86_64-pc-windows-msvc"]
    assert m.endereco_do_uv(meta, "aarch64-apple-darwin")[0].endswith(
        "/uv-aarch64-apple-darwin.tar.gz"
    )
    url, nome, sha = m.endereco_do_python(meta, "x86_64-unknown-linux-gnu")
    assert nome == f"cpython-{v}+{tag}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
    assert url == (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        f"{tag}/{nome.replace('+', '%2B')}"
    )
    assert sha == meta["python"]["sha256"]["x86_64-unknown-linux-gnu"]


def test_baixar_confere_o_sha_e_apaga_o_que_nao_bate(tmp_path: Path) -> None:
    m = _script()
    origem = tmp_path / "origem.bin"
    origem.write_bytes(b"conteudo")
    destino = tmp_path / "baixado.bin"
    m.baixar(origem.as_uri(), destino, _sha(b"conteudo"))
    assert destino.read_bytes() == b"conteudo"
    ruim = tmp_path / "ruim.bin"
    with pytest.raises(SystemExit, match="sha256"):
        m.baixar(origem.as_uri(), ruim, _sha(b"outro"))
    assert not ruim.exists()


def test_restricoes_acrescenta_a_linha_do_jobot(tmp_path: Path) -> None:
    m = _script()
    deps = tmp_path / "dependencias.txt"
    deps.write_text("httpx==0.28.1 \\\n    --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    roda = tmp_path / "jobot-0.3.0-py3-none-any.whl"
    roda.write_bytes(b"roda")
    saida = tmp_path / "restricoes.txt"
    m.restricoes(deps, roda, saida)
    texto = saida.read_text(encoding="utf-8")
    assert texto.startswith(deps.read_text(encoding="utf-8"))
    assert texto.endswith(f"jobot==0.3.0 --hash=sha256:{_sha(b'roda')}\n")


def _uv_falso(pasta: Path, alvo: str) -> Path:
    if "windows" in alvo:
        arquivo = pasta / f"uv-{alvo}.zip"
        with zipfile.ZipFile(arquivo, "w") as z:
            z.writestr("uv.exe", b"uv falso")
            z.writestr("uvx.exe", b"uvx falso")
        return arquivo
    arquivo = pasta / f"uv-{alvo}.tar.gz"
    with tarfile.open(arquivo, "w:gz") as tar:
        for nome, dados in ((f"uv-{alvo}/uv", b"uv falso"), (f"uv-{alvo}/uvx", b"uvx")):
            info = tarfile.TarInfo(nome)
            info.size = len(dados)
            tar.addfile(info, io.BytesIO(dados))
    return arquivo


@pytest.mark.parametrize("alvo", ["x86_64-unknown-linux-gnu", "x86_64-pc-windows-msvc"])
def test_extrair_uv_tira_so_o_uv(tmp_path: Path, alvo: str) -> None:
    m = _script()
    destino = m.extrair_uv(_uv_falso(tmp_path, alvo), tmp_path / "bin")
    assert destino.name == ("uv.exe" if "windows" in alvo else "uv")
    assert destino.read_bytes() == b"uv falso"
    assert [p.name for p in (tmp_path / "bin").iterdir()] == [destino.name]
    if os.name == "posix":
        assert destino.stat().st_mode & stat.S_IXUSR


def test_tar_do_navegador_guarda_modo_e_symlink_e_deixa_os_ocultos(tmp_path: Path) -> None:
    m = _script()
    pasta = tmp_path / "navegadores"
    chrome = pasta / "chromium-1254" / "chrome-linux" / "chrome"
    chrome.parent.mkdir(parents=True)
    chrome.write_bytes(b"chrome")
    chrome.chmod(0o755)
    (pasta / "chromium-1254" / "atalho").symlink_to("chrome-linux/chrome")
    (pasta / ".links").mkdir()
    (pasta / ".links" / "x").write_text("y", encoding="utf-8")
    arquivo = tmp_path / "chromium-x86_64-unknown-linux-gnu.tar.gz"
    m.tar_do_navegador(pasta, arquivo)
    with tarfile.open(arquivo) as tar:
        membros = {t.name: t for t in tar.getmembers()}
    assert ".links" not in membros and ".links/x" not in membros
    assert membros["chromium-1254/chrome-linux/chrome"].mode & 0o111
    assert membros["chromium-1254/atalho"].issym()
    assert membros["chromium-1254/atalho"].linkname == "chrome-linux/chrome"


def _roda(caminho: Path, script: str) -> Path:
    caminho.parent.mkdir(exist_ok=True)
    nome, versao = caminho.name.split("-")[:2]
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr(f"{nome}/__init__.py", "")
        z.writestr(
            f"{nome}-{versao}.dist-info/entry_points.txt",
            f"[console_scripts]\n{script} = {nome}:main\n",
        )
    return caminho


def _cenario(tmp_path: Path, alvo: str) -> dict[str, Path]:
    rodas = tmp_path / "rodas"
    _roda(rodas / "httpx-0.28.1-py3-none-any.whl", "httpx")
    roda = _roda(tmp_path / "dist" / "jobot-0.3.0-py3-none-any.whl", "jobot")
    restricoes = tmp_path / "restricoes.txt"
    restricoes.write_text("httpx==0.28.1\njobot==0.3.0\n", encoding="utf-8")
    python = tmp_path / "cpython-3.14.10+20261110-x-install_only_stripped.tar.gz"
    python.write_bytes(b"python")
    navegadores = tmp_path / "navegadores"
    (navegadores / "chromium-1254").mkdir(parents=True)
    (navegadores / "chromium-1254" / "chrome").write_bytes(b"chrome")
    return {
        "uv": _uv_falso(tmp_path, alvo),
        "python": python,
        "rodas": rodas,
        "roda": roda,
        "restricoes": restricoes,
        "navegadores": navegadores,
    }


def _manifesto(bruto: bytes) -> dict[str, tuple[int, str]]:
    conteudo = json.loads(bruto)
    assert conteudo["versao"] == "0.3.0"
    return {e["nome"]: (e["tamanho"], e["sha256"]) for e in conteudo["arquivos"]}


def test_montar_gera_recursos_com_manifesto_de_tudo(tmp_path: Path) -> None:
    m = _script()
    alvo = "x86_64-unknown-linux-gnu"
    c = _cenario(tmp_path, alvo)
    saida = tmp_path / "recursos"
    saida.mkdir()
    (saida / "sobra.txt").write_text("de um build velho", encoding="utf-8")
    sha = m.montar(
        saida=saida,
        alvo=alvo,
        versao="0.3.0",
        uv=c["uv"],
        python=c["python"],
        tag="20261110",
        rodas=c["rodas"],
        roda=c["roda"],
        restricoes=c["restricoes"],
        navegadores=c["navegadores"],
    )
    bruto = (saida / "manifesto.json").read_bytes()
    assert sha == _sha(bruto)
    manifesto = _manifesto(bruto)
    achados = sorted(
        p.relative_to(saida).as_posix()
        for p in saida.rglob("*")
        if p.is_file() and p.name != "manifesto.json"
    )
    assert sorted(manifesto) == achados
    assert achados == [
        "bin/uv",
        f"chromium-{alvo}.tar.gz",
        f"python/20261110/{c['python'].name}",
        "restricoes.txt",
        "wheels/httpx-0.28.1-py3-none-any.whl",
        "wheels/jobot-0.3.0-py3-none-any.whl",
    ]
    for nome, (tamanho, sha_arquivo) in manifesto.items():
        dados = (saida / nome).read_bytes()
        assert (tamanho, sha_arquivo) == (len(dados), _sha(dados)), nome


def test_pacote_de_atualizacao_no_formato_do_canal_casca(tmp_path: Path) -> None:
    m = _script()
    alvo = "x86_64-pc-windows-msvc"
    c = _cenario(tmp_path, alvo)
    saida = tmp_path / "recursos"
    m.montar(
        saida=saida,
        alvo=alvo,
        versao="0.3.0",
        uv=c["uv"],
        python=c["python"],
        tag="20261110",
        rodas=c["rodas"],
        roda=c["roda"],
        restricoes=c["restricoes"],
        navegadores=c["navegadores"],
    )
    assert (saida / "bin" / "uv.exe").read_bytes() == b"uv falso"
    pacote = m.pacote_de_atualizacao(saida, tmp_path / "dist", "0.3.0", alvo)
    assert pacote.name == f"jobot-atualizacao-0.3.0-{alvo}.zip"
    with zipfile.ZipFile(pacote) as z:
        nomes = sorted(z.namelist())
        manifesto = _manifesto(z.read("manifesto.json"))
        dentro = {n: z.read(n) for n in nomes if n != "manifesto.json"}
    assert nomes == [
        "manifesto.json",
        f"python/{c['python'].name}",
        "restricoes.txt",
        "wheels/httpx-0.28.1-py3-none-any.whl",
        "wheels/jobot-0.3.0-py3-none-any.whl",
    ]
    for nome, dados in dentro.items():
        assert manifesto[nome] == (len(dados), _sha(dados)), nome
    # o Chromium fica listado sem estar dentro (D174.8)
    chromium = f"chromium-{alvo}.tar.gz"
    assert chromium not in dentro
    assert manifesto[chromium] == _manifesto((saida / "manifesto.json").read_bytes())[chromium]
    assert set(manifesto) == set(dentro) | {chromium}


def test_exes_do_windows_cobrem_a_instalacao(tmp_path: Path) -> None:
    m = _script()
    alvo = "x86_64-pc-windows-msvc"
    c = _cenario(tmp_path, alvo)
    # wheel com script de console e um .exe dentro, como o node.exe do driver do Playwright
    roda = c["rodas"] / "playwright-1.65.1-py3-none-win_amd64.whl"
    with zipfile.ZipFile(roda, "w") as z:
        z.writestr("playwright/driver/node.exe", b"node")
        z.writestr(
            "playwright-1.65.1.dist-info/entry_points.txt",
            "[console_scripts]\nplaywright = playwright.__main__:main\n",
        )
    python = tmp_path / "cpython-3.14.10+20261110-windows-install_only_stripped.tar.gz"
    with tarfile.open(python, "w:gz") as tar:
        for nome in ("python/python.exe", "python/pythonw.exe", "python/Scripts/pip.exe"):
            info = tarfile.TarInfo(nome)
            tar.addfile(info, io.BytesIO(b""))
    c["navegadores"].joinpath("chromium-1254", "chrome-win").mkdir()
    c["navegadores"].joinpath("chromium-1254", "chrome-win", "chrome.exe").write_bytes(b"")
    saida = tmp_path / "recursos"
    m.montar(
        saida=saida,
        alvo=alvo,
        versao="0.3.0",
        uv=c["uv"],
        python=python,
        tag="20261110",
        rodas=c["rodas"],
        roda=c["roda"],
        restricoes=c["restricoes"],
        navegadores=c["navegadores"],
    )
    inst = "C:\\U\\AppData\\Local\\joBot"
    exes = m.exes_do_windows(saida, inst, "C:\\U\\AppData\\Local\\ms-playwright", "0.3.0")
    casca = inst + "\\app"
    venv = casca + "\\venvs\\venv-0.3.0"
    cpython = casca + "\\python\\cpython-3.14.10-windows-x86_64-none"
    for esperado in (
        inst + "\\jobot-app.exe",
        inst + "\\uninstall.exe",
        inst + "\\recursos\\bin\\uv.exe",
        casca + "\\bin\\uv.exe",
        cpython + "\\python.exe",
        cpython + "\\pythonw.exe",
        cpython + "\\Scripts\\pip.exe",
        venv + "\\Scripts\\python.exe",
        venv + "\\Scripts\\pythonw.exe",
        venv + "\\Scripts\\jobot.exe",
        venv + "\\Scripts\\httpx.exe",
        venv + "\\Scripts\\playwright.exe",
        venv + "\\Lib\\site-packages\\playwright\\driver\\node.exe",
        "C:\\U\\AppData\\Local\\ms-playwright\\chromium-1254\\chrome-win\\chrome.exe",
    ):
        assert esperado in exes, esperado
    assert len(exes) == len(set(exes))
