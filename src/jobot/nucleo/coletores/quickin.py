"""Coletor Quickin (apêndice 3.1): API pública do site de carreiras, um escopo por empresa.

O escopo é uma string que se basta: `<account_id>:<nome>`, com o `account_id` (24 hex) que a API
exige no caminho e o nome do cadastro, que vale quando a vaga não traz o cliente (`company_id`).
A lista já traz a descrição: não há `detalhar`. O `account_id` não está no slug: o `resolver` lê
do `__NUXT_DATA__` da página da empresa, como texto.
"""

import json
import math
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
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
from jobot.nucleo.modelo import Periodo, SalarioBruto, VagaColetada

_LIMITES = limites("quickin")
_API = "https://api.quickin.io/public/{conta}/jobs"
_PAGINA = "https://jobs.quickin.io/{slug}/jobs"
_HOST_SITE = "jobs.quickin.io"
# shortcut: teto local de páginas (3.000 vagas por conta), mesmo que a API mande `pages` maior;
# rever se uma conta passar disso.
_MAX_PAGINAS = 100
_LIMIT = 30  # tamanho de página da API; vale o `limit` da resposta quando ela traz
_CONTA = re.compile(r"[0-9a-f]{24}")
_SLUG = re.compile(r"[A-Za-z0-9_-]{1,100}")
_NUXT_DATA = re.compile(
    r"""<script[^>]*\bid=["']__NUXT_DATA__["'][^>]*>(.*?)</script>""", re.DOTALL | re.IGNORECASE
)
_PERIODOS: Mapping[str, Periodo] = {
    "hour": "hora",
    "day": "dia",
    "week": "semana",
    "month": "mes",
    "year": "ano",
}


class _NaoEncontrado(Exception):
    """400/404: a conta não existe (a API responde 400 a um `account_id` inválido)."""


class _FormatoMudou(Exception):
    """A resposta não traz a lista `docs`, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _nome(valor: object) -> str:
    """O `name` de um objeto aninhado (`company_id`, `contract_id`), ou vazio."""
    return _texto(valor.get("name")) if isinstance(valor, dict) else ""


def _salario(doc: Mapping[str, object]) -> SalarioBruto | None:
    valor = doc.get("remuneration")
    if not isinstance(valor, int | float) or isinstance(valor, bool):
        return None
    try:
        if not math.isfinite(valor) or valor <= 0:
            return None
    except OverflowError:  # inteiro maior que um float
        return None
    moeda = _texto(doc.get("currency")) or None
    periodo = _PERIODOS.get(_texto(doc.get("remuneration_period")))
    return SalarioBruto(moeda=moeda, minimo_unidades=valor, maximo_unidades=valor, periodo=periodo)


def _vaga(escopo: str, empresa: str, doc: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(doc, dict):
        return None
    titulo, url = _texto(doc.get("title")), _texto(doc.get("career_url"))
    if not titulo or not url:
        return None
    local = ", ".join(filter(None, (_texto(doc.get(c)) for c in ("city", "region", "country"))))
    texto = "\n".join(
        filter(None, (_texto(doc.get(c)) for c in ("description", "requirements", "benefits")))
    )
    id_ = doc.get("_id")
    try:
        return VagaColetada(
            fonte="quickin",
            escopo=escopo,
            url=url,
            titulo=titulo,
            empresa=_nome(doc.get("company_id")) or empresa,
            descricao_formato="html",
            descricao=texto,
            id_externo=id_ if isinstance(id_, str) and id_ else None,
            locais=(local,) if local else (),
            modalidade_declarada=_texto(doc.get("workplace_type")) or None,
            contrato_declarado=_nome(doc.get("contract_id")) or None,
            salario_estruturado=_salario(doc),
            publicada_em=_data_hora(doc.get("created_at")),
            etiquetas=tuple(filter(None, [_texto(doc.get("position_category"))])),
        )
    except ValueError:  # url fora de http/https
        return None


def _inteiro_positivo(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0 else None


def _ler(
    escopo: str, empresa: str, texto: str
) -> tuple[list[VagaColetada], int, int, int, int | None]:
    """(vagas, puladas por formato, itens na página, limit da resposta, pages da resposta)."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    itens = dados.get("docs") if isinstance(dados, dict) else None
    if not isinstance(itens, list):
        raise _FormatoMudou
    vagas = [v for v in (_vaga(escopo, empresa, d) for d in itens) if v is not None]
    if itens and not vagas:
        raise _FormatoMudou
    return (
        vagas,
        len(itens) - len(vagas),
        len(itens),
        _inteiro_positivo(dados.get("limit")) or _LIMIT,
        _inteiro_positivo(dados.get("pages")),
    )


