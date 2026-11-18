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
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FLUXOS = RAIZ / ".github" / "workflows"
RELEASE = FLUXOS / "release.yml"
PACOTES = FLUXOS / "pacotes.yml"
META = RAIZ / "desktop" / "uv.meta.json"
APPIMAGE = RAIZ / "desktop" / "appimage.meta.json"
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
    assert f"  {nome}:" in linhas, f"{caminho.name} sem o job {nome}"
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
    # um permissions no topo e um no publicar, só com contents: write
    assert texto.count("permissions:") == 2
    assert _permissoes_do_job(RELEASE, "publicar") == ["contents: write"]
    assert set(re.findall(r"secrets\.\w+", texto)) == {"secrets.GITHUB_TOKEN"}
    assert texto.count("secrets") == 1


def _permissoes_do_job(caminho: Path, nome: str) -> list[str]:
    linhas = _job(caminho, nome).splitlines()
    corpo = []
    for linha in linhas[linhas.index("    permissions:") + 1 :]:
        if not linha.startswith("      "):
            break
        corpo.append(linha.strip())
    return corpo


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
    # sem --latest: o gh marca a release nova como a latest, que o versao.py lê
    assert "--draft" not in publicar and "--prerelease" not in publicar
    assert "--latest" not in publicar
    assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in publicar
    # o publicar só baixa o que o juntar do pacotes.yml montou (e o ensaio provou) e cria a
    # release: confere o SHA256SUMS, não o gera
    assert "name: release" in publicar
    assert "sha256sum -c" in publicar
    assert "merge-multiple" not in publicar and "> SHA256SUMS" not in publicar
    assert "--notes-file ../notas.md" in publicar


def test_juntar_monta_os_anexos_o_sha256sums_e_as_notas() -> None:
    juntar = _job(PACOTES, "juntar")
    assert "needs: [wheel, casca]" in juntar
    assert "merge-multiple: true" in juntar
    assert "shopt -s failglob" in juntar
    assert "sha256sum --" in juntar and "> SHA256SUMS" in juntar
    assert "name: release" in juntar
    for anexo in (
        "*-setup.exe",
        "*.dmg",
        "*.deb",
        "*.rpm",
        "*.AppImage",
        "jobot-atualizacao-*.zip",
        "jobot-*.whl",
        "restricoes.txt",
    ):
        assert anexo in juntar, anexo
    # o navegador não vai na release (D183.24)
    assert "chromium" not in juntar
    # 1 .exe, 2 .dmg, .deb, .rpm, AppImage, 4 pacotes, a wheel e o restricoes.txt
    assert 'test "${#anexos[@]}" = 12' in juntar
    assert "CHANGELOG.md CHANGELOG.en.md" in juntar
    # a versão das notas vem do job wheel, que confere a da tag
    assert "needs.wheel.outputs.versao" in juntar


def test_pacotes_so_chamado_e_sem_escrita() -> None:
    texto = _codigo(PACOTES)
    assert _secao(texto, "on") == ["workflow_call:"]
    assert _secao(texto, "permissions") == ["contents: read"]
    assert texto.count("permissions:") == 1
    assert _jobs(PACOTES) == ["wheel", "casca", "juntar"]
    for nome in _jobs(PACOTES):
        assert "timeout-minutes:" in _job(PACOTES, nome), nome
    # sem segredo, nem herdado de quem chama
    assert "secrets" not in texto
    for quem in (RELEASE, FLUXOS / "casca.yml"):
        assert "secrets: inherit" not in _codigo(quem), quem.name


