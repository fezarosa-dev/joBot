"""Aviso de versão nova no painel (plano T85; ADR 0014 e 0018; D31).

O aviso nasce ligado (D105): a pessoa o desliga em Privacidade (`aviso_versao_ligada`); desligado,
nada vai ao GitHub e o fragmento sai vazio.
"""

import asyncio
import re
from contextlib import closing
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from jobot import __version__
from jobot.agenda import versao
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.painel.app import criar_app

PORTA = 47621
BASE = f"http://127.0.0.1:{PORTA}"
DIV_AVISO = re.compile(r"<div\b[^>]*\bid=\"aviso-versao\"[^>]*>", re.S)


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


@pytest.fixture
def dados(tmp_path: Path) -> Path:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        migrar(con, tmp_path / "jobot.db")
    return tmp_path


def _cliente(dados: Path) -> TestClient:
    return TestClient(criar_app(dados, PORTA), base_url=BASE)


def _checar(dados: Path, pedidos: list[httpx.Request]) -> None:
    def github(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return httpx.Response(200, json={"tag_name": "v99.0.0"})

    async def rodar() -> None:
        relogio = RelogioFalso()
        cliente = ClienteEducado(
            httpx.MockTransport(github), relogio, _SemValidadores(), __version__
        )
        try:
            with closing(abrir(dados / "jobot.db")) as con:
                await versao.checar_versao_nova(con, cliente, relogio)
        finally:
            await cliente.fechar()

    asyncio.run(rodar())


def test_aviso_nasce_ligado_e_desligado_nao_checa_nem_mostra(dados: Path) -> None:
    pedidos: list[httpx.Request] = []
    _checar(dados, pedidos)
    assert len(pedidos) == 1  # banco novo: checa sem a pessoa ter ligado nada
    assert "99.0.0" in _cliente(dados).get("/aviso-versao").text
    with closing(abrir(dados / "jobot.db")) as con:
        gravar_config(con, "aviso_versao_ligada", False)
    _checar(dados, pedidos)
    assert len(pedidos) == 1  # desligado, não checa de novo
    resposta = _cliente(dados).get("/aviso-versao")
    assert resposta.status_code == 200
    assert resposta.text.strip() == ""


def test_aviso_aparece_no_painel_com_role_status(dados: Path) -> None:
    with closing(abrir(dados / "jobot.db")) as con:
        gravar_config(con, "aviso_versao_ligada", True)
        gravar_config(con, "versao_nova", "v99.0.0")
        gravar_config(con, "idioma", "pt")
    cliente = _cliente(dados)
    pagina = cliente.get("/configuracoes/privacidade")
    assert pagina.status_code == 200
    div = DIV_AVISO.search(pagina.text)
    assert div is not None, "a casca não tem a div do aviso"
    assert 'role="status"' in div.group(0)
    assert 'hx-get="/aviso-versao"' in div.group(0)
    assert 'hx-trigger="load"' in div.group(0)
    fragmento = cliente.get("/aviso-versao")
    assert fragmento.status_code == 200
    assert "<html" not in fragmento.text  # fragmento HTMX, sem a casca
    assert "v99.0.0" in fragmento.text
    assert "Atualizar agora" in fragmento.text  # T332: o botão, não o terminal (ADR 0023)
    assert "terminal" not in fragmento.text


def test_aviso_em_ingles(dados: Path) -> None:
    with closing(abrir(dados / "jobot.db")) as con:
        gravar_config(con, "aviso_versao_ligada", True)
        gravar_config(con, "versao_nova", "v99.0.0")
        gravar_config(con, "idioma", "en")
    texto = _cliente(dados).get("/aviso-versao").text
    assert "v99.0.0" in texto
    assert "available" in texto


def test_etiqueta_gravada_fora_do_padrao_nao_vai_para_a_tela(dados: Path) -> None:
    with closing(abrir(dados / "jobot.db")) as con:
        gravar_config(con, "aviso_versao_ligada", True)
        gravar_config(con, "versao_nova", "<script>9.9.9</script>")
    assert _cliente(dados).get("/aviso-versao").text.strip() == ""
