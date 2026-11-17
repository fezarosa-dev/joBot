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
ESTADO = {"completo": True, "dados": DADOS, "base": 80_000_000, "navegador": 170_000_000}
# a ponte falsa: mesma forma do `withGlobalTauri` (window.__TAURI__.core)
PONTE = """
window.__chamadas = [];
window.__TAURI__ = { core: {
  Channel: class { constructor() { this.onmessage = () => {}; window.__canal = this; } },
  invoke: async (comando, args) => {
    window.__chamadas.push([comando, args && 'navegador' in args ? args.navegador : null]);
    if (comando === 'estado_instalador') return window.__estado;
    return null;
  },
} };
"""
ETAPAS = {
    "conferir": "Conferindo os arquivos",
    "python": "Preparando o Python",
    "jobot": "Instalando o joBot",
    "navegador": "Instalando o navegador",
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


def test_etapas_escritas_sem_baixando(page: Page, ui: str) -> None:
    _ate_instalando(page, ui)
    linha = page.locator(".progresso-linha")
    for etapa, texto in ETAPAS.items():
        _aviso(page, {"etapa": etapa})
        expect(linha).to_have_text(texto)
        expect(page.get_by_role("status")).to_have_text(texto)
    assert all("Baixando" not in t for t in ETAPAS.values())


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
