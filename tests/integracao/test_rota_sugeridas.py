"""Rotas das empresas sugeridas: lista, aprovar e descartar (plano T74, D71).

Sem rede: o `ClienteEducado` da rota usa o `httpx.MockTransport` de `app.state.transporte`.
"""

import json
import re
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from apoio.faixa import faixa, form_da_faixa
from apoio.relogio import RelogioFalso
from jobot.banco.cadastros import adicionar_empresa, remover_empresa
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.banco.sugeridas import gravar_sugestoes
from jobot.nucleo.coletores.descoberta_cc import Sugestao
from jobot.nucleo.modelo import Empresa
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47620
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ESTA_PAGINA = "/empresas/sugeridas"
HX = {"HX-Request": "true"}


class Painel:
    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            con.executemany(
                "INSERT INTO fonte (chave, leva, intervalo_min) VALUES (?, 'A', 60)",
                [("greenhouse",), ("gupy",), ("lever",)],
            )
            con.commit()
        self.pedidos: list[httpx.Request] = []
        self.gupy_fora = False
        self.gupy_html: str | None = None  # troca a página de carreira que o falso devolve
        self.app = criar_app(tmp_path, PORTA)
        self.relogio = RelogioFalso()
        self.app.state.relogio = self.relogio
        self.app.state.transporte = httpx.MockTransport(self._responder)
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

    def _responder(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if pedido.url.host.endswith(".gupy.io"):
            if self.gupy_fora:
                return httpx.Response(500)
            html = self.gupy_html or (FIXTURES / "gupy" / "pagina_carreira.html").read_text(
                encoding="utf-8"
            )
            return httpx.Response(200, text=html)
        raise AssertionError(f"teste não fala com {pedido.url}")

    def sugerir(self, fonte: str, identificador: str, url: str | None = None) -> int:
        url = url or f"https://exemplo.test/{identificador}"
        with closing(abrir(self.banco)) as con:
            gravar_sugestoes(con, [Sugestao(fonte, identificador, url)], self.relogio.agora())
            return int(
                con.execute(
                    "SELECT id FROM empresa_sugerida WHERE identificador = ?", (identificador,)
                ).fetchone()[0]
            )

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def empresas(self) -> list[tuple[Any, ...]]:
        return self.sql(
            "SELECT fonte, identificador, nome, parametros, ativa, removida_em, origem"
            " FROM empresa ORDER BY id"
        )

    def estado(self, id_: int) -> str:
        return str(self.sql("SELECT estado FROM empresa_sugerida WHERE id = ?", id_)[0][0])

    def post(self, url: str, dados: dict[str, Any] | None = None) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **(dados or {})})


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def test_lista_so_as_pendentes(painel: Painel) -> None:
    painel.sugerir("greenhouse", "pendente-a")
    painel.sugerir("lever", "pendente-b")
    aprovada = painel.sugerir("greenhouse", "ja-aprovada")
    descartada = painel.sugerir("greenhouse", "ja-descartada")
    painel.post(f"{ESTA_PAGINA}/{aprovada}/aprovar")
    painel.post(f"{ESTA_PAGINA}/{descartada}/descartar")

    r = painel.http.get(ESTA_PAGINA)

    assert r.status_code == 200
    assert "pendente-a" in r.text
    assert "pendente-b" in r.text
    assert "ja-aprovada" not in r.text
    assert "ja-descartada" not in r.text


def test_sem_pendentes_mostra_o_aviso_de_vazio(painel: Painel) -> None:
    r = painel.http.get(ESTA_PAGINA)
    assert r.status_code == 200
    assert "Nenhuma empresa sugerida" in r.text


def test_aprovar_cria_a_empresa_da_descoberta_e_a_sugestao_some(painel: Painel) -> None:
    id_ = painel.sugerir("greenhouse", "vitta")

    r = painel.post(f"{ESTA_PAGINA}/{id_}/aprovar")

    assert r.status_code == 303
    assert r.headers["location"] == ESTA_PAGINA
    assert painel.empresas() == [("greenhouse", "vitta", "vitta", "{}", 1, None, "descoberta")]
    assert painel.estado(id_) == "aprovada"
    assert "vitta" not in painel.http.get(ESTA_PAGINA).text
    assert painel.pedidos == []  # fora da Gupy, aprovar não faz pedido
    assert "vitta" in painel.http.get("/empresas").text  # a empresa aparece na tela Empresas


