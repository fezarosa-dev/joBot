"""Cada seção da aba Perfil salva sozinha (D230, decidido pelo dono em 2026-11-24).

Com HTMX, o Salvar de uma seção troca só a própria seção (`hx-select` dela), e o que foi digitado
nas outras fica na tela; o "Salvo." e o alerta do erro moram dentro da seção, para a troca os
trazer. Sem JavaScript (T443, D237.3), a aba é um formulário só: cada Salvar manda tudo, grava só a
sua seção e a página volta com o que foi digitado nas outras.
"""

import html as html_lib
import re
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from selectolax.lexbor import LexborHTMLParser

from apoio.relogio import RelogioFalso
from jobot.banco import cadastros, perfil
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.painel import i18n
from jobot.painel.app import criar_app
from jobot.painel.seguranca import CAMPO_CSRF

PORTA = 47619
PERFIL = "/configuracoes/perfil"
SECOES = ("sobre", "habilidades", "experiencias", "cursos")
DADOS = {
    "secao": "dados",
    "nome": "",
    "email": "",
    "telefone": "",
    "cidade_moradia": "",
    "cargo_atual": "",
    "anos_de_experiencia": "",
    "formacao_nivel": "",
    "resumo": "",
    "links": "",
    "idioma_pt": "",
    "idioma_en": "",
    "idioma_es": "",
}


class Http(TestClient):
    """O cliente do app com o token CSRF e o banco à mão."""

    token: str
    banco: Path

    def gravar(self, dados: dict[str, Any]) -> Any:
        return self.post(PERFIL, data={CAMPO_CSRF: self.token} | dados)

    def idioma(self, idioma: str) -> None:
        with closing(abrir(self.banco)) as con:
            cadastros.gravar_config(con, "idioma", idioma)


@pytest.fixture
def http(tmp_path: Path) -> Http:
    banco = tmp_path / "jobot.db"
    with closing(abrir(banco)) as con:
        migrar(con, banco)
        cadastros.semear(con)
    app = criar_app(tmp_path, PORTA)
    app.state.relogio = RelogioFalso()
    cliente = Http(app, base_url=f"http://127.0.0.1:{PORTA}", follow_redirects=False)
    cliente.token, cliente.banco = app.state.csrf, banco
    return cliente


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", html)))


def pt(chave: str) -> str:
    return i18n.carregar()["pt"][chave]


def _fora_das_secoes(html: str) -> str:
    """A página sem as seções que trocam sozinhas: o que sobra é o alto da aba."""
    arvore = LexborHTMLParser(html)
    for secao in arvore.css("section[id^='bloco-']"):
        secao.decompose()
    conteudo = arvore.css_first(".config-conteudo")
    assert conteudo is not None
    return _texto(conteudo.html or "")


def test_cada_secao_troca_so_a_si_mesma(http: Http) -> None:
    arvore = LexborHTMLParser(http.get(PERFIL).text)
    for nome in SECOES:
        secao = arvore.css_first(f"section#bloco-{nome}")
        assert secao is not None, nome
        atributos = secao.attributes
        assert atributos.get("hx-select") == f"#bloco-{nome}", nome
        assert (atributos.get("hx-target"), atributos.get("hx-swap")) == ("this", "outerHTML")
        assert "data-troca-422" in atributos, nome
        botoes = secao.css("button[type=submit]")
        assert botoes, nome
        for botao in botoes:  # sem JavaScript, o mesmo botão posta igual, e volta à seção
            atributos = botao.attributes
            assert atributos.get("hx-post") == PERFIL, nome
            assert atributos.get("formaction") == f"{PERFIL}#perfil-{nome}", nome


