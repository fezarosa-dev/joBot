"""Coletor Super Estágios (apêndice 3.2): fonte de sitemap (DR-70), `detalhar` lê o JSON-LD.

`coletar` baixa `/sitemap_vagas.php` e devolve uma `UrlListada` (endereço e `lastmod`) para cada
`<url>`, sem filtrar por data: o filtro de 30 dias e o orçamento de detalhes são do executor.
`detalhar` abre a página da vaga e monta a `VagaColetada` do JSON-LD `JobPosting` (título,
empresa, local, salário, datas); a descrição vem da tabela da página (Atividades primeiro) ou,
sem tabela, do `description` do JSON-LD. Sem título ou empresa a página não vira vaga (`None`).
O endereço da vaga é sempre o da `UrlListada`: o `url` do JSON-LD é dado de terceiro e é ignorado.
A conferência só viu `cache-control` no sitemap, sem `ETag` nem `Last-Modified`: não há pedido
condicional.
"""

import json
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from selectolax.lexbor import LexborHTMLParser

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import ErroDeRede, HttpEducado
from jobot.nucleo.modelo import Periodo, SalarioBruto, VagaColetada

_LIMITES = limites("super_estagios")
_URL_SITEMAP = "https://www.superestagios.com.br/sitemap_vagas.php"
# Só `https://www.superestagios.com.br/vaga/<número>`: o sitemap é dado de terceiro, então host
# local, outro host e página de listagem não passam (e nunca viram pedido).
_URL_VAGA = re.compile(r"https://www\.superestagios\.com\.br/vaga/(\d+)")
# shortcut: `lastmod`, `datePosted` sem fuso valem hora de Brasília (o site é brasileiro e o Brasil
# não tem horário de verão desde 2019; o `validThrough` do site vem com -03:00). Conferir na rede
# real e trocar se o site passar a mandar UTC.
_BRASILIA = timezone(timedelta(hours=-3))
_PERIODOS: Mapping[str, Periodo] = {
    "HOUR": "hora",
    "DAY": "dia",
    "WEEK": "semana",
    "MONTH": "mes",
    "YEAR": "ano",
}
# Linhas da tabela que já estão em outros campos (ou só contam vagas); o resto vai na descrição.
_FORA_DA_DESCRICAO = frozenset(
    {"Número da vaga", "Empresa", "Bairro", "Cidade", "Estado", "Quantidade de vagas"}
)


class _FormatoMudou(Exception):
    """O sitemap não é um `urlset`, ou nenhuma `<url>` dele deu uma vaga do site."""


def _nome(elemento: ET.Element) -> str:
    """Nome da tag sem o namespace do protocolo de sitemap (o site hoje não o usa)."""
    return elemento.tag.rpartition("}")[2]


def _data_hora(valor: object) -> datetime | None:
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    if lida is None or lida.utcoffset() is not None:
        return lida
    return lida.replace(tzinfo=_BRASILIA)


def _ler_sitemap(texto: str) -> tuple[list[Item], int, int]:
    """(vagas na ordem do sitemap, `<url>` sem endereço, `<url>` recusadas por não serem vaga)."""
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError:
        raise _FormatoMudou from None
    if _nome(raiz) != "urlset":
        raise _FormatoMudou
    urls = [e for e in raiz if _nome(e) == "url"]
    vagas: list[Item] = []
    sem_endereco = recusadas = 0
    for url in urls:
        loc = next((e for e in url if _nome(e) == "loc"), None)
        endereco = (loc.text or "").strip() if loc is not None else ""
        if not endereco:
            sem_endereco += 1
        elif _URL_VAGA.fullmatch(endereco) is None:
            recusadas += 1
        else:
            lastmod = next((e for e in url if _nome(e) == "lastmod"), None)
            vagas.append(
                UrlListada(
                    endereco,
                    _data_hora(
                        lastmod.text.strip() if lastmod is not None and lastmod.text else None
                    ),
                )
            )
    if urls and not vagas:
        raise _FormatoMudou
    return vagas, sem_endereco, recusadas


def _texto(valor: object) -> str | None:
    return valor.strip() or None if isinstance(valor, str) else None


def _numero(valor: object) -> float | None:
    """Valor positivo e finito; `bool` (que é `int`), texto e zero não valem."""
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    return valor if math.isfinite(valor) and valor > 0 else None


def _salario(base: object) -> SalarioBruto | None:
    if not isinstance(base, dict):
        return None
    valor = base.get("value")
    if not isinstance(valor, dict):
        return None
    unico = _numero(valor.get("value"))
    minimo = unico if unico is not None else _numero(valor.get("minValue"))
    maximo = None if unico is not None else _numero(valor.get("maxValue"))
    if minimo is None and maximo is None:
        return None
    unidade = valor.get("unitText")
    return SalarioBruto(
        moeda=_texto(base.get("currency")),
        minimo_unidades=minimo,
        maximo_unidades=maximo,
        periodo=_PERIODOS.get(unidade) if isinstance(unidade, str) else None,
    )


