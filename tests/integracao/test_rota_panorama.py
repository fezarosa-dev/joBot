"""A tela Panorama (plano T288; desenho 5.1 a 5.3 e 5.10; E11, E16, E19).

O banco parte do conjunto de `apoio.semear` (a não ser que o teste peça o banco vazio), com a
primeira execução concluída. As execuções e a saúde das fontes entram pelas funções do banco; a
hora vem do `RelogioFalso` do app. O fuso é o de São Paulo (-03:00) em todo teste.
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
from apoio.semear import inserir_vaga, semear
from jobot.banco import acoes, leitura
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import abrir_execucao, fechar_execucao, gravar_saude
from jobot.banco.leitura import Filtros
from jobot.banco.migrar import migrar
from jobot.banco.sessoes import gravar_sessao
from jobot.nucleo.gmail import CONTA
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.rotas.panorama import pct

pytestmark = pytest.mark.usefixtures("fuso_de_sao_paulo")

PORTA = 47624
HORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)  # 09:00 em São Paulo, o AGORA do `semear`
HTMX = {"HX-Request": "true"}
ABAS_DE_HOJE = ("novas", "fecham_logo", "salvas", "candidatei", "todas")
GRUPO = re.compile(
    r'<section\b[^>]*\baria-labelledby="([^"]+)"[^>]*>\s*<h2 id="([^"]+)">([^<]*)</h2>'
)
NUMERO_DE_HOJE = re.compile(
    r'<li><a href="([^"]+)"><span class="numero">(\d+)</span>'
    r'<span class="rotulo">([^<]+)</span></a></li>'
)
PASSO = re.compile(
    r'<li><span class="rotulo">([^<]+)</span> <span class="numero">(\d+)</span></li>'
)
BARRA = re.compile(
    r'<li><a href="([^"]+)"><span class="rotulo">([^<]+)</span><span class="so-leitor">, </span>'
    r'<svg class="barra" aria-hidden="true" focusable="false"><rect width="(\d+)%" height="100%"/>'
    r'</svg><span class="numero">(\d+)</span></a></li>'
)
CATALOGO = i18n.carregar()


class Painel:
    """App sobre um banco semeado (ou vazio), com o relógio parado em `hora`."""

    def __init__(
        self, tmp_path: Path, hora: datetime = HORA, semente: bool = True, primeira: bool = True
    ) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            self.ids = semear(con) if semente else {}
            if primeira:
                gravar_config(con, "primeira_execucao_concluida", True)
        self.app = criar_app(tmp_path, PORTA)
        self.relogio(hora)
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )

    def relogio(self, hora: datetime) -> None:
        self.app.state.relogio = RelogioFalso(hora)

    def con(self) -> closing[sqlite3.Connection]:
        return closing(abrir(self.banco))

    def sql(self, texto: str, *params: Any) -> None:
        with self.con() as con:
            con.execute(texto, params)
            con.commit()

    def get(self, url: str = "/panorama", **cabecalhos: str) -> Any:
        return self.http.get(url, headers=cabecalhos)

    def pagina(self, url: str = "/panorama") -> str:
        resposta = self.get(url)
        assert resposta.status_code == 200
        return str(resposta.text)

    def texto(self, url: str = "/panorama") -> str:
        return _texto(self.pagina(url))

    def execucao(
        self,
        inicio: datetime,
        *linhas: tuple[str, str] | tuple[str, str, str],
        tipo: str = "busca",
        concluir: bool = True,
    ) -> None:
        """Uma execução (concluída cinco minutos depois) com as linhas de saúde (fonte, estado,
        motivo), de escopo único."""
        with self.con() as con:
            id_ = abrir_execucao(con, tipo, "agenda", inicio)  # type: ignore[arg-type]
            assert id_ is not None
            for fonte, estado, *motivo in linhas:
                gravar_saude(
                    con,
                    id_,
                    fonte,
                    "",
                    estado,  # type: ignore[arg-type]
                    pedidos=1,
                    motivo=motivo[0] if motivo else None,
                )
            if concluir:
                fechar_execucao(con, id_, inicio + timedelta(minutes=5))

    def abrir(self, nome: str, minutos: int) -> int:
        vaga = self.ids[nome]
        with self.con() as con:
            assert acoes.abriu_candidatura(con, vaga, HORA + timedelta(minutes=minutos))
        return vaga

    def so_ligadas(self, *chaves: str) -> None:
        """Deixa ligadas só as fontes pedidas (criando as que faltam) e sem intervalo próprio."""
        with self.con() as con:
            for chave in chaves:
                con.execute(
                    "INSERT INTO fonte (chave, leva) VALUES (?, 'A') ON CONFLICT DO NOTHING",
                    (chave,),
                )
            marcas = ", ".join("?" * len(chaves))
            con.execute(
                f"UPDATE fonte SET ligada = chave IN ({marcas}), intervalo_min = NULL", chaves
            )
            con.commit()


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _grupos(html: str) -> list[str]:
    achados = GRUPO.findall(html)
    assert all(rotulo == id_ for rotulo, id_, _ in achados), achados
    return [titulo for _, _, titulo in achados]


def _secao(html: str, id_: str) -> str:
    assert f'aria-labelledby="{id_}"' in html, id_
    inicio = html.index(f'aria-labelledby="{id_}"')
    return html[inicio : html.index("</section>", inicio)]


def _bloco(html: str, nome: str) -> str:
    assert f'aria-labelledby="panorama-aparece-{nome}"' in html, nome
    inicio = html.index(f'aria-labelledby="panorama-aparece-{nome}"')
    fins = [f for m in ('<div class="bloco"', "</section>") if (f := html.find(m, inicio)) >= 0]
    return html[inicio : min(fins, default=len(html))]


def _para_responder(html: str) -> str:
    assert 'id="para-responder"' in html
    inicio = html.index('id="para-responder"')
    return html[inicio : html.index('<div class="bloco">', inicio)]


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _contagens(painel: Painel) -> dict[str, int]:
    with painel.con() as con:
        return dict(leitura.contar_abas(con, painel.ids["busca"], HORA))


def _chips(painel: Painel) -> dict[str, dict[str, int]]:
    filtros = Filtros(aba="todas", busca_id=painel.ids["busca"])
    with painel.con() as con:
        return {k: dict(v) for k, v in leitura.contar_chips(con, filtros, HORA).items()}


# --- Hoje ---


def test_quatro_grupos_em_ordem(painel: Painel) -> None:
    assert _grupos(painel.pagina()) == ["Hoje", "Candidaturas", "A busca", "O que aparece"]


def test_numeros_hoje_batem_com_contar_abas(painel: Painel) -> None:
    contagens = _contagens(painel)
    assert contagens["candidatei"] == 0  # o zero aparece como "0"
    assert contagens["todas"] > 0
    rotulos = CATALOGO["pt"]
    numeros = [(r, int(n)) for _, n, r in NUMERO_DE_HOJE.findall(painel.pagina())]
    assert numeros == [(rotulos[f"vagas.aba.{a}"], contagens[a]) for a in ABAS_DE_HOJE]


def test_numero_e_link_para_a_aba_com_busca(painel: Painel) -> None:
    busca = painel.ids["busca"]
    links = [html_lib.unescape(h) for h, _, _ in NUMERO_DE_HOJE.findall(painel.pagina())]
    assert links == [f"/vagas?aba={a}&busca={busca}" for a in ABAS_DE_HOJE]


# --- Candidaturas ---


def test_candidaturas_por_passo(painel: Painel) -> None:
    painel.sql(
        "UPDATE vaga SET status = 'candidatei' WHERE id IN (?, ?)",
        *[painel.ids["usd"], painel.ids["fechada_salva"]],
    )
    painel.sql("UPDATE vaga SET status = 'entrevista' WHERE id = ?", painel.ids["brl"])
    html = _secao(painel.pagina(), "panorama-candidaturas")
    assert PASSO.findall(html) == [
        ("Candidatei", "2"),
        ("Entrevista", "1"),
        ("Oferta", "0"),
        ("Recusada", "0"),
    ]
    assert 'href="/vagas?aba=candidatei' in html


def test_para_responder_lista_pendentes(painel: Painel) -> None:
    antiga = painel.abrir("usd", 1)
    nova = painel.abrir("brl", 2)
    lista = _para_responder(painel.pagina())
    ids = re.findall(r'<p id="responder-pergunta-(\d+)">', lista)
    assert ids == [str(nova), str(antiga)]  # a aberta mais recente primeiro
    assert set(re.findall(r'name="voltar" value="([^"]*)"', lista)) == {"/panorama"}
    assert "Nenhuma pergunta esperando." not in lista


def test_para_responder_fragmento(painel: Painel) -> None:
    vaga = painel.abrir("usd", 1)
    resposta = painel.get("/panorama/para-responder", **HTMX)
    assert resposta.status_code == 200
    assert f'<p id="responder-pergunta-{vaga}">' in resposta.text
    assert 'name="voltar" value="/panorama"' in resposta.text
    for casca in ("<html", "<h1", 'id="para-responder"', "<section"):
        assert casca not in resposta.text, casca


def test_fecham_ate_5(painel: Painel) -> None:
    with painel.con() as con:
        for dia in (19, 14, 18, 15, 17, 16):  # seis salvas de 14/11 a 19/11 (hoje é 13/11)
            inserir_vaga(con, titulo=f"Salva {dia}", status="salva", prazo=f"2026-11-{dia}")
    html = _secao(painel.pagina(), "panorama-candidaturas")
    fecham = html[html.index('id="panorama-fecham"') :]
    achadas = re.findall(r'<a href="/vagas/\d+">(Salva \d+)</a>.*?fecha (\d\d/\d\d)', fecham)
    assert achadas == [(f"Salva {d}", f"{d}/11") for d in (14, 15, 16, 17, 18)]
    assert 'href="/vagas?aba=salvas' in fecham


# --- A busca ---


def test_ultima_e_proxima_busca(tmp_path: Path) -> None:
    painel = Painel(tmp_path, datetime(2026, 11, 17, 1, 30, tzinfo=UTC))  # 22:30 de 16/11
    painel.execucao(datetime(2026, 11, 17, 1, 0, tzinfo=UTC))
    texto = painel.texto()
    assert "Última busca completa: 16/11/2026." in texto
    # 04:00 UTC é 01:00 de 17/11: outro dia local, com a chave que leva o dia
    assert "Próxima busca automática em 17/11, por volta das 01:00." in texto


def test_proxima_no_mesmo_dia_so_hora(painel: Painel) -> None:
    painel.relogio(HORA + timedelta(minutes=30))
    painel.execucao(HORA)
    texto = painel.texto()
    assert "Próxima busca automática por volta das 12:00." in texto  # 15:00 UTC
    assert "Próxima busca automática em" not in texto


def test_proxima_some_quando_passou(painel: Painel) -> None:
    painel.execucao(HORA - timedelta(hours=7))  # a próxima seria às 08:00 UTC
    assert "Próxima busca" not in painel.texto()
    painel.relogio(HORA - timedelta(hours=6))  # controle: antes dela, a linha aparece
    assert "Próxima busca automática por volta das 05:00." in painel.texto()


def test_proxima_igual_a_de_fontes(tmp_path: Path) -> None:
    """Uma fonte ligada, sem `intervalo_min` e fora de `no_limite`: as duas telas dão a mesma
    hora. Nos outros casos o cartão de Fontes pode dar uma hora mais tarde, por desenho."""
    painel = Painel(tmp_path, datetime(2026, 11, 17, 1, 30, tzinfo=UTC))
    painel.so_ligadas("himalayas")
    painel.execucao(datetime(2026, 11, 17, 1, 0, tzinfo=UTC), ("himalayas", "ok"))
    de_fontes = re.findall(r"Próxima execução (\d\d/\d\d) (\d\d:\d\d)", painel.texto("/fontes"))
    do_panorama = re.findall(r"em (\d\d/\d\d), por volta das (\d\d:\d\d)", painel.texto())
    assert de_fontes == do_panorama == [("17/11", "01:00")]


def test_fontes_com_problema_conta_falhou_e_parcial(painel: Painel) -> None:
    painel.so_ligadas("remotive", "himalayas", "greenhouse")
    painel.sql("INSERT INTO fonte (chave, leva, ligada) VALUES ('lever', 'A', 0)")
    painel.execucao(
        HORA - timedelta(hours=1),
        ("remotive", "falhou", "saude.excecao"),
        ("himalayas", "parcial", "saude.parcial_n"),
        ("greenhouse", "ok"),
        ("lever", "falhou", "saude.excecao"),  # desligada: não conta
    )
    html = _secao(painel.pagina(), "panorama-busca")
    assert "Fontes com problema: 2" in _texto(html)
    assert 'href="/fontes"' in html
    assert "Todas as fontes funcionaram" not in _texto(html)


# --- Barras e O que aparece ---


def test_pct_das_barras() -> None:
    assert (pct(0, 10), pct(1, 1000), pct(5, 10), pct(10, 10), pct(3, 0)) == (0, 2, 50, 100, 0)


def test_barras_sem_atributo_style(painel: Painel) -> None:
    html = painel.pagina()
    assert '<svg class="barra"' in html  # controle: as barras estão na página
    assert "style=" not in html


def test_barra_aria_hidden_e_numero_no_texto(painel: Painel) -> None:
    remoto = _chips(painel)["modalidade"]["remoto"]
    linhas = BARRA.findall(_bloco(painel.pagina(), "modalidade"))
    assert linhas, "sem barras de modalidade"
    achada = [(r, int(n)) for _, r, _, n in linhas if r == "Remoto"]
    assert achada == [("Remoto", remoto)]
    # o leitor de tela lê o rótulo e o número do link; a barra (aria-hidden) fica de fora
    link = next(
        m
        for m in re.finditer(r"<a [^>]*>(.*?)</a>", _bloco(painel.pagina(), "modalidade"))
        if "Remoto" in m.group(1)
    )
    sem_barra = re.sub(r"<svg\b.*?</svg>", "", link.group(1))
    assert html_lib.unescape(re.sub(r"<[^>]+>", "", sem_barra)) == f"Remoto, {remoto}"


def test_barras_proporcionais_e_link_do_chip(painel: Painel) -> None:
    contagem = _chips(painel)["modalidade"]
    maior = max(contagem.values())
    busca = painel.ids["busca"]
    linhas = BARRA.findall(_bloco(painel.pagina(), "modalidade"))
    assert [(html_lib.unescape(u), int(p)) for u, _, p, _ in linhas] == [
        (f"/vagas?aba=todas&busca={busca}&modalidade={valor}", pct(n, maior))
        for valor, n in sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def test_frase_mais_comum(painel: Painel) -> None:
    total = _contagens(painel)["todas"]
    remoto = _chips(painel)["modalidade"]["remoto"]
    assert remoto == max(_chips(painel)["modalidade"].values())
    frase = f"Mais comum: Remoto, com {remoto} de {total} vagas."
    assert frase in _texto(_bloco(painel.pagina(), "modalidade"))


def test_blocos_de_o_que_aparece_em_ordem_com_ver(painel: Painel) -> None:
    html = _secao(painel.pagina(), "panorama-aparece")
    blocos = re.findall(r'aria-labelledby="panorama-aparece-(\w+)"', html)
    assert blocos == ["encaixe", "modalidade", "area", "fonte"]
    busca = painel.ids["busca"]
    ver = f'<a href="/vagas?aba=todas&amp;busca={busca}">Ver em Vagas</a>'
    assert ver not in _bloco(html, "encaixe")  # Encaixe mostra todos os níveis, sem "Ver"
    assert all(ver in _bloco(html, nome) for nome in ("modalidade", "area", "fonte"))
    niveis = [r for _, r, _, _ in BARRA.findall(_bloco(html, "encaixe"))]
    assert niveis == ["Bom", "Médio", "Fraco"]


def test_bloco_mostra_os_5_maiores(painel: Painel) -> None:
    with painel.con() as con:
        for i, area in enumerate(("design", "vendas", "financas", "marketing", "saude")):
            for _ in range(i + 3):
                inserir_vaga(con, area=area)
    contagem = _chips(painel)["area"]
    assert len(contagem) > 5
    cinco = sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    linhas = BARRA.findall(_bloco(painel.pagina(), "area"))
    assert [int(n) for _, _, _, n in linhas] == [n for _, n in cinco]


# --- Busca escolhida e ids ---


def test_busca_escolhida_vale(painel: Painel) -> None:
    with painel.con() as con:
        cur = con.execute(
            "INSERT INTO busca (nome, cargos, criada_em) VALUES ('Segunda', '[]', ?)",
            (HORA.isoformat(),),
        )
        segunda = cur.lastrowid
        con.commit()
        gravar_config(con, "busca_escolhida", segunda)
    html = painel.pagina()
    assert "Contando a busca Segunda." in _texto(html)
    links = [html_lib.unescape(h) for h, _, _ in NUMERO_DE_HOJE.findall(html)]
    links += [html_lib.unescape(h) for h, _, _, _ in BARRA.findall(html)]
    assert links
    assert all(f"busca={segunda}" in h for h in links), links
    # a busca da URL vence a gravada
    primeira = painel.ids["busca"]
    assert "Contando a busca Python remoto." in painel.texto(f"/panorama?busca={primeira}")


def test_ids_unicos_com_faixa_e_para_responder(painel: Painel) -> None:
    vaga = painel.abrir("usd", 1)
    pagina = painel.pagina()
    faixa = painel.get("/aviso-candidatura", **HTMX).text
    assert f'id="responder-pergunta-{vaga}"' in pagina
    assert f'id="faixa-pergunta-{vaga}"' in faixa
    ids = re.findall(r'\bid="([^"]+)"', pagina + faixa)
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    assert repetidos == []


# --- Um teste por linha da tabela 5.10 ---


def test_antes_da_primeira_execucao_redireciona(tmp_path: Path) -> None:
    painel = Painel(tmp_path, primeira=False)
    resposta = painel.get()
    assert (resposta.status_code, resposta.headers.get("location")) == (
        303,
        "/primeira-execucao/1",
    )
    with painel.con() as con:  # controle: concluída, a página abre
        gravar_config(con, "primeira_execucao_concluida", True)
    assert painel.get().status_code == 200


def test_banco_vazio_mostra_estado_vazio(tmp_path: Path) -> None:
    painel = Painel(tmp_path, semente=False)
    html = painel.pagina()
    buscar = CATALOGO["pt"]["execucao.buscar_agora"]
    assert f'Ainda não há vagas. Aperte "{buscar}" para fazer a primeira busca.' in _texto(html)
    assert _grupos(html) == ["A busca"]
    assert "Nenhuma busca completa ainda." in _texto(html)


def test_so_vagas_fechadas_com_candidatura_nao_e_vazio(tmp_path: Path) -> None:
    painel = Painel(tmp_path, semente=False)
    with painel.con() as con:
        inserir_vaga(con, status="candidatei", fechada_em=HORA.isoformat())
        salva = inserir_vaga(con, status="salva", fechada_em=HORA.isoformat())
        assert acoes.abriu_candidatura(con, salva, HORA)
    html = painel.pagina()
    assert "Ainda não há vagas" not in _texto(html)
    assert _grupos(html) == ["Hoje", "Candidaturas", "A busca", "O que aparece"]
    numeros = {r: int(n) for _, n, r in NUMERO_DE_HOJE.findall(html)}
    assert (numeros.get("Todas"), numeros.get("Salvas"), numeros.get("Candidatei")) == (0, 1, 1)
    assert f'id="responder-pergunta-{salva}"' in _para_responder(html)


def test_sem_busca_ativa_esconde_encaixe(painel: Painel) -> None:
    html = painel.pagina()  # controle: com a busca ativa, o Encaixe aparece
    assert 'aria-labelledby="panorama-aparece-encaixe"' in html
    assert "Contando a busca Python remoto." in _texto(html)
    painel.sql("UPDATE busca SET ativa = 0")
    html = painel.pagina()
    blocos = re.findall(r'aria-labelledby="panorama-aparece-(\w+)"', html)
    assert blocos == ["modalidade", "area", "fonte"]
    assert "Nenhuma busca ativa: o encaixe não aparece." in _texto(html)
    assert "Contando a busca" not in _texto(html)
    numeros = [h for h, _, _ in NUMERO_DE_HOJE.findall(html)]
    assert numeros and all("busca=" not in h for h in numeros)


def test_sem_busca_completa(painel: Painel) -> None:
    texto = painel.texto()
    assert "Nenhuma busca completa ainda." in texto
    assert "Próxima busca" not in texto
    painel.execucao(HORA - timedelta(hours=1))  # controle
    texto = painel.texto()
    assert "Última busca completa: 13/11/2026." in texto
    assert "Próxima busca automática por volta das 11:00." in texto


def test_sem_busca_completa_sem_frase_de_fontes_ok(painel: Painel) -> None:
    painel.so_ligadas("remotive", "himalayas")
    # todas em ok, mas numa execução que não é busca: nenhuma busca completa
    painel.execucao(
        HORA - timedelta(hours=1), ("remotive", "ok"), ("himalayas", "ok"), tipo="descoberta"
    )
    texto = painel.texto()
    assert "Nenhuma busca completa ainda." in texto
    assert "Todas as fontes funcionaram" not in texto
    assert "Fontes com problema" not in texto
    painel.execucao(HORA - timedelta(minutes=30))  # controle: com a busca completa, a frase vem
    assert "Todas as fontes funcionaram da última vez que rodaram." in painel.texto()


def test_sem_fonte_ligada_sem_frase_de_fontes_ok(painel: Painel) -> None:
    painel.so_ligadas("remotive")
    painel.execucao(HORA - timedelta(hours=1), ("remotive", "ok"))
    assert "Todas as fontes funcionaram da última vez que rodaram." in painel.texto()  # controle
    painel.sql("UPDATE fonte SET ligada = 0")
    assert "Todas as fontes funcionaram" not in painel.texto()


@pytest.mark.parametrize("estado", ["no_limite", "sem_execucao"])
def test_fonte_no_limite_ou_sem_execucao_sem_frase(painel: Painel, estado: str) -> None:
    painel.so_ligadas("remotive", "himalayas")
    linhas: list[tuple[str, str] | tuple[str, str, str]] = [("remotive", "ok")]
    if estado == "no_limite":
        linhas.append(("himalayas", "no_limite", "saude.cota"))
    painel.execucao(HORA - timedelta(hours=1), *linhas)
    texto = painel.texto()
    assert "Todas as fontes funcionaram" not in texto
    assert "Fontes com problema" not in texto
    # controle: a mesma fonte em ok mostra a frase
    painel.execucao(HORA - timedelta(minutes=30), ("himalayas", "ok"))
    assert "Todas as fontes funcionaram da última vez que rodaram." in painel.texto()


def test_buscando_agora(painel: Painel) -> None:
    painel.execucao(HORA - timedelta(hours=1))
    assert "Próxima busca automática" in painel.texto()  # controle
    assert "Buscando agora." not in painel.texto()
    painel.execucao(HORA - timedelta(minutes=1), concluir=False)
    texto = painel.texto()
    assert "Buscando agora." in texto
    assert "Próxima busca" not in texto


def test_proxima_com_relogio_que_voltou(painel: Painel) -> None:
    painel.execucao(HORA + timedelta(days=1))  # a última busca está no futuro
    texto = painel.texto()
    assert "Última busca completa: 14/11/2026." in texto
    assert "Próxima busca" not in texto
    painel.relogio(HORA + timedelta(days=1, hours=1))  # controle: o relógio em dia
    assert "Próxima busca automática por volta das 12:00." in painel.texto()


def test_fontes_todas_ok(painel: Painel) -> None:
    painel.so_ligadas("remotive", "himalayas")
    painel.execucao(HORA - timedelta(hours=1), ("remotive", "ok"), ("himalayas", "sem_mudanca"))
    html = _secao(painel.pagina(), "panorama-busca")
    assert "Todas as fontes funcionaram da última vez que rodaram." in _texto(html)
    assert "Fontes com problema" not in _texto(html)


def _cair_gmail(painel: Painel) -> None:
    with painel.con() as con:
        gravar_sessao(con, "conta", CONTA, "conectado", None, HORA - timedelta(hours=2))
        gravar_sessao(con, "conta", CONTA, "precisa_entrar", None, HORA - timedelta(hours=1))


def test_sem_contas_em_queda_sem_linha(painel: Painel) -> None:
    assert "Contas que precisam de você" not in painel.texto()
    _cair_gmail(painel)  # controle
    assert "Contas que precisam de você: 1" in painel.texto()


def test_contas_em_queda(painel: Painel) -> None:
    _cair_gmail(painel)
    html = _secao(painel.pagina(), "panorama-busca")
    assert "Contas que precisam de você: 1 Ver contas" in _texto(html)
    assert '<a href="/configuracoes/contas">Ver contas</a>' in html


def test_para_responder_vazio(painel: Painel) -> None:
    lista = _para_responder(painel.pagina())
    assert "Nenhuma pergunta esperando." in lista
    vaga = painel.abrir("usd", 1)  # controle
    lista = _para_responder(painel.pagina())
    assert "Nenhuma pergunta esperando." not in lista
    assert f'id="responder-pergunta-{vaga}"' in lista