def test_job_wheel_gera_a_wheel_e_o_restricoes_com_hash() -> None:
    texto = _job(PACOTES, "wheel")
    assert "uv build --wheel" in texto
    assert "uv export --locked --no-dev --no-emit-project --format requirements-txt" in texto
    assert "scripts/montar_recursos.py restricoes" in texto
    # na tag, a versão do pyproject tem de ser a da tag; o passo roda também no ensaio
    assert "GITHUB_REF_NAME" in texto
    assert "if: startsWith(github.ref" not in texto
    assert "versao: ${{ steps.versao.outputs.versao }}" in texto
    # na tag, só a forma vN.N.N, a única que o versao.py e o canal casca leem
    tag = 'if [[ "$GITHUB_REF" == refs/tags/v* ]]; then'
    forma = r'[[ "$GITHUB_REF_NAME" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 1'
    assert forma in texto
    assert texto.index(tag) < texto.index(forma) < texto.index('test "v$versao"')


def _meta() -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(META.read_text(encoding="utf-8"))
    return dados


def test_versoes_do_build_fixadas_como_no_uv_meta() -> None:
    texto = _codigo(PACOTES)
    meta = _meta()
    # o setup-uv com a versão do uv dos recursos, nunca a última
    usos = texto.count("uses: astral-sh/setup-uv@")
    assert usos == 2
    assert texto.count(f'version: "{meta["uv"]["versao"]}"') == usos
    # o Python do uv.meta.json em toda chamada do montar_recursos.py (D183.25; o tar do Chromium
    # que o pedia saiu com a D183.24, o pino fica)
    chamadas = texto.count("scripts/montar_recursos.py")
    pythons = re.findall(r"--python (\S+) python scripts/montar_recursos\.py", texto)
    assert len(pythons) == chamadas == 4
    assert set(pythons) == {meta["python"]["versao"]}
    # o Cargo.lock vale também no build da release
    assert "cargo tauri build --bundles ${{ matrix.pacotes }} -- --locked\n" in texto


def test_artefatos_do_pacotes_vivem_pouco() -> None:
    # os instaladores são grandes (D183.23): o artefato do ensaio some em dois dias
    texto = _codigo(PACOTES)
    assert texto.count("actions/upload-artifact@") == texto.count("retention-days: 2") == 3


def test_job_casca_monta_os_recursos_e_compila_com_o_sha_do_manifesto() -> None:
    texto = _job(PACOTES, "casca")
    for alvo, runner in (
        ("x86_64-unknown-linux-gnu", "ubuntu-22.04"),
        ("x86_64-pc-windows-msvc", "windows-latest"),
        ("aarch64-apple-darwin", "macos-latest"),
        ("x86_64-apple-darwin", "macos-15-intel"),
    ):
        assert re.search(rf"os: {runner}\n\s+alvo: {alvo}\n", texto), alvo
    # o joBot não redistribui o Chrome for Testing do Playwright: nada de navegador no build
    # (D183.24); a fumaça o baixa como a pessoa, pelo --verificar-navegador
    assert "playwright install" not in texto and "--navegadores" not in texto
    assert "chromium-" not in texto
    for passo in (
        "pip==26.2 download --only-binary=:all: --require-hashes",
        "scripts/montar_recursos.py recursos",
        'echo "JOBOT_MANIFESTO_SHA256=',
        "cargo install tauri-cli --version =2.12.4 --locked",
        "cargo tauri build",
        "actions/upload-artifact@",
    ):
        assert passo in texto, passo


def test_ferramentas_do_appimage_conferidas_antes_do_build() -> None:
    # o Tauri só baixa o AppRun, o linuxdeploy e o plugin se não estão no cache (D183.21)
    texto = _job(PACOTES, "casca")
    semear = 'montar_recursos.py ferramentas --saida "${XDG_CACHE_HOME:-$HOME/.cache}/tauri"'
    assert semear in texto
    passo = texto[texto.rindex("- ", 0, texto.index(semear)) : texto.index(semear)]
    assert "if: runner.os == 'Linux'" in passo
    assert texto.index(semear) < texto.index("cargo tauri build")
    ferramentas = json.loads(APPIMAGE.read_text(encoding="utf-8"))
    # os nomes que o bundler do tauri-cli 2.12.4 procura no cache (linuxdeploy.rs)
    assert sorted(ferramentas) == [
        "AppRun-x86_64",
        "linuxdeploy-07333c6-x86_64.AppImage",
        "linuxdeploy-plugin-appimage.AppImage",
    ]
    for nome, f in ferramentas.items():
        assert sorted(f) == ["sha256", "url"], nome
        assert HEX.fullmatch(f["sha256"]), nome
        assert f["url"].startswith("https://github.com/"), nome
        # release com tag fixa, nunca a móvel continuous
        assert "/releases/download/" in f["url"] and "continuous" not in f["url"], nome


