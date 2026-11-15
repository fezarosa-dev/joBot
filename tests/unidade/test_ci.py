"""Prende os gatilhos e as permissões do CI lendo o texto do workflow."""

import re
from pathlib import Path

CI = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


def _secao(texto: str, chave: str) -> list[str]:
    linhas = texto.splitlines()
    inicio = linhas.index(f"{chave}:")
    corpo = []
    for linha in linhas[inicio + 1 :]:
        if linha and not linha.startswith(" "):
            break
        if linha.strip() and not linha.strip().startswith("#"):
            corpo.append(linha.strip())
    return corpo


def test_ci_roda_em_pr_em_lote_e_a_mao() -> None:
    bruto = CI.read_text(encoding="utf-8")
    # O comentário do topo cita pull_request_target para proibi-lo: só o código conta.
    texto = "\n".join(x for x in bruto.splitlines() if not x.lstrip().startswith("#"))
    assert _secao(texto, "on") == [
        "pull_request:",
        "push:",
        "branches: ['lote/**']",
        "workflow_dispatch:",
    ]
    assert "pull_request_target" not in texto
    assert _secao(texto, "permissions") == ["contents: read"]
    assert texto.count("permissions:") == 1
    assert set(re.findall(r"secrets\.(\w+)", texto)) <= {"GITHUB_TOKEN"}
