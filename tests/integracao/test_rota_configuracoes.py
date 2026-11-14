"""Configurações e interruptores (desenho 13.2 e 13.7; plano T54; decisão 17; DP8).

O segundo plano e o systemd são falsos: nenhum teste chama `systemctl` nem `distrobox` de verdade.
"""

import html as html_lib
import json
import re
import time
from collections.abc import Iterator, Sequence
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.segundo_plano_falso import FalsoSistema
from apoio.semear import semear
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema.segundo_plano_linux import Resultado

PORTA = 47618
FUNCOES = (
    "descoberta_cc_ligada",
    "paginas_ligadas",
    "enriquecimento_ligado",
    "destaques_ligados",
    "conversao_moeda_ligada",
    "regras_ocultar_ligadas",
)
FUNCOES_URL = "/configuracoes/funcoes"
PRIVACIDADE = "/configuracoes/privacidade"
SEGUNDO_PLANO = "/configuracoes/segundo-plano"
FONTES = "/configuracoes/fontes"
GRAVAR_CHAVE = (
    "INSERT INTO config (chave, valor) VALUES ('segundo_plano', ?) "
    "ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor"
)


class Painel:
    """Cliente do app sobre um banco semeado (vagas e fontes), com o relógio parado."""

    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        self.dados = tmp_path
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            self.ids = semear(con)
            cadastros.semear(con)
        self.casa = tmp_path / "casa"
        self.casa.mkdir()
        self.sistema = FalsoSistema(home=str(self.casa))
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso()
        self.app.state.rodar_comando = self.sistema
        self.app.state.ambiente = {"HOME": str(self.casa)}
        self.app.state.plataforma = "linux"
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def config(self, chave: str) -> object:
        linhas = self.sql("SELECT valor FROM config WHERE chave = ?", chave)
        return json.loads(linhas[0][0]) if linhas else None

    def get(self, url: str, **kw: Any) -> Any:
        return self.http.get(url, **kw)

    def post(self, url: str, dados: dict[str, Any] | None = None) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **(dados or {})})

    def funcoes(self, **mudar: object) -> Any:
        """POST das funções: tudo ligado e N = 10, menos o que `mudar` diz (False tira a marca)."""
        dados: dict[str, Any] = {chave: "on" for chave in FUNCOES} | {"destaques_n": "10"}
        for chave, valor in mudar.items():
            if valor is False:
                dados.pop(chave)
            else:
                dados[chave] = valor
        return self.post(FUNCOES_URL, dados)

    def brl(self, nome: str) -> int | None:
        linhas = self.sql("SELECT sal_mensal_min_brl FROM vaga WHERE id = ?", self.ids[nome])
        return None if linhas[0][0] is None else int(linhas[0][0])

    def oculta(self, nome: str, busca: int) -> str | None:
        linhas = self.sql(
            "SELECT oculta_motivo FROM encaixe WHERE busca_id = ? AND vaga_id = ?",
            busca,
            self.ids[nome],
        )
        return None if linhas[0][0] is None else str(linhas[0][0])


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


def _interruptor(html: str, nome: str) -> tuple[bool, bool]:
    """(existe, marcado) do checkbox de nome `nome`."""
    for tag in re.findall(r"<input\b[^>]*>", html):
        if f'name="{nome}"' in tag and 'type="checkbox"' in tag:
            return True, bool(re.search(r"\schecked\b", tag))
    return False, False


def _valor(tag: str) -> str:
    achou = re.search(r'value="([^"]*)"', tag)
    assert achou is not None, tag
    return achou.group(1)


def _texto(html: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html_lib.unescape(sem_tags))


def _alerta(html: str) -> str:
    achou = re.search(r'role="alert"[^>]*>(.*?)</(?:p|div)>', html, re.S)
    assert achou is not None, "sem aviso na página"
    return _texto(achou.group(1))


# ------------------------------------------------------------------ grupos


def test_raiz_leva_ao_primeiro_grupo(painel: Painel) -> None:
    resposta = painel.get("/configuracoes")
    assert (resposta.status_code, resposta.headers.get("location")) == (303, FONTES)


@pytest.mark.parametrize(
    "grupo", ["fontes", "funcoes", "segundo-plano", "aparencia", "privacidade"]
)
def test_cada_grupo_abre_com_a_aba_dele_marcada(painel: Painel, grupo: str) -> None:
    resposta = painel.get(f"/configuracoes/{grupo}")
    assert resposta.status_code == 200
    marcadas = re.findall(r'<a [^>]*href="([^"]+)"[^>]*aria-current="page"', resposta.text)
    # o menu principal marca Configurações; a aba do grupo é a outra
    assert f"/configuracoes/{grupo}" in marcadas
    assert "/configuracoes/fontes" in re.findall(r'href="(/configuracoes/[^"]+)"', resposta.text)


