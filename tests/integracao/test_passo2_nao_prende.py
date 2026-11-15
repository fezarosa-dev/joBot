"""D49 (b) e D106: o passo 2 nunca prende a pessoa, e nenhum erro mostra o texto da exceção.

'Não ligar' conclui mesmo se o sistema recusar; 'Ligar' com falha fica no passo 2 com texto fixo.
A mesma regra vale em Configurações > Segundo plano. O sistema é falso (`FalsoSistema`).
"""

import html
import json
import logging
import subprocess
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.segundo_plano_falso import FalsoSistema
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.modelo import Motivo
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema import segundo_plano_linux
from jobot.sistema.segundo_plano_linux import Recusa, Resultado

PORTA = 47621
PASSO_2 = "/primeira-execucao/2"
CONFIG_SP = "/configuracoes/segundo-plano"
SEGREDO = "SEGREDO-da-excecao-/etc/jobot"


class Painel:
    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
        casa = tmp_path / "casa"
        casa.mkdir()
        self.sistema = FalsoSistema(home=str(casa))
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso()
        self.app.state.rodar_comando = self.sistema
        self.app.state.ambiente = {"HOME": str(casa)}
        self.app.state.plataforma = "linux"
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )

    def get(self, url: str, **kw: Any) -> Any:
        return self.http.get(url, **kw)

    def post(self, url: str, dados: dict[str, Any], **kw: Any) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.app.state.csrf, **dados}, **kw)

    def config(self, chave: str) -> object:
        with closing(abrir(self.banco)) as con:
            linha = con.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
        return None if linha is None else json.loads(linha[0])


@pytest.fixture(autouse=True)
def _sem_comando_de_verdade(monkeypatch: pytest.MonkeyPatch) -> None:
    def armadilha(*args: object, **kw: object) -> None:
        raise AssertionError(f"comando de verdade num teste: {args!r}")

    monkeypatch.setattr(subprocess, "run", armadilha)


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _quebra(erro: Exception) -> Any:
    def quebrar(*args: object, **kw: object) -> None:
        raise erro

    return quebrar


def _concluiu_com_aviso(painel: Painel, resposta: Any, codigo: str) -> str:
    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"{PASSO_2}?feito=1&aviso={codigo}"
    assert painel.config("primeira_execucao_concluida") is True
    assert painel.config("segundo_plano") is False
    return str(html.unescape(painel.get(resposta.headers["location"]).text))


@pytest.mark.parametrize("onde", ["desligar", "criar_atalho"])
@pytest.mark.parametrize("erro", [OSError(SEGREDO), ValueError(SEGREDO)])
def test_nao_ligar_com_falha_conclui_e_avisa(
    painel: Painel,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    onde: str,
    erro: Exception,
) -> None:
    monkeypatch.setattr(segundo_plano_linux, onde, _quebra(erro))
    with caplog.at_level(logging.WARNING):
        resposta = painel.post(PASSO_2, {"segundo_plano": "desligar"})
    pagina = _concluiu_com_aviso(painel, resposta, "desligar")
    assert "O segundo plano não pôde ser desligado direito" in pagina
    assert "Tente de novo em Configurações > Segundo plano." in pagina
    assert "Tudo pronto" in pagina
    assert SEGREDO not in pagina
    assert SEGREDO in caplog.text  # o detalhe vai para o log, não para a tela


def test_nao_ligar_com_recusa_do_systemctl_conclui_e_avisa(
    painel: Painel, caplog: pytest.LogCaptureFixture
) -> None:
    painel.post(PASSO_2, {"segundo_plano": "ligar"})
    painel.sistema.falha_em["disable"] = Resultado(1, "", SEGREDO)
    with caplog.at_level(logging.WARNING):
        resposta = painel.post(PASSO_2, {"segundo_plano": "desligar"})
    pagina = _concluiu_com_aviso(painel, resposta, "systemctl_falhou")
    assert "O segundo plano não pôde ser desligado direito" in pagina
    assert SEGREDO not in pagina  # a saída do systemctl fica no log
    assert SEGREDO not in resposta.headers["location"]
    assert sum(SEGREDO in r.getMessage() for r in caplog.records) == 1  # uma vez, na origem


