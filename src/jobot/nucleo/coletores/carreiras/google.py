"""Coletor Google Careers (apêndice 3.4): o feed XML público, uma lista única.

Um pedido traz o mundo inteiro (3.271 vagas, 19,8 MB sem compressão), acima do teto padrão de
5 MB do cliente: o pedido leva `TETO_FEED_BYTES` e o cliente lê o corpo em fluxo, como no Ashby;
acima do teto `RespostaGrande` sobe e o executor dá "falhou". O XML é percorrido com
`iterparse`, cada `<job>` é descartado depois de lido, e só fica a vaga com algum
`locations/location/country == 'Brazil'`. O feed traz `Last-Modified`: o pedido é condicional
(`If-Modified-Since`), e 304 vira "sem_mudanca".
"""

import io
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Literal

from jobot.nucleo.coletores.base import (
    SEM_MUDANCA,
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import HttpEducado
from jobot.nucleo.modelo import VagaColetada

_LIMITES = limites("google")
_FEED = "https://www.google.com/about/careers/applications/jobs/feed.xml"
_PAIS = "Brazil"
_EMPRESA = "Google"  # reserva para `employer` ausente: o feed é só de Google, YouTube e DeepMind
TETO_FEED_BYTES = 32 * 1024 * 1024  # o feed tem 19,8 MB; o padrão do cliente é 5 MB


class _FormatoMudou(Exception):
    """O corpo não é XML ou a raiz não é `<jobs>`; há filho direto de `<jobs>` com outro nome
    (fora `<updated>`) e nenhum `<job>`; há `<job>` e nenhum traz país; ou há vaga do Brasil e
    nenhuma é legível."""


def _texto(no: ET.Element, caminho: str) -> str:
    return (no.findtext(caminho) or "").strip()


def _data_hora(valor: str) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor)
    except ValueError:
        return None
    return lida if lida.utcoffset() is not None else None


def _modalidade(job: ET.Element) -> str | None:
    if _texto(job, "isHybrid") == "Yes":
        return "hybrid"
    if _texto(job, "isRemote") == "Yes" or _texto(job, "remote") == "remote":
        return "remote"
    return _texto(job, "remote") or None


def _vaga(job: ET.Element, locais: tuple[str, ...]) -> VagaColetada | None:
    """A vaga, ou `None` se faltar título ou URL, ou a URL não for http/https (DR-08)."""
    titulo = _texto(job, "title")
    if not titulo:
        return None
    try:
        return VagaColetada(
            fonte="google",
            escopo="",
            url=_texto(job, "url"),
            titulo=titulo,
            empresa=_texto(job, "employer") or _EMPRESA,
            descricao_formato="html",  # o HTML vem escapado dentro do XML
            descricao=_texto(job, "description"),
            id_externo=_texto(job, "jobid") or None,
            locais=locais,
            modalidade_declarada=_modalidade(job),
            contrato_declarado=_texto(job, "jobtype") or None,
            publicada_em=_data_hora(_texto(job, "published")),
            etiquetas=tuple(
                dict.fromkeys(t for c in job.iterfind("categories/category") if (t := c.text))
            ),
        )
    except ValueError:  # url vazia ou fora de http/https
        return None


def _locais(job: ET.Element) -> tuple[list[str], tuple[str, ...]]:
    """Os países e os locais (`cidade, estado, país`, sem repetição) do `<job>`."""
    paises: list[str] = []
    locais: list[str] = []
    for local in job.iterfind("locations/location"):
        paises.append(_texto(local, "country"))
        locais.append(", ".join(t for c in ("city", "state", "country") if (t := _texto(local, c))))
    return paises, tuple(dict.fromkeys(x for x in locais if x))


def _ler(texto: str) -> tuple[list[VagaColetada], int]:
    """As vagas do Brasil e quantas delas foram puladas por formato."""
    vagas: list[VagaColetada] = []
    pulados = n_jobs = com_pais = desconhecidos = 0
    try:
        eventos = ET.iterparse(io.StringIO(texto), events=("start", "end"))
        _, raiz = next(eventos)
        if raiz.tag != "jobs":
            raise _FormatoMudou
        profundidade = 1
        for evento, no in eventos:
            profundidade += 1 if evento == "start" else -1
            if evento == "start" or profundidade != 1:
                continue  # só o fim de um filho direto de <jobs>
            if no.tag == "job":
                n_jobs += 1
                paises, locais = _locais(no)
                com_pais += any(paises)
                if _PAIS in paises:
                    if vaga := _vaga(no, locais):
                        vagas.append(vaga)
                    else:
                        pulados += 1
            elif no.tag != "updated":
                desconhecidos += 1
            raiz.clear()  # o filho lido sai da árvore: o feed inteiro nunca fica montado
    except (ET.ParseError, StopIteration) as erro:
        raise _FormatoMudou from erro
    # Sem <job> (outro nome) ou sem país em nenhum <job>, o "ok" vazio fecharia todas as vagas.
    if (pulados and not vagas) or (n_jobs and not com_pais) or (desconhecidos and not n_jobs):
        raise _FormatoMudou
    return vagas, pulados


class Google:
    chave: str = "google"
    nome: str = "Google Careers"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("www.google.com",)
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
            resposta = await http.pedir("GET", _FEED, condicional=True, teto_bytes=TETO_FEED_BYTES)
            if resposta.status == 304:
                yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                return
            vagas, pulados = _ler(resposta.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            # `RespostaGrande` sobe, como no Ashby: o executor a traduz em saude.resposta_grande
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (D45, opção provisória como no
            # Ashby). Trocar quando a D45 decidir.
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """O feed já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """O Google é uma lista só, sem empresa nem identificador a resolver."""
        raise ValueError(f"o Google Careers não tem identificador: {identificador!r}")


COLETOR = Google()
