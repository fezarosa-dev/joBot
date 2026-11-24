"""Aba IA de Configurações (desenho 5.6, 6 e 10.3 da fase 4; plano T415; D202).

Os atalhos ("Desligar a IA", "Tudo offline", "Tudo Claude") e a tabela por tarefa gravam
`ia_tarefas`; só os backends configurados aparecem; serviço pago leva "cobrado por uso" e
"experimental, ainda não provado"; ligar o `encaixe` num serviço pago pede confirmação do custo.
O cofre é o `CofreFalso` e o modelo local vem de `app.state.modelo_local`: nada toca o sistema.
"""

import asyncio
import html as html_lib
import json
import logging
import re
import threading
from contextlib import closing
from pathlib import Path
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient
from selectolax.lexbor import LexborHTMLParser

from apoio.cofre_falso import CofreFalso
from apoio.relogio import RelogioFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.navegador import limites
from jobot.nucleo.ia.contrato import Motivo
from jobot.painel.app import criar_app
from jobot.painel.i18n import carregar
from jobot.painel.seguranca import CAMPO_CSRF
from jobot.sistema.cofre import Cofre

PORTA = 47619
IA = "/configuracoes/ia"
CHAVE = "sk-ant-AbCd1234EfGh5678IjKl9012"
LOCAL = "Qwen3.5-4B-Q4_K_M"
DESLIGADA = {"ligada": False, "backend": "", "modelo": ""}


class Painel:
    """Cliente do app sobre um banco migrado, com cofre falso e o modelo local injetável."""

    def __init__(self, tmp_path: Path) -> None:
        self.banco = tmp_path / "jobot.db"
        with closing(abrir(self.banco)) as con:
            migrar(con, self.banco)
            cadastros.semear(con)
        self.cofre = Cofre(tmp_path, CofreFalso())
        self.app = criar_app(tmp_path, PORTA)
        self.app.state.cofre = self.cofre
        self.app.state.relogio = RelogioFalso()
        self.app.state.modelo_local = lambda: None
        self.acordar = asyncio.Event()
        self.app.state.ia_acordar = self.acordar
        self.http = TestClient(
            self.app,
            base_url=f"http://127.0.0.1:{PORTA}",
            follow_redirects=False,
            headers={"Accept-Language": "pt"},
        )
        self.token: str = self.app.state.csrf

    def get(self, url: str = IA) -> Any:
        return self.http.get(url)

    def post(self, dados: dict[str, Any], *, csrf: bool = True) -> Any:
        token = {CAMPO_CSRF: self.token} if csrf else {}
        return self.http.post(IA, data=token | dados)

    def config(self, chave: str, valor: object) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.gravar_config(con, chave, valor)

    def tarefa(self, ligada: bool, backend: str, modelo: str) -> None:
        self.config(
            "ia_tarefas", {"encaixe": {"ligada": ligada, "backend": backend, "modelo": modelo}}
        )

    def tarefas(self) -> object:
        with closing(abrir(self.banco)) as con:
            return cadastros.ler_config(con, "ia_tarefas")

    def idioma(self, idioma: str) -> None:
        self.config("idioma", idioma)

    def local(self, nome: str | None = LOCAL) -> None:
        self.app.state.modelo_local = lambda: nome


@pytest.fixture
def painel(tmp_path: Path) -> Painel:
    return Painel(tmp_path)


def _sem_paleta(html: str) -> str:
    return re.sub(r'<dialog id="paleta".*?</dialog>', "", html, flags=re.S)


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", _sem_paleta(html))))


def _opcoes(html: str) -> list[str]:
    select = LexborHTMLParser(html).css_first('select[name="encaixe_backend"]')
    return [] if select is None else [o.attributes["value"] or "" for o in select.css("option")]


def _atalhos(html: str) -> list[str]:
    """Os `value` dos botões de atalho da página."""
    return [
        b.attributes["value"] or "" for b in LexborHTMLParser(html).css('button[name="atalho"]')
    ]