@pytest.mark.parametrize(
    ("secao", "dados", "ancora"),
    [
        (None, {"habilidades": "Python"}, "habilidades"),
        ("dados", DADOS | {"nome": "Ana"}, "sobre"),
        (
            "experiencia",
            {
                "secao": "experiencia",
                "id": "",
                "cargo": "Analista",
                "empresa": "",
                "inicio": "",
                "fim": "",
                "descricao": "",
            },
            "experiencias",
        ),
        (
            "curso",
            {
                "secao": "curso",
                "id": "",
                "nome": "ADS",
                "instituicao": "",
                "situacao": "",
                "previsao": "",
            },
            "cursos",
        ),
    ],
)
def test_salvo_aparece_dentro_da_secao_que_gravou(
    http: Http, secao: str | None, dados: dict[str, str], ancora: str
) -> None:
    resposta = http.gravar(dados)
    destino = f"{PERFIL}?salvo={ancora}#perfil-{ancora}"
    assert (resposta.status_code, resposta.headers.get("location")) == (303, destino)
    html = http.get(destino.split("#")[0]).text
    gravou = LexborHTMLParser(html).css_first(f"#bloco-{ancora}")
    assert gravou is not None
    salvo = gravou.css_first("[role=status]")
    assert salvo is not None and _texto(salvo.html or "").strip() == pt("configuracoes.salvo")
    assert pt("configuracoes.salvo") not in _fora_das_secoes(html)
    for outra in set(SECOES) - {ancora}:  # só na que gravou
        no = LexborHTMLParser(html).css_first(f"#bloco-{outra}")
        assert no is not None and no.css_first("[role=status]") is None, outra


@pytest.mark.parametrize(
    ("dados", "ancora", "campo"),
    [
        (DADOS | {"email": "sem-arroba"}, "sobre", "perfil-email"),
        ({"habilidades": "x" * 101}, "habilidades", "campo-habilidades"),
        (
            {
                "secao": "experiencia",
                "id": "",
                "cargo": "Analista",
                "empresa": "",
                "inicio": "2020-13",
                "fim": "",
                "descricao": "",
            },
            "experiencias",
            "exp-nova-inicio",
        ),
    ],
)
def test_erro_aparece_dentro_da_secao_com_o_campo_marcado(
    http: Http, dados: dict[str, str], ancora: str, campo: str
) -> None:
    resposta = http.gravar(dados)
    assert resposta.status_code == 422
    secao = LexborHTMLParser(resposta.text).css_first(f"#bloco-{ancora}")
    assert secao is not None
    alerta = secao.css_first("#config-erro")
    assert alerta is not None and alerta.attributes.get("role") == "alert"
    marcado = secao.css_first(f"#{campo}")
    assert marcado is not None and marcado.attributes.get("aria-invalid") == "true"
    assert "config-erro" in (marcado.attributes.get("aria-describedby") or "").split()
    assert len(LexborHTMLParser(resposta.text).css("#config-erro")) == 1  # nada no alto


def test_curriculo_segue_com_o_salvo_no_alto(http: Http) -> None:
    """A revisão do currículo grava várias seções e recarrega a página: o aviso fica no alto."""
    html = http.get(PERFIL + "?salvo=1").text
    assert pt("configuracoes.salvo") in _fora_das_secoes(html)


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_sem_javascript_a_aba_nao_avisa_mais_que_salvar_perde(http: Http, idioma: str) -> None:
    """O aviso da D230.8(b) sai com a correção (T443): salvar não perde mais nada."""
    http.idioma(idioma)
    html = http.get(PERFIL).text
    assert LexborHTMLParser(html).css_first("noscript#perfil-sem-js") is None
    assert "configuracoes.perfil.sem_js" not in i18n.carregar()[idioma]


def test_apagar_perfil_vem_junto_na_troca(http: Http) -> None:
    """Com HTMX, o "Apagar perfil" fica fora das seções: cada uma o traz por troca fora de banda,
    para ele aparecer depois do primeiro Salvar sem recarregar a página."""
    arvore = LexborHTMLParser(http.get(PERFIL).text)
    for nome in SECOES:
        secao = arvore.css_first(f"section#bloco-{nome}")
        assert secao is not None and secao.attributes.get("hx-select-oob") == "#perfil-apagar"
    vazio = arvore.css_first("#perfil-apagar")  # o alvo existe mesmo sem perfil
    assert vazio is not None and vazio.css_first("button") is None
    assert http.gravar({"habilidades": "Python"}).status_code == 303
    cheio = LexborHTMLParser(http.get(PERFIL).text).css_first("#perfil-apagar")
    assert cheio is not None
    assert pt("configuracoes.perfil.apagar") in _texto(cheio.html or "")