def test_grupo_desconhecido_da_404(painel: Painel) -> None:
    assert painel.get("/configuracoes/nada").status_code == 404
    assert painel.post("/configuracoes/nada").status_code == 404


def test_post_sem_token_da_403(painel: Painel) -> None:
    assert painel.http.post(FUNCOES_URL, data={"paginas_ligadas": "on"}).status_code == 403
    assert painel.config("paginas_ligadas") is None


# ------------------------------------------------------------------ funções (13.7)


def test_todos_os_interruptores_da_13_7_aparecem_ligados_de_partida(painel: Painel) -> None:
    html = painel.get(FUNCOES_URL).text
    for chave in FUNCOES:
        assert _interruptor(html, chave) == (True, True), chave


@pytest.mark.parametrize("chave", FUNCOES)
def test_cada_interruptor_grava_desligado_e_ligado(painel: Painel, chave: str) -> None:
    resposta = painel.funcoes(**{chave: False})
    assert (resposta.status_code, resposta.headers.get("location")) == (303, FUNCOES_URL)
    assert painel.config(chave) is False
    # só ele mudou
    assert [painel.config(c) for c in FUNCOES if c != chave] == [True] * 5
    assert _interruptor(painel.get(FUNCOES_URL).text, chave) == (True, False)

    painel.funcoes()
    assert painel.config(chave) is True
    assert _interruptor(painel.get(FUNCOES_URL).text, chave) == (True, True)


def test_destaques_n_grava_inteiro_e_volta_na_tela(painel: Painel) -> None:
    assert painel.funcoes(destaques_n="3").status_code == 303
    assert painel.config("destaques_n") == 3
    assert 'name="destaques_n"' in painel.get(FUNCOES_URL).text
    assert re.search(r'name="destaques_n"[^>]*value="3"', painel.get(FUNCOES_URL).text)


@pytest.mark.parametrize("ruim", ["0", "101", "-1", "abc", "", " ", "2.5", "１０", "9" * 40])
def test_destaques_n_invalido_da_422_e_nao_grava_nada(painel: Painel, ruim: str) -> None:
    resposta = painel.funcoes(destaques_n=ruim, conversao_moeda_ligada=False)
    assert resposta.status_code == 422
    assert "1 a 100" in _alerta(resposta.text)
    assert painel.config("destaques_n") is None
    assert painel.config("conversao_moeda_ligada") is None  # nem o resto do formulário


def test_destaques_desligados_tiram_a_aba_e_o_painel_abre_em_todas(painel: Painel) -> None:
    painel.sql("INSERT INTO config (chave, valor) VALUES ('primeira_execucao_concluida', 'true')")
    assert painel.get("/").headers.get("location") == "/vagas?aba=destaques"
    assert 'id="aba-destaques"' in painel.get("/vagas?aba=destaques").text
    painel.funcoes(destaques_ligados=False)
    assert painel.get("/").headers.get("location") == "/vagas?aba=todas"
    html = painel.get("/vagas?aba=destaques").text  # a aba pedida não existe mais: abre em Todas
    assert 'id="aba-destaques"' not in html
    assert re.search(r'id="aba-todas"[^>]*aria-current="page"', html)


def test_regras_de_ocultar_desligadas_param_de_ocultar_e_ligadas_voltam(painel: Painel) -> None:
    busca = painel.ids["busca"]
    assert painel.oculta("oculta_regra", busca) == "modalidade"  # do exemplo
    painel.funcoes(regras_ocultar_ligadas=False)
    assert painel.oculta("oculta_regra", busca) is None
    painel.funcoes()
    assert painel.oculta("oculta_regra", busca) == "modalidade"


def test_conversao_desligada_tira_o_real_da_vaga_estrangeira_e_mantem_o_da_vaga_em_brl(
    painel: Painel,
) -> None:
    assert (painel.brl("usd"), painel.brl("brl")) == (28250, 8000)
    painel.funcoes(conversao_moeda_ligada=False)
    assert (painel.brl("usd"), painel.brl("brl")) == (None, 8000)
    assert painel.sql("SELECT sal_cotacao_data FROM vaga WHERE id = ?", painel.ids["usd"]) == [
        (None,)
    ]
    detalhe = _texto(painel.get(f"/vagas/{painel.ids['usd']}").text)
    assert "US$ 5.000/mês" in detalhe
    assert "PTAX" not in detalhe
    # ligar de novo traz o valor de volta, pela cotação guardada
    painel.funcoes()
    assert (painel.brl("usd"), painel.brl("brl")) == (28250, 8000)