def test_ferramentas_baixa_confere_e_poe_o_bit_de_execucao(tmp_path: Path) -> None:
    m = _script()
    origem = tmp_path / "origem"
    origem.mkdir()
    meta = {}
    for nome in ("AppRun-x86_64", "linuxdeploy-07333c6-x86_64.AppImage"):
        (origem / nome).write_bytes(nome.encode())
        meta[nome] = {"url": (origem / nome).as_uri(), "sha256": _sha(nome.encode())}
    cache = tmp_path / "cache" / "tauri"
    m.ferramentas(meta, cache)
    assert sorted(p.name for p in cache.glob("*")) == sorted(meta)
    for nome in meta:
        assert (cache / nome).read_bytes() == nome.encode()
        if os.name == "posix":
            assert (cache / nome).stat().st_mode & 0o111 == 0o111, nome


def test_fumaca_sem_rede_no_linux_no_windows_e_no_mac() -> None:
    texto = _job(PACOTES, "casca")
    # Linux: imagem com as bibliotecas do .deb e do Chromium, e o .deb e o AppImage sem rede
    for passo in (
        "ubuntu:22.04",
        "dpkg-deb -f",
        "apt-get satisfy",
        "install-deps chromium",
        "dpkg -i",
        "APPIMAGE_EXTRACT_AND_RUN=1",
    ):
        assert passo in texto, passo
    # o .deb e o AppImage na 22.04 e o AppImage de novo na 24.04, cada um no seu contêiner e
    # como usuário comum (root leria qualquer arquivo dos recursos): o --verificar sem rede
    # (conferida: só a interface lo) e, depois, com rede, o --verificar-navegador (D183.24)
    assert "useradd -m pessoa" in texto
    linux = texto[texto.index("fumaça (Linux)") : texto.index("AppImage sem lixo no /tmp (Linux)")]
    assert linux.count("docker run") == 1  # dentro da função, chamada três vezes
    ordem = [linux.index('docker network disconnect bridge "$c"')]
    for passo in (
        'test "$(ls /sys/class/net)" = lo',
        'runuser -u pessoa -- $3 --verificar"',
        'docker network connect bridge "$c"',
        "runuser -u pessoa -- $3 --verificar-navegador",
    ):
        ordem.append(linux.index(passo, ordem[-1]))
    assert ordem == sorted(ordem)
    assert "fumaca jobot-fumaca 'dpkg -i /saida/*.deb' jobot-app\n" in linux
    for nome in ("jobot-fumaca", "jobot-fumaca-nova"):
        assert f'fumaca {nome} "$appimage" ./jobot.AppImage\n' in linux, nome
    for imagem, nome in (("ubuntu:22.04", "jobot-fumaca"), ("ubuntu:24.04", "jobot-fumaca-nova")):
        assert f"docker build -t {nome} --build-arg BASE={imagem}" in texto, imagem
    # o AppRun do AppImage exporta o LD_LIBRARY_PATH que a casca tira dos filhos (D183.18):
    # a fumaça falha se não o achar
    assert 'test -n "$ld" && echo "o AppRun exporta: $ld"' in texto
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
    # o próprio instalador também tem regra (é ele que baixaria o WebView2, D183)
    assert "$exes = @($setup) + $exes" in texto
    assert texto.index("$exes = @($setup) + $exes") < texto.index("New-NetFirewallRule")
    # ordem: instalar, conferir, --verificar, conferir, controle, troca pela tela normal e
    # reinstalação, tudo sem rede; só então as regras saem e o navegador vem da internet
    # (D183.24); elas voltam para a desinstalação final
    ordem = [texto.index("Start-Process $setup -ArgumentList '/S'")]
    for passo in (
        "Conferir-Regras\n",
        "'--verificar'",
        "Conferir-Regras\n",
        "WinError 10013",
        '"_?=$inst"',
        "Start-Process $setup -ArgumentList '/S'",
        "Remove-NetFirewallRule",
        "'--verificar-navegador'",
        "Bloquear\n",
        "Start-Process $un -ArgumentList '/S' -Wait\n",
    ):
        ordem.append(texto.index(passo, ordem[-1] + 1))
    assert ordem == sorted(ordem)
    assert "ms-playwright" not in texto and "--playwright" not in texto
    # controle: o Python do venv não sai e o do runner, sem regra, sai
    assert texto.count("socket.create_connection") == 1
    controle = texto[texto.index("socket.create_connection") :]
    assert "& $venvpy -c $teste" in controle
    assert "-match 'WinError 10013'" in controle
    assert "uv run --no-project --python 3.14 python -c $teste" in controle
    assert controle.index("& $venvpy") < controle.index("uv run --no-project")
    # troca pela tela normal: o desinstalador velho no lugar (_?=), como o instalador do Tauri
    troca = texto[texto.index('"_?=$inst"') :]
    assert troca.index("app\\venvs") < troca.index("Start-Process $setup -ArgumentList '/S'")
    assert "instalacao.json" in troca[: troca.index("Start-Process $setup")]
    # depois de desinstalar de verdade, os dados ficam
    assert "Join-Path $inst 'jobot.db'" in texto
    # Mac: o .app de dentro do .dmg, com rede, nos dois passos
    assert "hdiutil attach" in texto
    mac = texto[texto.index("fumaça (Mac, com rede)") :]
    assert mac.index('jobot-app" --verificar\n') < mac.index('jobot-app" --verificar-navegador')


