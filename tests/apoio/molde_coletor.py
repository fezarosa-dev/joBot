"""Molde do coletor público: busca por termo, resposta JSON, paginada por número de página.

Ponto de partida para uma fonte nova (guia `docs/site-novo.md`). Mora em `tests/apoio` para não
virar fonte: o `descobrir()` não o acha. Na cópia, cada linha com `# MUDE:` muda.

Resposta que o molde espera: `{"vagas": [{...}, ...], "proxima": true|false}`.
"""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Literal

from jobot.nucleo.coletores.base import (
    SEM_MUDANCA,
    ContextoColeta,
    Estado,
    Item,
    LimiteEscopo,
    LimitesDaFonte,
    ResultadoEscopo,
    juntar_paginas,  # pelo nome: o `test_304` espia esta função no módulo
)
from jobot.nucleo.http import HttpEducado
from jobot.nucleo.modelo import VagaColetada

CHAVE = "molde_coletor"  # MUDE: a chave da fonte, igual à linha de `fontes.json`
NOME = "Molde"  # MUDE: o nome que o painel mostra
_HOST = "vagas.exemplo.invalid"  # MUDE: o host da API do site
_API = f"https://{_HOST}/api/vagas"  # MUDE: o endereço da busca
_POR_PAGINA = 20  # MUDE: quantas vagas o site entrega por página
_MAX_PAGINAS = 5  # MUDE: o teto de páginas por termo

# MUDE: na cópia, `limites(CHAVE)` (de `jobot.nucleo.coletores.registro`); o molde não está
# em `fontes.json`.
_LIMITES = LimitesDaFonte()


class _FormatoMudou(Exception):
    """A resposta não é JSON, não traz a lista, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _vaga(escopo: str, item: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar título, empresa ou URL http(s)."""
    if not isinstance(item, dict):
        return None
    titulo, empresa = _texto(item.get("titulo")), _texto(item.get("empresa"))  # MUDE: campos
    if not titulo or not empresa:
        return None
    try:
        return VagaColetada(
            fonte=CHAVE,
            escopo=escopo,
            url=_texto(item.get("url")),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",  # MUDE: "texto" se a descrição vier sem HTML
            descricao=_texto(item.get("descricao")),
            id_externo=str(item["id"]) if isinstance(item.get("id"), int | str) else None,
            locais=tuple(filter(None, [_texto(item.get("local"))])),
            publicada_em=_data_hora(item.get("publicada_em")),
        )
    except ValueError:  # url fora de http/https
        return None


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, bool]:
    """As vagas legíveis, quantas foram puladas e se há próxima página."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    itens = dados.get("vagas") if isinstance(dados, dict) else None  # MUDE: o nome da lista
    proxima = dados.get("proxima") if isinstance(dados, dict) else None  # MUDE: o campo
    if not isinstance(itens, list) or not isinstance(proxima, bool):
        raise _FormatoMudou
    vagas = [v for v in (_vaga(escopo, i) for i in itens) if v is not None]
    if itens and not vagas:
        raise _FormatoMudou
    return vagas, len(itens) - len(vagas), proxima


class Molde:
    chave: str = CHAVE
    nome: str = NOME
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (_HOST,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        """Um escopo por termo da pessoa, sem espaço nas bordas, sem vazio e sem repetido."""
        return list(dict.fromkeys(t for t in (t.strip() for t in ctx.termos) if t))

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = 0
        parada: tuple[Estado, str] | None = None

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, parada
            for n in range(1, _MAX_PAGINAS + 1):
                params = {"q": escopo, "pagina": str(n), "por_pagina": str(_POR_PAGINA)}
                resposta = await http.pedir("GET", _API, params=params, condicional=True)
                if resposta.status == 304:
                    yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                    return  # o 304 não diz se há próxima
                try:
                    vagas, ruins, proxima = _ler(escopo, resposta.texto)
                except _FormatoMudou:
                    if n == 1:
                        raise
                    parada = ("parcial", "saude.formato_mudou")  # as páginas lidas ficam
                    return
                pulados += ruins
                yield vagas
                if not proxima:
                    return
            # shortcut: o teto é fixo por termo; passar dele vira "parcial". Subir `_MAX_PAGINAS`
            # se um termo comum passar dele na rede.
            parada = ("parcial", "saude.limite_atingido")

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if resultado.estado != "ok":
            return resultado
        if parada is not None:
            return ResultadoEscopo(resultado.vagas, *parada, resultado.pedidos)
        if pulados:
            # shortcut: a contagem de pulados não vai no motivo (D45, como no Greenhouse).
            # Trocar quando a chave com `n` existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar.

        MUDE: se a lista do site vier sem descrição, busque aqui a página da vaga.
        """
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Fonte por termo, não por empresa: não há identificador para resolver."""
        raise ValueError(f"{NOME} não tem identificador de empresa: {identificador!r}")


COLETOR = Molde()
