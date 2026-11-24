"""A tela de instalação da casca (T336; desenho 5.2), com o `window.__TAURI__` falso.

`desktop/ui/` é servida por um servidor de arquivos em 127.0.0.1; `painel/` (que o `build.rs`
copia no build) sai direto de `src/jobot/painel/static/`. O canal falso guarda o `onmessage`
que a página põe, e o teste manda por ele os avisos que a casca mandaria.
"""

import json
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.tela

RAIZ = Path(__file__).resolve().parents[2]
UI = RAIZ / "desktop" / "ui"
ESTATICOS = RAIZ / "src" / "jobot" / "painel" / "static"
ICONE = RAIZ / "desktop" / "icons" / "icon.png"
DADOS = "/home/ana/.local/share/jobot"
# os tamanhos do Modelo local, como o build os copia do `ia_local.json` (T418)
IA_LOCAL = {"servidor": 20_000_000, "modelos": {"2b": 1_280_835_840, "4b": 2_740_937_888}}
ESTADO = {
    "completo": True,
    "dados": DADOS,
    "base": 80_000_000,
    "navegador": 170_000_000,
    "ia_local": IA_LOCAL,
}
# a ponte falsa: mesma forma do `withGlobalTauri` (window.__TAURI__.core)
PONTE = """
window.__chamadas = [];
window.__instalar = [];
window.__TAURI__ = { core: {
  Channel: class { constructor() { this.onmessage = () => {}; window.__canal = this; } },
  invoke: async (comando, args) => {
    window.__chamadas.push([comando, args && 'navegador' in args ? args.navegador : null]);
    if (comando === 'instalar') {
      window.__instalar.push([Object.keys(args).sort(), args.navegador, args.modelo_local]);
    }
    if (comando === 'estado_instalador') return window.__estado;
    return null;
  },
} };
"""
ETAPAS = {
    "conferir": "Conferindo os arquivos",
    "python": "Preparando o Python",
    "jobot": "Instalando o joBot",
    "navegador": "Baixando o navegador",
    "ia_local": "Baixando o modelo local",
    "abrir": "Abrindo",
}


class _Arquivos(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        caminho = unquote(urlsplit(path).path)
        if caminho == "/painel/icone.png":
            return str(ICONE)
        if caminho.startswith("/painel/"):
            return str(ESTATICOS / caminho.removeprefix("/painel/"))
        return str(UI / caminho.lstrip("/"))

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture
def ui() -> Iterator[str]:
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Arquivos)
    linha = threading.Thread(target=servidor.serve_forever, args=(0.02,), daemon=True)
    linha.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def _abrir(page: Page, ui: str, estado: dict[str, Any] | None = None) -> None:
    page.add_init_script(PONTE + f"window.__estado = {json.dumps(estado or ESTADO)};")
    page.goto(f"{ui}/index.html")


def _chamadas(page: Page) -> list[list[Any]]:
    resultado: list[list[Any]] = page.evaluate("window.__chamadas")
    return resultado


def _aviso(page: Page, aviso: dict[str, Any]) -> None:
    page.evaluate("a => window.__canal.onmessage(a)", aviso)


def _valor(page: Page) -> int:
    # pelo id: no passo "Pronto" a seção do progresso some da árvore de acessibilidade
    return int(page.locator("#trilho").get_attribute("aria-valuenow") or "-1")


def _ate_instalando(page: Page, ui: str, *, navegador: bool = True) -> None:
    _abrir(page, ui)
    page.get_by_role("button", name="Continuar", exact=True).click()
    if not navegador:
        page.get_by_label("Navegador para sites com login").uncheck()
    page.get_by_role("button", name="Instalar", exact=True).click()
    expect(page.get_by_role("heading", name="Instalando o joBot")).to_be_visible()


