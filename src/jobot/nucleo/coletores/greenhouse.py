"""Coletor Greenhouse (apêndice 2.4): API pública do quadro, um escopo por empresa.

A lista inteira vem numa resposta, com a descrição: não há paginação nem `detalhar`.
"""

import html
import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import date, datetime
from typing import Literal
from urllib.parse import parse_qs, quote, urlsplit

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

_LIMITES = limites("greenhouse")
_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,100}")
# Hosts dos endereços que a pessoa cola; o europeu fica de fora (não testado, apêndice 2.4).
_HOSTS_BOARD = frozenset({"boards.greenhouse.io", "job-boards.greenhouse.io"})
_HOST_API = "boards-api.greenhouse.io"


class _NaoEncontrado(Exception):
    """404: o quadro não existe (decisão 3: chega como `ErroDeRede` com status 404)."""


class _FormatoMudou(Exception):
    """A resposta não traz a lista `jobs`, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _data(valor: object) -> date | None:
    # shortcut: o formato de `application_deadline` não apareceu em nenhuma captura; vale o dia
    # escrito na fonte (ISO 8601, data ou data e hora). Trocar quando a captura mostrar o campo.
    try:
        return datetime.fromisoformat(valor).date() if isinstance(valor, str) else None
    except ValueError:
        return None


def _vaga(escopo: str, job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    titulo, empresa = _texto(job.get("title")), _texto(job.get("company_name"))
    if not titulo or not empresa:
        return None
    local = job.get("location")
    departamentos = job.get("departments")
    try:
        return VagaColetada(
            fonte="greenhouse",
            escopo=escopo,
            url=_texto(job.get("absolute_url")),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html",
            descricao=html.unescape(_texto(job.get("content"))),  # vem escapado em entidades
            id_externo=str(job["id"]) if isinstance(job.get("id"), int | str) else None,
            locais=tuple(filter(None, [_texto(local.get("name"))]))
            if isinstance(local, dict)
            else (),
            publicada_em=_data_hora(job.get("first_published")),
            prazo=_data(job.get("application_deadline")),
            etiquetas=tuple(
                n
                for d in (departamentos if isinstance(departamentos, list) else [])
                if isinstance(d, dict) and (n := _texto(d.get("name")))
            ),
        )
    except ValueError:  # url fora de http/https
        return None


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas legíveis e quantas foram puladas."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    jobs = dados.get("jobs") if isinstance(dados, dict) else None
    if not isinstance(jobs, list):
        raise _FormatoMudou
    vagas = [v for v in (_vaga(escopo, j) for j in jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    return vagas, len(jobs) - len(vagas)


class Greenhouse:
    chave: str = "greenhouse"
    nome: str = "Greenhouse"
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
        pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            url = _API.format(token=quote(escopo, safe=""))
            try:
                resposta = await http.pedir(
                    "GET", url, params={"content": "true"}, condicional=True
                )
            except ErroDeRede as erro:
                if erro.status == 404:
                    raise _NaoEncontrado from erro
                raise
            if resposta.status == 304:
                yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                return
            vagas, pulados = _ler(escopo, resposta.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except (_NaoEncontrado, _FormatoMudou) as erro:
            motivo = "saude.empresa_nao_encontrada" if isinstance(erro, _NaoEncontrado) else None
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", motivo or "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (não há chave `saude.*` com `n`
            # para isso; ver duvidas da T27). Trocar quando a chave existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o token ou o endereço do quadro e devolve o token; não faz pedido.

        `ValueError` se não for um quadro do Greenhouse (host europeu incluído: não testado).
        """
        texto = identificador.strip()
        token = texto
        if "/" in texto or "." in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            caminho = [p for p in partes.path.split("/") if p]
            host = (partes.hostname or "").lower()
            if partes.scheme not in ("http", "https"):
                raise ValueError(f"endereço não é http/https: {identificador!r}")
            if host in _HOSTS_BOARD and caminho[:1] == ["embed"]:
                # toda a família embed/* (job_board, job_app...) traz o token no `for`
                token = (parse_qs(partes.query).get("for") or [""])[0]
            elif host in _HOSTS_BOARD and caminho:
                token = caminho[0]
            elif host == _HOST_API and caminho[:2] == ["v1", "boards"] and len(caminho) > 2:
                token = caminho[2]
            else:
                raise ValueError(f"não é um quadro do Greenhouse: {identificador!r}")
        if not _TOKEN.fullmatch(token):
            raise ValueError(f"identificador inválido: {identificador!r}")
        return {"identificador": token}


COLETOR = Greenhouse()
