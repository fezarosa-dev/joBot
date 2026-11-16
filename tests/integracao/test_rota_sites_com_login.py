"""Grupo "Sites com login" em Configurações (plano T218; D132.8, D132.23, D132.41, D132.48).

O painel lê o que o `serve` deixa em `app.state`; "Fazer login agora" e "Esquecer logins" usam
o `jobot.navegador` (T219).
"""

import asyncio
import html as html_lib
import json
import re
import threading
import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager, closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import EstadoSaude, abrir_execucao, fechar_execucao, gravar_saude
from jobot.banco.migrar import migrar
from jobot.navegador import abrir as abrir_navegador
from jobot.nucleo.leitores.base import LeitorComLogin
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.rotas import configuracoes
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema.pastas import PASTA_NAVEGADOR

PORTA = 47619
GRUPO = "/configuracoes/sites-com-login"
CHAVE = "falso_logado"
INTERRUPTOR = f"{GRUPO}/{CHAVE}/interruptor"
LOGIN = f"{GRUPO}/{CHAVE}/login"
ESQUECER = f"{GRUPO}/esquecer"
CONFIRMAR = f"{ESQUECER}/confirmar"
AGORA = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
CHAVES_DE_HORARIO = ("formato", "repetido", "muitos", "perto")
TEXTOS: dict[str, dict[str, Any]] = {
    "pt": {
        "explicacao": "O joBot nunca digita a sua senha",
        "risco": ("pode ir contra os termos", "conta pode ser restringida", "site por site"),
        "chrome": "Chrome encontrado",
        "chromium": "Usando o Chromium do Playwright",
        "nenhum": "Nenhum navegador encontrado",
        "rodando": "Lendo agora",
        "esquecer": "Esquecer logins",
        "precisa_login": "Precisa entrar de novo no site: use Fazer login agora",
    },
    "en": {
        "explicacao": "joBot never types your password",
        "risco": ("may go against their terms", "account may be restricted", "site by site"),
        "chrome": "Chrome found",
        "chromium": "Using Playwright's Chromium",
        "nenhum": "No browser found",
        "rodando": "Reading now",
        "esquecer": "Forget logins",
        "precisa_login": "You need to sign in to the site again: use Sign in now",
    },
}


class Painel:
    """App sobre um banco migrado, com o leitor do site falso registrado e a fonte semeada."""

    def __init__(self, tmp_path: Path, *, com_leitor: bool = True) -> None:
        self.banco = tmp_path / "jobot.db"
        self.leitor = LeitorFalso(base="http://127.0.0.1:9")
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            cadastros.semear(con)
            cadastros.semear_leitores(con, [self.leitor])
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.relogio = RelogioFalso(AGORA)
        self.app.state.leitores = (self.leitor,) if com_leitor else ()
        self.http = TestClient(
            self.app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False
        )
        self.token: str = self.app.state.csrf

    def sql(self, texto: str, *params: Any) -> list[tuple[Any, ...]]:
        with closing(abrir(self.banco)) as con:
            linhas = con.execute(texto, params).fetchall()
            con.commit()
        return [tuple(linha) for linha in linhas]

    def idioma(self, idioma: str) -> None:
        self.sql(
            "INSERT INTO config (chave, valor) VALUES ('idioma', ?)"
            " ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor",
            json.dumps(idioma),
        )

    def ligada(self) -> int:
        return int(self.sql("SELECT ligada FROM fonte WHERE chave = ?", CHAVE)[0][0])

    def horarios(self) -> object:
        linhas = self.sql("SELECT valor FROM config WHERE chave = 'login_horarios'")
        return json.loads(linhas[0][0]) if linhas else None

    def post(self, url: str, dados: dict[str, Any] | None = None) -> Any:
        return self.http.post(url, data={CAMPO_CSRF: self.token, **(dados or {})})


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


@pytest.fixture
def sem_leitor(tmp_path: Path) -> Painel:
    return Painel(tmp_path, com_leitor=False)


def _texto(html: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html_lib.unescape(sem_tags))


def _interruptor(html: str) -> tuple[bool, bool]:
    """(existe com `role="switch"`, marcado) do interruptor do site falso."""
    for tag in re.findall(r"<input\b[^>]*>", html):
        if 'name="ligada"' in tag and 'role="switch"' in tag:
            return True, bool(re.search(r"\schecked\b", tag))
    return False, False


def _abas(html: str) -> list[str]:
    return re.findall(r'href="(/configuracoes/[^"]+)"', html)


def _cartao_com_leitura(
    painel: Painel, estado: EstadoSaude, motivo: str | None, rodando: bool
) -> None:
    with closing(abrir(painel.banco)) as con:
        execucao = abrir_execucao(con, "login", "agenda", AGORA)
        assert execucao is not None
        gravar_saude(con, execucao, CHAVE, "", estado, motivo=motivo)
        con.commit()
        if not rodando:
            fechar_execucao(con, execucao, AGORA)


# ------------------------------------------------------------------ só com leitor


