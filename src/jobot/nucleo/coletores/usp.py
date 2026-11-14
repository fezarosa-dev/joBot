"""Coletor da USP (apêndice 3.2): os murais do IF e da FEA, um escopo por unidade.

Cada mural é uma lista HTML mais uma página por vaga. A lista só dá título, empresa e prazo;
o texto da vaga vem da página dela. O executor só chama `detalhar` para `UrlListada`, então
`coletar` lê os detalhes ele mesmo e `detalhar` não faz nada. O endereço de cada vaga é
refeito a partir do número que o link traz: o host nunca vem da página.
"""

import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import (
    ErroDeRede,
    HttpEducado,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    RespostaGrande,
)
from jobot.nucleo.modelo import VagaColetada

_LIMITES = limites("usp")
HOST_IF = "portal.if.usp.br"
HOST_FEA = "estagios.fea.usp.br"
URL_IF = f"https://{HOST_IF}/carreiras/pt-br/oportunidades"
URL_FEA = f"https://{HOST_FEA}/"
_NODE_IF = f"https://{HOST_IF}/carreiras/pt-br/node/{{id}}"
_VAGA_FEA = f"https://{HOST_FEA}/vagas/{{id}}"
_LINK_IF = re.compile(r"/carreiras/pt-br/node/(\d+)")
_LINK_FEA = re.compile(r"/vagas/(\d+)")
_DATA = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
# A FEA não diz quem contrata na lista nem na página: a vaga fica com o nome do mural.
EMPRESA_FEA = "FEA-USP"
_SP = timezone(timedelta(hours=-3))  # sem horário-verão desde 2019
_MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
_PARAR = (LimiteAtingido, OrcamentoGasto, Parou429)


class _FormatoMudou(Exception):
    """A página não tem a lista, ou nenhuma vaga dela é legível."""


@dataclass(frozen=True)
class _Linha:
    vaga: VagaColetada
    prazo: date | None