# --- sem JavaScript, um formulário só (T443; D230.8 e D237.3) ----------------------------------


def _envio(html: str, botao: tuple[str, str], **trocas: str) -> dict[str, list[str]]:
    """O que o navegador manda ao apertar `botao` no formulário da aba, com `trocas` digitadas."""
    form = LexborHTMLParser(html).css_first("form#perfil-aba")
    assert form is not None
    envio: dict[str, list[str]] = {}
    for no in form.css("input, textarea, select"):
        nome = no.attributes.get("name")
        if not nome or no.attributes.get("type") in ("submit", "file"):
            continue
        if no.tag == "textarea":
            valor = no.text()
        elif no.tag == "select":
            opcao = no.css_first("option[selected]") or no.css_first("option")
            valor = (opcao.attributes.get("value") or "") if opcao else ""
        else:
            valor = no.attributes.get("value") or ""
        envio.setdefault(nome, []).append(trocas.get(nome, valor))
    return envio | {botao[0]: [botao[1]]}


DIGITADO = {
    "nome": "Maria Exemplo",
    "habilidades": "Python",
    "exp-nova-cargo": "Analista",
    "curso-nova-nome": "ADS",
}


def _valor(html: str, campo_id: str) -> str:
    no = LexborHTMLParser(html).css_first(f"#{campo_id}")
    assert no is not None, campo_id
    return no.text() if no.tag == "textarea" else no.attributes.get("value") or ""


def _gravados(http: Http) -> dict[str, Any]:
    with closing(abrir(http.banco)) as con:
        return {
            "nome": perfil.dados(con).nome,
            "habilidades": perfil.habilidades(con),
            "experiencias": [e.cargo for e in perfil.experiencias(con)],
            "cursos": [c.nome for c in perfil.cursos(con)],
        }


def test_a_aba_e_um_formulario_so(http: Http) -> None:
    arvore = LexborHTMLParser(http.get(PERFIL).text)
    form = arvore.css_first("form#perfil-aba")
    assert form is not None
    assert (form.attributes.get("method"), form.attributes.get("action")) == ("post", PERFIL)
    token = form.css_first(f"input[name={CAMPO_CSRF}]")
    assert token is not None and token.attributes.get("value") == http.token
    for nome in SECOES:
        secao = form.css_first(f"section#bloco-{nome}")
        assert secao is not None, nome
        assert secao.css("form") == [], nome  # sem formulário dentro de formulário
        for botao in secao.css("button[type=submit]"):
            # a conferência é do servidor: o campo errado de outra seção não barra este Salvar
            assert "formnovalidate" in botao.attributes, nome
            assert botao.attributes.get("name") in ("secao", "tirar"), nome


SALVAR = {
    "habilidades": (("secao", "habilidades"), "habilidades"),
    "dados": (("secao", "dados"), "nome"),
    "experiencia": (("secao", "exp-nova"), "experiencias"),
    "curso": (("secao", "curso-nova"), "cursos"),
}
ESPERADO = {"nome": "Maria Exemplo", "habilidades": ["Python"], "experiencias": ["Analista"]}
ESPERADO |= {"cursos": ["ADS"]}
VAZIO: dict[str, Any] = {"nome": None, "habilidades": [], "experiencias": [], "cursos": []}
ANCORA = {"habilidades": "habilidades", "dados": "sobre", "experiencia": "experiencias"}
ANCORA |= {"curso": "cursos"}
CAMPO = {"nome": ("perfil-nome", "nome"), "habilidades": ("campo-habilidades", "habilidades")}
CAMPO |= {"experiencias": ("exp-nova-cargo", "exp-nova-cargo")}
CAMPO |= {"cursos": ("curso-nova-nome", "curso-nova-nome")}


