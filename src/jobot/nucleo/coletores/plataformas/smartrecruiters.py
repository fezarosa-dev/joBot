"""Coletor SmartRecruiters (apêndice 2.4): API pública de vagas, um escopo por empresa e país.

O escopo é `<identificador>|<país>` (país ISO em minúsculas, do `ctx.paises`). A lista não traz
descrição: o `detalhar` busca `jobAd.sections` de cada vaga. A caixa do identificador é preservada.
"""

import html
import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Literal
from urllib.parse import quote, urlsplit

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

_LIMITES = limites("smartrecruiters")
_API = "https://api.smartrecruiters.com/v1/companies/{empresa}/postings"
_VAGA = "https://jobs.smartrecruiters.com/{empresa}/{id}"
_POR_PAGINA = 100  # máximo da API
MAX_PAGINAS = 200  # trava contra `totalFound` mentiroso: 20 mil vagas num escopo já é anomalia
_IDENTIFICADOR = re.compile(r"[A-Za-z0-9_-]{1,100}")
_ID_VAGA = re.compile(r"[A-Za-z0-9_-]{1,100}")
_PAIS = re.compile(r"[a-z]{2}")
_HOSTS_VAGAS = frozenset({"jobs.smartrecruiters.com", "careers.smartrecruiters.com"})
_HOST_API = "api.smartrecruiters.com"
# Primeiro segmento que não é identificador de empresa nos endereços de vagas.
_RESERVADOS = frozenset(
    {"oneclick-ui", "external-referrals", "search", "jobs", "company", "companies", "v1", "api"}
)
_SECOES = ("companyDescription", "jobDescription", "qualifications", "additionalInformation")


class _FormatoMudou(Exception):
    """A resposta não traz `content` como lista, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _rotulo(valor: object) -> str:
    return _texto(valor.get("label")) if isinstance(valor, dict) else ""


def _local(valor: object) -> tuple[tuple[str, ...], str | None]:
    """Locais e modalidade declarada (`remote`, `hybrid`) de `location`."""
    if not isinstance(valor, dict):
        return (), None
    completo = _texto(valor.get("fullLocation"))
    partes = [_texto(valor.get(c)) for c in ("city", "region", "country")]
    nome = completo or ", ".join(p for p in partes if p)
    modalidade = (
        "remote"
        if valor.get("remote") is True
        else "hybrid"
        if valor.get("hybrid") is True
        else None
    )
    return ((nome,) if nome else ()), modalidade


def _vaga(escopo: str, empresa_id: str, item: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(item, dict):
        return None
    titulo = _texto(item.get("name"))
    empresa = _texto(item["company"].get("name")) if isinstance(item.get("company"), dict) else ""
    bruto = item.get("id")
    id_vaga = str(bruto) if isinstance(bruto, int | str) and not isinstance(bruto, bool) else ""
    if not titulo or not empresa or not _ID_VAGA.fullmatch(id_vaga):
        return None
    locais, modalidade = _local(item.get("location"))
    try:
        return VagaColetada(
            fonte="smartrecruiters",
            escopo=escopo,
            url=_VAGA.format(empresa=quote(empresa_id, safe=""), id=id_vaga),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            id_externo=id_vaga,
            locais=locais,
            modalidade_declarada=modalidade,
            publicada_em=_data_hora(item.get("releasedDate")),
            etiquetas=tuple(
                r for r in (_rotulo(item.get("department")), _rotulo(item.get("function"))) if r
            ),
        )
    except ValueError:  # url fora de http/https
        return None


def _separar(escopo: str) -> tuple[str, str | None]:
    """`<identificador>|<país>` em duas partes; sem `|`, sem filtro de país."""
    empresa, barra, pais = escopo.rpartition("|")
    return (empresa, pais) if barra else (escopo, None)


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, int, int]:
    """As vagas legíveis, quantas foram puladas, quantos itens vieram e o `totalFound`."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    itens = dados.get("content") if isinstance(dados, dict) else None
    total = dados.get("totalFound") if isinstance(dados, dict) else None
    if not isinstance(itens, list) or not isinstance(total, int) or isinstance(total, bool):
        raise _FormatoMudou
    empresa_id, _ = _separar(escopo)
    vagas = [v for v in (_vaga(escopo, empresa_id, i) for i in itens) if v is not None]
    if itens and not vagas:
        raise _FormatoMudou
    return vagas, len(itens) - len(vagas), len(itens), total


