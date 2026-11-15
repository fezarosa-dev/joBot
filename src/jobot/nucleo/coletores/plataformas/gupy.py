"""Coletor Gupy (apêndice 2.5): API de busca do portal, um escopo por empresa e um por cargo.

O escopo é uma string que se basta (o `coletar` só recebe ela): `empresa:<subdomínio>:<nome>`,
com o nome de exibição que a API casa (`careerPageName`, caixa exata), ou `cargo:<termo>`.
A lista já traz a descrição: não há `detalhar`.
"""

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from jobot.nucleo.coletores.base import (
    SEM_MUDANCA,
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import ErroDeRede, HttpEducado
from jobot.nucleo.modelo import VagaColetada

_LIMITES = limites("gupy")
_API = "https://portal.gupy.io/api/job-search/jobs"
_LIMIT = 100  # a API recusa 200
_DOMINIO = ".gupy.io"
_SUBDOMINIO = re.compile(r"[a-z0-9-]{1,63}")
_NAO_EMPRESA = frozenset({"portal", "www"})
_NEXT_DATA = re.compile(
    r"""<script[^>]*\bid=["']__NEXT_DATA__["'][^>]*>(.*?)</script>""", re.DOTALL | re.IGNORECASE
)


class _FormatoMudou(Exception):
    """A resposta não traz a lista `data`, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _data(valor: object) -> date | None:
    # shortcut: `applicationDeadline` vem à meia-noite UTC (`2027-01-12T00:00:00.000Z`), que é o
    # dia escrito; vale esse dia, sem converter fuso (D45, prazo). Trocar se a D45 mandar converter.
    try:
        return datetime.fromisoformat(valor).date() if isinstance(valor, str) else None
    except ValueError:
        return None


def _local(job: Mapping[str, object]) -> tuple[str, ...]:
    cidade, estado = _texto(job.get("city")), _texto(job.get("state"))
    return tuple(filter(None, [", ".join(filter(None, [cidade, estado]))]))


def _vaga(escopo: str, job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    titulo, empresa = _texto(job.get("name")), _texto(job.get("careerPageName"))
    if not titulo or not empresa:
        return None
    try:
        return VagaColetada(
            fonte="gupy",
            escopo=escopo,
            url=_texto(job.get("jobUrl")),  # com ?jobBoardSource=: a canônica tira
            titulo=titulo,
            empresa=empresa,
            descricao_formato="texto",
            descricao=_texto(job.get("description")),
            id_externo=str(job["id"]) if isinstance(job.get("id"), int | str) else None,
            locais=_local(job),
            modalidade_declarada=_texto(job.get("workplaceType")) or None,
            contrato_declarado=_texto(job.get("type")) or None,
            publicada_em=_data_hora(job.get("publishedDate")),
            prazo=_data(job.get("applicationDeadline")),
        )
    except ValueError:  # url fora de http/https
        return None


def _do_host(vaga: VagaColetada, identificador: str) -> bool:
    return (urlsplit(vaga.url).hostname or "").lower() == f"{identificador}{_DOMINIO}"


def _ler(
    escopo: str, identificador: str | None, texto: str
) -> tuple[list[VagaColetada], int, int, int]:
    """(vagas, puladas por formato, itens na página, limit da resposta)."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    itens = dados.get("data") if isinstance(dados, dict) else None
    if not isinstance(itens, list):
        raise _FormatoMudou
    lidas = [v for v in (_vaga(escopo, j) for j in itens) if v is not None]
    if itens and not lidas:
        raise _FormatoMudou
    # Nome genérico ("Página de Carreira") casa vaga de outras empresas: só vale o host da empresa.
    vagas = [v for v in lidas if identificador is None or _do_host(v, identificador)]
    paginacao = dados.get("pagination")
    limit = paginacao.get("limit") if isinstance(paginacao, dict) else None
    limit = (
        limit if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0 else _LIMIT
    )
    return vagas, len(itens) - len(lidas), len(itens), limit


def _escopo(escopo: str) -> tuple[str | None, dict[str, str]]:
    """(subdomínio da empresa ou None, parâmetro de busca); `ValueError` se não for nosso."""
    tipo, _, resto = escopo.partition(":")
    if tipo == "cargo" and resto:
        return None, {"jobName": resto}
    identificador, _, nome = resto.partition(":")
    if tipo == "empresa" and identificador and nome:
        return identificador, {"careerPageName": nome}
    raise ValueError(f"escopo inválido: {escopo!r}")


class Gupy:
    chave: str = "gupy"
    nome: str = "Gupy"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("portal.gupy.io",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        empresas: dict[str, str] = {}
        for e in ctx.empresas:
            nome = _texto(e.parametros.get("careerPageName")) or e.nome.strip()
            empresas.setdefault(e.identificador, f"empresa:{e.identificador}:{nome}")
        cargos = dict.fromkeys(f"cargo:{t.strip()}" for t in ctx.termos if t.strip())
        return [*empresas.values(), *cargos]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        identificador, busca = _escopo(escopo)
        pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            offset = 0
            while True:
                params = {**busca, "limit": str(_LIMIT), "offset": str(offset)}
                # shortcut: só a primeira página leva pedido condicional; o 304 dela vale pela
                # lista toda (304 não diz quantas páginas há). Mudança só nas páginas seguintes
                # (empresa com mais de 100 vagas) aparece quando a primeira mudar.
                resposta = await http.pedir("GET", _API, params=params, condicional=offset == 0)
                if resposta.status == 304:
                    yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                    return
                vagas, ruins, itens, limit = _ler(escopo, identificador, resposta.texto)
                pulados += ruins
                yield vagas
                if itens < limit:
                    return
                offset += limit

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (D45, como no Greenhouse).
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o subdomínio ou o endereço de uma página da empresa; faz um pedido à página.

        Devolve o subdomínio em minúsculas e o `publicationName` da página (com strip), que é o
        `careerPageName` que a API aceita (decisão 29). `ValueError` se não for uma página de
        empresa da Gupy ou se a página não trouxer o nome.
        """
        texto = identificador.strip()
        host = texto
        if "/" in texto or "." in texto or ":" in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            if partes.scheme not in ("http", "https"):
                raise ValueError(f"endereço não é http/https: {identificador!r}")
            host = (partes.hostname or "").lower()
            if not host.endswith(_DOMINIO):
                raise ValueError(f"não é uma página da Gupy: {identificador!r}")
            host = host.removesuffix(_DOMINIO)
        sub = host.lower()
        if not _SUBDOMINIO.fullmatch(sub) or sub in _NAO_EMPRESA:
            raise ValueError(f"identificador inválido: {identificador!r}")
        try:
            pagina = await http.pedir("GET", f"https://{sub}{_DOMINIO}/")
        except ErroDeRede as erro:
            if erro.status == 404:
                raise ValueError(f"a Gupy não tem a página {sub}{_DOMINIO}") from erro
            raise
        return {"identificador": sub, "careerPageName": _publication_name(pagina.texto, sub)}


def _publication_name(html: str, sub: str) -> str:
    """O `props.pageProps.careerPage.publicationName` do `__NEXT_DATA__`, sem espaços nas pontas."""
    achado = _NEXT_DATA.search(html)
    if achado is None:
        raise ValueError(f"a página de {sub} não traz __NEXT_DATA__")
    try:
        nome = json.loads(achado.group(1))["props"]["pageProps"]["careerPage"]["publicationName"]
    except (ValueError, KeyError, TypeError) as erro:
        raise ValueError(f"a página de {sub} não traz publicationName") from erro
    if not isinstance(nome, str) or not nome.strip():
        raise ValueError(f"a página de {sub} traz publicationName vazio")
    return nome.strip()


COLETOR = Gupy()
