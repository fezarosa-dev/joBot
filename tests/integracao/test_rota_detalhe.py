"""Rotas do detalhe da vaga e da correção (plano T46; D11, D12, D40, DP8)."""

import html as html_lib
import importlib
import re
import time
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import semear
from jobot.banco import acoes
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import seguranca
from jobot.painel.app import criar_app
from jobot.painel.rotas import vagas
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47616
GRANDE = 2**63 - 1  # o maior id do SQLite: vaga que não existe, e não 500


class Painel:
    """Cliente do app sobre um banco semeado, com o relógio parado em `AGORA`."""

    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            self.ids = semear(con)
        self.app = criar_app(tmp_path, PORTA)
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

    def post(self, url: str, **dados: str) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **dados})

    def detalhe(self, nome: str) -> str:
        resposta = self.get(f"/vagas/{self.ids[nome]}")
        assert resposta.status_code == 200
        return str(resposta.text)

    def corrigir(self, nome: str, campo: str, valor: str, comentario: str = "") -> Any:
        return self.post(
            f"/vagas/{self.ids[nome]}/correcao",
            campo=campo,
            **{f"valor_{campo}": valor},
            comentario=comentario,
        )


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


FAIXA = r'<section class="[^"]*\bfaixa\b[^"]*".*?</section>'


def _texto(html: str) -> str:
    """O texto visível aproximado: sem tags, entidades desfeitas, espaço único."""
    sem_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html_lib.unescape(sem_tags))


def _secao_faixa(html: str) -> str:
    achou = re.search(FAIXA, html, re.S)
    assert achou is not None
    return achou.group(0)


def _ancora(html: str, pedaco: str) -> str:
    achou = re.search(rf"<a\b[^>]*{re.escape(pedaco)}[^>]*>", html)
    assert achou, f"sem link com {pedaco!r}"
    return achou.group(0)


# ---------------------------------------------------------------- D40


def test_de_volta_vive_em_seguranca() -> None:
    assert getattr(seguranca, "de_volta", None) is not None
    assert vars(vagas)["de_volta"] is seguranca.de_volta
    assert seguranca.de_volta("/vagas?aba=salvas").headers["location"] == "/vagas?aba=salvas"
    for fora in ("//evil.test", "https://evil.test/x", "/a\\b", "evil"):
        assert seguranca.de_volta(fora).headers["location"] == "/"


# ---------------------------------------------------------------- detalhe


def test_detalhe_de_vaga_inexistente_e_404(painel: Painel) -> None:
    assert painel.get("/vagas/9999").status_code == 404
    assert painel.get(f"/vagas/{GRANDE}").status_code == 404
    assert painel.get(f"/vagas/{GRANDE + 1}").status_code == 422
    assert painel.get(f"/vagas/{GRANDE}/correcao").status_code == 404


def test_descricao_com_script_aparece_como_texto(painel: Painel) -> None:
    html = painel.detalhe("script")
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt;" in html
    assert "Olá <script>" in _texto(html)


def test_via_fonte_com_link_seguro_para_toda_fonte(painel: Painel) -> None:
    html = painel.detalhe("usd")
    ancora = _ancora(html, 'href="https://exemplo.test/vagas/')
    assert 'target="_blank"' in ancora
    assert 'rel="noopener noreferrer"' in ancora
    assert "nofollow" not in html
    assert "via Remotive" in _texto(html)
    # Himalayas tem crédito obrigatório e mesmo assim não muda nada: o link é o da própria vaga
    himalayas = painel.detalhe("himalayas")
    assert 'href="https://himalayas.app/companies/beta/jobs/42"' in himalayas
    assert "via Himalayas" in _texto(himalayas)


def test_botao_de_candidatura_usa_o_link_da_fonte_sem_mudar(painel: Painel) -> None:
    html = painel.detalhe("himalayas")
    ancora = _ancora(html, 'href="https://himalayas.app/companies/beta/jobs/42/apply"')
    assert 'rel="noopener noreferrer"' in ancora
    assert 'target="_blank"' in ancora
    # sem link de candidatura a fonte manda, o botão abre a página da vaga na fonte (desenho 13.5)
    botao = _ancora(painel.detalhe("usd"), 'class="primario"')
    assert 'href="https://exemplo.test/vagas/' in botao
    assert 'target="_blank"' in botao
    assert 'rel="noopener noreferrer"' in botao
    assert "/apply" not in botao


