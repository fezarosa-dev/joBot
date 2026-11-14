"""Rotas das empresas: lista, testar, adicionar, ligar, desligar e remover (plano T51).

Sem rede: o `ClienteEducado` da rota usa o `httpx.MockTransport` de `app.state.transporte` e o
relógio falso; o servidor falso responde com os exemplos capturados em `tests/fixtures`.
"""

import json
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.coletores.base import ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import HttpEducado
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.painel.app import criar_app
from jobot.painel.rotas import empresas as rota_empresas
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47617
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
AGIBANK = "Agibank (quadro de vagas futuras)"
AVISO_ZERO = "O identificador pode estar errado"
ETIQUETA = "Banco de talentos"
JSON_HDR = {"Content-Type": "application/json"}


def _arquivo(caminho: str) -> str:
    return (FIXTURES / caminho).read_text(encoding="utf-8")


def _servidor(pedidos: list[httpx.Request]) -> httpx.MockTransport:
    """Greenhouse (`vazia` sem vagas, `inexistente` 404) e Gupy (página, lista e `fora` com 500)."""

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        url = pedido.url
        if url.host == "boards-api.greenhouse.io":
            token = url.path.split("/")[3]
            if token == "inexistente":
                return httpx.Response(404, text=_arquivo("greenhouse/nao_encontrado.json"))
            arquivo = "vazio" if token == "vazia" else "normal"
            return httpx.Response(
                200, text=_arquivo(f"greenhouse/{arquivo}.json"), headers=JSON_HDR
            )
        if url.host == "portal.gupy.io":
            arquivo = "vazio" if url.params.get("careerPageName") == "Vazia" else "normal"
            return httpx.Response(200, text=_arquivo(f"gupy/{arquivo}.json"), headers=JSON_HDR)
        if url.host == "fora.gupy.io":
            return httpx.Response(500)
        if url.host.endswith(".gupy.io"):
            return httpx.Response(200, text=_arquivo("gupy/pagina_carreira.html"))
        raise AssertionError(f"teste não fala com {url}")

    return httpx.MockTransport(responder)


class Painel:
    def __init__(self, tmp_path: Path, *, semeado: bool = False) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            if semeado:
                cadastros.semear(con)
            else:  # só as fontes: o cadastro recusa fonte que não está na tabela
                con.executemany(
                    "INSERT INTO fonte (chave, leva, intervalo_min) VALUES (?, 'A', 60)",
                    [("greenhouse",), ("gupy",), ("lever",)],
                )
                con.commit()
        self.pedidos: list[httpx.Request] = []
        self.app: FastAPI = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso()
        self.app.state.transporte = _servidor(self.pedidos)
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

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

    def get(self, url: str) -> Any:
        return self.http.get(url)

    def post(self, url: str, dados: dict[str, Any] | None = None) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **(dados or {})})

    def testar(self, fonte: str, endereco: str, nome: str = "") -> Any:
        return self.post("/empresas/testar", {"fonte": fonte, "endereco": endereco, "nome": nome})

    def adicionar(self, fonte: str, endereco: str, nome: str = "") -> Any:
        return self.post("/empresas", {"fonte": fonte, "endereco": endereco, "nome": nome})


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def test_testar_mostra_a_contagem_antes_de_salvar(painel: Painel) -> None:
    r = painel.testar("greenhouse", "https://boards.greenhouse.io/vitta")
    assert r.status_code == 200
    assert "Vagas encontradas: 3" in r.text
    assert AVISO_ZERO not in r.text
    assert painel.empresas() == []  # testar não grava nada


def test_url_colada_resolve_o_identificador_sem_mudar_a_caixa(painel: Painel) -> None:
    entradas = [
        "  https://boards.greenhouse.io/Vitta/  ",
        "job-boards.greenhouse.io/Vitta",
        "https://boards.greenhouse.io/embed/job_board?for=Vitta",
        "https://boards-api.greenhouse.io/v1/boards/Vitta/jobs",
        " Vitta ",
        "HTTPS://Boards.Greenhouse.IO/Vitta",
    ]
    for entrada in entradas:
        r = painel.adicionar("greenhouse", entrada)
        assert r.status_code == 303, entrada
    assert [(e[0], e[1]) for e in painel.empresas()] == [("greenhouse", "Vitta")]  # uma linha só


@pytest.mark.parametrize("token", ["Vitta", "VITTA", "vitta", "NielsenIQ"])
def test_rota_nunca_muda_a_caixa_do_identificador(painel: Painel, token: str) -> None:
    painel.adicionar("greenhouse", f"https://boards.greenhouse.io/{token}/")
    assert painel.empresas()[0][1] == token
    painel.testar("greenhouse", f"https://boards.greenhouse.io/{token}/")
    assert painel.pedidos[-1].url.path == f"/v1/boards/{token}/jobs"  # o testar pede como veio


