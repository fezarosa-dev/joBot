"""Rotas da tela de vagas: abas, filtros, ordem, destaques e ações da vaga (plano T45)."""

import json
import re
import time
from collections.abc import Iterator
from contextlib import closing
from datetime import timedelta
from html import unescape
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


def _chips(painel: Painel, url: str, **kw: Any) -> str:
    """O fragmento dos chips da mesma vista: a página só traz o contêiner que o busca (T191)."""
    assert url.startswith("/vagas?") or url == "/vagas"
    return str(painel.get("/vagas/chips" + url.removeprefix("/vagas"), **kw).text)


def _atual(html: str) -> list[str]:
    """As abas marcadas com aria-current: as abas moram só na lateral (T254, D150 item 1)."""
    abas = re.search(r'<ul id="lateral-vagas".*?</ul>', html, re.S)
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
    # a contagem mora na lateral (T253); a tela não repete as abas (T254)
    assert _contagem_da_aba(painel.get("/vagas?aba=todas").text, "todas") == 7


def test_chips_com_contagem_e_aria_pressed(painel: Painel) -> None:
    html = _chips(painel, "/vagas?aba=todas")
    remoto = _tag(html, "chip-modalidade-remoto")
    assert 'aria-pressed="false"' in remoto
    assert 'data-contagem="4"' in remoto
    assert 'data-contagem="2"' in _tag(html, "chip-modalidade-presencial")
    ligado = _chips(painel, "/vagas?aba=todas&modalidade=remoto")
    assert 'aria-pressed="true"' in _tag(ligado, "chip-modalidade-remoto")


def _contador_que_falha(*_: object, **__: object) -> None:
    raise AssertionError("contar_chips no caminho da lista")


@pytest.mark.parametrize("cabecalhos", [{}, HX])
def test_lista_nao_espera_as_contagens_dos_chips(
    painel: Painel, monkeypatch: pytest.MonkeyPatch, cabecalhos: dict[str, str]
) -> None:
    monkeypatch.setattr("jobot.banco.leitura.contar_chips", _contador_que_falha)
    resposta = painel.get("/vagas?aba=todas&modalidade=remoto&q=python", headers=cabecalhos)
    assert resposta.status_code == 200
    assert _cartoes(resposta.text)
    recipiente = _tag(resposta.text, "filtros-chips")
    assert 'hx-get="/vagas/chips?aba=todas&amp;q=python&amp;modalidade=remoto"' in recipiente
    assert 'hx-trigger="load"' in recipiente
    assert 'aria-busy="true"' in recipiente
    assert "chip-modalidade-remoto" not in resposta.text
    assert t("pt", "vagas.filtros_carregando") in resposta.text


def test_destaques_nao_tem_o_recipiente_dos_chips(painel: Painel) -> None:
    assert "filtros-chips" not in painel.get("/vagas?aba=destaques").text


def test_rota_dos_chips_traz_o_fragmento_com_as_contagens(painel: Painel) -> None:
    resposta = painel.get("/vagas/chips?aba=todas&modalidade=remoto", headers=HX)
    assert resposta.status_code == 200
    assert "<html" not in resposta.text
    assert "HX-Request" in resposta.headers["vary"]
    assert 'id="filtros-chips"' in resposta.text
    assert "aria-busy" not in resposta.text
    assert "hx-trigger" not in resposta.text.split('id="chip-')[0]
    assert 'aria-pressed="true"' in _tag(resposta.text, "chip-modalidade-remoto")
    assert 'data-contagem="2"' in _tag(resposta.text, "chip-modalidade-presencial")
    assert _chips(painel, "/vagas?aba=todas") == painel.get("/vagas/chips?aba=todas").text


def test_chips_de_valores_que_so_diferem_por_espaco_e_sublinhado_tem_ids_diferentes(
    painel: Painel,
) -> None:
    painel.semear_mais(fonte="a b")
    painel.semear_mais(fonte="a_b")
    html = _chips(painel, "/vagas?aba=todas")
    botoes = re.findall(r'<button\b[^>]*\bid="(chip-fonte-[^"]*)"', html)
    assert len(botoes) == len(set(botoes))
    assert len([b for b in botoes if b.startswith("chip-fonte-a_")]) == 2
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))


def test_rota_dos_chips_sem_chips_vem_vazia(painel: Painel) -> None:
    resposta = painel.get("/vagas/chips?aba=destaques")
    assert (resposta.status_code, resposta.text.strip()) == (200, "")


@pytest.mark.parametrize(
    "consulta",
    [
        "aba=%FF&busca=x&sal_de=abc&sal_ate=-1&pais=ZZ&publicada=nunca&ordem=zzz&pagina=x",
        "aba=todas&q=%00&cidade=%27%22&modalidade=" + "x" * 500,
        "",
    ],
)
def test_rota_dos_chips_com_parametro_torto_nao_da_500(painel: Painel, consulta: str) -> None:
    assert painel.get(f"/vagas/chips?{consulta}").status_code == 200


def test_filtro_vai_para_a_url_e_a_url_reabre_igual(painel: Painel) -> None:
    ids = painel.ids
    html = _chips(painel, "/vagas?aba=todas")
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
    ligado = _tag(_chips(painel, destino), "chip-modalidade-remoto")
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
    chips = _chips(painel, "/vagas?aba=todas&q=python")
    assert "q=python" in _tag(chips, "chip-modalidade-remoto")


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


