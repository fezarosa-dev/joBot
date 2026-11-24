"""Questionário do perfil no navegador (plano T437; desenho 8 da fase 4; D233).

Da aba Perfil ao questionário, responder e salvar pelo teclado, o erro com o foco no campo,
a espera do "Salvar e sugerir perguntas" (com JavaScript, sem segundo envio, com a navegação
segurada) e, sem JavaScript, o mesmo botão com a IA falsa (`app.state.ia`). Nenhum teste espera
tempo real: `expect_navigation` e `expect`.
"""

import re
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.console import anotar_erros
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.perfil import dados, habilidades
from jobot.nucleo.ia.contrato import Pedido, Resposta
from jobot.nucleo.ia.falso import BackendFalso

pytestmark = pytest.mark.tela

PAGINA = "/configuracoes/perfil/perguntas"


@pytest.fixture(autouse=True)
def _sem_erro_no_console(page: Page) -> Iterator[None]:
    erros = anotar_erros(page, ignorar="422")  # o 422 do erro é a resposta esperada da página
    yield
    assert erros == []


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


def test_da_aba_perfil_ao_questionario_e_salvar_pelo_teclado(
    page: Page, painel: str, tmp_path: Path
) -> None:
    page.goto(f"{painel}/configuracoes/perfil")
    with page.expect_navigation():
        page.get_by_role("link", name=re.compile("Abra o questionário")).click()
    expect(page.get_by_role("heading", name="Questionário do perfil")).to_be_visible()
    sobre = page.get_by_role("region", name="Sobre você")
    sobre.get_by_role("textbox", name="Em que cidade você mora?").fill("Campinas")
    idiomas = sobre.get_by_role("group", name="Que idiomas você fala, e com que nível?")
    idiomas.get_by_role("combobox", name="Inglês").select_option("avancado")
    sobre.get_by_role("textbox", name="Quais são suas principais habilidades?").fill("Python\nSQL")
    ia = page.get_by_role("region", name="Perguntas da IA")
    expect(ia).to_contain_text("Nenhuma pergunta da IA ainda.")
    expect(page.get_by_role("button", name="Salvar e sugerir perguntas")).to_have_count(0)
    salvar = page.get_by_role("button", name="Salvar", exact=True)
    salvar.focus()
    with page.expect_navigation():
        page.keyboard.press("Enter")
    expect(page.get_by_role("status").filter(has_text="Salvo.")).to_be_visible()
    expect(sobre.get_by_role("textbox", name="Em que cidade você mora?")).to_have_value("Campinas")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert dados(con).cidade_moradia == "Campinas"
        assert dados(con).idiomas_falados == (("en", "avancado"),)
        assert habilidades(con) == ["Python", "SQL"]


def test_erro_marca_o_campo_com_o_foco(page: Page, painel: str, tmp_path: Path) -> None:
    page.goto(f"{painel}{PAGINA}")
    page.get_by_role("textbox", name="Em que cidade você mora?").fill("Campinas")
    campo = page.get_by_role("textbox", name="Quais são suas principais habilidades?")
    campo.fill("x" * 101)  # uma habilidade acima do teto: o servidor recusa
    with page.expect_navigation():
        page.get_by_role("button", name="Salvar", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Até 200 habilidades")
    expect(campo).to_have_attribute("aria-invalid", "true")
    expect(campo).to_be_focused()  # o `autofocus` leva ao campo errado, sem JavaScript
    expect(campo).to_have_value("x" * 101)
    expect(page.get_by_role("textbox", name="Em que cidade você mora?")).to_have_value("Campinas")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert dados(con).cidade_moradia is None  # nada grava


def test_sugerir_perguntas_sem_javascript(
    pagina_sem_js: Page, painel: str, app_painel: FastAPI, tmp_path: Path
) -> None:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravar_config(
            con, "ia_tarefas", {"perguntas": {"ligada": True, "backend": "local", "modelo": "m"}}
        )
    pergunta = {"pergunta": "Você tem certificações?", "por_que": "Ajudam na triagem."}
    app_painel.state.ia = _Fabrica([{"perguntas": [pergunta]}])
    pagina_sem_js.goto(f"{painel}{PAGINA}")
    expect(pagina_sem_js.get_by_text("as perguntas usam o modelo local")).to_be_visible()
    with pagina_sem_js.expect_navigation():
        pagina_sem_js.get_by_role("button", name="Salvar e sugerir perguntas").click()
    ia = pagina_sem_js.get_by_role("region", name="Perguntas da IA")
    expect(ia.get_by_role("status")).to_have_text("1 pergunta nova.")
    resposta = ia.get_by_role("textbox", name="Você tem certificações?")
    expect(resposta).to_have_accessible_description("Por quê: Ajudam na triagem.")
    resposta.fill("AWS Cloud Practitioner")
    with pagina_sem_js.expect_navigation():
        pagina_sem_js.get_by_role("button", name="Salvar", exact=True).click()
    expect(pagina_sem_js.get_by_role("textbox", name="Você tem certificações?")).to_have_value(
        "AWS Cloud Practitioner"
    )


# depois do `app.js` (que registrou o seu antes): conta o envio que passou e segura a navegação,
# porque com ela pendente o Playwright espera a página nova para ler qualquer locator
_SEGURAR = """() => {
    window.envios = 0;
    document.addEventListener("submit", (e) => {
        if (!e.defaultPrevented) window.envios += 1;
        e.preventDefault();
    });
}"""


def test_sugerir_mostra_a_espera_e_nao_envia_duas_vezes(
    page: Page, painel: str, tmp_path: Path
) -> None:
    with closing(abrir(tmp_path / "jobot.db")) as con:
        gravar_config(
            con, "ia_tarefas", {"perguntas": {"ligada": True, "backend": "local", "modelo": "m"}}
        )
    page.goto(f"{painel}{PAGINA}")
    page.evaluate(_SEGURAR)
    botao = page.locator('button[name="sugerir"]')
    botao.click()
    expect(botao).to_have_class(re.compile(r"\besperando\b"))
    expect(botao).to_have_attribute("aria-disabled", "true")
    expect(botao.locator(".botao-espera")).to_have_text("Sugerindo perguntas…")
    # o segundo envio não sai (o `app.js` o cancela antes deste contador)
    botao.evaluate("b => b.form.requestSubmit(b)")
    assert page.evaluate("window.envios") == 1