def test_conversao_com_cotacao_de_8_dias_nao_converte(painel: Painel, fuso_sao_paulo: None) -> None:
    # 13/11 12:00 UTC é 13/11 09:00 em São Paulo: a cotação vale 7 dias a partir do dia local
    painel.funcoes(conversao_moeda_ligada=False)
    painel.sql("UPDATE cotacao SET data = '2026-11-05'")  # 8 dias antes de 13/11
    painel.funcoes()
    assert (painel.brl("usd"), painel.brl("brl")) == (None, 8000)
    painel.funcoes(conversao_moeda_ligada=False)
    painel.sql("UPDATE cotacao SET data = '2026-11-06'")  # 7 dias antes: ainda vale
    painel.funcoes()
    assert painel.brl("usd") == 28250


@pytest.mark.parametrize(
    ("cotacao", "converte", "oculta"),
    [
        ("2026-11-06", True, "salario"),  # 7 dias antes do dia local (13/11): vale
        ("2026-11-05", False, None),  # 8 dias antes do dia local: não vale
    ],
)
def test_conversao_e_encaixe_usam_o_dia_local(
    painel: Painel, fuso_sao_paulo: None, cotacao: str, converte: bool, oculta: str | None
) -> None:
    # 14/11 02:00 UTC ainda é 13/11 23:00 em São Paulo; 06/11 está a 8 dias do dia UTC
    painel.app.state.relogio = RelogioFalso(datetime(2026, 11, 14, 2, 0, tzinfo=UTC))
    painel.sql("UPDATE cotacao SET data = ?, venda = '5.65'", cotacao)
    # busca com mínimo de US$ 2.000 (R$ 11.300): a vaga em BRL de R$ 8.000 fica abaixo dele
    painel.sql(
        "INSERT INTO busca (nome, salario_min, salario_moeda, criada_em)"
        " VALUES ('com mínimo', 200000, 'USD', '2026-11-13T12:00:00+00:00')"
    )
    busca = int(painel.sql("SELECT MAX(id) FROM busca")[0][0])
    painel.funcoes(conversao_moeda_ligada=False)
    assert painel.brl("usd") is None
    painel.funcoes()  # liga: aplicar_cotacoes e recalcular_encaixe, os dois com o dia local
    assert (painel.brl("usd") == 28250) is converte
    assert painel.oculta("brl", busca) == oculta


def test_recalculo_que_falha_nao_deixa_a_chave_gravada_e_o_salvar_de_novo_refaz(
    painel: Painel, monkeypatch: pytest.MonkeyPatch
) -> None:
    busca = painel.ids["busca"]
    assert painel.oculta("oculta_regra", busca) == "modalidade"

    def quebra(*_: object, **__: object) -> None:
        raise RuntimeError("banco travado")

    with monkeypatch.context() as m:
        m.setattr("jobot.painel.rotas.configuracoes.buscas.recalcular_encaixe", quebra)
        with pytest.raises(RuntimeError):
            painel.funcoes(regras_ocultar_ligadas=False)
    assert (
        painel.config("regras_ocultar_ligadas") is not False
    )  # a chave não ficou à frente das vagas
    painel.funcoes(regras_ocultar_ligadas=False)  # a mesma tentativa, agora sem falha
    assert painel.oculta("oculta_regra", busca) is None
    assert painel.config("regras_ocultar_ligadas") is False


def test_conversao_ligada_sem_mudar_a_chave_nao_mexe_nas_vagas(painel: Painel) -> None:
    painel.sql("UPDATE vaga SET sal_mensal_min_brl = 1 WHERE id = ?", painel.ids["usd"])
    painel.funcoes(destaques_n="4")  # a conversão continua ligada
    assert painel.brl("usd") == 1


# ------------------------------------------------------------------ fontes


def test_fontes_mostra_uma_chave_por_fonte_agrupadas_por_leva(painel: Painel) -> None:
    html = painel.get(FONTES).text
    cadastradas = [f.chave for f in _fontes(painel)]
    assert len(cadastradas) >= 28
    marcas = re.findall(r'<input\b[^>]*name="fonte"[^>]*>', html)
    assert [_valor(m) for m in marcas] == cadastradas
    assert all(re.search(r"\schecked\b", m) for m in marcas)
    assert html.count('class="grupo-leva"') == 2