def test_salvar_pelo_teclado_fica_no_detalhe(painel: Painel) -> None:
    """T254: a linha da lista é só o link; salvar e ocultar moram na página da vaga (E10)."""
    vaga = painel.ids["nova"]
    assert "/status" not in _cartao_html(painel.get("/vagas?aba=todas").text, vaga)
    html = painel.get(f"/vagas/{vaga}").text
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
    # T254: as fontes saem da linha (D143.53) e ficam no detalhe
    assert "via " not in _cartao_html(painel.get("/vagas?aba=todas").text, vaga)
    cartao = painel.get(f"/vagas/{vaga}").text
    links = re.findall(r"<a\b[^>]*>", cartao)
    fontes = [x for x in links if 'aria-label="via ' in x]
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
    assert "javascript:" not in painel.get(f"/vagas/{vaga}").text


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
    """A linha da vaga na lista (T254: o cartão virou `<a role="option">`)."""
    achou = re.search(rf'<a\b[^>]*\bid="vaga-{vaga}".*?</a>', html, re.S)
    assert achou, f"sem a linha da vaga {vaga}"
    return achou.group(0)


# a linha mostra o convertido e leva o original e a cotação no title (D143.53)
CONVERTIDO_EUR_LINHA = (
    r'<span class="linha-salario" title="US\$ 5\.000/mês · ≈ € 4\.520/mês · '
    r'US\$ 1 = € 0,904 \(PTAX de 12/11\)">≈ € 4\.520/mês</span>'
)

# o cartão devolvido pelas ações (corpo.html) segue com o valor em linha própria
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


def test_valor_convertido_vai_na_linha_com_o_original_no_title(painel: Painel) -> None:
    _em_euro(painel)
    cartao = _cartao_html(painel.get("/vagas?aba=todas").text, painel.ids["usd"])
    assert re.search(CONVERTIDO_EUR_LINHA, cartao)
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
    assert re.search(CONVERTIDO_EUR_LINHA, segunda)
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
    marca = (
        'class="linha-salario nao-informado" title="Salário não informado">Salário não informado<'
    )
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


def _faixa(html: str) -> str:
    """A faixa de desfazer que veio por OOB (T256): o nó de `base.html`, trocado por dentro."""
    achou = re.search(r'<div\b[^>]*\bid="faixa-desfazer"[^>]*>.*?</div>\s*$', html, re.S | re.M)
    assert achou, "sem a faixa de desfazer na resposta"
    abertura = _tag(achou.group(0), "faixa-desfazer")
    assert 'role="status"' in abertura
    assert 'hx-swap-oob="innerHTML"' in abertura
    return achou.group(0)


def _ocultar_hx(painel: Painel, vaga: int) -> Any:
    return painel.http.post(
        f"/vagas/{vaga}/ocultar", data={CAMPO_CSRF: painel.token, "voltar": "/vagas"}, headers=HX
    )


def _mostrar_hx(painel: Painel, vaga: int) -> Any:
    return painel.http.post(
        f"/vagas/{vaga}/mostrar", data={CAMPO_CSRF: painel.token, "voltar": "/vagas"}, headers=HX
    )


def _form_da_faixa(faixa: str, destino: str) -> str:
    achou = re.search(rf'<form\b[^>]*\baction="{re.escape(destino)}"[^>]*>.*?</form>', faixa, re.S)
    assert achou, f"a faixa não traz o formulário para {destino}"
    return achou.group(0)


def test_ocultar_traz_a_faixa_com_mostrar(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    # no detalhe ao lado, Ocultar vai por HTMX sem herdar o hx-target de ninguém
    _, miolo = _lado(painel.get(f"/vagas?aba=todas&vaga={vaga}").text)
    achou = re.search(rf'<form\b[^>]*action="/vagas/{vaga}/ocultar"[^>]*>', miolo)
    assert achou and f'hx-post="/vagas/{vaga}/ocultar"' in achou.group(0)
    assert 'hx-target="this"' in achou.group(0) and 'hx-swap="none"' in achou.group(0)
    resposta = _ocultar_hx(painel, vaga)
    assert resposta.status_code == 200
    faixa = _faixa(resposta.text)
    assert "Vaga ocultada" in faixa
    form = _form_da_faixa(faixa, f"/vagas/{vaga}/mostrar")
    assert 'method="post"' in form
    assert f'name="{CAMPO_CSRF}" value="{painel.token}"' in form
    assert ">Desfazer<" in form
    # o botão da faixa não leva o hx-target herdado de quem o contém
    assert 'hx-target="this"' in form and 'hx-swap="none"' in form
    assert 'aria-label="Fechar"' in faixa
    # quem pediu é avisado para tirar a linha (e fechar o detalhe, se for ela) só depois do settle,
    # quando a faixa nova já tem os hx-* (antes, um ⌘Z viraria POST nativo)
    assert "HX-Trigger" not in resposta.headers
    assert json.loads(resposta.headers["HX-Trigger-After-Settle"]) == {
        "vaga-ocultada": {"vaga": vaga}
    }


def test_desfazer_traz_a_faixa_com_ocultar(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    _ocultar_hx(painel, vaga)
    resposta = _mostrar_hx(painel, vaga)
    assert resposta.status_code == 200
    faixa = _faixa(resposta.text)
    assert "Vaga mostrada de novo" in faixa
    form = _form_da_faixa(faixa, f"/vagas/{vaga}/ocultar")
    assert f'name="{CAMPO_CSRF}" value="{painel.token}"' in form
    assert ">Refazer<" in form
    assert f"/vagas/{vaga}/mostrar" not in faixa
    assert "HX-Trigger" not in resposta.headers
    assert json.loads(resposta.headers["HX-Trigger-After-Settle"]) == {
        "vaga-mostrada": {"vaga": vaga}
    }
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(0,)]


def test_refazer_oculta_de_novo(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    _ocultar_hx(painel, vaga)
    _mostrar_hx(painel, vaga)
    resposta = _ocultar_hx(painel, vaga)
    assert resposta.status_code == 200
    assert "Vaga ocultada" in _faixa(resposta.text)
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(1,)]
    assert vaga in _cartoes(painel.get("/vagas?aba=ocultas").text)
    # ocultar continua sendo acréscimo de evento: nada apagado
    assert painel.sql("SELECT acao FROM evento WHERE vaga_id = ? ORDER BY id", vaga) == [
        ("ocultou",),
        ("desfez",),
        ("ocultou",),
    ]


def test_form_da_faixa_leva_voltar_e_busca(painel: Painel) -> None:
    """Sem o JS (POST nativo), o form da faixa volta para a página de onde veio a ação."""
    vaga = painel.ids["nova"]
    voltar = "/vagas?aba=salvas&q=dev"
    resposta = painel.http.post(
        f"/vagas/{vaga}/ocultar",
        data={CAMPO_CSRF: painel.token, "voltar": voltar, "busca": "7"},
        headers=HX,
    )
    form = _form_da_faixa(_faixa(resposta.text), f"/vagas/{vaga}/mostrar")
    assert 'name="voltar" value="/vagas?aba=salvas&amp;q=dev"' in form
    assert 'name="busca" value="7"' in form
    resposta = painel.http.post(
        f"/vagas/{vaga}/mostrar", data={CAMPO_CSRF: painel.token, "voltar": voltar}, headers=HX
    )
    form = _form_da_faixa(_faixa(resposta.text), f"/vagas/{vaga}/ocultar")
    assert 'name="voltar" value="/vagas?aba=salvas&amp;q=dev"' in form
    assert 'name="busca" value=""' in form


def _enviar_form_da_faixa(painel: Painel, resposta: Any, destino: str) -> Any:
    """Aperta o botão da faixa como o navegador: manda todos os campos hidden do formulário."""
    form = _form_da_faixa(_faixa(resposta.text), destino)
    campos = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form))
    return painel.http.post(destino, data={k: unescape(v) for k, v in campos.items()}, headers=HX)