def test_link_de_candidatura_tem_data_candidatura(painel: Painel) -> None:
    vaga = painel.ids["himalayas"]
    ancora = _ancora(painel.detalhe("himalayas"), 'class="primario"')
    assert f'data-candidatura="/vagas/{vaga}/candidatura"' in ancora
    # continua um link normal
    assert 'href="https://himalayas.app/companies/beta/jobs/42/apply"' in ancora
    assert 'target="_blank"' in ancora
    assert 'rel="noopener noreferrer"' in ancora
    # o link "Abrir no site" não registra candidatura
    assert "data-candidatura" not in _ancora(painel.detalhe("himalayas"), 'class="secundario"')


def test_sem_nenhum_link_http_nao_ha_botao_de_candidatura(painel: Painel) -> None:
    painel.sql(
        "UPDATE ocorrencia SET url = 'ftp://exemplo.test/x' WHERE vaga_id = ?", painel.ids["usd"]
    )
    assert 'class="primario"' not in painel.detalhe("usd")


def test_fonte_repetida_em_escopos_diferentes_mostra_todos_os_links(painel: Painel) -> None:
    painel.sql(
        "INSERT INTO ocorrencia (vaga_id, fonte, escopo, url, coletada, primeira_vista_em,"
        " ultima_vista_em) SELECT vaga_id, fonte, 'b', 'https://exemplo.test/outro', coletada,"
        " primeira_vista_em, ultima_vista_em FROM ocorrencia WHERE vaga_id = ?",
        painel.ids["usd"],
    )
    html = painel.detalhe("usd")
    assert f'href="https://exemplo.test/vagas/{painel.ids["usd"]}"' in html
    assert 'href="https://exemplo.test/outro"' in html


def test_salario_em_moeda_estrangeira_traz_a_cotacao_ao_lado(painel: Painel) -> None:
    texto = _texto(painel.detalhe("usd"))
    assert "US$ 5.000/mês" in texto
    assert "≈ R$ 28.250/mês · US$ 1 = R$ 5,65 (PTAX de 13/11)" in texto


def test_valor_convertido_fica_em_linha_propria_no_detalhe(painel: Painel) -> None:
    painel.sql(
        "INSERT INTO cotacao (moeda, data, venda, buscada_em) VALUES ('EUR', '2026-11-12', '6.25',"
        " '2026-11-13T12:00:00+00:00')"
    )
    painel.sql(
        "INSERT INTO config (chave, valor) VALUES ('moeda_exibicao', '\"EUR\"')"
        " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor"
    )
    html = painel.detalhe("usd")
    assert re.search(
        r"<strong>US\$ 5\.000/mês</strong>\s*"
        r'<small class="convertido">≈ € 4\.520/mês · US\$ 1 = € 0,904 \(PTAX de 12/11\)</small>',
        html,
    )
    assert 'class="cotacao"' not in html


def test_salario_sem_cotacao_mostra_so_o_valor_original(painel: Painel) -> None:
    painel.sql("DELETE FROM cotacao")
    painel.sql(
        "UPDATE vaga SET sal_mensal_min_brl = NULL, sal_cotacao_data = NULL WHERE id = ?",
        painel.ids["usd"],
    )
    html = painel.detalhe("usd")
    assert "US$ 5.000/mês" in _texto(html)
    assert "PTAX" not in html
    assert "≈" not in html


def test_vaga_sem_salario_diz_que_nao_foi_informado(painel: Painel) -> None:
    assert "Salário não informado" in _texto(painel.detalhe("nova"))


def test_faixa_de_doze_meses_tem_texto_equivalente(painel: Painel) -> None:
    faixa = _secao_faixa(painel.detalhe("prazo_3_dias"))
    grade = re.search(r"<ol\b[^>]*>.*?</ol>", faixa, re.S)
    assert grade is not None
    assert len(re.findall(r"<li\b", grade.group(0))) == 12
    assert 'aria-hidden="true"' in grade.group(0).split(">")[0]
    texto = _texto(faixa)
    assert "Prazo: 16/11/2026" in texto
    assert "faltam 3 dias" in texto
    assert "sem datas informadas" not in texto


def test_faixa_comeca_no_mes_atual(painel: Painel) -> None:
    grade = re.search(r"<ol\b[^>]*>.*?</ol>", _secao_faixa(painel.detalhe("prazo_3_dias")), re.S)
    assert grade is not None
    primeiro = re.search(r"<li\b[^>]*>", grade.group(0))
    assert primeiro is not None
    assert 'class="atual"' in primeiro.group(0)  # hoje é 13/11: a grade abre em novembro


def test_faixa_sem_nenhuma_data_diz_sem_datas_informadas(painel: Painel) -> None:
    painel.sql("UPDATE vaga SET publicada_em = NULL, prazo = NULL, inicio = NULL")
    faixa = _secao_faixa(painel.detalhe("nova"))
    assert "sem datas informadas" in _texto(faixa)
    assert "<ol" not in faixa


