"""Rotas de sites (páginas acompanhadas): lista, adicionar, desativar e remover (plano T75, T112).

Sem rede: o painel não faz pedido nenhum aqui (só o DNS, trocado por `app.state.resolvedor`).
"""

from contextlib import closing
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.paginas import adicionar_pagina, gravar_leitura, marcar_falhou
from jobot.nucleo.coletores.paginas import Mudanca
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47622
AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
PUBLICO = "https://programa.exemplo.test/trainee"


async def _dns_publico(host: str) -> list[str]:
    return ["93.184.216.34"]


async def _dns_local(host: str) -> list[str]:
    return ["10.0.0.5"]


class Painel:
    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso(AGORA)
        self.app.state.resolvedor = _dns_publico
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def semear(self, url: str = PUBLICO, nome: str = "Trainee Alfa") -> int:
        with closing(abrir(self.banco)) as con:
            return adicionar_pagina(con, url, nome)

    def leitura(self, id_: int, texto: str, diferenca: str | None) -> None:
        with closing(abrir(self.banco)) as con:
            gravar_leitura(con, id_, Mudanca(texto, f"h-{texto}", diferenca), AGORA)

    def post(self, url: str, dados: dict[str, Any] | None = None) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **(dados or {})})

    def adicionar(self, url: str, nome: str = "Trainee Alfa") -> Any:
        return self.post("/sites", {"url": url, "nome": nome})


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def test_pagina_de_sites_abre_vazia_com_o_formulario(painel: Painel) -> None:
    r = painel.http.get("/sites")
    assert r.status_code == 200
    assert "Você ainda não acompanha nenhuma página" in r.text
    assert f'name="{CAMPO_CSRF}"' in r.text
    assert 'action="/sites"' in r.text


def test_adicionar_grava_e_volta_para_a_lista(painel: Painel) -> None:
    r = painel.adicionar(PUBLICO, "Trainee Alfa")
    assert r.status_code == 303
    assert r.headers["location"] == "/sites"
    assert painel.sql("SELECT url, nome, ativa FROM pagina_acompanhada") == [
        (PUBLICO, "Trainee Alfa", 1)
    ]
    assert "Trainee Alfa" in painel.http.get("/sites").text


@pytest.mark.parametrize(
    "endereco",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8080/",
        "http://[::1]/",
        "http://192.168.0.10/",
        "http://roteador/",
        "file:///etc/passwd",
        "ftp://exemplo.test/x",
        "http://usuario:senha@exemplo.test/",
        "isto não é um endereço",
    ],
)
def test_endereco_interno_ou_torto_e_recusado_com_mensagem(painel: Painel, endereco: str) -> None:
    r = painel.adicionar(endereco)
    assert r.status_code == 422
    assert "Esse endereço não pode ser acompanhado" in r.text
    assert f'value="{escape(endereco)}"' in r.text  # o texto digitado volta
    assert painel.sql("SELECT 1 FROM pagina_acompanhada") == []


def test_nome_que_resolve_para_rede_local_e_recusado_pela_barreira_de_dns(painel: Painel) -> None:
    painel.app.state.resolvedor = _dns_local
    r = painel.adicionar("https://parece-publico.exemplo.test/vagas")
    assert r.status_code == 422
    assert "Esse endereço não pode ser acompanhado" in r.text
    assert painel.sql("SELECT 1 FROM pagina_acompanhada") == []


def test_nome_que_nao_resolve_e_recusado_sem_500(painel: Painel) -> None:
    async def sem_dns(host: str) -> list[str]:
        raise OSError("sem resposta")

    painel.app.state.resolvedor = sem_dns
    r = painel.adicionar("https://nao-existe.exemplo.test/vagas")
    assert r.status_code == 422
    assert "Esse endereço não pode ser acompanhado" in r.text


