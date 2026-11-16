"""Assistente de primeira execução no navegador: dois passos, recusa e fim (plano T53)."""

import re
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from playwright.sync_api import Page, expect

from apoio.relogio import RelogioFalso
from apoio.segundo_plano_falso import FalsoSistema
from apoio.site_falso import LeitorFalso
from jobot.banco import cadastros
from jobot.banco.conexao import abrir

pytestmark = pytest.mark.tela


@pytest.fixture
def sistema(tmp_path: Path) -> FalsoSistema:
    return FalsoSistema(home=str(tmp_path / "casa"))


@pytest.fixture
def app_painel(app_painel: FastAPI, sistema: FalsoSistema, tmp_path: Path) -> FastAPI:
    # nenhum systemctl de verdade: o segundo plano e o ambiente são falsos
    casa = tmp_path / "casa"
    casa.mkdir()
    app_painel.state.relogio = RelogioFalso()
    app_painel.state.rodar_comando = sistema
    app_painel.state.ambiente = {"HOME": str(casa)}
    app_painel.state.plataforma = "linux"
    app_painel.state.leitores = ()  # sem leitor o assistente tem dois passos; o caso novo liga um
    return app_painel


def _passo_1(page: Page) -> None:
    page.get_by_label("Cargos ou palavras-chave").fill("Python")
    page.get_by_label("Cidade 1").fill("Curitiba")
    page.locator("select[name=uf]").first.select_option("PR")
    page.get_by_label("Remoto").check()
    page.get_by_role("button", name="Continuar").click()


def test_fluxo_completo_vai_do_passo_1_ao_fim_e_para_nos_destaques(
    page: Page, painel: str, sistema: FalsoSistema
) -> None:
    erros: list[str] = []  # violação do CSP aparece como erro no console
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))

    page.goto(f"{painel}/")
    expect(page).to_have_url(f"{painel}/primeira-execucao/1")
    expect(page.get_by_role("heading", name="O que você procura?")).to_be_visible()
    _passo_1(page)

    expect(page).to_have_url(re.compile(r"/primeira-execucao/2\?busca=\d+$"))
    resumo = page.locator("[data-resumo]")
    expect(resumo).to_contain_text("Python")
    expect(resumo).to_contain_text("Curitiba, PR")
    expect(resumo).to_contain_text("Remoto")

    page.get_by_label("Não ligar agora").check()
    page.get_by_role("button", name="Concluir").click()
    expect(page.get_by_role("heading", name="Tudo pronto")).to_be_visible()
    expect(page.get_by_role("button", name="Buscar agora")).to_have_count(1)
    assert all(c[0] != "enable" for c in sistema.systemctl())

    page.get_by_role("link", name="Ir para as vagas").click()
    expect(page).to_have_url(f"{painel}/vagas?aba=destaques")
    page.goto(f"{painel}/")  # concluído: a raiz não volta ao assistente
    expect(page).to_have_url(f"{painel}/vagas?aba=destaques")
    assert erros == []


def test_pular_o_passo_1_vai_direto_as_vagas(page: Page, painel: str) -> None:
    page.goto(f"{painel}/primeira-execucao/1")
    page.get_by_role("button", name="Pular").click()
    expect(page).to_have_url(re.compile(r"/vagas(\?.*)?$"))
    page.goto(f"{painel}/")  # concluído: a raiz não volta ao assistente
    expect(page).to_have_url(re.compile(r"/vagas(\?.*)?$"))


def test_pular_no_passo_2_vai_as_vagas_sem_ligar_o_segundo_plano(
    page: Page, painel: str, sistema: FalsoSistema
) -> None:
    page.goto(f"{painel}/primeira-execucao/1")
    _passo_1(page)
    expect(page).to_have_url(re.compile(r"/primeira-execucao/2\?busca=\d+$"))
    page.get_by_role("button", name="Pular").click()
    expect(page).to_have_url(re.compile(r"/vagas(\?.*)?$"))
    assert all(c[0] != "enable" for c in sistema.systemctl())


def test_voltar_do_passo_2_leva_ao_passo_1(page: Page, painel: str) -> None:
    page.goto(f"{painel}/primeira-execucao/1")
    _passo_1(page)
    page.get_by_role("link", name="Voltar ao passo 1").click()
    expect(page).to_have_url(re.compile(r"/primeira-execucao/1(\?.*)?$"))


def _pe_dentro_da_janela(page: Page, nomes: tuple[str, ...]) -> None:
    for nome in nomes:
        # nome exato: "Pular" por substring casa também o "Pular para o conteúdo" da casca
        botao = page.get_by_role("button", name=nome, exact=True).or_(
            page.get_by_role("link", name=nome, exact=True)
        )
        expect(botao).to_be_in_viewport()
        caixa = botao.bounding_box()
        assert caixa is not None and caixa["y"] + caixa["height"] <= 560
    assert page.evaluate("document.documentElement.scrollHeight <= window.innerHeight")