def test_adicionar_grava_com_origem_pessoa_e_nome_dado(painel: Painel) -> None:
    painel.adicionar("greenhouse", "vitta", nome="Vitta Saúde")
    fonte, ident, nome, parametros, ativa, removida, origem = painel.empresas()[0]
    assert (fonte, ident, nome, json.loads(parametros), ativa, removida, origem) == (
        "greenhouse",
        "vitta",
        "Vitta Saúde",
        {},
        1,
        None,
        "pessoa",
    )


def test_adicionar_sem_nome_usa_o_identificador(painel: Painel) -> None:
    painel.adicionar("greenhouse", "vitta")
    assert painel.empresas()[0][2] == "vitta"


class _Falso:
    """Coletor falso: guarda o contexto e o escopo e prova que `coletar` roda na mesma instância."""

    chave = "greenhouse"
    nome = "Falso"
    leva = "A"
    hosts: tuple[str, ...] = ()
    credito_obrigatorio = False
    intervalo_min = None
    max_pedidos = None
    espera_s = 1.0
    por_escopo: Mapping[str, Any] = {}

    def __init__(self) -> None:
        self.contextos: list[ContextoColeta] = []
        self.coletados: list[str] = []
        self.vistos_em_escopos: set[str] = set()

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        self.contextos.append(ctx)
        self.vistos_em_escopos = {"montado-por-escopos"}
        return ["montado-por-escopos|BR", "segundo-escopo"]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        assert self.vistos_em_escopos == {"montado-por-escopos"}  # estado de `escopos`, D50
        self.coletados.append(escopo)
        vaga = VagaColetada(
            fonte="greenhouse",
            escopo=escopo,
            url=f"https://exemplo.test/{len(self.coletados)}",
            titulo="Vaga",
            empresa="Falsa",
            descricao_formato="texto",
            descricao="Descrição.",
        )
        return ResultadoEscopo((vaga,), "ok", None, 1)

    async def detalhar(self, item: Any, http: HttpEducado) -> None:
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        return {"identificador": identificador.strip(), "extra": "x"}


