"""Valores da navegação com login que dependem de decisão do dono (D132, para confirmar).

Moram só aqui: o resto do código e os testes leem daqui.
"""

from typing import Final

MAX_LISTA: Final = 10  # páginas de lista por site, contando a `url_entrada` (D132.19, E16)
MAX_VAGA: Final = 20  # páginas de vaga por site (D132.32)
ESPERA_MIN_S: Final = 3.0  # espera antes de cada navegação depois da primeira (D132.19)
ESPERA_MAX_S: Final = 8.0
ESPERA_CLOUDFLARE_S: Final = 30  # (D132.30, D132.44)
ESPERA_TOKEN_S: Final = 30  # (D132.31)
JANELA_PARADA_S: Final = 900  # (D132.26)
PRAZO_LOGIN_MANUAL_S: Final = 600  # (D132.52)
INTERVALO_LOGIN_MANUAL_S: Final = 5.0  # leitura da janela de login enquanto a pessoa entra
MAX_RESPOSTA_BYTES: Final = 5 * 1024 * 1024  # (D132.54)
MAX_RESPOSTAS: Final = 50
# Técnico, fora da D132: o `close` do contexto pode chegar logo depois do erro do Playwright que
# o fechamento causou; só nesse caminho de erro a execução espera por ele, no máximo este tempo.
ESPERA_FECHAR_S: Final = 1.0
# Técnicos, fora da D132: o cofre do sistema pode travar esperando a senha da pessoa; o widget
# acabou de ser achado, então ler um atributo dele não espera mais que isto.
PRAZO_COFRE_S: Final = 15.0
ESPERA_ATRIBUTO_MS: Final = 1_000