@pytest.mark.parametrize("texto", ["16px", "24px"])
@pytest.mark.parametrize("passo", ["1", "sites", "2"])
def test_botoes_visiveis_com_janela_baixa(
    page: Page, painel: str, app_painel: FastAPI, tmp_path: Path, texto: str, passo: str
) -> None:
    """Janela de 560px e texto maior, com tudo marcado: o pé (Continuar, Pular, Voltar) fica na
    janela e só o corpo do passo rola."""
    leitor = LeitorFalso(base="http://127.0.0.1:9")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.semear_leitores(con, [leitor])
    app_painel.state.leitores = (leitor,)
    app_painel.state.navegador_instalado = "chrome"
    page.set_viewport_size({"width": 1024, "height": 560})
    page.goto(f"{painel}/primeira-execucao/{passo}")
    page.evaluate(f"document.documentElement.style.fontSize = '{texto}'")
    caixas = page.locator("#assistente-form input[type=checkbox]")
    for i in range(caixas.count()):
        caixas.nth(i).check()
    nomes = {
        "1": ("Continuar", "Pular"),
        "sites": ("Continuar", "Pular", "Voltar ao passo 1"),
        "2": ("Concluir", "Pular", "Voltar ao passo 2"),
    }[passo]
    _pe_dentro_da_janela(page, nomes)
    corpo = page.locator(".assistente-corpo")
    if texto == "24px":  # o corpo rola e o pé continua à vista
        if (
            passo == "1"
        ):  # só o passo mais longo tem conteúdo de sobra; nos outros o corpo pode caber
            assert corpo.evaluate("el => el.scrollHeight > el.clientHeight")
        corpo.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        _pe_dentro_da_janela(page, nomes)


def test_salario_invalido_mostra_o_aviso_e_guarda_o_que_foi_digitado(
    page: Page, painel: str
) -> None:
    page.goto(f"{painel}/primeira-execucao/1")
    page.get_by_label("Cargos ou palavras-chave").fill("Python")
    page.get_by_label("Salário mínimo por mês").fill("muito")
    page.get_by_role("button", name="Continuar").click()
    expect(page.get_by_role("alert")).to_contain_text("Salário mínimo inválido")
    expect(page.get_by_label("Cargos ou palavras-chave")).to_have_value("Python")


def test_recusa_do_segundo_plano_aparece_traduzida_na_tela(
    page: Page, painel: str, sistema: FalsoSistema
) -> None:
    sistema.systemd_ok = False
    page.goto(f"{painel}/primeira-execucao/2")
    page.get_by_label("Ligar o segundo plano").check()
    page.get_by_role("button", name="Concluir").click()
    alerta = page.get_by_role("alert")
    expect(alerta).to_contain_text("o systemd do usuário não responde")
    expect(alerta).not_to_contain_text("segundo_plano.")
    # a pessoa escolhe de novo e conclui
    page.get_by_label("Não ligar agora").check()
    page.get_by_role("button", name="Concluir").click()
    expect(page.get_by_role("heading", name="Tudo pronto")).to_be_visible()


def test_regiao_do_andamento_vazia_nao_ocupa_linha(page: Page, painel: str) -> None:
    page.goto(f"{painel}/primeira-execucao/2")
    page.get_by_label("Não ligar agora").check()
    page.get_by_role("button", name="Concluir").click()
    expect(page.get_by_role("heading", name="Tudo pronto")).to_be_visible()
    regiao = page.locator("#andamento")  # a região viva é o #andamento-etapa (T252)
    expect(regiao).to_be_empty()
    caixa = regiao.bounding_box()
    barra = page.locator(".execucao").bounding_box()
    botao = page.get_by_role("button", name="Buscar agora").bounding_box()
    assert caixa is not None and barra is not None and botao is not None
    assert caixa["height"] == 0
    assert barra["height"] <= botao["height"] + 1  # a barra tem só a linha dos botões


def test_passo_dos_sites_liga_o_site_e_segue(
    page: Page, painel: str, app_painel: FastAPI, tmp_path: Path
) -> None:
    leitor = LeitorFalso(base="http://127.0.0.1:9")
    with closing(abrir(tmp_path / "jobot.db")) as con:
        cadastros.semear_leitores(con, [leitor])
    app_painel.state.leitores = (leitor,)
    app_painel.state.navegador_instalado = "chrome"

    page.goto(f"{painel}/primeira-execucao/1")
    expect(page.get_by_text("Passo 1 de 3")).to_be_visible()
    _passo_1(page)
    expect(page).to_have_url(re.compile(r"/primeira-execucao/sites\?busca=\d+$"))
    expect(page.get_by_text("Passo 2 de 3")).to_be_visible()

    with page.expect_response("**/configuracoes/contas/falso_logado/interruptor"):
        page.get_by_role("switch", name="Site falso").click()
    expect(page.locator("#status-sites")).to_contain_text("Salvo")
    page.get_by_role("button", name="Continuar").click()
    expect(page).to_have_url(re.compile(r"/primeira-execucao/2\?busca=\d+$"))
    expect(page.get_by_text("Passo 3 de 3")).to_be_visible()
    with closing(abrir(tmp_path / "jobot.db")) as con:
        assert cadastros.fontes_com_login_ligadas(con) == ["falso_logado"]
