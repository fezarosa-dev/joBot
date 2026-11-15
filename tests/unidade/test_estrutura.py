import ast
import json
from pathlib import Path

from jobot.nucleo.coletores import registro

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "jobot"
COLETORES = FONTE / "nucleo" / "coletores"
INFRAESTRUTURA = {"base.py", "executor.py", "registro.py", "paginas.py", "descoberta_cc.py"}
TIPOS = {"carreiras", "plataformas", "agregadores", "portais"}


def test_todo_pacote_explica_o_que_faz() -> None:
    sem_explicacao = [
        str(init.relative_to(RAIZ))
        for init in sorted(FONTE.rglob("__init__.py"))
        if not (ast.get_docstring(ast.parse(init.read_text(encoding="utf-8"))) or "").strip()
    ]
    assert sem_explicacao == [], f"__init__.py sem docstring: {sem_explicacao}"


def test_coletor_mora_na_pasta_do_tipo() -> None:
    na_raiz = {p.name for p in COLETORES.glob("*.py")}
    assert na_raiz == INFRAESTRUTURA | {"__init__.py"}
    soltos = [
        p.name
        for p in COLETORES.glob("*.py")
        if any(
            isinstance(no, ast.Assign)
            and any(getattr(a, "id", "") == "COLETOR" for a in no.targets)
            or isinstance(no, ast.AnnAssign)
            and getattr(no.target, "id", "") == "COLETOR"
            for no in ast.parse(p.read_text(encoding="utf-8")).body
        )
    ]
    assert soltos == []
    assert {p.name for p in COLETORES.iterdir() if p.is_dir() and p.name != "__pycache__"} == TIPOS


def test_descobrir_acha_todos_os_coletores() -> None:
    fontes = json.loads((FONTE / "nucleo" / "dados" / "fontes.json").read_text(encoding="utf-8"))
    assert set(registro.descobrir()) == set(fontes)