def _destino(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.headers.get("location", "")


def pt(chave: str, **params: object) -> str:
    texto = carregar()["pt"][chave]
    return texto.format(**params) if params else texto


# ------------------------------------------------------------------ a aba


def test_tudo_desligado_na_primeira_abertura(painel: Painel) -> None:
    resposta = painel.get()
    assert resposta.status_code == 200
    texto = _texto(resposta.text)
    assert pt("configuracoes.ia.modo", modo=pt("configuracoes.ia.modo.desligada")) in texto
    assert pt("configuracoes.ia.privacidade.desligada") in texto
    caixa = LexborHTMLParser(resposta.text).css_first('input[name="encaixe_ligada"]')
    assert caixa is not None
    assert "checked" not in caixa.attributes
    assert painel.tarefas() == {"encaixe": DESLIGADA}  # abrir não grava nada


def test_ia_vem_depois_de_perfil_nas_abas(painel: Painel) -> None:
    resposta = painel.get()
    assert resposta.status_code == 200
    nav = resposta.text.split('class="config-grupos"')[1].split("</nav>")[0]
    abas = re.findall(r'href="/configuracoes/([^"]+)"', nav)
    assert abas[abas.index("funcoes") + 1 : abas.index("funcoes") + 3] == ["perfil", "ia"]
    assert re.search(r'href="/configuracoes/ia"[^>]*aria-current="page"', nav)


def test_um_botao_principal_por_tela(painel: Painel) -> None:
    painel.local()
    painel.cofre.gravar("ia_anthropic", CHAVE)
    html = painel.get().text
    assert len(re.findall(r'class="[^"]*botao-primario', _sem_paleta(html))) == 1
    aviso = painel.post({"atalho": "claude"}).text  # na confirmação de custo também
    assert len(re.findall(r'class="[^"]*botao-primario', _sem_paleta(aviso))) == 1


@pytest.mark.parametrize("dados", [{"atalho": "desligada"}, {"encaixe_backend": ""}])
def test_post_sem_csrf_e_recusado(painel: Painel, dados: dict[str, str]) -> None:
    painel.tarefa(True, "local", LOCAL)
    resposta = painel.post(dados, csrf=False)
    assert resposta.status_code == 403
    assert painel.tarefas() == {"encaixe": {"ligada": True, "backend": "local", "modelo": LOCAL}}
    assert painel.post(dados).status_code == 303  # controle: com o token, grava


# ------------------------------------------------------------------ atalhos


def test_desligar_a_ia_mantem_o_backend_e_o_modelo(painel: Painel) -> None:
    painel.tarefa(True, "openai", "gpt-x")
    assert _destino(painel.post({"atalho": "desligada"})) == (303, IA + "?salvo=1")
    assert painel.tarefas() == {
        "encaixe": {"ligada": False, "backend": "openai", "modelo": "gpt-x"},
        "perguntas": DESLIGADA,  # o atalho grava todas as tarefas do `ia.json` (T437)
        "curriculo": DESLIGADA,  # e a do currículo (T436)
    }
    assert not painel.acordar.is_set()  # desligar não acorda o laço


def test_tudo_offline_grava_o_modelo_local_e_acorda_o_laco(painel: Painel) -> None:
    painel.local()
    assert "offline" in _atalhos(painel.get().text)
    assert _destino(painel.post({"atalho": "offline"})) == (303, IA + "?salvo=1")
    no_local = {"ligada": True, "backend": "local", "modelo": LOCAL}
    assert painel.tarefas() == {"encaixe": no_local, "perguntas": no_local, "curriculo": no_local}
    assert painel.acordar.is_set()
    texto = _texto(painel.get().text)
    assert pt("configuracoes.ia.modo", modo=pt("configuracoes.ia.modo.offline")) in texto


def test_tudo_offline_sem_o_modelo_leva_a_ferramentas(painel: Painel) -> None:
    html = painel.get().text
    assert "offline" not in _atalhos(html)
    link = LexborHTMLParser(html).css_first('a.botao[href="/configuracoes/ferramentas"]')
    assert link is not None
    assert link.text(strip=True) == pt("configuracoes.ia.atalho.offline.baixar")
    resposta = painel.post({"atalho": "offline"})
    assert _destino(resposta) == (303, "/configuracoes/ferramentas")
    assert painel.tarefas() == {"encaixe": DESLIGADA}
    # o destino tem o cartão do modelo local mesmo sem leitor com login (T417; D185.20)
    painel.app.state.leitores = ()
    ferramentas = painel.get("/configuracoes/ferramentas")
    assert ferramentas.status_code == 200
    assert 'id="ferramenta-ia-local"' in ferramentas.text


def test_atalhos_preservam_tarefa_desconhecida(painel: Painel) -> None:
    painel.local()
    outra = {"ligada": True, "backend": "openai", "modelo": "y"}
    painel.config("ia_tarefas", {"encaixe": DESLIGADA, "futura": outra})
    painel.post({"atalho": "offline"})
    assert painel.tarefas() == {
        "encaixe": {"ligada": True, "backend": "local", "modelo": LOCAL},
        "perguntas": {"ligada": True, "backend": "local", "modelo": LOCAL},
        "curriculo": {"ligada": True, "backend": "local", "modelo": LOCAL},
        "futura": outra,
    }


@pytest.mark.parametrize(
    ("idioma", "frase"),
    [("pt", "API da Anthropic, cobrada por uso"), ("en", "Anthropic API, billed per use")],
)
def test_tudo_claude_diz_api_da_anthropic_cobrada_por_uso(
    painel: Painel, idioma: str, frase: str
) -> None:
    painel.idioma(idioma)
    painel.cofre.gravar("ia_anthropic", CHAVE)
    html = painel.get().text
    assert "claude" in _atalhos(html)
    assert frase in _texto(html)


def test_tudo_claude_sem_chave_leva_a_servicos(painel: Painel) -> None:
    html = painel.get().text
    assert "claude" not in _atalhos(html)
    assert pt("configuracoes.ia.atalho.claude.ajuda") in _texto(html)  # o custo já aparece
    link = LexborHTMLParser(html).css_first('a.botao[href="/configuracoes/servicos"]')
    assert link is not None
    assert link.text(strip=True) == pt("configuracoes.ia.atalho.claude.chave")
    assert _destino(painel.post({"atalho": "claude"})) == (303, "/configuracoes/servicos")
    assert painel.tarefas() == {"encaixe": DESLIGADA}


def test_tudo_claude_pede_confirmacao_do_custo_antes_de_gravar(painel: Painel) -> None:
    painel.cofre.gravar("ia_anthropic", CHAVE)
    resposta = painel.post({"atalho": "claude"})
    assert resposta.status_code == 200
    assert painel.tarefas() == {"encaixe": DESLIGADA}
    assert not painel.acordar.is_set()
    texto = _texto(resposta.text)
    titulo = pt("configuracoes.servicos.ia.anthropic.titulo")
    assert pt("configuracoes.ia.custo.texto", servico=titulo, teto=200) in texto
    form = LexborHTMLParser(resposta.text).css_first("form[data-confirmar-custo]")
    assert form is not None
    ocultos = {
        i.attributes["name"]: i.attributes["value"] for i in form.css('input[type="hidden"]')
    }
    assert ocultos == {CAMPO_CSRF: painel.token, "atalho": "claude", "confirmar": "1"}

    assert _destino(painel.post({"atalho": "claude", "confirmar": "1"})) == (303, IA + "?salvo=1")
    assert painel.tarefas() == {
        "encaixe": {"ligada": True, "backend": "anthropic", "modelo": "claude-haiku-5-5"},
        "perguntas": {"ligada": True, "backend": "anthropic", "modelo": "claude-sonnet-5-5"},
        "curriculo": {"ligada": True, "backend": "anthropic", "modelo": "claude-sonnet-5-5"},
    }
    assert painel.acordar.is_set()
    modo = pt("configuracoes.ia.modo", modo=pt("configuracoes.ia.modo.claude"))
    assert modo in _texto(painel.get().text)


def test_confirmacao_do_custo_abre_com_o_foco_no_aviso(painel: Painel) -> None:
    # o Return repetido de quem apertou "Tudo Claude" não pode cair em "Ligar mesmo assim"
    painel.cofre.gravar("ia_anthropic", CHAVE)
    arvore = LexborHTMLParser(painel.post({"atalho": "claude"}).text)
    aviso = arvore.css_first('section[aria-labelledby="ia-custo-titulo"]')
    assert aviso is not None
    assert "autofocus" in aviso.attributes
    assert aviso.attributes.get("tabindex") == "-1"
    assert aviso.css("form [autofocus]") == []  # nem o "Ligar mesmo assim" nem outro botão


def test_atalho_desconhecido_e_422(painel: Painel) -> None:
    assert painel.post({"atalho": "tudo"}).status_code == 422
    assert painel.tarefas() == {"encaixe": DESLIGADA}


# ------------------------------------------------------------------ backends


def test_so_backends_configurados_aparecem(painel: Painel) -> None:
    html = painel.get().text
    assert _opcoes(html) == []
    assert pt("configuracoes.ia.sem_backend") in _texto(html)
    caixa = LexborHTMLParser(html).css_first('input[name="encaixe_ligada"]')
    assert caixa is not None
    assert "disabled" in caixa.attributes  # sem lugar para rodar, não liga

    painel.cofre.gravar("ia_openai", "sk-1234567890")
    painel.config("ia_compativel", {"endereco": "http://127.0.0.1:11434/v1"})
    assert _opcoes(painel.get().text) == ["openai", "compativel"]

    painel.cofre.gravar("ia_anthropic", CHAVE)
    painel.cofre.gravar("ia_gemini", "AIza1234567890")
    painel.local()
    opcoes = _opcoes(painel.get().text)
    assert opcoes == ["anthropic", "openai", "gemini", "compativel", "local"]


def test_compativel_so_com_endereco(painel: Painel) -> None:
    painel.cofre.gravar("ia_compativel", "chave-opcional-123")  # chave sem endereço não basta
    assert _opcoes(painel.get().text) == []
    painel.config("ia_compativel", {"endereco": "https://exemplo.invalid/v1"})
    assert _opcoes(painel.get().text) == ["compativel"]


def test_backend_nao_configurado_e_422_e_nada_grava(painel: Painel) -> None:
    painel.cofre.gravar("ia_openai", "sk-1234567890")
    dados = {"encaixe_ligada": "on", "encaixe_backend": "gemini", "encaixe_modelo": "x"}
    assert painel.post(dados).status_code == 422
    assert painel.tarefas() == {"encaixe": DESLIGADA}
    dados["encaixe_backend"] = "openai"  # controle: o configurado grava (com a confirmação)
    assert painel.post(dados | {"confirmar": "1"}).status_code == 303


def test_tarefa_ligada_num_servico_sem_chave_avisa(painel: Painel) -> None:
    painel.tarefa(True, "openai", "gpt-x")  # a chave foi apagada em Serviços
    texto = _texto(painel.get().text)
    servico = pt("configuracoes.perfil.servico.openai")
    assert pt("configuracoes.ia.sem_servico", servico=servico) in texto
    painel.cofre.gravar("ia_openai", "sk-1234567890")
    assert pt("configuracoes.ia.sem_servico", servico=servico) not in _texto(painel.get().text)


def test_modelo_local_que_sumiu_avisa(painel: Painel) -> None:
    painel.tarefa(True, "local", LOCAL)
    assert pt("configuracoes.ia.sem_servico.local") in _texto(painel.get().text)
    painel.local()
    assert pt("configuracoes.ia.sem_servico.local") not in _texto(painel.get().text)


def test_cofre_travado_avisa_e_esconde_os_servicos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path)
    trava = threading.Event()
    painel.app.state.cofre = Cofre(tmp_path, CofreFalso(trava=trava))
    painel.local()
    monkeypatch.setattr(limites, "PRAZO_COFRE_S", 0.05)
    try:
        resposta = painel.get()
    finally:
        trava.set()  # solta as threads presas
    assert resposta.status_code == 200
    assert pt("configuracoes.servicos.erro.cofre") in _texto(resposta.text)
    assert _opcoes(resposta.text) == ["local"]