def test_desfazer_volta_ao_mostrar_mesmo_assim(painel: Painel) -> None:
    """O Desfazer é o inverso do Ocultar: quem tinha mandado "mostrar mesmo assim" (-1) numa vaga
    que a regra oculta volta a -1, não a 0 (que a regra esconderia de novo). Vale no Refazer."""
    vaga = painel.ids["oculta_regra"]
    painel.post(f"/vagas/{vaga}/mostrar")
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(-1,)]
    oculta = _ocultar_hx(painel, vaga)
    volta = _enviar_form_da_faixa(painel, oculta, f"/vagas/{vaga}/mostrar")
    assert volta.status_code == 200
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(-1,)]
    assert vaga in _cartoes(painel.get("/vagas?aba=todas").text)
    refeita = _enviar_form_da_faixa(painel, volta, f"/vagas/{vaga}/ocultar")
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(1,)]
    _enviar_form_da_faixa(painel, refeita, f"/vagas/{vaga}/mostrar")
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(-1,)]
    # só acréscimo: cada passo é um evento
    assert painel.sql("SELECT acao FROM evento WHERE vaga_id = ? ORDER BY id", vaga) == [
        ("mostrou",),
        ("ocultou",),
        ("desfez",),
        ("ocultou",),
        ("desfez",),
    ]
    # o "Trazer de volta" das Ocultas (sem o campo da faixa) segue zerando, como na decisão da T44
    painel.post(f"/vagas/{vaga}/ocultar")
    painel.post(f"/vagas/{vaga}/mostrar")
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(0,)]


def test_mostrar_mesmo_assim_numa_vaga_oculta_por_regra(painel: Painel) -> None:
    vaga = painel.ids["oculta_regra"]
    assert vaga in _cartoes(painel.get("/vagas?aba=ocultas").text)
    resposta = painel.post(f"/vagas/{vaga}/mostrar")
    assert resposta.status_code == 303
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(-1,)]
    assert vaga in _cartoes(painel.get("/vagas?aba=todas").text)
    assert vaga not in _cartoes(painel.get("/vagas?aba=ocultas").text)


def test_vaga_oculta_oferece_trazer_de_volta(painel: Painel) -> None:
    """T254: a linha diz por que está oculta; o botão de trazer de volta fica no detalhe."""
    html = painel.get("/vagas?aba=ocultas").text
    for chave in ("oculta_manual", "oculta_regra"):
        vaga = painel.ids[chave]
        assert 'data-icone="eye-off"' in _cartao_html(html, vaga)
        assert f'action="/vagas/{vaga}/mostrar"' in painel.get(f"/vagas/{vaga}").text


def test_motivo_do_encaixe_aparece_com_texto_para_leitor_de_tela(painel: Painel) -> None:
    painel.sql(
        "UPDATE encaixe SET motivos = ? WHERE vaga_id = ?",
        json.dumps([{"chave": "encaixe.cargo_titulo", "params": {"palavra": "python"}}]),
        painel.ids["usd"],
    )
    # T254: na linha, o nível vai para o leitor de tela; o motivo fica no detalhe (D143.53)
    linha = _cartao_html(painel.get("/vagas?aba=todas").text, painel.ids["usd"])
    assert '<span class="so-leitor">, Encaixe: Bom</span>' in linha
    assert "Cargo no título" not in linha
    detalhe = painel.get(f"/vagas/{painel.ids['usd']}").text
    assert "Cargo no título: python" in detalhe
    assert "Bom" in detalhe


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
    chips = _chips(painel, f"/vagas?aba=todas&{_OITO}")
    for nome, valor in (
        ("excluir", "cobol"),
        ("cidade", "sao"),
        ("empresa", "zeta"),
        ("sal_de", "1"),
        ("sal_ate", "99999"),
    ):
        assert f'value="{valor}"' in _input(html, nome), nome
    # o chip de outro valor do mesmo grupo troca só o dele e leva os outros sete campos
    trocado = _hx_get(chips, "chip-publicada-30d")
    ligado = _hx_get(chips, "chip-pais-PT")
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
    html = _chips(painel, "/vagas?aba=todas&sal_de=7000&cidade=sao")
    url = _hx_get(html, "chip-modalidade-remoto")
    assert "sal_de=7000" in url
    assert "cidade=sao" in url


