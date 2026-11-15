"""Rotas da tela de vagas: abas, filtros, ordem, destaques e ações da vaga (plano T45)."""

import json
import re
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from apoio.relogio import RelogioFalso
from apoio.semear import AGORA, inserir_vaga, semear
from jobot.banco import acoes
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.i18n import t
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47616
HX = {"HX-Request": "true"}
ABAS = [
    "destaques",
    "todas",
    "novas",
    "fecham_logo",
    "salvas",
    "candidatei",
    "programas",
    "ocultas",
]


class Painel:
    """Cliente do app sobre um banco semeado, com o relógio parado em `AGORA`."""

    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            self.ids = semear(con)
        app = criar_app(tmp_path, PORTA)
        app.state.relogio = RelogioFalso()
        self.http = TestClient(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)
        self.token: str = app.state.csrf

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def semear_mais(self, **campos: Any) -> int:
        with closing(abrir(self.banco)) as con:
            return inserir_vaga(con, **campos)

    def config(self, chave: str, valor: object) -> None:
        self.sql(
            "INSERT INTO config (chave, valor) VALUES (?, ?)"
            " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            chave,
            json.dumps(valor),
        )

    def get(self, url: str, **kw: Any) -> Any:
        return self.http.get(url, **kw)

    def post(self, url: str, **dados: str) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **dados})


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _cartoes(html: str) -> list[int]:
    return [int(n) for n in re.findall(r'\bid="vaga-(\d+)"', html)]


def _tag(html: str, id_: str) -> str:
    achou = re.search(rf'<[a-z]+\b[^>]*\bid="{re.escape(id_)}"[^>]*>', html)
    assert achou, f"sem elemento id={id_!r}"
    return achou.group(0)


def _atual(html: str) -> list[str]:
    """As abas marcadas com aria-current (só o `<nav class="abas">`, não o menu da casca)."""
    abas = re.search(r'<nav class="abas".*?</nav>', html, re.S)
    assert abas is not None
    return re.findall(r'<a\b[^>]*aria-current="page"[^>]*>', abas.group(0))


def test_raiz_vai_para_vagas_ou_para_a_primeira_execucao(painel: Painel) -> None:
    primeira = painel.get("/")
    assert (primeira.status_code, primeira.headers["location"]) == (303, "/primeira-execucao/1")
    painel.config("primeira_execucao_concluida", True)
    pronta = painel.get("/")
    assert (pronta.status_code, pronta.headers["location"]) == (303, "/vagas?aba=destaques")
    painel.config("destaques_ligados", False)
    assert painel.get("/").headers["location"] == "/vagas?aba=todas"


def test_oito_abas_e_so_a_atual_tem_aria_current(painel: Painel) -> None:
    html = painel.get("/vagas?aba=salvas").text
    assert [bool(re.search(rf'href="/vagas\?aba={a}[&"]', html)) for a in ABAS] == [True] * 8
    atual = _atual(html)
    assert len(atual) == 1
    assert "aba=salvas" in atual[0]


def test_sem_aba_abre_nos_destaques(painel: Painel) -> None:
    atual = _atual(painel.get("/vagas").text)
    assert len(atual) == 1
    assert "aba=destaques" in atual[0]


def test_destaques_desligado_some_a_aba_e_abre_em_todas(painel: Painel) -> None:
    painel.config("destaques_ligados", False)
    html = painel.get("/vagas").text
    assert "aba=destaques" not in html
    assert "aba=todas" in _atual(html)[0]
    assert "aba=todas" in _atual(painel.get("/vagas?aba=destaques").text)[0]


def test_abas_trazem_a_contagem(painel: Painel) -> None:
    html = painel.get("/vagas?aba=todas").text
    todas = re.search(r'<a\b[^>]*href="/vagas\?aba=todas[^"]*"[^>]*>(.*?)</a>', html, re.S)
    assert todas
    assert "7" in todas.group(1)


def test_chips_com_contagem_e_aria_pressed(painel: Painel) -> None:
    html = painel.get("/vagas?aba=todas").text
    remoto = _tag(html, "chip-modalidade-remoto")
    assert 'aria-pressed="false"' in remoto
    assert 'data-contagem="4"' in remoto
    assert 'data-contagem="2"' in _tag(html, "chip-modalidade-presencial")
    ligado = painel.get("/vagas?aba=todas&modalidade=remoto").text
    assert 'aria-pressed="true"' in _tag(ligado, "chip-modalidade-remoto")


def test_filtro_vai_para_a_url_e_a_url_reabre_igual(painel: Painel) -> None:
    ids = painel.ids
    html = painel.get("/vagas?aba=todas").text
    chip = _tag(html, "chip-modalidade-remoto")
    url = re.search(r'hx-get="([^"]+)"', chip)
    assert url
    destino = url.group(1).replace("&amp;", "&")
    assert "modalidade=remoto" in destino
    assert 'hx-push-url="true"' in chip
    pelo_chip = painel.get(destino, headers=HX)
    reaberta = painel.get(destino)
    quatro = [ids["usd"], ids["himalayas"], ids["nova"], ids["prazo_3_dias"]]
    assert sorted(_cartoes(reaberta.text)) == sorted(quatro)
    assert _cartoes(pelo_chip.text) == _cartoes(reaberta.text)
    # apertar de novo o chip que está ligado tira o filtro
    ligado = _tag(reaberta.text, "chip-modalidade-remoto")
    volta = re.search(r'hx-get="([^"]+)"', ligado)
    assert volta
    assert "modalidade" not in volta.group(1)