def test_os_cinco_passos(page: Page, ui: str) -> None:
    _abrir(page, ui)
    expect(page.get_by_role("heading", name="joBot", exact=True)).to_be_visible()
    page.get_by_role("button", name="Continuar", exact=True).click()
    expect(page.get_by_role("heading", name="O que instalar")).to_be_visible()
    page.get_by_role("button", name="Instalar", exact=True).click()
    expect(page.get_by_role("heading", name="Instalando o joBot")).to_be_visible()
    assert ["instalar", True] in _chamadas(page)
    _aviso(page, {"fim": "falhou", "motivo": "outro"})
    expect(page.get_by_role("alert")).to_contain_text("A instalação não terminou")
    page.get_by_role("button", name="Tentar de novo", exact=True).click()
    expect(page.get_by_role("heading", name="Instalando o joBot")).to_be_visible()
    assert [c for c in _chamadas(page) if c[0] == "instalar"] == [["instalar", True]] * 2
    _aviso(page, {"etapa": "abrir"})
    _aviso(page, {"fim": "pronto"})
    expect(page.get_by_role("heading", name="Pronto")).to_be_visible()


def test_voltar_leva_as_boas_vindas(page: Page, ui: str) -> None:
    _abrir(page, ui)
    page.get_by_role("button", name="Continuar", exact=True).click()
    page.get_by_role("button", name="Voltar", exact=True).click()
    expect(page.get_by_role("heading", name="joBot", exact=True)).to_be_visible()


def test_jobot_e_python_travados_e_navegador_desmarcavel(page: Page, ui: str) -> None:
    _abrir(page, ui)
    page.get_by_role("button", name="Continuar", exact=True).click()
    jobot = page.get_by_label("joBot e Python 3.14")
    expect(jobot).to_be_checked()
    expect(jobot).to_be_disabled()
    expect(page.locator(".ferramenta").first).to_contain_text("necessário")
    navegador = page.get_by_label("Navegador para sites com login")
    expect(navegador).to_be_checked()
    expect(navegador).to_be_enabled()
    espaco = page.locator("#espaco")
    com_navegador = espaco.inner_text()
    navegador.uncheck()
    expect(espaco).not_to_have_text(com_navegador)
    page.get_by_role("button", name="Instalar", exact=True).click()
    assert ["instalar", False] in _chamadas(page)


def test_rodape_com_a_pasta_e_o_espaco_sem_baixar(page: Page, ui: str) -> None:
    _abrir(page, ui)
    page.get_by_role("button", name="Continuar", exact=True).click()
    rodape = page.locator("#rodape")
    expect(rodape).to_contain_text(DADOS)
    expect(rodape).to_contain_text("Espaço em disco")
    # (80 + 170) MB compactados x 3: cerca de 750 MB
    expect(page.locator("#espaco")).to_have_text("cerca de 750 MB")
    assert "baix" not in rodape.inner_text().lower()


