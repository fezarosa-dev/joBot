"""Coletor Lever (apêndice 2.4): API pública de vagas, um escopo por empresa.

A lista inteira vem numa resposta (sem `skip` nem `limit`), com a descrição: não há
paginação nem `detalhar`. A API não traz o nome da empresa: ele vem do cadastro.
"""

import html
import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
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
from jobot.nucleo.modelo import Periodo, SalarioBruto, VagaColetada, confere_http

_LIMITES = limites("lever")
_API = "https://api.lever.co/v0/postings/{site}"
_SITE = re.compile(r"[A-Za-z0-9_-]{1,100}")
# Hosts dos endereços que a pessoa cola; o europeu fica de fora (não testado, apêndice 2.4).
_HOST_VAGAS = "jobs.lever.co"
_HOST_API = "api.lever.co"
_EPOCA = datetime(1970, 1, 1, tzinfo=UTC)
# O texto do `interval` da API é "per-<período>-salary" ou "per-<período>-wage".
_PERIODOS: tuple[tuple[str, Periodo], ...] = (
    ("hour", "hora"),
    ("day", "dia"),
    ("week", "semana"),
    ("month", "mes"),
    ("year", "ano"),
)


class _NaoEncontrado(Exception):
    """404: o site não existe (decisão 3: chega como `ErroDeRede` com status 404)."""


class _FormatoMudou(Exception):
    """A resposta não é uma lista, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _http(valor: object) -> str | None:
    """O endereço como veio, se for http(s); senão `None` (nunca reescreve)."""
    if not isinstance(valor, str):
        return None
    try:
        confere_http(valor, "url")
    except ValueError:
        return None
    return valor


def _publicada(valor: object) -> datetime | None:
    """`createdAt` é epoch em milissegundos."""
    if not isinstance(valor, int) or isinstance(valor, bool):
        return None
    try:
        return _EPOCA + timedelta(milliseconds=valor)
    except OverflowError:
        return None


def _numero(valor: object) -> int | float | None:
    return valor if isinstance(valor, int | float) and not isinstance(valor, bool) else None


def _salario(faixa: object) -> SalarioBruto | None:
    if not isinstance(faixa, dict):
        return None
    minimo, maximo = _numero(faixa.get("min")), _numero(faixa.get("max"))
    if minimo is None and maximo is None:
        return None
    intervalo = _texto(faixa.get("interval")).lower()
    return SalarioBruto(
        moeda=_texto(faixa.get("currency")) or None,
        minimo_unidades=minimo,
        maximo_unidades=maximo,
        periodo=next((p for chave, p in _PERIODOS if f"-{chave}-" in intervalo), None),
    )


def _descricao(job: dict[str, object]) -> str:
    """Corpo, listas (título e itens) e o texto adicional, em HTML."""
    corpo = _texto(job.get("description")) or (
        _texto(job.get("opening")) + _texto(job.get("descriptionBody"))
    )
    listas = job.get("lists")
    partes = [corpo]
    for lista in listas if isinstance(listas, list) else []:
        if isinstance(lista, dict) and (itens := _texto(lista.get("content"))):
            titulo = html.escape(_texto(lista.get("text")))
            partes.append(f"<h3>{titulo}</h3><ul>{itens}</ul>" if titulo else f"<ul>{itens}</ul>")
    partes.append(_texto(job.get("additional")))
    return "".join(partes)


def _vaga(escopo: str, empresa: str, job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    titulo, url = _texto(job.get("text")), _http(job.get("hostedUrl"))
    if not titulo or url is None:
        return None
    categorias = job.get("categories")
    categorias = categorias if isinstance(categorias, dict) else {}
    todos = categorias.get("allLocations")
    locais = [_texto(c) for c in todos] if isinstance(todos, list) else []
    locais = locais or [_texto(categorias.get("location"))]
    modalidade = job.get("workplaceType")
    return VagaColetada(
        fonte="lever",
        escopo=escopo,
        url=url,
        titulo=titulo,
        empresa=empresa,
        descricao_formato="html",
        descricao=_descricao(job),
        id_externo=str(job["id"]) if isinstance(job.get("id"), int | str) else None,
        url_candidatura=_http(job.get("applyUrl")),
        locais=tuple(dict.fromkeys(filter(None, locais))),
        modalidade_declarada=_texto(modalidade) or None,
        contrato_declarado=_texto(categorias.get("commitment")) or None,
        salario_estruturado=_salario(job.get("salaryRange")),
        publicada_em=_publicada(job.get("createdAt")),
        etiquetas=tuple(
            dict.fromkeys(
                filter(None, (_texto(categorias.get("department")), _texto(categorias.get("team"))))
            )
        ),
    )


def _ler(escopo: str, empresa: str, texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis e quantas foram puladas."""
    try:
        jobs = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    if not isinstance(jobs, list):
        raise _FormatoMudou
    vagas = [v for v in (_vaga(escopo, empresa, j) for j in jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    return vagas, len(jobs) - len(vagas)


class Lever:
    chave: str = "lever"
    nome: str = "Lever"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (_HOST_API,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def __init__(self) -> None:
        # shortcut: `coletar(escopo, http)` não recebe o cadastro; os nomes ficam aqui, guardados
        # por `escopos`. Sem passar por `escopos`, o identificador serve de nome. Trocar se o
        # contrato do coletor passar a entregar a empresa (R4, ver duvidas da T28).
        self._nomes: dict[str, str] = {}

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        nomes: dict[str, str] = {}
        for e in ctx.empresas:
            nomes.setdefault(e.identificador, e.nome)  # duplicata na chamada: o primeiro vale
        self._nomes = nomes  # a cada chamada, o cadastro atual substitui o anterior
        return list(dict.fromkeys(e.identificador for e in ctx.empresas))

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = 0
        empresa = self._nomes.get(escopo) or escopo

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            url = _API.format(site=quote(escopo, safe=""))
            try:
                resposta = await http.pedir("GET", url, params={"mode": "json"}, condicional=True)
            except ErroDeRede as erro:
                if erro.status == 404:
                    raise _NaoEncontrado from erro
                raise
            if resposta.status == 304:
                yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                return
            vagas, pulados = _ler(escopo, empresa, resposta.texto)
            yield vagas

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
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (não há chave `saude.*` com `n`
            # para isso; D45). Trocar quando a chave existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o site ou o endereço da vaga e devolve o site; não faz pedido.

        `ValueError` se não for um site do Lever (host europeu incluído: não testado).
        """
        texto = identificador.strip()
        site = texto
        if "/" in texto or "." in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            caminho = [p for p in partes.path.split("/") if p]
            host = (partes.hostname or "").lower()
            if partes.scheme not in ("http", "https"):
                raise ValueError(f"endereço não é http/https: {identificador!r}")
            if host == _HOST_VAGAS and caminho:
                site = caminho[0]
            elif host == _HOST_API and caminho[:2] == ["v0", "postings"] and len(caminho) > 2:
                site = caminho[2]
            else:
                raise ValueError(f"não é um site do Lever: {identificador!r}")
        if not _SITE.fullmatch(site):
            raise ValueError(f"identificador inválido: {identificador!r}")
        return {"identificador": site}


COLETOR = Lever()
