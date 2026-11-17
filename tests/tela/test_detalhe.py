"""Detalhe da vaga e correção no navegador: abrir, texto da descrição, corrigir, celular (T46)."""

import re

import pytest
from fastapi import FastAPI
from playwright.sync_api import Dialog, FloatRect, Page, expect

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
    # abaixo de 640px de miolo a linha leva à página da vaga; mais largo, o detalhe abre ao lado
    page.set_viewport_size({"width": 600, "height": 900})
    page.goto(painel + "/vagas?aba=todas")
    # a linha da lista é um `<a role="option">` (T254): o nome começa pelo título
    page.get_by_role("option", name=re.compile(r"^Desenvolvedor Python")).click()
    expect(page).to_have_url(f"{painel}/vagas/{USD}")
    expect(page.get_by_role("heading", level=1, name="Desenvolvedor Python")).to_be_visible()
    expect(page.get_by_text("US$ 5.000/mês")).to_be_visible()
    expect(page.get_by_text("≈ R$ 28.250/mês · US$ 1 = R$ 5,65 (PTAX de 13/11)")).to_be_visible()


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
    sheet = page.locator("dialog.sheet")
    expect(sheet).to_be_visible()  # com JavaScript a correção abre no sheet, sem sair da página
    expect(page).to_have_url(f"{painel}/vagas/{USD}")
    sheet.get_by_role("textbox", name="Salário").fill("USD 6.000 per month")
    sheet.get_by_role("button", name="Salvar a correção de Salário").click()
    expect(page).to_have_url(f"{painel}/vagas/{USD}")
    expect(page.locator("dialog.sheet")).to_have_count(0)
    expect(page.get_by_text("US$ 6.000/mês")).to_be_visible()
    expect(page.get_by_text("≈ R$ 33.900/mês · US$ 1 = R$ 5,65 (PTAX de 13/11)")).to_be_visible()


