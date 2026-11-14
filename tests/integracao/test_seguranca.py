"""App do painel e segurança (desenho 14; plano T26)."""

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from jinja2 import DictLoader

from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import app as modulo_app
from jobot.painel import rotas, seguranca
from jobot.painel.app import criar_app
from jobot.painel.i18n import t
from jobot.painel.seguranca import Con, csrf_token, renderizar

PORTA = 47615
BASE = f"http://127.0.0.1:{PORTA}"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def _app(dados: Path) -> FastAPI:
    """App real com duas rotas de teste: um GET que mostra o token e um POST qualquer."""
    app = criar_app(dados, PORTA)

    @app.get("/teste")
    def ler(request: Request) -> dict[str, str]:
        return {"token": csrf_token(request)}

    @app.post("/teste")
    def gravar() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    return TestClient(_app(tmp_path), base_url=BASE)


def _token(cliente: TestClient) -> str:
    token: str = cliente.get("/teste").json()["token"]
    return token


def test_host_errado_400(tmp_path: Path) -> None:
    app = _app(tmp_path)
    for base in (BASE, f"http://localhost:{PORTA}"):
        assert TestClient(app, base_url=base).get("/teste").status_code == 200
    for base in ("http://evil.com", f"http://evil.com:{PORTA}", "http://127.0.0.1:8080"):
        assert TestClient(app, base_url=base).get("/teste").status_code == 400


def test_post_sem_csrf_403(cliente: TestClient) -> None:
    resposta = cliente.post("/teste", data={"x": "1"})
    assert resposta.status_code == 403


def test_csrf_por_campo_e_por_cabecalho(cliente: TestClient) -> None:
    token = _token(cliente)
    por_campo = cliente.post("/teste", data={seguranca.CAMPO_CSRF: token})
    assert por_campo.status_code == 200
    por_cabecalho = cliente.post("/teste", headers={"X-CSRF-Token": token})
    assert por_cabecalho.status_code == 200
    errado = cliente.post("/teste", headers={"X-CSRF-Token": token + "x"})
    assert errado.status_code == 403


def test_sec_fetch_site_cross_site_403(cliente: TestClient) -> None:
    token = _token(cliente)
    cabecalhos = {"X-CSRF-Token": token, "Sec-Fetch-Site": "cross-site"}
    assert cliente.post("/teste", headers=cabecalhos).status_code == 403
    cabecalhos["Sec-Fetch-Site"] = "same-origin"
    assert cliente.post("/teste", headers=cabecalhos).status_code == 200


def test_origin_diferente_403(cliente: TestClient) -> None:
    token = _token(cliente)
    for origem in ("http://evil.com", f"http://localhost:{PORTA}", "null"):
        cabecalhos = {"X-CSRF-Token": token, "Origin": origem}
        assert cliente.post("/teste", headers=cabecalhos).status_code == 403, origem
    cabecalhos = {"X-CSRF-Token": token, "Origin": BASE}
    assert cliente.post("/teste", headers=cabecalhos).status_code == 200


def test_token_velho_pede_recarregar(tmp_path: Path) -> None:
    antes = TestClient(_app(tmp_path), base_url=BASE)
    token_velho = _token(antes)
    depois = TestClient(_app(tmp_path), base_url=BASE)  # servidor reiniciado
    assert _token(depois) != token_velho
    resposta = depois.post("/teste", headers={"X-CSRF-Token": token_velho, "Accept-Language": "en"})
    assert resposta.status_code == 403
    assert resposta.json()["detail"] == t("en", "seguranca.recarregue")


def test_cabecalhos(cliente: TestClient) -> None:
    for resposta in (
        cliente.get("/teste"),
        cliente.post("/teste"),  # 403 também leva os cabeçalhos
        TestClient(cliente.app, base_url="http://evil.com").get("/teste"),  # e o 400
    ):
        cabecalhos = resposta.headers
        assert cabecalhos.get("content-security-policy") == CSP
        assert cabecalhos.get("x-content-type-options") == "nosniff"
        assert cabecalhos.get("referrer-policy") == "no-referrer"
        assert cabecalhos.get("cross-origin-opener-policy") == "same-origin"
        assert cabecalhos.get("permissions-policy") == "camera=(), microphone=(), geolocation=()"
        # só prova algo com o uvicorn real (server_header=False é da T48); o TestClient nunca manda
        assert "server" not in cabecalhos