def test_trocar_de_busca_mantem_os_campos_da_vista(painel: Painel) -> None:
    """T254: o seletor de busca da barra leva a aba e os filtros; só a busca muda."""
    _nova_busca(painel, "Segunda")
    html = painel.get(
        "/vagas?aba=novas&sal_de=7000&cidade=sao&excluir=cobol&modalidade=remoto"
    ).text
    form = re.search(r'<form class="seletor-busca".*?</form>', html, re.S)
    assert form
    ocultos = dict(
        re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', form.group(0))
    )
    assert ocultos["aba"] == "novas"
    assert (ocultos["sal_de"], ocultos["cidade"], ocultos["excluir"]) == ("7000", "sao", "cobol")
    assert ocultos["modalidade"] == "remoto"
    assert "busca" not in ocultos  # vem do <select>


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
    pt = _chips(painel, "/vagas?aba=todas")
    en = _chips(painel, "/vagas?aba=todas", headers={"Accept-Language": "en"})
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
    html = _chips(painel, "/vagas?aba=todas&q=zzmarca")
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
    # nas URLs do contêiner dos chips e nas dos chips o valor vai codificado
    consulta = {"aba": "todas", "cidade": "sao", "empresa": 'a"b'}
    assert "empresa=a%22b" in _tag(painel.get("/vagas", params=consulta).text, "filtros-chips")
    painel.semear_mais(titulo="Vaga AB", empresa='a"b', modalidade="remoto", **_SAL_SP)
    fragmento = painel.get("/vagas/chips", params=consulta).text
    assert "empresa=a%22b" in _hx_get(fragmento, "chip-modalidade-remoto")


# ---- contagens da lateral e busca escolhida (T253; D143.50, E16) ----


def _nova_busca(painel: Painel, nome: str, *, ativa: int = 1) -> int:
    linhas = painel.sql(
        "INSERT INTO busca (nome, cargos, modalidades, ativa, criada_em)"
        " VALUES (?, '[\"python\"]', '[]', ?, ?) RETURNING id",
        nome,
        ativa,
        AGORA.isoformat(),
    )
    return int(linhas[0][0])


def _config_toda(painel: Painel) -> list[tuple[Any, ...]]:
    return painel.sql("SELECT chave, valor FROM config ORDER BY chave")


def _ids_da_lateral(html: str) -> set[str]:
    """Os `busca=` dos links de Vagas da lateral."""
    ul = re.search(r'<ul\b[^>]*id="lateral-vagas".*?</ul>', html, re.S)
    assert ul is not None, "sem a seção Vagas da lateral"
    return set(re.findall(r"busca=(\d+)", unescape(ul.group(0))))


def _contagem_da_aba(html: str, aba: str) -> int:
    achou = re.search(
        rf'<a\b[^>]*href="/vagas\?aba={aba}[^"]*"[^>]*>[^<]*'
        r'(?:<span class="contagem">(\d+)</span>)?',
        html,
    )
    assert achou, f"sem o link da aba {aba} na lateral"
    return int(achou.group(1) or 0)


def _busca_marcada(html: str) -> list[str]:
    """O nome da busca marcada no seletor da barra da lista (T254: um `<select>`)."""
    seletor = re.search(r'<select id="busca-escolhida".*?</select>', html, re.S)
    assert seletor is not None
    return re.findall(r"<option\b[^>]*\bselected[^>]*>([^<]*)</option>", seletor.group(0))


def test_busca_escolhida_vale_sem_busca_na_url(painel: Painel) -> None:
    primeira = painel.ids["busca"]
    segunda = _nova_busca(painel, "Segunda")
    # sem escolha, a lateral usa a primeira ativa
    assert _ids_da_lateral(painel.get("/fontes").text) == {str(primeira)}
    painel.get(f"/vagas?aba=todas&busca={segunda}")
    assert painel.sql("SELECT valor FROM config WHERE chave = 'busca_escolhida'") == [
        (str(segunda),)
    ]
    # outra página, sem busca na URL: a lateral leva a escolhida
    assert _ids_da_lateral(painel.get("/fontes").text) == {str(segunda)}
    # e Vagas usa a escolhida: o seletor marca a segunda
    assert _busca_marcada(painel.get("/vagas?aba=novas").text) == ["Segunda"]


def test_busca_escolhida_apagada_cai_na_primeira_ativa(painel: Painel) -> None:
    primeira = painel.ids["busca"]
    segunda = _nova_busca(painel, "Segunda")
    painel.get(f"/vagas?aba=todas&busca={segunda}")
    assert _ids_da_lateral(painel.get("/fontes").text) == {str(segunda)}
    painel.sql("UPDATE busca SET ativa = 0 WHERE id = ?", segunda)  # desligada
    assert _ids_da_lateral(painel.get("/fontes").text) == {str(primeira)}
    painel.sql("UPDATE busca SET ativa = 1 WHERE id = ?", segunda)
    assert _ids_da_lateral(painel.get("/fontes").text) == {str(segunda)}
    painel.sql("DELETE FROM busca WHERE id = ?", segunda)  # apagada
    assert _ids_da_lateral(painel.get("/fontes").text) == {str(primeira)}
    assert "aba=novas" in painel.get("/vagas?aba=novas").text  # a tela não quebra


