"""As rotas do painel não copiam o relógio nem o leitor sem validadores (T129, A49)."""

import ast
from pathlib import Path

PAINEL = Path(__file__).resolve().parents[2] / "src/jobot/painel"
ROTAS = sorted((PAINEL / "rotas").glob("*.py"))
USAM_A_HORA = ("buscas", "configuracoes", "empresas", "primeira_execucao", "sugeridas")


def _arvore(caminho: Path) -> ast.Module:
    return ast.parse(caminho.read_text(encoding="utf-8"))


def test_rotas_sem_copia_de_relogio() -> None:
    for rota in ROTAS:
        arvore = _arvore(rota)
        definidos = {n.name for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)}
        assert "_relogio" not in definidos, rota.name
        if rota.name != "vagas.py":
            # a leitura de app.state.relogio mora só em relogio_do_painel, qualquer que seja o nome
            assert '"relogio", None' not in rota.read_text(encoding="utf-8"), rota.name
    for nome in USAM_A_HORA:
        importados = {
            (n.module, a.name)
            for n in ast.walk(_arvore(PAINEL / "rotas" / f"{nome}.py"))
            if isinstance(n, ast.ImportFrom)
            for a in n.names
        }
        assert ("jobot.painel.rotas.vagas", "relogio_do_painel") in importados, nome


def test_sem_validadores_definido_uma_vez() -> None:
    donos = [
        f"{caminho.relative_to(PAINEL)}:{n.name}"
        for caminho in PAINEL.rglob("*.py")
        for n in ast.walk(_arvore(caminho))
        if isinstance(n, ast.ClassDef) and n.name.lstrip("_") == "SemValidadores"
    ]
    assert len(donos) == 1, donos
    for nome in ("empresas", "sugeridas"):
        importados = {
            a.name
            for n in ast.walk(_arvore(PAINEL / "rotas" / f"{nome}.py"))
            if isinstance(n, ast.ImportFrom)
            for a in n.names
        }
        assert "SemValidadores" in importados, nome