@pytest.mark.parametrize("backend", ["anthropic", "openai", "gemini"])
def test_servico_pago_diz_cobrado_por_uso_e_experimental(painel: Painel, backend: str) -> None:
    painel.cofre.gravar(f"ia_{backend}", CHAVE)
    painel.tarefa(False, backend, "m")
    html = painel.get().text
    opcao = LexborHTMLParser(html).css_first(f'option[value="{backend}"]')
    assert opcao is not None
    assert "selected" in opcao.attributes
    assert re.search(r"cobrad[ao] por uso", opcao.text())
    texto = _texto(html)
    assert pt("configuracoes.ia.cobrado") in texto
    assert pt("configuracoes.ia.experimental") in texto


@pytest.mark.parametrize("backend", ["compativel", "local"])
def test_compativel_e_local_sem_cobrado_nem_experimental(painel: Painel, backend: str) -> None:
    painel.config("ia_compativel", {"endereco": "http://127.0.0.1:11434/v1"})
    painel.local()
    painel.tarefa(True, backend, LOCAL)
    texto = _texto(painel.get().text)
    for chave in ("configuracoes.ia.cobrado", "configuracoes.ia.experimental"):
        assert pt(chave) not in texto
    painel.cofre.gravar("ia_openai", CHAVE)  # controle: com o pago escolhido, as duas aparecem
    painel.tarefa(True, "openai", "m")
    texto = _texto(painel.get().text)
    assert pt("configuracoes.ia.cobrado") in texto
    assert pt("configuracoes.ia.experimental") in texto