@pytest.mark.parametrize("secao", list(SALVAR))
def test_sem_javascript_salvar_uma_secao_guarda_o_digitado_nas_outras(
    http: Http, secao: str
) -> None:
    botao, gravada = SALVAR[secao]
    resposta = http.post(PERFIL, data=_envio(http.get(PERFIL).text, botao, **DIGITADO))
    assert resposta.status_code == 200
    # (guarda) grava só a seção do botão; o controle é a própria seção gravada
    assert _gravados(http) == VAZIO | {gravada: ESPERADO[gravada]}
    html = resposta.text
    for chave, (campo_id, nome) in CAMPO.items():
        if chave != gravada:  # o digitado nas outras volta, ainda não salvo
            assert _valor(html, campo_id) == DIGITADO[nome], campo_id
    salvo = LexborHTMLParser(html).css_first(f"#bloco-{ANCORA[secao]} [role=status]")
    assert salvo is not None and _texto(salvo.html or "").strip() == pt("configuracoes.salvo")


def test_sem_javascript_o_erro_de_uma_secao_guarda_o_digitado_nas_outras(http: Http) -> None:
    envio = _envio(http.get(PERFIL).text, ("secao", "dados"), email="sem-arroba", **DIGITADO)
    resposta = http.post(PERFIL, data=envio)
    assert resposta.status_code == 422
    assert _gravados(http) == VAZIO
    html = resposta.text
    alerta = LexborHTMLParser(html).css_first("#bloco-sobre #config-erro")
    assert alerta is not None
    assert _valor(html, "perfil-email") == "sem-arroba"
    assert _valor(html, "campo-habilidades") == "Python"
    assert _valor(html, "exp-nova-cargo") == "Analista"
    assert _valor(html, "curso-nova-nome") == "ADS"


def test_sem_javascript_tirar_um_item_guarda_o_digitado_nos_outros(http: Http) -> None:
    with closing(abrir(http.banco)) as con:
        perfil.gravar_experiencia(con, perfil.Experiencia("Analista"))
        perfil.gravar_experiencia(con, perfil.Experiencia("Gerente"))
        analista, gerente = (e.id for e in perfil.experiencias(con))
    html = http.get(PERFIL).text
    trocas = {f"exp-{gerente}-cargo": "Gerente de projetos", "habilidades": "Go"}
    resposta = http.post(PERFIL, data=_envio(html, ("tirar", f"exp-{analista}"), **trocas))
    assert resposta.status_code == 200
    assert _gravados(http)["experiencias"] == ["Gerente"]
    assert _valor(resposta.text, f"exp-{gerente}-cargo") == "Gerente de projetos"
    assert _valor(resposta.text, "campo-habilidades") == "Go"


@pytest.mark.parametrize("valor", ["exp-abc", "exp-0", "curso-", "outra", "exp-nova-x"])
def test_botao_de_secao_desconhecido_e_422(http: Http, valor: str) -> None:
    envio = _envio(http.get(PERFIL).text, ("secao", valor))
    assert http.post(PERFIL, data=envio).status_code == 422


def test_sem_javascript_o_envio_sem_csrf_e_recusado(http: Http) -> None:
    envio = _envio(http.get(PERFIL).text, ("secao", "habilidades"), **DIGITADO)
    del envio[CAMPO_CSRF]
    assert http.post(PERFIL, data=envio).status_code == 403
    assert _gravados(http) == VAZIO


# --- correções da revisão da T443 ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("botao", "campo", "chave"),
    [("exp-nova", "exp-nova-cargo", "experiencias"), ("curso-nova", "curso-nova-nome", "cursos")],
)
def test_sem_javascript_reenviar_o_adicionar_nao_repete_o_item(
    http: Http, botao: str, campo: str, chave: str
) -> None:
    """Sem 303, recarregar a página reenvia o formulário: o Adicionar repetido não grava de novo."""
    envio = _envio(http.get(PERFIL).text, ("secao", botao), **DIGITADO)
    assert http.post(PERFIL, data=envio).status_code == 200
    assert http.post(PERFIL, data=envio).status_code == 200  # o reenvio
    assert _gravados(http)[chave] == ESPERADO[chave]
    assert _valor(http.get(PERFIL).text, campo) == ""


