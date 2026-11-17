"""Rotas das buscas salvas: criar, editar, desligar, apagar e o seletor da lista (plano T52)."""

import json
import re
import time
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import semear
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.modelo import Local
from jobot.nucleo.tratamento.locais import _PAISES, ler_locais
from jobot.painel.app import criar_app
from jobot.painel.rotas import buscas as rota_buscas
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47617
REGRAS = ["modalidade", "nivel", "salario", "idioma", "pais"]


class Painel:
    """App sobre um banco semeado (11 vagas e a busca "Python remoto"), relógio parado."""

    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            self.ids = semear(con)
        self.app: FastAPI = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso()
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def get(self, url: str) -> Any:
        return self.http.get(url)

    def post(self, url: str, dados: dict[str, Any] | None = None) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **(dados or {})})

    def busca_id(self, nome: str) -> int:
        return int(self.sql("SELECT id FROM busca WHERE nome = ?", nome)[0][0])

    def total(self, tabela: str) -> int:
        return int(self.sql(f"SELECT COUNT(*) FROM {tabela}")[0][0])


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _form(**campos: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "nome": "Dados em Curitiba",
        "cargos": "analista de dados, python",
        "cidades": "Curitiba, PR",
        "modalidade": ["hibrido", "remoto"],
        "nivel": ["junior"],
        "salario": "5.000,50",
        "moeda": "BRL",
        "idioma": ["pt", "en"],
        "regra": REGRAS,
    }
    return base | campos


def _busca(painel: Painel, nome: str) -> tuple[Any, ...]:
    return painel.sql(
        "SELECT nome, ativa, cargos, cidades, modalidades, niveis, salario_min, salario_moeda,"
        " idiomas, regras_ocultar FROM busca WHERE nome = ?",
        nome,
    )[0]


def test_lista_mostra_as_buscas_e_o_formulario_de_nova(painel: Painel) -> None:
    r = painel.get("/buscas")
    assert r.status_code == 200
    assert "Python remoto" in r.text
    assert 'action="/buscas"' in r.text
    assert f'name="{CAMPO_CSRF}"' in r.text


def test_nome_da_busca_sai_escapado(painel: Painel) -> None:
    painel.post("/buscas", _form(nome="<b>x</b>"))
    html = painel.get("/buscas").text
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html


def test_criar_busca_grava_os_campos_e_calcula_o_encaixe(painel: Painel) -> None:
    r = painel.post("/buscas", _form())
    assert r.status_code == 303
    assert r.headers["location"] == "/buscas"
    nome, ativa, cargos, cidades, modalidades, niveis, minimo, moeda, idiomas, regras = _busca(
        painel, "Dados em Curitiba"
    )
    assert (nome, ativa, minimo, moeda) == ("Dados em Curitiba", 1, 500050, "BRL")
    assert isinstance(minimo, int)
    assert json.loads(cargos) == ["analista de dados", "python"]
    assert json.loads(cidades) == [{"cidade": "Curitiba", "uf": "PR", "pais": "BR"}]
    assert json.loads(modalidades) == ["hibrido", "remoto"]
    assert json.loads(niveis) == ["junior"]
    assert json.loads(idiomas) == ["pt", "en"]
    assert json.loads(regras) == dict.fromkeys(REGRAS, True)
    novo = painel.busca_id("Dados em Curitiba")
    linhas = painel.sql("SELECT COUNT(*) FROM encaixe WHERE busca_id = ?", novo)
    assert linhas[0][0] == painel.total("vaga")


def test_regra_desmarcada_fica_desligada(painel: Painel) -> None:
    painel.post("/buscas", _form(regra=["modalidade"]))
    regras = json.loads(_busca(painel, "Dados em Curitiba")[9])
    assert regras == {
        "modalidade": True,
        "nivel": False,
        "salario": False,
        "idioma": False,
        "pais": False,
    }


def test_criar_sem_token_csrf_e_403(painel: Painel) -> None:
    r = painel.http.post("/buscas", data=_form())
    assert r.status_code == 403
    assert painel.total("busca") == 1


