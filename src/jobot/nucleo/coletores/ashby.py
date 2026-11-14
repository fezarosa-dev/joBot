"""Coletor Ashby (apêndice 2.4): API pública do quadro, um escopo por empresa.

A lista inteira vem numa resposta, com a descrição (até 4,5 MB, perto do teto de 5 MB): não há
paginação nem `detalhar`. A resposta não traz o nome da empresa: ele vem do cadastro, guardado
em `escopos()`.
"""

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
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

_LIMITES = limites("ashby")
_API = "https://api.ashbyhq.com/posting-api/job-board/{nome}"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,100}")
_HOST_QUADRO = "jobs.ashbyhq.com"  # o europeu fica de fora: não testado
_HOST_API = "api.ashbyhq.com"


class _NaoEncontrado(Exception):
    """404: o quadro não existe (chega como `ErroDeRede` com status 404)."""


class _FormatoMudou(Exception):
    """A resposta não traz a lista `jobs`, ou nenhum item dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    return lida if lida is not None and lida.utcoffset() is not None else None


def _sem_repeticao(valores: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(v for v in valores if v))


def _locais(job: dict[str, object]) -> tuple[str, ...]:
    # shortcut: `secondaryLocations` veio vazio em toda captura; lê string ou objeto com
    # `location`. Conferir quando uma captura trouxer o formato.
    outras = job.get("secondaryLocations")
    extras = [
        _texto(o.get("location") if isinstance(o, dict) else o)
        for o in (outras if isinstance(outras, list) else [])
    ]
    return _sem_repeticao([_texto(job.get("location")), *extras])


def _salario_texto(job: dict[str, object]) -> str | None:
    # shortcut: só o resumo em texto (o tratamento lê a faixa dele); `compensationTiers` fica de
    # fora porque o formato de `interval` não apareceu em captura. Ler quando aparecer.
    comp = job.get("compensation")
    if not isinstance(comp, dict):
        return None
    for campo in ("scrapeableCompensationSalarySummary", "compensationTierSummary"):
        if texto := _texto(comp.get(campo)):
            return texto
    return None


def _vaga(escopo: str, empresa: str, job: dict[str, object]) -> VagaColetada | None:
    """A vaga, ou `None` se faltar campo obrigatório ou a URL não for http/https (DR-08)."""
    titulo = _texto(job.get("title"))
    if not titulo:
        return None
    html, puro = _texto(job.get("descriptionHtml")), _texto(job.get("descriptionPlain"))
    apply = job.get("applyUrl")
    try:
        return VagaColetada(
            fonte="ashby",
            escopo=escopo,
            url=_texto(job.get("jobUrl")),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="html" if html or not puro else "texto",
            descricao=html or puro,
            id_externo=str(job["id"]) if isinstance(job.get("id"), int | str) else None,
            url_candidatura=apply if isinstance(apply, str) and apply else None,  # sem mudança
            locais=_locais(job),
            modalidade_declarada=_texto(job.get("workplaceType")) or None,
            contrato_declarado=_texto(job.get("employmentType")) or None,
            salario_texto=_salario_texto(job),
            publicada_em=_data_hora(job.get("publishedAt")),
            etiquetas=_sem_repeticao([_texto(job.get("department")), _texto(job.get("team"))]),
        )
    except ValueError:  # url fora de http/https
        return None


def _ler(escopo: str, empresa: str, texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas listadas e quantos itens foram pulados por formato."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    jobs = dados.get("jobs") if isinstance(dados, dict) else None
    if not isinstance(jobs, list):
        raise _FormatoMudou
    vagas: list[VagaColetada] = []
    nao_listadas = pulados = 0
    for job in jobs:
        # `isListed` que não é booleano é formato mudado: tratá-lo como "não listada" faria o
        # quadro inteiro parecer vazio ("ok") e fecharia todas as vagas da empresa.
        listada = job.get("isListed") if isinstance(job, dict) else None
        if not isinstance(listada, bool):
            pulados += 1
        elif not listada:
            nao_listadas += 1
        elif vaga := _vaga(escopo, empresa, job):
            vagas.append(vaga)
        else:
            pulados += 1
    if jobs and not vagas and not nao_listadas:
        raise _FormatoMudou
    return vagas, pulados


class Ashby:
    chave: str = "ashby"
    nome: str = "Ashby"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (_HOST_API,)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def __init__(self) -> None:
        self._empresas: dict[str, str] = {}  # identificador -> nome do cadastro

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        self._empresas = {}
        for e in ctx.empresas:
            self._empresas.setdefault(e.identificador, e.nome)
        return list(self._empresas)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = 0
        # shortcut: sem `escopos()` antes (nome fora do cadastro), a empresa é o identificador.
        empresa = self._empresas.get(escopo, escopo)

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            url = _API.format(nome=quote(escopo, safe=""))
            try:
                resposta = await http.pedir(
                    "GET", url, params={"includeCompensation": "true"}, condicional=True
                )
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
            # shortcut: a contagem de pulados não vai no motivo (D45, opção provisória como no
            # Greenhouse). Trocar quando a D45 decidir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o nome ou o endereço do quadro e devolve o nome; não faz pedido.

        `ValueError` se não for um quadro do Ashby (host europeu incluído: não testado). A caixa
        é preservada, como no Greenhouse (D45).
        """
        texto = identificador.strip()
        nome = texto
        if "/" in texto or "." in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            caminho = [p for p in partes.path.split("/") if p]
            host = (partes.hostname or "").lower()
            if partes.scheme not in ("http", "https"):
                raise ValueError(f"endereço não é http/https: {identificador!r}")
            if host == _HOST_QUADRO and caminho:
                nome = caminho[0]
            elif (
                host == _HOST_API
                and caminho[:2] == ["posting-api", "job-board"]
                and len(caminho) > 2
            ):
                nome = caminho[2]
            else:
                raise ValueError(f"não é um quadro do Ashby: {identificador!r}")
        if not _TOKEN.fullmatch(nome):
            raise ValueError(f"identificador inválido: {identificador!r}")
        return {"identificador": nome}


COLETOR = Ashby()