# ------------------------------------------------------------------ a tabela


def test_ligar_no_compativel_grava_sem_aviso(painel: Painel) -> None:
    painel.config("ia_compativel", {"endereco": "http://127.0.0.1:11434/v1"})
    dados = {
        "encaixe_ligada": "on",
        "encaixe_backend": "compativel",
        "encaixe_modelo": " qwen3:4b ",
    }
    assert _destino(painel.post(dados)) == (303, IA + "?salvo=1")
    assert painel.tarefas() == {
        "encaixe": {"ligada": True, "backend": "compativel", "modelo": "qwen3:4b"}
    }
    assert painel.acordar.is_set()
    modo = pt("configuracoes.ia.modo", modo=pt("configuracoes.ia.modo.personalizado"))
    assert modo in _texto(painel.get().text)


def test_local_grava_o_modelo_baixado_mesmo_com_outro_digitado(painel: Painel) -> None:
    painel.local()
    dados = {"encaixe_ligada": "on", "encaixe_backend": "local", "encaixe_modelo": "outro"}
    assert painel.post(dados).status_code == 303
    assert painel.tarefas() == {"encaixe": {"ligada": True, "backend": "local", "modelo": LOCAL}}


@pytest.mark.parametrize("backend", ["anthropic", "openai", "gemini"])
def test_ligar_encaixe_num_servico_pago_mostra_o_aviso_de_custo(
    painel: Painel, backend: str
) -> None:
    painel.cofre.gravar(f"ia_{backend}", CHAVE)
    modelo = "claude-sonnet-5-5" if backend == "anthropic" else "modelo-x"
    dados = {"encaixe_ligada": "on", "encaixe_backend": backend, "encaixe_modelo": modelo}
    resposta = painel.post(dados)
    assert resposta.status_code == 200
    assert painel.tarefas() == {"encaixe": DESLIGADA}
    titulo = pt(f"configuracoes.servicos.ia.{backend}.titulo")
    assert pt("configuracoes.ia.custo.texto", servico=titulo, teto=200) in _texto(resposta.text)
    form = LexborHTMLParser(resposta.text).css_first("form[data-confirmar-custo]")
    assert form is not None
    ocultos = {
        i.attributes["name"]: i.attributes["value"] for i in form.css('input[type="hidden"]')
    }
    assert ocultos == {CAMPO_CSRF: painel.token, **dados, "confirmar": "1"}
    assert painel.post(dados | {"confirmar": "1"}).status_code == 303
    assert painel.tarefas() == {"encaixe": {"ligada": True, "backend": backend, "modelo": modelo}}