@pytest.mark.parametrize(
    ("texto", "centavos"),
    [
        ("5000", 500000),
        ("5.000", 500000),
        ("5.000,50", 500050),
        ("5000,5", 500050),
        ("12.345.678", 1234567800),
        ("  3000  ", 300000),
    ],
)
def test_salario_digitado_vira_centavos_inteiros(painel: Painel, texto: str, centavos: int) -> None:
    assert painel.post("/buscas", _form(salario=texto)).status_code == 303
    assert _busca(painel, "Dados em Curitiba")[6] == centavos


def test_salario_em_branco_nao_grava_minimo_nem_moeda(painel: Painel) -> None:
    painel.post("/buscas", _form(salario="", moeda="USD"))
    linha = _busca(painel, "Dados em Curitiba")
    assert (linha[6], linha[7]) == (None, None)


def test_salario_em_dolar_guarda_a_moeda(painel: Painel) -> None:
    painel.post("/buscas", _form(salario="4000", moeda="USD"))
    linha = _busca(painel, "Dados em Curitiba")
    assert (linha[6], linha[7]) == (400000, "USD")


@pytest.mark.parametrize(
    "campos",
    [
        {"nome": ""},
        {"nome": "   "},
        {"nome": "x" * 101},
        {"salario": "abc"},
        {"salario": "5000.5"},
        {"salario": "1e5"},
        {"salario": "-5"},
        {"salario": "0"},
        {"salario": "5,000"},
        {"salario": "٣٠٠٠"},
        {"salario": "9" * 40},
        {"salario": "1" + "0" * 17},
        {"moeda": "XXX"},
        {"moeda": "brl"},
        {"modalidade": ["xyz"]},
        {"modalidade": ["nao_informado"]},
        {"nivel": ["chefe"]},
        {"idioma": ["klingon"]},
        {"regra": ["inventada"]},
        {"cidades": "Lugar Nenhum"},
        {"cidades": "Curitiba, PR\nnada que se entenda"},
        {"cargos": ",".join(f"c{n}" for n in range(60))},
        {"cargos": "x" * 101},
    ],
)
def test_valor_invalido_e_422_e_nao_grava(painel: Painel, campos: dict[str, Any]) -> None:
    r = painel.post("/buscas", _form(**campos))
    assert r.status_code == 422
    assert painel.total("busca") == 1


def test_erro_de_digitacao_mostra_a_mensagem_e_guarda_o_que_foi_digitado(
    painel: Painel,
) -> None:
    r = painel.post("/buscas", _form(nome="Minha busca", salario="abc"))
    assert r.status_code == 422
    assert 'role="alert"' in r.text
    assert 'value="Minha busca"' in r.text
    assert 'value="abc"' in r.text


def test_editar_mostra_o_formulario_preenchido(painel: Painel) -> None:
    painel.post("/buscas", _form())
    busca = painel.busca_id("Dados em Curitiba")
    html = painel.get(f"/buscas/{busca}").text
    assert f'action="/buscas/{busca}"' in html
    assert 'value="Dados em Curitiba"' in html
    assert "analista de dados" in html and "Curitiba, PR" in html
    assert 'value="5000,50"' in html
    assert re.search(r'name="modalidade" value="hibrido"[^>]*\schecked', html)
    assert not re.search(r'name="modalidade" value="presencial"[^>]*\schecked', html)
    assert re.search(r'name="nivel" value="junior"[^>]*\schecked', html)
    assert re.search(r'name="idioma" value="en"[^>]*\schecked', html)
    assert not re.search(r'name="idioma" value="es"[^>]*\schecked', html)


def test_editar_com_o_texto_do_formulario_nao_muda_nada(painel: Painel) -> None:
    painel.post("/buscas", _form(cidades="Lisboa, Portugal\nCuritiba, PR"))
    antes = _busca(painel, "Dados em Curitiba")
    busca = painel.busca_id("Dados em Curitiba")
    html = painel.get(f"/buscas/{busca}").text
    assert "Lisboa, Portugal" in html
    r = painel.post(
        f"/buscas/{busca}",
        _form(cidades="Lisboa, Portugal\nCuritiba, PR", salario="5000,50"),
    )
    assert r.status_code == 303
    assert _busca(painel, "Dados em Curitiba") == antes
    assert json.loads(antes[3])[0] == {"cidade": "Lisboa", "uf": None, "pais": "PT"}