# o gancho, instrução por instrução (sem comentários): o ramo "falta o WebView2" só se prova aqui,
# porque o runner do Windows tem o runtime
_SEM_WEBVIEW2 = (
    "O joBot precisa do Microsoft Edge WebView2 Runtime, que não está instalado neste computador. "
    "Instale-o pela página oficial da Microsoft e rode este instalador de novo: "
    "${JOBOT_WEBVIEW2_URL}"
)
_NO_WEBVIEW2 = (
    "joBot needs the Microsoft Edge WebView2 Runtime, which is not installed on this computer. "
    "Install it from Microsoft's official page and run this installer again: ${JOBOT_WEBVIEW2_URL}"
)
_SE_FALTA = ['${If} $R9 == ""', '${OrIf} $R9 == "0.0.0.0"']
_GANCHO_WEBVIEW2 = [
    'ReadRegStr $R9 HKLM "SOFTWARE\\WOW6432Node\\${JOBOT_WEBVIEW2}" "pv"',
    *_SE_FALTA,
    'ReadRegStr $R9 HKLM "SOFTWARE\\${JOBOT_WEBVIEW2}" "pv"',
    "${EndIf}",
    *_SE_FALTA,
    'ReadRegStr $R9 HKCU "SOFTWARE\\${JOBOT_WEBVIEW2}" "pv"',
    "${EndIf}",
    *_SE_FALTA,
    "${If} $LANGUAGE == 1046",
    f'StrCpy $R8 "{_SEM_WEBVIEW2}"',
    "${Else}",
    f'StrCpy $R8 "{_NO_WEBVIEW2}"',
    "${EndIf}",
    'MessageBox MB_ICONSTOP|MB_OK "$R8" /SD IDOK',
    'Abort "$R8"',
    "${EndIf}",
]