def test_aprovar_uma_a_uma_deixa_a_outra_pendente(painel: Painel) -> None:
    a = painel.sugerir("greenhouse", "alfa")
    b = painel.sugerir("greenhouse", "beta")

    painel.post(f"{ESTA_PAGINA}/{a}/aprovar")

    assert [e[1] for e in painel.empresas()] == ["alfa"]
    assert painel.estado(b) == "pendente"
    texto = painel.http.get(ESTA_PAGINA).text
    assert "beta" in texto
    assert "alfa" not in texto


def test_aprovar_gupy_grava_o_career_page_name_que_a_pagina_traz(painel: Painel) -> None:
    id_ = painel.sugerir("gupy", "agriness")

    r = painel.post(f"{ESTA_PAGINA}/{id_}/aprovar")

    assert r.status_code == 303
    [(fonte, ident, nome, parametros, ativa, removida, origem)] = painel.empresas()
    assert (fonte, ident, nome, ativa, removida, origem) == (
        "gupy",
        "agriness",
        "Agriness",
        1,
        None,
        "descoberta",
    )
    assert json.loads(parametros) == {"careerPageName": "Agriness"}
    assert [p.url.host for p in painel.pedidos] == ["agriness.gupy.io"]


def test_aprovar_gupy_com_a_fonte_fora_mantem_a_sugestao_pendente(painel: Painel) -> None:
    id_ = painel.sugerir("gupy", "agriness")
    painel.gupy_fora = True

    r = painel.post(f"{ESTA_PAGINA}/{id_}/aprovar")

    assert r.status_code == 502
    assert "Não deu para falar com a fonte" in r.text
    assert "agriness" in r.text  # a sugestão segue na lista
    assert painel.estado(id_) == "pendente"
    assert painel.empresas() == []


def test_aprovar_gupy_pagina_invalida_da_422(painel: Painel) -> None:
    id_ = painel.sugerir("gupy", "agriness")
    painel.gupy_html = (
        "<html><body>sem __NEXT_DATA__</body></html>"  # o resolver recusa: ValueError
    )

    r = painel.post(f"{ESTA_PAGINA}/{id_}/aprovar")

    assert r.status_code == 422
    assert "não parece ser de uma empresa da Gupy" in r.text
    assert "Não deu para falar com a fonte" not in r.text  # a fonte está no ar
    assert "agriness" in r.text  # a sugestão segue na lista
    assert painel.estado(id_) == "pendente"
    assert painel.empresas() == []


def test_aprovar_gupy_grava_identificador_do_resolver(painel: Painel) -> None:
    id_ = painel.sugerir("gupy", "Agriness")

    r = painel.post(f"{ESTA_PAGINA}/{id_}/aprovar")

    assert r.status_code == 303
    assert [e[1] for e in painel.empresas()] == ["agriness"]  # minúsculas, como o resolver (D45)


def test_descartar_some_da_lista_e_nao_cria_empresa(painel: Painel) -> None:
    id_ = painel.sugerir("greenhouse", "vitta")

    r = painel.post(f"{ESTA_PAGINA}/{id_}/descartar")

    assert r.status_code == 303
    assert painel.estado(id_) == "descartada"
    assert painel.empresas() == []
    assert "vitta" not in painel.http.get(ESTA_PAGINA).text


@pytest.mark.parametrize("acao", ["aprovar", "descartar"])
def test_sugestao_inexistente_ou_ja_decidida_e_404(painel: Painel, acao: str) -> None:
    id_ = painel.sugerir("greenhouse", "vitta")
    assert painel.post(f"{ESTA_PAGINA}/999/{acao}").status_code == 404
    painel.post(f"{ESTA_PAGINA}/{id_}/descartar")
    assert painel.estado(id_) == "descartada"
    assert painel.post(f"{ESTA_PAGINA}/{id_}/{acao}").status_code == 404


@pytest.mark.parametrize("acao", ["aprovar", "descartar", "restaurar"])
def test_id_fora_da_faixa_e_422(painel: Painel, acao: str) -> None:
    assert painel.post(f"{ESTA_PAGINA}/0/{acao}").status_code == 422
    assert painel.post(f"{ESTA_PAGINA}/{2**63}/{acao}").status_code == 422


def test_post_sem_token_csrf_e_403(painel: Painel) -> None:
    id_ = painel.sugerir("greenhouse", "vitta")
    r = painel.http.post(f"{ESTA_PAGINA}/{id_}/aprovar")
    assert r.status_code == 403
    assert painel.estado(id_) == "pendente"