def test_prazo_perto_e_marcado_como_urgente_e_longe_nao(painel: Painel) -> None:
    assert 'class="urgente"' in painel.detalhe("prazo_3_dias")
    assert 'class="urgente"' not in painel.detalhe("trainee")  # prazo em 37 dias
    # menos de 7 dias: 6 dias é urgente, 7 já não (o selo "Fecha logo" vai até 7, a faixa não)
    painel.sql("UPDATE vaga SET prazo = '2026-11-19' WHERE id = ?", painel.ids["trainee"])
    assert 'class="urgente"' in painel.detalhe("trainee")
    painel.sql("UPDATE vaga SET prazo = '2026-11-20' WHERE id = ?", painel.ids["trainee"])
    assert 'class="urgente"' not in painel.detalhe("trainee")


def test_detalhe_mostra_encaixe_e_ocultar_volta_para_o_detalhe(painel: Painel) -> None:
    html = painel.detalhe("usd")
    assert "Encaixe: Bom" in _texto(html)
    vaga = painel.ids["usd"]
    assert f'value="/vagas/{vaga}"' in html  # `voltar` das ações da vaga
    assert f'action="/vagas/{vaga}/ocultar"' in html
    assert f'href="/vagas/{vaga}/correcao"' in html


def test_pagina_propria_embrulha_o_detalhe_para_a_leitura(painel: Painel) -> None:
    html = painel.detalhe("usd")
    # T264: a página própria tem o seu invólucro (título e largura de leitura vêm dele)
    assert re.search(
        r'<div class="detalhe-pagina">\s*<p class="voltar"><a href="/vagas">[^<]+</a></p>\s*'
        r'<article class="detalhe">',
        html,
    )
    assert html.count('class="detalhe-pagina"') == 1


def test_acoes_de_estado_ficam_num_grupo_so(painel: Painel) -> None:
    """Salvar e Ocultar formam um grupo: quebra de linha inteiro, nunca um botão só. A situação
    fica fora dele, antes de toda a fileira (T301 item 8: numa linha própria, acima)."""
    html = painel.detalhe("usd")
    achou = re.search(r'<div class="acoes-estado">(.*?)</div>\s*</div>\s*<section', html, re.S)
    assert achou is not None
    grupo = achou.group(1)
    vaga = painel.ids["usd"]
    assert 'class="situacao"' not in grupo
    assert f'action="/vagas/{vaga}/status"' in grupo
    assert f'action="/vagas/{vaga}/ocultar"' in grupo
    grupo_acoes = re.search(r'<div class="acoes".*?<div class="acoes-estado">', html, re.S)
    assert grupo_acoes is not None
    antes = grupo_acoes.group(0)
    assert 'class="primario"' in antes  # os links de fora ficam antes do grupo
    assert antes.index('class="situacao"') < antes.index('class="primario"')


def _aba_marcada(html: str) -> list[str]:
    """Os `href` dos itens da seção Vagas da lateral que levam `aria-current`."""
    lista = re.search(r'<ul id="lateral-vagas".*?</ul>', html, re.S)
    assert lista is not None
    itens = re.findall(r"<a\b[^>]*>", lista.group(0))
    assert itens
    marcados = re.findall(r'href="([^"]*)"[^>]*aria-current', "".join(itens))
    return [href.split("&amp;")[0] for href in marcados]  # sem o `&busca=` da busca escolhida


def test_detalhe_sem_aba_na_url_nao_marca_aba_nenhuma(painel: Painel) -> None:
    assert _aba_marcada(painel.detalhe("usd")) == []


def test_detalhe_com_aba_na_url_marca_a_de_origem(painel: Painel) -> None:
    resposta = painel.get(f"/vagas/{painel.ids['usd']}?aba=salvas")
    assert resposta.status_code == 200
    assert _aba_marcada(resposta.text) == ["/vagas?aba=salvas"]
    assert 'aria-current="true"' in resposta.text  # área marcada, não a página dela


def test_detalhe_com_aba_que_nao_existe_nao_marca_aba_nenhuma(painel: Painel) -> None:
    resposta = painel.get(f"/vagas/{painel.ids['usd']}?aba=inventada")
    assert resposta.status_code == 200
    assert _aba_marcada(resposta.text) == []


def test_lista_de_vagas_sem_aba_na_url_marca_a_primeira(painel: Painel) -> None:
    """Guarda: só o detalhe perde a aba padrão; a lista segue marcando a primeira."""
    resposta = painel.get("/vagas")
    assert resposta.status_code == 200
    marcadas = _aba_marcada(resposta.text)
    assert len(marcadas) == 1
    assert marcadas[0].startswith("/vagas?aba=")


