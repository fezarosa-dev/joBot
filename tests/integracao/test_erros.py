"""Erros do servidor viram página amigável ou fragmento HTMX (D106; T150)."""

import logging
import re
from contextlib import closing
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from markupsafe import escape

from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import seguranca
from jobot.painel.app import CABECALHOS, criar_app
from jobot.painel.i18n import t

PORTA = 47615
BASE = f"http://127.0.0.1:{PORTA}"
HTMX = {"HX-Request": "true"}
SEGREDO = "segredo-da-excecao-xyz"
CHAVES = ("nao_existe", "desatualizada", "invalido", "outro", "indisponivel", "interno")


def _app(dados: Path, banco_ok: bool = True) -> FastAPI:
    banco = dados / "jobot.db"
    if banco_ok:
        with closing(abrir(banco)) as con:
            migrar(con, banco)
    else:
        banco.write_bytes(b"isto nao e um banco sqlite" * 100)
    app = criar_app(dados, PORTA)

    @app.get("/teste-quebra")
    def quebra() -> None:
        raise RuntimeError(SEGREDO)

    @app.get("/teste-quebra/{resto}")
    def quebra_com_caminho(resto: str) -> None:
        raise RuntimeError(SEGREDO)

    return app


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    return TestClient(_app(tmp_path), base_url=BASE, raise_server_exceptions=False)


def _texto(idioma: str, chave: str, **params: object) -> str:
    return str(escape(t(idioma, chave, **params)))


def _confere_cabecalhos(resposta: httpx.Response) -> None:
    for nome, valor in CABECALHOS.items():
        assert resposta.headers[nome] == valor, nome


def _log(dados: Path) -> Path:
    return dados / "logs" / "jobot.log"


def test_chaves_de_erro_em_pt_e_en() -> None:
    for idioma in ("pt", "en"):
        assert t(idioma, "erro.inicio") != "erro.inicio"
        for chave in CHAVES:
            # o 403 usa o `seguranca.recarregue` como texto
            for parte in ("titulo",) if chave == "desatualizada" else ("titulo", "texto"):
                k = f"erro.{chave}.{parte}"
                assert t(idioma, k, log="x") != k, (idioma, k)
        assert "/tmp/x.log" in t(idioma, "erro.interno.texto", log="/tmp/x.log")


def test_404_vira_pagina_html_com_cabecalhos(cliente: TestClient) -> None:
    resposta = cliente.get("/nao-existe-mesmo")
    assert resposta.status_code == 404
    assert resposta.headers["content-type"].startswith("text/html")
    assert _texto("pt", "erro.nao_existe.titulo") in resposta.text
    assert _texto("pt", "erro.nao_existe.texto") in resposta.text
    assert 'href="/"' in resposta.text
    assert "detail" not in resposta.text
    _confere_cabecalhos(resposta)


def test_404_de_rota_com_detail_do_codigo_nao_mostra_o_detail(cliente: TestClient) -> None:
    resposta = cliente.get("/vagas/999999")
    assert resposta.status_code == 404
    assert _texto("pt", "erro.nao_existe.texto") in resposta.text
    assert 'não existe"' not in resposta.text and "detail" not in resposta.text


def test_404_htmx_devolve_fragmento(cliente: TestClient) -> None:
    resposta = cliente.get("/nao-existe-mesmo", headers=HTMX)
    assert resposta.status_code == 404
    assert resposta.text == f"<p data-aviso-erro>{_texto('pt', 'erro.nao_existe.texto')}</p>"
    _confere_cabecalhos(resposta)


def test_405_vira_generico_e_mantem_allow(cliente: TestClient) -> None:
    resposta = cliente.put("/saude-local")
    assert resposta.status_code == 405
    assert "allow" in resposta.headers
    assert _texto("pt", "erro.outro.texto") in resposta.text


def test_422_de_validacao_vira_html_sem_json(tmp_path: Path) -> None:
    app = _app(tmp_path)
    cliente = TestClient(app, base_url=BASE)
    # POST com o token certo e sem o campo obrigatório `tema`
    resposta = cliente.post("/preferencias/tema", data={seguranca.CAMPO_CSRF: app.state.csrf})
    assert resposta.status_code == 422
    assert resposta.headers["content-type"].startswith("text/html")
    assert _texto("pt", "erro.invalido.texto") in resposta.text
    assert "detail" not in resposta.text and "missing" not in resposta.text
    _confere_cabecalhos(resposta)