def test_correcao_abre_e_esc_fecha(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{USD}")
    link = page.get_by_role("link", name="Algo errado nesta vaga?")
    link.click()
    sheet = page.locator("dialog.sheet")
    expect(sheet).to_be_visible()
    assert sheet.evaluate("el => el.matches(':modal')")  # modal: o resto da página fica inerte
    caixa = sheet.bounding_box()
    assert caixa is not None and caixa["width"] <= 520 + 1
    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    expect(link).to_be_focused()  # o foco volta ao link que abriu
    page.get_by_role("link", name="Algo errado nesta vaga?").click()
    expect(page.locator("dialog.sheet")).to_be_visible()
    page.locator("dialog.sheet").get_by_role("button", name="Fechar").click()
    expect(page.locator("dialog.sheet")).to_be_hidden()


# reabre o sheet e lê, na hora, as transições que o @starting-style dispara. O getComputedStyle
# entre os dois faz o navegador ver o sheet fechado; o app.js o tira do DOM no `close`, depois
TRANSICOES_DO_SHEET = """el => {
  el.close();
  getComputedStyle(el).display;
  el.showModal();
  return el.getAnimations().map(a => [a.transitionProperty, a.effect.getTiming().duration]);
}"""


def test_sheet_sem_movimento_reduzido_nao_anima(page: Page, painel: str) -> None:
    """Desenho 5.1 (T305 j): o sheet entra descendo em 280 a 300ms (opacidade e transform); com
    movimento reduzido, nada se desloca: só o fundido, em até 120ms."""
    page.goto(f"{painel}/vagas/{USD}")
    page.get_by_role("link", name="Algo errado nesta vaga?").click()
    sheet = page.locator("dialog.sheet")
    expect(sheet).to_be_visible()
    entrada = dict(sheet.evaluate(TRANSICOES_DO_SHEET))
    assert set(entrada) == {"opacity", "transform"}
    assert all(280 <= d <= 300 for d in entrada.values())
    expect(sheet).to_have_count(0)  # o `close` do evaluate tirou o sheet
    page.emulate_media(reduced_motion="reduce")
    page.get_by_role("link", name="Algo errado nesta vaga?").click()
    expect(sheet).to_be_visible()
    assert sheet.evaluate("el => getComputedStyle(el).transform") == "none"
    reduzida = dict(sheet.evaluate(TRANSICOES_DO_SHEET))
    assert "transform" not in reduzida
    assert all(d <= 120 for d in reduzida.values())


def test_sheet_fica_no_alto_com_os_campos_estilizados(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{USD}")
    page.get_by_role("link", name="Algo errado nesta vaga?").click()
    sheet = page.locator("dialog.sheet")
    expect(sheet).to_be_visible()
    caixa = sheet.bounding_box()
    assert caixa is not None and caixa["y"] <= 64  # no alto da janela, não centrado
    # não os 3px do <dialog>
    assert sheet.evaluate("el => getComputedStyle(el).borderTopWidth") == "1px"
    campo = sheet.locator("textarea").first
    borda, raio, largura = campo.evaluate(
        "el => { const c = getComputedStyle(el);"
        " return [c.borderTopWidth, parseFloat(c.borderTopLeftRadius),"
        " el.getBoundingClientRect().width]; }"
    )
    assert borda == "1px"  # a página hospedeira não carrega o buscas.css
    assert raio > 0
    assert largura >= 300  # ocupa a largura do corpo, não o tamanho padrão do navegador


def test_sheet_fecha_pelo_fundo_mas_nao_ao_soltar_a_selecao_fora(page: Page, painel: str) -> None:
    page.goto(f"{painel}/vagas/{USD}")
    link = page.get_by_role("link", name="Algo errado nesta vaga?")
    link.click()
    sheet = page.locator("dialog.sheet")
    expect(sheet).to_be_visible()
    campo = sheet.locator("textarea").first
    campo.fill("texto digitado")
    caixa = campo.bounding_box()
    assert caixa is not None
    # arrasta de dentro do campo até o fundo e solta: o clique cai no <dialog>, mas não fecha
    page.mouse.move(caixa["x"] + 10, caixa["y"] + 10)
    page.mouse.down()
    page.mouse.move(5, 5)
    page.mouse.up()
    expect(sheet).to_be_visible()
    expect(campo).to_have_value("texto digitado")
    page.mouse.click(5, 5)  # um clique inteiro no fundo fecha
    expect(sheet).to_be_hidden()


def test_ctrl_clique_no_link_da_correcao_abre_a_pagina_em_outra_aba(
    page: Page, painel: str
) -> None:
    page.goto(f"{painel}/vagas/{USD}")
    link = page.get_by_role("link", name="Algo errado nesta vaga?")
    with page.context.expect_page() as nova:
        link.click(modifiers=["Control"])
    nova.value.wait_for_url(re.compile(rf"/vagas/{USD}/correcao$"))  # no evento a URL é about:blank
    expect(page.locator("dialog.sheet")).to_have_count(0)  # o sheet não abriu nesta aba


def test_sheet_correcao_botoes_visiveis(page: Page, painel: str) -> None:
    """E17: janela baixa, o pé do sheet com o botão fica inteiro na janela e só o corpo rola."""
    # teste de layout: sem a entrada do sheet (translateY de 280ms) a caixa medida não anda
    page.emulate_media(reduced_motion="reduce")
    page.set_viewport_size({"width": 1024, "height": 560})
    page.goto(f"{painel}/vagas/{USD}")
    page.get_by_role("link", name="Algo errado nesta vaga?").click()
    sheet = page.locator("dialog.sheet")
    expect(sheet).to_be_visible()

    def dentro_da_janela(caixa: FloatRect | None) -> bool:
        return (
            caixa is not None
            and caixa["x"] >= 0
            and caixa["y"] >= 0
            and caixa["x"] + caixa["width"] <= 1024
            and caixa["y"] + caixa["height"] <= 560
        )

    assert dentro_da_janela(sheet.bounding_box())
    fechar = sheet.get_by_role("button", name="Fechar")
    assert dentro_da_janela(fechar.bounding_box())
    corpo = sheet.locator(".sheet-corpo")
    rola = corpo.evaluate(
        "el => [el.scrollHeight > el.clientHeight + 1, getComputedStyle(el).overflowY]"
    )
    assert rola[0], "o corpo do sheet precisa rolar com a janela baixa"
    assert rola[1] in ("auto", "scroll")
    antes = fechar.bounding_box()
    corpo.evaluate("el => { el.scrollTop = el.scrollHeight }")
    assert fechar.bounding_box() == antes  # o pé não anda com a rolagem
    assert dentro_da_janela(fechar.bounding_box())


def test_pagina_estreita_nao_cola_voltar_no_titulo(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 600, "height": 900})
    page.goto(f"{painel}/vagas/{USD}")
    voltar = page.locator(".voltar")
    titulo = page.get_by_role("heading", level=1, name="Desenvolvedor Python")
    empresa = page.locator(".detalhe .cartao-empresa")
    v, h, e = voltar.bounding_box(), titulo.bounding_box(), empresa.bounding_box()
    assert v is not None and h is not None and e is not None
    assert h["y"] - (v["y"] + v["height"]) >= 8  # respiro entre o "Voltar" e o título
    assert e["y"] >= h["y"] + h["height"] - 0.5  # a empresa começa onde o título termina
    # o título tem entrelinha própria: com a herdada do corpo (16px) as letras passavam da caixa
    linha, corpo = titulo.evaluate(
        "el => { const c = getComputedStyle(el);"
        " return [parseFloat(c.lineHeight), parseFloat(c.fontSize)]; }"
    )
    assert linha >= corpo * 1.1
    assert h["height"] >= corpo * 1.1


def test_salvar_e_ocultar_ficam_na_mesma_linha_a_600px(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 600, "height": 900})
    page.goto(f"{painel}/vagas/{USD}")
    salvar = page.locator(".acoes-estado").get_by_role("button", name="Salvar", exact=True)
    ocultar = page.locator(".acoes-estado").get_by_role("button", name="Ocultar", exact=True)
    s, o = salvar.bounding_box(), ocultar.bounding_box()
    assert s is not None and o is not None
    assert abs(s["y"] - o["y"]) < 2  # o Ocultar não vai sozinho para a linha de baixo
    # e o rótulo não quebra de linha: a altura do miolo (sem padding e borda) é a de uma linha
    linhas = ocultar.evaluate(
        """el => {
          const s = getComputedStyle(el);
          const miolo = el.getBoundingClientRect().height
            - parseFloat(s.paddingTop) - parseFloat(s.paddingBottom)
            - parseFloat(s.borderTopWidth) - parseFloat(s.borderBottomWidth);
          return miolo / parseFloat(s.lineHeight);
        }"""
    )
    assert linhas < 1.5, linhas
    assert o["x"] + o["width"] <= 600
    folga = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert folga <= 0


def test_detalhe_a_600px_nao_marca_destaques_sem_aba_na_url(page: Page, painel: str) -> None:
    page.set_viewport_size({"width": 600, "height": 900})
    page.goto(f"{painel}/vagas/{USD}")
    expect(page.locator("#lateral-vagas [aria-current]")).to_have_count(0)
    page.goto(f"{painel}/vagas/{USD}?aba=salvas")
    marcada = page.locator("#lateral-vagas [aria-current]")
    expect(marcada).to_have_count(1)
    expect(marcada).to_contain_text("Salvas")


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
        for seletor in (".convertido", ".cartao-empresa", ".fontes a", "h2")
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
    expect(page.locator("dialog.sheet")).to_be_visible()  # Enter abre o sheet da correção


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