def _sugerir_empresa_removida(painel: Painel) -> int:
    """Sugestão pendente de uma empresa que a pessoa cadastrou e removeu depois (D71)."""
    id_ = painel.sugerir("greenhouse", "vitta")
    with closing(abrir(painel.banco)) as con:
        empresa = adicionar_empresa(
            con, Empresa(nome="Vitta", fonte="greenhouse", identificador="Vitta", origem="pessoa")
        )
        remover_empresa(con, empresa, painel.relogio.agora())
    return id_


def test_sugestao_de_empresa_removida_avisa_com_a_data_da_remocao(painel: Painel) -> None:
    _sugerir_empresa_removida(painel)

    texto = painel.http.get(ESTA_PAGINA).text

    assert "Você removeu esta empresa em 13/11/2026" in texto


def test_aviso_da_removida_sai_em_ingles_com_a_data_em_ingles(painel: Painel) -> None:
    _sugerir_empresa_removida(painel)

    texto = painel.http.get(ESTA_PAGINA, headers={"Accept-Language": "en"}).text

    assert "You removed this company on 11/13/2026" in texto


def test_sugestao_sem_remocao_nao_leva_o_aviso(painel: Painel) -> None:
    painel.sugerir("greenhouse", "outra")
    _sugerir_empresa_removida(painel)

    texto = painel.http.get(ESTA_PAGINA).text

    assert texto.count("Você removeu esta empresa") == 1  # só a do Vitta


def test_aprovar_a_removida_nao_a_reativa(painel: Painel) -> None:
    id_ = _sugerir_empresa_removida(painel)
    antes = painel.empresas()

    r = painel.post(f"{ESTA_PAGINA}/{id_}/aprovar")

    assert r.status_code == 303
    assert painel.empresas() == antes  # removida_em e ativa ficam como estavam
    assert painel.empresas()[0][5] is not None
    assert painel.estado(id_) == "aprovada"
    assert "Vitta" not in painel.http.get("/empresas").text  # segue removida


def test_aprovar_removida_nao_pede_a_gupy(painel: Painel) -> None:
    id_ = painel.sugerir("gupy", "agriness")
    with closing(abrir(painel.banco)) as con:
        empresa = adicionar_empresa(
            con, Empresa(nome="Agriness", fonte="gupy", identificador="agriness", origem="pessoa")
        )
        remover_empresa(con, empresa, painel.relogio.agora())
    painel.gupy_fora = True  # com a Gupy fora do ar, o pedido desnecessário travaria a aprovação
    antes = painel.empresas()

    r = painel.post(f"{ESTA_PAGINA}/{id_}/aprovar")

    assert r.status_code == 303
    assert painel.pedidos == []
    assert painel.empresas() == antes
    assert painel.estado(id_) == "aprovada"


def test_url_de_exemplo_so_vira_link_se_for_http(painel: Painel) -> None:
    painel.sugerir("greenhouse", "boa", "https://boards.greenhouse.io/boa")
    painel.sugerir("greenhouse", "ruim", "javascript:alert(1)")

    texto = painel.http.get(ESTA_PAGINA).text

    assert 'href="https://boards.greenhouse.io/boa"' in texto
    assert 'rel="noopener noreferrer"' in texto
    assert 'href="javascript:' not in texto


def test_menu_leva_para_a_tela_nova_com_sugestao_pendente(painel: Painel) -> None:
    # a lateral só mostra Sugeridas com sugestão pendente (T251)
    assert 'href="/empresas/sugeridas"' not in painel.http.get("/vagas").text
    painel.sugerir("greenhouse", "boa", "https://boards.greenhouse.io/boa")
    assert 'href="/empresas/sugeridas"' in painel.http.get("/vagas").text


def _por_htmx(painel: Painel, acao: str, id_: int, idioma: str = "pt") -> Any:
    return painel.http.post(
        f"{ESTA_PAGINA}/{id_}/{acao}",
        data={CAMPO_CSRF: painel.token, "voltar": ESTA_PAGINA},
        headers={**HX, "Accept-Language": idioma},
    )


def _corpo(html: str) -> str:
    """A lista que veio por OOB (`#corpo-sugeridas`, trocado por dentro)."""
    achou = re.search(r'<div\b[^>]*\bid="corpo-sugeridas"[^>]*>.*', html, re.S)
    assert achou, "sem a lista na resposta"
    assert 'hx-swap-oob="innerHTML"' in re.match(r"<div\b[^>]*>", achou.group(0))[0]  # type: ignore[index]
    return achou.group(0)


