"""Aba Perfil no navegador (planos T413 e T434; desenho 8 da fase 4; D200, D230).

Salvar pelo teclado, "Sobre você", experiências entrando e saindo (também sem JavaScript),
"Apagar perfil" pelo alerta e sem JavaScript, foco e cores forçadas, o currículo em PDF (T435) e a
revisão do que a IA leu dele, também pela IA manual (T436).
Nenhum teste espera tempo real: `expect_navigation` e `expect`.
"""

import json
import re
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Browser, Locator, Page, expect

from apoio.console import anotar_erros
from apoio.pdf import montar_pdf
from apoio.semear import AGORA
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.perfil import (
    dados,
    experiencias,
    gravar_habilidades,
    gravar_pergunta,
    habilidades,
    perguntas,
)
from jobot.nucleo.ia.contrato import Pedido, Resposta
from jobot.nucleo.ia.falso import BackendFalso

pytestmark = pytest.mark.tela


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> Iterator[None]:
    # violação do CSP aparece como erro; o 422 do teto e o 413 do currículo grande são respostas
    # esperadas da página
    erros = anotar_erros(page, ignorar="422")
    yield
    assert [erro for erro in erros if "413" not in erro] == []


def _gravar(tmp_path: Path, lista: list[str]) -> None:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravar_habilidades(con, lista, AGORA)


def _lidas(tmp_path: Path) -> tuple[int, list[str]]:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        return con.execute("SELECT count(*) FROM perfil").fetchone()[0], habilidades(con)


