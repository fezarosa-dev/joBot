"""Empresas sugeridas pela descoberta: lista, aprovar e descartar (plano T74, D71).

Nada entra na busca sozinho: a pessoa aprova ou descarta uma por uma. Aprovar chama
`banco.sugeridas.aprovar`; na Gupy a rota lê antes o `careerPageName` da página de carreira (o
nome que a API casa, decisão 29), e as outras fontes não fazem pedido. Sugestão de empresa que a
pessoa removeu depois leva um aviso com a data (D71, opção a): aprovar não a reativa.
Sugestão que não está mais pendente é 404; a fonte da Gupy fora do ar é 502 e a sugestão fica.
A rede vem do `ClienteEducado`; `app.state.transporte` troca o transporte nos testes.
"""

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from jobot import __version__
from jobot.banco.sugeridas import Sugerida, aprovar, descartar, sugeridas
from jobot.nucleo.coletores import gupy
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.nucleo.relogio import Relogio, RelogioReal
from jobot.painel.seguranca import Con, renderizar

router = APIRouter(prefix="/empresas/sugeridas")
registro = logging.getLogger(__name__)

SugestaoId = Annotated[int, Path(ge=1, le=2**63 - 1)]  # o INTEGER do SQLite tem 64 bits com sinal
PRAZO_S = 120.0


@dataclass(frozen=True)
class Linha:
    s: Sugerida
    removida_em: str | None  # quando a pessoa removeu a empresa (D71); None se não removeu
    link: bool  # a URL de exemplo só vira link se for http ou https


class _SemValidadores:
    """Resolver não usa pedido condicional: não há validador guardado."""

    def ler(self, url: str) -> Validadores | None:
        return None


def _relogio(request: Request) -> Relogio:
    relogio: Relogio = getattr(request.app.state, "relogio", None) or RelogioReal()
    return relogio


def _linhas(con: sqlite3.Connection) -> list[Linha]:
    removidas = {
        (fonte, identificador): quando
        for fonte, identificador, quando in con.execute(
            "SELECT fonte, lower(identificador), removida_em FROM empresa"
            " WHERE removida_em IS NOT NULL"
        )
    }
    return [
        Linha(
            s,
            removidas.get((s.fonte, s.identificador.lower())),
            s.url_exemplo.startswith(("http://", "https://")),
        )
        for s in sugeridas(con)
    ]


def _pagina(request: Request, con: sqlite3.Connection, erro: str | None = None) -> HTMLResponse:
    resposta = renderizar(request, "sugeridas/lista.html", linhas=_linhas(con), erro=erro)
    resposta.status_code = 502 if erro else 200
    return resposta


async def _career_page_name(request: Request, identificador: str) -> str:
    """O nome que a página de carreira da Gupy traz; `ValueError` ou erro de rede se não der."""
    cliente = ClienteEducado(
        getattr(request.app.state, "transporte", None),
        _relogio(request),
        _SemValidadores(),
        __version__,
    )
    try:
        async with asyncio.timeout(PRAZO_S):
            http = cliente.escopo(
                espera_s=gupy.COLETOR.espera_s,
                condicional=False,
                max_pedidos=gupy.COLETOR.max_pedidos,
            )
            return (await gupy.COLETOR.resolver(identificador, http))["careerPageName"]
    finally:
        await cliente.fechar()


@router.get("")
async def lista(request: Request, con: Con) -> HTMLResponse:
    return _pagina(request, con)


@router.post("/{sugestao_id}/aprovar")
async def aprovar_sugestao(request: Request, con: Con, sugestao_id: SugestaoId) -> Response:
    pendente = next((s for s in sugeridas(con) if s.id == sugestao_id), None)
    if pendente is None:
        raise HTTPException(404)
    nome: str | None = None
    parametros: dict[str, str] = {}
    if pendente.fonte == "gupy":
        try:
            nome = await _career_page_name(request, pendente.identificador)
        except Exception as erro:  # ValueError (página não é da Gupy), rede, bloqueio, prazo
            registro.warning(
                "aprovar %s/%s falhou: %r", pendente.fonte, pendente.identificador, erro
            )
            return _pagina(request, con, "sugeridas.erro.fonte_fora")
        parametros = {"careerPageName": nome}
    try:
        aprovar(con, sugestao_id, nome=nome, parametros=parametros)
    except LookupError as erro:  # decidida por outra aba entre a leitura e a gravação
        raise HTTPException(404) from erro
    return RedirectResponse("/empresas/sugeridas", status_code=303)


@router.post("/{sugestao_id}/descartar")
async def descartar_sugestao(con: Con, sugestao_id: SugestaoId) -> Response:
    try:
        descartar(con, sugestao_id)
    except LookupError as erro:
        raise HTTPException(404) from erro
    return RedirectResponse("/empresas/sugeridas", status_code=303)
