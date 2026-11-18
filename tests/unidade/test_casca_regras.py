"""A casca (Rust) acha a pasta de dados com a mesma regra de `pastas.py` (desenho 7.1).

Conferência por texto: `pastas.py` é a fonte; `desktop/src/servidor.rs` repete os caminhos
(um `&[...]` por caminho) e as variáveis de ambiente. Se divergir muito, a casca passa a
perguntar `jobot dados --json`.
"""

import ast
import json
import re
from pathlib import Path

from jobot.sistema import instancia, pastas

RAIZ = Path(__file__).resolve().parents[2]
SERVIDOR = RAIZ / "desktop" / "src" / "servidor.rs"
_ENV = re.compile(r"[A-Z][A-Z_]+")


def _funcao_python() -> ast.FunctionDef:
    arvore = ast.parse(Path(pastas.__file__).read_text(encoding="utf-8"))
    return next(
        n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "pasta_de_dados"
    )


def _partes(no: ast.expr | None) -> list[str]:
    """`base / "a" / "b"` vira `["a", "b"]`."""
    if (
        isinstance(no, ast.BinOp)
        and isinstance(no.op, ast.Div)
        and isinstance(no.right, ast.Constant)
        and isinstance(no.right.value, str)
    ):
        return [*_partes(no.left), no.right.value]
    return []


def _corpo_rust() -> str:
    texto = SERVIDOR.read_text(encoding="utf-8")
    inicio = texto.index("pub fn pasta_de_dados(")
    return texto[inicio : texto.index("\n}\n", inicio)]


def test_mesmos_caminhos_da_pasta_de_dados() -> None:
    python = sorted(
        tuple(p)
        for no in ast.walk(_funcao_python())
        if isinstance(no, ast.Return) and (p := _partes(no.value))
    )
    rust = sorted(
        tuple(re.findall(r'"([^"]*)"', lista))
        for lista in re.findall(r"&\[([^\]]*)\]", _corpo_rust())
    )
    assert len(python) == 5
    assert rust == python


def test_mesmas_variaveis_de_ambiente() -> None:
    python = {
        no.value
        for no in ast.walk(_funcao_python())
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and _ENV.fullmatch(no.value)
    }
    rust = {v for v in re.findall(r'"([^"]*)"', _corpo_rust()) if _ENV.fullmatch(v)}
    assert "JOBOT_DADOS" in python
    assert rust == python


def test_mesma_porta_padrao() -> None:
    texto = SERVIDOR.read_text(encoding="utf-8")
    assert f"pub const PORTA_PADRAO: u16 = {instancia.PORTA_PADRAO};" in texto


def test_desinstalar_no_windows_chama_a_casca_fora_da_atualizacao() -> None:
    # desenho 7.2 (T337): o NSIS só chama `--desinstalar` da casca; quem desliga o segundo
    # plano, para o servidor e apaga a pasta da casca é o Rust. Na troca de versão (pelo
    # updater, `/UPDATE`, ou pela tela normal), nada disso roda: o venv e o segundo plano
    # continuam (D182).
    desktop = RAIZ / "desktop"
    conf = json.loads((desktop / "tauri.conf.json").read_text(encoding="utf-8"))
    nsis = conf["bundle"].get("windows", {}).get("nsis", {})
    assert "installerHooks" in nsis
    ganchos = desktop / nsis["installerHooks"]
    texto = ganchos.read_text(encoding="utf-8")
    corpo = texto.split("!macro NSIS_HOOK_PREUNINSTALL", 1)[1].split("!macroend", 1)[0]
    assert "${If} $UpdateMode <> 1" in corpo
    # troca manual (o .exe novo pela tela normal): o instalador novo roda o desinstalador
    # velho no lugar (`_?=`), então ele roda de dentro de $INSTDIR; o desinstalador de
    # verdade se copia para o temporário antes. Assim só a desinstalação de verdade apaga.
    assert "${AndIf} $EXEDIR != $INSTDIR" in corpo
    assert "ExecWait '\"$INSTDIR\\${MAINBINARYNAME}.exe\" --desinstalar'" in corpo
    assert '"--desinstalar"' in (desktop / "src" / "main.rs").read_text(encoding="utf-8")


def test_comandos_das_paginas_estao_nas_quatro_listas() -> None:
    # T350: o comando que a página chama precisa estar no build.rs (AppManifest), no
    # generate_handler! do main.rs e como allow-<kebab> no local.json; faltar em um deles
    # compila e passa nos testes, mas a janela de verdade só responde com erro
    desktop = RAIZ / "desktop"
    ui = desktop / "ui"
    js = (ui / "controle.js").read_text(encoding="utf-8")
    chamados = set(re.findall(r'(?:chamar|agir)\("(\w+)"', js))
    chamados |= set(
        re.findall(r'invoke\("(\w+)"', (ui / "instalador.js").read_text(encoding="utf-8"))
    )
    assert {"estado_controle", "ligar", "parar", "abrir_jobot", "instalar"} <= chamados
    build = (desktop / "build.rs").read_text(encoding="utf-8")
    manifesto = set(re.findall(r'"(\w+)"', build.split(".commands(&[", 1)[1].split("]", 1)[0]))
    main = (desktop / "src" / "main.rs").read_text(encoding="utf-8")
    handler = set(re.findall(r"\w+", main.split("generate_handler![", 1)[1].split("]", 1)[0]))
    local = json.loads((desktop / "capabilities" / "local.json").read_text(encoding="utf-8"))
    permitidos = {p.removeprefix("allow-").replace("-", "_") for p in local["permissions"]}
    assert chamados == manifesto == handler, (chamados, manifesto, handler)
    assert chamados <= permitidos, chamados - permitidos
