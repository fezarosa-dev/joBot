"""Região do aviso de erro na casca (T151; D106): textos genéricos do servidor, em pt e en."""

import re
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import i18n
from jobot.painel.app import criar_app

PORTA = 47631
CHAVES = ("4xx", "5xx", "rede", "fechar")
REGIAO = re.compile(r"<div\b([^>]*\bid=\"aviso-erro\"[^>]*)>(.*?)</div>", re.S)
DATA = re.compile(r'\b(data-msg-[\w-]+)="([^"]*)"')
TEXTOS = {
    "pt": {
        "4xx": "Não deu para fazer isso. Recarregue a página e tente de novo.",
        "5xx": "Algo deu errado no joBot. Tente de novo; se repetir, veja o arquivo de log"
        " do joBot.",
        "rede": "O joBot não respondeu. Ele pode ter sido fechado: ligue de novo pelo botão Ligar"
        " da janela do joBot (o atalho do menu), ou com jobot abrir.",
        "fechar": "Fechar aviso",
    },
}


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
    return TestClient(criar_app(tmp_path, PORTA), base_url=f"http://127.0.0.1:{PORTA}")


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_casca_tem_a_regiao_do_aviso_de_erro_com_os_textos(
    cliente: TestClient, idioma: str
) -> None:
    html = cliente.get("/vagas", headers={"Accept-Language": idioma}).text
    achados = REGIAO.findall(html)
    assert len(achados) == 1, "a casca precisa de uma região #aviso-erro"
    atributos, interno = achados[0]
    assert re.search(r"""\brole=['"]alert['"]""", atributos)
    # aspas simples: o `role="alert"` das mensagens de cada página não pode vir da casca
    assert 'role="alert"' not in html
    assert re.search(r"\bhidden\b", atributos)
    dados = dict(DATA.findall(atributos))
    esperado = {f"data-msg-{c}": i18n.t(idioma, f"casca.erro.{c}") for c in ("4xx", "5xx", "rede")}
    assert dados == esperado
    botao = re.search(r"<button\b([^>]*)>", interno)
    assert botao is not None, "a região precisa do botão de fechar"
    assert f'aria-label="{i18n.t(idioma, "casca.erro.fechar")}"' in botao.group(1)


@pytest.mark.parametrize("caminho", ["/vagas", "/fontes", "/nao-existe-mesmo"])
def test_aviso_de_erro_logo_depois_da_barra_e_fora_do_rodape(
    cliente: TestClient, caminho: str
) -> None:
    html = cliente.get(caminho).text
    fim_da_barra = html.index("</header>")
    regiao = html.index('<div id="aviso-erro"')
    assert html[fim_da_barra + len("</header>") : regiao].strip() == ""
    rodape = re.search(r"<footer\b.*?</footer>", html, re.S)
    assert rodape is None or 'id="aviso-erro"' not in rodape.group(0)
    assert re.search(r"<div id=\"aviso-erro\" role='alert'", html)


def test_textos_em_portugues_sao_os_do_brief(cliente: TestClient) -> None:
    for chave, texto in TEXTOS["pt"].items():
        assert i18n.t("pt", f"casca.erro.{chave}") == texto


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize("chave", CHAVES)
def test_chave_do_aviso_existe_nos_dois_idiomas(idioma: str, chave: str) -> None:
    assert i18n.carregar()[idioma].get(f"casca.erro.{chave}", "").strip()


def test_textos_em_ingles_diferem_dos_em_portugues() -> None:
    for chave in CHAVES:
        assert i18n.t("pt", f"casca.erro.{chave}") != i18n.t("en", f"casca.erro.{chave}")