def test_trocar_so_o_modelo_no_mesmo_servico_pago_nao_pede_de_novo(painel: Painel) -> None:
    painel.cofre.gravar("ia_openai", CHAVE)
    painel.tarefa(True, "openai", "modelo-a")
    dados = {"encaixe_ligada": "on", "encaixe_backend": "openai", "encaixe_modelo": "modelo-b"}
    assert painel.post(dados).status_code == 303
    assert painel.tarefas() == {
        "encaixe": {"ligada": True, "backend": "openai", "modelo": "modelo-b"}
    }
    painel.cofre.gravar("ia_gemini", CHAVE)  # controle: trocar de serviço pago pede
    dados["encaixe_backend"] = "gemini"
    assert painel.post(dados).status_code == 200


def test_salvar_desligada_num_pago_nao_pede_confirmacao(painel: Painel) -> None:
    painel.cofre.gravar("ia_openai", CHAVE)
    dados = {"encaixe_backend": "openai", "encaixe_modelo": "gpt-x"}
    assert painel.post(dados).status_code == 303
    assert painel.tarefas() == {
        "encaixe": {"ligada": False, "backend": "openai", "modelo": "gpt-x"}
    }
    assert not painel.acordar.is_set()


def test_claude_com_modelo_vazio_usa_o_padrao_da_tarefa(painel: Painel) -> None:
    painel.cofre.gravar("ia_anthropic", CHAVE)
    dados = {"encaixe_ligada": "on", "encaixe_backend": "anthropic", "encaixe_modelo": " "}
    assert painel.post(dados | {"confirmar": "1"}).status_code == 303
    assert painel.tarefas() == {
        "encaixe": {"ligada": True, "backend": "anthropic", "modelo": "claude-haiku-5-5"}
    }