def test_sem_documentacao_automatica(cliente: TestClient) -> None:
    # a página /docs do FastAPI puxa script de CDN, o que o painel não pode ter (desenho 13.13)
    for caminho in ("/docs", "/redoc", "/openapi.json"):
        assert cliente.get(caminho).status_code == 404


def test_inclui_router_de_cada_modulo_de_rotas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = tmp_path / "rotas_extra"
    pasta.mkdir()
    (pasta / "zz_teste_t26.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/zz')\n"
        "def zz() -> str:\n"
        "    return 'achou'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rotas, "__path__", [*rotas.__path__, str(pasta)])
    monkeypatch.delitem(sys.modules, "jobot.painel.rotas.zz_teste_t26", raising=False)
    resposta = TestClient(criar_app(tmp_path, PORTA), base_url=BASE).get("/zz")
    assert resposta.json() == "achou"


def test_monta_static_se_a_pasta_existir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sem = tmp_path / "nao_existe"
    monkeypatch.setattr(modulo_app, "ESTATICOS", sem)
    sem_static = TestClient(criar_app(tmp_path, PORTA), base_url=BASE)
    assert sem_static.get("/static/a.css").status_code == 404

    com = tmp_path / "static"
    com.mkdir()
    (com / "a.css").write_text("body{}", encoding="utf-8")
    monkeypatch.setattr(modulo_app, "ESTATICOS", com)
    resposta = TestClient(criar_app(tmp_path, PORTA), base_url=BASE).get("/static/a.css")
    assert resposta.status_code == 200
    assert resposta.text == "body{}"
    assert resposta.headers.get("x-content-type-options") == "nosniff"


def test_conexao_por_pedido_e_renderizar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    banco = tmp_path / "jobot.db"
    con = abrir(banco)
    migrar(con, banco)
    con.close()
    monkeypatch.setattr(
        seguranca.TEMPLATES.env,
        "loader",
        DictLoader({"t26.html": "{{ t('seguranca.recarregue') }}|{{ csrf_token }}|{{ texto }}"}),
    )
    abertas: list[sqlite3.Connection] = []
    app = criar_app(tmp_path, PORTA)

    @app.get("/pagina")
    async def pagina(request: Request, con: Con) -> HTMLResponse:
        abertas.append(con)
        return renderizar(request, "t26.html", texto="<script>x</script>")

    cliente = TestClient(app, base_url=BASE)
    corpo = cliente.get("/pagina", headers={"Accept-Language": "en"}).text
    token = csrf_token_de(app)
    assert corpo == f"{t('en', 'seguranca.recarregue')}|{token}|&lt;script&gt;x&lt;/script&gt;"

    gravar = abrir(banco)
    gravar.execute("INSERT INTO config (chave, valor) VALUES ('idioma', '\"pt\"')")
    gravar.commit()
    gravar.close()
    corpo = cliente.get("/pagina", headers={"Accept-Language": "en"}).text
    assert corpo.startswith(t("pt", "seguranca.recarregue") + "|")  # a escolha salva vale mais

    assert len(abertas) == 2 and abertas[0] is not abertas[1]
    with pytest.raises(sqlite3.ProgrammingError):  # fechada no fim do pedido
        abertas[0].execute("SELECT 1")


def test_idioma_salvo_vale_sem_con(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    banco = tmp_path / "jobot.db"
    con = abrir(banco)
    migrar(con, banco)
    con.execute("INSERT INTO config (chave, valor) VALUES ('idioma', '\"pt\"')")
    con.commit()
    con.close()
    monkeypatch.setattr(
        seguranca.TEMPLATES.env,
        "loader",
        DictLoader({"t26.html": "{{ t('seguranca.recarregue') }}"}),
    )
    app = criar_app(tmp_path, PORTA)

    @app.post("/sem-con")
    @app.get("/sem-con")
    def sem_con(request: Request) -> HTMLResponse:  # síncrona e sem Con, de propósito
        return renderizar(request, "t26.html")

    cliente = TestClient(app, base_url=BASE)
    en = {"Accept-Language": "en"}
    assert cliente.get("/sem-con", headers=en).text == t("pt", "seguranca.recarregue")
    recusa = cliente.post("/sem-con", headers=en)  # o 403 do CSRF roda antes de Con
    assert recusa.status_code == 403
    assert recusa.json()["detail"] == t("pt", "seguranca.recarregue")


def csrf_token_de(app: FastAPI) -> str:
    token: str = app.state.csrf
    return token