def test_editar_troca_os_campos(painel: Painel) -> None:
    painel.post("/buscas", _form())
    busca = painel.busca_id("Dados em Curitiba")
    r = painel.post(
        f"/buscas/{busca}",
        _form(nome="Outro nome", modalidade=["presencial"], salario="", regra=[]),
    )
    assert r.status_code == 303
    linha = _busca(painel, "Outro nome")
    assert json.loads(linha[4]) == ["presencial"]
    assert linha[6] is None
    assert json.loads(linha[9]) == dict.fromkeys(REGRAS, False)
    assert painel.total("busca") == 2


def test_editar_recalcula_so_o_encaixe_da_busca_editada(painel: Painel) -> None:
    painel.post("/buscas", _form())
    outra = painel.busca_id("Dados em Curitiba")
    painel.sql("UPDATE encaixe SET nota = 7 WHERE busca_id = ?", outra)
    editada = painel.ids["busca"]
    antes = painel.sql("SELECT vaga_id, nota FROM encaixe WHERE busca_id = ?", editada)
    r = painel.post(
        f"/buscas/{editada}",
        _form(nome="Python remoto", cargos="python", cidades="", modalidade=["remoto"]),
    )
    assert r.status_code == 303
    depois = painel.sql("SELECT vaga_id, nota FROM encaixe WHERE busca_id = ?", editada)
    assert sorted(antes) != sorted(depois)
    sobra = painel.sql("SELECT nota FROM encaixe WHERE busca_id = ?", outra)
    assert len(sobra) == painel.total("vaga")
    assert {n for (n,) in sobra} == {7}


def test_desligar_e_ligar(painel: Painel) -> None:
    busca = painel.ids["busca"]
    r = painel.post(f"/buscas/{busca}/desligar")
    assert (r.status_code, r.headers["location"]) == (303, "/buscas")
    assert painel.sql("SELECT ativa FROM busca WHERE id = ?", busca) == [(0,)]
    assert "Desligada" in painel.get("/buscas").text
    painel.post(f"/buscas/{busca}/ligar")
    assert painel.sql("SELECT ativa FROM busca WHERE id = ?", busca) == [(1,)]


def test_desligar_nao_mexe_nos_outros_campos(painel: Painel) -> None:
    painel.post("/buscas", _form())
    antes = _busca(painel, "Dados em Curitiba")
    painel.post(f"/buscas/{painel.busca_id('Dados em Curitiba')}/desligar")
    depois = _busca(painel, "Dados em Curitiba")
    assert depois[1] == 0
    assert (antes[0], *antes[2:]) == (depois[0], *depois[2:])


@pytest.mark.parametrize(("acao", "ativa_antes"), [("ligar", 0), ("desligar", 1)])
def test_ligar_busca_com_valor_recusado_da_422(painel: Painel, acao: str, ativa_antes: int) -> None:
    busca = painel.ids["busca"]
    # gravada direto no banco com uma moeda que `editar_busca` recusa (moeda sem cotação)
    painel.sql(
        "UPDATE busca SET ativa = ?, salario_min = 500000, salario_moeda = 'XXX' WHERE id = ?",
        ativa_antes,
        busca,
    )
    # sem relançar a exceção do servidor: o vermelho é o 500, não um ValueError solto no teste
    http = TestClient(
        painel.app,
        base_url=f"http://127.0.0.1:{PORTA}",
        follow_redirects=False,
        raise_server_exceptions=False,
    )
    r = http.post(f"/buscas/{busca}/{acao}", data={CAMPO_CSRF: painel.token})
    assert r.status_code == 422
    assert painel.sql("SELECT ativa FROM busca WHERE id = ?", busca) == [(ativa_antes,)]


