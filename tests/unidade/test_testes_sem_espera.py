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


def test_tela_nao_espera_tempo_real() -> None:
    achados: list[str] = []
    for arquivo in sorted((TESTS / "tela").glob("*.py")):
        for c in _chamadas(arquivo):
            onde = f"{arquivo.name}:{c.lineno}"
            nome = _nome(c)
            if nome.endswith(".wait_for_timeout"):
                achados.append(f"{onde} wait_for_timeout")
            if nome in ("time.sleep", "asyncio.sleep") and c.args:
                s = _numero(c.args[0])
                if s is None or s > DORMIDA_MAX_S:
                    achados.append(f"{onde} {nome}")
            for k in c.keywords:
                ms = _numero(k.value)
                if k.arg == "timeout" and ms is not None and ms > EXPECT_PADRAO_MS:
                    achados.append(f"{onde} timeout={ms:g}")
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