def _fontes(painel: Painel) -> list[Any]:
    with closing(abrir(painel.banco)) as con:
        return cadastros.fontes(con)


def test_desligar_fonte_pela_configuracao_grava_ligada_zero(painel: Painel) -> None:
    todas = [f.chave for f in _fontes(painel)]
    resposta = painel.post(FONTES, {"fonte": [c for c in todas if c != "remotive"]})
    assert (resposta.status_code, resposta.headers.get("location")) == (303, FONTES)
    assert painel.sql("SELECT chave FROM fonte WHERE ligada = 0") == [("remotive",)]
    marcadas = re.findall(r'<input\b[^>]*name="fonte"[^>]*>', painel.get(FONTES).text)
    desmarcada = [m for m in marcadas if 'value="remotive"' in m]
    assert len(desmarcada) == 1 and not re.search(r"\schecked\b", desmarcada[0])
    painel.post(FONTES, {"fonte": todas})
    assert painel.sql("SELECT COUNT(*) FROM fonte WHERE ligada = 0") == [(0,)]


def test_fonte_desconhecida_da_422_e_nao_grava(painel: Painel) -> None:
    resposta = painel.post(FONTES, {"fonte": ["remotive", "nao_existe"]})
    assert resposta.status_code == 422
    assert painel.sql("SELECT COUNT(*) FROM fonte WHERE ligada = 0") == [(0,)]


# ------------------------------------------------------------------ segundo plano


def test_segundo_plano_ligar_habilita_o_servico_e_grava_a_chave(painel: Painel) -> None:
    resposta = painel.post(SEGUNDO_PLANO, {"segundo_plano": "on"})
    assert (resposta.status_code, resposta.headers.get("location")) == (303, SEGUNDO_PLANO)
    assert ("enable", "--now", "jobot.service") in painel.sistema.systemctl()
    assert painel.config("segundo_plano") is True
    assert _interruptor(painel.get(SEGUNDO_PLANO).text, "segundo_plano") == (True, True)


def test_segundo_plano_desligar_desabilita_o_servico_e_grava_a_chave(painel: Painel) -> None:
    painel.post(SEGUNDO_PLANO, {"segundo_plano": "on"})
    painel.post(SEGUNDO_PLANO)
    assert ("disable", "--now", "jobot.service") in painel.sistema.systemctl()
    assert painel.config("segundo_plano") is False
    painel.sistema.falha_em["is-enabled"] = Resultado(1)  # o falso não guarda estado
    assert _interruptor(painel.get(SEGUNDO_PLANO).text, "segundo_plano") == (True, False)


def test_segundo_plano_recusado_mostra_o_motivo_e_nao_grava(painel: Painel) -> None:
    painel.sistema.systemd_ok = False
    resposta = painel.post(SEGUNDO_PLANO, {"segundo_plano": "on"})
    assert resposta.status_code == 200
    assert "o systemd do usuário não responde" in _alerta(resposta.text)
    assert painel.config("segundo_plano") is None
    assert all(c[0] != "enable" for c in painel.sistema.systemctl())


def test_segundo_plano_mostra_o_container_e_o_estado_do_servico(painel: Painel) -> None:
    painel.app.state.ambiente = {"HOME": str(painel.casa), "CONTAINER_ID": "fedora-dev"}
    texto = _texto(painel.get(SEGUNDO_PLANO).text)
    assert "fedora-dev" in texto
    assert "Serviço instalado: sim" in texto
    assert "Rodando agora: sim" in texto


def test_interruptor_segue_o_systemd_e_nao_a_chave(painel: Painel) -> None:
    # D61: no Linux o "ligado" vem do is-enabled; ativo (is-active) não entra
    painel.sql(GRAVAR_CHAVE, "false")
    assert painel.config("segundo_plano") is False
    assert _interruptor(painel.get(SEGUNDO_PLANO).text, "segundo_plano") == (True, True)
    painel.sql(GRAVAR_CHAVE, "true")
    painel.sistema.falha_em["is-enabled"] = Resultado(1)
    assert _interruptor(painel.get(SEGUNDO_PLANO).text, "segundo_plano") == (True, False)
    assert painel.config("segundo_plano") is True  # o GET só lê


def test_interruptor_ligado_nao_depende_do_ativo(painel: Painel) -> None:
    painel.sistema.falha_em["is-active"] = Resultado(3)
    assert _interruptor(painel.get(SEGUNDO_PLANO).text, "segundo_plano") == (True, True)