def test_busca_invalida_nao_grava(painel: Painel) -> None:
    desligada = _nova_busca(painel, "Desligada", ativa=0)
    ativa = _nova_busca(painel, "Ativa")
    antes = _config_toda(painel)
    for pedida in ("abc", "999999", "0", "-1", str(desligada)):
        assert painel.get(f"/vagas?aba=todas&busca={pedida}").status_code == 200
        assert _config_toda(painel) == antes, f"busca={pedida} gravou"
    # controle positivo: com o id de uma busca ativa, a escolha muda
    painel.get(f"/vagas?aba=todas&busca={ativa}")
    depois = _config_toda(painel)
    assert depois != antes
    assert ("busca_escolhida", str(ativa)) in depois


def test_busca_desligada_na_url_continua_valendo(painel: Painel) -> None:
    """Guarda (mutante: `busca_efetiva` aceitar só busca ativa)."""
    _nova_busca(painel, "Ativa")
    desligada = _nova_busca(painel, "Desligada", ativa=0)
    antes = _config_toda(painel)
    html = painel.get(f"/vagas?aba=todas&busca={desligada}").text
    assert _busca_marcada(html) == ["Desligada"]
    assert _config_toda(painel) == antes


def test_ocultar_atualiza_a_contagem_por_oob(painel: Painel) -> None:
    antes = _contagem_da_aba(painel.get("/vagas?aba=todas").text, "ocultas")
    assert antes == 2
    vaga = painel.ids["nova"]
    resposta = painel.http.post(
        f"/vagas/{vaga}/ocultar",
        data={CAMPO_CSRF: painel.token, "voltar": "/vagas?aba=salvas"},
        headers=HX,
    )
    assert resposta.status_code == 200
    html = resposta.text
    oob = re.search(r'<ul\b[^>]*hx-swap-oob="true"[^>]*>.*?</ul>', html, re.S)
    assert oob is not None, "a seção Vagas da lateral não veio por hx-swap-oob"
    assert 'id="lateral-vagas"' in oob.group(0)
    assert _contagem_da_aba(oob.group(0), "ocultas") == antes + 1
    # o item marcado é o da aba de onde a pessoa veio
    marcados = re.findall(r'<a\b[^>]*aria-current="page"[^>]*>', oob.group(0))
    assert len(marcados) == 1 and "aba=salvas" in marcados[0]


def test_aba_por_htmx_traz_a_lateral_por_oob_uma_vez(painel: Painel) -> None:
    """Guarda: a troca de aba troca a seção Vagas da lateral (uma só, não uma por cartão); a
    página inteira traz o id uma vez e sem `hx-swap-oob`."""
    inteira = painel.get("/vagas?aba=salvas").text
    assert inteira.count('id="lateral-vagas"') == 1 and "hx-swap-oob" not in inteira
    parcial = painel.get("/vagas?aba=salvas", headers=HX).text
    assert parcial.count('id="lateral-vagas"') == 1
    oob = re.search(r'<ul\b[^>]*hx-swap-oob="true"[^>]*>.*?</ul>', parcial, re.S)
    assert oob is not None
    marcados = re.findall(r'<a\b[^>]*aria-current="page"[^>]*>', oob.group(0))
    assert len(marcados) == 1 and "aba=salvas" in marcados[0]


def test_acao_na_pagina_da_vaga_marca_a_lateral_como_area(painel: Painel) -> None:
    """Guarda: de uma página filha (detalhe), o item fica `aria-current="true"`, como na casca."""
    vaga = painel.ids["nova"]
    resposta = painel.http.post(
        f"/vagas/{vaga}/status",
        data={CAMPO_CSRF: painel.token, "status": "salva", "voltar": f"/vagas/{vaga}"},
        headers=HX,
    )
    oob = re.search(r'<ul\b[^>]*hx-swap-oob="true"[^>]*>.*?</ul>', resposta.text, re.S)
    assert oob is not None
    marcados = re.findall(r'<a\b[^>]*aria-current="([a-z]+)"[^>]*>', oob.group(0))
    assert marcados == ["true"]
    assert _contagem_da_aba(oob.group(0), "salvas") == 2


# --- T254: a lista em linhas (listbox), a barra da lista e o estado vazio ---

LISTBOX = re.compile(r'(<div\b[^>]*\brole="listbox"[^>]*>)(.*?)</div>', re.S)
OPCAO = re.compile(r'(<a\b[^>]*\brole="option"[^>]*>)(.*?)</a>', re.S)


def _listbox(html: str) -> tuple[str, str]:
    """A abertura e o miolo do `role="listbox"` (as linhas só têm `<span>` e `<time>` dentro)."""
    achados = LISTBOX.findall(html)
    assert len(achados) == 1, f"esperava 1 listbox, achou {len(achados)}"
    abertura, miolo = achados[0]
    return str(abertura), str(miolo)


def _opcoes(html: str) -> list[tuple[str, str]]:
    return OPCAO.findall(_listbox(html)[1])


def _linha(html: str, vaga: int) -> tuple[str, str]:
    achadas = [(a, d) for a, d in _opcoes(html) if f'id="vaga-{vaga}"' in a]
    assert len(achadas) == 1, f"sem a linha da vaga {vaga}"
    return achadas[0]


def test_lista_e_listbox_com_options(painel: Painel) -> None:
    html = painel.get("/vagas?aba=todas").text
    abertura, miolo = _listbox(html)
    assert 'id="lista-vagas"' in abertura
    assert f'aria-label="{t("pt", "vagas.lista")}"' in abertura
    opcoes = _opcoes(html)
    assert len(opcoes) == len(_cartoes(html)) == 7
    for abertura_opcao, dentro in opcoes:
        assert 'aria-selected="false"' in abertura_opcao
        assert "<a" not in dentro and "<button" not in dentro and "<form" not in dentro
    # nada fora das options dentro do listbox (sem <li>, sem <ul>)
    assert re.sub(OPCAO, "", miolo).strip() == ""