def _botoes_da_aba(html: str) -> list[Any]:
    """Os botões do formulário da aba na ordem da página: os de dentro e os com `form`."""
    return LexborHTMLParser(html).css("button[form=perfil-aba], form#perfil-aba button")


def test_sem_javascript_o_enter_nao_grava_outra_secao(http: Http) -> None:
    """O Enter sem JavaScript aperta o primeiro botão do formulário: um botão oculto que não grava
    nada e devolve a página com o digitado (antes, gravava "Sobre você")."""
    with closing(abrir(http.banco)) as con:
        agora = RelogioFalso().agora()
        perfil.gravar_pergunta(con, "ia:k8s", "Usa Kubernetes?", "ia", agora, sugerida=True)
    html = http.get(PERFIL).text
    primeiro = _botoes_da_aba(html)[0]
    atributos = primeiro.attributes
    assert (atributos.get("name"), atributos.get("value")) == ("secao", "nenhuma")
    assert "hidden" in atributos and "formnovalidate" in atributos
    resposta = http.post(PERFIL, data=_envio(html, ("secao", "nenhuma"), **DIGITADO))
    assert resposta.status_code == 200
    assert _gravados(http) == VAZIO
    for campo_id, nome in CAMPO.values():
        assert _valor(resposta.text, campo_id) == DIGITADO[nome], campo_id
    assert pt("configuracoes.perfil.nada_salvo") in _fora_das_secoes(resposta.text)


def test_sem_javascript_aceitar_sugerida_guarda_o_digitado(http: Http) -> None:
    """As perguntas sugeridas também mandam o formulário da aba (D230.8, D237.3)."""
    with closing(abrir(http.banco)) as con:
        agora = RelogioFalso().agora()
        perfil.gravar_pergunta(con, "ia:k8s", "Usa Kubernetes?", "ia", agora, sugerida=True)
    html = http.get(PERFIL).text
    botoes = LexborHTMLParser(html).css("#bloco-sugeridas button")
    assert [(b.attributes.get("form"), b.attributes.get("name")) for b in botoes] == [
        ("perfil-aba", "sugerida")
    ] * 2
    assert [b.attributes.get("value") for b in botoes] == ["aceitar:ia:k8s", "descartar:ia:k8s"]
    for botao in botoes:
        assert botao.attributes.get("formaction") == f"{PERFIL}#perfil-sugeridas"
        assert "formnovalidate" in botao.attributes and botao.attributes.get("hx-post") == PERFIL
    resposta = http.post(PERFIL, data=_envio(html, ("sugerida", "aceitar:ia:k8s"), **DIGITADO))
    assert resposta.status_code == 200
    with closing(abrir(http.banco)) as con:
        assert [p.chave for p in perfil.perguntas(con)] == ["ia:k8s"]
    assert _gravados(http) == VAZIO
    for campo_id, nome in CAMPO.values():
        assert _valor(resposta.text, campo_id) == DIGITADO[nome], campo_id
    salvo = LexborHTMLParser(resposta.text).css_first("#bloco-sugeridas [role=status]")
    assert salvo is not None and _texto(salvo.html or "").strip() == pt("configuracoes.salvo")


@pytest.mark.parametrize("valor", ["aceitar", "outra:ia:k8s", ":ia:k8s"])
def test_sem_javascript_sugerida_desconhecida_e_422(http: Http, valor: str) -> None:
    envio = _envio(http.get(PERFIL).text, ("sugerida", valor))
    assert http.post(PERFIL, data=envio).status_code == 422


