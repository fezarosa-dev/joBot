"""Coletor InHire (apêndice 3.1): API pública do portal de vagas, um escopo por empresa (tenant).

O tenant é o subdomínio de `<tenant>.inhire.app` e vai no cabeçalho `X-Tenant`. A lista vem inteira
numa resposta (`jobsPage`, sem paginação) e não traz descrição nem data: o `detalhar` busca as duas
em `/pages/<jobId>`. O nome da empresa vem de `tenantName`, na raiz da resposta.
"""

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Literal
from urllib.parse import quote, urlsplit

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import ErroDeRede, HttpEducado
from jobot.nucleo.modelo import VagaColetada

_LIMITES = limites("inhire")
_HOST_API = "api.inhire.app"
_API = f"https://{_HOST_API}/job-posts/public/pages"
# O link usa o tenant como subdomínio: só rótulo de DNS (a captura não abriu o link; a rota
# `/vagas/:jobId` vem do código do site).
_VAGA = "https://{tenant}.inhire.app/vagas/{id}"
_DOMINIO = ".inhire.app"
_TENANT = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_ID_VAGA = re.compile(r"[A-Za-z0-9_-]{1,100}")
_RESERVADOS = frozenset({"api", "www", "embed", "files"})  # subdomínios do site, sem vagas


class _NaoEncontrado(Exception):
    """404: o tenant não existe (chega como `ErroDeRede` com status 404)."""


class _FormatoMudou(Exception):
    """A resposta não traz a lista `jobsPage`, ou nenhum item dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _contrato(valor: object) -> str | None:
    """`contractType` vem como lista (`["CLT"]`); aceita também um texto só."""
    partes = valor if isinstance(valor, list) else [valor]
    return ", ".join(t for t in (_texto(p) for p in partes) if t) or None


def _vaga(escopo: str, empresa: str, job: object) -> VagaColetada | None:
    """A vaga da lista, ou `None` se faltar campo obrigatório ou o id não servir de caminho."""
    if not isinstance(job, dict):
        return None
    bruto = job.get("jobId")
    id_vaga = str(bruto) if isinstance(bruto, int | str) and not isinstance(bruto, bool) else ""
    titulo = _texto(job.get("displayName"))
    if not titulo or not _ID_VAGA.fullmatch(id_vaga):
        return None
    local = _texto(job.get("location"))
    try:
        return VagaColetada(
            fonte="inhire",
            escopo=escopo,
            url=_VAGA.format(tenant=escopo, id=id_vaga),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            id_externo=id_vaga,
            locais=(local,) if local else (),
            modalidade_declarada=_texto(job.get("workplaceType")) or None,
            contrato_declarado=_contrato(job.get("contractType")),
        )
    except ValueError:  # url fora de http/https
        return None


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis e quantos itens foram pulados."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    jobs = dados.get("jobsPage") if isinstance(dados, dict) else None
    if not isinstance(jobs, list):
        raise _FormatoMudou
    # shortcut: sem `tenantName` a empresa é o identificador; o cadastro não é consultado.
    empresa = _texto(dados.get("tenantName")) or escopo
    vagas = [v for v in (_vaga(escopo, empresa, j) for j in jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    return vagas, len(jobs) - len(vagas)


class InHire:
    chave: str = "inhire"
    nome: str = "InHire"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (_HOST_API,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return list(dict.fromkeys(e.identificador for e in ctx.empresas))

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
        if not _TENANT.fullmatch(escopo):  # vira host do link e cabeçalho: nada de pedido
            return ResultadoEscopo((), "falhou", "saude.empresa_nao_encontrada", pedidos)
        pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            # sem `condicional`: a resposta não traz ETag nem Last-Modified
            try:
                resposta = await http.pedir("GET", _API, cabecalhos={"X-Tenant": escopo})
            except ErroDeRede as erro:
                if erro.status == 404:
                    raise _NaoEncontrado from erro
                raise
            vagas, pulados = _ler(escopo, resposta.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except (_NaoEncontrado, _FormatoMudou) as erro:
            motivo = (
                "saude.empresa_nao_encontrada"
                if isinstance(erro, _NaoEncontrado)
                else "saude.formato_mudou"
            )
            return ResultadoEscopo((), "falhou", motivo, getattr(http, "pedidos", 0))
        if pulados and resultado.estado == "ok":
            # shortcut: sem a contagem de pulados no motivo (D45, opção provisória como no Ashby).
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """Completa a vaga da lista com descrição, data e contrato de `/pages/<jobId>`.

        `None` se o item não for da lista, a vaga sumiu (404) ou o detalhe vier sem descrição.
        A `url` e os demais campos da lista ficam como estão (a URL é a chave da vaga).
        """
        if (
            not isinstance(item, VagaColetada)
            or not _TENANT.fullmatch(item.escopo)
            or not _ID_VAGA.fullmatch(item.id_externo or "")
        ):
            return None
        url = f"{_API}/{quote(item.id_externo or '', safe='')}"
        try:
            resposta = await http.pedir("GET", url, cabecalhos={"X-Tenant": item.escopo})
        except ErroDeRede as erro:
            if erro.status == 404:  # a vaga fechou entre a lista e o detalhe
                return None
            raise
        try:
            dados = json.loads(resposta.texto)
        except ValueError:
            return None
        descricao = _texto(dados.get("description")) if isinstance(dados, dict) else ""
        if not descricao:
            return None
        return replace(
            item,
            descricao=descricao,
            descricao_formato="html",
            publicada_em=_data_hora(dados.get("publishedAt")) or item.publicada_em,
            contrato_declarado=_contrato(dados.get("contractType")) or item.contrato_declarado,
        )

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o tenant ou o endereço do portal e devolve o tenant em minúsculas; sem pedido.

        `ValueError` se não for um portal `<tenant>.inhire.app`. O subdomínio não tem caixa, então
        a caixa se normaliza aqui (D45).
        """
        texto = identificador.strip()
        tenant = texto.lower()
        if "/" in texto or "." in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            host = partes.hostname or ""
            if partes.scheme not in ("http", "https") or partes.username or partes.password:
                raise ValueError(f"endereço não é http/https sem usuário: {identificador!r}")
            if not host.endswith(_DOMINIO) or host.removesuffix(_DOMINIO) in _RESERVADOS:
                raise ValueError(f"não é um portal do InHire: {identificador!r}")
            tenant = host.removesuffix(_DOMINIO)
        if not _TENANT.fullmatch(tenant):
            raise ValueError(f"identificador inválido: {identificador!r}")
        return {"identificador": tenant}


COLETOR = InHire()