def _escopo(escopo: str) -> tuple[str, str]:
    """(account_id, nome da empresa); `ValueError` se não for nosso."""
    conta, _, nome = escopo.partition(":")
    if not _CONTA.fullmatch(conta) or not nome.strip():
        raise ValueError(f"escopo inválido: {escopo!r}")
    return conta, nome.strip()


class Quickin:
    chave: str = "quickin"
    nome: str = "Quickin"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("api.quickin.io",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        # sem `account_id` válido a empresa fica de fora: o slug no lugar dele dá 400 na API
        contas: dict[str, str] = {}
        for e in ctx.empresas:
            conta = _texto(e.parametros.get("account_id"))
            if _CONTA.fullmatch(conta):
                contas.setdefault(conta, f"{conta}:{e.nome.strip() or e.identificador}")
        return list(contas.values())

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        conta, empresa = _escopo(escopo)
        url = _API.format(conta=conta)
        incompleto = False
        parada: tuple[Literal["parcial"], str] | None = None

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal incompleto, parada
            for n in range(1, _MAX_PAGINAS + 1):
                params = {"sort": "-created_at", "page": str(n)}
                try:
                    # shortcut: só a primeira página leva pedido condicional; o 304 dela vale pela
                    # lista toda (304 não diz quantas páginas há). Mudança só nas páginas seguintes
                    # aparece quando a primeira mudar.
                    resposta = await http.pedir("GET", url, params=params, condicional=n == 1)
                except ErroDeRede as erro:
                    if n == 1 and erro.status in (400, 404):
                        raise _NaoEncontrado from erro
                    raise
                if resposta.status == 304:
                    yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                    return
                try:
                    vagas, ruins, itens, limit, total = _ler(escopo, empresa, resposta.texto)
                except _FormatoMudou:
                    if n == 1:
                        raise
                    incompleto = True  # as páginas já lidas valem
                    return
                incompleto |= bool(ruins)
                yield vagas
                if itens < limit or (total is not None and n >= total):
                    return
            parada = ("parcial", "saude.limite_atingido")

        try:
            resultado = await juntar_paginas(http, paginas())
        except (_NaoEncontrado, _FormatoMudou) as erro:
            motivo = (
                "saude.empresa_nao_encontrada"
                if isinstance(erro, _NaoEncontrado)
                else "saude.formato_mudou"
            )
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", motivo, pedidos)
        if parada is not None and resultado.estado == "ok":
            return ResultadoEscopo(resultado.vagas, *parada, resultado.pedidos)
        if incompleto and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (D45, como na Gupy).
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o slug ou o endereço de uma página da empresa; faz um pedido à página.

        Devolve o slug que a página declara e o `account_id` (24 hex) lido do `__NUXT_DATA__`
        como texto, sem executar nada. `ValueError` se não for uma página de empresa do Quickin
        ou se a página não trouxer um `account_id` válido para esse slug.
        """
        texto = identificador.strip()
        slug = texto
        if "/" in texto or "." in texto or ":" in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            if partes.scheme not in ("http", "https") or partes.hostname != _HOST_SITE:
                raise ValueError(f"não é uma página do Quickin: {identificador!r}")
            slug = next(iter(partes.path.split("/")[1:2]), "")
        if not _SLUG.fullmatch(slug):
            raise ValueError(f"identificador inválido: {identificador!r}")
        try:
            pagina = await http.pedir("GET", _PAGINA.format(slug=slug))
        except ErroDeRede as erro:
            if erro.status == 404:
                raise ValueError(f"o Quickin não tem a página {slug}") from erro
            raise
        return {"identificador": slug.lower(), "account_id": _account_id(pagina.texto, slug)}


def _account_id(html: str, slug: str) -> str:
    """O `account_id` do objeto do site (o que tem `slug` e `account_id`) no `__NUXT_DATA__`.

    Formato devalue: lista JSON em que cada objeto aponta por índice para seus valores.
    """
    achado = _NUXT_DATA.search(html)
    if achado is None:
        raise ValueError(f"a página de {slug} não traz __NUXT_DATA__")
    try:
        lista = json.loads(achado.group(1))
    except ValueError as erro:
        raise ValueError(f"o __NUXT_DATA__ de {slug} não é JSON") from erro
    if not isinstance(lista, list):
        raise ValueError(f"o __NUXT_DATA__ de {slug} não é uma lista")

    def valor(objeto: dict[str, object], chave: str) -> object:
        i = objeto.get(chave)
        if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(lista):
            return lista[i]
        return None

    for objeto in lista:
        if isinstance(objeto, dict) and _texto(valor(objeto, "slug")).lower() == slug.lower():
            conta = valor(objeto, "account_id")
            if isinstance(conta, str) and _CONTA.fullmatch(conta):
                return conta
    raise ValueError(f"a página de {slug} não traz account_id válido")


COLETOR = Quickin()