def test_etapas_escritas_e_so_o_navegador_baixa(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    linha = page.locator(".progresso-linha")
    for etapa, texto in ETAPAS.items():
        _aviso(page, {"etapa": etapa})
        expect(linha).to_have_text(texto)
        expect(page.get_by_role("status")).to_have_text(texto)
    # só o navegador (D183.24) e o modelo (D185.7) vêm da internet; o resto sai dos recursos
    assert [e for e, t in ETAPAS.items() if "Baixando" in t] == ["navegador", "ia_local"]


def test_progresso_determinado_nao_volta_e_para_no_teto(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    expect(page.get_by_role("progressbar")).to_have_attribute("aria-valuenow", "0")
    valores = []
    avisos: list[dict[str, Any]] = [
        {"etapa": "conferir", "feito": 50, "total": 100},
        {"etapa": "conferir", "feito": 10, "total": 100},  # volta: a barra fica
        {"etapa": "python"},
        {"etapa": "jobot"},
        {"etapa": "navegador", "feito": 7, "total": 14},
        {"etapa": "navegador", "feito": 14, "total": 14},
        {"etapa": "abrir"},
        {"etapa": "conferir", "feito": 0, "total": 100},
    ]
    for aviso in avisos:
        _aviso(page, aviso)
        valores.append(_valor(page))
    assert valores == sorted(valores)
    assert valores[0] == 5  # metade dos 10% da conferência
    assert valores[1] == 5
    assert valores[2] == 10 and valores[3] == 30  # as fatias do uv se completam de uma vez
    assert max(valores) == 95
    _aviso(page, {"etapa": "abrir", "feito": 9, "total": 1})
    assert _valor(page) <= 99
    _aviso(page, {"fim": "pronto"})
    assert _valor(page) == 100


def _largura(page: Page) -> float:
    return page.evaluate(  # type: ignore[no-any-return]
        """() => document.getElementById("instalador-preenchimento").getBoundingClientRect().width
          / document.getElementById("trilho").getBoundingClientRect().width * 100"""
    )


def test_barra_anda_fluida_dentro_da_etapa_e_sem_salto_na_troca(page: Page, ui: str) -> None:
    """D216: sem aviso novo a largura segue andando, rápida no começo e freando, sem passar do
    fim da fatia; o valor real (aria-valuenow) não muda; trocar de etapa não dá salto."""
    page.clock.install()
    _ate_instalando(page, ui)
    _aviso(page, {"etapa": "python"})  # fatia do Python: de 10 a 30
    larguras = []
    for _ in range(8):
        page.clock.run_for(1000)
        larguras.append(_largura(page))
    assert _valor(page) == 10
    passos = [b - a for a, b in zip(larguras, larguras[1:], strict=False)]
    assert all(p > 0 for p in passos), larguras  # nunca para
    assert all(a > b for a, b in zip(passos[1:], passos[2:], strict=False)), larguras  # freando
    assert 10 < larguras[-1] < 30, larguras
    antes = _largura(page)
    _aviso(page, {"etapa": "jobot"})
    page.clock.run_for(100)
    assert 0 <= _largura(page) - antes < 2  # a troca de etapa não pula


def test_sem_navegador_as_outras_etapas_dividem_a_barra(page: Page, ui: str) -> None:
    _ate_instalando(page, ui, navegador=False)
    _aviso(page, {"etapa": "abrir"})
    assert _valor(page) == 92  # 60 de 65 (sem os 35 do navegador)


def test_pe_preso_com_janela_baixa_e_texto_maior(page: Page, ui: str) -> None:
    page.set_viewport_size({"width": 1024, "height": 560})
    _abrir(page, ui)
    page.evaluate("document.documentElement.dataset.texto = 'maior'")
    page.get_by_role("button", name="Continuar", exact=True).click()
    instalar = page.get_by_role("button", name="Instalar", exact=True)
    expect(instalar).to_be_visible()
    caixa = instalar.bounding_box()
    assert caixa is not None
    assert caixa["y"] + caixa["height"] <= 560
    instalar.click()
    expect(page.get_by_role("heading", name="Instalando o joBot")).to_be_visible()


def test_fechar_no_meio_pede_confirmacao(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    page.get_by_role("button", name="Fechar", exact=True).click()
    alerta = page.get_by_role("dialog", name="Parar a instalação?")
    expect(alerta).to_be_visible()
    page.get_by_role("button", name="Continuar instalando", exact=True).click()
    expect(alerta).to_be_hidden()
    assert "fechar_instalador" not in [c[0] for c in _chamadas(page)]
    page.evaluate("window.__jobotPedirFechar()")  # o fechar da janela, pela casca
    page.get_by_role("button", name="Parar e fechar", exact=True).click()
    assert "fechar_instalador" in [c[0] for c in _chamadas(page)]


def test_alerta_com_a_acao_em_cima_e_nenhum_botao_padrao(page: Page, ui: str) -> None:
    # visual do Mac (Alerta): a ação em cima, "Cancelar" embaixo, sem estilo de padrão nem
    # destrutivo (a pessoa pediu para fechar)
    _ate_instalando(page, ui)
    page.evaluate("window.__jobotPedirFechar()")
    botoes = page.get_by_role("dialog").get_by_role("button")
    expect(botoes).to_have_text(["Parar e fechar", "Continuar instalando"])
    for i in range(2):
        classes = botoes.nth(i).get_attribute("class") or ""
        assert "botao-principal" not in classes and "botao-destrutivo" not in classes


def test_parar_mostra_parando_e_o_progresso_nao_apaga(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    page.evaluate("window.__jobotPedirFechar()")
    page.get_by_role("button", name="Parar e fechar", exact=True).click()
    expect(page.get_by_role("status")).to_have_text("Parando…")
    expect(page.locator(".progresso-linha")).to_have_text("Parando…")
    _aviso(page, {"etapa": "jobot"})
    expect(page.locator(".progresso-linha")).to_have_text("Parando…")


def test_tab_segue_a_ordem_visual_do_pe(page: Page, ui: str) -> None:
    _abrir(page, ui)
    page.get_by_role("button", name="Continuar", exact=True).click()
    voltar = page.get_by_role("button", name="Voltar", exact=True)
    instalar = page.get_by_role("button", name="Instalar", exact=True)
    caixa_voltar, caixa_instalar = voltar.bounding_box(), instalar.bounding_box()
    assert caixa_voltar is not None and caixa_instalar is not None
    assert caixa_voltar["x"] < caixa_instalar["x"]
    voltar.focus()
    page.keyboard.press("Tab")
    expect(instalar).to_be_focused()


def test_titulo_com_foco_sem_anel_e_controles_com(page: Page, ui: str) -> None:
    # D217: o título recebe o foco por script (leitor de tela) e não ganha o anel azul
    _abrir(page, ui)
    titulo = page.get_by_role("heading", name="joBot", exact=True)
    titulo.focus()
    expect(titulo).to_be_focused()
    assert titulo.evaluate("e => getComputedStyle(e).outlineStyle") == "none"
    continuar = page.get_by_role("button", name="Continuar", exact=True)
    for _ in range(5):
        page.keyboard.press("Tab")
        if continuar.evaluate("e => e === document.activeElement"):
            break
    expect(continuar).to_be_focused()
    assert continuar.evaluate("e => getComputedStyle(e).outlineStyle") != "none"


def test_falha_mostra_o_detalhe_para_diagnostico(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    _aviso(page, {"fim": "falhou", "motivo": "outro", "detalhe": "uv pip install: deu errado"})
    detalhe = page.locator("#falha-detalhe")
    expect(detalhe).to_be_visible()
    detalhe.get_by_text("Detalhes", exact=True).click()
    expect(detalhe).to_contain_text("uv pip install: deu errado")
    page.get_by_role("button", name="Tentar de novo", exact=True).click()
    _aviso(page, {"fim": "falhou", "motivo": "arquivo"})
    expect(detalhe).to_be_hidden()


def test_fechar_fora_da_instalacao_fecha_sem_perguntar(page: Page, ui: str) -> None:
    _abrir(page, ui)
    expect(page.get_by_role("button", name="Continuar", exact=True)).to_be_visible()
    page.get_by_role("button", name="Fechar", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert "fechar_instalador" in [c[0] for c in _chamadas(page)]


@pytest.mark.parametrize(
    ("motivo", "frase"),
    [
        ("arquivo", "Um arquivo do instalador não é o esperado"),
        ("espaco", "Falta espaço em disco"),
        ("prova", "A conferência do joBot instalado falhou"),
        ("navegador", "Não consegui baixar o navegador"),
        ("qualquer", "A instalação não terminou"),
    ],
)
def test_falha_diz_o_que_houve_com_tentar_de_novo(
    page: Page, ui: str, motivo: str, frase: str
) -> None:
    _ate_instalando(page, ui)
    _aviso(page, {"fim": "falhou", "motivo": motivo})
    expect(page.get_by_role("alert")).to_contain_text(frase)
    expect(page.get_by_role("button", name="Tentar de novo", exact=True)).to_be_visible()


def test_falha_do_navegador_oferece_instalar_sem_ele(page: Page, ui: str) -> None:
    """D183.24: sem rede, tentar de novo com o navegador falha sempre; a própria tela de falha
    instala sem ele (o passo Ferramentas fica para trás, sem Voltar)."""
    _ate_instalando(page, ui)
    _aviso(page, {"fim": "falhou", "motivo": "navegador"})
    expect(page.locator("#falha-oque")).to_contain_text("confira a conexão e o espaço em disco")
    expect(page.locator("#falha-oque")).to_contain_text("instale sem ele")
    page.get_by_role("button", name="Instalar sem o navegador", exact=True).click()
    expect(page.get_by_role("heading", name="Instalando o joBot")).to_be_visible()
    assert [c for c in _chamadas(page) if c[0] == "instalar"] == [
        ["instalar", True],
        ["instalar", False],
    ]
    # sem o navegador a barra não reserva a fatia dele
    _aviso(page, {"etapa": "abrir"})
    assert _valor(page) == 92


@pytest.mark.parametrize("motivo", ["arquivo", "espaco", "prova", "qualquer"])
def test_so_a_falha_do_navegador_oferece_instalar_sem_ele(page: Page, ui: str, motivo: str) -> None:
    _ate_instalando(page, ui)
    _aviso(page, {"fim": "falhou", "motivo": "navegador"})
    page.get_by_role("button", name="Tentar de novo", exact=True).click()
    _aviso(page, {"fim": "falhou", "motivo": motivo})
    expect(page.get_by_role("button", name="Tentar de novo", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Instalar sem o navegador", exact=True)).to_have_count(0)


def test_instalador_incompleto_nao_oferece_instalar(page: Page, ui: str) -> None:
    _abrir(page, ui, {"completo": False, "dados": DADOS})
    expect(page.get_by_role("alert")).to_contain_text("Este instalador está incompleto")
    for nome in ("Continuar", "Instalar", "Tentar de novo"):
        expect(page.get_by_role("button", name=nome, exact=True)).to_have_count(0)
    assert _chamadas(page) == [["estado_instalador", None]]


def test_em_ingles_e_troca_de_idioma(page: Page, ui: str) -> None:
    page.add_init_script("Object.defineProperty(navigator, 'language', {get: () => 'en-US'})")
    _abrir(page, ui)
    expect(page.get_by_role("button", name="Continue", exact=True)).to_be_visible()
    expect(page.locator("html")).to_have_attribute("lang", "en")
    page.get_by_label("Language").select_option("pt")
    expect(page.get_by_role("button", name="Continuar", exact=True)).to_be_visible()
    expect(page.locator("html")).to_have_attribute("lang", "pt")
    # a escolha fica para o controle, que abre logo depois na mesma origem (D207.9)
    assert page.evaluate("localStorage.getItem('jobot.idioma')") == "pt"


# --- Modelo local (T418; desenho 10.1; D185.17) ---

FRASE_IA = (
    "Para usar IA sem internet e sem pagar. Se você marcar, baixa da internet de 1,3 a 2,7 GB, "
    "conforme a memória do computador; dá para baixar depois em Configurações › Ferramentas."
)


def _instalar_args(page: Page) -> list[Any]:
    resultado: list[Any] = page.evaluate("window.__instalar")
    return resultado


def test_grupo_de_ia_so_com_o_modelo_local_desmarcado(page: Page, ui: str) -> None:
    _abrir(page, ui)
    page.get_by_role("button", name="Continuar", exact=True).click()
    grupo = page.get_by_role("group", name="Inteligência artificial (opcional)")
    expect(grupo).to_be_visible()
    # só o Modelo local: Claude Code e Codex esperam o dono (D185.5 e D185.6)
    expect(grupo.get_by_role("checkbox")).to_have_count(1)
    modelo = grupo.get_by_role("checkbox", name="Modelo local", exact=True)
    expect(modelo).not_to_be_checked()
    expect(modelo).to_be_enabled()
    expect(modelo).to_have_accessible_description(FRASE_IA)
    expect(grupo).to_contain_text("até 2,8 GB")
    corpo = page.locator("body").inner_text()
    for nome in ("Claude", "Codex", "vem com", "inclui"):
        assert nome not in corpo, nome
    # depois do navegador, na ordem do DOM (a do Tab)
    caixas = page.get_by_role("checkbox")
    expect(caixas).to_have_count(3)
    assert caixas.nth(2).get_attribute("id") == "ferramenta-ia-local"
    page.get_by_role("button", name="Instalar", exact=True).click()
    assert _instalar_args(page) == [[["modelo_local", "navegador", "progresso"], True, False]]


def test_rodape_soma_o_modelo_marcado(page: Page, ui: str) -> None:
    _abrir(page, ui)
    page.get_by_role("button", name="Continuar", exact=True).click()
    espaco = page.locator("#espaco")
    expect(espaco).to_have_text("cerca de 750 MB")
    page.get_by_label("Modelo local", exact=True).check()
    # 750 MB + o llama-server compactado x 3 (60 MB) + o modelo maior (2 741 MB): 3,6 GB
    expect(espaco).to_have_text("cerca de 3,6 GB")
    page.get_by_label("Modelo local", exact=True).press("Space")  # desmarca pelo teclado
    expect(espaco).to_have_text("cerca de 750 MB")
    page.get_by_label("Modelo local", exact=True).check()
    page.get_by_role("button", name="Instalar", exact=True).click()
    assert _instalar_args(page)[0][1:] == [True, True]


def test_sem_os_tamanhos_o_instalador_nao_oferece_o_modelo(page: Page, ui: str) -> None:
    _abrir(page, ui, {k: v for k, v in ESTADO.items() if k != "ia_local"})
    page.get_by_role("button", name="Continuar", exact=True).click()
    expect(page.get_by_role("heading", name="O que instalar")).to_be_visible()
    expect(page.get_by_role("group", name="Inteligência artificial (opcional)")).to_have_count(0)
    page.get_by_role("button", name="Instalar", exact=True).click()
    assert _instalar_args(page)[0][1:] == [True, False]


def test_etapa_do_modelo_reserva_a_fatia_so_quando_marcado(page: Page, ui: str) -> None:
    _abrir(page, ui)
    page.get_by_role("button", name="Continuar", exact=True).click()
    page.get_by_label("Navegador para sites com login").uncheck()
    page.get_by_label("Modelo local", exact=True).check()
    page.get_by_role("button", name="Instalar", exact=True).click()
    _aviso(page, {"etapa": "ia_local", "feito": 0, "total": 100})
    expect(page.locator(".progresso-linha")).to_have_text("Baixando o modelo local")
    # 60 de 125 (conferir 10, python 20, jobot 30, modelo 60, abrir 5)
    assert _valor(page) == 48
    _aviso(page, {"etapa": "ia_local", "feito": 50, "total": 100})
    assert _valor(page) == 72  # 90 de 125


def test_pronto_diz_o_que_nao_baixou_e_segue_para_o_controle(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    _aviso(page, {"etapa": "ia_local"})
    _aviso(page, {"fim": "pronto", "ia_local": "sem_rede"})
    expect(page.get_by_role("heading", name="Pronto")).to_be_visible()
    expect(page.get_by_role("heading", name="Pronto")).to_be_focused()
    aviso = page.locator("#pronto-ia")
    expect(aviso).to_have_text(
        "O joBot está instalado, mas o modelo local não baixou: sem conexão com a internet. "
        "Baixe depois em Configurações › Ferramentas."
    )
    expect(page.get_by_role("heading", name="Pronto")).to_have_accessible_description(
        aviso.inner_text()
    )
    expect(page.locator("[data-passo=pronto]")).not_to_contain_text("Abrindo")
    principais = page.locator(".botao-principal:visible")
    expect(principais).to_have_count(1)
    seguir = page.get_by_role("button", name="Continuar", exact=True)
    expect(principais).to_have_text("Continuar")
    # do título, o Tab vai direto ao botão (o caminho do job aberta do pacotes.yml)
    page.keyboard.press("Tab")
    expect(seguir).to_be_focused()
    url = page.url
    page.keyboard.press("Enter")
    # quem encolhe a janela e mostra o controle é a casca (D207.2), não a página
    page.wait_for_function("window.__chamadas.at(-1)[0] === 'mostrar_controle'")
    assert page.url == url


@pytest.mark.parametrize(
    ("motivo", "frase"),
    [
        ("espaco", "falta espaço em disco"),
        ("arquivo", "o arquivo baixado não confere"),
        ("ocupado", "outro download do modelo está em curso"),
        ("programa_ausente", "o programa do modelo não roda neste computador"),
        ("modelo_ausente", "o modelo não está disponível para este computador"),
        ("qualquer", "o download não terminou"),
    ],
)
def test_pronto_traduz_o_motivo_do_modelo(page: Page, ui: str, motivo: str, frase: str) -> None:
    _ate_instalando(page, ui)
    _aviso(page, {"fim": "pronto", "ia_local": motivo})
    expect(page.locator("#pronto-ia")).to_contain_text(f"não baixou: {frase}.")


def test_pronto_sem_falha_do_modelo_nao_mostra_aviso(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    _aviso(page, {"etapa": "abrir"})
    _aviso(page, {"fim": "pronto"})
    expect(page.get_by_role("heading", name="Pronto")).to_be_visible()
    expect(page.locator("[data-passo=pronto]")).to_contain_text("Abrindo")
    # controle: o aviso existe e fica escondido
    expect(page.locator("#pronto-ia")).to_have_count(1)
    expect(page.locator("#pronto-ia")).to_be_hidden()
    expect(page.locator("#seguir")).to_be_hidden()


def test_fechar_no_download_do_modelo_diz_que_o_jobot_fica(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    page.evaluate("window.__jobotPedirFechar()")
    expect(page.get_by_role("dialog", name="Parar a instalação?")).to_be_visible()
    page.get_by_role("button", name="Continuar instalando", exact=True).click()
    _aviso(page, {"etapa": "ia_local", "feito": 1, "total": 10})
    page.evaluate("window.__jobotPedirFechar()")
    alerta = page.get_by_role("dialog", name="Parar o download do modelo?")
    expect(alerta).to_be_visible()
    expect(alerta).to_contain_text("O joBot já está instalado")
    expect(alerta).to_contain_text("Configurações › Ferramentas")
    page.get_by_role("button", name="Parar e fechar", exact=True).click()
    assert "fechar_instalador" in [c[0] for c in _chamadas(page)]


def test_modelo_local_em_ingles(page: Page, ui: str) -> None:
    page.add_init_script("Object.defineProperty(navigator, 'language', {get: () => 'en-US'})")
    _abrir(page, ui)
    page.get_by_role("button", name="Continue", exact=True).click()
    grupo = page.get_by_role("group", name="Artificial intelligence (optional)")
    modelo = grupo.get_by_role("checkbox", name="Local model", exact=True)
    expect(modelo).not_to_be_checked()
    expect(modelo).to_have_accessible_description(
        "To use AI offline and for free. If you check it, it downloads 1.3 to 2.7 GB from the "
        "internet, depending on the computer's memory; you can download it later in "
        "Settings › Tools."
    )