@pytest.mark.parametrize("nome", ["", "   "])
def test_nome_vazio_e_recusado_com_mensagem(painel: Painel, nome: str) -> None:
    r = painel.adicionar(PUBLICO, nome)
    assert r.status_code == 422
    assert "Dê um nome" in r.text
    assert painel.sql("SELECT 1 FROM pagina_acompanhada") == []


def test_texto_enorme_e_recusado_com_mensagem(painel: Painel) -> None:
    assert painel.adicionar(PUBLICO, "n" * 101).status_code == 422
    assert painel.adicionar("https://exemplo.test/" + "a" * 600).status_code == 422
    assert painel.sql("SELECT 1 FROM pagina_acompanhada") == []


def test_post_sem_token_de_csrf_e_recusado(painel: Painel) -> None:
    r = painel.http.post("/sites", data={"url": PUBLICO, "nome": "X"})
    assert r.status_code == 403
    assert painel.sql("SELECT 1 FROM pagina_acompanhada") == []


def test_texto_da_pagina_de_terceiro_e_escapado(painel: Painel) -> None:
    id_ = painel.semear(nome="<script>alert(1)</script>")
    painel.leitura(id_, "a", None)
    painel.leitura(id_, "b", "-<img src=x onerror=alert(1)>\n+<b>novo</b>")
    html = painel.http.get("/sites").text
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_lista_mostra_estado_e_a_diferenca_da_mudanca(painel: Painel) -> None:
    id_ = painel.semear()
    painel.leitura(id_, "inscrições abertas", None)
    painel.leitura(id_, "inscrições encerradas", "-inscrições abertas\n+inscrições encerradas")
    html = painel.http.get("/sites").text
    assert "Mudou em 13/11/2026" in html
    assert "+inscrições encerradas" in html


def test_pagina_que_falhou_diz_isso_em_palavras_simples(painel: Painel) -> None:
    id_ = painel.semear()
    painel.leitura(id_, "texto bom", None)
    with closing(abrir(painel.banco)) as con:
        marcar_falhou(con, id_, "fora_do_ar")
    html = painel.http.get("/sites").text
    assert "Não deu para ler a página" in html
    assert "O último texto lido foi mantido" in html


@pytest.mark.parametrize(
    ("motivo", "frase"),
    [
        ("fora_do_ar", "fora do ar"),
        ("bloqueada", "bloqueou"),
        ("nao_e_texto", "não é texto"),
        ("endereco_recusado", "endereço não é permitido"),
        ("grande_demais", "grande demais"),
        ("erro", "erro inesperado"),
    ],
)
def test_sites_mostra_o_motivo_da_falha(painel: Painel, motivo: str, frase: str) -> None:
    id_ = painel.semear()
    painel.leitura(id_, "texto bom", None)
    with closing(abrir(painel.banco)) as con:
        marcar_falhou(con, id_, motivo)
    html = painel.http.get("/sites").text
    assert frase in html
    assert "fora do ar, bloqueada" not in html  # não é o texto genérico
    assert "O último texto lido foi mantido" in html


def test_sites_pagina_que_falhou_antes_do_motivo_mantem_o_texto_generico(painel: Painel) -> None:
    id_ = painel.semear()
    painel.leitura(id_, "texto bom", None)
    painel.sql("UPDATE pagina_acompanhada SET estado='falhou' WHERE id=?", id_)
    html = painel.http.get("/sites").text
    assert "Não deu para ler a página" in html
    assert "fora do ar, bloqueada ou ser um arquivo" in html


def test_programas_mostra_falhou_em_pagina_que_ja_mudou(painel: Painel) -> None:
    id_ = painel.semear(nome="Trainee Alfa")
    painel.leitura(id_, "a", None)
    painel.leitura(id_, "b", "-a\n+b")
    html = painel.http.get("/vagas?aba=programas").text
    assert "mudou em 13/11/2026" in html
    assert "Não deu para ler" not in html  # controle: lida, sem falha
    with closing(abrir(painel.banco)) as con:
        marcar_falhou(con, id_, "bloqueada")
    html = painel.http.get("/vagas?aba=programas").text
    assert "mudou em 13/11/2026" in html
    assert "Não deu para ler na última tentativa" in html
    assert "bloqueou" in html