def test_apagar_leva_o_encaixe_e_deixa_a_vaga(painel: Painel) -> None:
    busca = painel.ids["busca"]
    vagas = painel.total("vaga")
    r = painel.post(f"/buscas/{busca}/apagar")
    assert (r.status_code, r.headers["location"]) == (303, "/buscas")
    assert painel.total("busca") == 0
    assert painel.sql("SELECT COUNT(*) FROM encaixe WHERE busca_id = ?", busca) == [(0,)]
    assert painel.total("vaga") == vagas


def _dialogo(html: str, busca: int) -> str:
    achado = re.search(rf'<dialog\b[^>]*id="alerta-busca-{busca}".*?</dialog>', html, re.DOTALL)
    assert achado, "falta o <dialog> do alerta de apagar"
    return achado.group(0)


def _tag_de_abertura(html: str) -> str:
    return html[: html.index(">") + 1]


def test_apagar_tem_alerta(painel: Painel) -> None:
    """T259: o alerta é um <dialog> com o nome escapado, o form de hoje, o foco no próprio dialog
    (E13: nenhum botão com autofocus) e o Cancelar fora do envio."""
    busca = painel.ids["busca"]
    painel.sql("UPDATE busca SET nome = ? WHERE id = ?", 'Dados <b>&"x"', busca)
    html = painel.get("/buscas").text
    dialogo = _dialogo(html, busca)
    abertura = _tag_de_abertura(dialogo)
    assert 'role="alertdialog"' in abertura
    assert re.search(r"\bautofocus\b", abertura)
    assert 'tabindex="-1"' in abertura
    assert "<b>" not in html  # o nome entrou escapado
    achou = re.search(r'<h2[^>]*class="alerta-titulo"[^>]*>(.*?)</h2>', dialogo, re.DOTALL)
    assert achou
    titulo = unescape(achou.group(1))
    assert titulo.strip() == 'Apagar a busca «Dados <b>&"x"»?'
    assert re.search(r'aria-labelledby="alerta-busca-\d+-titulo"', abertura)
    form = re.search(
        r'<form[^>]*action="/buscas/(\d+)/apagar"[^>]*>(.*?)</form>', dialogo, re.DOTALL
    )
    assert form and int(form.group(1)) == busca
    assert 'method="post"' in form.group(0)
    assert f'name="{CAMPO_CSRF}" value="{painel.token}"' in form.group(2)
    botoes = re.findall(r"<button\b[^>]*>", dialogo)
    assert len(botoes) == 2
    assert not any(re.search(r"\bautofocus\b", b) for b in botoes)
    cancelar = [b for b in botoes if 'type="button"' in b]
    assert len(cancelar) == 1 and "data-alerta-fecha" in cancelar[0]
    assert "As vagas que ela trouxe continuam." in dialogo


def _fora_do_dialogo(html: str) -> str:
    return re.sub(r"<dialog\b.*?</dialog>", "", html, flags=re.DOTALL)