def test_htmx_recebe_so_o_miolo_e_a_volta_do_historico_recebe_a_pagina(painel: Painel) -> None:
    parcial = painel.get("/vagas?aba=todas", headers=HX)
    assert "<html" not in parcial.text
    assert _cartoes(parcial.text)
    historico = painel.get("/vagas?aba=todas", headers=HX | {"HX-History-Restore-Request": "true"})
    assert "<html" in historico.text
    assert "HX-Request" in parcial.headers["vary"]


def test_busca_de_texto_e_preservada_nos_links(painel: Painel) -> None:
    html = painel.get("/vagas?aba=todas&q=python").text
    assert sorted(_cartoes(html)) == sorted(
        [painel.ids["usd"], painel.ids["script"], painel.ids["prazo_3_dias"]]
    )
    assert "data-busca" in html
    assert "q=python" in _tag(html, "chip-modalidade-remoto")


@pytest.mark.parametrize(
    ("ordem", "esperado"),
    [
        ("encaixe", ["usd", "nova", "himalayas", "prazo_3_dias", "brl", "script", "trainee"]),
        ("recentes", ["nova", "usd", "brl", "himalayas", "script", "prazo_3_dias", "trainee"]),
        ("prazo", ["prazo_3_dias", "trainee", "usd", "brl", "himalayas", "script", "nova"]),
        ("salario", ["usd", "brl", "himalayas", "script", "nova", "prazo_3_dias", "trainee"]),
        ("empresa", ["brl", "himalayas", "script", "nova", "prazo_3_dias", "trainee", "usd"]),
    ],
)
def test_cinco_ordens(painel: Painel, ordem: str, esperado: list[str]) -> None:
    html = painel.get(f"/vagas?aba=todas&ordem={ordem}").text
    assert _cartoes(html) == [painel.ids[nome] for nome in esperado]
    assert "selected" in re.search(rf"<option[^>]*value=\"{ordem}\"[^>]*>", html).group(0)  # type: ignore[union-attr]


def test_carregar_mais(painel: Painel) -> None:
    for n in range(60):
        painel.semear_mais(titulo=f"Extra {n}", empresa=f"Extra SA {n}")
    primeira = painel.get("/vagas?aba=todas").text
    assert len(_cartoes(primeira)) == 50
    mais = re.search(r'hx-get="([^"]+)"', _tag(primeira, "mais-2"))
    assert mais
    assert "pagina=2" in mais.group(1)
    segunda = painel.get(mais.group(1).replace("&amp;", "&"), headers=HX)
    assert len(_cartoes(segunda.text)) == 17
    assert not set(_cartoes(primeira)) & set(_cartoes(segunda.text))
    assert 'id="mais-3"' not in segunda.text


def test_cartao_com_botao_de_salvar_so_pelo_teclado(painel: Painel) -> None:
    html = painel.get("/vagas?aba=todas").text
    vaga = painel.ids["nova"]
    form = re.search(rf'<form\b[^>]*action="/vagas/{vaga}/status"[^>]*>(.*?)</form>', html, re.S)
    assert form
    assert 'name="status" value="salva"' in form.group(1)
    assert 'type="submit"' in form.group(1)
    assert f'action="/vagas/{vaga}/ocultar"' in html


def test_via_fonte_com_link_em_toda_fonte_sem_olhar_credito(painel: Painel) -> None:
    # remotive tem credito_obrigatorio e github_issues não: as duas aparecem do mesmo jeito
    vaga = painel.ids["nova"]
    painel.sql(
        "INSERT INTO fonte (chave, leva) VALUES ('github_issues', 'A') ON CONFLICT DO NOTHING"
    )
    painel.sql(
        "INSERT INTO ocorrencia (vaga_id, fonte, url, coletada, primeira_vista_em, ultima_vista_em)"
        " VALUES (?, 'github_issues', 'https://github.test/issues/9', '{}', ?, ?)",
        vaga,
        AGORA.isoformat(),
        AGORA.isoformat(),
    )
    html = painel.get("/vagas?aba=todas").text
    cartao = html.split(f'id="vaga-{vaga}"')[1].split("</article>")[0]
    links = re.findall(r"<a\b[^>]*>", cartao)
    fontes = [x for x in links if "exemplo.test" in x or "github.test" in x]
    assert len(fontes) == 2
    for tag in fontes:
        assert 'rel="noopener noreferrer"' in tag
        assert 'target="_blank"' in tag
        assert "nofollow" not in tag
    assert "via Remotive" in cartao
    assert "via GitHub Issues" in cartao


