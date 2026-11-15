"""Valores da navegação com login que dependem de decisão do dono (D132, para confirmar).

Moram só aqui: o resto do código e os testes leem daqui.
"""

from typing import Final

from jobot.nucleo.http import ESPERAS_LIMITE

MAX_LISTA: Final = 10  # páginas de lista por site, contando a `url_entrada` (D132.19, E16)
MAX_VAGA: Final = 20  # páginas de vaga por site (D132.32)
ESPERA_MIN_S: Final = 3.0  # espera antes de cada navegação depois da primeira (D132.19)
ESPERA_MAX_S: Final = 8.0
ESPERA_CLOUDFLARE_S: Final = 30  # (D132.30, D132.44)
ESPERA_TOKEN_S: Final = 30  # (D132.31)
JANELA_PARADA_S: Final = 900  # (D132.26)
OLHAR_S: Final = 5  # a janela parada olha cada aba a cada 5 s (D132.26)
PRAZO_LOGIN_MANUAL_S: Final = 600  # (D132.52)
ESPERA_SAIR_JANELA_S: Final = 10.0  # entre o SIGTERM e o SIGKILL da janela comum (D136.3)
MAX_RESPOSTA_BYTES: Final = 5 * 1024 * 1024  # (D132.54)
MAX_RESPOSTAS: Final = 50
# Técnico, fora da D132: o `close` do contexto pode chegar logo depois do erro do Playwright que
# o fechamento causou, ou do `close` da aba parada que fechou (T225); só nesses dois caminhos a
# execução espera por ele, no máximo este tempo.
ESPERA_FECHAR_S: Final = 1.0
# Técnicos, fora da D132: o cofre do sistema pode travar esperando a senha da pessoa; o widget
# acabou de ser achado, então ler um atributo dele não espera mais que isto.
PRAZO_COFRE_S: Final = 15.0
ESPERA_ATRIBUTO_MS: Final = 1_000
# Técnicos, fora da D132 (T228, D135.7): moravam em `pagina.py`.
ESPERA_ASSENTAR_MS: Final = 10_000  # `networkidle` depois do `load` (E11); estouro é ignorado
PASSOS_DEPOIS_DE_ROLAR: Final = (
    5  # shortcut: até 5 s de 1 em 1 pelos pedidos da página; rever na Parte B
)
ESPERA_429_S: Final = ESPERAS_LIMITE[0]  # 429 sem `Retry-After`: o número único de `nucleo/http.py`
# Técnico, fora da D132: resposta em fluxo (long-poll) nunca entrega o corpo; `prontas()` espera
# os corpos só este tempo e cancela os que sobrarem.
PRAZO_CORPOS_S: Final = 10.0