def test_appimage_sem_fuse_nao_deixa_lixo_no_tmp() -> None:
    # T354 (D211): num contêiner sem FUSE, o /tmp volta ao que era depois da saída normal e
    # depois do SIGKILL no grupo do runtime e da casca; o controle mata também o vigia e
    # precisa deixar a pasta, senão a conferência não enxergaria o lixo
    texto = _job(PACOTES, "casca")
    passo = texto[
        texto.index("AppImage sem lixo no /tmp (Linux)") : texto.index(
            "fumaça sem rede e navegador (Windows)"
        )
    ]
    assert "if: runner.os == 'Linux'" in passo
    assert "test ! -e /dev/fuse" in passo
    ordem = [passo.index('antes=$(docker exec "$c" ls -A /tmp)')]
    for trecho in (
        "env APPIMAGE_EXTRACT_AND_RUN=1 ./jobot.AppImage --verificar\n",
        'test "$depois" = "$antes"',
        "bash /lixo/forcar.sh controle",
        "bash /lixo/forcar.sh vigia",
    ):
        ordem.append(passo.index(trecho, ordem[-1]))
    assert ordem == sorted(ordem)
    for trecho in (
        "APPIMAGE_EXTRACT_AND_RUN=1 setsid ./jobot.AppImage --verificar",
        'kill -STOP -- "-$grupo" || { echo "a casca saiu antes da morte forçada"; exit 1; }',
        'kill -KILL -- "-$grupo"',
        "grep -q jobot-vigia",
        'echo "o controle não deixou lixo"; exit 1',
        'echo "nenhum vigia rodando"; cat',
        'echo "sobrou lixo no /tmp"; exit 1',
    ):
        assert trecho in passo, trecho


def test_instalador_do_windows_nao_baixa_o_webview2_e_confere_antes() -> None:
    """D183.20: sem rede na instalação (D174.1); sem o WebView2, aviso e cancela."""
    conf = json.loads((RAIZ / "desktop" / "tauri.conf.json").read_text(encoding="utf-8"))
    windows = conf["bundle"]["windows"]
    assert windows["webviewInstallMode"] == {"type": "skip"}
    assert windows["nsis"]["languages"] == ["English", "PortugueseBR"]
    bruto = (RAIZ / "desktop" / "windows" / "ganchos.nsh").read_bytes()
    # precaução: o tauri-bundler 2.12.4 chama o makensis com -INPUTCHARSET UTF8; o BOM vale
    # também para quem compila o gancho à mão
    assert bruto.startswith(b"\xef\xbb\xbf")
    gancho = bruto.decode("utf-8-sig")
    assert (
        '!define JOBOT_WEBVIEW2 "Microsoft\\EdgeUpdate\\Clients\\'
        '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"' in gancho
    )
    assert (
        '!define JOBOT_WEBVIEW2_URL "https://developer.microsoft.com/microsoft-edge/webview2/"'
        in gancho
    )
    assert gancho.count("!macro NSIS_HOOK_PREINSTALL") == 1
    corpo = gancho[gancho.index("!macro NSIS_HOOK_PREINSTALL") :]
    assert "!macroend" in corpo
    corpo = corpo[: corpo.index("!macroend")]
    instrucoes = [
        linha.strip()
        for linha in corpo.splitlines()[1:]
        if linha.strip() and not linha.strip().startswith((";", "#"))
    ]
    # sem a chave nos três lugares, a caixa (no /S, só a resposta padrão) e o Abort; e nada de
    # download, que nem existe nesta lista
    assert instrucoes == _GANCHO_WEBVIEW2
    # nem outro gancho que baixe: só estes dois macros, e nenhuma instrução de download no arquivo
    assert re.findall(r"^\s*!macro\s+(\S+)", gancho, re.M) == [
        "NSIS_HOOK_PREUNINSTALL",
        "NSIS_HOOK_PREINSTALL",
    ]
    codigo = "\n".join(
        linha for linha in gancho.splitlines() if not linha.strip().startswith((";", "#"))
    ).lower()
    for proibido in ("nsisdl", "inetc", "download"):
        assert proibido not in codigo


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
    # o texto das duas licenças do uv vai junto do binário (desenho 3)
    licencas = meta["uv"].get("licencas", {})
    assert sorted(licencas) == ["LICENSE-APACHE", "LICENSE-MIT"]
    for sha in licencas.values():
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
    assert m.licencas_do_uv(meta) == [
        (
            f"https://raw.githubusercontent.com/astral-sh/uv/{versao_uv}/{nome}",
            nome,
            meta["uv"].get("licencas", {}).get(nome),
        )
        for nome in ("LICENSE-APACHE", "LICENSE-MIT")
    ]


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
    licencas = tmp_path / "licencas"
    licencas.mkdir()
    for nome in ("LICENSE-MIT", "LICENSE-APACHE"):
        (licencas / nome).write_text(f"texto da {nome}", encoding="utf-8")
    return {
        "licencas": licencas,
        "uv": _uv_falso(tmp_path, alvo),
        "python": python,
        "rodas": rodas,
        "roda": roda,
        "restricoes": restricoes,
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
        versao="0.3.0",
        uv=c["uv"],
        python=c["python"],
        tag="20261110",
        rodas=c["rodas"],
        roda=c["roda"],
        restricoes=c["restricoes"],
        licencas=sorted(c["licencas"].iterdir()),
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
        "bin/uv.tar",
        "licencas/uv/LICENSE-APACHE",
        "licencas/uv/LICENSE-MIT",
        f"python/20261110/{c['python'].name}",
        "restricoes.txt",
        "wheels/httpx-0.28.1-py3-none-any.whl",
        "wheels/jobot-0.3.0-py3-none-any.whl",
    ]
    for nome, (tamanho, sha_arquivo) in manifesto.items():
        dados = (saida / nome).read_bytes()
        assert (tamanho, sha_arquivo) == (len(dados), _sha(dados)), nome
    assert (saida / "licencas" / "uv" / "LICENSE-MIT").read_text(encoding="utf-8") == (
        "texto da LICENSE-MIT"
    )


