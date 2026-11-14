"""Rotas do detalhe da vaga e da correção (plano T46; D11, D12, D40, DP8)."""

import html as html_lib
import importlib
import re
import time
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import semear
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


@pytest.fixture
def fuso_sao_paulo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    yield
    monkeypatch.undo()  # volta o TZ antes do tzset: sem isso o fuso vaza para os outros testes
    time.tzset()


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
    assert "US$ 1 = R$ 5,65 (PTAX de 13/11) · ≈ R$ 28.250/mês" in texto


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
    assert "US$ 1 = R$ 5,65 (PTAX de 13/11) · ≈ R$ 33.900/mês" in texto
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


def test_correcao_passa_o_dia_local_como_hoje(painel: Painel, fuso_sao_paulo: None) -> None:
    # 14/11 02:00 UTC é 13/11 23:00 em São Paulo: a cotação vale 7 dias a partir do dia LOCAL
    painel.app.state.relogio = RelogioFalso(datetime(2026, 11, 14, 2, 0, tzinfo=UTC))
    painel.sql("UPDATE cotacao SET data = '2026-11-06', venda = '5.50'")  # 7 dias antes de 13/11
    painel.corrigir("usd", "salario", "USD 6.000 per month")
    texto = _texto(painel.detalhe("usd"))
    assert "US$ 1 = R$ 5,50 (PTAX de 06/11) · ≈ R$ 33.000/mês" in texto
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
