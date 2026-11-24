"""Templates do painel: autoescape sempre e `|safe` só na lista curta (desenho 14.3)."""

import ast
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


def test_detalhe_ao_lado_repassa_todo_o_contexto_do_detalhe() -> None:
    # a página usa o dict inteiro; o detalhe ao lado repassa chave por chave no `with`, e a que
    # faltar some em silêncio (Undefined do Jinja), como as habilidades da IA antes
    arvore = ast.parse((TEMPLATES.parent / "detalhe_vaga.py").read_text(encoding="utf-8"))
    funcao = next(
        n
        for n in ast.walk(arvore)
        if isinstance(n, ast.FunctionDef) and n.name == "contexto_do_detalhe"
    )
    retorno = next(n.value for n in ast.walk(funcao) if isinstance(n, ast.Return))
    assert isinstance(retorno, ast.Dict)
    chaves = {k.value for k in retorno.keys if isinstance(k, ast.Constant)}
    lado = (TEMPLATES / "vagas" / "detalhe_lado.html").read_text(encoding="utf-8")
    com = re.search(r"{%-?\s*with\s+(.*?)\s*-?%}", lado, re.S)
    assert com is not None
    repassadas = dict(re.findall(r"(\w+)=detalhe\.(\w+)", com.group(1)))
    assert all(nome == chave for nome, chave in repassadas.items())
    assert chaves and set(repassadas) == chaves