def test_apagar_busca_sem_js_vai_para_confirmar(painel: Painel) -> None:
    """T307: o botão Apagar da linha, lido sem JavaScript, leva à página de confirmação (GET que
    não muda nada); o texto é o do alerta, o botão faz o POST de hoje e o Cancelar volta."""
    busca = painel.ids["busca"]
    painel.sql("UPDATE busca SET nome = ? WHERE id = ?", 'Dados <b>&"x"', busca)
    fora = _fora_do_dialogo(painel.get("/buscas").text)
    (form,) = re.findall(
        rf'<form[^>]*action="/buscas/{busca}/apagar/confirmar"[^>]*>.*?</form>', fora, re.DOTALL
    )
    assert 'method="get"' in form
    assert re.search(r'<button[^>]*type="submit"[^>]*data-alerta-abre="alerta-busca-\d+"', form)
    assert CAMPO_CSRF not in form  # GET: nada de token na URL
    assert f'action="/buscas/{busca}/apagar"' not in fora  # o POST direto só existe no alerta
    assert "<details" not in fora

    antes = painel.total("busca")
    for _ in range(2):  # GET repetido: nada muda
        r = painel.get(f"/buscas/{busca}/apagar/confirmar")
        assert r.status_code == 200
        assert painel.total("busca") == antes == 1
    pagina = r.text
    assert "<b>" not in pagina  # o nome entrou escapado
    titulo = re.search(r'<h1[^>]*class="alerta-titulo"[^>]*>(.*?)</h1>', pagina, re.DOTALL)
    assert titulo and unescape(titulo.group(1)).strip() == 'Apagar a busca «Dados <b>&"x"»?'
    assert "As vagas que ela trouxe continuam." in pagina
    (post,) = re.findall(
        rf'<form[^>]*action="/buscas/{busca}/apagar"[^>]*>(.*?)</form>', pagina, re.DOTALL
    )
    assert f'name="{CAMPO_CSRF}" value="{painel.token}"' in post
    assert re.search(r'<button[^>]*type="submit"[^>]*>\s*Apagar\s*</button>', post)
    assert re.search(r'<a\b[^>]*href="/buscas"[^>]*>\s*Cancelar\s*</a>', pagina)
    sem_paleta = re.sub(
        r'<dialog\b[^>]*\bid="(?:paleta|alerta-encerrar)".*?</dialog>', "", pagina, flags=re.S
    )
    assert "<dialog" not in sem_paleta and "autofocus" not in sem_paleta


def test_apagar_busca_confirmar_em_ingles(painel: Painel) -> None:
    painel.sql(
        "INSERT INTO config (chave, valor) VALUES ('idioma', '\"en\"')"
        " ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor"
    )
    pagina = painel.get(f"/buscas/{painel.ids['busca']}/apagar/confirmar").text
    assert "Delete the Search" in pagina and re.search(r">\s*Cancel\s*</a>", pagina)


@pytest.mark.parametrize(("busca", "status"), [("999", 404), (str(2**63 - 1), 404), ("0", 422)])
def test_apagar_busca_confirmar_de_busca_que_nao_existe(
    painel: Painel, busca: str, status: int
) -> None:
    assert painel.get(f"/buscas/{busca}/apagar/confirmar").status_code == status


def test_apagar_busca_post_direto_continua(painel: Painel) -> None:
    """O POST de hoje (o do alerta e o do botão da página de confirmação) apaga como antes."""
    busca = painel.ids["busca"]
    r = painel.post(f"/buscas/{busca}/apagar")
    assert (r.status_code, r.headers["location"], painel.total("busca")) == (303, "/buscas", 0)


@pytest.mark.parametrize(("ativa", "acao"), [(1, "desligar"), (0, "ligar")])
def test_linha_tem_interruptor_mini_e_menu(painel: Painel, ativa: int, acao: str) -> None:
    """Cada linha: o interruptor (role switch) num form que liga ou desliga, e o alvo do menu."""
    busca = painel.ids["busca"]
    painel.sql("UPDATE busca SET ativa = ? WHERE id = ?", ativa, busca)
    html = painel.get("/buscas").text
    linha = re.search(
        rf'<li\b[^>]*id="busca-{busca}".*?(?=<li\b[^>]*id="busca-|<dialog\b)', html, re.DOTALL
    )
    assert linha
    abertura = _tag_de_abertura(linha.group(0))
    assert 'data-menu="menu-busca"' in abertura and f'data-id="{busca}"' in abertura
    assert (" data-ligada" in abertura) == bool(ativa)
    assert (" data-desligada" in abertura) == (not ativa)
    form = re.search(
        rf'<form[^>]*action="/buscas/{busca}/{acao}"[^>]*>(.*?)</form>', linha.group(0), re.DOTALL
    )
    assert form and "data-envia-ao-mudar" in form.group(0)
    caixa = re.search(r'<input[^>]*role="switch"[^>]*>', form.group(1))
    assert caixa and 'class="chave chave-mini"' in caixa.group(0)
    assert ("checked" in caixa.group(0)) == bool(ativa)
    assert "aria-label=" in caixa.group(0)
    assert f'name="{CAMPO_CSRF}"' in form.group(1)