def test_sem_leitor_a_aba_nao_aparece(painel: Painel, sem_leitor: Painel) -> None:
    assert GRUPO in _abas(painel.http.get("/configuracoes/fontes").text)  # controle
    assert GRUPO not in _abas(sem_leitor.http.get("/configuracoes/fontes").text)


def test_sem_leitor_rota_da_404(sem_leitor: Painel, painel: Painel) -> None:
    def gravar(p: Painel) -> int:
        return int(p.post(GRUPO, {"horarios": "09:00, 18:00"}).status_code)

    assert gravar(painel) in (200, 303)  # controle: com leitor a rota existe
    assert gravar(sem_leitor) == 404


def test_sem_leitor_o_get_vai_para_geral(sem_leitor: Painel) -> None:
    # o navegador pode ter guardado o grupo (T262, T308): cai em Geral em vez de 404
    resposta = sem_leitor.http.get(GRUPO)
    assert (resposta.status_code, resposta.headers.get("location")) == (
        303,
        "/configuracoes/geral",
    )


def test_sem_leitor_o_interruptor_da_404(sem_leitor: Painel) -> None:
    assert sem_leitor.post(INTERRUPTOR, {"ligada": "on"}).status_code == 404
    assert sem_leitor.ligada() == 0


def test_o_grupo_e_o_penultimo_das_abas(painel: Painel) -> None:
    """Ferramentas (T240) entra por último; Sites com login vem logo antes."""
    abas = _abas(painel.http.get("/configuracoes/fontes").text)
    assert abas[-2:] == [GRUPO, "/configuracoes/ferramentas"]


# ------------------------------------------------------------------ o interruptor


def test_com_leitor_interruptor_nasce_desligado_e_grava(painel: Painel) -> None:
    pagina = painel.http.get(GRUPO)
    assert pagina.status_code == 200
    assert _interruptor(pagina.text) == (True, False)
    caixa = re.search(r'<input\b[^>]*name="ligada"[^>]*>', pagina.text)
    assert caixa is not None and 'class="chave"' in caixa[0]

    ligado = painel.post(INTERRUPTOR, {"ligada": "on"})
    assert ligado.status_code == 200
    assert painel.ligada() == 1
    assert _interruptor(ligado.text) == (True, True)
    assert _interruptor(painel.http.get(GRUPO).text) == (True, True)

    desligado = painel.post(INTERRUPTOR)  # checkbox sem marca não manda o campo
    assert desligado.status_code == 200
    assert painel.ligada() == 0
    assert _interruptor(desligado.text) == (True, False)


def test_interruptor_sem_token_da_403_e_nao_grava(painel: Painel) -> None:
    assert painel.http.post(INTERRUPTOR, data={"ligada": "on"}).status_code == 403
    assert painel.ligada() == 0


def test_interruptor_de_fonte_que_nao_e_leitor_da_404(painel: Painel) -> None:
    resposta = painel.post(f"{GRUPO}/remotive/interruptor", {"ligada": "on"})
    assert resposta.status_code == 404
    assert painel.sql("SELECT ligada FROM fonte WHERE chave = 'remotive'") == [(1,)]
    painel.sql("UPDATE fonte SET ligada = 0 WHERE chave = 'remotive'")
    assert painel.post(f"{GRUPO}/remotive/interruptor", {"ligada": "on"}).status_code == 404
    assert painel.sql("SELECT ligada FROM fonte WHERE chave = 'remotive'") == [(0,)]


def test_interruptor_de_leitor_sem_fonte_semeada_da_404(painel: Painel) -> None:
    painel.sql("DELETE FROM fonte WHERE chave = ?", CHAVE)
    assert painel.post(INTERRUPTOR, {"ligada": "on"}).status_code == 404


# ------------------------------------------------------------------ o cartão


def test_cartao_mostra_o_nome_e_ainda_nao_leu(painel: Painel) -> None:
    texto = _texto(painel.http.get(GRUPO).text)
    assert painel.leitor.nome in texto
    assert "Ainda não leu" in texto
    assert TEXTOS["pt"]["rodando"] not in texto


def test_cartao_mostra_leitura_rodando(painel: Painel) -> None:
    painel.post(INTERRUPTOR, {"ligada": "on"})
    assert TEXTOS["pt"]["rodando"] not in _texto(painel.http.get(GRUPO).text)  # controle
    _cartao_com_leitura(painel, "ok", None, rodando=True)
    assert TEXTOS["pt"]["rodando"] in _texto(painel.http.get(GRUPO).text)


def test_leitura_rodando_nao_aparece_no_site_desligado(painel: Painel) -> None:
    _cartao_com_leitura(painel, "ok", None, rodando=True)
    assert painel.ligada() == 0
    assert TEXTOS["pt"]["rodando"] not in _texto(painel.http.get(GRUPO).text)