def test_linha_tem_tres_linhas(painel: Painel) -> None:
    """Título com o encaixe; empresa e local; salário, selos e data: nessa ordem, com `title`."""
    vaga = painel.ids["usd"]
    _, dentro = _linha(painel.get("/vagas?aba=todas").text, vaga)
    partes = re.findall(r'class="linha-(\d)"', dentro)
    assert partes == ["1", "2", "3"]
    titulo = re.search(r'<span class="linha-titulo" title="([^"]*)">([^<]*)</span>', dentro)
    assert titulo and titulo.groups() == ("Desenvolvedor Python", "Desenvolvedor Python")
    empresa = re.search(r'<span class="linha-2" title="([^"]*)">', dentro)
    assert empresa and empresa.group(1).startswith("Zeta Corp")
    salario = re.search(r'<span class="linha-salario" title="([^"]*)">([^<]*)</span>', dentro)
    assert salario
    assert salario.group(1) == "US$ 5.000/mês · ≈ R$ 28.250/mês · US$ 1 = R$ 5,65 (PTAX de 13/11)"
    assert salario.group(2) == "≈ R$ 28.250/mês"
    data = re.search(r'<time datetime="([^"]+)" title="([^"]+)">([^<]+)</time>', dentro)
    assert data, "sem a data na linha 3"
    marcas = ('class="linha-titulo"', 'class="linha-2"', "linha-salario", "<time")
    ordem = [dentro.index(m) for m in marcas]
    assert ordem == sorted(ordem)
    # fontes, motivo do encaixe e botões saem da linha (detalhe e menu)
    assert "via " not in dentro and 'class="motivo"' not in dentro


def test_linha_e_link_sem_js(painel: Painel) -> None:
    html = painel.get("/vagas?aba=todas").text
    ids = _cartoes(html)
    opcoes = _opcoes(html)
    assert [re.findall(r'id="vaga-(\d+)"', a) for a, _ in opcoes] == [[str(i)] for i in ids]
    for abertura, dentro in opcoes:
        vaga = re.findall(r'id="vaga-(\d+)"', abertura)[0]
        assert f'href="/vagas/{vaga}"' in abertura
        assert "tabindex" not in abertura  # sem JS, todo link no Tab
        # T255: com JS a linha abre o detalhe ao lado; o htmx só age por cima do href
        assert re.findall(r"\b(hx-[a-z-]+)=", abertura) == [
            "hx-get",
            "hx-target",
            "hx-select",
            "hx-swap",
            "hx-push-url",
        ]
        assert 'hx-target="#detalhe-vaga"' in abertura
        assert "<a" not in dentro and "<button" not in dentro
    vaga = painel.ids["usd"]
    assert painel.get(f"/vagas/{vaga}").status_code == 200


def test_abas_saem_do_topo(painel: Painel) -> None:
    _nova_busca(painel, "Segunda")
    html = painel.get("/vagas?aba=todas").text
    assert 'class="abas"' not in html and 'id="aba-todas"' not in html
    seletor = re.search(r'<select\b[^>]*\bname="busca"[^>]*>(.*?)</select>', html, re.S)
    assert seletor, "o seletor de busca não é um <select>"
    assert len(re.findall(r"<option\b", seletor.group(1))) == 2
    assert len(re.findall(r"<option\b[^>]*\bselected\b", seletor.group(1))) == 1
    ordem = re.search(r'<select\b[^>]*\bid="ordem"[^>]*>', html)
    assert ordem and 'form="busca"' in ordem.group(0)
    barra = re.search(r'<div class="barra-lista"[^>]*>.*?<form id="busca"', html, re.S)
    assert barra, "o form#busca não está na barra da lista"


def test_seletor_de_busca_so_com_duas_buscas(painel: Painel) -> None:
    html = painel.get("/vagas?aba=todas").text
    assert not re.search(r'<select\b[^>]*\bname="busca"', html)


def test_vagas_tem_um_so_aria_current_page(painel: Painel) -> None:
    """D150.1: sem a `nav.abas`, só o item da lateral marca a página aberta."""
    for url in ("/vagas", "/vagas?aba=salvas"):
        assert painel.get(url).text.count('aria-current="page"') == 1


def test_programas_fora_do_listbox(painel: Painel) -> None:
    from jobot.banco.paginas import adicionar_pagina

    with closing(abrir(painel.banco)) as con:
        adicionar_pagina(con, "https://alfa.exemplo.test/trainee", "Trainee Alfa")
        con.commit()
    vaga = painel.semear_mais(titulo="Trainee 2027", contrato="trainee")
    html = painel.get("/vagas?aba=programas").text
    abertura, miolo = _listbox(html)
    assert f'id="vaga-{vaga}"' in miolo
    assert "lista-programas-paginas" not in miolo and "Trainee Alfa" not in miolo
    secao = html.index('id="lista-programas-paginas"')
    assert html.index(abertura) < secao
    assert "Trainee Alfa" in html[secao:]
    assert 'href="/sites#site-' in html[secao:]