def test_descartar_traz_a_faixa_com_restaurar(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    painel.sugerir("greenhouse", "beta")

    r = _por_htmx(painel, "descartar", alfa)

    assert r.status_code == 200
    f = faixa(r.text)
    assert "Sugestão descartada" in f
    form = form_da_faixa(f, f"{ESTA_PAGINA}/{alfa}/restaurar")
    assert 'method="post"' in form and f'name="{CAMPO_CSRF}" value="{painel.token}"' in form
    assert ">Desfazer<" in form
    assert 'hx-target="this"' in form and 'hx-swap="none"' in form
    assert 'aria-label="Fechar"' in f
    assert f"{ESTA_PAGINA}/{alfa}/descartar" not in f  # o Refazer só aparece depois do Desfazer
    corpo = _corpo(r.text)  # a lista volta sem a linha, sem recarregar a página
    assert "alfa" not in corpo and "beta" in corpo
    assert painel.estado(alfa) == "descartada"


def _lateral_onde(html: str) -> str:
    """O item "Onde buscar" da lateral que veio por OOB (`#lateral-onde`, trocado no lugar)."""
    achou = re.search(r'<ul\b[^>]*\bid="lateral-onde"[^>]*>.*?</ul>', html, re.S)
    assert achou, "sem a lateral na resposta"
    assert 'hx-swap-oob="true"' in re.match(r"<ul\b[^>]*>", achou.group(0))[0]  # type: ignore[index]
    return achou.group(0)


def test_descartar_traz_a_lateral_com_a_contagem_nova(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    painel.sugerir("greenhouse", "beta")

    lateral = _lateral_onde(_por_htmx(painel, "descartar", alfa).text)

    assert re.search(
        r'href="/empresas/sugeridas"[^>]*>.*?<span class="contagem">1</span>', lateral, re.S
    )
    assert 'aria-current="page"' in lateral.split('href="/empresas/sugeridas"')[1].split("</a>")[0]


def test_descartar_a_ultima_tira_sugeridas_da_lateral_e_marca_empresas(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")

    lateral = _lateral_onde(_por_htmx(painel, "descartar", alfa).text)

    assert 'href="/empresas/sugeridas"' not in lateral
    assert re.search(
        r'href="/empresas"[^>]*aria-current="true"', lateral
    )  # área marcada, página não


def test_restaurar_traz_sugeridas_de_volta_na_lateral(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    painel.post(f"{ESTA_PAGINA}/{alfa}/descartar")

    lateral = _lateral_onde(_por_htmx(painel, "restaurar", alfa).text)

    assert re.search(
        r'href="/empresas/sugeridas"[^>]*>.*?<span class="contagem">1</span>', lateral, re.S
    )


def test_descartar_e_restaurar_avisam_o_app_depois_do_settle(painel: Painel) -> None:
    # o app.js devolve o foco ao botão da faixa ou à lista só com este aviso (depois do settle)
    alfa = painel.sugerir("greenhouse", "alfa")
    r = _por_htmx(painel, "descartar", alfa)
    assert json.loads(r.headers["HX-Trigger-After-Settle"]) == {"lista-mudou": {"linha": ""}}
    r = _por_htmx(painel, "restaurar", alfa)
    assert json.loads(r.headers["HX-Trigger-After-Settle"]) == {
        "lista-mudou": {"linha": f"sugerida-{alfa}"}
    }


def test_a_lista_marca_o_foco_a_devolver(painel: Painel) -> None:
    painel.sugerir("greenhouse", "alfa")
    assert 'id="corpo-sugeridas" data-lista-desfazer' in painel.http.get(ESTA_PAGINA).text


def test_descartar_em_ingles_traz_a_faixa_em_ingles(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    f = faixa(_por_htmx(painel, "descartar", alfa, "en").text)
    assert "Suggestion discarded" in f and ">Undo<" in f


def test_descartar_sem_htmx_volta_para_a_lista_sem_faixa(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    r = painel.post(f"{ESTA_PAGINA}/{alfa}/descartar")
    assert (r.status_code, r.headers["location"]) == (303, ESTA_PAGINA)
    assert "faixa" not in r.text


def test_restaurar_volta_a_pendente_e_traz_a_faixa_com_descartar(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    painel.post(f"{ESTA_PAGINA}/{alfa}/descartar")

    r = _por_htmx(painel, "restaurar", alfa)

    assert r.status_code == 200
    assert painel.estado(alfa) == "pendente"
    f = faixa(r.text)
    assert "Sugestão restaurada" in f
    form = form_da_faixa(f, f"{ESTA_PAGINA}/{alfa}/descartar")  # o Refazer é a ação de hoje
    assert ">Refazer<" in form and f"{ESTA_PAGINA}/{alfa}/restaurar" not in f
    achou = re.search(rf'<li\b[^>]*id="sugerida-{alfa}"[^>]*>', _corpo(r.text))
    assert achou and "linha-volta" in achou.group(0)  # a linha volta destacada por 1 s (CSS)
    assert 'class="linha-busca' in achou.group(0)
    assert painel.sql("SELECT count(*) FROM empresa_sugerida") == [(1,)]  # mesma linha, sem cópia


def test_restaurar_sem_htmx_volta_para_a_lista(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    painel.post(f"{ESTA_PAGINA}/{alfa}/descartar")
    r = painel.post(f"{ESTA_PAGINA}/{alfa}/restaurar")
    assert (r.status_code, r.headers["location"]) == (303, ESTA_PAGINA)
    assert painel.estado(alfa) == "pendente"
    assert "alfa" in painel.http.get(ESTA_PAGINA).text


def test_restaurar_sem_csrf_da_403(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    painel.post(f"{ESTA_PAGINA}/{alfa}/descartar")
    r = painel.http.post(f"{ESTA_PAGINA}/{alfa}/restaurar", headers=HX)
    assert r.status_code == 403
    assert painel.estado(alfa) == "descartada"


def test_restaurar_id_que_nao_existe_da_404(painel: Painel) -> None:
    assert painel.post(f"{ESTA_PAGINA}/999/restaurar").status_code == 404
    assert _por_htmx(painel, "restaurar", 999).status_code == 404


def test_restaurar_sugestao_aprovada_da_404_e_nao_a_mexe(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa")
    painel.post(f"{ESTA_PAGINA}/{alfa}/aprovar")
    assert painel.post(f"{ESTA_PAGINA}/{alfa}/restaurar").status_code == 404
    assert painel.estado(alfa) == "aprovada"


def test_lista_agrupada_com_o_alvo_do_menu_e_descartar_por_htmx(painel: Painel) -> None:
    alfa = painel.sugerir("greenhouse", "alfa", "https://boards.greenhouse.io/alfa")
    painel.sugerir("greenhouse", "ruim", "javascript:alert(1)")
    html = painel.http.get(ESTA_PAGINA).text

    assert re.search(r'<ul class="lista-agrupada" id="lista-sugeridas"', html)
    assert 'id="corpo-sugeridas"' in html
    linha = re.search(rf'<li\b[^>]*id="sugerida-{alfa}"[^>]*>', html)
    assert linha and 'class="linha-busca"' in linha.group(0)
    assert 'data-menu="menu-sugerida"' in linha.group(0) and f'data-id="{alfa}"' in linha.group(0)
    assert 'data-site="https://boards.greenhouse.io/alfa"' in linha.group(0)
    ruim = re.search(r'<li\b[^>]*id="sugerida-\d+"[^>]*data-site="javascript[^>]*>', html)
    assert ruim is None  # a URL que não é http(s) não vai para o menu
    form = re.search(
        rf'<form\b[^>]*action="{ESTA_PAGINA}/{alfa}/descartar"[^>]*>', html
    )  # sem pergunta: HTMX por baixo, a faixa traz o Desfazer
    assert form and f'hx-post="{ESTA_PAGINA}/{alfa}/descartar"' in form.group(0)
    assert 'hx-target="this"' in form.group(0) and 'hx-swap="none"' in form.group(0)
    assert '<li class="cartao' not in html


def test_menu_da_lista_tem_as_acoes_da_linha(painel: Painel) -> None:
    painel.sugerir("greenhouse", "alfa")
    html = painel.http.get(ESTA_PAGINA).text
    menu = re.search(
        r'<div id="menu-sugerida"[^>]*data-menu-contexto.*?</div>\s*<div id="menu-sugerida-aviso"',
        html,
        re.DOTALL,
    )
    assert menu
    for modelo in (f"{ESTA_PAGINA}/{{id}}/aprovar", f"{ESTA_PAGINA}/{{id}}/descartar", "{site}"):
        assert modelo in menu.group(0), modelo
    assert 'data-requer="site"' in menu.group(0)
    assert re.search(r'data-modelo-acao="[^"]*/descartar"[^>]*hx-post=', menu.group(0))
    assert len(re.findall(r'role="group"', menu.group(0))) <= 3
    assert 'aria-label="Ações da sugestão"' in menu.group(0)
