"""Scripts de JavaScript da página. Único módulo que chama `evaluate`.

Os três scripts são literais fixos (o teste por AST confere). Dados da chamada (campo,
token, nome da função de retorno) entram só como argumento do `evaluate`, nunca no texto.
"""

import re
from typing import Final

from playwright.async_api import Page

ROLAR: Final = "() => window.scrollBy(0, document.body.scrollHeight)"

# Escreve o token no campo de resposta do próprio widget e, se o widget declarou uma função de
# retorno, chama só ela: o nome é resolvido parte por parte a partir de `window` (sem eval nem
# Function) e função nativa (eval, Function, alert...) não é chamada. Erro do JS da página nunca
# sobe: escrita do token que lança ou caminho que não leva a função dá false (função não chamada);
# função do site que lança já foi chamada, dá true.
ENTREGAR_TOKEN: Final = """([campo, token, retorno]) => {
  try {
    for (const el of document.getElementsByName(campo)) {
      if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') el.value = token;
    }
  } catch (e) {
    return false;
  }
  if (retorno === null) return false;
  let pai = window;
  let alvo = window;
  try {
    for (const parte of retorno.split('.')) {
      if (alvo === null || alvo === undefined) return false;
      pai = alvo;
      alvo = alvo[parte];
    }
    if (typeof alvo !== 'function') return false;
    if (Function.prototype.toString.call(alvo).includes('[native code]')) return false;
  } catch (e) {
    return false;
  }
  try {
    alvo.call(pai, token);
  } catch (e) {
    // o site já foi chamado; o erro é dele
  }
  return true;
}"""

# Só se o cabeçalho `user-agent` do pedido não servir.
USER_AGENT: Final = "() => navigator.userAgent"

NOME_RETORNO = re.compile(r"[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*", re.ASCII)


def nome_de_retorno_valido(nome: str) -> bool:
    return NOME_RETORNO.fullmatch(nome) is not None


async def rolar(page: Page) -> None:
    await page.evaluate(ROLAR)


async def entregar_token(page: Page, campo: str, token: str, nome_retorno: str | None) -> bool:
    """True se a função de retorno foi chamada. Nome fora do padrão: não toca na página."""
    if nome_retorno is not None and not nome_de_retorno_valido(nome_retorno):
        return False
    return await page.evaluate(ENTREGAR_TOKEN, [campo, token, nome_retorno]) is True


async def agente_do_navegador(page: Page) -> str:
    """O user agent do próprio navegador, para quando nenhum pedido trouxe o cabeçalho."""
    agente = await page.evaluate(USER_AGENT)
    return agente if isinstance(agente, str) else ""
