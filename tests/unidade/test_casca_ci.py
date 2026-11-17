"""Prende o `casca.yml` (gatilhos, permissões, actions fixadas) e a página da prova da janela."""

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
    ]
    assert "pull_request_target" not in texto
    assert _secao(texto, "permissions") == ["contents: read"]
    assert texto.count("permissions:") == 1
    assert re.findall(r"secrets\.\w+", texto) == []


def test_actions_fixadas_por_hash_com_versao() -> None:
    usos = re.findall(r"^\s*(?:- )?uses: (.+)$", CASCA.read_text(encoding="utf-8"), re.MULTILINE)
    assert usos
    for uso in usos:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+", uso), uso


def test_job_linux_confere_a_janela_sob_xvfb() -> None:
    texto = _codigo()
    assert "runs-on: ubuntu-22.04" in texto
    assert "timeout-minutes:" in texto
    for passo in (
        "libwebkit2gtk-4.1-dev",
        "cargo fmt --check",
        "cargo test --locked",
        "xvfb-run",
        "--verificar-janela",
        "scripts/prova_janela.py",
    ):
        assert passo in texto, passo


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