def test_leitura_que_acabou_nao_aparece_como_rodando(painel: Painel) -> None:
    painel.post(INTERRUPTOR, {"ligada": "on"})
    _cartao_com_leitura(painel, "ok", None, rodando=False)
    texto = _texto(painel.http.get(GRUPO).text)
    assert TEXTOS["pt"]["rodando"] not in texto
    assert "Ainda não leu" not in texto
    assert "Ok" in texto


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_cartao_mostra_o_motivo_da_ultima(painel: Painel, idioma: str) -> None:
    painel.idioma(idioma)
    assert TEXTOS[idioma]["precisa_login"] not in _texto(painel.http.get(GRUPO).text)  # controle
    _cartao_com_leitura(painel, "falhou", "saude.precisa_login", rodando=False)
    assert TEXTOS[idioma]["precisa_login"] in _texto(painel.http.get(GRUPO).text)


def test_motivo_com_parametro_vira_texto(painel: Painel) -> None:
    _cartao_com_leitura(painel, "falhou", "saude.excecao:ValueError", rodando=False)
    assert "Erro inesperado: ValueError" in _texto(painel.http.get(GRUPO).text)


def test_cartao_segue_a_regra_da_pagina_de_saude_com_varios_escopos(painel: Painel) -> None:
    with closing(abrir(painel.banco)) as con:
        execucao = abrir_execucao(con, "login", "agenda", AGORA)
        assert execucao is not None
        gravar_saude(con, execucao, CHAVE, "a", "parcial", motivo="saude.zero_inesperado")
        gravar_saude(con, execucao, CHAVE, "b", "falhou", motivo="saude.formato_mudou")
        fechar_execucao(con, execucao, AGORA)
        con.commit()
    texto = _texto(painel.http.get(GRUPO).text)
    assert "Última leitura: Parcial" in texto  # um escopo falhou e outro não: parcial
    assert "O formato da fonte mudou" in texto  # o motivo é o do escopo mais grave
    assert "não devolveu nenhuma vaga" not in texto


def test_cartao_vem_na_resposta_do_interruptor(painel: Painel) -> None:
    _cartao_com_leitura(painel, "falhou", "saude.precisa_login", rodando=False)
    resposta = painel.post(INTERRUPTOR, {"ligada": "on"})
    texto = _texto(resposta.text)
    assert painel.leitor.nome in texto
    assert TEXTOS["pt"]["precisa_login"] in texto
    assert "<html" not in resposta.text  # só o cartão: o HTMX troca no lugar


# ------------------------------------------------------------------ horários


def test_horarios_mostram_o_padrao_num_campo_de_texto(painel: Painel) -> None:
    html = painel.http.get(GRUPO).text
    campo = re.search(r'<input\b[^>]*name="horarios"[^>]*>', html)
    assert campo is not None
    assert 'class="campo-texto"' in campo[0]
    assert 'value="09:00, 18:00"' in campo[0]


@pytest.mark.parametrize(
    ("texto", "chave"),
    [
        ("9:00", "formato"),
        ("", "formato"),
        ("09:00, 09:00", "repetido"),
        ("06:00, 10:00, 14:00, 18:00, 22:00", "muitos"),
        ("09:00, 12:00", "perto"),
        ("22:00, 01:00", "perto"),
    ],
)
@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_horarios_tortos_voltam_422_sem_gravar(
    painel: Painel, texto: str, chave: str, idioma: str
) -> None:
    painel.idioma(idioma)
    antes = painel.horarios()
    resposta = painel.post(GRUPO, {"horarios": texto})
    assert resposta.status_code == 422
    assert painel.horarios() == antes
    pagina = resposta.text
    alerta = re.search(r'role="alert"[^>]*>(.*?)</div>', pagina, re.S)
    assert alerta is not None
    esperado = _MENSAGENS[idioma][chave]
    assert esperado in _texto(alerta[1])
    assert f'value="{html_lib.escape(texto)}"' in pagina  # o que a pessoa digitou volta


_MENSAGENS = {
    "pt": {
        "formato": "Use o formato HH:MM",
        "repetido": "Não repita o mesmo horário",
        "muitos": "No máximo 4 horários",
        "perto": "pelo menos 4 horas",
    },
    "en": {
        "formato": "Use the HH:MM format",
        "repetido": "Do not repeat a time",
        "muitos": "At most 4 times",
        "perto": "at least 4 hours",
    },
}


def test_horarios_validos_gravam(painel: Painel) -> None:
    resposta = painel.post(GRUPO, {"horarios": "18:30,  06:00"})
    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"{GRUPO}?salvo=1"
    assert painel.horarios() == ["06:00", "18:30"]
    assert 'value="06:00, 18:30"' in painel.http.get(GRUPO).text


def test_horario_torto_gravado_a_mao_mostra_o_padrao(painel: Painel) -> None:
    painel.sql("INSERT INTO config (chave, valor) VALUES ('login_horarios', ?)", json.dumps(["9h"]))
    pagina = painel.http.get(GRUPO)
    assert pagina.status_code == 200
    assert 'value="09:00, 18:00"' in pagina.text


# ------------------------------------------------------------------ navegador


