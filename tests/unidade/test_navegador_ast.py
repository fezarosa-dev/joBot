"""Guarda por AST: o navegador só usa a lista permitida do Playwright (D132.38)."""

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest
from playwright.async_api import (
    Browser,
    BrowserContext,
    Frame,
    Locator,
    Page,
    Request,
    Response,
)

RAIZ = Path(__file__).resolve().parents[2]
NAVEGADOR = RAIZ / "src" / "jobot" / "navegador"
JS = NAVEGADOR / "js.py"
CAPTURAR_LOGADO = RAIZ / "scripts" / "capturar_logado.py"

# Nomes públicos dos objetos do Playwright (APIRequestContext e APIResponse ficam de fora:
# chegar a eles exige `.request`, que sempre reprova).
CLASSES = (Page, Frame, Locator, BrowserContext, Browser, Request, Response)
PUBLICOS = {n for c in CLASSES for n in dir(c) if not n.startswith("_")}

PERMITIDOS = {
    "launch_persistent_context",  # BrowserType
    "new_page",
    "pages",
    "goto",
    "wait_for_load_state",
    "content",
    "url",
    "title",
    "close",
    "is_closed",
    "frames",
    "on",
    "once",
    "locator",
    "get_attribute",
    "inner_text",
    "count",
    "all",
    "headers",
    "status",
    "text",
    "body",
}
TOLERADOS = {"name"}  # só leitura em Frame
SEMPRE_RECUSADOS = {"request", "all_headers", "evaluate"}
EVENTOS = {"response", "request", "close"}
SCRIPTS = {"ROLAR", "ENTREGAR_TOKEN", "USER_AGENT"}


def _ruins_da_lista(arquivos: Iterable[Path]) -> list[str]:
    ruins: list[str] = []
    for arquivo in arquivos:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            onde = f"{arquivo.name}:{getattr(no, 'lineno', 0)}"
            if isinstance(no, ast.Attribute):
                if no.attr in SEMPRE_RECUSADOS or (
                    no.attr in PUBLICOS and no.attr not in PERMITIDOS | TOLERADOS
                ):
                    ruins.append(f"{onde}: {no.attr}")
            elif (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Name)
                and no.func.id in {"getattr", "setattr"}
            ):
                nome = no.args[1] if len(no.args) > 1 else None
                if (
                    isinstance(nome, ast.Constant)
                    and nome.value in PUBLICOS
                    and nome.value not in PERMITIDOS | TOLERADOS
                ):
                    ruins.append(f"{onde}: {no.func.id} de {nome.value}")
            elif (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr in {"on", "once"}
            ):
                primeiro = no.args[0] if no.args else None
                if not (isinstance(primeiro, ast.Constant) and primeiro.value in EVENTOS):
                    ruins.append(f"{onde}: {no.func.attr} com evento fora da lista")
    return ruins