@pytest.mark.parametrize(
    ("backend", "modelo", "erro"),
    [
        ("anthropic", "claude-opus-5-5", "configuracoes.ia.erro.modelo_claude"),
        ("openai", "", "configuracoes.ia.erro.modelo"),
        ("openai", "gpt x", "configuracoes.ia.erro.modelo"),
        ("openai", "g" * 201, "configuracoes.ia.erro.modelo"),
        ("", "gpt-x", "configuracoes.ia.erro.sem_backend"),
    ],
)
def test_modelo_ou_backend_invalido_volta_com_422_e_nada_grava(
    painel: Painel, backend: str, modelo: str, erro: str
) -> None:
    painel.cofre.gravar("ia_anthropic", CHAVE)
    painel.cofre.gravar("ia_openai", CHAVE)
    dados = {
        "encaixe_ligada": "on",
        "encaixe_backend": backend,
        "encaixe_modelo": modelo,
        "confirmar": "1",
    }
    resposta = painel.post(dados)
    assert resposta.status_code == 422
    assert painel.tarefas() == {"encaixe": DESLIGADA}
    assert pt(erro) in _texto(resposta.text)
    arvore = LexborHTMLParser(resposta.text)
    campo = arvore.css_first(
        'select[name="encaixe_backend"]' if not backend else 'input[name="encaixe_modelo"]'
    )
    assert campo is not None
    assert campo.attributes.get("aria-invalid") == "true"
    # o campo aponta para a mensagem do erro, não só para a ajuda
    assert "config-erro" in (campo.attributes.get("aria-describedby") or "").split()
    alerta = arvore.css_first("#config-erro")
    assert alerta is not None
    assert pt(erro) in _texto(alerta.html or "")
    if backend:  # o digitado volta para corrigir
        assert campo.attributes.get("value") == modelo
    caixa = arvore.css_first('input[name="encaixe_ligada"]')
    assert caixa is not None
    assert "checked" in caixa.attributes


def test_modelo_de_200_caracteres_vale(painel: Painel) -> None:
    painel.cofre.gravar("ia_openai", CHAVE)
    dados = {"encaixe_backend": "openai", "encaixe_modelo": "g" * 200}
    assert painel.post(dados).status_code == 303


@pytest.mark.parametrize("ligada", [False, True])
def test_salvar_sem_o_select_mantem_a_tarefa_gravada(painel: Painel, ligada: bool) -> None:
    # a chave saiu: a tela não mostra o select e a caixa vem desativada (não vai no form)
    painel.tarefa(ligada, "openai", "gpt-x")
    assert _opcoes(painel.get().text) == []
    assert painel.post({}).status_code == 303
    tarefa = {"ligada": ligada, "backend": "openai", "modelo": "gpt-x"}
    assert painel.tarefas() == {"encaixe": tarefa}


def test_cofre_travado_e_salvar_nao_apaga_a_tarefa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel = Painel(tmp_path)
    painel.tarefa(True, "anthropic", "claude-haiku-5-5")
    trava = threading.Event()
    painel.app.state.cofre = Cofre(tmp_path, CofreFalso(trava=trava))
    monkeypatch.setattr(limites, "PRAZO_COFRE_S", 0.05)
    try:
        assert _opcoes(painel.get().text) == []
        assert painel.post({}).status_code == 303
    finally:
        trava.set()  # solta as threads presas
    tarefa = {"ligada": True, "backend": "anthropic", "modelo": "claude-haiku-5-5"}
    assert painel.tarefas() == {"encaixe": tarefa}


# ------------------------------------------------------------------ frases e contagem


def test_frase_de_privacidade_por_tarefa(painel: Painel) -> None:
    painel.local()
    painel.cofre.gravar("ia_gemini", CHAVE)
    painel.tarefa(True, "local", LOCAL)
    texto = _texto(painel.get().text)
    assert pt("configuracoes.ia.privacidade.local") in texto
    painel.tarefa(True, "gemini", "m")
    texto = _texto(painel.get().text)
    servico = pt("configuracoes.perfil.servico.gemini")
    assert pt("configuracoes.ia.privacidade.fora", servico=servico) in texto
    painel.tarefa(True, "estranho", "m")  # backend desconhecido: "um serviço de fora"
    texto = _texto(painel.get().text)
    outro = pt("configuracoes.perfil.servico.outro")
    assert pt("configuracoes.ia.privacidade.fora", servico=outro) in texto


def test_chamadas_de_hoje_num_servico_de_fora(painel: Painel) -> None:
    painel.cofre.gravar("ia_openai", CHAVE)
    painel.tarefa(True, "openai", "gpt-x")
    dia = painel.app.state.relogio.agora().astimezone().date().isoformat()  # o dia local
    painel.config("ia_chamadas", {"dia": dia, "por_backend": {"openai": 37, "gemini": 5}})
    texto = _texto(painel.get().text)
    assert pt("configuracoes.ia.hoje", n=37, teto=200) in texto
    assert "37 de 200 hoje" in texto
    painel.config("ia_chamadas", {"dia": "2000-01-01", "por_backend": {"openai": 37}})
    assert pt("configuracoes.ia.hoje", n=0, teto=200) in _texto(painel.get().text)