def test_422_htmx_devolve_fragmento(cliente: TestClient) -> None:
    resposta = cliente.get("/vagas/abc", headers=HTMX)
    assert resposta.status_code == 422
    assert resposta.text == f"<p data-aviso-erro>{_texto('pt', 'erro.invalido.texto')}</p>"


def test_403_do_csrf_vira_html_com_recarregue(cliente: TestClient) -> None:
    resposta = cliente.post("/preferencias/tema", data={"tema": "claro"})
    assert resposta.status_code == 403
    assert resposta.headers["content-type"].startswith("text/html")
    assert _texto("pt", "seguranca.recarregue") in resposta.text
    assert _texto("pt", "erro.desatualizada.titulo") in resposta.text
    _confere_cabecalhos(resposta)


def test_403_htmx_em_ingles(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/preferencias/tema", data={"tema": "claro"}, headers={**HTMX, "Accept-Language": "en"}
    )
    assert resposta.status_code == 403
    assert resposta.text == f"<p data-aviso-erro>{_texto('en', 'seguranca.recarregue')}</p>"


def test_500_vira_pagina_sem_traceback_e_anota_no_log(
    tmp_path: Path, cliente: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="jobot"):
        resposta = cliente.get("/teste-quebra?q=secreto")
    assert resposta.status_code == 500
    assert resposta.headers["content-type"].startswith("text/html")
    assert _texto("pt", "erro.interno.titulo") in resposta.text
    assert _texto("pt", "erro.interno.texto", log=_log(tmp_path)) in resposta.text
    assert "Traceback" not in resposta.text and SEGREDO not in resposta.text
    assert "RuntimeError" not in resposta.text
    _confere_cabecalhos(resposta)
    registros = [r for r in caplog.records if r.exc_info]
    assert len(registros) == 1
    assert "GET '/teste-quebra'" in registros[0].getMessage()
    assert "secreto" not in registros[0].getMessage()
    excecao = registros[0].exc_info[1]  # type: ignore[index]
    assert isinstance(excecao, RuntimeError) and str(excecao) == SEGREDO


def test_500_nao_deixa_quebra_de_linha_do_caminho_no_log(
    cliente: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="jobot"):
        resposta = cliente.get("/teste-quebra/a%0A%1B[31mforjado")
    assert resposta.status_code == 500
    mensagens = [r.getMessage() for r in caplog.records if r.exc_info]
    assert len(mensagens) == 1
    assert mensagens[0].isprintable()  # sem \n nem ESC: o caminho chega decodificado
    assert "forjado" in mensagens[0]