def _locais(lugares: object) -> tuple[str, ...]:
    achados: list[str] = []
    for lugar in lugares if isinstance(lugares, list) else [lugares]:
        endereco = lugar.get("address") if isinstance(lugar, dict) else None
        if isinstance(endereco, dict):
            local = ", ".join(
                filter(
                    None,
                    [
                        _texto(endereco.get("addressLocality")),
                        _texto(endereco.get("addressRegion")),
                    ],
                )
            )
            if local:
                achados.append(local)
    return tuple(dict.fromkeys(achados))


def _candidatos(dado: object) -> Iterator[dict[str, object]]:
    """Os objetos do JSON-LD solto, em lista ou em `@graph`."""
    if isinstance(dado, list):
        for filho in dado:
            yield from _candidatos(filho)
    elif isinstance(dado, dict):
        yield dado
        yield from _candidatos(dado.get("@graph"))


def _vaga_do_json_ld(arvore: LexborHTMLParser) -> dict[str, object] | None:
    for script in arvore.css('script[type="application/ld+json"]'):
        try:
            dado = json.loads(script.text())
        except ValueError:
            continue
        for candidato in _candidatos(dado):
            tipo = candidato.get("@type")
            if tipo == "JobPosting" or (isinstance(tipo, list) and "JobPosting" in tipo):
                return candidato
    return None


def _descricao(arvore: LexborHTMLParser, ld: Mapping[str, object]) -> str:
    linhas: list[tuple[str, str]] = []
    for linha in arvore.css("tr"):
        celulas = linha.css("td")
        if len(celulas) != 2:
            continue
        rotulo = celulas[0].text(strip=True).rstrip(":").strip()
        valor = celulas[1].text(separator="\n", strip=True)
        if rotulo and valor and rotulo not in _FORA_DA_DESCRICAO:
            linhas.append((rotulo, valor))
    if not linhas:
        return _texto(ld.get("description")) or ""
    linhas.sort(
        key=lambda r: not r[0].startswith("Atividades")
    )  # estável: o resto na ordem da página
    return "\n\n".join(f"{rotulo}: {valor}" for rotulo, valor in linhas)


def _vaga(url: str, numero: str, arvore: LexborHTMLParser) -> VagaColetada | None:
    ld = _vaga_do_json_ld(arvore)
    if ld is None:
        return None
    organizacao = ld.get("hiringOrganization")
    titulo = _texto(ld.get("title"))
    empresa = _texto(organizacao.get("name")) if isinstance(organizacao, dict) else None
    if titulo is None or empresa is None:
        return None
    identificador = ld.get("identifier")
    valor_id = identificador.get("value") if isinstance(identificador, dict) else None
    if isinstance(valor_id, int) and not isinstance(valor_id, bool):
        valor_id = str(valor_id)
    validade = _texto(ld.get("validThrough"))
    try:
        prazo = date.fromisoformat(validade[:10]) if validade else None
    except ValueError:
        prazo = None
    return VagaColetada(
        fonte="super_estagios",
        escopo="",
        url=url,
        titulo=titulo,
        empresa=empresa,
        descricao_formato="texto",
        descricao=_descricao(arvore, ld),
        id_externo=_texto(valor_id) or numero,
        locais=_locais(ld.get("jobLocation")),
        contrato_declarado=_texto(ld.get("employmentType")),
        salario_estruturado=_salario(ld.get("baseSalary")),
        publicada_em=_data_hora(ld.get("datePosted")),
        prazo=prazo,
    )


class SuperEstagios:
    chave: str = "super_estagios"
    nome: str = "Super Estágios"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("www.superestagios.com.br",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return [""]

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        sem_endereco = recusadas = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal sem_endereco, recusadas
            resposta = await http.pedir("GET", _URL_SITEMAP)
            vagas, sem_endereco, recusadas = _ler_sitemap(resposta.texto)
            yield vagas

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if resultado.estado != "ok":
            return resultado
        if sem_endereco:  # item pulado: "ok" fecharia a vaga que ficou de fora
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        if recusadas:  # o executor soma o `sem_detalhe_n` na saúde da fonte
            return ResultadoEscopo(
                resultado.vagas, "ok", f"saude.sem_detalhe_n:{recusadas}", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        if not isinstance(item, UrlListada):
            return None
        achou = _URL_VAGA.fullmatch(item.url)
        if achou is None:
            return None
        try:
            resposta = await http.pedir("GET", item.url)
        except ErroDeRede as erro:
            if erro.status in (404, 410):  # saiu do ar: `None` a guarda 30 dias, sem repetir o 404
                return None
            raise
        return _vaga(item.url, achou[1], LexborHTMLParser(resposta.texto))

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """A fonte não é por empresa: não há o que resolver."""
        raise ValueError(f"o Super Estágios não usa identificador: {identificador!r}")


COLETOR = SuperEstagios()
