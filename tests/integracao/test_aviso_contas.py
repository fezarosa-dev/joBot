"""Faixa de queda de sessão no topo (plano T276; desenho 5.5; E11, E14).

Os leitores falsos entram em `app.state.leitores`; as linhas de sessão vêm de `gravar_sessao`
com o relógio avançando, como a conferência as grava.
"""

import html as html_lib
import re
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.sessoes import gravar_sessao
from jobot.nucleo.contas import EstadoSessao, MotivoSessao
from jobot.nucleo.gmail import CONTA
from jobot.painel.app import criar_app

PORTA = 47622
INICIO = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
FALSO = "falso_logado"
OUTRO = "outro_logado"
LEITOR_FALSO = LeitorFalso(base="http://127.0.0.1:9")
LEITOR_OUTRO = LeitorFalso(base="http://127.0.0.1:9", chave=OUTRO, nome="Outro Site")
DIV = re.compile(r"<div\b[^>]*\bid=\"aviso-contas\"[^>]*>", re.S)


class Faixa:
    """App sobre um banco migrado com os dois sites semeados (desligados) e só o primeiro
    registrado como leitor, a não ser que `registrar` diga outra coisa."""

    def __init__(self, tmp_path: Path, registrar: tuple[LeitorFalso, ...]) -> None:
        self.banco = tmp_path / "jobot.db"
        self.hora = INICIO
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            cadastros.semear(con)
            cadastros.semear_leitores(con, [LEITOR_FALSO, LEITOR_OUTRO])
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.leitores = registrar
        self.http = TestClient(self.app, base_url=f"http://127.0.0.1:{PORTA}")

    def ligar(self, chave: str, ligada: bool = True) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.ligar_fonte(con, chave, ligada)

    def gravar(
        self,
        tipo: str,
        chave: str,
        estado: EstadoSessao,
        motivo: MotivoSessao | None = None,
    ) -> None:
        self.hora += timedelta(hours=1)
        with closing(abrir(self.banco)) as con:
            gravar_sessao(
                con, "conta" if tipo == "conta" else "site", chave, estado, motivo, self.hora
            )

    def cair(self, tipo: str, chave: str) -> None:
        """`conectado` e depois `precisa_entrar`: abre a queda."""
        self.gravar(tipo, chave, "conectado")
        self.gravar(tipo, chave, "precisa_entrar")

    def corpo(self) -> str:
        resposta = self.http.get("/aviso-contas")
        assert resposta.status_code == 200
        return str(resposta.text)

    def texto(self) -> str:
        sem_tags = re.sub(r"<[^>]+>", " ", self.corpo())
        return re.sub(r"\s+", " ", html_lib.unescape(sem_tags)).strip()


@pytest.fixture
def faixa(tmp_path: Path) -> Faixa:
    f = Faixa(tmp_path, (LEITOR_FALSO,))
    f.ligar(FALSO)
    return f


def test_vazio_sem_queda(faixa: Faixa) -> None:
    faixa.gravar("site", FALSO, "conectado")
    assert faixa.corpo().strip() == ""
    faixa.gravar("site", FALSO, "precisa_entrar")  # controle: a mesma montagem, agora em queda
    assert "Site falso" in faixa.corpo()


def test_um_site(faixa: Faixa) -> None:
    faixa.cair("site", FALSO)
    assert faixa.texto() == (
        "Sua sessão no Site falso caiu. Entre de novo para o joBot voltar a ler as vagas."
        " Entrar de novo"
    )
    assert f'href="/configuracoes/contas#conta-{FALSO}"' in faixa.corpo()


def test_varios_conta_o_gmail(faixa: Faixa) -> None:
    faixa.cair("site", FALSO)
    faixa.cair("conta", CONTA)
    texto = faixa.texto()
    assert texto.startswith("Sua sessão caiu em 2 contas. Entre de novo em Configurações › Contas.")
    assert "ler as vagas" not in texto
    assert f'href="/configuracoes/contas#conta-{FALSO}"' in faixa.corpo()