def test_casca_quebrada_nao_deixa_quebra_de_linha_do_caminho_no_log(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def quebra(*_: object) -> str:
        raise RuntimeError(SEGREDO)

    monkeypatch.setitem(seguranca.TEMPLATES.env.globals, "url_de_volta", quebra)
    with caplog.at_level(logging.ERROR, logger="jobot"):
        resposta = cliente.get("/teste-quebra/a%0A%1B[31mforjado")
    assert resposta.status_code == 500
    mensagens = [r.getMessage() for r in caplog.records if "casca" in r.getMessage()]
    assert len(mensagens) == 1
    assert mensagens[0].isprintable()  # sem \n nem ESC: o caminho chega decodificado
    assert "forjado" in mensagens[0]


def test_500_htmx_devolve_fragmento(tmp_path: Path, cliente: TestClient) -> None:
    resposta = cliente.get("/teste-quebra", headers=HTMX)
    assert resposta.status_code == 500
    esperado = _texto("pt", "erro.interno.texto", log=_log(tmp_path))
    assert resposta.text == f"<p data-aviso-erro>{esperado}</p>"
    _confere_cabecalhos(resposta)


def test_pagina_de_erro_sai_com_banco_ilegivel(tmp_path: Path) -> None:
    app = _app(tmp_path, banco_ok=False)
    cliente = TestClient(app, base_url=BASE, raise_server_exceptions=False)
    en = {"Accept-Language": "en"}
    nao_existe = cliente.get("/nao-existe-mesmo", headers=en)
    assert nao_existe.status_code == 404
    assert _texto("en", "erro.nao_existe.texto") in nao_existe.text
    quebra = cliente.get("/fontes", headers=en)  # a rota abre o banco e ele falha
    assert quebra.status_code == 500
    assert _texto("en", "erro.interno.texto", log=_log(tmp_path)) in quebra.text
    assert "database" not in quebra.text
    _confere_cabecalhos(quebra)


def _data_texto(html: str) -> str | None:
    achou = re.search(r"<html[^>]*\bdata-texto=\"([^\"]*)\"", html)
    return achou.group(1) if achou else None


def test_erro_leva_o_tamanho_do_texto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(tmp_path)
    cliente = TestClient(app, base_url=BASE, raise_server_exceptions=False)
    assert _data_texto(cliente.get("/nao-existe-mesmo").text) == "padrao"  # sem chave
    with closing(abrir(tmp_path / "jobot.db")) as con:
        con.execute("INSERT INTO config (chave, valor) VALUES ('tamanho_texto', '\"grande\"')")
        con.commit()
    assert _data_texto(cliente.get("/nao-existe-mesmo").text) == "grande"

    # a página mínima (a casca falha) leva o mesmo tamanho
    def quebra(*_: object) -> str:
        raise RuntimeError(SEGREDO)

    monkeypatch.setitem(seguranca.TEMPLATES.env.globals, "url_de_volta", quebra)
    assert _data_texto(cliente.get("/nao-existe-mesmo").text) == "grande"


def test_erro_com_banco_quebrado_traz_o_texto_padrao(tmp_path: Path) -> None:
    cliente = TestClient(_app(tmp_path, banco_ok=False), base_url=BASE)
    resposta = cliente.get("/nao-existe-mesmo")
    assert resposta.status_code == 404
    assert _data_texto(resposta.text) == "padrao"


def test_tamanho_do_texto_estragado_traz_o_padrao(tmp_path: Path) -> None:
    """Guarda (T250): idioma e tema válidos, `tamanho_texto` que não é JSON; a página sai com
    `padrao` (mutante: ler `tamanho_texto` fora do `try` de `erros._aparencia`)."""
    cliente = TestClient(_app(tmp_path), base_url=BASE, raise_server_exceptions=False)
    with closing(abrir(tmp_path / "jobot.db")) as con:
        con.executemany(
            "INSERT INTO config (chave, valor) VALUES (?, ?)",
            [("idioma", '"en"'), ("tema", '"escuro"'), ("tamanho_texto", "nao-json")],
        )
        con.commit()
    resposta = cliente.get("/nao-existe-mesmo")
    assert resposta.status_code == 404
    assert _data_texto(resposta.text) == "padrao"


def test_pagina_de_erro_traz_a_lateral(cliente: TestClient) -> None:
    resposta = cliente.get("/nao-existe-mesmo", headers={"Accept-Language": "en"})
    assert resposta.status_code == 404
    assert re.search(r'<aside\b[^>]*class="lateral vidro"', resposta.text)
    assert 'aria-label="Main"' in resposta.text
    assert _texto("en", "erro.nao_existe.titulo") in resposta.text


def test_casca_que_falha_usa_a_pagina_minima(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def quebra(*_: object) -> str:
        raise RuntimeError(SEGREDO)

    monkeypatch.setitem(seguranca.TEMPLATES.env.globals, "url_de_volta", quebra)
    resposta = cliente.get("/nao-existe-mesmo", headers={"Accept-Language": "en"})
    assert resposta.status_code == 404
    assert _texto("en", "erro.nao_existe.texto") in resposta.text
    assert 'href="/static/css/base.css"' in resposta.text and 'href="/"' in resposta.text
    assert SEGREDO not in resposta.text


@pytest.mark.parametrize(("idioma", "cabecalho"), [("pt", "pt-BR"), ("en", "en-US,en;q=0.9")])
def test_texto_segue_o_idioma(cliente: TestClient, idioma: str, cabecalho: str) -> None:
    resposta = cliente.get("/nao-existe-mesmo", headers={"Accept-Language": cabecalho})
    assert f'lang="{idioma}"' in resposta.text
    assert _texto(idioma, "erro.nao_existe.titulo") in resposta.text


def test_saude_local_continua_json(cliente: TestClient) -> None:
    resposta = cliente.get("/saude-local")
    assert resposta.status_code == 200
    assert resposta.json()["app"] == "jobot"
