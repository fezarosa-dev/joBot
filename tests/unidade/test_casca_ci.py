"""Prende o `casca.yml` (gatilhos, permissões, jobs, actions) e a página da prova da janela."""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from jobot.painel.app import CABECALHOS

RAIZ = Path(__file__).resolve().parents[2]
CASCA = RAIZ / ".github" / "workflows" / "casca.yml"


def _codigo() -> str:
    # O comentário do topo cita pull_request_target para proibi-lo: só o código conta.
    bruto = CASCA.read_text(encoding="utf-8")
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


def test_casca_roda_em_pr_em_lote_e_a_mao_sem_segredo() -> None:
    texto = _codigo()
    assert _secao(texto, "on") == [
        "pull_request:",
        "push:",
        "branches: ['lote/**']",
        "workflow_dispatch:",
        "inputs:",
        "pacotes:",
        "description: Gera os instaladores, sem publicar",
        "type: boolean",
        "default: false",
        "ia:",
        "description: Prova o modelo local de verdade (T410)",
        "type: boolean",
        "default: false",
    ]
    assert "pull_request_target" not in texto
    assert _secao(texto, "permissions") == ["contents: read"]
    assert texto.count("permissions:") == 1
    assert re.findall(r"secrets\.\w+", texto) == []


def test_actions_fixadas_por_hash_com_versao() -> None:
    usos = re.findall(r"^\s*(?:- )?uses: (.+)$", CASCA.read_text(encoding="utf-8"), re.MULTILINE)
    assert usos
    for uso in usos:
        if uso in ("./.github/workflows/pacotes.yml", "./.github/workflows/ia.yml"):
            continue
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+", uso), uso


def _job(nome: str) -> str:
    """O bloco de um job (do `  nome:` até o próximo job), sem os comentários."""
    linhas = _codigo().splitlines()
    inicio = linhas.index(f"  {nome}:") + 1
    corpo = []
    for linha in linhas[inicio:]:
        if re.match(r"  \S", linha) or (linha and not linha.startswith(" ")):
            break
        corpo.append(linha)
    return "\n".join(corpo)


def test_jobs_da_casca() -> None:
    jobs = re.findall(r"^  (\w+):$", _codigo().split("\njobs:\n", 1)[1], re.MULTILINE)
    assert jobs == ["casca", "windows", "uv", "pacotes", "ia"]
    # o pacotes e o ia chamam o pacotes.yml e o ia.yml, que têm os prazos deles
    for nome in jobs[:-2]:
        assert "timeout-minutes:" in _job(nome), nome


def test_job_casca_confere_rust_e_a_janela_sob_xvfb() -> None:
    texto = _job("casca")
    assert "runs-on: ubuntu-22.04" in texto
    for passo in (
        "libwebkit2gtk-4.1-dev",
        "--component rustfmt --component clippy",
        "cargo fmt --check",
        "cargo clippy --locked --all-targets -- -D warnings",
        "cargo test --locked",
        "xvfb-run",
        "--verificar-janela",
        "scripts/prova_janela.py",
    ):
        assert passo in texto, passo


def test_job_windows_roda_os_testes_de_sistema() -> None:
    texto = _job("windows")
    assert "runs-on: windows-latest" in texto
    assert "uv sync --locked" in texto
    filtro = '-k "pastas or instancia or processo or segundo_plano or atualizar"'
    assert f"uv run pytest tests/unidade {filtro}" in texto
    # os ramos #[cfg(windows)] da casca (nota da revisão da T337)
    assert "--component clippy" in texto
    assert "cargo clippy --locked --all-targets -- -D warnings" in texto
    assert "cargo test --locked" in texto


def test_job_uv_so_a_mao_nos_tres_sistemas() -> None:
    texto = _job("uv")
    assert "if: github.event_name == 'workflow_dispatch'" in texto
    assert "os: [ubuntu-latest, windows-latest, macos-latest]" in texto
    assert "runs-on: ${{ matrix.os }}" in texto
    assert "uv run python scripts/provar_uv.py" in texto


def test_job_pacotes_so_com_a_entrada_e_sem_publicar() -> None:
    texto = _job("pacotes")
    assert "if: github.event_name == 'workflow_dispatch' && inputs.pacotes" in texto
    # os mesmos pacotes e a mesma fumaça sem rede da release, sem o publicar (T339)
    assert "uses: ./.github/workflows/pacotes.yml" in texto
    assert "release" not in texto


def test_job_ia_so_com_a_entrada() -> None:
    texto = _job("ia")
    assert "if: github.event_name == 'workflow_dispatch' && inputs.ia" in texto
    assert "uses: ./.github/workflows/ia.yml" in texto
    assert "secrets" not in texto


def _prova() -> ModuleType:
    caminho = RAIZ / "scripts" / "prova_janela.py"
    spec = importlib.util.spec_from_file_location("prova_janela", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_prova_manda_os_cabecalhos_reais_do_painel() -> None:
    assert _prova().cabecalhos(com_ipc=False) == CABECALHOS


def test_prova_com_ipc_so_acrescenta_a_origem_ao_connect_src() -> None:
    com = _prova().cabecalhos(com_ipc=True)
    csp = com.pop("Content-Security-Policy", "")
    original = CABECALHOS["Content-Security-Policy"]
    assert com == {k: v for k, v in CABECALHOS.items() if k != "Content-Security-Policy"}
    assert csp == original.replace(
        "connect-src 'self';", "connect-src 'self' ipc: http://ipc.localhost;"
    )
    assert csp != original
