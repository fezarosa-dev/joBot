"""Grupo "Sites com login" em Configurações (plano T218; D132.8, D132.23, D132.41, D132.48).

O painel não importa `jobot.navegador`: lê só o que o `serve` deixa em `app.state`.
"""

import html as html_lib
import json
import re
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apoio.relogio import RelogioFalso
from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import EstadoSaude, abrir_execucao, fechar_execucao, gravar_saude
from jobot.banco.migrar import migrar
from jobot.navegador import abrir as abrir_navegador
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47619
GRUPO = "/configuracoes/sites-com-login"
CHAVE = "falso_logado"
INTERRUPTOR = f"{GRUPO}/{CHAVE}/interruptor"
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


@pytest.mark.parametrize("metodo", ["GET", "POST"])
def test_sem_leitor_rota_da_404(sem_leitor: Painel, painel: Painel, metodo: str) -> None:
    def chamar(p: Painel) -> int:
        if metodo == "GET":
            return int(p.http.get(GRUPO).status_code)
        return int(p.post(GRUPO, {"horarios": "09:00, 18:00"}).status_code)

    assert chamar(painel) in (200, 303)  # controle: com leitor a rota existe
    assert chamar(sem_leitor) == 404


def test_sem_leitor_o_interruptor_da_404(sem_leitor: Painel) -> None:
    assert sem_leitor.post(INTERRUPTOR, {"ligada": "on"}).status_code == 404
    assert sem_leitor.ligada() == 0


def test_o_grupo_e_o_ultimo_das_abas(painel: Painel) -> None:
    assert _abas(painel.http.get("/configuracoes/fontes").text)[-1] == GRUPO


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


def test_esquecer_logins_so_aparece_sem_fazer_nada(painel: Painel) -> None:
    html = painel.http.get(GRUPO).text
    botao = re.search(r"<button\b[^>]*>\s*Esquecer logins\s*</button>", html)
    assert botao is not None
    assert "hx-post" not in botao[0] and 'type="submit"' not in botao[0]
    assert "disabled" in botao[0]


def test_nenhum_recurso_externo_na_pagina(painel: Painel) -> None:
    html = painel.http.get(GRUPO).text
    # recurso = o que a página carrega (src, link); o `<a>` do rodapé da base só aponta
    assert re.findall(r'(?:\ssrc|<link\b[^>]*\shref)="https?://', html) == []


def test_nome_do_leitor_e_escapado(painel: Painel) -> None:
    painel.leitor.nome = "<b>X</b>"
    html = painel.http.get(GRUPO).text
    assert "<b>X</b>" not in html
    assert "&lt;b&gt;X&lt;/b&gt;" in html