class _NaoDeviaChamar:
    def __call__(self, comando: Sequence[str]) -> Resultado:
        raise AssertionError(f"consultou o systemd fora do Linux: {comando!r}")


def test_fora_do_linux_nao_consulta_o_systemd(painel: Painel) -> None:
    painel.sql(GRAVAR_CHAVE, "true")
    painel.app.state.plataforma = "win32"
    painel.app.state.rodar_comando = _NaoDeviaChamar()
    html = painel.get(SEGUNDO_PLANO).text
    tag = next(t for t in re.findall(r"<input\b[^>]*>", html) if 'name="segundo_plano"' in t)
    assert re.search(r"\sdisabled\b", tag)
    assert not re.search(r"\schecked\b", tag)


def test_segundo_plano_fora_do_linux_fica_desativado(painel: Painel) -> None:
    painel.app.state.plataforma = "win32"
    html = painel.get(SEGUNDO_PLANO).text
    tag = next(t for t in re.findall(r"<input\b[^>]*>", html) if 'name="segundo_plano"' in t)
    assert re.search(r"\sdisabled\b", tag)
    resposta = painel.post(SEGUNDO_PLANO, {"segundo_plano": "on"})  # forjado: nada é ligado
    assert resposta.status_code == 303
    assert painel.config("segundo_plano") is False
    assert painel.sistema.chamadas == []


# ------------------------------------------------------------------ aparência


def test_aparencia_usa_as_rotas_de_preferencia_e_volta_para_ela(painel: Painel) -> None:
    html = painel.get("/configuracoes/aparencia").text
    for qual in ("tema", "idioma"):  # os formulários da página, além dos da casca
        assert re.search(rf'<form [^>]*action="/preferencias/{qual}"[^>]*data-preferencia', html)
    assert html.count('name="voltar" value="/configuracoes/aparencia"') >= 4
    resposta = painel.post(
        "/preferencias/tema", {"tema": "escuro", "voltar": "/configuracoes/aparencia"}
    )
    assert resposta.headers.get("location") == "/configuracoes/aparencia"
    assert painel.config("tema") == "escuro"


# ------------------------------------------------------------------ privacidade


def test_privacidade_diz_onde_ficam_os_dados_sem_telemetria_e_recomenda_disco_cifrado(
    painel: Painel,
) -> None:
    texto = _texto(painel.get(PRIVACIDADE).text)
    assert str(painel.dados) in texto
    assert "sem telemetria" in texto.lower()
    assert "criptografar o disco" in texto


def test_privacidade_lista_os_destinos_reais_sem_afirmar_exclusividade(
    painel: Painel,
) -> None:
    pt = _texto(painel.get(PRIVACIDADE).text)
    assert "Banco Central" in pt
    assert "único outro pedido" not in pt
    assert "nada sai do computador" not in pt
    en = _texto(painel.get(PRIVACIDADE, headers={"Accept-Language": "en"}).text)
    assert "Central Bank" in en
    assert "only other request" not in en
    assert "nothing leaves the computer" not in en


def test_privacidade_em_ingles(painel: Painel) -> None:
    texto = _texto(painel.get(PRIVACIDADE, headers={"Accept-Language": "en"}).text)
    assert "disk encryption" in texto
    assert "criptografar" not in texto


def test_interruptor_aviso_versao_aparece_em_privacidade_e_grava(painel: Painel) -> None:
    # nasce desligado (ADR 0014: os dados só saem para o que a pessoa liga)
    assert _interruptor(painel.get(PRIVACIDADE).text, "aviso_versao_ligada") == (True, False)
    assert painel.config("aviso_versao_ligada") is None
    resposta = painel.post(PRIVACIDADE, {"aviso_versao_ligada": "on"})
    assert (resposta.status_code, resposta.headers.get("location")) == (303, PRIVACIDADE)
    assert painel.config("aviso_versao_ligada") is True
    assert _interruptor(painel.get(PRIVACIDADE).text, "aviso_versao_ligada") == (True, True)
    painel.post(PRIVACIDADE)
    assert painel.config("aviso_versao_ligada") is False
    assert _interruptor(painel.get(PRIVACIDADE).text, "aviso_versao_ligada") == (True, False)


def test_aviso_de_versao_nao_aparece_nas_funcoes(painel: Painel) -> None:
    assert _interruptor(painel.get(FUNCOES_URL).text, "aviso_versao_ligada") == (False, False)