def test_modelo_local_nao_mostra_contagem(painel: Painel) -> None:
    painel.local()
    painel.tarefa(True, "local", LOCAL)
    dia = painel.app.state.relogio.agora().astimezone().date().isoformat()
    painel.config("ia_chamadas", {"dia": dia, "por_backend": {"local": 9, "openai": 9}})
    assert "de 200 hoje" not in _texto(painel.get().text)
    painel.cofre.gravar("ia_openai", CHAVE)  # controle: num serviço de fora, a contagem aparece
    painel.tarefa(True, "openai", "gpt-x")
    assert "9 de 200 hoje" in _texto(painel.get().text)


def test_contagem_do_dia_so_nas_tarefas_do_laco(painel: Painel) -> None:
    """O teto do dia é do laço (`encaixe`): a linha Perguntas, sob pedido, não mostra a contagem
    que não é dela. Controle: com o encaixe no mesmo serviço, a contagem aparece uma vez."""
    painel.cofre.gravar("ia_openai", CHAVE)
    dia = painel.app.state.relogio.agora().astimezone().date().isoformat()
    painel.config("ia_chamadas", {"dia": dia, "por_backend": {"openai": 7}})
    perguntas = {"ligada": True, "backend": "openai", "modelo": "gpt-x"}
    painel.config("ia_tarefas", {"perguntas": perguntas})
    assert "de 200 hoje" not in _texto(painel.get().text)
    painel.config("ia_tarefas", {"perguntas": perguntas, "encaixe": perguntas})
    assert _texto(painel.get().text).count("7 de 200 hoje") == 1


