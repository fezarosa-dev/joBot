"""`GET /aviso-candidatura`: a faixa "Você se candidatou?" (plano T285; desenho 5.6).

Lê só as perguntas pendentes; não faz pedido nenhum. O fragmento leva a chave `mostrando` do que
fica à vista, e a casca a manda de volta no próximo GET (`hx-include`): com o mesmo total e a mesma
pergunta no topo (ou a confirmação, ou a faixa vazia), a rota responde 204 e o HTMX não troca nada,
então a volta de foco à janela não refaz a faixa nem tira o Desfazer.
"""

import re
import sqlite3
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Request, Response

from jobot.banco import leitura
from jobot.painel.seguranca import Con, caminho_do_painel, renderizar

router = APIRouter()

# até 19 dígitos: o `int()` de um texto enorme levantaria ValueError (500)
_CHAVE = re.compile(r"([pc])([0-9]{1,19})-([0-9]{1,19})|v-0")


def chave_mostrando(tipo: Literal["p", "c", "v"], vaga_id: int = 0, total: int = 0) -> str:
    """`p{id}-{total}` (pergunta), `c{id}-{total}` (confirmação) ou `v-0` (faixa vazia)."""
    return "v-0" if tipo == "v" else f"{tipo}{vaga_id}-{total}"


def _nada_mudou(chave: str, lista: list[leitura.Pergunta], total: int) -> bool:
    achou = _CHAVE.fullmatch(chave)
    if achou is None:
        return False
    if chave == "v-0":
        return total == 0
    tipo, vaga, n = achou.groups()
    if int(n) != total:
        return False
    return tipo == "c" or (bool(lista) and lista[0].vaga_id == int(vaga))


def voltar_da_pagina(request: Request) -> str:
    """Caminho e consulta da página aberta (`HX-Current-URL`), pela regra do `de_volta` (E21)."""
    atual = request.headers.get("hx-current-url")
    if atual is None:
        return "/"
    partes = urlsplit(atual)
    return caminho_do_painel(partes.path + ("?" + partes.query if partes.query else ""))


def faixa(
    request: Request, con: sqlite3.Connection, voltar: str, confirmada: int | None = None
) -> Response:
    """O fragmento: a confirmação da vaga `confirmada`, a pendente mais recente ou vazio."""
    lista, total = leitura.perguntas_pendentes(con, 1)
    ctx: dict[str, object] = {"voltar": voltar, "total": total, "p": None, "confirmada": None}
    if confirmada is not None:
        titulo = con.execute("SELECT titulo FROM vaga WHERE id = ?", (confirmada,)).fetchone()[0]
        ctx["confirmada"] = {"vaga_id": confirmada, "titulo": titulo}
        ctx["mostrando"] = chave_mostrando("c", confirmada, total)
    elif lista:
        ctx["p"] = lista[0]
        ctx["mostrando"] = chave_mostrando("p", lista[0].vaga_id, total)
    else:
        ctx["mostrando"] = chave_mostrando("v")
    return renderizar(request, "aviso_candidatura/faixa.html", **ctx)


@router.get("/aviso-candidatura")
async def aviso_candidatura(request: Request, con: Con, mostrando: str = "") -> Response:
    lista, total = leitura.perguntas_pendentes(con, 1)
    if _nada_mudou(mostrando, lista, total):
        return Response(status_code=204)
    return faixa(request, con, voltar_da_pagina(request))
