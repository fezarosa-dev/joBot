"""Varredura do texto dos testes de tela e de navegador (T292, T295): nada de esperar tempo real
nem de subir o Playwright a cada teste."""

import ast
import socketserver
from pathlib import Path

import pytest

from apoio.site_falso import SiteFalso

TESTS = Path(__file__).resolve().parents[1]
DORMIDA_MAX_S = 0.1  # laço de condição curto (o `painel` olha `started` de 0,05 em 0,05 s)
EXPECT_PADRAO_MS = 5000  # passar disso é esperar um timer da página: use `page.clock`


def _chamadas(arquivo: Path) -> list[ast.Call]:
    return [n for n in ast.walk(ast.parse(arquivo.read_text())) if isinstance(n, ast.Call)]


def _nome(chamada: ast.Call) -> str:
    f = chamada.func
    if isinstance(f, ast.Attribute):
        return f"{f.value.id}.{f.attr}" if isinstance(f.value, ast.Name) else f".{f.attr}"
    return f.id if isinstance(f, ast.Name) else ""


def _numero(no: ast.expr) -> float | None:
    return no.value if isinstance(no, ast.Constant) and isinstance(no.value, int | float) else None


def _sonos(arquivo: Path) -> set[str]:
    """Nomes de `sleep`: os pontuados e o que `from time|asyncio|anyio import sleep [as x]` traz."""
    importados = {
        a.asname or a.name
        for n in ast.walk(ast.parse(arquivo.read_text()))
        if isinstance(n, ast.ImportFrom) and n.module in ("time", "asyncio", "anyio")
        for a in n.names
        if a.name == "sleep"
    }
    return {"time.sleep", "asyncio.sleep", "anyio.sleep"} | importados


def _achados_de_espera(arquivos: list[Path]) -> list[str]:
    achados: list[str] = []
    for arquivo in arquivos:
        sonos = _sonos(arquivo)
        for c in _chamadas(arquivo):
            onde = f"{arquivo.name}:{c.lineno}"
            nome = _nome(c)
            if nome.endswith(".wait_for_timeout"):
                achados.append(f"{onde} wait_for_timeout")
            if nome in sonos and c.args:
                s = _numero(c.args[0])
                if s is None or s > DORMIDA_MAX_S:
                    achados.append(f"{onde} {nome}")
            for k in c.keywords:
                ms = _numero(k.value)
                if k.arg == "timeout" and ms is not None and ms > EXPECT_PADRAO_MS:
                    achados.append(f"{onde} timeout={ms:g}")
    return achados


def test_tela_nao_espera_tempo_real() -> None:
    assert _achados_de_espera(sorted((TESTS / "tela").glob("*.py"))) == []


def test_tela_nao_espera_a_pergunta_do_progresso() -> None:
    # a pergunta de 2 s do painel se adianta com `page.clock.fast_forward`; `timeout=` numérico em
    # chamada do arquivo é esperar tempo real (o padrão do `expect` já cobre o resto)
    achados = [
        f"test_progresso.py:{c.lineno} timeout={_numero(k.value):g}"
        for c in _chamadas(TESTS / "tela" / "test_progresso.py")
        for k in c.keywords
        if k.arg == "timeout" and _numero(k.value) is not None
    ]
    assert achados == []


def test_site_falso_desce_sem_esperar_a_volta_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    # o `shutdown` espera uma volta do `serve_forever`: 0,5 s no padrão, por servidor e por teste
    voltas: list[float] = []
    original = socketserver.BaseServer.serve_forever

    def serve_forever(self: socketserver.BaseServer, poll_interval: float = 0.5) -> None:
        voltas.append(poll_interval)
        original(self, poll_interval)

    monkeypatch.setattr(socketserver.BaseServer, "serve_forever", serve_forever)
    with SiteFalso():
        pass
    assert len(voltas) == 2 and max(voltas) <= DORMIDA_MAX_S


def test_navegador_sobe_o_playwright_uma_vez_por_sessao() -> None:
    # o teste de `capturar_logado_site` é síncrono: o script roda o próprio laço e o seu Playwright
    permitidos = {"navegador/conftest.py", "navegador/test_capturar_logado_site.py"}
    arquivos = [*(TESTS / "navegador").glob("*.py"), TESTS / "apoio" / "site_falso.py"]
    achados = sorted(
        f"{a.relative_to(TESTS)}:{c.lineno}"
        for a in arquivos
        if str(a.relative_to(TESTS)) not in permitidos
        for c in _chamadas(a)
        if _nome(c) == "async_playwright"
    )
    assert achados == []


def _arquivo_de_exemplo(tmp_path: Path, texto: str) -> Path:
    arquivo = tmp_path / "test_exemplo.py"
    arquivo.write_text(texto)
    return arquivo


@pytest.mark.parametrize("modulo", ["time", "asyncio", "anyio"])
def test_guarda_pega_sleep_importado(tmp_path: Path, modulo: str) -> None:
    arquivo = _arquivo_de_exemplo(tmp_path, f"from {modulo} import sleep\n\nsleep(5)\n")
    assert _achados_de_espera([arquivo]) == ["test_exemplo.py:3 sleep"]


@pytest.mark.parametrize("modulo", ["time", "asyncio", "anyio"])
def test_guarda_pega_sleep_com_apelido(tmp_path: Path, modulo: str) -> None:
    arquivo = _arquivo_de_exemplo(tmp_path, f"from {modulo} import sleep as dormir\n\ndormir(5)\n")
    assert _achados_de_espera([arquivo]) == ["test_exemplo.py:3 dormir"]


def test_guarda_pega_anyio_sleep_pontuado(tmp_path: Path) -> None:
    arquivo = _arquivo_de_exemplo(tmp_path, "import anyio\n\nanyio.sleep(5)\n")
    assert _achados_de_espera([arquivo]) == ["test_exemplo.py:3 anyio.sleep"]


def test_guarda_deixa_passar_sleep_curto_e_sleep_de_outro_modulo(tmp_path: Path) -> None:
    arquivo = _arquivo_de_exemplo(
        tmp_path,
        "from time import sleep\nfrom outro import sleep as dormir\n\nsleep(0.05)\ndormir(5)\n",
    )
    assert _achados_de_espera([arquivo]) == []


def _fixtures_de(arquivo: Path) -> set[str]:
    def _e_fixture(d: ast.expr) -> bool:
        d = d.func if isinstance(d, ast.Call) else d
        return isinstance(d, ast.Attribute) and d.attr == "fixture"

    return {
        n.name
        for n in ast.walk(ast.parse(arquivo.read_text()))
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        and any(_e_fixture(d) for d in n.decorator_list)
    }


def test_sem_fixture_sombra() -> None:
    # fixture com o nome de uma do conftest raiz sombreia a outra: quem lê não sabe qual vale
    do_conftest = _fixtures_de(TESTS / "conftest.py")
    achados = sorted(
        f"{a.name}: {nome}"
        for a in (TESTS / "unidade" / "coletores").glob("*.py")
        for nome in _fixtures_de(a) & do_conftest
    )
    assert achados == []
