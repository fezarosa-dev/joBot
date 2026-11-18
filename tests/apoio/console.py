"""Erros do console nos testes de tela, com o mesmo critério nos três motores (T352)."""

from playwright.sync_api import ConsoleMessage, Page

# O Firefox registra como erro a fonte cujo download a navegação seguinte cortou
# (NS_BINDING_ABORTED, 0x804B0002); a página nova carrega a fonte de novo, nada falha no painel.
_FONTE_CORTADA = ("downloadable font: download failed", "status=2152398850")

# O WebKit dá `error` (não `abort`) ao pedido do htmx que a navegação corta, e o htmx escreve
# `htmx:sendError` no console. A página já está saindo, ninguém vê; vira aviso só nesse intervalo
# (do beforeunload ou pagehide ao pageshow), e o resto do htmx continua contando como erro.
_SAINDO = """
addEventListener('beforeunload', () => { window.__jobotSaindo = true; });
addEventListener('pagehide', () => { window.__jobotSaindo = true; });
addEventListener('pageshow', () => { window.__jobotSaindo = false; });
const __jobotErro = console.error.bind(console);
console.error = (...partes) => {
  const saindo = window.__jobotSaindo && String(partes[0]).startsWith('htmx:');
  (saindo ? console.warn : __jobotErro)(...partes);
};
"""


def anotar_erros(page: Page, ignorar: str | None = None) -> list[str]:
    """Junta os erros do console e as exceções da página; violação do CSP aparece como erro.
    `ignorar` tira as mensagens com esse trecho (um erro que o teste provoca de propósito)."""
    erros: list[str] = []

    def no_console(mensagem: ConsoleMessage) -> None:
        texto = mensagem.text
        if mensagem.type != "error" or all(x in texto for x in _FONTE_CORTADA):
            return
        if ignorar is None or ignorar not in texto:
            erros.append(texto)

    page.add_init_script(_SAINDO)
    page.on("console", no_console)
    page.on("pageerror", lambda e: erros.append(str(e)))
    return erros