@pytest.mark.parametrize(
    ("idioma", "titulo", "botao"),
    [("pt", "Nenhuma vaga", "Buscar vagas"), ("en", "No Jobs", "Search for Jobs")],
)
@pytest.mark.parametrize(
    ("aba", "frase"), [("todas", "vagas.vazio"), ("destaques", "vagas.vazio_destaques")]
)
def test_vazio_tem_buscar_vagas(
    painel: Painel, idioma: str, titulo: str, botao: str, aba: str, frase: str
) -> None:
    cab = {"Accept-Language": idioma}
    # destaques não usam a busca: ficam vazios quando nada foi visto nas últimas 24 h
    painel.sql("UPDATE vaga SET primeira_vista_em = ?", (AGORA - timedelta(days=30)).isoformat())
    html = painel.get(f"/vagas?aba={aba}&q=zzzznadaachado", headers=cab).text
    vazio = re.search(r'<div id="lista-vagas" class="vazio"[^>]*>(.*?)</div>', html, re.S)
    assert vazio, "sem o estado vazio"
    corpo = vazio.group(1)
    assert 'data-icone="search-x"' in corpo
    assert f">{titulo}</h2>" in corpo
    assert f"<p>{t(idioma, frase)}</p>" in corpo
    form = re.search(r'<form\b[^>]*action="/buscar-agora"[^>]*>(.*?)</form>', corpo, re.S)
    assert form and 'hx-target="#andamento"' in form.group(0)
    assert f">{botao}</button>" in form.group(1)
    assert f'name="{CAMPO_CSRF}"' in form.group(1)
    assert 'role="listbox"' not in html


@pytest.fixture
def fuso_sao_paulo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    yield
    monkeypatch.undo()  # volta o TZ antes do tzset: sem isso o fuso vaza para os outros testes
    time.tzset()


@pytest.mark.usefixtures("fuso_sao_paulo")
def test_data_de_coleta_na_linha_e_o_dia_local(painel: Painel) -> None:
    """Vista às 01:00Z de 16/11 = 22:00 de 15/11 em Brasília: a linha mostra 15/11."""
    vaga = painel.semear_mais(publicada_em=None, primeira_vista_em="2026-11-16T01:00:00+00:00")
    _, dentro = _linha(painel.get("/vagas?aba=todas").text, vaga)
    data = re.search(r'<time datetime="[^"]+" title="([^"]+)">([^<]+)</time>', dentro)
    assert data and data.groups() == ("15/11/2026", "15/11")


def test_ordem_e_mais_filtros_em_title_case_no_en(painel: Painel) -> None:
    """Restrições globais: item de menu e botão em inglês seguem o Title Case da HIG."""
    html = painel.get("/vagas?aba=todas", headers={"Accept-Language": "en"}).text
    ordem = re.search(r'<select\b[^>]*\bid="ordem"[^>]*>(.*?)</select>', html, re.S)
    assert ordem
    opcoes = [unescape(o) for o in re.findall(r"<option\b[^>]*>([^<]+)</option>", ordem.group(1))]
    assert opcoes == [
        "Best Fit",
        "Most Recent",
        "Closest Deadline",
        "Highest Salary",
        "Company (A to Z)",
    ]
    assert "<summary>More Filters</summary>" in html
    assert t("en", "vagas.mais_filtros_n", n=2) == "More Filters (2)"
    assert t("en", "vagas.mais") == "Load More Jobs"


# --- T255: o detalhe ao lado da lista (`/vagas?vaga=<id>`) ---

LADO = re.compile(r'(<dialog\b[^>]*\bid="detalhe-vaga"[^>]*>)(.*?)</dialog>', re.S)


def _lado(html: str) -> tuple[str, str]:
    """A abertura e o miolo do `<dialog>` do detalhe: ele existe sempre, aberto ou vazio."""
    achados = LADO.findall(html)
    assert len(achados) == 1, f"esperava 1 detalhe ao lado, achou {len(achados)}"
    abertura, miolo = achados[0]
    return str(abertura), str(miolo)