# ---------------------------------------------------------------- correção


def test_formulario_de_correcao_tem_um_campo_por_item(painel: Painel) -> None:
    resposta = painel.get(f"/vagas/{painel.ids['usd']}/correcao")
    assert resposta.status_code == 200
    html = resposta.text
    for campo in ("area", "nivel", "modalidade", "contrato", "uf", "salario", "fechada", "outro"):
        assert f'name="valor_{campo}"' in html
        assert f'name="campo" value="{campo}"' in html
        assert f'id="correcao-comentario-{campo}"' in html  # comentário opcional em toda linha
    assert html.count('name="comentario"') == 8
    assert "Algo errado nesta vaga?" in _texto(html)


def test_formulario_traz_o_valor_atual_selecionado(painel: Painel) -> None:
    def pagina(nome: str) -> str:
        return str(painel.get(f"/vagas/{painel.ids[nome]}/correcao").text)

    html = pagina("script")
    for opcao in ("dados", "junior", "hibrido", "clt"):
        assert f'<option value="{opcao}" selected>' in html
    assert '<option value="nao" selected>' in html  # um clique distraído não fecha a vaga
    assert '<option value="sim" selected>' in pagina("fechada_salva")
    assert '<option value="sim" selected>' in pagina("prazo_vencido")  # vencida também é fechada


def test_comentario_vale_em_qualquer_campo(painel: Painel) -> None:
    assert painel.corrigir("usd", "nivel", "junior", "era estágio").status_code == 303
    linhas = painel.sql(
        "SELECT campo, valor_novo, comentario FROM correcao WHERE vaga_id = ?", painel.ids["usd"]
    )
    assert linhas == [("nivel", "junior", "era estágio")]
    erro = painel.corrigir("usd", "uf", "ZZ9", "meu comentário")
    assert erro.status_code == 422
    achou = re.search(r'<textarea[^>]*id="correcao-comentario-uf"[^>]*>(.*?)</textarea>', erro.text)
    assert achou is not None
    assert achou.group(1) == "meu comentário"


def test_corrigir_aplica_na_hora(painel: Painel) -> None:
    # 1) salário numa vaga em dólar: as `_brl` e a cotação mostrada são as novas
    resposta = painel.corrigir("usd", "salario", "USD 6.000 per month", "era 6 mil")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/vagas/{painel.ids['usd']}"
    texto = _texto(painel.detalhe("usd"))
    assert "US$ 6.000/mês" in texto
    assert "≈ R$ 33.900/mês · US$ 1 = R$ 5,65 (PTAX de 13/11)" in texto
    assert "US$ 5.000" not in texto
    colunas = painel.sql(
        "SELECT sal_mensal_min_brl, sal_cotacao_data FROM vaga WHERE id = ?", painel.ids["usd"]
    )
    assert colunas == [(33900, "2026-11-13")]
    # nos dois sentidos: salário vazio apaga o valor, e a tela já mostra isso
    painel.corrigir("usd", "salario", "")
    assert "Salário não informado" in _texto(painel.detalhe("usd"))
    # 2) correção que muda o encaixe: nota e `oculta_motivo` saem novos
    antes = painel.sql(
        "SELECT nota, oculta_motivo FROM encaixe WHERE vaga_id = ?", painel.ids["oculta_regra"]
    )
    assert antes == [(10, "modalidade")]
    assert painel.corrigir("oculta_regra", "modalidade", "remoto").status_code == 303
    depois = painel.sql(
        "SELECT nota, oculta_motivo FROM encaixe WHERE vaga_id = ?", painel.ids["oculta_regra"]
    )
    assert depois == [(33, None)]
    html = painel.detalhe("oculta_regra")
    assert "Oculta pela regra" not in html
    assert "Remoto" in _texto(html)


def test_correcao_fica_registrada_com_o_comentario(painel: Painel) -> None:
    painel.corrigir("usd", "outro", "titulo trocado", "comentário da pessoa")
    linhas = painel.sql(
        "SELECT campo, valor_novo, comentario FROM correcao WHERE vaga_id = ?", painel.ids["usd"]
    )
    assert linhas == [("outro", "titulo trocado", "comentário da pessoa")]