def test_link_de_fonte_que_nao_e_http_nao_vira_href(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    painel.sql(
        "UPDATE ocorrencia SET url = 'javascript:alert(1)' WHERE vaga_id = ?",
        vaga,
    )
    assert "javascript:" not in painel.get("/vagas?aba=todas").text


def test_texto_de_vaga_sai_escapado(painel: Painel) -> None:
    vaga = painel.semear_mais(titulo="<script>alert(1)</script>", empresa="<b>Ruim</b> SA")
    html = painel.get("/vagas?aba=todas&ordem=recentes").text
    assert f'id="vaga-{vaga}"' in html
    assert "<script>alert(1)" not in html
    assert "<b>Ruim" not in html
    assert "&lt;script&gt;alert(1)" in html


def test_salario_em_dolar_mostra_cotacao_e_reais(painel: Painel) -> None:
    html = painel.get("/vagas?aba=todas").text
    assert "US$ 5.000/mês" in html
    assert "≈ R$ 28.250/mês · US$ 1 = R$ 5,65 (PTAX de 13/11)" in html
    assert "R$ 8.000/mês" in html


def _cartao_html(html: str, vaga: int) -> str:
    achou = re.search(rf'id="vaga-{vaga}".*?</article>', html, re.S)
    assert achou, f"sem cartão da vaga {vaga}"
    return achou.group(0)


CONVERTIDO_EUR = (
    r"<strong>US\$ 5\.000/mês</strong>\s*"
    r'<small class="convertido">≈ € 4\.520/mês · US\$ 1 = € 0,904 \(PTAX de 12/11\)</small>'
)


def _em_euro(painel: Painel) -> None:
    """Moeda de exibição EUR, com a cotação de 12/11 (a do USD é de 13/11)."""
    painel.config("moeda_exibicao", "EUR")
    painel.sql(
        "INSERT INTO cotacao (moeda, data, venda, buscada_em)"
        " VALUES ('EUR', '2026-11-12', '6.25', ?)",
        AGORA.isoformat(),
    )


def test_valor_convertido_fica_em_linha_propria_no_cartao(painel: Painel) -> None:
    _em_euro(painel)
    cartao = _cartao_html(painel.get("/vagas?aba=todas").text, painel.ids["usd"])
    assert re.search(CONVERTIDO_EUR, cartao)
    assert "em-reais" not in cartao


def test_valor_convertido_vale_no_carregar_mais(painel: Painel) -> None:
    _em_euro(painel)
    for n in range(60):
        painel.semear_mais(
            titulo=f"Extra {n}",
            empresa=f"Extra SA {n}",
            sal_moeda="USD",
            sal_min=500000,
            sal_periodo="mes",
            sal_mensal_min=500000,
            sal_mensal_min_brl=28250,
            sal_cotacao_data="2026-11-13",
            sal_plausivel=1,
        )
    primeira = painel.get("/vagas?aba=todas").text
    segunda = painel.get(_hx_get(primeira, "mais-2"), headers=HX).text
    assert re.search(CONVERTIDO_EUR, segunda)
    assert "≈ R$" not in segunda


def test_valor_convertido_vale_no_cartao_devolvido_pela_acao(painel: Painel) -> None:
    _em_euro(painel)
    resposta = painel.http.post(
        f"/vagas/{painel.ids['usd']}/status",
        data={CAMPO_CSRF: painel.token, "status": "salva", "voltar": "/vagas"},
        headers=HX,
    )
    assert resposta.status_code == 200
    assert re.search(CONVERTIDO_EUR, resposta.text)


def test_vaga_sem_salario_diz_nao_informado(painel: Painel) -> None:
    """Desenho 13.4: sem salário ou implausível o cartão diz 'não informado'; com salário, não."""
    sem = painel.semear_mais(titulo="Sem salário")
    implausivel = painel.semear_mais(
        titulo="Salário absurdo", sal_moeda="BRL", sal_min=99999900, sal_plausivel=0
    )
    html = painel.get("/vagas?aba=todas&ordem=recentes").text
    marca = '<p class="salario nao-informado">Salário não informado</p>'
    assert marca in _cartao_html(html, sem)
    assert marca in _cartao_html(html, implausivel)
    assert marca not in _cartao_html(html, painel.ids["brl"])
    en = painel.get("/vagas?aba=todas&ordem=recentes", headers={"Accept-Language": "en"}).text
    assert "Salary not listed" in _cartao_html(en, sem)


def test_parametro_invalido_cai_no_padrao(painel: Painel) -> None:
    """RF2: link velho ou torto dá 200 e a lista padrão, nunca 422 nem 500."""
    padrao = _cartoes(painel.get("/vagas?aba=todas").text)
    assert padrao
    for query in (
        "pagina=abc",
        "pagina=0",
        "pagina=-5",
        "pagina=999999999999999999999",
        "ordem=xyz",
        "busca=999999",
        "busca=abc",
        "ordem=xyz&pagina=abc&busca=999999",
    ):
        resposta = painel.get(f"/vagas?aba=todas&{query}")
        assert resposta.status_code == 200, query
        assert _cartoes(resposta.text) == padrao, query
    inicial = _cartoes(painel.get("/vagas").text)
    for query in ("aba=nada", "aba=", "aba=TODAS", "aba=todas&aba=nada", "pagina=abc"):
        resposta = painel.get(f"/vagas?{query}")
        assert resposta.status_code == 200, query
    assert _cartoes(painel.get("/vagas?aba=nada").text) == inicial
    desconhecido = painel.get("/vagas?aba=todas&area=nao-existe&uf=%00&q=%22%00")
    assert desconhecido.status_code == 200
    assert _cartoes(desconhecido.text) == []


def test_destaques_so_vagas_abertas_nao_ocultas_e_novas(painel: Painel) -> None:
    ids = painel.ids
    recente = (AGORA - timedelta(hours=3)).isoformat()
    base: dict[str, Any] = {"primeira_vista_em": recente}
    boa = painel.semear_mais(titulo="Boa", empresa="Boa SA", **base)
    salva = painel.semear_mais(titulo="Salva", empresa="Salva SA", status="salva", **base)
    fechada = painel.semear_mais(
        titulo="Fechada", empresa="Fechada SA", fechada_em=AGORA.isoformat(), **base
    )
    vencida = painel.semear_mais(titulo="Vencida", empresa="Vencida SA", prazo="2026-11-01", **base)
    manual = painel.semear_mais(titulo="Manual", empresa="Manual SA", oculta_manual=1, **base)
    por_regra = painel.semear_mais(titulo="Regra", empresa="Regra SA", **base)
    antiga = painel.semear_mais(
        titulo="Antiga",
        empresa="Antiga SA",
        primeira_vista_em=(AGORA - timedelta(hours=30)).isoformat(),
    )
    painel.sql(
        "INSERT INTO encaixe (busca_id, vaga_id, nota, nivel, motivos, oculta_motivo)"
        " VALUES (?, ?, 99, 'bom', '[]', 'nivel')",
        ids["busca"],
        por_regra,
    )
    visiveis = _cartoes(painel.get("/vagas?aba=destaques").text)
    assert boa in visiveis
    assert ids["nova"] in visiveis
    for fora in (salva, fechada, vencida, manual, por_regra, antiga):
        assert fora not in visiveis
    # as vagas antigas do conjunto fechado (mais de 24 h) também não entram
    assert ids["usd"] not in visiveis


def test_destaques_uma_por_empresa_com_a_maior_nota(painel: Painel) -> None:
    recente = (AGORA - timedelta(hours=2)).isoformat()
    fraca = painel.semear_mais(titulo="Fraca", empresa="Mesma SA", primeira_vista_em=recente)
    forte = painel.semear_mais(titulo="Forte", empresa="mesma sa", primeira_vista_em=recente)
    for vaga, nota in ((fraca, 20), (forte, 95)):
        painel.sql(
            "INSERT INTO encaixe (busca_id, vaga_id, nota, nivel, motivos)"
            " VALUES (?, ?, ?, 'bom', '[]')",
            painel.ids["busca"],
            vaga,
            nota,
        )
    visiveis = _cartoes(painel.get("/vagas?aba=destaques").text)
    assert forte in visiveis
    assert fraca not in visiveis
    assert visiveis[0] == forte


def test_destaques_respeita_o_n_da_configuracao(painel: Painel) -> None:
    for n in range(4):
        painel.semear_mais(
            titulo=f"Hoje {n}",
            empresa=f"Hoje SA {n}",
            primeira_vista_em=(AGORA - timedelta(hours=1 + n)).isoformat(),
        )
    assert len(_cartoes(painel.get("/vagas?aba=destaques").text)) == 5
    painel.config("destaques_n", 2)
    assert len(_cartoes(painel.get("/vagas?aba=destaques").text)) == 2


def test_sem_preferencia_mostra_o_pedido_e_destaques_por_data(painel: Painel) -> None:
    com = painel.get("/vagas?aba=todas").text
    assert 'data-aviso="sem-criterio"' not in com
    painel.sql("DELETE FROM busca")
    velha = painel.semear_mais(
        titulo="Velha",
        empresa="Velha SA",
        primeira_vista_em=(AGORA - timedelta(hours=3)).isoformat(),
        publicada_em=(AGORA - timedelta(hours=10)).isoformat(),
    )
    nova = painel.semear_mais(
        titulo="Nova",
        empresa="Nova Ltda",
        primeira_vista_em=(AGORA - timedelta(hours=2)).isoformat(),
        publicada_em=(AGORA - timedelta(hours=5)).isoformat(),
    )
    lista = painel.get("/vagas?aba=todas").text
    assert 'data-aviso="sem-criterio"' in lista
    assert "selected" in re.search(r'<option[^>]*value="recentes"[^>]*>', lista).group(0)  # type: ignore[union-attr]
    destaques = painel.get("/vagas?aba=destaques").text
    assert 'data-aviso="sem-criterio"' in destaques
    assert _cartoes(destaques)[:2] == [nova, velha]


def test_busca_sem_nenhum_criterio_tambem_pede_preferencias(painel: Painel) -> None:
    painel.sql("UPDATE busca SET cargos = '[]', modalidades = '[]'")
    assert 'data-aviso="sem-criterio"' in painel.get("/vagas?aba=todas").text


@pytest.mark.parametrize("acao", ["status", "ocultar", "mostrar"])
def test_acao_sem_csrf_403(painel: Painel, acao: str) -> None:
    vaga = painel.ids["nova"]
    resposta = painel.http.post(f"/vagas/{vaga}/{acao}", data={"status": "salva"})
    assert resposta.status_code == 403
    assert painel.sql("SELECT status, oculta_manual FROM vaga WHERE id = ?", vaga) == [("nova", 0)]


@pytest.mark.parametrize("acao", ["status", "ocultar", "mostrar"])
def test_acao_em_vaga_inexistente_404(painel: Painel, acao: str) -> None:
    existente = painel.post(f"/vagas/{painel.ids['nova']}/{acao}", status="salva")
    assert existente.status_code == 303  # a rota existe: só o id muda o resultado
    resposta = painel.post(f"/vagas/999999/{acao}", status="salva")
    assert resposta.status_code == 404
    assert painel.sql("SELECT COUNT(*) FROM evento WHERE vaga_id = 999999") == [(0,)]


@pytest.mark.parametrize("acao", ["status", "ocultar", "mostrar"])
@pytest.mark.parametrize("vaga", ["99999999999999999999", str(2**63), "0", "-1"])
def test_acao_com_id_fora_da_faixa_do_banco_nao_da_500(
    painel: Painel, acao: str, vaga: str
) -> None:
    """D12: id que o SQLite não guarda (acima de 2**63-1) é 404 ou 422, nunca 500."""
    resposta = painel.post(f"/vagas/{vaga}/{acao}", status="salva")
    assert resposta.status_code in (404, 422)
    assert painel.sql("SELECT COUNT(*) FROM evento") == [(0,)]


@pytest.mark.parametrize("acao", ["status", "ocultar", "mostrar"])
def test_vaga_com_id_que_nao_e_numero_422(painel: Painel, acao: str) -> None:
    assert painel.post(f"/vagas/abc/{acao}", status="salva").status_code == 422


@pytest.mark.parametrize("acao", ["ocultar", "mostrar"])
def test_mostrar_e_ocultar_valor_invalido_422(
    painel: Painel, monkeypatch: pytest.MonkeyPatch, acao: str
) -> None:
    """D40: o `ValueError` de `acoes.ocultar` e de `acoes.mostrar` vira 422, uma rota por vez."""

    def recusa(*_: object) -> None:
        raise ValueError("estado inválido")

    monkeypatch.setattr(acoes, acao, recusa)
    vaga = painel.ids["nova"]  # visível: a rota /mostrar chama `acoes.mostrar`
    resposta = painel.post(f"/vagas/{vaga}/{acao}")
    assert resposta.status_code == 422
    # T150: o texto da tela sai do status, nunca do `str(erro)`
    assert "estado inválido" not in resposta.text
    assert str(escape(t("pt", "erro.invalido.texto"))) in resposta.text
    assert painel.sql("SELECT COUNT(*) FROM evento") == [(0,)]


def test_status_invalido_ou_ausente_422_e_nada_grava(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    assert painel.post(f"/vagas/{vaga}/status", status="xyz").status_code == 422
    assert painel.post(f"/vagas/{vaga}/status", status="").status_code == 422
    assert painel.post(f"/vagas/{vaga}/status").status_code == 422
    assert painel.sql("SELECT status FROM vaga WHERE id = ?", vaga) == [("nova",)]
    assert painel.sql("SELECT COUNT(*) FROM evento") == [(0,)]


def test_salvar_e_mudar_status_no_cartao(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    resposta = painel.http.post(
        f"/vagas/{vaga}/status",
        data={CAMPO_CSRF: painel.token, "status": "salva", "voltar": "/vagas?aba=novas"},
        headers=HX,
    )
    assert resposta.status_code == 200
    assert "<html" not in resposta.text
    assert "Salva" in resposta.text
    assert 'name="status" value="candidatei"' in resposta.text
    assert painel.sql("SELECT status FROM vaga WHERE id = ?", vaga) == [("salva",)]
    painel.post(f"/vagas/{vaga}/status", status="candidatei")
    desfazer = painel.post(f"/vagas/{vaga}/status", status="salva")
    assert desfazer.status_code == 303
    eventos = painel.sql("SELECT acao, de, para FROM evento WHERE vaga_id = ? ORDER BY id", vaga)
    assert eventos == [
        ("salvou", "nova", "salva"),
        ("mudou_status", "salva", "candidatei"),
        ("desfez", "candidatei", "salva"),
    ]


def test_acao_sem_htmx_volta_para_a_pagina(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    resposta = painel.post(f"/vagas/{vaga}/status", status="salva", voltar="/vagas?aba=salvas&q=x")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/vagas?aba=salvas&q=x"
    fora = painel.post(f"/vagas/{vaga}/status", status="nova", voltar="https://evil.test/")
    assert fora.headers["location"] == "/"


def test_ocultar_e_trazer_de_volta(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    assert painel.get("/vagas?aba=ocultas").text.count(f'id="vaga-{vaga}"') == 0
    oculta = painel.http.post(
        f"/vagas/{vaga}/ocultar", data={CAMPO_CSRF: painel.token, "voltar": "/vagas"}, headers=HX
    )
    assert oculta.status_code == 200
    assert f'action="/vagas/{vaga}/mostrar"' in oculta.text
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(1,)]
    assert vaga in _cartoes(painel.get("/vagas?aba=ocultas").text)
    assert vaga not in _cartoes(painel.get("/vagas?aba=todas").text)
    volta = painel.http.post(f"/vagas/{vaga}/mostrar", data={CAMPO_CSRF: painel.token}, headers=HX)
    assert volta.status_code == 200
    assert f'action="/vagas/{vaga}/ocultar"' in volta.text
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(0,)]
    assert painel.sql("SELECT acao FROM evento WHERE vaga_id = ? ORDER BY id", vaga) == [
        ("ocultou",),
        ("desfez",),
    ]


def test_mostrar_mesmo_assim_numa_vaga_oculta_por_regra(painel: Painel) -> None:
    vaga = painel.ids["oculta_regra"]
    assert vaga in _cartoes(painel.get("/vagas?aba=ocultas").text)
    resposta = painel.post(f"/vagas/{vaga}/mostrar")
    assert resposta.status_code == 303
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(-1,)]
    assert vaga in _cartoes(painel.get("/vagas?aba=todas").text)
    assert vaga not in _cartoes(painel.get("/vagas?aba=ocultas").text)


def test_cartao_de_vaga_oculta_oferece_trazer_de_volta(painel: Painel) -> None:
    html = painel.get("/vagas?aba=ocultas").text
    assert f'action="/vagas/{painel.ids["oculta_manual"]}/mostrar"' in html
    assert f'action="/vagas/{painel.ids["oculta_regra"]}/mostrar"' in html


def test_motivo_do_encaixe_aparece_com_texto_para_leitor_de_tela(painel: Painel) -> None:
    painel.sql(
        "UPDATE encaixe SET motivos = ? WHERE vaga_id = ?",
        json.dumps([{"chave": "encaixe.cargo_titulo", "params": {"palavra": "python"}}]),
        painel.ids["usd"],
    )
    html = painel.get("/vagas?aba=todas").text
    cartao = html.split(f'id="vaga-{painel.ids["usd"]}"')[1].split("</article>")[0]
    assert "Cargo no título: python" in cartao
    assert "Bom" in cartao


def test_motivo_com_chave_desconhecida_ou_parametro_faltando_nao_derruba(painel: Painel) -> None:
    painel.sql(
        "UPDATE encaixe SET motivos = ? WHERE vaga_id = ?",
        json.dumps([{"chave": "encaixe.cargo_titulo", "params": {}}]),
        painel.ids["usd"],
    )
    assert painel.get("/vagas?aba=todas").status_code == 200


def test_banco_sem_vagas_nem_busca_pede_as_preferencias(tmp_path: Path) -> None:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
    app = criar_app(tmp_path, PORTA)
    http = TestClient(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)
    resposta = http.get("/vagas")
    assert resposta.status_code == 200
    assert 'data-aviso="sem-criterio"' in resposta.text


# ---- filtros novos (plano T168) ----

_OITO = (
    "excluir=cobol&cidade=sao&empresa=zeta&sal_de=1&sal_ate=99999&sem_salario=1"
    "&pais=PT&publicada=7d"
)
_SAL_SP = {
    "uf": "SP",
    "cidade": "São Paulo",
    "sal_moeda": "BRL",
    "sal_min": 900000,
    "sal_periodo": "mes",
    "sal_mensal_min": 900000,
    "sal_mensal_min_brl": 9000,
    "sal_plausivel": 1,
}


def _hx_get(html: str, id_: str) -> str:
    achou = re.search(r'hx-get="([^"]+)"', _tag(html, id_))
    assert achou, f"{id_} sem hx-get"
    return achou.group(1).replace("&amp;", "&")


def _input(html: str, nome: str) -> str:
    achou = re.search(rf'<input\b[^>]*\bname="{nome}"[^>]*>', html)
    assert achou, f"sem input {nome}"
    return achou.group(0)


def test_parametros_novos_vao_e_voltam_na_url(painel: Painel) -> None:
    html = painel.get(f"/vagas?aba=todas&{_OITO}").text
    for nome, valor in (
        ("excluir", "cobol"),
        ("cidade", "sao"),
        ("empresa", "zeta"),
        ("sal_de", "1"),
        ("sal_ate", "99999"),
    ):
        assert f'value="{valor}"' in _input(html, nome), nome
    # o chip de outro valor do mesmo grupo troca só o dele e leva os outros sete campos
    trocado = _hx_get(html, "chip-publicada-30d")
    ligado = _hx_get(html, "chip-pais-PT")
    for url, faltando in ((trocado, "publicada=30d"), (ligado, "publicada=7d")):
        for parte in _OITO.split("&"):
            if parte.startswith(("publicada=", "pais=")):
                continue
            assert parte in url, (url, parte)
        assert faltando in url
    assert "pais=PT" in trocado
    assert "pais=" not in ligado


def test_clicar_num_chip_mantem_os_campos_de_mais_filtros(painel: Painel) -> None:
    painel.semear_mais(titulo="Vaga SP", modalidade="remoto", **_SAL_SP)
    html = painel.get("/vagas?aba=todas&sal_de=7000&cidade=sao").text
    url = _hx_get(html, "chip-modalidade-remoto")
    assert "sal_de=7000" in url
    assert "cidade=sao" in url


def test_url_das_abas_mantem_os_campos_novos(painel: Painel) -> None:
    html = painel.get(
        "/vagas?aba=todas&sal_de=7000&cidade=sao&excluir=cobol&modalidade=remoto"
    ).text
    abas = re.search(r'<nav class="abas".*?</nav>', html, re.S)
    assert abas
    links = re.findall(r'<a\b[^>]*\bhref="([^"]+)"', abas.group(0))
    assert len(links) == 8
    for link in links:
        for parte in ("sal_de=7000", "cidade=sao", "excluir=cobol"):
            assert parte in link, (link, parte)
        assert "modalidade" not in link


def test_sem_salario_vai_nos_campos_ocultos(painel: Painel) -> None:
    oculto = '<input type="hidden" name="sem_salario" value="1">'
    assert oculto in painel.get("/vagas?aba=todas&sal_de=1&sem_salario=1").text
    assert oculto not in painel.get("/vagas?aba=todas&sal_de=1").text


def test_carregar_mais_mantem_os_filtros_novos(painel: Painel) -> None:
    com = [painel.semear_mais(titulo=f"Legado cobol {n}", empresa=f"Banco {n}") for n in range(60)]
    for n in range(60):
        painel.semear_mais(titulo=f"Moderna {n}", empresa=f"Startup {n}")
    controle = painel.get("/vagas?aba=todas&q=cobol&ordem=recentes").text
    assert set(_cartoes(controle)) <= set(com)
    assert len(_cartoes(controle)) == 50
    primeira = painel.get("/vagas?aba=todas&excluir=cobol").text
    assert len(_cartoes(primeira)) == 50
    assert not set(_cartoes(primeira)) & set(com)
    mais = _hx_get(primeira, "mais-2")
    assert "excluir=cobol" in mais
    segunda = painel.get(mais, headers=HX)
    assert len(_cartoes(segunda.text)) == 17
    assert not set(_cartoes(segunda.text)) & set(com)


def test_mais_filtros_fechado_sem_filtro_e_aberto_com_contador(painel: Painel) -> None:
    fechado = painel.get("/vagas?aba=todas").text
    assert '<details class="mais-filtros">' in fechado
    assert "<summary>Mais filtros</summary>" in fechado
    aberto = painel.get("/vagas?aba=todas&cidade=sao&sal_de=7000").text
    assert '<details class="mais-filtros" open>' in aberto
    assert "<summary>Mais filtros (2)</summary>" in aberto


@pytest.mark.parametrize(
    "torto",
    [
        "sal_de=abc",
        "sal_de=-5",
        "sal_de=0",
        "sal_de=10000000000000",
        "sem_salario=2",
        "pais=xx",
        "pais=ZZ",
        "publicada=1h",
        "cidade=%00",
        "excluir=%00",
        "empresa=%00",
        "sal_de=" + "9" * 5000,
    ],
)
def test_parametros_novos_tortos_caem_no_padrao(painel: Painel, torto: str) -> None:
    padrao = _cartoes(painel.get("/vagas?aba=todas").text)
    assert padrao
    resposta = painel.get(f"/vagas?aba=todas&{torto}")
    assert resposta.status_code == 200
    assert _cartoes(resposta.text) == padrao


def test_sal_de_maior_que_sal_ate_troca(painel: Painel) -> None:
    certo = _cartoes(painel.get("/vagas?aba=todas&sal_de=7000&sal_ate=9000").text)
    assert certo == [painel.ids["brl"]]
    assert _cartoes(painel.get("/vagas?aba=todas&sal_de=9000&sal_ate=7000").text) == certo


def test_salario_enorme_nao_da_500(painel: Painel) -> None:
    painel.config("moeda_exibicao", "USD")
    painel.sql("UPDATE cotacao SET venda = '99999999.9999' WHERE moeda = 'USD'")
    resposta = painel.get("/vagas?aba=todas&sal_de=1000000000000")
    assert resposta.status_code == 200
    assert _cartoes(resposta.text) == []


def test_aviso_sem_salario_e_mostrar_tambem(painel: Painel) -> None:
    ids = painel.ids
    html = painel.get("/vagas?aba=todas&sal_de=1").text
    assert "Vagas sem salário que ficaram de fora: 5." in html
    assert ids["himalayas"] not in _cartoes(html)
    achou = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>Mostrar também</a>', html)
    assert achou
    seguido = painel.get(achou.group(1).replace("&amp;", "&"))
    assert "sem_salario=1" in achou.group(1)
    assert ids["himalayas"] in _cartoes(seguido.text)
    assert len(_cartoes(seguido.text)) == 7


def test_avisos_so_com_n_maior_que_zero(painel: Painel) -> None:
    assert "ficaram de fora" in painel.get("/vagas?aba=todas&sal_de=1").text
    assert "ficaram de fora" not in painel.get("/vagas?aba=todas&sal_de=1&sem_salario=1").text
    sem_fora = painel.get("/vagas?aba=todas&sal_de=1&empresa=agil")
    assert _cartoes(sem_fora.text) == [painel.ids["brl"]]
    assert "ficaram de fora" not in sem_fora.text


def test_aviso_sem_valor_convertido(painel: Painel) -> None:
    painel.config("conversao_moeda_ligada", False)
    painel.sql(
        "UPDATE vaga SET sal_mensal_min_brl = NULL, sal_cotacao_data = NULL WHERE id = ?",
        painel.ids["usd"],
    )
    html = painel.get("/vagas?aba=todas&sal_de=1").text
    assert "Vagas em outra moeda, sem valor convertido, que ficaram de fora: 1." in html
    assert "Ligue a conversão de moeda em Configurações" in html


def test_aviso_so_moeda_com_conversao_desligada(painel: Painel) -> None:
    painel.config("moeda_exibicao", "EUR")
    painel.config("conversao_moeda_ligada", False)
    html = painel.get("/vagas?aba=todas&sal_de=1").text
    assert "Com a conversão desligada, o filtro de salário só olha vagas pagas em EUR." in html
    assert "Salário de" in html
    assert "EUR por mês" in html


def test_aviso_sem_cotacao_da_moeda(painel: Painel) -> None:
    painel.config("moeda_exibicao", "EUR")
    sem = _cartoes(painel.get("/vagas?aba=todas").text)
    html = painel.get("/vagas?aba=todas&sal_de=1")
    msg = (
        "Ainda não temos a cotação de EUR; o filtro de salário fica desligado até a próxima busca."
    )
    assert msg in html.text
    assert _cartoes(html.text) == sem  # sem cotação o filtro não corta nada
    assert "ficaram de fora" not in html.text


def test_chip_de_pais_com_nome_na_lingua_da_tela(painel: Painel) -> None:
    painel.semear_mais(titulo="Vaga na Alemanha", pais="DE")
    pt = painel.get("/vagas?aba=todas").text
    en = painel.get("/vagas?aba=todas", headers={"Accept-Language": "en"}).text
    chip = r'<button[^>]*id="chip-pais-DE"[^>]*>(.*?)</button>'
    achou_pt, achou_en = re.search(chip, pt, re.S), re.search(chip, en, re.S)
    assert achou_pt
    assert achou_en
    assert achou_pt.group(1).strip().startswith("Alemanha")
    assert achou_en.group(1).strip().startswith("Germany")
    assert 'data-contagem="1"' in _tag(pt, "chip-pais-DE")


def test_chips_publicada_na_ordem_fixa(painel: Painel) -> None:
    for horas in (2, 72, 24 * 20):
        painel.semear_mais(
            titulo=f"Zzmarca {horas}",
            publicada_em=(AGORA - timedelta(hours=horas)).isoformat(),
            primeira_vista_em=(AGORA - timedelta(days=60)).isoformat(),
        )
    html = painel.get("/vagas?aba=todas&q=zzmarca").text
    ids = re.findall(r'\bid="chip-publicada-([^"]+)"', html)
    assert ids == ["24h", "7d", "30d"]
    esperado = {"24h": ("24 h", "1"), "7d": ("7 dias", "2"), "30d": ("30 dias", "3")}
    for chave, (texto, n) in esperado.items():
        botao = re.search(
            rf'<button[^>]*id="chip-publicada-{chave}"[^>]*>(.*?)</button>', html, re.S
        )
        assert botao
        assert botao.group(1).strip().startswith(texto)
        assert f'data-contagem="{n}"' in _tag(html, f"chip-publicada-{chave}")


def test_cidade_sem_cidade_no_local_responde_200(painel: Painel) -> None:
    resposta = painel.get("/vagas?aba=todas&cidade=sao")
    assert resposta.status_code == 200
    assert _cartoes(resposta.text) == []
    painel.semear_mais(titulo="Vaga SP", **_SAL_SP)
    assert len(_cartoes(painel.get("/vagas?aba=todas&cidade=sao").text)) == 1


@pytest.mark.parametrize("campo", ["pagina", "busca", "sal_ate", "sal_de"])
def test_numero_com_milhares_de_digitos_nao_da_500(painel: Painel, campo: str) -> None:
    padrao = _cartoes(painel.get("/vagas?aba=todas").text)
    assert padrao
    resposta = painel.get(f"/vagas?aba=todas&{campo}=" + "9" * 5000)
    assert resposta.status_code == 200
    assert _cartoes(resposta.text) == padrao


@pytest.mark.parametrize("venda", ["NaN", "0", "-1"])
def test_cotacao_estragada_vale_como_sem_cotacao(painel: Painel, venda: str) -> None:
    painel.config("moeda_exibicao", "USD")
    painel.sql("UPDATE cotacao SET venda = ? WHERE moeda = 'USD'", venda)
    sem = _cartoes(painel.get("/vagas?aba=todas").text)
    resposta = painel.get("/vagas?aba=todas&sal_de=1")
    assert resposta.status_code == 200
    assert "Ainda não temos a cotação de USD" in resposta.text
    assert _cartoes(resposta.text) == sem


def test_aviso_de_salario_nao_aparece_nos_destaques(painel: Painel) -> None:
    painel.config("moeda_exibicao", "EUR")
    assert "Ainda não temos a cotação de EUR" in painel.get("/vagas?aba=todas&sal_de=1").text
    destaques = painel.get("/vagas?aba=destaques&sal_de=1")
    assert destaques.status_code == 200
    assert "Ainda não temos a cotação" not in destaques.text
    assert "ficaram de fora" not in destaques.text


def test_campos_de_texto_novos_saem_escapados(painel: Painel) -> None:
    painel.semear_mais(titulo="Vaga SP", modalidade="remoto", **_SAL_SP)
    html = painel.get(
        "/vagas",
        params={"aba": "todas", "cidade": '"><script>x</script>', "empresa": 'a"b', "q": "vaga"},
    ).text
    assert "<script>x" not in html
    assert 'value=""><script>' not in html
    assert "&#34;&gt;&lt;script&gt;x&lt;/script&gt;" in _input(html, "cidade")
    assert "a&#34;b" in _input(html, "empresa")
    # na URL dos chips os dois vão codificados (o chip existe: a vaga SP casa o q)
    html_ok = painel.get("/vagas", params={"aba": "todas", "cidade": "sao", "empresa": 'a"b'}).text
    assert "empresa=a%22b" in html_ok
