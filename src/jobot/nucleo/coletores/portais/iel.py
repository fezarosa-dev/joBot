"""Coletor IEL Carreiras (apêndice 3.2): uma página HTML por UF, com as vagas embutidas.

As vagas estão nos blocos `self.__next_f.push([1, "<texto RSC>"])` do Next.js. Cada bloco é
lido como JSON (nunca executado), os textos são juntados (uma linha RSC pode vir partida em
dois blocos) e cada objeto que começa com `{"vagaOrigem"` é lido com `raw_decode`. Cada vaga
aparece duas vezes na página: vale a primeira cópia legível de cada `vagaIdentificador`.
String longa (1024 caracteres ou mais) não vem no objeto: o React Flight a grava numa linha
`<id>:T<bytes em hex>,<texto>` e o campo guarda só `"$<id>"`; essas linhas são resolvidas antes.
UF sem vaga: a página traz o aviso "Nenhuma vaga encontrada" e vale `ok` com zero vagas; sem
objeto e sem o aviso, o formato mudou.
A página traz a descrição: não há `detalhar`. A conferência não viu `ETag` nem
`Last-Modified`, então não há pedido condicional.
"""

import json
import re
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from datetime import datetime, timedelta, timezone
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

_LIMITES = limites("iel")
_BASE = "https://carreiras.iel.org.br"
# Lista fixa (decisão A29, opção (b)): o `sitemap.xml` de 2026-11-14 só tem estas 19 UFs, e as
# outras não têm página de vaga (/BA responde 500). Atualizar quando o sitemap mudar.
UFS_COM_VAGA = (
    "AC", "AL", "AM", "DF", "ES", "GO", "MG", "MS", "MT", "PA",
    "PB", "PE", "PR", "RN", "RO", "SC", "SE", "SP", "TO",
)  # fmt: skip
_UF = re.compile(r"[A-Z]{2}")
_PUSH = re.compile(r"self\.__next_f\.push\(")
_INICIO = '{"vagaOrigem"'
_LINHA_T = re.compile(rb"([0-9a-f]+):T([0-9a-f]+),")
_REFERENCIA_T = re.compile(r"\$([0-9a-f]+)")
_AVISO_SEM_VAGA = "Nenhuma vaga encontrada"
# shortcut: `vagaInclusao` vem sem fuso; vale a hora de Brasília (o site é brasileiro e o Brasil não
# tem horário de verão desde 2019). O `lastmod` do sitemap traz a mesma hora com `Z`, então pode
# ser UTC: conferir na rede real e trocar se for.
_BRASILIA = timezone(timedelta(hours=-3))
_DESCRICAO = (
    ("Atividades", "vagaObservacao"),
    ("Requisitos", "vagaRequisitos"),
    ("Benefícios", "vagaBeneficios"),
    ("Horários", "vagaHorarios"),
    ("Cursos", "vagaCursos"),
)


class _FormatoMudou(Exception):
    """A página não traz os blocos RSC, ou nenhuma vaga embutida é legível."""


class _SemTexto(ValueError):
    """Referência do RSC sem texto resolvido: a vaga é pulada, nunca sai com o campo vazio."""


def _linhas(rsc: str) -> Iterator[tuple[str | None, str]]:
    """O RSC em linhas: `(id, texto)` para `<id>:T<bytes em hex>,<texto>` (sem `\\n` no fim) e
    `(None, linha)` para as demais, em ordem."""
    dados = rsc.encode("utf-8", "surrogatepass")
    pos = 0
    while pos < len(dados):
        # Só no começo de uma linha: o fim colado de um texto (ex.: "2025") não vira parte do id.
        linha = _LINHA_T.match(dados, pos)
        if linha is None:
            fim = dados.find(b"\n", pos)
            fim = len(dados) if fim == -1 else fim
            yield None, dados[pos:fim].decode("utf-8", "surrogatepass")
            pos = fim + 1
            continue
        pos = linha.end() + int(linha[2], 16)
        if pos <= len(dados):  # texto cortado fica sem resolver
            yield linha[1].decode(), dados[linha.end() : pos].decode("utf-8", "replace")


def _textos_longos(rsc: str) -> dict[str, str]:
    """As linhas T do RSC, por id."""
    return {id_: texto for id_, texto in _linhas(rsc) if id_ is not None}


def _texto(valor: object, textos: Mapping[str, str]) -> str:
    """Texto do RSC: `$$` é o `$` escapado, `$undefined` é ausente e `$<id>` é uma linha T."""
    if not isinstance(valor, str):
        return ""
    if valor.startswith("$$"):
        return valor[1:].strip()
    if valor == "$undefined":
        return ""
    if valor.startswith("$"):
        referencia = _REFERENCIA_T.fullmatch(valor)
        if referencia is None or referencia[1] not in textos:
            raise _SemTexto(valor)
        return textos[referencia[1]].strip()
    return valor.strip()


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    if lida is None or lida.utcoffset() is not None:
        return lida
    return lida.replace(tzinfo=_BRASILIA)


def _identificador(valor: object, textos: Mapping[str, str]) -> str | None:
    if isinstance(valor, int) and not isinstance(valor, bool):
        return str(valor)
    try:
        return _texto(valor, textos) or None
    except _SemTexto:
        return None