def _ruins_do_js(arquivo: Path) -> list[str]:
    """`evaluate` só com um dos três scripts, e cada um literal; nenhum outro script."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    # js.py também fica sob a lista permitida; só o `evaluate` é liberado (e conferido abaixo)
    ruins = [r for r in _ruins_da_lista([arquivo]) if not r.endswith(": evaluate")]
    achados: set[str] = set()
    # só a docstring de verdade (primeira instrução do módulo, função ou classe)
    docstrings = {
        id(no.body[0].value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and no.body
        and isinstance(no.body[0], ast.Expr)
        and isinstance(no.body[0].value, ast.Constant)
    }
    literais: set[int] = set()
    for instr in arvore.body:
        alvo, valor = None, None
        if isinstance(instr, ast.AnnAssign) and isinstance(instr.target, ast.Name):
            alvo, valor = instr.target.id, instr.value
        elif isinstance(instr, ast.Assign) and isinstance(instr.targets[0], ast.Name):
            alvo, valor = instr.targets[0].id, instr.value
        if alvo in SCRIPTS:
            achados.add(alvo)
            if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                literais.add(id(valor))
            else:
                ruins.append(f"{arquivo.name}:{instr.lineno}: {alvo} não é literal")
    ruins += [f"{arquivo.name}: falta {n}" for n in sorted(SCRIPTS - achados)]
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            if no.func.attr == "evaluate":
                primeiro = no.args[0] if no.args else None
                if not (isinstance(primeiro, ast.Name) and primeiro.id in SCRIPTS):
                    ruins.append(f"{arquivo.name}:{no.lineno}: evaluate fora dos três scripts")
        if (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in literais
            and id(no) not in docstrings
            and ("=>" in no.value or "function" in no.value)
        ):
            ruins.append(f"{arquivo.name}:{no.lineno}: script solto")
    return ruins


def _alvos() -> list[Path]:
    alvos = [p for p in sorted(NAVEGADOR.rglob("*.py")) if p != JS]
    return [*alvos, *([CAPTURAR_LOGADO] if CAPTURAR_LOGADO.exists() else [])]


def test_pacote_navegador_existe_e_e_conferido() -> None:
    assert JS in NAVEGADOR.rglob("*.py")
    assert NAVEGADOR / "__init__.py" in _alvos()


def test_lista_permitida_do_navegador() -> None:
    assert _ruins_da_lista(_alvos()) == []


def test_tolerados_sao_so_name() -> None:
    assert TOLERADOS == {"name"}


def test_lista_permitida_so_tem_nomes_conhecidos() -> None:
    # nome na lista que sumiu do Playwright instalado é erro de digitação ou versão nova
    assert PERMITIDOS - PUBLICOS <= {"launch_persistent_context"}
    assert not (PERMITIDOS & SEMPRE_RECUSADOS)
    assert {"wait_for", "json"} <= PUBLICOS - PERMITIDOS


def test_scripts_de_js_sao_literais_e_so_os_tres() -> None:
    assert _ruins_do_js(JS) == []


def test_so_js_chama_evaluate() -> None:
    assert [r for r in _ruins_da_lista(_alvos()) if r.endswith("evaluate")] == []


@pytest.mark.parametrize(
    "codigo",
    [
        'ROLAR = f"() => {x}"\nENTREGAR_TOKEN = "a"\nUSER_AGENT = "b"\n',
        'ROLAR = "() => " + x\nENTREGAR_TOKEN = "a"\nUSER_AGENT = "b"\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\nUSER_AGENT = "c"\nawait p.evaluate(x)\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\nUSER_AGENT = "c"\nawait p.evaluate("() => 1")\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\nUSER_AGENT = "c"\nX = "() => 1"\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\nUSER_AGENT = "c"\nX = "function f() {}"\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\nUSER_AGENT = "c"\n"() => 1"\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\nUSER_AGENT = "c"\ndef f():\n    pass\n"function x"\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\nUSER_AGENT = "c"\npage.click("x")\n',
        'ROLAR = "a"\nENTREGAR_TOKEN = "b"\nUSER_AGENT = "c"\npage.route("**", f)\n',
    ],
)
def test_detector_do_js_acha_o_ruim(tmp_path: Path, codigo: str) -> None:
    arquivo = tmp_path / "js.py"
    arquivo.write_text(codigo)
    assert _ruins_do_js(arquivo) != []


def test_detector_do_js_aceita_o_bom(tmp_path: Path) -> None:
    arquivo = tmp_path / "js.py"
    arquivo.write_text(
        '"""function => doc."""\n'
        'ROLAR: Final = "() => 1"\nENTREGAR_TOKEN = "() => 2"\nUSER_AGENT = "() => 3"\n'
        "async def f(p):\n    await p.evaluate(ROLAR)\n    await p.evaluate(ENTREGAR_TOKEN, [1])\n"
    )
    assert _ruins_do_js(arquivo) == []


@pytest.mark.parametrize(
    "codigo",
    [
        "page.click()",
        'page.evaluate("x")',
        'page.route("**", f)',
        "context.request.get(u)",
        "pedido.all_headers()",
        'page.on("dialog", f)',
        "page.on(nome, f)",
        'page.get_by_role("x")',
        "d.clear()",
        "await page.wait_for(1)",
        'getattr(page, "click")()',
        'setattr(page, "route", f)',
        "(await resposta.json())",
    ],
)
def test_detector_da_lista_permitida_acha_o_ruim(tmp_path: Path, codigo: str) -> None:
    arquivo = tmp_path / "ruim.py"
    arquivo.write_text(codigo + "\n")
    assert _ruins_da_lista([arquivo]) != []


def test_detector_da_lista_permitida_aceita_o_bom(tmp_path: Path) -> None:
    arquivo = tmp_path / "bom.py"
    arquivo.write_text(
        "page.goto(u)\n"
        'page.locator("x").get_attribute("y")\n'
        'page.on("response", f)\n'
        'page.once("close", f)\n'
        "pedido.headers\n"
        "frame.name\n"
        "json.loads(await resposta.text())\n"
        "asyncio.timeout(3)\n"
        'getattr(obj, "nome_qualquer")\n'
        "getattr(obj, nome)\n"
    )
    assert _ruins_da_lista([arquivo]) == []