def test_vaga_na_url_traz_o_detalhe(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    url = f"/vagas?aba=todas&ordem=recentes&vaga={vaga}"
    for resposta in (painel.get(url), painel.get(url, headers=HX)):
        assert resposta.status_code == 200
        abertura, miolo = _lado(resposta.text)
        assert re.search(r"\sopen\b", abertura)
        assert f'data-vaga="{vaga}"' in abertura
        assert "Engenheira de Integração" in miolo
        assert re.search(r"<h2\b[^>]*>Engenheira de Integração</h2>", miolo)  # h1 é o da página
        linha, _ = _linha(resposta.text, vaga)
        assert 'aria-selected="true"' in linha
        outras = [a for a, _ in _opcoes(resposta.text) if f'id="vaga-{vaga}"' not in a]
        assert outras and all('aria-selected="false"' in a for a in outras)
    # a linha pede o detalhe por HTMX e guarda aba e ordem no endereço; sem JS, a página da vaga
    linha, _ = _linha(painel.get("/vagas?aba=todas&ordem=recentes").text, vaga)
    assert f'href="/vagas/{vaga}"' in linha
    assert f'hx-get="/vagas?aba=todas&amp;ordem=recentes&amp;vaga={vaga}"' in linha
    assert 'hx-target="#detalhe-vaga"' in linha
    assert 'hx-push-url="true"' in linha


@pytest.mark.parametrize("valor", ["abc", "999999", "9" * 5000, str(2**63), "0", "-3", ""])
def test_vaga_invalida_na_url_sem_detalhe(painel: Painel, valor: str) -> None:
    for cabecalhos in ({}, HX):
        resposta = painel.get(f"/vagas?aba=todas&vaga={valor}", headers=cabecalhos)
        assert resposta.status_code == 200
        assert _cartoes(resposta.text)  # a lista vem inteira
        abertura, miolo = _lado(resposta.text)
        assert not re.search(r"\sopen\b", abertura)
        assert "data-vaga" not in abertura
        assert miolo.strip() == ""
        assert 'aria-selected="true"' not in _listbox(resposta.text)[1]


def test_detalhe_tem_os_botoes_da_linha(painel: Painel) -> None:
    vaga = painel.ids["nova"]
    lista = f"/vagas?aba=todas&vaga={vaga}"
    _, miolo = _lado(painel.get(lista).text)
    # Abrir no site: a página da vaga na fonte, em outra aba
    site = re.search(r"<a\b([^>]*)>Abrir no site</a>", miolo)
    assert site
    assert f'href="https://exemplo.test/vagas/{vaga}"' in site.group(1)
    assert 'target="_blank"' in site.group(1)
    assert 'rel="noopener noreferrer"' in site.group(1)
    # as fontes ("via …") e o motivo do encaixe
    assert 'aria-label="via Remotive' in miolo
    assert re.search(rf"<h3\b[^>]*>{t('pt', 'detalhe.secao.encaixe')}</h3>", miolo)
    assert t("pt", "detalhe.encaixe.nota", nota=80) in miolo
    # Salvar e Ocultar voltam para a mesma vista, com o detalhe aberto
    status = re.search(rf'<form\b[^>]*action="/vagas/{vaga}/status"[^>]*>(.*?)</form>', miolo, re.S)
    assert status
    assert 'name="status" value="salva"' in status.group(1)
    assert f'name="voltar" value="{escape(lista)}"' in status.group(1)
    ocultar = re.search(
        rf'<form\b[^>]*action="/vagas/{vaga}/ocultar"[^>]*>(.*?)</form>', miolo, re.S
    )
    assert ocultar
    assert f'name="voltar" value="{escape(lista)}"' in ocultar.group(1)
    # salva, o detalhe ao lado oferece o Candidatei
    salvar = painel.post(f"/vagas/{vaga}/status", status="salva", voltar=lista)
    assert (salvar.status_code, salvar.headers["location"]) == (303, lista)
    _, miolo = _lado(painel.get(lista).text)
    assert (
        f'value="candidatei" class="secundario">{t("pt", "vagas.acao.para.candidatei")}<' in miolo
    )


def test_pedido_do_detalhe_traz_so_o_dialog(painel: Painel) -> None:
    """A linha pede só o detalhe (`HX-Target: detalhe-vaga`): o servidor não refaz a lista, os
    Destaques nem a lateral a cada clique."""
    vaga = painel.ids["nova"]
    url = f"/vagas?aba=todas&vaga={vaga}"
    so_o_lado = {**HX, "HX-Target": "detalhe-vaga"}
    resposta = painel.get(url, headers=so_o_lado)
    assert resposta.status_code == 200
    abertura, miolo = _lado(resposta.text)
    assert f'data-vaga="{vaga}"' in abertura
    assert re.search(r"<h2\b[^>]*>Engenheira de Integração</h2>", miolo)
    assert 'id="lista-vagas"' not in resposta.text
    assert "hx-swap-oob" not in resposta.text
    # controle: o mesmo pedido de outro alvo traz o miolo inteiro
    assert 'id="lista-vagas"' in painel.get(url, headers=HX).text
    # vaga torta no pedido do detalhe: o dialog vazio, nunca 500
    torta = painel.get("/vagas?aba=todas&vaga=abc", headers=so_o_lado)
    assert torta.status_code == 200
    abertura, miolo = _lado(torta.text)
    assert "data-vaga" not in abertura
    assert miolo.strip() == ""


def test_detalhe_pelo_clique_usa_a_moeda_de_exibicao(painel: Painel) -> None:
    """O detalhe pedido só (o clique na linha) converte na moeda escolhida, igual à página cheia."""
    _em_euro(painel)
    url = f"/vagas?aba=todas&vaga={painel.ids['usd']}"
    convertido = r"≈ € 4\.520/mês · US\$ 1 = € 0,904 \(PTAX de 12/11\)"
    for cabecalhos in ({}, {**HX, "HX-Target": "detalhe-vaga"}):
        _, miolo = _lado(painel.get(url, headers=cabecalhos).text)
        assert re.search(convertido, miolo)
        assert "≈ R$" not in miolo


def test_lista_vazia_com_vaga_na_url_traz_o_detalhe(painel: Painel) -> None:
    """O dialog existe mesmo sem linhas: a vaga da URL abre, e o alvo do htmx não some."""
    vaga = painel.ids["nova"]
    for cabecalhos in ({}, HX):
        resposta = painel.get(f"/vagas?aba=todas&q=zzqxnadaqui&vaga={vaga}", headers=cabecalhos)
        assert resposta.status_code == 200
        assert not _cartoes(resposta.text)
        abertura, miolo = _lado(resposta.text)
        assert f'data-vaga="{vaga}"' in abertura
        assert "Engenheira de Integração" in miolo


def test_ocultar_repetido_nao_troca_a_faixa(painel: Painel) -> None:
    """Duplo clique no Ocultar: o 2º POST acha a vaga já oculta e não troca a faixa, que guarda
    o `antes=-1` do 1º. Senão o Desfazer zeraria a vaga e não voltaria ao "mostrar mesmo assim"."""
    vaga = painel.ids["oculta_regra"]
    painel.post(f"/vagas/{vaga}/mostrar")
    primeira = _ocultar_hx(painel, vaga)
    form = _form_da_faixa(_faixa(primeira.text), f"/vagas/{vaga}/mostrar")
    assert 'name="antes" value="-1"' in form
    segunda = _ocultar_hx(painel, vaga)
    assert segunda.status_code == 200
    assert 'id="faixa-desfazer"' not in segunda.text
    assert painel.sql("SELECT oculta_manual FROM vaga WHERE id = ?", vaga) == [(1,)]
    assert painel.sql("SELECT acao FROM evento WHERE vaga_id = ? ORDER BY id", vaga) == [
        ("mostrou",),
        ("ocultou",),
    ]
