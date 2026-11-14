"""Rotas das empresas sugeridas: lista, aprovar e descartar (plano T74, D71).

Sem rede: o `ClienteEducado` da rota usa o `httpx.MockTransport` de `app.state.transporte`.
"""

import json
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

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
            html = (FIXTURES / "gupy" / "pagina_carreira.html").read_text(encoding="utf-8")
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


@pytest.mark.parametrize("acao", ["aprovar", "descartar"])
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


def test_url_de_exemplo_so_vira_link_se_for_http(painel: Painel) -> None:
    painel.sugerir("greenhouse", "boa", "https://boards.greenhouse.io/boa")
    painel.sugerir("greenhouse", "ruim", "javascript:alert(1)")

    texto = painel.http.get(ESTA_PAGINA).text

    assert 'href="https://boards.greenhouse.io/boa"' in texto
    assert 'rel="noopener noreferrer"' in texto
    assert 'href="javascript:' not in texto


def test_menu_leva_para_a_tela_nova(painel: Painel) -> None:
    texto = painel.http.get("/vagas").text
    assert 'href="/empresas/sugeridas"' in texto