def test_gmail_entra_na_faixa(faixa: Faixa) -> None:
    faixa.cair("conta", CONTA)
    texto = faixa.texto()
    assert texto.startswith("Sua sessão no Gmail caiu. Entre de novo em Configurações › Contas.")
    assert "ler as vagas" not in texto
    assert 'href="/configuracoes/contas#conta-gmail"' in faixa.corpo()


def test_continua_em_nao_conferiu(faixa: Faixa) -> None:
    faixa.cair("site", FALSO)
    faixa.gravar("site", FALSO, "nao_conferiu", "sem_rede")
    assert "Site falso" in faixa.corpo()


def test_vazio_em_nunca_entrou(faixa: Faixa) -> None:
    faixa.gravar("site", FALSO, "precisa_entrar")
    assert faixa.corpo().strip() == ""
    faixa.cair("site", FALSO)  # controle: com `conectado` antes, a queda abre
    assert "Site falso" in faixa.corpo()


def test_some_em_conectado(faixa: Faixa) -> None:
    faixa.cair("site", FALSO)
    assert "Site falso" in faixa.corpo()  # controle
    faixa.gravar("site", FALSO, "conectado")
    assert faixa.corpo().strip() == ""


def test_some_depois_de_esquecer(faixa: Faixa) -> None:
    faixa.cair("site", FALSO)
    faixa.cair("conta", CONTA)
    assert "2 contas" in faixa.corpo()  # controle
    faixa.gravar("site", FALSO, "precisa_entrar", "esquecido")
    faixa.gravar("conta", CONTA, "precisa_entrar", "esquecido")
    assert faixa.corpo().strip() == ""


def test_some_desligado_e_volta_ao_ligar(faixa: Faixa) -> None:
    faixa.cair("site", FALSO)
    assert "Site falso" in faixa.corpo()  # controle
    faixa.ligar(FALSO, False)
    assert faixa.corpo().strip() == ""
    faixa.ligar(FALSO)
    assert "Site falso" in faixa.corpo()


def test_fonte_orfa_fica_de_fora(faixa: Faixa) -> None:
    faixa.ligar(OUTRO)
    faixa.cair("site", FALSO)
    faixa.cair("site", OUTRO)  # a fonte existe e caiu, mas não há leitor dela
    texto = faixa.texto()
    assert "Sua sessão no Site falso caiu." in texto  # controle positivo
    assert "Outro Site" not in texto and "2 contas" not in texto


def test_sem_leitor_so_o_gmail_da_faixa(tmp_path: Path) -> None:
    """D167 (E11, E13): sem leitor registrado o site nunca aparece, mas o Gmail ainda cai."""
    f = Faixa(tmp_path, ())
    f.ligar(FALSO)
    f.cair("site", FALSO)
    assert f.corpo().strip() == ""  # sem queda do Gmail, vazio
    f.cair("conta", CONTA)
    texto = f.texto()
    assert texto.startswith("Sua sessão no Gmail caiu. Entre de novo em Configurações › Contas.")
    assert "Site falso" not in texto and "2 contas" not in texto
    assert 'href="/configuracoes/contas#conta-gmail"' in f.corpo()


def test_varios_leva_ao_primeiro_da_ordem(tmp_path: Path) -> None:
    f = Faixa(tmp_path, (LEITOR_OUTRO, LEITOR_FALSO))  # a ordem dada, não a do cadastro
    f.ligar(FALSO)
    f.ligar(OUTRO)
    f.cair("site", FALSO)
    f.cair("site", OUTRO)
    assert "2 contas" in f.texto()
    assert f'href="/configuracoes/contas#conta-{OUTRO}"' in f.corpo()
    assert f"#conta-{FALSO}" not in f.corpo()


def test_casca_tem_o_aviso_contas(faixa: Faixa) -> None:
    html = faixa.http.get("/vagas").text
    div = DIV.search(html)
    assert div is not None
    for atributo in (
        'role="status"',
        'hx-get="/aviso-contas"',
        'hx-trigger="load, contas-mudou from:body"',
    ):
        assert atributo in div.group(0), atributo
    assert html.index('id="aviso-versao"') < div.start() < html.index('id="faixa-desfazer"')
    assert 'id="faixa-contas"' not in html
