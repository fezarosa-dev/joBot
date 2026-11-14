"""Coletor Hacker News "Who is hiring" (apêndice 2.3): só a API de busca da Algolia.

Dois pedidos por execução: acha o tópico do mês e lê a árvore dele. Cada comentário de primeiro
nível é uma vaga. Nunca se pede página de `news.ycombinator.com` (os termos do site proíbem);
o endereço do comentário só vira o link da vaga. O autor do comentário não é lido.
"""

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Literal

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import HttpEducado
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.texto import para_texto

_LIMITES = limites("hn_algolia")
_API = "https://hn.algolia.com/api/v1"
_TITULO = "Ask HN: Who is hiring?"  # "Who wants to be hired?" e "Freelancer?" ficam de fora
_ID = re.compile(r"[0-9]{1,18}")
_ITEM = "https://news.ycombinator.com/item?id={id}"  # só link da vaga, nunca pedido
_MODALIDADES = frozenset({"remote", "onsite", "hybrid", "on-site", "on site"})
_MAX_LINHA = 120


class _FormatoMudou(Exception):
    """Nenhum tópico legível na busca, ou nenhum comentário legível na árvore."""


def _json(texto: str) -> object:
    try:
        return json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro


def _id_do_topico(busca: object) -> str | None:
    """O id do tópico mais novo cujo título começa com `_TITULO`; `None` se a busca veio vazia."""
    hits = busca.get("hits") if isinstance(busca, dict) else None
    if not isinstance(hits, list):
        raise _FormatoMudou
    if not hits:
        return None
    validos: list[tuple[int, str]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        titulo, id_, em = hit.get("title"), hit.get("objectID"), hit.get("created_at_i")
        if (
            isinstance(titulo, str)
            and titulo.startswith(_TITULO)
            and isinstance(id_, str)
            and _ID.fullmatch(id_)
        ):
            validos.append((em if isinstance(em, int) else 0, id_))
    if not validos:
        raise _FormatoMudou  # o título mudou: "falhou" não fecha nada, "ok" vazio fecharia tudo
    return max(validos)[1]


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _empresa_e_cargo(html: str) -> tuple[str, str]:
    """`Empresa | Cargo | Local | ...` da primeira linha; fora do costume, a linha toda.

    shortcut: heurística sem corpus além da captura (apêndice 2.3: "é só costume"); a segunda
    posição só vale se não for rótulo de modalidade. Calibrar na T78, com o gabarito.
    """
    linha = para_texto(re.split(r"<p>", html, maxsplit=1, flags=re.IGNORECASE)[0], "html")
    linha = " ".join(linha.split())
    partes = [p.strip() for p in linha.split("|")]
    empresa = partes[0][:_MAX_LINHA]
    if len(partes) > 1 and partes[1] and partes[1].lower() not in _MODALIDADES:
        return empresa, partes[1][:_MAX_LINHA]
    return empresa, linha[:_MAX_LINHA]


def _vaga(comentario: object) -> VagaColetada | None:
    """Uma vaga da árvore, ou `None` se o comentário não for legível (DR-08)."""
    if not isinstance(comentario, dict):
        return None
    id_, texto = comentario.get("id"), comentario.get("text")
    if not isinstance(id_, int | str) or not _ID.fullmatch(str(id_)) or not isinstance(texto, str):
        return None
    empresa, titulo = _empresa_e_cargo(texto)
    if not empresa:
        return None
    return VagaColetada(
        fonte="hn_algolia",
        escopo="",
        url=_ITEM.format(id=id_),
        titulo=titulo,
        empresa=empresa,
        descricao_formato="html",
        descricao=texto,
        id_externo=str(id_),
        publicada_em=_data_hora(comentario.get("created_at")),
    )


def _ler(texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis e quantos comentários foram pulados (os apagados não contam)."""
    arvore = _json(texto)
    filhos = arvore.get("children") if isinstance(arvore, dict) else None
    if not isinstance(filhos, list):
        raise _FormatoMudou
    # Comentário apagado chega com `text` nulo ou vazio; sem a chave `text`, o formato mudou.
    reais = [f for f in filhos if not (isinstance(f, dict) and "text" in f and not f["text"])]
    vagas = [v for v in map(_vaga, reais) if v is not None]
    if filhos and not vagas:
        raise _FormatoMudou  # todos sem texto: o campo `text` mudou
    return vagas, len(reais) - len(vagas)


class HnAlgolia:
    chave: str = "hn_algolia"
    nome: str = "Hacker News"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("hn.algolia.com",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return [""]  # fonte de lista única

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            busca = await http.pedir(
                "GET",
                f"{_API}/search_by_date",
                params={
                    "query": '"Ask HN: Who is hiring"',
                    "tags": "story,author_whoishiring",
                    "hitsPerPage": "5",
                },
            )
            id_topico = _id_do_topico(_json(busca.texto))
            if id_topico is None:
                yield []  # a busca não achou tópico nenhum: lista vazia, sem segundo pedido
                return
            arvore = await http.pedir("GET", f"{_API}/items/{id_topico}")
            vagas, pulados = _ler(arvore.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: sem contagem no motivo, como o Greenhouse (D45, opção b); trocar com ela.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A árvore já traz o texto inteiro: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Fonte sem identificador por empresa: nunca é chamada por cadastro."""
        raise ValueError(f"hn_algolia não tem identificador: {identificador!r}")


COLETOR = HnAlgolia()
