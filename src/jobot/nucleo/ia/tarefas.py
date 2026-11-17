"""Tarefas da IA (desenho 5.2 da fase 4): esquema de saída, `VERSAO` e a conferência no código."""

import re
import string
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from jobot.nucleo.texto import normalizar

# Sobe quando o texto do pedido (`pedidos.py`) ou o esquema da tarefa mudam: a chave do laço muda e
# a vaga é pedida de novo (desenho 5.1 e 5.4).
VERSAO = {"encaixe": 1}


class SaidaEncaixe(BaseModel):
    """O que o modelo devolve no `encaixe`: só o que a vaga pede. `tem` e `faltam` são do código."""

    model_config = ConfigDict(extra="forbid")
    pede: list[Annotated[str, Field(max_length=60)]] = Field(max_length=30)


# Pontas que saem de cada item (D190.5): só a pontuação de fechamento no fim e "(" no começo; o "."
# do começo fica (".NET"), e "+" e "#" também ("C++", "C#").
_COMECO = string.whitespace + "("
_FIM = string.whitespace + ",;:.!?)"


def pede_da_vaga(pede: list[str], texto: str) -> list[str]:
    """Anti-invenção: fica só o item que aparece, normalizado e como palavra inteira, no texto
    enviado ao modelo (`TextoVaga.texto`); repetidos e vazios saem, na ordem da resposta."""
    alvo = normalizar(texto)
    vistos: set[str] = set()
    ficam = []
    for item in pede:
        limpo = item.lstrip(_COMECO).rstrip(_FIM)
        forma = normalizar(limpo)
        if not forma or forma in vistos:
            continue
        if re.search(rf"(?<![\w+#]){re.escape(forma)}(?![\w+#])", alvo):
            vistos.add(forma)
            ficam.append(limpo)
    return ficam
