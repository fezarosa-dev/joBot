"""Coletor Cia de Talentos (apêndice 3.2): programas de estágio e trainee, um `POST` só.

`POST` com `{"locale":"pt"}` devolve a lista inteira (27 programas, sem paginação, sem login:
"authentication" no caminho é só o nome). A descrição já vem na lista: não há `detalhar`.
São programas, não vagas individuais, e o endereço é interno do sistema de candidatura, sem
documentação pública: se a forma mudar, a fonte falha com `saude.formato_mudou`.
"""

import html
import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
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
from jobot.nucleo.modelo import VagaColetada, confere_http

_LIMITES = limites("cia_de_talentos")
_API = "https://vagas.ciadetalentos.com.br/applicant/rest/applicant/authentication/filter"
_PREFIXO = re.compile(r"\s*(?:localidade|[áa]rea)\s*:\s*", re.IGNORECASE)
_DIAS = re.compile(r"-?[0-9]{1,6}")
_CONTRATO = {1: "trainee", 2: "estágio", 3: "estágio"}  # o site agrupa assim (loading.js)


class _FormatoMudou(Exception):
    """A resposta não é uma lista, ou nenhum programa dela é legível."""


def _agora() -> datetime:
    return datetime.now(UTC)


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _inteiro(valor: object) -> int | None:
    """Número inteiro que a fonte manda ora como número, ora como texto; `bool` e o resto não."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and _DIAS.fullmatch(valor.strip()):
        return int(valor)
    return None


def _id(valor: object) -> str | None:
    """`bool` e texto vazio não viram `id_externo` (D57)."""
    if isinstance(valor, bool) or not isinstance(valor, int | str):
        return None
    return str(valor).strip() or None


def _textos(valor: object) -> tuple[str, ...]:
    """Local ou área como a fonte manda (texto ou lista de textos), sem o rótulo e sem "Diversas".

    shortcut: só se viu "Localidade: Diversas"; um texto com várias cidades vira um local só.
    Separar quando a fonte mostrar o formato.
    """
    itens = valor if isinstance(valor, list) else [valor]
    limpos = (_PREFIXO.sub("", _texto(i), count=1).strip() for i in itens)
    return tuple(t for t in limpos if t and t.casefold() != "diversas")


def _prazo(dias: object) -> date | None:
    """Hoje (dia local) mais `countFinishDays`; `daysRemainingForInscription` não vale."""
    n = _inteiro(dias)
    if n is None:
        return None
    try:
        return _agora().astimezone().date() + timedelta(days=n)
    except OverflowError:
        return None


def _descricao(job: dict[str, object]) -> str:
    texto = job.get("opportunityDescription")
    partes = [texto.strip()] if isinstance(texto, str) and texto.strip() else []
    area = ", ".join(_textos(job.get("opportunityAreas")))
    if area:
        partes.append(f"<p>Área: {html.escape(area)}</p>")
    return "\n".join(partes)


def _http_valido(valor: object) -> str | None:
    url = _texto(valor)
    try:
        confere_http(url, "url")
    except ValueError:
        return None
    return url


def _vaga(job: object) -> VagaColetada | None:
    """Um programa da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    titulo, empresa = _texto(job.get("opportunityName")), _texto(job.get("companyName"))
    hotsite = _http_valido(job.get("opportunityHotsiteUrl"))
    inscricao = _http_valido(job.get("opportunityInscriptionUrl"))
    url = hotsite or inscricao  # como o site: a página do programa, senão a inscrição
    if not titulo or not empresa or url is None:
        return None
    tipo = _inteiro(job.get("hiringTypeId"))
    nivel = _texto(job.get("hiringType"))
    return VagaColetada(
        fonte="cia_de_talentos",
        escopo="",
        url=url,
        titulo=titulo,
        empresa=empresa,
        descricao_formato="html",
        descricao=_descricao(job),
        id_externo=_id(job.get("opportunityId")),
        url_candidatura=inscricao,
        locais=_textos(job.get("opportunityLocations")),
        contrato_declarado=_CONTRATO.get(tipo) if tipo is not None else None,
        prazo=_prazo(job.get("countFinishDays")),
        etiquetas=(nivel,) if nivel else (),
    )


def _ler(dados: object) -> tuple[list[VagaColetada], int]:
    """Os programas legíveis da resposta e quantos foram pulados."""
    if not isinstance(dados, list):
        raise _FormatoMudou
    vagas = [v for v in map(_vaga, dados) if v is not None]
    if dados and not vagas:
        raise _FormatoMudou
    return vagas, len(dados) - len(vagas)


class CiaDeTalentos:
    chave: str = "cia_de_talentos"
    nome: str = "Cia de Talentos"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("vagas.ciadetalentos.com.br",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return [""]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            # sem `condicional`: a resposta é no-store e não traz ETag nem Last-Modified
            resposta = await http.pedir(
                "POST",
                _API,
                cabecalhos={"Accept": "application/json"},
                corpo_json={"locale": "pt"},
            )
            try:
                vagas, pulados = _ler(json.loads(resposta.texto))
            except (ValueError, _FormatoMudou) as erro:
                raise _FormatoMudou from erro
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # HttpDoEscopo conta; outro, não
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem não vai no motivo (não há chave `saude.*` com `n` para isso;
            # D45). Trocar quando a chave existir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A Cia de Talentos é uma lista só, sem empresa nem identificador a resolver."""
        raise ValueError(f"a Cia de Talentos não tem identificador: {identificador!r}")


COLETOR = CiaDeTalentos()