def test_pacote_de_atualizacao_no_formato_do_canal_casca(tmp_path: Path) -> None:
    m = _script()
    alvo = "x86_64-pc-windows-msvc"
    c = _cenario(tmp_path, alvo)
    saida = tmp_path / "recursos"
    m.montar(
        saida=saida,
        versao="0.3.0",
        uv=c["uv"],
        python=c["python"],
        tag="20261110",
        rodas=c["rodas"],
        roda=c["roda"],
        restricoes=c["restricoes"],
        licencas=sorted(c["licencas"].iterdir()),
    )
    # o uv vai num tar ustar sem compressão, de um arquivo só, que a casca abre (D183)
    assert (saida / "bin" / "uv.tar").read_bytes()[257:263] == b"ustar\x00"
    with tarfile.open(saida / "bin" / "uv.tar", "r:") as tar:
        (membro,) = tar.getmembers()
        assert (membro.name, membro.mode) == ("uv.exe", 0o755)
        leitor = tar.extractfile(membro)
        assert leitor is not None and leitor.read() == b"uv falso"
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
    assert set(manifesto) == set(dentro)


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
    saida = tmp_path / "recursos"
    m.montar(
        saida=saida,
        versao="0.3.0",
        uv=c["uv"],
        python=python,
        tag="20261110",
        rodas=c["rodas"],
        roda=c["roda"],
        restricoes=c["restricoes"],
        licencas=sorted(c["licencas"].iterdir()),
    )
    inst = "C:\\U\\AppData\\Local\\joBot"
    exes = m.exes_do_windows(saida, inst, "0.3.0")
    casca = inst + "\\app"
    venv = casca + "\\venvs\\venv-0.3.0"
    cpython = casca + "\\python\\cpython-3.14.10-windows-x86_64-none"
    for esperado in (
        inst + "\\jobot-app.exe",
        inst + "\\uninstall.exe",
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
    ):
        assert esperado in exes, esperado
    assert len(exes) == len(set(exes))