MOTIVOS_FIXOS = {
    "sem_host_exec": (
        "não consegui falar com o sistema de fora",
        "could not reach the host system",
    ),
    "systemd_nao_responde": (
        "o systemd do usuário não responde",
        "the user systemd is not responding",
    ),
    "home_diferente": (
        "a pasta pessoal do container não é a do sistema",
        "the container home folder is not the host home folder",
    ),
}


@pytest.mark.parametrize("codigo", sorted(MOTIVOS_FIXOS))
def test_nao_ligar_com_recusa_diz_o_motivo_nos_dois_idiomas(
    painel: Painel, monkeypatch: pytest.MonkeyPatch, codigo: str
) -> None:
    recusa = Recusa(Motivo(chave=f"segundo_plano.{codigo}"))
    monkeypatch.setattr(segundo_plano_linux, "desligar", _quebra(recusa))
    resposta = painel.post(PASSO_2, {"segundo_plano": "desligar"})
    pagina = _concluiu_com_aviso(painel, resposta, codigo)
    pt, en = MOTIVOS_FIXOS[codigo]
    assert f"O segundo plano não pôde ser desligado direito: {pt}" in pagina
    assert f"segundo_plano.{codigo}" not in pagina  # nunca a chave crua
    ingles = html.unescape(
        painel.get(resposta.headers["location"], headers={"Accept-Language": "en"}).text
    )
    assert f"could not be turned off properly: {en}" in ingles
    assert "Try again in Settings > Background." in ingles


