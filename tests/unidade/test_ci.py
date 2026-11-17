"""Prende os gatilhos e as permissões do CI lendo o texto do workflow."""

import re
from pathlib import Path

import pytest

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


def _jobs(texto: str) -> dict[str, str]:
    """Os jobs do workflow: nome -> texto do bloco (sem YAML: os testes não o leem)."""
    corpo = texto.split("\njobs:\n", 1)[1]
    partes = re.split(r"^  (\w+):\n", corpo, flags=re.MULTILINE)
    return dict(zip(partes[1::2], partes[2::2], strict=True))


def _confere_estrutura(texto: str) -> None:
    jobs = _jobs(texto)
    assert set(jobs) == {"lint", "comuns", "tela", "ok"}
    for nome, bloco in jobs.items():
        assert re.search(r"^    timeout-minutes: \d+$", bloco, re.MULTILINE), nome
    for nome, quantas in (("comuns", 2), ("tela", 16)):
        bloco = jobs[nome]
        assert "      fail-fast: false\n" in bloco, nome
        achou = re.search(r"^        parte: \[([\d, ]+)\]$", bloco, re.MULTILINE)
        assert achou is not None, nome
        assert [int(x) for x in achou[1].split(",")] == list(range(1, quantas + 1)), nome
    assert "    needs: [lint, comuns, tela]\n" in jobs["ok"]
    assert "    if: always()\n" in jobs["ok"]


def test_ci_tem_jobs_em_paralelo_e_o_ok_que_junta_tudo() -> None:
    _confere_estrutura(CI.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "tira",
    ["    needs: [lint, comuns, tela]\n", "    timeout-minutes: 5\n", "      fail-fast: false\n"],
)
def test_estrutura_do_ci_reprova_quando_falta_peca(tira: str) -> None:
    texto = CI.read_text(encoding="utf-8")
    assert tira in texto
    with pytest.raises(AssertionError):
        _confere_estrutura(texto.replace(tira, "", 1))