def _descricao(obj: Mapping[str, object], textos: Mapping[str, str]) -> str:
    partes = [(rotulo, _texto(obj.get(campo), textos)) for rotulo, campo in _DESCRICAO]
    de = _texto(obj.get("vagaEscolaridadeDe"), textos)
    ate = _texto(obj.get("vagaEscolaridadeAte"), textos)
    partes.insert(2, ("Escolaridade", " a ".join(dict.fromkeys(filter(None, [de, ate])))))
    return "\n\n".join(f"{rotulo}: {texto}" for rotulo, texto in partes if texto)


def _vaga(
    escopo: str, obj: Mapping[str, object], id_externo: str, textos: Mapping[str, str]
) -> VagaColetada | None:
    """Uma vaga embutida, ou `None` se faltar título, endereço ou texto referenciado (DR-08)."""

    def texto(campo: str) -> str:
        return _texto(obj.get(campo), textos)

    try:
        titulo = texto("vagaTitulo")
        if not titulo:
            return None
        uf = texto("vagaEstadoSigla") or escopo
        # Empresa quase sempre em sigilo (`vagaEmpresaNome` vazio): vale o IEL do estado.
        empresa = texto("vagaEmpresaNome") or f"IEL {texto('vagaEstado') or uf}"
        return VagaColetada(
            fonte="iel",
            escopo=escopo,
            url=texto("vagaUrl"),
            titulo=titulo,
            empresa=empresa,
            descricao_formato="texto",
            descricao=_descricao(obj, textos),
            id_externo=id_externo,
            locais=(", ".join(filter(None, [texto("vagaCidade"), uf])),),
            modalidade_declarada=texto("vagaModeloTrabalho") or None,
            contrato_declarado=texto("vagaTipo") or None,
            salario_texto=texto("vagaSalario") or None,
            publicada_em=_data_hora(obj.get("vagaInclusao")),
        )
    except ValueError:  # url fora de http/https, ou referência sem texto (`_SemTexto`)
        return None


def _blocos(html: str) -> Iterator[str]:
    """O texto de cada `self.__next_f.push([1, "..."])`, lido como JSON; o resto é ignorado."""
    decodificador = json.JSONDecoder()
    for achado in _PUSH.finditer(html):
        try:
            bloco, _ = decodificador.raw_decode(html, achado.end())
        except ValueError:
            continue
        if isinstance(bloco, list) and len(bloco) == 2 and bloco[0] == 1:
            if isinstance(bloco[1], str):
                yield bloco[1]


def _objetos(rsc: str) -> Iterator[object]:
    """Cada objeto `{"vagaOrigem"...}` do RSC; `None` no lugar do que não se lê.

    Só as linhas que não são T: o texto longo de um campo não é lido como objeto.
    """
    decodificador = json.JSONDecoder()
    for id_, linha in _linhas(rsc):
        if id_ is not None:
            continue
        inicio = linha.find(_INICIO)
        while inicio != -1:
            try:
                objeto, fim = decodificador.raw_decode(linha, inicio)
            except ValueError:
                objeto, fim = None, inicio + len(_INICIO)
            yield objeto
            inicio = linha.find(_INICIO, fim)


def _ler(escopo: str, html: str) -> tuple[list[VagaColetada], int]:
    """(vagas sem repetição, vagas puladas por formato)."""
    blocos = list(_blocos(html))
    if not blocos:
        raise _FormatoMudou
    # Na ordem da página; `None` enquanto nenhuma cópia daquele id se leu.
    vistas: dict[str, VagaColetada | None] = {}
    sem_id = 0
    rsc = "".join(blocos)
    textos = _textos_longos(rsc)
    for obj in _objetos(rsc):
        if not isinstance(obj, dict):
            sem_id += 1
            continue
        id_externo = _identificador(obj.get("vagaIdentificador"), textos)
        if id_externo is None:
            sem_id += 1
            continue
        if vistas.get(id_externo) is None:
            vistas[id_externo] = _vaga(escopo, obj, id_externo, textos)
    if not vistas and not sem_id and _AVISO_SEM_VAGA not in html:
        raise _FormatoMudou  # UF sem objeto e sem o aviso da página: o formato mudou
    vagas = [vaga for vaga in vistas.values() if vaga is not None]
    # Uma vaga só é pulada se nenhuma das suas cópias se leu; sem id, cada objeto conta.
    pulados = len(vistas) - len(vagas) + sem_id
    if pulados and not vagas:
        raise _FormatoMudou
    return vagas, pulados


class Iel:
    chave: str = "iel"
    nome: str = "IEL"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("carreiras.iel.org.br",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        brasil = any(p.strip().upper() == "BR" for p in ctx.paises)
        return list(UFS_COM_VAGA) if brasil else []

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        if not _UF.fullmatch(escopo):
            raise ValueError(f"escopo inválido: {escopo!r}")
        pulados = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados
            resposta = await http.pedir("GET", f"{_BASE}/{escopo}")
            vagas, pulados = _ler(escopo, resposta.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if pulados and resultado.estado == "ok":
            # shortcut: a contagem de pulados não vai no motivo (D45, como no Greenhouse).
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A página do estado já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A fonte não é por empresa: não há o que resolver."""
        raise ValueError(f"o IEL não usa identificador: {identificador!r}")


COLETOR = Iel()