def test_correcao_vaga_inexistente_404_valor_invalido_422(painel: Painel) -> None:
    dados = {"campo": "uf", "valor_uf": "SP", "comentario": ""}
    assert painel.post("/vagas/9999/correcao", **dados).status_code == 404
    assert painel.post(f"/vagas/{GRANDE}/correcao", **dados).status_code == 404
    vaga = painel.ids["usd"]
    url = f"/vagas/{vaga}/correcao"
    for ruim in (
        {"campo": "titulo", "valor_titulo": "x"},  # campo que não se corrige
        {"campo": "nivel", "valor_nivel": "chefe"},  # fora da lista oferecida
        {"campo": "fechada", "valor_fechada": "talvez"},
        {"campo": "area"},  # sem valor
    ):
        assert painel.post(url, **ruim).status_code == 422, ruim
    # texto que a pessoa digitou e não vale: volta o formulário, com o que ela escreveu
    uf = painel.corrigir("usd", "uf", "ZZ9")
    assert uf.status_code == 422
    assert 'value="ZZ9"' in uf.text
    assert 'role="alert"' in uf.text
    sal = painel.corrigir("usd", "salario", "quase nada")
    assert sal.status_code == 422
    assert 'value="quase nada"' in sal.text
    assert painel.sql("SELECT COUNT(*) FROM correcao") == [(0,)]


def test_correcao_passa_o_dia_local_como_hoje(painel: Painel, fuso_de_sao_paulo: None) -> None:
    # 14/11 02:00 UTC é 13/11 23:00 em São Paulo: a cotação vale 7 dias a partir do dia LOCAL
    painel.app.state.relogio = RelogioFalso(datetime(2026, 11, 14, 2, 0, tzinfo=UTC))
    painel.sql("UPDATE cotacao SET data = '2026-11-06', venda = '5.50'")  # 7 dias antes de 13/11
    painel.corrigir("usd", "salario", "USD 6.000 per month")
    texto = _texto(painel.detalhe("usd"))
    assert "≈ R$ 33.000/mês · US$ 1 = R$ 5,50 (PTAX de 06/11)" in texto
    # controle: um dia mais velha já não vale, e a vaga fica só com o valor original
    painel.sql("UPDATE cotacao SET data = '2026-11-05'")
    painel.corrigir("usd", "salario", "USD 7.000 per month")
    texto = _texto(painel.detalhe("usd"))
    assert "US$ 7.000/mês" in texto
    assert "PTAX" not in texto


def _alerta(html: str) -> str:
    achou = re.search(r'role="alert"[^>]*>(.*?)</p>', html, re.S)
    assert achou is not None
    return html_lib.unescape(achou.group(1))


def test_valor_longo_e_comentario_longo_tem_mensagens_diferentes(painel: Painel) -> None:
    longo = "a" * 501
    valor = painel.corrigir("usd", "outro", longo)
    assert valor.status_code == 422
    assert "valor" in _alerta(valor.text)
    assert "comentário" not in _alerta(valor.text)
    comentario = painel.corrigir("usd", "outro", "certo", longo)
    assert comentario.status_code == 422
    assert "comentário" in _alerta(comentario.text)
    assert painel.sql("SELECT COUNT(*) FROM correcao") == [(0,)]