class SmartRecruiters:
    chave: str = "smartrecruiters"
    nome: str = "SmartRecruiters"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (_HOST_API,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        """Uma empresa por país das buscas ativas (DR-53); sem país válido, nada a pedir."""
        paises = dict.fromkeys(
            p for p in (p.strip().lower() for p in ctx.paises) if _PAIS.fullmatch(p)
        )
        empresas = dict.fromkeys(e.identificador for e in ctx.empresas)
        return [f"{e}|{p}" for e in empresas for p in paises]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = 0
        truncou = False
        empresa_id, pais = _separar(escopo)
        url = _API.format(empresa=quote(empresa_id, safe=""))

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, truncou
            offset = 0
            for _ in range(MAX_PAGINAS):
                params = {"limit": str(_POR_PAGINA), "offset": str(offset)}
                if pais:
                    params["country"] = pais
                resposta = await http.pedir("GET", url, params=params, condicional=True)
                if resposta.status == 304:
                    # shortcut: 304 na página encerra o escopo; com mais de uma página, vaga que
                    # some das seguintes só fecha quando esta mudar; trocar se passar de 100.
                    yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                    return
                vagas, n_pulados, n_itens, total = _ler(escopo, resposta.texto)
                pulados += n_pulados
                yield vagas
                offset += n_itens
                if n_itens < _POR_PAGINA or offset >= total:
                    return
            truncou = True

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if truncou and resultado.estado == "ok":  # lista incompleta: só fecha o que tem 30+ dias
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.limite_atingido", resultado.pedidos
            )
        if pulados and resultado.estado == "ok":
            # shortcut: sem a contagem de pulados no motivo (D45, opção b); trocar com a D45.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """Completa a vaga da lista com `jobAd.sections`; `None` se não houver o que acrescentar.

        A `url` e os demais campos da lista ficam como estão (a URL é a chave da vaga). O criador
        do anúncio (`creator`) não é lido.
        """
        if not isinstance(item, VagaColetada) or not item.id_externo:
            return None
        empresa_id, _ = _separar(item.escopo)
        url = (
            _API.format(empresa=quote(empresa_id, safe="")) + f"/{quote(item.id_externo, safe='')}"
        )
        try:
            resposta = await http.pedir("GET", url)
        except ErroDeRede as erro:
            if erro.status == 404:  # a vaga fechou entre a lista e o detalhe
                return None
            raise
        try:
            dados = json.loads(resposta.texto)
        except ValueError:
            return None
        anuncio = dados.get("jobAd") if isinstance(dados, dict) else None
        secoes = anuncio.get("sections") if isinstance(anuncio, dict) else None
        if not isinstance(secoes, dict):
            return None
        blocos = []
        for nome in _SECOES:
            secao = secoes.get(nome)
            texto = _texto(secao.get("text")) if isinstance(secao, dict) else ""
            if texto:
                titulo = _texto(secao.get("title")) if isinstance(secao, dict) else ""
                blocos.append((f"<h2>{html.escape(titulo)}</h2>\n" if titulo else "") + texto)
        if not blocos:
            return None
        return replace(item, descricao="\n".join(blocos), descricao_formato="html")

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o identificador ou o endereço da empresa e devolve o identificador; sem pedido.

        `ValueError` se não for uma empresa do SmartRecruiters. A caixa fica como veio.
        """
        texto = identificador.strip()
        token = texto
        if "/" in texto or "." in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            caminho = [p for p in partes.path.split("/") if p]
            host = (partes.hostname or "").lower()
            if partes.scheme not in ("http", "https"):
                raise ValueError(f"endereço não é http/https: {identificador!r}")
            primeiro = caminho[:1]
            if (
                host in _HOSTS_VAGAS
                and primeiro
                and primeiro[0] in ("oneclick-ui", "external-referrals")
            ):
                # famílias `<prefixo>/company/<empresa>/...`
                token = caminho[2] if len(caminho) > 2 and caminho[1] == "company" else ""
            elif host in _HOSTS_VAGAS and primeiro and primeiro[0] not in _RESERVADOS:
                token = caminho[0]
            elif host == _HOST_API and caminho[:2] == ["v1", "companies"] and len(caminho) > 2:
                token = caminho[2]
            else:
                raise ValueError(f"não é uma empresa do SmartRecruiters: {identificador!r}")
        if not _IDENTIFICADOR.fullmatch(token):
            raise ValueError(f"identificador inválido: {identificador!r}")
        return {"identificador": token}


COLETOR = SmartRecruiters()
