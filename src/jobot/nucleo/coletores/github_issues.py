"""Coletor das issues do GitHub (apêndice 2.1): um escopo por repositório, API REST sem token.

A lista pagina pelo cabeçalho `Link` (`rel="next"`), seguido exatamente como vier. A API de
issues devolve pull requests junto: o item com a chave `pull_request` é descartado. O login do
autor não é lido (DR-15). Não há `detalhar`: a lista já traz o corpo, em Markdown.
"""

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from jobot.nucleo.coletores.base import (
    SEM_MUDANCA,
    ContextoColeta,
    Estado,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import HttpEducado
from jobot.nucleo.modelo import VagaColetada

_LIMITES = limites("github_issues")
_HOST_API = "api.github.com"
_URL = f"https://{_HOST_API}/repos/{{escopo}}/issues"
# Repositórios do apêndice 2.1, com a caixa exata do nome.
_REPOSITORIOS = (
    "backend-br/vagas",
    "frontendbr/vagas",
    "soujava/vagas-java",
    "remotejobsbr/design-ux-vagas",
    "developersRJ/vagas",
)
_ESCOPO = re.compile(r"[A-Za-z0-9_-]+/(?!\.\.?$)[A-Za-z0-9_.-]+")
_LINK = re.compile(r"<([^>]*)>([^,]*)")
_NEXT = re.compile(r'\brel="?next(?=["\s;]|$)')
# shortcut: 30 páginas de 100 issues (3.000 por repositório) é o teto contra um `Link` que nunca
# acaba; o maior repositório tem 42 abertas. Subir se algum passar de meio milhar.
_MAX_PAGINAS = 30


class _FormatoMudou(Exception):
    """A resposta não é uma lista, ou nenhum item dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _vaga(escopo: str, issue: dict[str, object]) -> VagaColetada | None:
    """Uma issue legível, ou `None` se faltar campo obrigatório (DR-08)."""
    titulo, numero = _texto(issue.get("title")), issue.get("number")
    if not titulo or type(numero) is not int:
        return None
    corpo, etiquetas = issue.get("body"), issue.get("labels")
    try:
        return VagaColetada(
            fonte="github_issues",
            escopo=escopo,
            url=_texto(issue.get("html_url")),
            titulo=titulo,
            # shortcut: a issue não traz a empresa em campo próprio (está no título ou no corpo,
            # em formatos que mudam por repositório); vale o nome do repositório até o dono
            # decidir (duvidas, T31).
            empresa=escopo,
            descricao_formato="markdown",
            descricao=corpo if isinstance(corpo, str) else "",
            id_externo=f"{escopo}#{numero}",
            publicada_em=_data_hora(issue.get("created_at")),
            etiquetas=tuple(
                n
                for e in (etiquetas if isinstance(etiquetas, list) else [])
                if isinstance(e, dict) and (n := _texto(e.get("name")))
            ),
        )
    except ValueError:  # url fora de http/https
        return None


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis e quantas foram puladas (pull request não conta como pulado)."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    if not isinstance(dados, list):
        raise _FormatoMudou
    issues = [i for i in dados if not (isinstance(i, dict) and "pull_request" in i)]
    vagas = [v for i in issues if isinstance(i, dict) and (v := _vaga(escopo, i)) is not None]
    if issues and not vagas:
        raise _FormatoMudou
    return vagas, len(issues) - len(vagas)


def _proxima(link: str | None) -> str | None:
    """O endereço do `rel="next"` do cabeçalho `Link`, como veio."""
    for url, parametros in _LINK.findall(link or ""):
        if _NEXT.search(parametros):
            return str(url)
    return None


def _da_api(url: str) -> bool:
    partes = urlsplit(url)
    return partes.scheme == "https" and partes.netloc.lower() == _HOST_API


class GithubIssues:
    chave: str = "github_issues"
    nome: str = "Issues do GitHub"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (_HOST_API,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return list(_REPOSITORIOS)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        if not _ESCOPO.fullmatch(escopo):
            raise ValueError(f"repositório inválido: {escopo!r}")
        pulados = 0
        parada: tuple[Estado, str] | None = None

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, parada
            url = _URL.format(escopo=escopo)
            params: dict[str, str] | None = {"state": "open", "per_page": "100"}
            vistas = {url}
            for n in range(_MAX_PAGINAS):
                # O 304 só vale para a primeira página (a 304 não traz `Link`): as seguintes
                # vão sem validador, e a mistura 200 com 304 nunca acontece.
                resposta = await http.pedir("GET", url, params=params, condicional=n == 0)
                if resposta.status == 304:
                    yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                    return
                vagas, ignoradas = _ler(escopo, resposta.texto)
                pulados += ignoradas
                yield vagas
                proxima = _proxima(resposta.cabecalhos.get("Link"))
                if proxima is None:
                    return
                if resposta.cabecalhos.get("x-ratelimit-remaining") == "0":
                    parada = ("no_limite", "saude.cota")  # só importa se ainda há o que ler
                    return
                if not _da_api(proxima) or proxima in vistas:
                    parada = ("parcial", "saude.formato_mudou")
                    return
                vistas.add(proxima)
                url, params = proxima, None
            parada = ("parcial", "saude.limite_atingido")

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            # shortcut: formato quebrado na página 2+ descarta as vagas da 1 (falhou não fecha
            # vaga); nenhum repositório passa de uma página hoje, rever se algum passar.
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if resultado.estado != "ok":
            return resultado
        if parada is not None:
            return ResultadoEscopo(resultado.vagas, *parada, resultado.pedidos)
        if pulados:
            # shortcut: a contagem de pulados não vai no motivo (D45, opção provisória (b)).
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz o corpo da issue: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Fonte sem cadastro de empresa: os repositórios são fixos."""
        raise ValueError(f"github_issues não tem empresa a resolver: {identificador!r}")


COLETOR = GithubIssues()