def test_recusa_de_chave_desconhecida_vira_o_aviso_generico(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    recusa = Recusa(Motivo(chave="segundo_plano.outra", params={"x": SEGREDO}))
    monkeypatch.setattr(segundo_plano_linux, "desligar", _quebra(recusa))
    resposta = painel.post(PASSO_2, {"segundo_plano": "desligar"})
    pagina = _concluiu_com_aviso(painel, resposta, "desligar")
    assert "O segundo plano não pôde ser desligado direito" in pagina
    assert SEGREDO not in pagina


def test_nao_ligar_sem_falha_nao_tem_aviso(painel: Painel) -> None:
    resposta = painel.post(PASSO_2, {"segundo_plano": "desligar"})
    assert resposta.headers["location"] == f"{PASSO_2}?feito=1"
    assert "não pôde ser desligado" not in painel.get(resposta.headers["location"]).text


@pytest.mark.parametrize(
    "codigo", ["x", "sem_host_exec%27%3E%3Cscript%3E", "segundo_plano.home_diferente", ""]
)
def test_aviso_desconhecido_na_url_e_ignorado(painel: Painel, codigo: str) -> None:
    painel.post(PASSO_2, {"segundo_plano": "desligar"})
    resposta = painel.get(f"{PASSO_2}?feito=1&aviso={codigo}")
    assert resposta.status_code == 200
    assert "Tudo pronto" in resposta.text
    assert "não pôde ser desligado" not in resposta.text
    assert "<script" not in resposta.text.split('id="conteudo"')[1]


def test_aviso_sem_concluir_nao_aparece(painel: Painel) -> None:
    resposta = painel.get(f"{PASSO_2}?feito=1&aviso=desligar")
    assert "Tudo pronto" not in resposta.text
    assert "não pôde ser desligado" not in resposta.text


@pytest.mark.parametrize("erro", [OSError(SEGREDO), ValueError(SEGREDO)])
def test_ligar_com_falha_fica_no_passo_2_sem_o_texto_da_excecao(
    painel: Painel,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    erro: Exception,
) -> None:
    monkeypatch.setattr(segundo_plano_linux, "ligar", _quebra(erro))
    with caplog.at_level(logging.WARNING):
        resposta = painel.post(PASSO_2, {"segundo_plano": "ligar"})
    assert resposta.status_code == 200
    assert 'role="alert"' in resposta.text
    assert "Não consegui gravar os arquivos do serviço" in resposta.text
    assert "detalhes no log" in resposta.text
    assert SEGREDO not in resposta.text
    assert SEGREDO in caplog.text
    assert 'name="segundo_plano"' in resposta.text
    assert painel.config("primeira_execucao_concluida") is None
    assert painel.config("segundo_plano") is None
    en = painel.post(PASSO_2, {"segundo_plano": "ligar"}, headers={"Accept-Language": "en"}).text
    assert "I could not write the service files" in en
    assert SEGREDO not in en
    # e "Não ligar" conclui, mesmo com o ligar quebrado
    monkeypatch.undo()
    assert painel.post(PASSO_2, {"segundo_plano": "desligar"}).status_code == 303


def test_configuracoes_com_falha_nao_mostra_o_texto_da_excecao(
    painel: Painel, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(segundo_plano_linux, "ligar", _quebra(OSError(SEGREDO)))
    with caplog.at_level(logging.WARNING):
        resposta = painel.post(CONFIG_SP, {"segundo_plano": "on"})
    assert resposta.status_code == 200
    assert "Não consegui gravar os arquivos do serviço" in resposta.text
    assert "detalhes no log" in resposta.text
    assert SEGREDO not in resposta.text
    assert SEGREDO in caplog.text
    assert painel.config("segundo_plano") is None
    monkeypatch.setattr(segundo_plano_linux, "desligar", _quebra(ValueError(SEGREDO)))
    resposta = painel.post(CONFIG_SP, {})
    assert resposta.status_code == 200
    assert SEGREDO not in resposta.text
    assert "Não consegui gravar os arquivos do serviço" in resposta.text
    en = painel.post(CONFIG_SP, {}, headers={"Accept-Language": "en"}).text
    assert "I could not write the service files" in en


def test_chaves_novas_existem_em_pt_e_en() -> None:
    catalogo = i18n.carregar()
    novas = [
        "primeira_execucao.p2.erro_arquivos",
        "primeira_execucao.p2.aviso",
        "primeira_execucao.p2.aviso.arquivos",
        "primeira_execucao.p2.aviso.systemctl_falhou",
        "configuracoes.erro.segundo_plano_arquivos",
    ]
    for idioma in ("pt", "en"):
        for chave in novas:
            assert catalogo[idioma][chave].strip(), (idioma, chave)
    assert "primeira_execucao.p2.erro_sistema" not in catalogo["pt"]


TEXTO_SYSTEMCTL = {
    "pt": "O systemctl daemon-reload falhou. Os detalhes ficaram no jobot.log.",
    "en": "systemctl daemon-reload failed. The details are in jobot.log.",
}


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize("onde", [PASSO_2, CONFIG_SP])
def test_systemctl_recusado_mostra_texto_fixo_e_loga_a_saida_uma_vez(
    painel: Painel, caplog: pytest.LogCaptureFixture, idioma: str, onde: str
) -> None:
    painel.sistema.falha_em["daemon-reload"] = Resultado(1, "", SEGREDO)
    dados = {"segundo_plano": "ligar" if onde == PASSO_2 else "on"}
    with caplog.at_level(logging.WARNING):
        resposta = painel.post(onde, dados, headers={"Accept-Language": idioma})
    assert resposta.status_code == 200
    pagina = html.unescape(resposta.text)
    assert TEXTO_SYSTEMCTL[idioma] in pagina
    assert SEGREDO not in pagina
    assert "segundo_plano.systemctl_falhou" not in pagina  # nunca a chave crua
    com_saida = [r for r in caplog.records if SEGREDO in r.getMessage()]
    assert len(com_saida) == 1  # a saída completa vai ao log uma vez só
    assert com_saida[0].levelno == logging.WARNING


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_texto_do_systemctl_nao_tem_o_marcador_da_saida(idioma: str) -> None:
    texto = i18n.carregar()[idioma]["segundo_plano.systemctl_falhou"]
    assert "{saida}" not in texto
    assert i18n.t(idioma, "segundo_plano.systemctl_falhou", comando="x", saida=SEGREDO) == (
        TEXTO_SYSTEMCTL[idioma].replace("daemon-reload", "x")
    )
