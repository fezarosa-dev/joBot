"""As rotas do painel não copiam relógio, leitor sem validadores nem auxiliares (T129, T131)."""

import ast
from pathlib import Path

PAINEL = Path(__file__).resolve().parents[2] / "src/jobot/painel"
ROTAS = sorted((PAINEL / "rotas").glob("*.py"))
USAM_A_HORA = ("buscas", "configuracoes", "empresas", "primeira_execucao", "vagas")


def _arvore(caminho: Path) -> ast.Module:
    return ast.parse(caminho.read_text(encoding="utf-8"))


def _funcoes(arvore: ast.Module, *, so_do_modulo: bool = False) -> list[str]:
    tipos = (ast.FunctionDef, ast.AsyncFunctionDef)
    nos = arvore.body if so_do_modulo else ast.walk(arvore)
    return [n.name for n in nos if isinstance(n, tipos)]


def _le_o_relogio_do_estado(arvore: ast.Module) -> bool:
    """`<algo>.state.relogio` ou `getattr(<algo>, "relogio", ...)`, qualquer que seja o jeito."""
    for n in ast.walk(arvore):
        if isinstance(n, ast.Attribute) and n.attr == "relogio":
            if isinstance(n.value, ast.Attribute) and n.value.attr == "state":
                return True
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "getattr"
            and len(n.args) >= 2
            and isinstance(n.args[1], ast.Constant)
            and n.args[1].value == "relogio"
        ):
            return True
    return False


def test_prova_do_relogio_pega_as_formas_de_ler_o_estado() -> None:
    """Controle do detector: as formas de ler caem, o uso de `relogio_do_painel` não."""
    pega = [
        "request.app.state.relogio",
        "getattr(request.app.state, 'relogio', None)",
        'getattr(request.app.state, "relogio")',
    ]
    for fonte in pega:
        assert _le_o_relogio_do_estado(ast.parse(fonte)), fonte
    assert not _le_o_relogio_do_estado(ast.parse("relogio_do_painel(request).agora()"))
    assert not _le_o_relogio_do_estado(ast.parse("getattr(request.app.state, 'ambiente', None)"))


def test_rotas_sem_copia_de_relogio() -> None:
    for rota in ROTAS:
        arvore = _arvore(rota)
        assert "_relogio" not in _funcoes(arvore), rota.name
        # a leitura de app.state.relogio mora só em relogio_do_painel, em `painel/consultas.py`
        assert not _le_o_relogio_do_estado(arvore), rota.name
    for nome in USAM_A_HORA:
        importados = {
            (n.module, a.name)
            for n in ast.walk(_arvore(PAINEL / "rotas" / f"{nome}.py"))
            if isinstance(n, ast.ImportFrom)
            for a in n.names
        }
        assert ("jobot.painel.consultas", "relogio_do_painel") in importados, nome


def test_sem_validadores_definido_uma_vez() -> None:
    donos = [
        f"{caminho.relative_to(PAINEL)}:{n.name}"
        for caminho in PAINEL.rglob("*.py")
        for n in ast.walk(_arvore(caminho))
        if isinstance(n, ast.ClassDef) and n.name.lstrip("_") == "SemValidadores"
    ]
    assert len(donos) == 1, donos
    importados = {
        a.name
        for n in ast.walk(_arvore(PAINEL / "cliente.py"))  # só o cliente do painel o usa (T185)
        if isinstance(n, ast.ImportFrom)
        for a in n.names
    }
    assert "SemValidadores" in importados


# o que cada auxiliar era (cópia privada nas rotas) e o nome que ele tem no módulo único
AUXILIARES = {
    "ambiente": ("_ambiente", "ambiente_do_painel"),
    "rodar": ("_rodar", "rodar_do_painel"),
    "um": ("_um", "campo_unico"),
}
IMPORTAM = {
    "configuracoes": ("ambiente_do_painel", "rodar_do_painel"),
    "primeira_execucao": ("ambiente_do_painel", "rodar_do_painel"),
    "buscas": ("campo_unico",),
    "detalhe": ("campo_unico",),
}


def test_funcoes_das_rotas_definidas_uma_vez() -> None:
    """Cada auxiliar tem um dono só no painel, com o nome velho ou o novo; as rotas importam."""
    definidos: dict[str, list[str]] = {chave: [] for chave in AUXILIARES}
    for caminho in PAINEL.rglob("*.py"):
        for funcao in _funcoes(_arvore(caminho), so_do_modulo=True):
            for chave, nomes in AUXILIARES.items():
                if funcao in nomes:
                    definidos[chave].append(f"{caminho.relative_to(PAINEL)}:{funcao}")
    for lista in definidos.values():
        assert len(lista) == 1, lista
    for rota, esperados in IMPORTAM.items():
        importados = {
            a.name
            for n in ast.walk(_arvore(PAINEL / "rotas" / f"{rota}.py"))
            if isinstance(n, ast.ImportFrom)
            for a in n.names
        }
        assert set(esperados) <= importados, rota


def _cria_cliente(arvore: ast.AST) -> bool:
    """Chamada `ClienteEducado(...)`, qualquer que seja o jeito de importar o nome."""
    return any(
        isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Name) and n.func.id == "ClienteEducado")
            or (isinstance(n.func, ast.Attribute) and n.func.attr == "ClienteEducado")
        )
        for n in ast.walk(arvore)
    )


def test_prova_do_cliente_pega_a_criacao_e_deixa_passar_o_uso() -> None:
    """Controle do detector: criar o cliente cai, usar `cliente_do_painel` não."""
    assert _cria_cliente(ast.parse("ClienteEducado(None, r, l, v)"))
    assert _cria_cliente(ast.parse("http.ClienteEducado(None, r, l, v)"))
    assert not _cria_cliente(ast.parse("cliente_do_painel(request)"))
    assert not _cria_cliente(ast.parse("def f(c: ClienteEducado) -> None: ..."))


def test_cliente_do_painel_definido_uma_vez() -> None:
    """Só `painel/cliente.py` monta o `ClienteEducado`; as rotas que têm rede o importam."""
    donos = [
        str(caminho.relative_to(PAINEL))
        for caminho in PAINEL.rglob("*.py")
        if _cria_cliente(_arvore(caminho))
    ]
    assert donos == ["cliente.py"], donos
    for nome in ("empresas", "sugeridas", "servicos"):
        importados = {
            (n.module, a.name)
            for n in ast.walk(_arvore(PAINEL / "rotas" / f"{nome}.py"))
            if isinstance(n, ast.ImportFrom)
            for a in n.names
        }
        assert ("jobot.painel.cliente", "cliente_do_painel") in importados, nome