@pytest.mark.parametrize("achado", ["chrome", "chromium", None])
@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_estado_do_navegador(painel: Painel, achado: str | None, idioma: str) -> None:
    painel.idioma(idioma)
    painel.app.state.navegador_instalado = achado
    texto = _texto(painel.http.get(GRUPO).text)
    chave = achado or "nenhum"
    assert TEXTOS[idioma][chave] in texto
    for outra in {"chrome", "chromium", "nenhum"} - {chave}:
        assert TEXTOS[idioma][outra] not in texto


def test_sem_calculo_do_serve_o_navegador_conta_como_nenhum(painel: Painel) -> None:
    assert not hasattr(painel.app.state, "navegador_instalado")
    assert TEXTOS["pt"]["nenhum"] in _texto(painel.http.get(GRUPO).text)


def _sem_paleta(html: str) -> str:
    """A paleta (T265) repete os links de Configurações; aqui só conta a aba."""
    return re.sub(r'<dialog\b[^>]*\bid="paleta".*?</dialog>', "", html, flags=re.S)


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_sites_com_login_aponta_ferramentas(painel: Painel, idioma: str) -> None:
    """Sem navegador, a aba diz onde baixar e leva a Ferramentas (T240; D137.8)."""
    painel.idioma(idioma)
    painel.app.state.navegador_instalado = None
    link = 'href="/configuracoes/ferramentas"'  # a aba já tem um; o atalho é o segundo
    html = _sem_paleta(painel.http.get(GRUPO).text)
    assert html.count(link) == 2
    em_ferramentas = {
        "pt": "baixe o navegador em Ferramentas",
        "en": "download the browser in Tools",
    }
    assert em_ferramentas[idioma] in _texto(html)
    painel.app.state.navegador_instalado = "chrome"  # controle: com navegador, sem o atalho
    assert _sem_paleta(painel.http.get(GRUPO).text).count(link) == 1


def test_aba_nao_sobe_o_driver(painel: Painel, monkeypatch: pytest.MonkeyPatch) -> None:
    subidas: list[str] = []

    def falso() -> object:
        subidas.append("subiu")
        raise AssertionError("o painel subiu o driver do Playwright")

    monkeypatch.setattr(abrir_navegador, "async_playwright", falso)
    with pytest.raises(AssertionError):  # controle: o falso está no lugar e levanta
        vars(abrir_navegador)["async_playwright"]()
    subidas.clear()
    painel.app.state.navegador_instalado = "chromium"
    assert painel.http.get(GRUPO).status_code == 200
    assert painel.post(INTERRUPTOR, {"ligada": "on"}).status_code == 200
    assert subidas == []


# ------------------------------------------------------------------ textos e controles


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_textos_do_grupo_em_pt_e_en(painel: Painel, idioma: str) -> None:
    painel.idioma(idioma)
    painel.app.state.navegador_instalado = "chrome"
    resposta = painel.http.get(GRUPO)
    assert resposta.status_code == 200  # chave que falta no catálogo dá 500
    texto = _texto(resposta.text)
    esperados = TEXTOS[idioma]
    assert esperados["explicacao"] in texto
    for trecho in esperados["risco"]:  # a frase de risco inteira (D132.8), não só um trecho
        assert trecho in texto
    assert esperados["esquecer"] in texto
    assert ("Sites com login" if idioma == "pt" else "Sites with login") in texto


@pytest.mark.parametrize("pagina", ["get", "interruptor"])
def test_nenhum_checkbox_sem_chave(painel: Painel, pagina: str) -> None:
    resposta = (
        painel.http.get(GRUPO) if pagina == "get" else painel.post(INTERRUPTOR, {"ligada": "on"})
    )
    caixas = [t for t in re.findall(r"<input\b[^>]*>", resposta.text) if 'type="checkbox"' in t]
    assert caixas  # controle: a página tem ao menos o interruptor do site
    for caixa in caixas:
        assert re.search(r'class="[^"]*\bchave\b', caixa), caixa
        assert 'role="switch"' in caixa, caixa


def test_esquecer_tem_alerta(painel: Painel) -> None:
    """O botão abre o alerta (T259); sem JavaScript ele segue sendo o envio do formulário."""
    html = painel.http.get(GRUPO).text
    botao = re.search(
        r"<button\b[^>]*data-alerta-abre=\"alerta-esquecer\"[^>]*>\s*Esquecer logins\s*</button>",
        html,
    )
    assert botao is not None
    assert 'type="submit"' in botao[0] and "disabled" not in botao[0]
    assert f'hx-post="{ESQUECER}"' not in html  # a pergunta de dois cliques saiu
    alerta = re.search(r'<dialog id="alerta-esquecer".*?</dialog>', html, re.S)
    assert alerta is not None
    corpo = alerta.group(0)
    assert 'role="alertdialog"' in corpo and "data-alerta" in corpo
    assert f'action="{CONFIRMAR}"' in corpo  # a rota de confirmar é a mesma
    assert re.search(r'<button type="submit">\s*Esquecer\s*</button>', corpo)
    assert re.search(r"<button type=\"button\" data-alerta-fecha>\s*Cancelar\s*</button>", corpo)
    assert "Apagar os logins de todos os sites?" in _texto(corpo)
    assert "hx-confirm" not in html and "confirm(" not in html  # nada de diálogo do navegador


