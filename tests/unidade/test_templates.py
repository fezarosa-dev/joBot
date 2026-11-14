"""Templates do painel: autoescape sempre e `|safe` só na lista curta (desenho 14.3)."""

import re
from pathlib import Path

from jobot.painel import seguranca

TEMPLATES = Path(seguranca.__file__).parent / "templates"
# lista curta e revisada: caminho relativo a templates/ de quem pode usar |safe
LISTA_CURTA: frozenset[str] = frozenset()
PROIBIDO = re.compile(r"\|\s*safe\b|autoescape\s+false")


def test_safe_so_na_lista_curta() -> None:
    achados = [
        str(arquivo.relative_to(TEMPLATES))
        for arquivo in sorted(TEMPLATES.rglob("*"))
        if arquivo.is_file() and PROIBIDO.search(arquivo.read_text(encoding="utf-8"))
    ]
    assert [a for a in achados if a not in LISTA_CURTA] == []


def test_autoescape_ligado_em_todo_template() -> None:
    # True, não select_autoescape(): vale para qualquer extensão de arquivo
    assert seguranca.TEMPLATES.env.autoescape is True