def test_erro_depois_de_gravar_nao_vira_422(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    rota = importlib.import_module("jobot.painel.rotas.detalhe")

    def quebra(*args: Any, **kwargs: Any) -> None:
        raise ValueError("reprocesso quebrou")

    monkeypatch.setattr(rota, "reprocessar_vaga", quebra)
    with pytest.raises(ValueError, match="reprocesso quebrou"):
        painel.corrigir("usd", "nivel", "junior")
    assert painel.sql("SELECT COUNT(*) FROM correcao") == [(1,)]  # a correção já estava guardada


def test_correcao_em_dialog_com_formulario_de_hoje(painel: Painel) -> None:
    vaga = painel.ids["usd"]
    resposta = painel.http.get(f"/vagas/{vaga}/correcao", headers={"HX-Request": "true"})
    assert resposta.status_code == 200
    html = resposta.text
    # só o sheet: sem a casca da página
    assert "<html" not in html
    assert "<aside" not in html
    abre = re.search(r"<dialog\b[^>]*>", html)
    assert abre is not None
    tag = abre.group(0)
    for classe in ("sheet", "vidro", "vidro-grande", "vidro-elevado"):
        assert re.search(rf'class="[^"]*\b{classe}\b', tag), classe
    assert 'aria-labelledby="correcao-titulo"' in tag
    assert 'id="correcao-titulo"' in html
    # o formulário de hoje: um por item, com os mesmos campos, ação e botão
    assert html.count(f'action="/vagas/{vaga}/correcao"') == 8
    for campo in ("area", "nivel", "modalidade", "contrato", "uf", "salario", "fechada", "outro"):
        assert f'name="valor_{campo}"' in html
        assert f'name="campo" value="{campo}"' in html
    assert html.count('name="comentario"') == 8
    # o pé do sheet: o botão de fechar, fora do corpo que rola
    corpo = re.search(r'<div class="sheet-corpo">(.*?)</div>\s*<footer', html, re.S)
    assert corpo is not None
    assert "data-fechar-sheet" not in corpo.group(1)
    pe = r"<footer\b[^>]*>\s*<button\b[^>]*data-fechar-sheet[^>]*>Fechar</button>"
    assert re.search(pe, html)
    assert "Vary" in resposta.headers and "HX-Request" in resposta.headers["Vary"]


def test_correcao_sem_htmx_segue_a_pagina_de_hoje(painel: Painel) -> None:
    resposta = painel.get(f"/vagas/{painel.ids['usd']}/correcao")
    assert resposta.status_code == 200
    assert "<html" in resposta.text
    assert "<dialog" not in re.sub(
        r'<dialog\b[^>]*\bid="(paleta|alerta-encerrar)".*?</dialog>', "", resposta.text, flags=re.S
    )
    assert 'class="painel correcoes"' in resposta.text


def test_restauracao_de_historico_do_htmx_recebe_a_pagina_inteira(painel: Painel) -> None:
    """Voltar no navegador (HX-History-Restore-Request) precisa da página toda."""
    cabecalhos = {"HX-Request": "true", "HX-History-Restore-Request": "true"}
    resposta = painel.http.get(f"/vagas/{painel.ids['usd']}/correcao", headers=cabecalhos)
    assert resposta.status_code == 200
    assert "<html" in resposta.text
    assert "<dialog" not in re.sub(
        r'<dialog\b[^>]*\bid="(paleta|alerta-encerrar)".*?</dialog>', "", resposta.text, flags=re.S
    )
    assert "HX-History-Restore-Request" in resposta.headers["Vary"]


def _regra(css: str, seletor: str) -> str:
    """O corpo da primeira regra cujo seletor é exatamente `seletor` (CSS plano, sem aninhar)."""
    achou = re.search(rf"(?:^|[}}/])\s*{re.escape(seletor)}\s*{{([^}}]*)}}", css)
    assert achou is not None, seletor
    return achou.group(1)


def test_sheet_estiliza_os_campos_que_a_pagina_hospedeira_nao_estiliza(painel: Painel) -> None:
    """O sheet entra em páginas sem o buscas.css: o detalhe.css cobre textarea e texto."""
    css = painel.http.get("/static/css/detalhe.css").text
    for seletor in (".sheet-corpo textarea", '.sheet-corpo input[type="text"]'):
        assert seletor in css, seletor
    regra = _regra(css, '.sheet-corpo input[type="text"],\n.sheet-corpo textarea')
    for declaracao in ("width: 100%", "border: 1px solid var(--borda)", "border-radius:"):
        assert declaracao in regra, declaracao


def test_sheet_fica_no_alto_e_nao_redefine_borda_nem_sombra_do_vidro(painel: Painel) -> None:
    css = painel.http.get("/static/css/detalhe.css").text
    regra = _regra(css, ".sheet")
    # `margin: auto` centra o <dialog> na vertical; o desenho pede o sheet no alto
    assert not re.search(r"margin:\s*auto\s*;", regra)
    assert "margin-block" in regra
    # borda e sombra do vidro são do base.css (inclusive o caminho sólido): a regra de base do
    # sheet só põe o raio; o vidro o enfeita dentro da media do caminho com transparência
    assert "border:" not in regra
    assert "box-shadow" not in regra


def test_sheet_tem_borda_base_sem_disputar_com_o_base_css(painel: Painel) -> None:
    """`<dialog>` traz `border: 3px solid`; fora dos blocos de media (contraste menor, navegador sem
    `prefers-reduced-transparency`) o sheet precisa de uma borda própria, de especificidade zero."""
    css = painel.http.get("/static/css/detalhe.css").text
    regra = _regra(css, ":where(.sheet)")
    assert "border: 1px solid var(--separador)" in regra


def test_link_da_correcao_abre_o_sheet_e_sem_js_leva_a_pagina(painel: Painel) -> None:
    html = painel.detalhe("usd")
    vaga = painel.ids["usd"]
    link = _ancora(html, f'href="/vagas/{vaga}/correcao"')
    assert f'hx-get="/vagas/{vaga}/correcao"' in link  # com JavaScript abre o sheet
    assert "data-correcao" in link
    assert 'class="correcao-slot"' in html  # onde o sheet entra


# ---------------------------------------------------------------- T286: linha do tempo e e-mail


@pytest.fixture
def fuso_menos_tres(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """TZ `<-03>3`: o dia mostrado é o local (E16); o fuso volta antes do último `tzset`."""
    monkeypatch.setenv("TZ", "<-03>3")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


COM_EMAIL = "Envie o currículo para rh@example.com."


def _descricao(painel: Painel, nome: str, texto: str) -> None:
    painel.sql("UPDATE vaga SET descricao_texto = ? WHERE id = ?", texto, painel.ids[nome])


def _href(ancora: str) -> str:
    achou = re.search(r'href="([^"]*)"', ancora)
    assert achou, ancora
    return html_lib.unescape(achou.group(1))


def _mailtos(html: str) -> list[str]:
    return [m for m in re.findall(r"<a\b[^>]*>", html) if 'href="mailto:' in m]


def _mailto(html: str) -> str:
    """O único link de e-mail da página."""
    achados = _mailtos(html)
    assert len(achados) == 1, achados
    return achados[0]


def test_linha_do_tempo(painel: Painel, fuso_menos_tres: None) -> None:
    vaga = painel.ids["usd"]
    painel.sql("UPDATE vaga SET primeira_vista_em = '2026-11-03T12:00:00+00:00' WHERE id = ?", vaga)
    with closing(abrir(painel.banco)) as con:
        acoes.mudar_status(con, vaga, "salva", datetime(2026, 11, 10, 12, 0, tzinfo=UTC))
        assert acoes.abriu_candidatura(con, vaga, datetime(2026, 11, 14, 12, 0, tzinfo=UTC))
        # 01:30 UTC de 17/11 ainda é 16/11 no fuso -03 (E16)
        sim = datetime(2026, 11, 17, 1, 30, tzinfo=UTC)
        assert acoes.responder_candidatura(con, vaga, True, sim) == "salva"
    achou = re.search(r'<section class="bloco passos".*?</section>', painel.detalhe("usd"), re.S)
    assert achou is not None
    assert "Linha do tempo" in _texto(achou.group(0))
    itens = [_texto(li).strip() for li in re.findall(r"<li>(.*?)</li>", achou.group(0), re.S)]
    assert itens == [
        "Vista em 03/11",
        "Abriu a candidatura em 14/11",
        "Salva em 10/11",
        "Candidatei em 16/11",
    ]


def test_email_vira_secundario_com_link_http(painel: Painel) -> None:
    _descricao(painel, "himalayas", COM_EMAIL)
    html = painel.detalhe("himalayas")
    assert _href(_ancora(html, 'class="primario"')) == (
        "https://himalayas.app/companies/beta/jobs/42/apply"
    )
    email = _mailto(html)
    assert 'class="secundario"' in email
    assert _href(email) == "mailto:rh@example.com?subject=Backend%20Engineer"


def test_email_vira_principal_sem_link_http(painel: Painel) -> None:
    _descricao(painel, "usd", COM_EMAIL)
    html = painel.detalhe("usd")
    vaga = painel.ids["usd"]
    principal = _ancora(html, 'class="primario"')
    assert _href(principal) == "mailto:rh@example.com?subject=Desenvolvedor%20Python"
    assert "Candidatar-se por e-mail" in _texto(html)
    assert len(_mailtos(html)) == 1  # sem o secundário repetido
    # a vaga na fonte continua no "Abrir no site" e na lista de fontes
    assert _href(_ancora(html, 'class="secundario"')) == f"https://exemplo.test/vagas/{vaga}"
    assert "via Remotive" in _texto(html)


def test_mailto_com_assunto_codificado(painel: Painel) -> None:
    _descricao(painel, "usd", COM_EMAIL)
    painel.sql("UPDATE vaga SET titulo = 'Dev & Ops São Paulo' WHERE id = ?", painel.ids["usd"])
    email = _mailto(painel.detalhe("usd"))
    partes = urlsplit(_href(email))
    assert partes.query == "subject=Dev%20%26%20Ops%20S%C3%A3o%20Paulo"
    assert parse_qs(partes.query) == {"subject": ["Dev & Ops São Paulo"]}


@pytest.mark.parametrize(
    "texto",
    [
        "Envie o currículo para rh@example.com?cc=outro@example.org",
        "Envie o currículo para rh@example.com&bcc=outro@example.org",
        "Envie o currículo para rh@example.com%0A",
        "Envie o currículo para rh%0A@example.com",
    ],
)
def test_mailto_sem_parametro_injetado(painel: Painel, texto: str) -> None:
    _descricao(painel, "usd", texto)
    assert "mailto:" not in painel.detalhe("usd")
    # controle na mesma montagem: endereço válido com gatilho vira mailto só com o subject
    _descricao(painel, "usd", COM_EMAIL)
    email = _mailto(painel.detalhe("usd"))
    partes = urlsplit(_href(email))
    assert (partes.scheme, partes.path) == ("mailto", "rh@example.com")
    assert set(parse_qs(partes.query)) == {"subject"}


def test_sem_email_fica_como_hoje(painel: Painel) -> None:
    """Guarda: sem endereço na descrição, nada de e-mail; o principal abre a vaga na fonte."""
    html = painel.detalhe("usd")
    assert "mailto:" not in html
    assert "data-copiar" not in html
    assert "email-candidatura" not in html
    vaga = painel.ids["usd"]
    assert _href(_ancora(html, 'class="primario"')) == f"https://exemplo.test/vagas/{vaga}"


def test_copiar_vem_hidden(painel: Painel) -> None:
    _descricao(painel, "usd", COM_EMAIL)
    html = painel.detalhe("usd")
    botao = re.search(r"<button\b[^>]*data-copiar[^>]*>([^<]*)</button>", html)
    assert botao is not None
    tag = botao.group(0)
    assert re.search(r"\shidden[\s>]", tag)
    assert 'type="button"' in tag
    assert 'data-copiar="rh@example.com"' in tag
    assert 'data-copiado="Endereço copiado."' in tag
    assert 'data-nao-copiou="Não deu para copiar. Selecione o endereço e copie."' in tag
    assert botao.group(1) == "Copiar endereço"
    # sem JavaScript o endereço continua à vista, com a região viva e o aviso ao lado
    texto = _texto(html)
    assert "Endereço para candidatura: rh@example.com" in texto
    assert "O joBot não envia nada: o e-mail sai do seu programa de e-mail." in texto
    assert re.search(r'data-copiar[^>]*>[^<]*</button>\s*<span role="status"></span>', html)


def test_email_tem_data_candidatura(painel: Painel) -> None:
    for nome in ("usd", "himalayas"):  # principal e secundário
        _descricao(painel, nome, COM_EMAIL)
        email = _mailto(painel.detalhe(nome))
        assert f'data-candidatura="/vagas/{painel.ids[nome]}/candidatura"' in email
        assert "target=" not in email  # o mailto abre o programa de e-mail, não uma aba
        assert 'aria-label="Candidatar-se por e-mail (abre o seu programa de e-mail)"' in email


class _Bloco(HTMLParser):
    """As tags de abertura dentro do elemento com `id` (ele incluído), contando os `div`."""

    def __init__(self, id_: str) -> None:
        super().__init__()
        self.id_ = id_
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.fundo = 0  # divs abertos dentro do bloco; 0 fora dele

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        dados = dict(attrs)
        if self.fundo == 0 and dados.get("id") == self.id_ and not self.tags:
            self.fundo = 1
            self.tags.append((tag, dados))
        elif self.fundo:
            self.tags.append((tag, dados))
            self.fundo += tag == "div"

    def handle_endtag(self, tag: str) -> None:
        if self.fundo and tag == "div":
            self.fundo -= 1


def _bloco(html: str, id_: str) -> list[tuple[str, dict[str, str | None]]]:
    leitor = _Bloco(id_)
    leitor.feed(html)
    assert leitor.tags, f"sem #{id_}"
    return leitor.tags


@pytest.mark.parametrize("onde", ["pagina", "lado"])
def test_detalhe_estado_escuta_a_vaga(painel: Painel, onde: str) -> None:
    vaga, busca = painel.ids["usd"], painel.ids["busca"]
    url = (
        f"/vagas/{vaga}?busca={busca}" if onde == "pagina" else f"/vagas?busca={busca}&vaga={vaga}"
    )
    html = painel.get(url).text
    assert html.count('id="estado-da-vaga"') == 1
    (_, raiz), *dentro = _bloco(html, "estado-da-vaga")
    voltar = {d.get("value") for t, d in dentro if t == "input" and d.get("name") == "voltar"}
    assert len(voltar) == 1  # o retorno da página, o mesmo nos forms
    assert raiz.get("hx-get") is not None
    assert {raiz.get("hx-get")} == voltar
    assert raiz.get("hx-trigger") == f"vaga-mudou-{vaga} from:body"
    assert raiz.get("hx-select") == "#estado-da-vaga"
    assert raiz.get("hx-swap") == "outerHTML"
    classes = {c for _, d in dentro for c in (d.get("class") or "").split()}
    assert {"situacao", "passos"} <= classes
    acoes_ = {d.get("action") for t, d in dentro if t == "form"}
    assert f"/vagas/{vaga}/status" in acoes_
    # o hx-select é herdado: filho com hx-* (o Ocultar do detalhe ao lado) o desliga
    for _, d in dentro:
        if any(k in d for k in ("hx-get", "hx-post")):
            assert d.get("hx-select") == "unset", d