def _elemento_por_id(html: str, id_: str) -> str | None:
    """O HTML de dentro do elemento com esse `id` (conta a abertura e o fecho da mesma tag)."""
    inicio = re.search(rf'<(\w+)\b[^>]*\bid="{id_}"[^>]*>', html)
    if inicio is None:
        return None
    tag, fundo = inicio[1], 1
    for achado in re.finditer(rf"<(/?){tag}\b[^>]*>", html[inicio.end() :]):
        fundo += -1 if achado[1] else 1
        if fundo == 0:
            return html[inicio.end() : inicio.end() + achado.start()]
    return None


def test_esquecer_mostra_o_componente_indeterminado(painel: Painel) -> None:
    """O componente da T252 já vem no HTML do GET, escondido, como `hx-indicator` do envio (E15)."""
    html = painel.http.get(GRUPO).text
    alerta = re.search(r'<dialog id="alerta-esquecer".*?</dialog>', html, re.S)
    assert alerta is not None
    formulario = re.search(r"<form\b[^>]*>", alerta.group(0))
    assert formulario is not None and f'hx-post="{CONFIRMAR}"' in formulario[0]
    indicador = re.search(r'hx-indicator="#([\w-]+)"', formulario[0])
    assert indicador is not None, formulario[0]
    espera = _elemento_por_id(html, indicador[1])
    assert espera is not None, "o indicador não existe na página"
    assert len(re.findall(r'role="progressbar"', espera)) == 1
    assert "aria-valuenow" not in espera  # indeterminado: sem valor
    assert 'class="progresso-preenchimento indeterminado"' in espera
    assert "Apagando os logins guardados" in _texto(espera)
    assert html.count('role="progressbar"') == 1  # um só componente na página


def test_barra_da_espera_nao_repete_o_texto_no_aria_label(painel: Painel) -> None:
    """T311 (c): o nome do trilho vem do texto visível (aria-labelledby), não de um aria-label
    que repete esse texto."""
    html = painel.http.get(GRUPO).text
    espera = _elemento_por_id(html, "esquecer-progresso")
    assert espera is not None
    trilho = re.search(r'<div\b[^>]*role="progressbar"[^>]*>', espera)
    assert trilho is not None
    assert "aria-label=" not in trilho[0], trilho[0]
    alvo = re.search(r'aria-labelledby="([\w-]+)"', trilho[0])
    assert alvo is not None, trilho[0]
    nomeado = _elemento_por_id(espera, alvo[1])
    assert nomeado is not None and "Apagando os logins guardados" in _texto(nomeado)


def test_esquecer_indicador_em_ingles(painel: Painel) -> None:
    painel.idioma("en")
    assert "Deleting saved sign-ins" in _texto(painel.http.get(GRUPO).text)


def test_resposta_de_esquecer_nao_traz_o_componente(painel: Painel) -> None:
    """O componente mora na página; a resposta do POST só troca o texto do resultado (E15)."""
    _perfil(painel)
    resposta = painel.post(CONFIRMAR)
    assert resposta.status_code == 200
    assert "progressbar" not in resposta.text and "progresso" not in resposta.text


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_alerta_de_esquecer_em_pt_e_en(painel: Painel, idioma: str) -> None:
    painel.idioma(idioma)
    alerta = re.search(
        r'<dialog id="alerta-esquecer".*?</dialog>', painel.http.get(GRUPO).text, re.S
    )
    assert alerta is not None
    texto = _texto(alerta.group(0))
    esperado = {
        "pt": ("Apagar os logins de todos os sites?", "Esquecer", "Cancelar"),
        "en": ("Delete the logins for all sites?", "Forget", "Cancel"),
    }[idioma]
    for trecho in esperado:
        assert trecho in texto


def test_grupos_do_login_e_das_ferramentas_tem_icone(painel: Painel) -> None:
    html = painel.http.get(GRUPO).text
    nav = re.search(r'<nav class="config-grupos".*?</nav>', html, re.S)
    assert nav is not None
    icones = dict(
        re.findall(r'<a href="/configuracoes/([^"]+)" data-icone="([^"]+)"', nav.group(0))
    )
    assert icones["sites-com-login"] == "key-round"
    assert icones["ferramentas"] == "globe"


def test_nenhum_recurso_externo_na_pagina(painel: Painel) -> None:
    html = painel.http.get(GRUPO).text
    # recurso = o que a página carrega (src, link); o `<a>` do rodapé da base só aponta
    assert re.findall(r'(?:\ssrc|<link\b[^>]*\shref)="https?://', html) == []


def test_nome_do_leitor_e_escapado(painel: Painel) -> None:
    painel.leitor.nome = "<b>X</b>"
    html = painel.http.get(GRUPO).text
    assert "<b>X</b>" not in html
    assert "&lt;b&gt;X&lt;/b&gt;" in html


# ------------------------------------------------------------------ fazer login agora