def test_menu_da_lista_tem_as_acoes_da_linha(painel: Painel) -> None:
    html = painel.get("/buscas").text
    menu = re.search(
        r'<div id="menu-busca"[^>]*data-menu-contexto.*?</div>\s*<div id="menu-busca-aviso"',
        html,
        re.DOTALL,
    )
    assert menu
    for modelo in (
        "/vagas?aba=todas&amp;busca={id}",
        "/buscas/{id}",
        "/buscas/{id}/ligar",
        "/buscas/{id}/desligar",
    ):
        assert modelo in menu.group(0), modelo
    assert 'data-requer="ligada"' in menu.group(0) and 'data-requer="desligada"' in menu.group(0)
    assert "data-acionar" in menu.group(0)
    assert len(re.findall(r'role="group"', menu.group(0))) == 3


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_buscas_sem_o_apagar_em_dois_cliques(painel: Painel, idioma: str) -> None:
    """O <details> de "Apagar mesmo" saiu: o texto antigo não aparece em nenhum idioma."""
    r = painel.http.get("/buscas", headers={"Accept-Language": idioma})
    assert "Apagar mesmo" not in r.text and "Delete it" not in r.text


@pytest.mark.parametrize("acao", ["", "/ligar", "/desligar", "/apagar"])
def test_busca_inexistente_e_404(painel: Painel, acao: str) -> None:
    assert painel.post(f"/buscas/999{acao}", _form()).status_code == 404
    assert painel.post(f"/buscas/{2**63 - 1}{acao}", _form()).status_code == 404


def test_busca_inexistente_no_get_e_404(painel: Painel) -> None:
    assert painel.get("/buscas/999").status_code == 404
    assert painel.get(f"/buscas/{2**63 - 1}").status_code == 404


@pytest.mark.parametrize("busca", ["0", "-1", str(2**63), "abc"])
def test_id_fora_do_alcance_e_422(painel: Painel, busca: str) -> None:
    assert painel.get(f"/buscas/{busca}").status_code == 422
    for acao in ("", "/ligar", "/desligar", "/apagar"):
        assert painel.post(f"/buscas/{busca}{acao}", _form()).status_code == 422


@pytest.mark.parametrize("codigo", sorted(set(_PAISES.values())))
def test_todo_pais_do_leitor_volta_igual_pelo_formulario(codigo: str) -> None:
    for local in (Local(pais=codigo), Local(cidade="Cidade Exemplo", pais=codigo)):
        assert ler_locais([rota_buscas._texto_local(local)]) == (local,)


def test_cidade_com_uf_volta_igual_pelo_formulario() -> None:
    for local in (Local(cidade="Curitiba", uf="PR", pais="BR"), Local(uf="SP", pais="BR")):
        assert ler_locais([rota_buscas._texto_local(local)]) == (local,)