def test_programas_mostra_o_motivo_da_pagina_que_nunca_mudou(painel: Painel) -> None:
    id_ = painel.semear(nome="Trainee Alfa")
    with closing(abrir(painel.banco)) as con:
        marcar_falhou(con, id_, "nao_e_texto")
    html = painel.http.get("/vagas?aba=programas").text
    assert "Não deu para ler na última tentativa" in html
    assert "não é texto" in html


def test_desativar_para_de_acompanhar_e_marca_na_lista(painel: Painel) -> None:
    id_ = painel.semear()
    r = painel.post(f"/sites/{id_}/desativar")
    assert r.status_code == 303
    assert r.headers["location"] == "/sites"
    assert painel.sql("SELECT ativa FROM pagina_acompanhada") == [(0,)]
    assert "Desativada" in painel.http.get("/sites").text


def test_remover_apaga_a_pagina_e_as_mudancas(painel: Painel) -> None:
    id_ = painel.semear()
    painel.leitura(id_, "a", None)
    painel.leitura(id_, "b", "-a\n+b")
    assert painel.sql("SELECT count(*) FROM mudanca_pagina") == [(1,)]
    r = painel.post(f"/sites/{id_}/remover")
    assert r.status_code == 303
    assert painel.sql("SELECT count(*) FROM pagina_acompanhada") == [(0,)]
    assert painel.sql("SELECT count(*) FROM mudanca_pagina") == [(0,)]


@pytest.mark.parametrize("acao", ["desativar", "remover"])
@pytest.mark.parametrize("id_", [999, 2**63 - 1])
def test_acao_em_pagina_que_nao_existe_e_404(painel: Painel, acao: str, id_: int) -> None:
    assert painel.post(f"/sites/{id_}/{acao}").status_code == 404


@pytest.mark.parametrize("id_", ["0", "-1", "abc", str(2**63)])
def test_id_torto_e_422(painel: Painel, id_: str) -> None:
    assert painel.post(f"/sites/{id_}/remover").status_code == 422


def test_aba_programas_lista_a_pagina_recem_adicionada_sem_mudanca(painel: Painel) -> None:
    id_ = painel.semear(nome="Trainee Alfa")
    html = painel.http.get("/vagas?aba=programas").text
    assert "Trainee Alfa" in html
    assert "Ainda não lida" in html
    assert "mudou em" not in html
    assert f'href="/sites#site-{id_}"' in html
    painel.leitura(id_, "a", None)  # primeira leitura: não grava mudança
    html = painel.http.get("/vagas?aba=programas").text
    assert "Trainee Alfa" in html
    assert "mudou em" not in html


def test_aba_programas_mostra_mudou_em_e_a_diferenca(painel: Painel) -> None:
    id_ = painel.semear(nome="Trainee Alfa")
    painel.leitura(id_, "a", None)
    painel.leitura(id_, "b", "-a\n+b")
    html = painel.http.get("/vagas?aba=programas").text
    assert "Trainee Alfa" in html
    assert "mudou em 13/11/2026" in html
    assert "+b" in html
    assert f'href="/sites#site-{id_}"' in html


def test_aba_programas_nao_mostra_pagina_desativada(painel: Painel) -> None:
    id_ = painel.semear(nome="Trainee Alfa")
    painel.leitura(id_, "a", None)
    painel.leitura(id_, "b", "-a\n+b")
    painel.post(f"/sites/{id_}/desativar")
    assert "Trainee Alfa" not in painel.http.get("/vagas?aba=programas").text


def test_outras_abas_nao_mostram_paginas(painel: Painel) -> None:
    id_ = painel.semear(nome="Trainee Alfa")
    painel.leitura(id_, "a", None)
    painel.leitura(id_, "b", "-a\n+b")
    assert "Trainee Alfa" not in painel.http.get("/vagas?aba=todas").text