def test_sem_javascript_salvar_item_que_saiu_devolve_o_digitado(http: Http) -> None:
    """O item que outra aba tirou não volta sozinho, mas o digitado nele volta no item novo, com o
    aviso na seção, e o das outras seções também (antes: 404 seco)."""
    with closing(abrir(http.banco)) as con:
        perfil.gravar_experiencia(con, perfil.Experiencia("Analista"))
        (id_,) = (e.id for e in perfil.experiencias(con))
    assert id_ is not None
    html = http.get(PERFIL).text
    with closing(abrir(http.banco)) as con:
        perfil.apagar_experiencia(con, id_)  # a outra aba
    trocas = {f"exp-{id_}-cargo": "Analista sênior", "habilidades": "Go"}
    resposta = http.post(PERFIL, data=_envio(html, ("secao", f"exp-{id_}"), **trocas))
    assert resposta.status_code == 422
    assert _gravados(http)["experiencias"] == []
    secao = LexborHTMLParser(resposta.text).css_first("#bloco-experiencias")
    assert secao is not None
    alerta = secao.css_first("#config-erro")
    assert alerta is not None
    assert pt("configuracoes.perfil.erro.saiu") in _texto(alerta.html or "")
    assert _valor(resposta.text, "exp-nova-cargo") == "Analista sênior"
    assert _valor(resposta.text, "campo-habilidades") == "Go"


def test_salvar_item_que_saiu_sozinho_segue_404(http: Http) -> None:
    """O envio de uma seção sozinha (sem o digitado das outras) segue com o 404 (D230.2)."""
    dados = {"secao": "experiencia", "id": "99", "cargo": "Analista"}
    dados |= {"empresa": "", "inicio": "", "fim": "", "descricao": ""}
    assert http.gravar(dados).status_code == 404


def test_envio_da_aba_sem_botao_e_422(http: Http) -> None:
    """Sem o botão, o envio com as outras seções não cai no ramo antigo das habilidades."""
    envio = _envio(http.get(PERFIL).text, ("secao", "habilidades"), **DIGITADO)
    del envio["secao"]
    assert http.post(PERFIL, data=envio).status_code == 422
    assert _gravados(http) == VAZIO


def test_sem_javascript_volta_a_lista_e_o_outro_idioma_digitados(http: Http) -> None:
    trocas = {"formacao_nivel": "graduacao", "idioma_en": "fluente", "outro_nome": "Alemão"}
    trocas |= {"outro_nivel": "basico", "curso-nova-situacao": "cursando"}
    resposta = http.post(
        PERFIL, data=_envio(http.get(PERFIL).text, ("secao", "habilidades"), **trocas)
    )
    assert resposta.status_code == 200
    arvore = LexborHTMLParser(resposta.text)
    for campo_id, valor in [
        ("perfil-formacao", "graduacao"),
        ("perfil-idioma-en", "fluente"),
        ("perfil-outro-1-nivel", "basico"),
        ("curso-nova-situacao", "cursando"),
    ]:
        opcao = arvore.css_first(f"#{campo_id} option[selected]")
        assert opcao is not None and opcao.attributes.get("value") == valor, campo_id
    assert _valor(resposta.text, "perfil-outro-1") == "Alemão"


def test_sem_javascript_erro_num_item_guarda_o_digitado_no_outro(http: Http) -> None:
    with closing(abrir(http.banco)) as con:
        perfil.gravar_experiencia(con, perfil.Experiencia("Analista"))
        perfil.gravar_experiencia(con, perfil.Experiencia("Gerente"))
        analista, gerente = (e.id for e in perfil.experiencias(con))
    trocas = {f"exp-{analista}-inicio": "2020-13", f"exp-{gerente}-cargo": "Gerente de projetos"}
    html = http.get(PERFIL).text
    resposta = http.post(PERFIL, data=_envio(html, ("secao", f"exp-{analista}"), **trocas))
    assert resposta.status_code == 422
    assert _valor(resposta.text, f"exp-{analista}-inicio") == "2020-13"
    assert _valor(resposta.text, f"exp-{gerente}-cargo") == "Gerente de projetos"
    arvore = LexborHTMLParser(resposta.text)
    marcados = [n.attributes.get("id") for n in arvore.css("[aria-invalid=true]")]
    assert marcados == [f"exp-{analista}-inicio"]