@pytest.fixture
def fuso_toquio(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TZ", "JST-9")  # sem banco de fusos: UTC+9 fixo
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.parametrize(
    ("cotacao", "oculta"),
    [
        ("2026-11-07", "salario"),  # 7 dias antes do dia local (14/11): vale (controle positivo)
        ("2026-11-06", None),  # 8 dias antes do dia local, mas 7 antes do dia UTC: não vale
    ],
)
def test_criar_e_editar_busca_passam_o_dia_local(
    painel: Painel, fuso_toquio: None, cotacao: str, oculta: str | None
) -> None:
    # 23:00 UTC de 13/11 já é 08:00 de 14/11 em UTC+9
    painel.app.state.relogio = RelogioFalso(datetime(2026, 11, 13, 23, 0, tzinfo=UTC))
    painel.sql("DELETE FROM cotacao")
    painel.sql(
        "INSERT INTO cotacao (moeda, data, venda, buscada_em) VALUES ('USD', ?, '5.65', ?)",
        cotacao,
        "2026-11-13T23:00:00+00:00",
    )
    brl = painel.ids["brl"]  # R$ 8.000 por mês, plausível: abaixo de US$ 2.000 (R$ 11.300)

    def ocultada(busca: int) -> str | None:
        linhas = painel.sql(
            "SELECT oculta_motivo FROM encaixe WHERE busca_id = ? AND vaga_id = ?", busca, brl
        )
        return None if linhas[0][0] is None else str(linhas[0][0])

    sem_nada = {"modalidade": [], "nivel": [], "idioma": [], "cargos": "", "cidades": ""}
    painel.post("/buscas", _form(nome="criada", salario="2000", moeda="USD", **sem_nada))
    assert ocultada(painel.busca_id("criada")) == oculta

    painel.post("/buscas", _form(nome="editada", salario="", **sem_nada))
    editada = painel.busca_id("editada")
    assert ocultada(editada) is None
    painel.post(
        f"/buscas/{editada}", _form(nome="editada", salario="2000", moeda="USD", **sem_nada)
    )
    assert ocultada(editada) == oculta


def _seletor(html: str) -> list[tuple[str, bool]]:
    """As opções do seletor de busca (T254: um `<select>` num form GET): (endereço que o form
    monta ao escolher a opção, é a busca atual)."""
    bloco = re.search(r'<form class="seletor-busca".*?</form>', html, re.S)
    if bloco is None:
        return []
    ocultos = [
        (unescape(n), unescape(v))
        for n, v in re.findall(
            r'<input type="hidden" name="([^"]+)" value="([^"]*)">', bloco.group(0)
        )
    ]
    return [
        ("/vagas?" + urlencode([*ocultos, ("busca", m.group(1))]), "selected" in m.group(0))
        for m in re.finditer(r'<option value="([^"]+)"[^>]*>', bloco.group(0))
    ]


def _titulos(html: str) -> list[str]:
    return re.findall(r'<span class="linha-titulo" title="[^"]*">([^<]*)</span>', html)


def test_seletor_so_aparece_com_duas_buscas_ativas(painel: Painel) -> None:
    assert _seletor(painel.get("/vagas?aba=todas").text) == []
    painel.post("/buscas", _form(nome="Segunda"))
    assert len(_seletor(painel.get("/vagas?aba=todas").text)) == 2
    painel.post(f"/buscas/{painel.busca_id('Segunda')}/desligar")
    assert _seletor(painel.get("/vagas?aba=todas").text) == []
    # busca desligada que veio na URL continua escolhida, ao lado das ativas
    desligada = painel.busca_id("Segunda")
    links = _seletor(painel.get(f"/vagas?aba=todas&busca={desligada}").text)
    assert [atual for _, atual in links] == [False, True]


def test_seletor_leva_a_url_e_muda_a_lista(painel: Painel) -> None:
    # só vaga remota serve: a presencial "Analista de Sistemas" some desta busca
    painel.post("/buscas", _form(nome="Só remoto", modalidade=["remoto"], cargos="", cidades=""))
    segunda = painel.busca_id("Só remoto")
    padrao = painel.get("/vagas?aba=todas&q=Analista")
    links = _seletor(padrao.text)
    assert [atual for _, atual in links] == [True, False]
    assert "Analista de Sistemas" in _titulos(padrao.text)

    destino = next(url for url, atual in links if not atual)
    assert f"busca={segunda}" in destino and "aba=todas" in destino and "q=Analista" in destino
    escolhida = painel.get(destino)
    assert [atual for _, atual in _seletor(escolhida.text)] == [False, True]
    assert "Analista de Sistemas" not in _titulos(escolhida.text)


@pytest.mark.parametrize(
    ("idioma", "trecho"),
    [("pt", "variações do mesmo cargo"), ("en", "variations of the same title")],
)
def test_formulario_dica_de_cargos_sugere_variacoes(
    painel: Painel, idioma: str, trecho: str
) -> None:
    html = painel.http.get("/buscas", headers={"Accept-Language": idioma}).text
    assert trecho in html
    assert "sysadmin" in html
