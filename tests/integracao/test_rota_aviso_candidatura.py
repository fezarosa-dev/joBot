"""A faixa "Você se candidatou?" e as respostas dela (plano T285; desenho 5.6; E6, E9, E18, E21).

As aberturas entram por `acoes.abriu_candidatura` com o relógio avançando; as rotas leem a hora
do `RelogioFalso` do app.
"""

import html as html_lib
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import semear
from jobot.banco import acoes, leitura
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import CABECALHOS, criar_app

PORTA = 47623
BASE = f"http://127.0.0.1:{PORTA}"
HORA = datetime(2026, 11, 16, 15, 30, tzinfo=UTC)
HTMX = {"HX-Request": "true"}
DIV = re.compile(r"<div\b[^>]*\bid=\"aviso-candidatura\"[^>]*>", re.S)
VOLTAR = re.compile(r'name="voltar" value="([^"]*)"')
MOSTRANDO = re.compile(r'<input type="hidden" name="mostrando" value="([^"]*)">')


class Painel:
    """App sobre um banco semeado, com o relógio parado em `HORA`."""

    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        self.hora = HORA
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            self.ids = semear(con)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso(HORA)
        self.http = TestClient(self.app, base_url=BASE, follow_redirects=False)
        self.token: str = self.app.state.csrf

    def con(self) -> closing[sqlite3.Connection]:
        return closing(abrir(self.banco))

    def abrir(self, nome: str) -> int:
        """Abre a candidatura da vaga `nome`, um minuto depois da anterior."""
        self.hora += timedelta(minutes=1)
        vaga = self.ids[nome]
        with self.con() as con:
            assert acoes.abriu_candidatura(con, vaga, self.hora)
        return vaga

    def status(self, vaga: int) -> str:
        with self.con() as con:
            return str(con.execute("SELECT status FROM vaga WHERE id = ?", (vaga,)).fetchone()[0])

    def pendentes(self) -> int:
        with self.con() as con:
            return leitura.perguntas_pendentes(con, 1)[1]

    def eventos(self, vaga: int) -> list[tuple[str, str | None, str | None]]:
        with self.con() as con:
            return con.execute(
                "SELECT acao, de, para FROM evento WHERE vaga_id = ? ORDER BY id", (vaga,)
            ).fetchall()

    def faixa(self, mostrando: str | None = None, **cabecalhos: str) -> Any:
        params = {} if mostrando is None else {"mostrando": mostrando}
        return self.http.get("/aviso-candidatura", params=params, headers=HTMX | cabecalhos)

    def responder(self, vaga: int, resposta: str, htmx: bool = True, **campos: str) -> Any:
        dados = {"csrf_token": self.token, "resposta": resposta, **campos}
        return self.http.post(
            f"/vagas/{vaga}/candidatura/resposta", data=dados, headers=HTMX if htmx else {}
        )

    def desfazer(self, vaga: int, htmx: bool = True, **campos: str) -> Any:
        dados = {"csrf_token": self.token, **campos}
        return self.http.post(
            f"/vagas/{vaga}/candidatura/desfazer", data=dados, headers=HTMX if htmx else {}
        )


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _texto(corpo: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", corpo)
    return re.sub(r"\s+", " ", html_lib.unescape(sem_tags)).strip()


def _mostrando(corpo: str) -> str:
    achou: list[str] = MOSTRANDO.findall(corpo)
    assert len(achou) == 1, corpo
    return achou[0]


def _gatilhos(resposta: Any) -> set[str]:
    return {nome.strip() for nome in resposta.headers.get("hx-trigger", "").split(",")}


# ---- fragmento ----


def test_sem_pendente_fragmento_vazio(painel: Painel) -> None:
    resposta = painel.faixa()
    assert resposta.status_code == 200
    assert resposta.text.strip() == '<input type="hidden" name="mostrando" value="v-0">'
    vaga = painel.abrir("nova")  # controle: depois de uma abertura, a pergunta aparece
    corpo = painel.faixa().text
    assert "Você se candidatou a Engenheira de Integração (Nova SA)?" in _texto(corpo)
    assert _mostrando(corpo) == f"p{vaga}-1"


def test_mostra_a_mais_recente(painel: Painel) -> None:
    painel.abrir("nova")
    recente = painel.abrir("usd")
    corpo = painel.faixa().text
    texto = _texto(corpo)
    assert "Você se candidatou a Desenvolvedor Python (Zeta Corp)?" in texto
    assert "Engenheira de Integração" not in texto
    assert "Você abriu a candidatura 16/11/2026." in texto
    assert _mostrando(corpo) == f"p{recente}-2"
    assert f'id="faixa-pergunta-{recente}"' in corpo
    assert f'aria-labelledby="faixa-pergunta-{recente}"' in corpo
    assert '<span class="icone" data-icone="circle-help" aria-hidden="true">' in corpo


def test_e_mais_n_leva_ao_panorama(painel: Painel) -> None:
    for nome in ("nova", "usd", "brl"):
        painel.abrir(nome)
    corpo = painel.faixa().text
    assert re.search(r'<a href="/panorama#para-responder">e mais 2 para responder</a>', corpo)


# ---- resposta ----


def test_resposta_sim_troca_status_e_dispara_evento(painel: Painel) -> None:
    vaga = painel.abrir("nova")
    resposta = painel.responder(vaga, "sim")
    assert resposta.status_code == 200
    assert painel.status(vaga) == "candidatei"
    assert _gatilhos(resposta) == {"candidatura-mudou", f"vaga-mudou-{vaga}"}
    corpo = resposta.text
    assert "Engenheira de Integração marcada como Candidatei." in _texto(corpo)
    assert f'hx-post="/vagas/{vaga}/candidatura/desfazer"' in corpo
    assert 'hx-target="#aviso-candidatura"' in corpo
    assert 'name="para"' not in corpo  # E18: o Desfazer não leva o status de antes
    assert _mostrando(corpo) == f"c{vaga}-0"


@pytest.mark.parametrize(
    ("atual", "esperado"),
    [
        ("http://127.0.0.1/vagas/{id}?busca=3", "/vagas/{id}?busca=3"),
        ("http://127.0.0.1//fora.test/x", "/"),
        ("http://127.0.0.1/vagas\\fora", "/"),
        (None, "/"),
    ],
)
def test_voltar_sai_do_hx_current_url(painel: Painel, atual: str | None, esperado: str) -> None:
    vaga = painel.abrir("nova")
    cabecalhos = {} if atual is None else {"HX-Current-URL": atual.format(id=vaga)}
    corpo = painel.faixa(**cabecalhos).text
    voltar = [html_lib.unescape(v) for v in VOLTAR.findall(corpo)]
    assert voltar == [esperado.format(id=vaga)] * 2


def test_resposta_invalida_422(painel: Painel) -> None:
    vaga = painel.abrir("nova")
    assert painel.responder(vaga, "talvez").status_code == 422
    assert painel.pendentes() == 1
    assert painel.status(vaga) == "nova"


def test_resposta_sem_js_303(painel: Painel) -> None:
    vaga = painel.abrir("nova")
    resposta = painel.responder(vaga, "ainda_nao", htmx=False, voltar="/vagas?aba=salvas")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/vagas?aba=salvas"
    assert painel.pendentes() == 0


def test_post_sem_csrf_recusado(painel: Painel) -> None:
    vaga = painel.abrir("nova")
    url = f"/vagas/{vaga}/candidatura/resposta"
    recusada = painel.http.post(url, data={"resposta": "sim"}, headers=HTMX)
    assert recusada.status_code == 403
    assert painel.status(vaga) == "nova"
    assert painel.pendentes() == 1
    # controle: com o token, grava
    assert painel.responder(vaga, "sim").status_code == 200
    assert painel.status(vaga) == "candidatei"


# ---- desfazer ----


def test_desfazer_volta_ao_status_anterior_sem_reabrir(painel: Painel) -> None:
    vaga = painel.abrir("fechada_salva")
    painel.responder(vaga, "sim")
    assert painel.status(vaga) == "candidatei"
    painel.desfazer(vaga)
    assert painel.status(vaga) == "salva"
    assert painel.pendentes() == 0
    assert painel.eventos(vaga)[-2:] == [
        ("mudou_status", "salva", "candidatei"),
        ("desfez", "candidatei", "salva"),
    ]


def test_desfazer_devolve_fragmento_da_faixa(painel: Painel) -> None:
    vaga = painel.abrir("nova")
    outra = painel.abrir("usd")
    painel.responder(vaga, "sim")
    resposta = painel.desfazer(vaga)
    assert resposta.status_code == 200
    assert painel.status(vaga) == "nova"
    assert _gatilhos(resposta) == {"candidatura-mudou", f"vaga-mudou-{vaga}"}
    assert _mostrando(resposta.text) == f"p{outra}-1"  # a próxima pendente
    assert 'class="linha' not in resposta.text and "<article" not in resposta.text


def test_desfazer_ignora_campo_para(painel: Painel) -> None:
    """Guarda (E18): o Desfazer decide no servidor (mutante: a rota ler `para` do formulário)."""
    vaga = painel.abrir("nova")
    with painel.con() as con:
        assert acoes.responder_candidatura(con, vaga, True, HORA) == "nova"
    painel.desfazer(vaga, para="salva")
    assert painel.status(vaga) == "nova"


def test_desfazer_sem_sim_nao_muda(painel: Painel) -> None:
    """Guarda (E18): `candidatei` por outro Desfazer não volta (mutante: `desfazer_status`)."""
    vaga = painel.ids["nova"]
    with painel.con() as con:
        for passo in ("salva", "candidatei", "entrevista"):
            acoes.mudar_status(con, vaga, passo, HORA)
        acoes.desfazer_status(con, vaga, HORA)
    assert painel.status(vaga) == "candidatei"
    resposta = painel.desfazer(vaga)
    assert resposta.status_code == 200
    assert painel.status(vaga) == "candidatei"
    assert _mostrando(resposta.text) == "v-0"


def test_desfazer_sem_js_303(painel: Painel) -> None:
    vaga = painel.abrir("nova")
    painel.responder(vaga, "sim")
    resposta = painel.desfazer(vaga, htmx=False, voltar="/vagas/1?busca=2")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/vagas/1?busca=2"
    assert painel.status(vaga) == "nova"


# ---- regra do 204 ----


def test_mesmo_estado_responde_204(painel: Painel) -> None:
    vaga = painel.abrir("nova")
    resposta = painel.faixa(f"p{vaga}-1")
    assert resposta.status_code == 204
    assert resposta.content == b""
    controle = painel.faixa()  # sem `mostrando`, a faixa
    assert controle.status_code == 200
    assert _mostrando(controle.text) == f"p{vaga}-1"


def test_confirmacao_fica_com_mesmo_total_204(painel: Painel) -> None:
    vaga = painel.abrir("nova")
    painel.responder(vaga, "sim")
    resposta = painel.faixa(f"c{vaga}-0")
    assert resposta.status_code == 204
    assert resposta.content == b""


def test_pendente_nova_troca_a_faixa(painel: Painel) -> None:
    primeira = painel.abrir("nova")
    segunda = painel.abrir("usd")
    resposta = painel.faixa(f"p{primeira}-1")
    assert resposta.status_code == 200
    assert _mostrando(resposta.text) == f"p{segunda}-2"


# ---- erro e casca ----


def test_erro_nao_quebra_a_pagina(painel: Painel, monkeypatch: pytest.MonkeyPatch) -> None:
    def quebra(*_: object) -> None:
        raise sqlite3.OperationalError("database disk image is malformed")

    monkeypatch.setattr(leitura, "perguntas_pendentes", quebra)
    http = TestClient(painel.app, base_url=BASE, raise_server_exceptions=False)
    resposta = http.get("/aviso-candidatura", headers=HTMX)
    assert resposta.status_code == 500
    for nome, valor in CABECALHOS.items():
        assert resposta.headers[nome] == valor, nome
    assert http.get("/vagas").status_code == 200


def test_casca_tem_o_aviso_candidatura(painel: Painel) -> None:
    html = painel.http.get("/vagas").text
    div = DIV.search(html)
    assert div is not None
    for atributo in (
        'role="status"',
        'hx-get="/aviso-candidatura"',
        'hx-trigger="load, focus from:window"',
        'hx-include="find input[name=mostrando]"',
        'hx-swap="innerHTML"',
    ):
        assert atributo in div.group(0), atributo
    assert "candidatura-mudou" not in div.group(0)
    assert html.index('id="aviso-contas"') < div.start() < html.index('id="faixa-desfazer"')
