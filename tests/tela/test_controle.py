"""O controle da casca (T350; D206, ADR 0027), com o `window.__TAURI__` falso.

Como o `test_instalador.py`: `desktop/ui/` sai de um servidor de arquivos em 127.0.0.1 e
`painel/icone.png` do ícone da casca. A ponte falsa responde aos comandos com o que o teste põe
em `window.__respostas` e anota as chamadas. O relógio é o do Playwright: a consulta periódica
do estado anda sem esperar tempo real.
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
ICONE = RAIZ / "desktop" / "icons" / "icon.png"
ENDERECO = "http://127.0.0.1:47615/"
PARADO = {"ligado": False, "endereco": ENDERECO}
LIGADO = {"ligado": True, "endereco": ENDERECO}
# a ponte falsa: mesma forma do `withGlobalTauri` (window.__TAURI__.core); a área de
# transferência falsa guarda o que a página copiou, nos três motores
PONTE = """
window.__chamadas = [];
window.__argumentos = [];
window.__copiado = null;
Object.defineProperty(navigator, 'clipboard', {
  value: { writeText: async (texto) => { window.__copiado = texto; } },
});
window.__TAURI__ = { core: {
  invoke: async (comando, argumentos) => {
    window.__chamadas.push(comando);
    if (argumentos !== undefined) window.__argumentos.push([comando, argumentos]);
    const resposta = window.__respostas[comando];
    if (comando !== 'estado_controle' && resposta && !resposta.falha) {
      window.__respostas.estado_controle = resposta;
    }
    return resposta;
  },
} };
"""


class _Arquivos(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        caminho = unquote(urlsplit(path).path)
        if caminho == "/painel/icone.png":
            return str(ICONE)
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


def _abrir(page: Page, ui: str, **respostas: dict[str, Any]) -> None:
    todas = {
        "estado_controle": PARADO,
        "ligar": LIGADO,
        "parar": PARADO,
        "abrir_jobot": LIGADO,
        "abrir_release": LIGADO,
    }
    todas.update(respostas)
    page.clock.install()
    page.add_init_script(PONTE + f"window.__respostas = {json.dumps(todas)};")
    page.goto(f"{ui}/controle.html")


def _chamadas(page: Page) -> list[str]:
    resultado: list[str] = page.evaluate("window.__chamadas")
    return resultado


def _botao(page: Page, nome: str) -> Any:
    return page.get_by_role("button", name=nome, exact=True)


def test_parado_ao_abrir_so_mostra_o_estado(page: Page, ui: str) -> None:
    _abrir(page, ui)
    expect(page.get_by_role("status").first).to_have_text("Parado")
    expect(page.get_by_label("Endereço")).to_have_value(ENDERECO)
    expect(_botao(page, "Ligar")).to_be_enabled()
    expect(_botao(page, "Parar")).to_be_disabled()
    expect(_botao(page, "Abrir joBot")).to_have_count(0)
    # o controle não liga nem abre nada sozinho (D206): só pergunta o estado
    assert set(_chamadas(page)) == {"estado_controle"}


def test_ligado_ao_abrir_mostra_abrir_jobot(page: Page, ui: str) -> None:
    # o painel já no ar, por exemplo pelo segundo plano
    _abrir(page, ui, estado_controle=LIGADO)
    expect(page.get_by_role("status").first).to_have_text("Ligado")
    expect(_botao(page, "Abrir joBot")).to_be_visible()
    expect(_botao(page, "Ligar")).to_be_disabled()
    expect(_botao(page, "Parar")).to_be_enabled()
    assert set(_chamadas(page)) == {"estado_controle"}


def test_ligar_parar_e_abrir_chamam_a_casca(page: Page, ui: str) -> None:
    _abrir(page, ui)
    _botao(page, "Ligar").click()
    expect(page.get_by_role("status").first).to_have_text("Ligado")
    expect(_botao(page, "Abrir joBot")).to_be_focused()
    _botao(page, "Abrir joBot").click()
    _botao(page, "Parar").click()
    expect(page.get_by_role("status").first).to_have_text("Parado")
    expect(_botao(page, "Ligar")).to_be_focused()
    expect(_botao(page, "Abrir joBot")).to_have_count(0)
    acoes = [c for c in _chamadas(page) if c != "estado_controle"]
    assert acoes == ["ligar", "abrir_jobot", "parar"]


def test_volta_a_parado_se_o_servidor_cair(page: Page, ui: str) -> None:
    _abrir(page, ui, estado_controle=LIGADO)
    expect(page.get_by_role("status").first).to_have_text("Ligado")
    page.evaluate(f"window.__respostas.estado_controle = {json.dumps(PARADO)}")
    page.clock.run_for(5000)
    expect(page.get_by_role("status").first).to_have_text("Parado")
    expect(_botao(page, "Abrir joBot")).to_have_count(0)


def test_falha_ao_ligar_diz_o_que_houve(page: Page, ui: str) -> None:
    falha = {**PARADO, "falha": "porta", "detalhe": "47615", "log": "fim do log"}
    _abrir(page, ui, ligar=falha)
    _botao(page, "Ligar").click()
    alerta = page.get_by_role("alert")
    expect(alerta).to_contain_text("A porta 47615 está ocupada")
    expect(page.locator("#falha-log")).to_have_text("fim do log")
    expect(page.get_by_role("status").first).to_have_text("Parado")
    expect(_botao(page, "Ligar")).to_be_enabled()


def test_falha_some_quando_a_consulta_ve_o_painel_no_ar(page: Page, ui: str) -> None:
    # o Ligar estourou o prazo, mas o servidor terminou de subir depois
    falha = {**PARADO, "falha": "sem_resposta", "detalhe": "47615", "log": ""}
    _abrir(page, ui, ligar=falha)
    _botao(page, "Ligar").click()
    expect(page.get_by_role("alert")).to_contain_text("não respondeu na porta 47615")
    page.evaluate(f"window.__respostas.estado_controle = {json.dumps(LIGADO)}")
    page.clock.run_for(5000)
    expect(page.get_by_role("status").first).to_have_text("Ligado")
    expect(page.get_by_role("alert")).to_be_hidden()


def test_falha_sem_log_nao_manda_ver_o_registro(page: Page, ui: str) -> None:
    falha = {**PARADO, "falha": "saiu", "detalhe": "", "log": ""}
    _abrir(page, ui, ligar=falha)
    _botao(page, "Ligar").click()
    expect(page.locator("#falha-texto")).to_contain_text("fechou logo ao ligar")
    expect(page.locator("#falha-texto")).not_to_contain_text("registro")
    expect(page.locator("#falha-registro")).to_be_hidden()


def test_parar_que_falha_diz_e_segue_ligado(page: Page, ui: str) -> None:
    _abrir(page, ui, estado_controle=LIGADO, parar={**LIGADO, "falha": "parar", "detalhe": ""})
    _botao(page, "Parar").click()
    expect(page.get_by_role("alert")).to_contain_text("O joBot não parou a tempo")
    expect(page.get_by_role("status").first).to_have_text("Ligado")
    expect(_botao(page, "Parar")).to_be_enabled()


def test_motivo_desconhecido_vira_a_falha_generica(page: Page, ui: str) -> None:
    _abrir(page, ui, ligar={**PARADO, "falha": "<b>x</b>", "detalhe": "y", "log": ""})
    _botao(page, "Ligar").click()
    expect(page.get_by_role("alert")).to_contain_text("Não consegui concluir")
    expect(page.locator("#falha-log")).to_be_hidden()


def _pedir_fechar(page: Page) -> None:
    # o que a casca faz no CloseRequested da janela (`pedir_fechar` do main.rs)
    page.evaluate("window.__jobotPedirFechar && window.__jobotPedirFechar()")


def _respostas_de_fechar(page: Page) -> list[Any]:
    resultado: list[Any] = page.evaluate(
        "window.__argumentos.filter(([c]) => c === 'fechar_controle').map(([, a]) => a)"
    )
    return resultado


def test_fechar_com_o_painel_no_ar_pergunta(page: Page, ui: str) -> None:
    # D215: fechar a janelinha não derruba a aba do navegador sem a pessoa saber
    _abrir(page, ui, estado_controle=LIGADO)
    expect(_botao(page, "Abrir joBot")).to_be_visible()
    _pedir_fechar(page)
    pergunta = page.get_by_role("dialog", name="Deixar o joBot ligado?")
    expect(pergunta).to_be_visible()
    expect(pergunta).to_contain_text("Parar")
    # o foco vai para o diálogo, no botão que não desliga nada
    expect(_botao(page, "Deixar ligado")).to_be_focused()
    expect(_botao(page, "Desligar")).to_be_visible()
    assert _respostas_de_fechar(page) == []


def test_deixar_ligado_so_fecha_a_janela(page: Page, ui: str) -> None:
    _abrir(page, ui, estado_controle=LIGADO)
    expect(_botao(page, "Abrir joBot")).to_be_visible()
    _pedir_fechar(page)
    _botao(page, "Deixar ligado").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert _respostas_de_fechar(page) == [{"desligar": False}]


def test_desligar_para_o_jobot_e_fecha(page: Page, ui: str) -> None:
    _abrir(page, ui, estado_controle=LIGADO)
    expect(_botao(page, "Abrir joBot")).to_be_visible()
    _pedir_fechar(page)
    _botao(page, "Desligar").click()
    assert _respostas_de_fechar(page) == [{"desligar": True}]


def test_esc_cancela_o_fechar(page: Page, ui: str) -> None:
    _abrir(page, ui, estado_controle=LIGADO)
    expect(_botao(page, "Abrir joBot")).to_be_visible()
    _pedir_fechar(page)
    expect(_botao(page, "Deixar ligado")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert _respostas_de_fechar(page) == []
    # e o controle segue como estava
    expect(_botao(page, "Parar")).to_be_enabled()
    # pedir de novo pergunta de novo
    _pedir_fechar(page)
    expect(page.get_by_role("dialog", name="Deixar o joBot ligado?")).to_be_visible()


def test_fechar_com_o_painel_parado_fecha_sem_perguntar(page: Page, ui: str) -> None:
    _abrir(page, ui)
    expect(_botao(page, "Ligar")).to_be_enabled()  # a página desenhou o estado
    _pedir_fechar(page)
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert _respostas_de_fechar(page) == [{"desligar": False}]


def test_sem_o_aviso_antigo_de_fechar(page: Page, ui: str) -> None:
    # o aviso de texto do D207.5 saiu: a pergunta ao fechar o substitui (D215)
    _abrir(page, ui, estado_controle={**LIGADO, "fecha_junto": True})
    expect(_botao(page, "Abrir joBot")).to_be_visible()
    expect(page.get_by_text("Fechar esta janela para o joBot.")).to_have_count(0)


def test_sem_janela_nova_com_o_painel_parado(page: Page, ui: str) -> None:
    _abrir(page, ui, estado_controle={**PARADO, "janela_velha": True})
    expect(page.get_by_role("status").first).to_have_text("Parado")
    expect(_botao(page, "Baixar a janela nova")).to_be_hidden()
    expect(_botao(page, "Ligar")).to_be_enabled()  # controle: a página desenhou o estado


def test_janela_nova_abre_a_pagina_da_release(page: Page, ui: str) -> None:
    # D207.12: o painel no ar é mais novo que esta casca
    _abrir(page, ui, estado_controle={**LIGADO, "janela_velha": True})
    expect(page.get_by_text("Há uma versão nova desta janela.")).to_be_visible()
    _botao(page, "Baixar a janela nova").click()
    expect(_botao(page, "Baixar a janela nova")).to_be_focused()
    assert [c for c in _chamadas(page) if c != "estado_controle"] == ["abrir_release"]


def test_janela_nova_que_nao_abre_mostra_o_endereco(page: Page, ui: str) -> None:
    falha = {**LIGADO, "janela_velha": True, "falha": "release", "detalhe": "sem xdg-open"}
    _abrir(page, ui, estado_controle={**LIGADO, "janela_velha": True}, abrir_release=falha)
    _botao(page, "Baixar a janela nova").click()
    alerta = page.get_by_role("alert")
    expect(alerta).to_contain_text("sem xdg-open")
    expect(alerta).to_contain_text("https://github.com/fezarosa-dev/joBot/releases/latest")


def test_copiar_o_endereco(page: Page, ui: str) -> None:
    _abrir(page, ui)
    _botao(page, "Copiar").click()
    expect(page.get_by_text("Copiado")).to_be_visible()
    assert page.evaluate("window.__copiado") == ENDERECO


def test_teclado_anda_pelos_botoes_ativos(page: Page, ui: str) -> None:
    _abrir(page, ui, estado_controle=LIGADO)
    expect(_botao(page, "Abrir joBot")).to_be_visible()
    vistos = []
    nome = "document.activeElement.textContent || document.activeElement.id"
    for _ in range(4):
        page.keyboard.press("Tab")
        vistos.append(page.evaluate(nome))
    assert vistos == ["endereco", "Copiar", "Parar", "Abrir joBot"]


def test_em_ingles(page: Page, ui: str) -> None:
    page.add_init_script("Object.defineProperty(navigator, 'language', {get: () => 'en-US'})")
    _abrir(page, ui)
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.get_by_role("status").first).to_have_text("Stopped")
    expect(_botao(page, "Start")).to_be_enabled()
    expect(page.get_by_label("Address")).to_have_value(ENDERECO)


def test_pergunta_de_fechar_em_ingles(page: Page, ui: str) -> None:
    page.add_init_script("Object.defineProperty(navigator, 'language', {get: () => 'en-US'})")
    _abrir(page, ui, estado_controle=LIGADO)
    expect(_botao(page, "Open joBot")).to_be_visible()
    _pedir_fechar(page)
    expect(page.get_by_role("dialog", name="Keep joBot running?")).to_be_visible()
    expect(_botao(page, "Keep running")).to_be_focused()
    expect(_botao(page, "Turn off")).to_be_visible()


def test_idioma_escolhido_na_instalacao(page: Page, ui: str) -> None:
    # sistema em português, mas a pessoa escolheu English na tela de instalação
    page.add_init_script("localStorage.setItem('jobot.idioma', 'en')")
    _abrir(page, ui)
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.get_by_role("status").first).to_have_text("Stopped")


def test_cores_do_sistema_no_modo_de_alto_contraste(page: Page, ui: str) -> None:
    page.emulate_media(forced_colors="active")
    _abrir(page, ui)
    # desativado vira GrayText, sem a opacidade que some com as cores do sistema
    parar = _botao(page, "Parar")
    expect(parar).to_be_disabled()
    assert parar.evaluate("b => getComputedStyle(b).opacity") == "1"
