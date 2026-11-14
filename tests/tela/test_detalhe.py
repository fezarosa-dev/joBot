"""Detalhe da vaga e correção no navegador: abrir, texto da descrição, corrigir, celular (T46)."""

import pytest
from fastapi import FastAPI
from playwright.sync_api import Dialog, Page, expect

from apoio.relogio import RelogioFalso
from tela.test_casca_menu import CONTRASTE

pytestmark = pytest.mark.tela

MINIMO = 4.5
USD = 1  # ids na ordem em que o `semear` grava
HIMALAYAS = 3
SCRIPT = 4
PRAZO_3_DIAS = 6
TRAINEE = 7  # prazo em 37 dias
MINIMO_GRAFICO = 3  # WCAG 1.4.11: a marca da grade é desenho, o texto ao lado diz o mesmo


@pytest.fixture
def app_painel(app_painel: FastAPI) -> FastAPI:
    app_painel.state.relogio = RelogioFalso()  # o semeado é datado de `AGORA`
    return app_painel


def test_abre_o_detalhe_pelo_titulo_do_cartao(page: Page, painel: str) -> None:
    page.goto(painel + "/vagas?aba=todas")
    page.get_by_role("link", name="Desenvolvedor Python").click()
    expect(page).to_have_url(f"{painel}/vagas/{USD}")
    expect(page.get_by_role("heading", level=1, name="Desenvolvedor Python")).to_be_visible()
    expect(page.get_by_text("US$ 5.000/mês")).to_be_visible()
    expect(page.get_by_text("US$ 1 = R$ 5,65 (PTAX de 13/11) · ≈ R$ 28.250/mês")).to_be_visible()


def test_descricao_com_script_aparece_como_texto(page: Page, painel: str) -> None:
    avisos: list[str] = []

    def _fechar(dialogo: Dialog) -> None:
        avisos.append(dialogo.message)
        dialogo.dismiss()

    page.on("dialog", _fechar)
    page.goto(f"{painel}/vagas/{SCRIPT}")
    expect(page.locator(".descricao")).to_contain_text("Olá <script>alert('x')</script> mundo")
    assert avisos == []


def test_links_de_fora_abrem_em_outra_aba_sem_dar_acesso(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{HIMALAYAS}")
    apply = page.locator('a[href$="/apply"]')
    expect(apply).to_have_attribute("target", "_blank")
    expect(apply).to_have_attribute("rel", "noopener noreferrer")
    expect(page.get_by_role("link", name="via Himalayas (abre em nova aba)")).to_be_visible()


def test_corrigir_o_salario_mostra_o_valor_novo_na_hora(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{USD}")
    page.get_by_role("link", name="Algo errado nesta vaga?").click()
    expect(page).to_have_url(f"{painel}/vagas/{USD}/correcao")
    page.get_by_role("textbox", name="Salário").fill("USD 6.000 per month")
    page.get_by_role("button", name="Salvar a correção de Salário").click()
    expect(page).to_have_url(f"{painel}/vagas/{USD}")
    expect(page.get_by_text("US$ 6.000/mês")).to_be_visible()
    expect(page.get_by_text("US$ 1 = R$ 5,65 (PTAX de 13/11) · ≈ R$ 33.900/mês")).to_be_visible()


def test_correcao_invalida_volta_com_o_texto_e_a_mensagem(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{USD}/correcao")
    page.get_by_role("textbox", name="Estado (sigla)").fill("ZZ9")
    page.get_by_role("button", name="Salvar a correção de Estado (sigla)").click()
    expect(page.get_by_role("alert")).to_contain_text("sigla do estado")
    expect(page.get_by_role("textbox", name="Estado (sigla)")).to_have_value("ZZ9")


@pytest.mark.parametrize(
    "rota", [f"/vagas/{USD}", f"/vagas/{PRAZO_3_DIAS}", f"/vagas/{USD}/correcao"]
)
def test_no_celular_nao_rola_de_lado(page: Page, painel: str, rota: str) -> None:
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(painel + rota)
    folga = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert folga <= 0


def test_faixa_de_meses_tem_texto_para_leitor_de_tela(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{PRAZO_3_DIAS}")
    expect(page.locator(".meses")).to_have_attribute("aria-hidden", "true")
    expect(page.locator(".meses li")).to_have_count(12)
    expect(page.locator(".datas .urgente")).to_contain_text("Prazo: 16/11/2026 (faltam 3 dias)")


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_contraste_dos_textos_menores(page: Page, painel: str, esquema: str) -> None:
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    page.goto(f"{painel}/vagas/{USD}")
    razoes = [
        page.locator(seletor).first.evaluate(CONTRASTE)
        for seletor in (".cotacao", ".cartao-empresa", ".fontes a", "h2")
    ]
    assert [r for r in razoes if r < MINIMO] == [], f"contraste no tema {esquema}: {razoes}"


def test_teclado_chega_ao_link_de_correcao_e_o_foco_aparece(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{USD}")
    for _ in range(40):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.textContent.trim()") == "Algo errado nesta vaga?":
            break
    else:
        pytest.fail("o Tab não chegou ao link de correção")
    estilo = page.evaluate(
        "[getComputedStyle(document.activeElement).outlineStyle,"
        " parseFloat(getComputedStyle(document.activeElement).outlineWidth)]"
    )
    assert estilo[0] != "none"
    assert estilo[1] >= 2
    page.keyboard.press("Enter")
    expect(page).to_have_url(f"{painel}/vagas/{USD}/correcao")


# cor que `var(--alerta)` resolve na página; sem o token o `color` herda e iguala o do corpo
COR_ALERTA = """() => {
  const e = document.createElement('i');
  e.style.color = 'var(--alerta)';
  document.body.append(e);
  const cor = getComputedStyle(e).color;
  e.remove();
  return cor;
}"""
COR = "el => getComputedStyle(el).color"


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_prazo_urgente_em_alerta_e_com_marca(page: Page, painel: str, esquema: str) -> None:
    page.emulate_media(color_scheme="light" if esquema == "light" else "dark")
    page.goto(f"{painel}/vagas/{PRAZO_3_DIAS}")
    alerta = page.evaluate(COR_ALERTA)
    assert alerta != page.locator("body").evaluate(COR), "o token --alerta não existe"
    urgente = page.locator(".datas .urgente")
    expect(urgente).to_contain_text("▲")  # a cor nunca é a única pista
    assert urgente.evaluate(COR) == alerta
    assert urgente.evaluate("el => getComputedStyle(el).fontWeight") == "700"
    marca = page.locator(".meses .urgente")
    expect(marca).to_have_text("▲")
    assert marca.evaluate(COR) == alerta
    assert urgente.evaluate(CONTRASTE) >= MINIMO
    assert marca.evaluate(CONTRASTE) >= MINIMO_GRAFICO


def test_prazo_longe_nao_fica_em_alerta(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{TRAINEE}")
    alerta = page.evaluate(COR_ALERTA)
    assert alerta != page.locator("body").evaluate(COR), "o token --alerta não existe"
    prazo = page.locator(".datas li", has_text="▲")
    expect(prazo).to_contain_text("Prazo: 20/12/2026")
    assert prazo.evaluate(COR) != alerta
    expect(page.locator(".datas .urgente")).to_have_count(0)
    expect(page.locator(".meses .urgente")).to_have_count(0)
    expect(page.locator(".meses .marcas", has_text="▲")).to_have_count(1)  # a marca segue lá