def test_salvar_pelo_teclado_grava_sem_repetidos(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}/configuracoes/perfil")
    expect(page.locator("nav.config-grupos").get_by_role("link", name="Perfil")).to_have_attribute(
        "aria-current", "page"
    )
    campo = page.get_by_role("textbox", name="Suas habilidades")
    expect(campo).to_have_accessible_description(re.compile("Uma por linha"))
    campo.fill("Python\n python \nGo,")
    page.keyboard.press("Tab")  # do campo, o Tab chega no Salvar da mesma seção
    salvar = page.get_by_role("region", name="Habilidades").get_by_role(
        "button", name="Salvar", exact=True
    )
    expect(salvar).to_be_focused()
    page.keyboard.press("Enter")
    # com JavaScript, o HTMX troca só a seção (D230): a página não navega e o "Salvo." vem nela
    regiao = page.get_by_role("region", name="Habilidades")
    expect(regiao.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    expect(page).to_have_url(re.compile(r"/configuracoes/perfil$"))
    expect(page.get_by_role("textbox", name="Suas habilidades")).to_have_value("Python\nGo")
    assert _lidas(tmp_path) == (1, ["Python", "Go"])


def test_apagar_pelo_alerta_e_cancelar_nao_apaga(page: Page, painel: str, tmp_path: Path) -> None:
    _gravar(tmp_path, ["Python"])
    page.goto(f"{painel}/configuracoes/perfil")
    abrir_alerta = page.get_by_role("button", name="Apagar perfil", exact=True)
    abrir_alerta.click()
    alerta = page.get_by_role("alertdialog", name="Apagar o perfil?")
    expect(alerta).to_be_visible()
    expect(alerta).to_be_focused()  # o foco fica no próprio alerta, nunca num botão (E13)
    alerta.get_by_role("button", name="Cancelar").click()
    expect(alerta).to_be_hidden()
    expect(abrir_alerta).to_be_focused()
    assert _lidas(tmp_path) == (1, ["Python"])

    abrir_alerta.click()
    with page.expect_navigation():
        alerta.get_by_role("button", name="Apagar", exact=True).click()
    expect(page).to_have_url(re.compile(r"/configuracoes/perfil\?apagado=1$"))
    expect(page.get_by_role("status").filter(has_text="Perfil apagado.")).to_be_visible()
    expect(page.get_by_role("textbox", name="Suas habilidades")).to_have_value("")
    expect(page.get_by_role("button", name="Apagar perfil", exact=True)).to_have_count(0)
    assert _lidas(tmp_path) == (0, [])


def test_apagar_sem_javascript_pede_confirmacao(
    browser: Browser, painel: str, tmp_path: Path
) -> None:
    _gravar(tmp_path, ["Python"])
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        pagina = contexto.new_page()
        pagina.goto(f"{painel}/configuracoes/perfil")
        pagina.get_by_role("button", name="Apagar perfil", exact=True).click()
        expect(pagina).to_have_url(re.compile(r"/configuracoes/perfil/apagar/confirmar\??$"))
        expect(pagina.get_by_role("heading", level=1)).to_have_text("Apagar o perfil?")
        pagina.get_by_role("link", name="Cancelar", exact=True).click()
        expect(pagina).to_have_url(re.compile(r"/configuracoes/perfil$"))
        assert _lidas(tmp_path) == (1, ["Python"])  # abrir e cancelar não apagou

        pagina.get_by_role("button", name="Apagar perfil", exact=True).click()
        pagina.get_by_role("button", name="Apagar", exact=True).click()
        expect(pagina).to_have_url(re.compile(r"/configuracoes/perfil\?apagado=1$"))
        assert _lidas(tmp_path) == (0, [])
    finally:
        contexto.close()


def test_campo_com_foco_visivel_em_cores_forcadas(page: Page, painel: str) -> None:
    page.emulate_media(forced_colors="active")
    page.goto(f"{painel}/configuracoes/perfil")
    campo = page.get_by_role("textbox", name="Suas habilidades")
    campo.focus()
    expect(campo).to_be_focused()
    borda = campo.evaluate("e => getComputedStyle(e).borderTopWidth")
    contorno = campo.evaluate(
        "e => [getComputedStyle(e).outlineStyle, getComputedStyle(e).outlineWidth]"
    )
    assert float(borda.removesuffix("px")) > 0
    assert contorno == ["solid", "2px"]  # o contorno transparente vira linha visível aqui


def test_erro_de_teto_marca_o_campo(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}/configuracoes/perfil")
    campo = page.get_by_role("textbox", name="Suas habilidades")
    campo.fill("x" * 101)
    regiao = page.get_by_role("region", name="Habilidades")
    regiao.get_by_role("button", name="Salvar", exact=True).click()
    # o 422 troca a seção com o alerta dentro dela (D230); o HTMX segue o `autofocus`
    expect(regiao.get_by_role("alert")).to_contain_text("Até 200 habilidades")
    expect(campo).to_have_attribute("aria-invalid", "true")
    expect(campo).to_be_focused()
    expect(campo).to_have_value("x" * 101)
    assert _lidas(tmp_path) == (0, [])


def test_sobre_voce_grava_e_volta_preenchido(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}/configuracoes/perfil")
    sobre = page.get_by_role("region", name="Sobre você")
    contato = sobre.get_by_role("group", name="Contato")
    expect(contato).to_have_accessible_description(
        re.compile("não põe estes campos nos pedidos à IA")
    )
    contato.get_by_role("textbox", name="Nome").fill("Maria Exemplo")
    contato.get_by_role("textbox", name="E-mail").fill("maria@exemplo.test")
    sobre.get_by_role("spinbutton", name="Anos de experiência na área").fill("7")
    sobre.get_by_role("combobox", name="Português").select_option(label="Fluente")
    sobre.get_by_role("textbox", name="Outro idioma 1").fill("Alemão")
    sobre.get_by_role("combobox", name="Nível do outro idioma 1").select_option(label="Básico")
    sobre.get_by_role("button", name="Salvar", exact=True).click()
    expect(sobre.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    sobre = page.get_by_role("region", name="Sobre você")
    expect(sobre.get_by_role("textbox", name="Nome")).to_have_value("Maria Exemplo")
    expect(sobre.get_by_role("combobox", name="Português")).to_have_value("fluente")
    expect(sobre.get_by_role("textbox", name="Outro idioma 1")).to_have_value("Alemão")
    expect(sobre.get_by_role("textbox", name="Outro idioma 2")).to_have_value("")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravados = dados(con)
    assert (gravados.nome, gravados.email, gravados.anos_de_experiencia) == (
        "Maria Exemplo",
        "maria@exemplo.test",
        7,
    )
    assert gravados.idiomas_falados == (("pt", "fluente"), ("Alemão", "basico"))


def _clicar(pagina: Page, botao: Locator, navega: bool) -> None:
    """Sem JavaScript, o formulário recarrega a página; com ele, o HTMX troca a seção (D230)."""
    if navega:
        with pagina.expect_navigation():
            botao.click()
    else:
        botao.click()


def _adicionar_e_tirar(pagina: Page, painel: str, tmp_path: Path, navega: bool) -> None:
    pagina.goto(f"{painel}/configuracoes/perfil")
    secao = pagina.get_by_role("region", name="Experiências")
    nova = secao.get_by_role("group", name="Nova experiência")
    nova.get_by_role("textbox", name="Cargo").fill("Analista")
    nova.get_by_role("textbox", name="Início").fill("2019-03")
    _clicar(pagina, secao.get_by_role("button", name="Adicionar", exact=True), navega)
    item = pagina.get_by_role("region", name="Experiências").get_by_role("group", name="Analista")
    expect(item.get_by_role("textbox", name="Início")).to_have_value("2019-03")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert [e.cargo for e in experiencias(con)] == ["Analista"]
    # cada item tem o seu Tirar, com o item no nome acessível
    secao = pagina.get_by_role("region", name="Experiências")
    _clicar(pagina, secao.get_by_role("button", name="Tirar Analista", exact=True), navega)
    secao = pagina.get_by_role("region", name="Experiências")
    expect(secao.get_by_role("group", name="Analista")).to_have_count(0)
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert experiencias(con) == []


def test_experiencia_entra_e_sai(page: Page, painel: str, tmp_path: Path) -> None:
    _adicionar_e_tirar(page, painel, tmp_path, navega=False)


def test_experiencia_entra_e_sai_sem_javascript(
    browser: Browser, painel: str, tmp_path: Path
) -> None:
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        _adicionar_e_tirar(contexto.new_page(), painel, tmp_path, navega=True)
    finally:
        contexto.close()


def _salvar_uma_secao(pagina: Page, painel: str, tmp_path: Path, navega: bool) -> None:
    pagina.goto(f"{painel}/configuracoes/perfil")
    sobre = pagina.get_by_role("region", name="Sobre você")
    sobre.get_by_role("textbox", name="Nome").fill("Maria Exemplo")  # digitado, sem salvar
    nova = pagina.get_by_role("region", name="Experiências").get_by_role(
        "group", name="Nova experiência"
    )
    nova.get_by_role("textbox", name="Cargo").fill("Analista")
    nova.get_by_role("textbox", name="Início").fill("2019-13")  # errado, e não barra o Salvar
    regiao = pagina.get_by_role("region", name="Habilidades")
    regiao.get_by_role("textbox", name="Suas habilidades").fill("Python")
    _clicar(pagina, regiao.get_by_role("button", name="Salvar", exact=True), navega)
    expect(regiao.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    expect(sobre.get_by_role("textbox", name="Nome")).to_have_value("Maria Exemplo")
    expect(nova.get_by_role("textbox", name="Cargo")).to_have_value("Analista")
    expect(nova.get_by_role("textbox", name="Início")).to_have_value("2019-13")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert (habilidades(con), dados(con).nome, experiencias(con)) == (["Python"], None, [])


def test_salvar_uma_secao_nao_apaga_o_digitado_nas_outras(
    page: Page, painel: str, tmp_path: Path
) -> None:
    """D230 (decidido pelo dono): o Salvar das habilidades troca só a seção dele."""
    _salvar_uma_secao(page, painel, tmp_path, navega=False)


def test_salvar_uma_secao_sem_javascript_nao_apaga_o_digitado_nas_outras(
    browser: Browser, painel: str, tmp_path: Path
) -> None:
    """T443 (D237.3): sem JavaScript, a aba é um formulário só e a página volta com o digitado."""
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        _salvar_uma_secao(contexto.new_page(), painel, tmp_path, navega=True)
    finally:
        contexto.close()


def test_enter_num_item_salva_o_item(page: Page, painel: str, tmp_path: Path) -> None:
    """Com um formulário só, o Enter do navegador apertaria o primeiro Salvar (o de "Sobre você"):
    o app.js manda o Enter ao botão do item onde ele foi dado (T443)."""
    page.goto(f"{painel}/configuracoes/perfil")
    page.get_by_role("region", name="Sobre você").get_by_role("textbox", name="Nome").fill("Ana")
    secao = page.get_by_role("region", name="Experiências")
    cargo = secao.get_by_role("group", name="Nova experiência").get_by_role("textbox", name="Cargo")
    cargo.fill("Analista")
    cargo.press("Enter")
    expect(secao.get_by_role("group", name="Analista")).to_be_visible()
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert ([e.cargo for e in experiencias(con)], dados(con).nome) == (["Analista"], None)


def test_apagar_perfil_aparece_depois_do_primeiro_salvar(page: Page, painel: str) -> None:
    """Com HTMX, o primeiro Salvar traz o "Apagar perfil" sem recarregar a página (D230.8)."""
    page.goto(f"{painel}/configuracoes/perfil")
    apagar = page.get_by_role("button", name="Apagar perfil")
    expect(apagar).to_have_count(0)
    regiao = page.get_by_role("region", name="Habilidades")
    regiao.get_by_role("textbox", name="Suas habilidades").fill("Python")
    regiao.get_by_role("button", name="Salvar", exact=True).click()
    expect(regiao.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    expect(apagar).to_be_visible()


def _sugerir(tmp_path: Path, chave: str, texto: str) -> None:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravar_pergunta(con, chave, texto, "ia", AGORA, sugerida=True)


def _aceitas(tmp_path: Path) -> list[str]:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        return [p.pergunta for p in perguntas(con)]


def test_aceitar_e_descartar_sugeridas(page: Page, painel: str, tmp_path: Path) -> None:
    """D234 (decidido pelo dono): com JavaScript, a seção troca sozinha."""
    _sugerir(tmp_path, "ia:k8s", "Usa Kubernetes?")
    _sugerir(tmp_path, "ia:gerente", "Qual o nome do seu gerente?")
    page.goto(f"{painel}/configuracoes/perfil")
    secao = page.get_by_role("region", name="Perguntas sugeridas")
    secao.get_by_role("button", name="Aceitar: Usa Kubernetes?", exact=True).click()
    expect(secao.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    expect(secao.get_by_text("Usa Kubernetes?")).to_have_count(0)
    secao.get_by_role("button", name="Descartar: Qual o nome do seu gerente?").click()
    expect(secao.get_by_text("Qual o nome do seu gerente?")).to_have_count(0)
    assert _aceitas(tmp_path) == ["Usa Kubernetes?"]


def test_aceitar_sugerida_sem_javascript(browser: Browser, painel: str, tmp_path: Path) -> None:
    _sugerir(tmp_path, "ia:k8s", "Usa Kubernetes?")
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        pagina = contexto.new_page()
        pagina.goto(f"{painel}/configuracoes/perfil")
        secao = pagina.get_by_role("region", name="Perguntas sugeridas")
        with pagina.expect_navigation():
            secao.get_by_role("button", name="Aceitar: Usa Kubernetes?").click()
        expect(pagina.get_by_role("region", name="Perguntas sugeridas")).to_contain_text("Salvo.")
    finally:
        contexto.close()
    assert _aceitas(tmp_path) == ["Usa Kubernetes?"]


def _enviar_curriculo(page: Page, painel: str, dados: bytes) -> None:
    page.goto(f"{painel}/configuracoes/perfil")
    secao = page.get_by_role("region", name="Currículo em PDF")
    campo = secao.get_by_label("Arquivo do currículo (PDF)")
    expect(campo).to_have_accessible_description(re.compile("Até 5 MB"))
    campo.set_input_files({"name": "curriculo.pdf", "mimeType": "application/pdf", "buffer": dados})
    secao.get_by_role("button", name="Ler currículo", exact=True).click()


def test_curriculo_lido_pelo_navegador(page: Page, painel: str) -> None:
    _enviar_curriculo(page, painel, montar_pdf(["Analista de dados", "Curso de SQL"]))
    expect(page.get_by_role("status").filter(has_text="Currículo lido")).to_have_text(
        "Currículo lido: 2 de 2 páginas. Nada foi guardado."
    )


def test_curriculo_com_senha_mostra_o_aviso(page: Page, painel: str) -> None:
    _enviar_curriculo(page, painel, montar_pdf(["segredo"], senha="abre-te"))
    expect(page.get_by_role("alert").filter(has_text="senha")).to_have_text(
        "Este PDF pede senha para abrir. Salve uma cópia sem senha e tente de novo."
    )


def test_curriculo_grande_avisa_e_limpa_o_resultado(page: Page, painel: str) -> None:
    # o 413 sai sem ler o corpo; o aviso de erro mostra o motivo e o resultado anterior não fica
    _enviar_curriculo(page, painel, montar_pdf(["Analista de dados"]))
    resultado = page.locator("#perfil-curriculo-resultado")
    expect(resultado).to_contain_text("Currículo lido")
    secao = page.get_by_role("region", name="Currículo em PDF")
    grande = b"%PDF-1.7\n" + b"0" * (5 * 1024 * 1024 + 1)
    secao.get_by_label("Arquivo do currículo (PDF)").set_input_files(
        {"name": "grande.pdf", "mimeType": "application/pdf", "buffer": grande}
    )
    secao.get_by_role("button", name="Ler currículo", exact=True).click()
    expect(page.locator("#aviso-erro")).to_contain_text(
        "O arquivo passa de 5 MB. Envie um PDF menor."
    )
    expect(resultado).to_be_empty()


def test_curriculo_sem_javascript_explica(browser: Browser, painel: str) -> None:
    contexto = browser.new_context(java_script_enabled=False, locale="pt-BR")
    try:
        pagina = contexto.new_page()
        pagina.goto(f"{painel}/configuracoes/perfil")
        secao = pagina.get_by_role("region", name="Currículo em PDF")
        # o get_by_text do Playwright pula o conteúdo de <noscript>: o parágrafo vai por CSS
        nota = secao.locator("noscript > p")
        expect(nota).to_be_visible()
        expect(nota).to_contain_text("precisa do JavaScript ligado")
        expect(secao.get_by_role("button", name="Ler currículo", exact=True)).to_be_hidden()
    finally:
        contexto.close()


# ------------------------------------------------------------------ extração pela IA (T436; D232)

_PAGINAS = ["Analista de dados", "contato@exemplo.invalid", "Python e SQL"]
_LIDO: dict[str, object] = {
    "cargo_atual": "Analista de dados",
    "habilidades": ["Python", "SQL", "Kubernetes"],
}


class _Fabrica:
    """`app.state.ia` falsa: devolve sempre o mesmo `BackendFalso`."""

    def __init__(self, prontas: list[dict[str, object]]) -> None:
        self.falso = BackendFalso(list(prontas))

    def __call__(self, backend: str, modelo: str) -> _Fabrica:
        return self

    def pedir(self, pedido: Pedido) -> Resposta:
        return self.falso.pedir(pedido)

    def fechar(self) -> None:
        pass


def _ligar_curriculo(tmp_path: Path, backend: str, modelo: str) -> None:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        tarefa = {"ligada": True, "backend": backend, "modelo": modelo}
        gravar_config(con, "ia_tarefas", {"curriculo": tarefa})


def _aprovar_e_conferir(page: Page, tmp_path: Path) -> None:
    revisao = page.get_by_role("form", name="Confira o que foi lido")
    expect(revisao).to_be_visible()
    marcada = revisao.get_by_role("checkbox", name="Usar Habilidade 3")
    expect(marcada).not_to_be_checked()
    expect(marcada).to_have_accessible_description(re.compile("Não achei no currículo"))
    expect(revisao.get_by_role("checkbox", name="Usar Habilidade 1")).to_be_checked()
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert habilidades(con) == []  # nada grava antes do Salvar
    with page.expect_navigation():
        revisao.get_by_role("button", name="Aprovar todas", exact=True).click()
    expect(page).to_have_url(re.compile(r"/configuracoes/perfil(\?salvo=1)?#perfil-sobre$"))
    expect(page.get_by_role("textbox", name="E-mail")).to_have_value("contato@exemplo.invalid")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert habilidades(con) == ["Python", "SQL"]
        assert dados(con).cargo_atual == "Analista de dados"


def test_curriculo_lido_pela_ia_e_aprovado(
    page: Page, painel: str, app_painel: FastAPI, tmp_path: Path
) -> None:
    _ligar_curriculo(tmp_path, "local", "qwen")
    app_painel.state.ia = _Fabrica([_LIDO])
    page.goto(f"{painel}/configuracoes/perfil")
    expect(page.locator("#perfil-curriculo-privacidade")).to_have_text(
        "O texto do currículo fica no seu computador: usa o modelo local."
    )
    _enviar_curriculo(page, painel, montar_pdf([*_PAGINAS]))
    _aprovar_e_conferir(page, tmp_path)


def test_curriculo_na_ia_manual_copia_e_cola(page: Page, painel: str, tmp_path: Path) -> None:
    _ligar_curriculo(tmp_path, "manual", "manual")
    _enviar_curriculo(page, painel, montar_pdf([*_PAGINAS]))
    pedido = page.get_by_role("textbox", name="Pedido para copiar")
    expect(pedido).to_have_attribute("readonly", "")
    expect(pedido).to_have_value(re.compile("<<<CURRICULO"))
    expect(pedido).not_to_have_value(re.compile("contato@exemplo"))
    expect(page.get_by_text("A IA não achou nada para preencher.")).to_have_count(0)
    page.get_by_role("textbox", name="Resposta do chat").fill(
        "```json\n" + json.dumps(_LIDO) + "\n```"
    )
    page.get_by_role("button", name="Ler a resposta", exact=True).click()
    _aprovar_e_conferir(page, tmp_path)