class LoginFalso:
    """Troca o `fazer_login` e as dependências do navegador: conta as chamadas e só termina
    quando o teste libera (prazo de 5 s: uma rota que espera o login falha, não pendura)."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []
        self.deps: list[tuple[Path, Mapping[str, str]]] = []
        self.liberar = threading.Event()
        self.resultado = "pronto"
        self.erro: Exception | None = None

    async def __call__(self, leitor: LeitorComLogin, deps: Any, janela: Any) -> str:
        self.chamadas.append(leitor.chave)
        for _ in range(500):
            if self.liberar.is_set():
                if self.erro is not None:
                    raise self.erro
                return self.resultado
            await asyncio.sleep(0.01)
        raise AssertionError("o teste não liberou o login")

    @asynccontextmanager
    async def dependencias(self, dados: Path, env: Mapping[str, str]) -> AsyncIterator[object]:
        self.deps.append((dados, env))
        yield object()


@pytest.fixture
def login_falso(monkeypatch: pytest.MonkeyPatch) -> LoginFalso:
    falso = LoginFalso()
    monkeypatch.setattr(configuracoes, "fazer_login", falso)
    monkeypatch.setattr(configuracoes, "dependencias_de_producao", falso.dependencias)
    return falso


def _esperar(condicao: Callable[[], bool], s: float = 5.0) -> bool:
    fim = time.monotonic() + s
    while not condicao():
        if time.monotonic() >= fim:
            return False
        time.sleep(0.01)
    return True


def _trava_presa(painel: Painel) -> asyncio.Lock:
    """A trava `login` do `serve`, presa como numa leitura com login que roda."""
    trava = asyncio.Lock()
    asyncio.run(trava.acquire())
    painel.app.state.travas = {"login": trava}
    return trava


def _perfil(painel: Painel) -> Path:
    pasta = painel.banco.parent / PASTA_NAVEGADOR
    (pasta / "Default").mkdir(parents=True)
    (pasta / "Default" / "Cookies").write_text("sessao")
    return pasta


def _contagem(painel: Painel) -> tuple[int, int]:
    ((vagas, ocorrencias),) = painel.sql(
        "SELECT (SELECT count(*) FROM vaga), (SELECT count(*) FROM ocorrencia)"
    )
    return vagas, ocorrencias


_EM_ANDAMENTO = "Uma leitura está em andamento; tente de novo quando terminar."


@pytest.mark.parametrize(
    ("metodo", "rota"),
    [("POST", LOGIN), ("GET", LOGIN), ("POST", CONFIRMAR), ("GET", CONFIRMAR)],
)
def test_sem_leitor_rotas_de_login_e_esquecer_dao_404(
    sem_leitor: Painel, painel: Painel, login_falso: LoginFalso, metodo: str, rota: str
) -> None:
    login_falso.liberar.set()
    perfil = _perfil(sem_leitor)

    def pedir(p: Painel, http: TestClient) -> int:
        dados = {CAMPO_CSRF: p.token}
        return int(
            (http.post(rota, data=dados) if metodo == "POST" else http.get(rota)).status_code
        )

    assert pedir(sem_leitor, sem_leitor.http) == 404
    assert perfil.exists()  # nada apagado
    assert login_falso.chamadas == []
    # controle: com o leitor a mesma rota existe (com o lifespan, a tarefa do login termina)
    with TestClient(painel.app, base_url=f"http://127.0.0.1:{PORTA}") as http:
        assert pedir(painel, http) == 200


@pytest.mark.parametrize("metodo", ["POST", "GET"])
def test_login_de_chave_desconhecida_da_404(
    painel: Painel, login_falso: LoginFalso, metodo: str
) -> None:
    login_falso.liberar.set()
    with TestClient(painel.app, base_url=f"http://127.0.0.1:{PORTA}") as http:
        for chave, esperado in (("remotive", 404), ("nao_existe", 404), (CHAVE, 200)):
            rota = f"{GRUPO}/{chave}/login"
            dados = {CAMPO_CSRF: painel.token}
            resposta = http.post(rota, data=dados) if metodo == "POST" else http.get(rota)
            assert resposta.status_code == esperado, chave
    assert login_falso.chamadas in ([], [CHAVE])  # nunca a fonte pública


def test_login_agora_com_trava_presa_responde_em_andamento(
    painel: Painel, login_falso: LoginFalso
) -> None:
    trava = _trava_presa(painel)
    resposta = painel.post(LOGIN)
    assert resposta.status_code == 200
    assert _EM_ANDAMENTO in _texto(resposta.text)
    assert "<html" not in resposta.text  # só o fragmento, para o HTMX
    assert login_falso.chamadas == [] and login_falso.deps == []
    assert getattr(painel.app.state, "login_manual", {}) == {}
    assert trava.locked()  # a trava continua de quem a pegou


def test_login_agora_pega_a_trava_e_guarda_o_estado(
    painel: Painel, login_falso: LoginFalso
) -> None:
    painel.app.state.ambiente = {"DISPLAY": ":7"}
    with TestClient(painel.app, base_url=f"http://127.0.0.1:{PORTA}") as http:
        dados = {CAMPO_CSRF: painel.token}
        resposta = http.post(LOGIN, data=dados)
        assert resposta.status_code == 200
        assert "feche a janela quando terminar" in _texto(resposta.text)
        trava = painel.app.state.travas["login"]
        assert trava.locked()  # pega antes de responder: um segundo clique já vê presa
        assert painel.app.state.login_manual == {CHAVE: "aguardando"}
        assert _esperar(lambda: login_falso.chamadas == [CHAVE])
        assert login_falso.deps == [(painel.banco.parent, {"DISPLAY": ":7"})]
        assert http.get(LOGIN).status_code == 204  # nada mudou: o HTMX não troca a tela
        # segundo clique no mesmo site com a janela aberta: segue esperando, com o polling
        segundo = http.post(LOGIN, data=dados).text
        assert 'hx-trigger="every 5s"' in segundo
        assert "feche a janela quando terminar" in _texto(segundo)
        login_falso.liberar.set()
        assert _esperar(lambda: not trava.locked())
        assert painel.app.state.login_manual == {CHAVE: "pronto"}
        final = http.get(LOGIN)
        assert final.status_code == 200
        assert "Login feito" in _texto(final.text)
    assert login_falso.chamadas == [CHAVE]  # o segundo clique não abriu outro navegador


def test_login_que_quebra_mostra_erro_e_solta_a_trava(
    painel: Painel, login_falso: LoginFalso
) -> None:
    login_falso.erro = RuntimeError("quebrou")
    login_falso.liberar.set()
    with TestClient(painel.app, base_url=f"http://127.0.0.1:{PORTA}") as http:
        assert http.post(LOGIN, data={CAMPO_CSRF: painel.token}).status_code == 200
        trava = painel.app.state.travas["login"]
        assert _esperar(lambda: not trava.locked())
        assert painel.app.state.login_manual == {CHAVE: "erro"}
        assert "Algo deu errado ao abrir o navegador" in _texto(http.get(LOGIN).text)


_ESTADOS_DO_LOGIN = {
    "pt": {
        "aguardando": (
            "Entre no site e feche a janela quando terminar. Depois o joBot confere o login"
            " sozinho (a janela fecha em 10 minutos se ficar aberta)."
        ),
        "pronto": "Login feito. O joBot já pode ler este site.",
        "nao_entrou": (
            "Não deu para confirmar o login. Tente de novo e entre no site antes de fechar"
            " a janela."
        ),
        "tempo_esgotado": (
            "A janela ficou aberta por 10 minutos sem login e foi fechada. Tente de novo."
        ),
        "sem_tela": "Não achei a tela do computador",
        "sem_navegador": "Nenhum navegador encontrado",
        "em_uso": "O navegador do joBot já está aberto. Feche-o e tente de novo.",
        "erro": "Algo deu errado ao abrir o navegador",
    },
    "en": {
        "aguardando": (
            "Sign in to the site and close the window when you are done. joBot then checks"
            " the sign-in by itself (the window closes after 10 minutes if left open)."
        ),
        "pronto": "Signed in. joBot can now read this site.",
        "nao_entrou": (
            "Could not confirm the sign-in. Try again and sign in before closing the window."
        ),
        "tempo_esgotado": (
            "The window stayed open for 10 minutes without a sign-in and was closed. Try again."
        ),
        "sem_tela": "Could not find the computer's screen",
        "sem_navegador": "No browser found",
        "em_uso": "joBot's browser is already open. Close it and try again.",
        "erro": "Something went wrong opening the browser",
    },
}


@pytest.mark.parametrize("estado", list(_ESTADOS_DO_LOGIN["pt"]))
@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_estado_do_login_em_pt_e_en(painel: Painel, estado: str, idioma: str) -> None:
    painel.idioma(idioma)
    painel.app.state.login_manual = {CHAVE: estado}
    resposta = painel.http.get(LOGIN)
    esperado = _ESTADOS_DO_LOGIN[idioma][estado]
    if estado == "aguardando":
        assert resposta.status_code == 204  # a tela já mostra a espera
        resposta = painel.http.get(GRUPO)  # e a página recarregada também
    assert resposta.status_code == 200
    assert esperado in _texto(resposta.text)
    polling = 'hx-trigger="every 5s"' in resposta.text
    assert polling == (estado == "aguardando")  # só a espera pergunta de novo


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_login_sem_resultado_fechado(idioma: str) -> None:
    assert "configuracoes.sites_com_login.login.fechado" not in i18n.carregar()[idioma]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_cartao_tem_fazer_login_agora(painel: Painel, idioma: str) -> None:
    painel.idioma(idioma)
    html = painel.http.get(GRUPO).text
    rotulo = "Fazer login agora" if idioma == "pt" else "Sign in now"
    botao = re.search(rf"<button\b[^>]*>\s*{rotulo}\s*</button>", html)
    assert botao is not None
    assert f'hx-post="{LOGIN}"' in botao[0]


# ------------------------------------------------------------------ esquecer logins


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_esquecer_so_apaga_ao_confirmar_e_a_pergunta_antiga_saiu(
    painel: Painel, idioma: str
) -> None:
    painel.idioma(idioma)
    perfil = _perfil(painel)
    with closing(abrir(painel.banco)) as con:
        inserir_vaga(con)
        con.commit()
    antes = _contagem(painel)
    assert antes == (1, 1)

    assert painel.post(ESQUECER).status_code in (404, 405)  # a pergunta é o alerta da página
    assert perfil.exists() and (perfil / "Default" / "Cookies").exists()

    resposta = painel.post(CONFIRMAR)
    assert resposta.status_code == 200
    apagados = {"pt": "Logins apagados", "en": "Logins deleted"}[idioma]
    assert apagados in _texto(resposta.text)
    assert not perfil.exists()
    assert _contagem(painel) == antes  # vagas e ocorrências intactas
    assert painel.http.get(GRUPO).status_code == 200


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_esquecer_logins_sem_js_vai_para_confirmar(painel: Painel, idioma: str) -> None:
    """T307: o botão Esquecer logins, lido sem JavaScript, leva à página de confirmação (GET que
    não apaga nada); o texto é o do alerta, o botão faz o POST de hoje e o Cancelar volta."""
    painel.idioma(idioma)
    perfil = _perfil(painel)
    html = painel.http.get(GRUPO).text
    fora = re.sub(r"<dialog\b.*?</dialog>", "", html, flags=re.S)
    (form,) = re.findall(rf'<form[^>]*action="{CONFIRMAR}"[^>]*>.*?</form>', fora, re.S)
    assert 'method="get"' in form and CAMPO_CSRF not in form
    assert 'data-alerta-abre="alerta-esquecer"' in form

    for _ in range(2):  # GET repetido: nada muda
        resposta = painel.http.get(CONFIRMAR)
        assert resposta.status_code == 200
        assert (perfil / "Default" / "Cookies").exists()
    pagina = resposta.text
    pergunta, rotulo, cancelar = {
        "pt": ("Apagar os logins de todos os sites?", "Esquecer", "Cancelar"),
        "en": ("Delete the logins for all sites?", "Forget", "Cancel"),
    }[idioma]
    assert pergunta in _texto(pagina)
    explicacao = i18n.carregar()[idioma]["configuracoes.sites_com_login.esquecer.explicacao"]
    assert _texto(explicacao) in _texto(pagina)
    ((abertura, post),) = re.findall(
        rf'(<form[^>]*action="{CONFIRMAR}"[^>]*>)(.*?)</form>', pagina, re.S
    )
    assert 'method="post"' in abertura
    assert f'name="{CAMPO_CSRF}" value="{painel.token}"' in post
    assert re.search(rf"<button[^>]*type=\"submit\"[^>]*>\s*{rotulo}\s*</button>", post)
    assert re.search(rf'<a\b[^>]*href="{GRUPO}"[^>]*>\s*{cancelar}\s*</a>', pagina)
    sem_paleta = re.sub(r'<dialog\b[^>]*\bid="paleta".*?</dialog>', "", pagina, flags=re.S)
    assert "<dialog" not in sem_paleta and "autofocus" not in sem_paleta


def test_esquecer_logins_post_direto_continua(painel: Painel) -> None:
    """O POST de hoje (o do alerta e o do botão da página de confirmação) apaga como antes."""
    perfil = _perfil(painel)
    resposta = painel.post(CONFIRMAR)
    assert resposta.status_code == 200 and "Logins apagados" in _texto(resposta.text)
    assert not perfil.exists()


def test_esquecer_com_leitura_rodando_nao_apaga(painel: Painel) -> None:
    perfil = _perfil(painel)
    trava = _trava_presa(painel)
    resposta = painel.post(CONFIRMAR)
    assert resposta.status_code == 200
    assert _EM_ANDAMENTO in _texto(resposta.text)
    assert (perfil / "Default" / "Cookies").exists()
    assert trava.locked()
    trava.release()  # controle: com a trava livre, apaga
    assert "Logins apagados" in _texto(painel.post(CONFIRMAR).text)
    assert not perfil.exists()


def test_esquecer_com_navegador_symlink_nao_apaga_o_alvo(
    painel: Painel, tmp_path_factory: pytest.TempPathFactory, caplog: pytest.LogCaptureFixture
) -> None:
    fora = tmp_path_factory.mktemp("fora")
    (fora / "Cookies").write_text("de outro lugar")
    link = painel.banco.parent / PASTA_NAVEGADOR
    link.symlink_to(fora, target_is_directory=True)
    resposta = painel.post(CONFIRMAR)
    assert resposta.status_code == 200
    texto = _texto(resposta.text)
    assert "Não consegui apagar os logins" in texto
    assert "Logins apagados" not in texto
    assert (fora / "Cookies").read_text() == "de outro lugar"
    assert link.is_symlink()
    assert str(fora) not in resposta.text  # o caminho fica só no log
    assert not painel.app.state.travas["login"].locked()  # a trava volta mesmo com o erro