def _data(texto: str) -> date | None:
    achou = _DATA.search(texto)
    if achou is None:
        return None
    dia, mes, ano = (int(g) for g in achou.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _id(href: str | None, base: str, host: str, padrao: re.Pattern[str]) -> str | None:
    """O número da vaga, se o link for do host esperado e do formato esperado."""
    if not href:
        return None
    partes = urlsplit(urljoin(base, href))
    achou = padrao.fullmatch(partes.path)
    if partes.scheme not in ("http", "https") or partes.hostname != host or achou is None:
        return None
    return achou.group(1)


def _arvore(texto: str) -> LexborHTMLParser:
    if not texto.strip():
        raise _FormatoMudou
    return LexborHTMLParser(texto)


def _sem_rotulo(texto: str, rotulo: str) -> str:
    texto = texto.strip()
    return texto.removeprefix(rotulo).strip() if texto.startswith(rotulo) else texto


def _campo(celula: LexborNode, classe: str, rotulo: str) -> str:
    no = celula.css_first(f".views-field-{classe} .field-content")
    return _sem_rotulo(no.text(strip=True), rotulo) if no is not None else ""


def _lista_if(texto: str) -> tuple[list[_Linha], int, bool]:
    """As vagas legíveis da lista do IF, as células puladas e se há pager que não se segue."""
    arvore = _arvore(texto)
    # shortcut: `view-empty` e `view-content` vêm do Drupal 7, mas a lista vazia não foi vista
    # ao vivo; se a página vazia real for outra, vira "falhou" até o marcador ser corrigido.
    if arvore.css_first("div.view-content") is None:
        if arvore.css_first("div.view-empty") is None:
            raise _FormatoMudou
        return [], 0, False
    linhas: dict[str, _Linha] = {}
    pulados = 0
    for celula in arvore.css("div.view-content td"):
        if not celula.text(strip=True):
            continue  # célula de enchimento da grade
        link = celula.css_first(".views-field-title a")
        id_ = _id(link.attributes.get("href") if link else None, URL_IF, HOST_IF, _LINK_IF)
        titulo = link.text(strip=True) if link is not None else ""
        empresa = _campo(celula, "field-instituicao", "Instituição:")
        if id_ is None or not titulo or not empresa:
            pulados += 1
            continue
        if id_ in linhas:
            continue
        linhas[id_] = _Linha(
            VagaColetada(
                fonte="usp",
                escopo="if",
                url=_NODE_IF.format(id=id_),
                titulo=titulo,
                empresa=empresa,
                descricao_formato="html",
                id_externo=id_,
                contrato_declarado=_campo(
                    celula, "field-tipo-de-oportunidade", "Tipo de Oportunidade:"
                )
                or None,
            ),
            _data(_campo(celula, "field-data-termino", "Data Término Inscrição:")),
        )
    if not linhas:
        raise _FormatoMudou
    # shortcut: o pager do Drupal (`ul.pager` com link) não é seguido; a lista sai parcial.
    # A lista tem 7 itens hoje; seguir as páginas quando passar de uma.
    pager = arvore.css_first("ul.pager li a[href]") is not None
    return list(linhas.values()), pulados, pager


def _detalhe_if(texto: str) -> tuple[str, datetime | None, date | None] | None:
    """Descrição em HTML, data de postagem e prazo; `None` se não achar a descrição."""
    arvore = _arvore(texto)
    descricao = arvore.css_first(".field-name-field-descricao .field-item")
    if descricao is None:
        return None
    postada = None
    dia, mes, ano = (arvore.css_first(f".submitted-date .{c}") for c in ("day", "month", "year"))
    if dia and mes and ano and (m := mes.text(strip=True).lower()) in _MESES:
        try:
            postada = datetime(
                int(ano.text(strip=True)),
                _MESES.index(m) + 1,
                int(dia.text(strip=True)),
                12,
                tzinfo=_SP,
            )
        except ValueError:
            pass  # sem hora na página: meio-dia, para a data não mudar de dia no fuso
    termino = arvore.css_first(".field-name-field-data-termino .date-display-single")
    prazo = _data(termino.text(strip=True)) if termino is not None else None
    return (descricao.inner_html or "").strip(), postada, prazo


def _lista_fea(texto: str) -> tuple[list[_Linha], int, bool]:
    arvore = _arvore(texto)
    if not any("Mural de Vagas" in h.text() for h in arvore.css("h2")):
        raise _FormatoMudou
    linhas: dict[str, _Linha] = {}
    pulados = 0
    for tr in arvore.css("tbody tr"):
        link = tr.css_first("a[href]")
        id_ = _id(link.attributes.get("href") if link else None, URL_FEA, HOST_FEA, _LINK_FEA)
        titulo_no = tr.css_first("h4")
        titulo = titulo_no.text(strip=True) if titulo_no is not None else ""
        if id_ is None or not titulo:
            pulados += 1
            continue
        if id_ in linhas:
            continue
        carga = bolsa = None
        for linha in tr.text(separator="\n", strip=True).splitlines():
            if linha.startswith("Carga horária semanal:"):
                carga = linha
            elif linha.startswith("Valor da bolsa:"):
                bolsa = _sem_rotulo(linha, "Valor da bolsa:") or None
        linhas[id_] = _Linha(
            VagaColetada(
                fonte="usp",
                escopo="fea",
                url=_VAGA_FEA.format(id=id_),
                titulo=titulo,
                empresa=EMPRESA_FEA,
                descricao_formato="texto",
                descricao=carga or "",
                id_externo=id_,
                contrato_declarado="Estágio",
                salario_texto=bolsa,
            ),
            None,
        )
    if arvore.css_first("tbody tr") is not None and not linhas:
        raise _FormatoMudou  # linhas que ninguém lê: o formato mudou, não é lista vazia
    return list(linhas.values()), pulados, False


def _campos_fea(texto: str) -> dict[str, str]:
    """Os pares `<b>Rótulo:</b> valor` do detalhe, com o rótulo em minúsculas."""
    bloco = _arvore(texto).css_first("#content .card-body .col-sm")
    campos: dict[str, str] = {}
    rotulo: str | None = None
    partes: list[str] = []
    for no in bloco.iter(include_text=True) if bloco is not None else ():
        if no.tag == "b":
            if rotulo is not None:
                campos[rotulo] = "".join(partes).strip()
            rotulo, partes = no.text(strip=True).rstrip(":").strip().casefold(), []
        elif no.tag == "-text" or not (no.tag or "-").startswith("-"):  # <a>, <i> também contam
            partes.append(no.text())
    if rotulo is not None:
        campos[rotulo] = "".join(partes).strip()
    return campos


def _detalhe_fea(texto: str) -> tuple[str, str | None, date | None] | None:
    """Descrição em texto, salário como veio e prazo; `None` se não achar a descrição."""
    campos = _campos_fea(texto)
    if not campos.get("descrição da vaga"):
        return None
    saidas = (
        ("benefícios", "Benefícios"),
        ("carga horária semanal", "Carga horária semanal"),
        ("horário do estágio", "Horário do estágio"),
        ("contato para vaga", "Contato para vaga"),
    )
    partes = [campos["descrição da vaga"]]
    partes += [f"{saida}: {campos[chave]}" for chave, saida in saidas if campos.get(chave)]
    return (
        "\n".join(partes),
        campos.get("valor mensal da bolsa") or None,
        _data(campos.get("divulgar até", "")),
    )


class USP:
    chave: str = "usp"
    nome: str = "USP"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (HOST_IF, HOST_FEA)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return ["if", "fea"]  # as unidades são fixas: não vêm do cadastro de empresas

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        if escopo not in ("if", "fea"):
            raise ValueError(f"escopo da USP desconhecido: {escopo!r}")
        # shortcut: a FEA lê só a página inicial (`/vagas` dá 403) e a lista dela é curta; se
        # passar a paginar, a página inicial deixa de bastar (apêndice 3.2).
        lista, ler_detalhe = (URL_IF, _lista_if) if escopo == "if" else (URL_FEA, _lista_fea)
        estado = {"formato": False, "rede": False, "pager": False}

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            linhas, pulados, pager = ler_detalhe((await http.pedir("GET", lista)).texto)
            estado["formato"] = bool(pulados)
            estado["pager"] = pager
            vagas: list[Item] = []
            parar: Exception | None = None
            for linha in linhas:
                vaga = replace(linha.vaga, prazo=linha.prazo)  # o que a lista já sabe
                if parar is None:
                    try:
                        resposta = await http.pedir("GET", vaga.url)
                    except _PARAR as erro:
                        parar = erro  # as vagas já lidas seguem como estão
                    except ErroDeRede, RespostaGrande:
                        estado["rede"] = True
                    else:
                        vaga, lido = _com_detalhe(escopo, vaga, resposta.texto)
                        estado["formato"] |= not lido
                vagas.append(vaga)
            yield vagas
            if parar is not None:
                raise parar

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if resultado.estado != "ok" or not any(estado.values()):
            return resultado
        # shortcut: a contagem de itens pulados não vai no motivo (não há chave `saude.*` com
        # `n`; D45). Trocar quando a chave existir.
        motivo = (
            "saude.formato_mudou"
            if estado["formato"]
            else "saude.listagem_incompleta"
            if estado["pager"]
            else "saude.erro_de_rede"
        )
        return ResultadoEscopo(resultado.vagas, "parcial", motivo, resultado.pedidos)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """`coletar` já leu o detalhe: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        raise ValueError("a USP não tem identificador para resolver")


def _com_detalhe(escopo: str, vaga: VagaColetada, texto: str) -> tuple[VagaColetada, bool]:
    """A vaga da lista completada pelo detalhe, e se o detalhe foi legível."""
    try:
        if escopo == "if":
            lido_if = _detalhe_if(texto)
            if lido_if is None:
                return vaga, False
            descricao, postada, prazo = lido_if
            return replace(
                vaga, descricao=descricao, publicada_em=postada, prazo=vaga.prazo or prazo
            ), True
        lido_fea = _detalhe_fea(texto)
    except _FormatoMudou:
        return vaga, False
    if lido_fea is None:
        return vaga, False
    descricao, bolsa, prazo = lido_fea
    return replace(
        vaga, descricao=descricao, salario_texto=bolsa or vaga.salario_texto, prazo=prazo
    ), True


COLETOR = USP()