def test_testar_pega_os_escopos_do_coletor_e_coleta_na_mesma_instancia(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    falso = _Falso()
    monkeypatch.setattr(rota_empresas, "_coletores", lambda: {"greenhouse": falso})
    r = painel.testar("greenhouse", " Vitta ", nome="Vitta Saúde")
    assert r.status_code == 200
    assert falso.coletados == ["montado-por-escopos|BR", "segundo-escopo"]  # nada montado à mão
    (ctx,) = falso.contextos
    assert list(ctx.termos) == [] and list(ctx.paises) == []
    (empresa,) = ctx.empresas
    assert (empresa.nome, empresa.fonte, empresa.identificador) == (
        "Vitta Saúde",
        "greenhouse",
        "Vitta",
    )
    assert dict(empresa.parametros) == {"extra": "x"}
    assert "Vagas encontradas: 2" in r.text  # soma dos escopos


def test_testar_nao_deixa_o_estado_do_escopos_no_coletor_compartilhado(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    falso = _Falso()
    monkeypatch.setattr(rota_empresas, "_coletores", lambda: {"greenhouse": falso})
    assert painel.testar("greenhouse", "Vitta").status_code == 200
    assert falso.coletados  # o teste coletou de fato
    # `escopos` rodou numa cópia: o estado do coletor que a busca real usa não troca (Lever, Ashby)
    assert falso.vistos_em_escopos == set()


def test_gupy_grava_o_career_page_name_do_resolver(painel: Painel) -> None:
    r = painel.adicionar("gupy", "https://agriness.gupy.io/")
    assert r.status_code == 303
    fonte, ident, nome, parametros, *_ = painel.empresas()[0]
    assert (fonte, ident, nome) == ("gupy", "agriness", "Agriness")  # nome padrão: o da página
    assert json.loads(parametros) == {"careerPageName": "Agriness"}


def test_gupy_testar_coleta_com_o_career_page_name(painel: Painel) -> None:
    r = painel.testar("gupy", "agriness.gupy.io")
    assert "Vagas encontradas: 4" in r.text
    lista = [p for p in painel.pedidos if p.url.host == "portal.gupy.io"]
    assert [p.url.params.get("careerPageName") for p in lista] == ["Agriness"]
    assert painel.empresas() == []


def test_adicionar_sobre_empresa_existente_preserva_os_parametros(painel: Painel) -> None:
    with closing(abrir(painel.banco)) as con:
        cadastros.adicionar_empresa(
            con,
            Empresa(
                nome="Antigo",
                fonte="gupy",
                identificador="agriness",
                parametros={"careerPageName": "Velho", "outro": "fica"},
            ),
        )
    painel.adicionar("gupy", "agriness.gupy.io", nome="Agriness")
    (linha,) = painel.empresas()
    assert json.loads(linha[3]) == {"careerPageName": "Agriness", "outro": "fica"}
    assert linha[2] == "Agriness"


def test_adicionar_sobre_empresa_removida_preserva_os_parametros_e_reativa(
    painel: Painel,
) -> None:
    with closing(abrir(painel.banco)) as con:
        id_ = cadastros.adicionar_empresa(
            con,
            Empresa(
                nome="Agriness",
                fonte="gupy",
                identificador="agriness",
                parametros={"outro": "fica"},
            ),
        )
    painel.post(f"/empresas/{id_}/remover")
    assert painel.empresas()[0][5] is not None
    painel.adicionar("gupy", "agriness.gupy.io")
    (linha,) = painel.empresas()
    assert json.loads(linha[3]) == {"careerPageName": "Agriness", "outro": "fica"}
    assert (linha[4], linha[5]) == (1, None)


def test_readicionar_sem_nome_mantem_o_nome_gravado_e_com_nome_troca(painel: Painel) -> None:
    painel.adicionar("greenhouse", "vitta", nome="Vitta Curada")
    (id_,) = [e[0] for e in painel.sql("SELECT id FROM empresa")]
    painel.post(f"/empresas/{id_}/remover")
    painel.adicionar("greenhouse", "vitta")  # campo nome vazio, linha removida
    assert [(e[2], e[4], e[5]) for e in painel.empresas()] == [("Vitta Curada", 1, None)]
    painel.adicionar("greenhouse", "vitta")  # linha existente e ativa
    assert painel.empresas()[0][2] == "Vitta Curada"
    painel.adicionar("greenhouse", "vitta", nome="Outro Nome")  # nome dado sobrescreve
    assert painel.empresas()[0][2] == "Outro Nome"


def test_readicionar_o_agibank_sem_nome_mantem_a_etiqueta(tmp_path: Path) -> None:
    painel = Painel(tmp_path, semeado=True)
    (id_,) = [e[0] for e in painel.sql("SELECT id FROM empresa WHERE nome = ?", AGIBANK)]
    painel.post(f"/empresas/{id_}/remover")
    painel.adicionar("greenhouse", "agibankvagasfuturas")
    do_agibank = [
        c for c in painel.get("/empresas").text.split('<li class="cartao')[1:] if AGIBANK in c
    ]
    assert len(do_agibank) == 1 and ETIQUETA in do_agibank[0]


def _servidor_gupy_vazia(pedidos: list[httpx.Request]) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        if pedido.url.host == "portal.gupy.io":
            return httpx.Response(200, text=_arquivo("gupy/vazio.json"), headers=JSON_HDR)
        return httpx.Response(200, text=_arquivo("gupy/pagina_carreira.html"))

    return httpx.MockTransport(responder)


def test_testar_com_zero_vagas_avisa_que_o_identificador_pode_estar_errado(
    painel: Painel,
) -> None:
    r = painel.testar("greenhouse", "vazia")
    assert r.status_code == 200
    assert "Vagas encontradas: 0" in r.text
    assert AVISO_ZERO in r.text


def test_testar_gupy_com_zero_vagas_tambem_avisa(painel: Painel) -> None:
    painel.app.state.transporte = _servidor_gupy_vazia(painel.pedidos)
    r = painel.testar("gupy", "agriness.gupy.io")
    assert "Vagas encontradas: 0" in r.text
    assert AVISO_ZERO in r.text


def test_testar_com_vagas_nao_mostra_o_aviso_de_zero(painel: Painel) -> None:
    r = painel.testar("gupy", "agriness.gupy.io")
    assert AVISO_ZERO not in r.text


def test_testar_empresa_inexistente_mostra_o_motivo_sem_o_aviso_de_zero(painel: Painel) -> None:
    r = painel.testar("greenhouse", "inexistente")
    assert r.status_code == 200
    assert "Empresa não encontrada na fonte" in r.text
    assert AVISO_ZERO not in r.text
    assert painel.empresas() == []


def test_endereco_que_o_resolver_recusa_volta_422_com_o_texto_e_sem_pedido(
    painel: Painel,
) -> None:
    for rota in ("testar", "adicionar"):
        r = getattr(painel, rota)("greenhouse", "https://exemplo.com/vagas?x=1")
        assert r.status_code == 422
        assert 'role="alert"' in r.text
        assert "https://exemplo.com/vagas?x=1" in r.text  # o texto volta no campo
    assert painel.pedidos == [] and painel.empresas() == []


def test_endereco_vazio_422(painel: Painel) -> None:
    assert painel.testar("greenhouse", "   ").status_code == 422
    assert painel.adicionar("greenhouse", "").status_code == 422


def test_endereco_vazio_cita_o_nome_da_fonte_e_nao_a_chave(painel: Painel) -> None:
    for rota in ("testar", "adicionar"):
        r = getattr(painel, rota)("gupy", " ")
        assert "quadro de vagas do Gupy." in r.text


def test_nome_longo_demais_422(painel: Painel) -> None:
    assert painel.adicionar("greenhouse", "vitta", nome="x" * 101).status_code == 422
    assert painel.empresas() == []


@pytest.mark.parametrize("fonte", ["remotive", "nao_existe", "", "himalayas"])
def test_fonte_que_nao_e_de_empresa_422_seco(painel: Painel, fonte: str) -> None:
    for rota in ("testar", "adicionar"):
        assert getattr(painel, rota)(fonte, "vitta").status_code == 422
    assert painel.empresas() == []


def test_erro_do_banco_na_gravacao_vira_422(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    def recusa(con: Any, empresa: Empresa) -> int:
        raise ValueError("recusada")

    monkeypatch.setattr(rota_empresas, "adicionar_empresa", recusa)
    assert painel.adicionar("greenhouse", "vitta").status_code == 422


def test_fonte_fora_do_ar_no_resolver_vira_502_com_o_motivo(painel: Painel) -> None:
    r = painel.adicionar("gupy", "https://fora.gupy.io/")
    assert r.status_code == 502
    assert "Erro de rede ao falar com a fonte" in r.text
    assert painel.empresas() == []


def test_desligar_ligar_e_remover(painel: Painel) -> None:
    painel.adicionar("greenhouse", "vitta", nome="Vitta")
    id_ = int(painel.sql("SELECT id FROM empresa")[0][0])
    assert painel.post(f"/empresas/{id_}/desligar").status_code == 303
    assert painel.sql("SELECT ativa FROM empresa") == [(0,)]
    assert "Desligada" in painel.get("/empresas").text
    assert painel.post(f"/empresas/{id_}/ligar").status_code == 303
    assert painel.sql("SELECT ativa FROM empresa") == [(1,)]
    assert painel.post(f"/empresas/{id_}/remover").status_code == 303
    (linha,) = painel.sql("SELECT removida_em FROM empresa")  # a linha fica (DR-68)
    assert linha[0] is not None
    assert "Vitta" not in painel.get("/empresas").text


def test_id_inexistente_404_e_fora_da_faixa_422(painel: Painel) -> None:
    painel.adicionar("greenhouse", "vitta")
    id_ = int(painel.sql("SELECT id FROM empresa")[0][0])
    painel.post(f"/empresas/{id_}/remover")
    for acao in ("ligar", "desligar", "remover"):
        assert painel.post(f"/empresas/999/{acao}").status_code == 404
        assert painel.post(f"/empresas/{2**63 - 1}/{acao}").status_code == 404
        assert painel.post(f"/empresas/0/{acao}").status_code == 422
    # empresa já removida não volta por "ligar" nem "desligar"
    assert painel.post(f"/empresas/{id_}/ligar").status_code == 404
    assert painel.post(f"/empresas/{id_}/desligar").status_code == 404


def test_agibank_mostra_etiqueta_de_banco_de_talentos(tmp_path: Path) -> None:
    painel = Painel(tmp_path, semeado=True)
    html = painel.get("/empresas").text
    cartoes = html.split('<li class="cartao')[1:]
    do_agibank = [c for c in cartoes if AGIBANK in c]
    assert len(do_agibank) == 1 and ETIQUETA in do_agibank[0]
    outros = [c for c in cartoes if AGIBANK not in c]
    assert len(outros) > 20  # controle: as demais empresas da lista inicial aparecem
    assert all(ETIQUETA not in c for c in outros)


def test_lista_mostra_so_as_nao_removidas_e_pede_csrf(painel: Painel) -> None:
    painel.adicionar("greenhouse", "vitta", nome="Vitta")
    painel.adicionar("greenhouse", "outra", nome="Outra")
    id_ = int(painel.sql("SELECT id FROM empresa WHERE identificador = 'outra'")[0][0])
    painel.post(f"/empresas/{id_}/remover")
    html = painel.get("/empresas").text
    assert "Vitta" in html and "Outra" not in html
    sem_token = painel.http.post("/empresas/testar", data={"fonte": "greenhouse"})
    assert sem_token.status_code == 403


def test_lista_vazia_mostra_o_formulario(painel: Painel) -> None:
    html = painel.get("/empresas").text
    assert 'name="endereco"' in html and 'formaction="/empresas/testar"' in html
    assert '<option value="greenhouse"' in html and '<option value="gupy"' in html
    assert '<option value="remotive"' not in html