def test_chave_nunca_volta_a_pagina_nem_ao_log(
    painel: Painel, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    for servico in ("anthropic", "openai", "gemini", "compativel"):
        painel.cofre.gravar(f"ia_{servico}", CHAVE)
    painel.config("ia_compativel", {"endereco": "http://127.0.0.1:11434/v1"})
    paginas = [
        painel.get().text,
        painel.post({"atalho": "claude"}).text,
        painel.post({"encaixe_ligada": "on", "encaixe_backend": "openai"}).text,
    ]
    # controle: a página viu as chaves (os quatro serviços aparecem)
    assert _opcoes(paginas[0]) == ["anthropic", "openai", "gemini", "compativel"]
    for html in paginas:
        assert CHAVE not in html
        assert CHAVE[-4:] not in html  # nem a máscara: a aba IA não mostra chave nenhuma
    assert all(CHAVE not in r.getMessage() for r in caplog.records)


def test_sem_modelo_local_injetado_conta_como_ausente(tmp_path: Path) -> None:
    painel = Painel(tmp_path)
    del painel.app.state.modelo_local  # o app sem o `serve` (montar) não tem o leitor
    html = painel.get().text
    assert "offline" not in _atalhos(html)
    assert _opcoes(html) == []
    painel.local()  # controle: com o leitor, o modelo local aparece
    html = painel.get().text
    assert "offline" in _atalhos(html)
    assert _opcoes(html) == ["local"]


# ------------------------------------------------------------------ textos


@pytest.mark.parametrize("lingua", ["pt", "en"])
def test_todo_motivo_de_falha_tem_texto(lingua: str) -> None:
    catalogo = carregar()[lingua]
    motivos = get_args(Motivo)
    assert len(motivos) == 12
    faltam = [m for m in motivos if not catalogo.get(f"configuracoes.ia.falha.{m}")]
    assert faltam == []
    # a chave da Anthropic presa a um workspace (D192.3)
    especial = catalogo["configuracoes.ia.falha.chave_recusada.anthropic"]
    assert "workspace" in especial


def test_textos_da_aba_em_ingles(painel: Painel) -> None:
    painel.idioma("en")
    painel.local()
    texto = _texto(painel.get().text)
    assert "Shortcuts" in texto
    assert "All offline" in texto
    assert "Off: job texts do not leave your computer." in texto
    assert "Atalhos" not in texto


def test_catalogos_sem_chave_ia_so_de_um_lado() -> None:
    pt_, en = carregar()["pt"], carregar()["en"]
    so_pt = {c for c in pt_ if c.startswith("configuracoes.ia.")} - set(en)
    so_en = {c for c in en if c.startswith("configuracoes.ia.")} - set(pt_)
    assert (so_pt, so_en) == (set(), set())
    assert json.dumps(sorted(c for c in pt_ if c.startswith("configuracoes.ia."))) != "[]"


# ------------------------------------------------------------------ perguntas (T437; D233)


def test_tarefa_perguntas_aparece_com_a_frase_dela(painel: Painel) -> None:
    painel.cofre.gravar("ia_gemini", CHAVE)
    painel.config("ia_tarefas", {"perguntas": {"ligada": True, "backend": "gemini", "modelo": "m"}})
    html = painel.get().text
    assert LexborHTMLParser(html).css_first('input[name="perguntas_ligada"]') is not None
    texto = _texto(html)
    assert pt("configuracoes.ia.tarefa.perguntas") in texto
    assert pt("configuracoes.ia.tarefa.perguntas.ajuda") in texto
    servico = pt("configuracoes.perfil.servico.gemini")
    assert pt("configuracoes.ia.privacidade.perguntas.fora", servico=servico) in texto
    # o encaixe, desligado, segue com a frase dele
    assert pt("configuracoes.ia.privacidade.desligada") in texto


def test_ligar_perguntas_num_servico_pago_nao_pede_confirmacao(painel: Painel) -> None:
    """(guarda) A tarefa sob pedido não vai ao aviso de custo do laço; controle: o encaixe vai."""
    painel.cofre.gravar("ia_openai", CHAVE)
    dados = {"perguntas_ligada": "on", "perguntas_backend": "openai", "perguntas_modelo": "gpt-x"}
    assert painel.post(dados).status_code == 303
    tarefas = painel.tarefas()
    assert isinstance(tarefas, dict)
    assert tarefas.get("perguntas") == {"ligada": True, "backend": "openai", "modelo": "gpt-x"}
    controle = {"encaixe_ligada": "on", "encaixe_backend": "openai", "encaixe_modelo": "gpt-x"}
    assert painel.post(dados | controle).status_code == 200


def test_tudo_claude_liga_perguntas_no_sonnet(painel: Painel) -> None:
    painel.cofre.gravar("ia_anthropic", CHAVE)
    assert painel.post({"atalho": "claude", "confirmar": "1"}).status_code == 303
    tarefas = painel.tarefas()
    assert isinstance(tarefas, dict)
    assert tarefas.get("perguntas") == {
        "ligada": True,
        "backend": "anthropic",
        "modelo": "claude-sonnet-5-5",
    }


# ------------------------------------------------------------------ currículo e IA manual (T436)


def _opcoes_de(html: str, tarefa: str) -> list[str]:
    select = LexborHTMLParser(html).css_first(f'select[name="{tarefa}_backend"]')
    return [] if select is None else [o.attributes["value"] or "" for o in select.css("option")]


def test_curriculo_aparece_com_a_frase_dela_e_so_ele_tem_a_ia_manual(painel: Painel) -> None:
    html = painel.get().text
    # sem serviço configurado, a IA manual já serve ao currículo; as outras não têm onde rodar
    assert _opcoes_de(html, "curriculo") == ["manual"]
    assert (_opcoes_de(html, "encaixe"), _opcoes_de(html, "perguntas")) == ([], [])
    texto = _texto(html)
    assert pt("configuracoes.ia.tarefa.curriculo") in texto
    assert pt("configuracoes.ia.tarefa.curriculo.ajuda") in texto
    assert pt("configuracoes.ia.privacidade.curriculo.desligada") in texto
    caixa = LexborHTMLParser(html).css_first('input[name="curriculo_ligada"]')
    assert caixa is not None and "disabled" not in caixa.attributes
    painel.cofre.gravar("ia_openai", CHAVE)
    html = painel.get().text
    assert _opcoes_de(html, "curriculo") == ["openai", "manual"]
    assert _opcoes_de(html, "encaixe") == ["openai"] == _opcoes_de(html, "perguntas")
    assert pt("configuracoes.ia.backend.manual") in _texto(html)


@pytest.mark.parametrize(
    ("tarefa", "frase"),
    [
        ("curriculo", "configuracoes.ia.privacidade.curriculo.manual"),
        ("encaixe", None),
        ("perguntas", None),
    ],
)
def test_ia_manual_so_no_curriculo(painel: Painel, tarefa: str, frase: str | None) -> None:
    # o modelo digitado não conta: a manual grava o modelo vazio
    dados = {f"{tarefa}_ligada": "on", f"{tarefa}_backend": "manual", f"{tarefa}_modelo": "gpt-x"}
    resposta = painel.post(dados)
    if frase is None:  # a lista é fechada: a tela não mostra "manual" nessas tarefas
        assert resposta.status_code == 422
        assert painel.tarefas() == {"encaixe": DESLIGADA}
        return
    assert _destino(resposta) == (303, IA + "?salvo=1")
    tarefas = painel.tarefas()
    assert isinstance(tarefas, dict)
    assert tarefas["curriculo"] == {"ligada": True, "backend": "manual", "modelo": ""}
    texto = _texto(painel.get().text)
    assert pt(frase) in texto
    assert pt("configuracoes.ia.hoje", n=0, teto=200) not in texto  # a manual não tem teto
