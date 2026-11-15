"""Coletor Recrutei (apêndice 3.1): um escopo por empresa (o `label` do quadro).

A lista é um `POST` com corpo `{}` e vem inteira, sem descrição, numa resposta 202. A descrição
só existe no HTML da vaga (`__NEXT_DATA__`), lida em `detalhar`. O site embute a chave de uma
API antiga: ela nunca é lida nem enviada (a lista não a pede). A empresa vem de `company_name`.
"""

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
from jobot.nucleo.modelo import VagaColetada, confere_http

_LIMITES = limites("recrutei")
_API = "https://api.recrutei.com.br/api/v2/vacancies/per-departments/{label}"
_LABEL = re.compile(r"[A-Za-z0-9_-]{1,100}")
_HOST_VAGAS = "jobs.recrutei.com.br"
_HOST_API = "api.recrutei.com.br"
_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)
_FUSO = timezone(timedelta(hours=-3))  # horário de Brasília, sem horário de verão desde 2019
_FORMATO_DATA = "%d/%m/%Y %H:%M:%S"
# shortcut: só o 0 (presencial) foi confirmado na captura; 1, 2 e 3 seguem a ordem do site
# (apêndice 3.1). Trocar quando uma vaga com cada valor for conferida.
_MODALIDADES = {0: "presencial", 1: "remoto", 2: "presencial ou remoto", 3: "hibrido"}


class _NaoEncontrado(Exception):
    """404: o `label` não existe (decisão 3: chega como `ErroDeRede` com status 404)."""


class _FormatoMudou(Exception):
    """A resposta não tem a forma conhecida, ou nenhuma vaga dela é legível."""


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


def _locais(valor: object) -> tuple[str, ...]:
    """`[cidade, UF, país]` vira um local; o texto "Não informado" não é local."""
    if not isinstance(valor, list):
        return ()
    partes = [p for p in map(_texto, valor) if p]
    return (", ".join(partes),) if partes else ()


def _data(valor: object) -> datetime | None:
    """ "dd/mm/aaaa hh:mm:ss" no horário de Brasília (confirmado pelo JSON-LD da página)."""
    if not isinstance(valor, str):
        return None
    try:
        return datetime.strptime(valor, _FORMATO_DATA).replace(tzinfo=_FUSO)
    except ValueError:
        return None


def _vaga(escopo: str, departamento: str, item: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(item, dict):
        return None
    titulo, empresa = _texto(item.get("title")), _texto(item.get("company_name"))
    url = _http(item.get("public_link"))
    if not titulo or not empresa or url is None:
        return None
    id_externo, remote = item.get("id"), item.get("remote")
    regime = _texto(item.get("regime"))
    return VagaColetada(
        fonte="recrutei",
        escopo=escopo,
        url=url,
        titulo=titulo,
        empresa=empresa,
        descricao_formato="html",
        id_externo=str(id_externo)
        if isinstance(id_externo, int | str) and not isinstance(id_externo, bool)
        else None,
        locais=_locais(item.get("location")),
        modalidade_declarada=_MODALIDADES.get(remote)
        if isinstance(remote, int) and not isinstance(remote, bool)
        else None,
        contrato_declarado=None if regime.lower() == "não informado" else regime or None,
        salario_texto=_texto(item.get("salary")) or None,
        etiquetas=(departamento,) if departamento else (),
    )


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, int]:
    """As vagas legíveis, quantas foram puladas e o total que a resposta declara."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    corpo = dados.get("data") if isinstance(dados, dict) else None
    total = corpo.get("total") if isinstance(corpo, dict) else None
    departamentos = corpo.get("vacancies") if isinstance(corpo, dict) else None
    if not isinstance(total, int) or isinstance(total, bool) or not isinstance(departamentos, list):
        raise _FormatoMudou
    vagas: list[VagaColetada] = []
    pulados = 0
    for dep in departamentos:
        itens = dep.get("items") if isinstance(dep, dict) else None
        if not isinstance(itens, list):
            raise _FormatoMudou
        nome = _texto(dep.get("department"))
        lidas = [_vaga(escopo, nome, i) for i in itens]
        vagas += [v for v in lidas if v is not None]
        pulados += lidas.count(None)
    if not vagas and (pulados or total):
        raise _FormatoMudou
    return vagas, pulados, total


def _no_host_das_vagas(url: str) -> bool:
    partes = urlsplit(url)
    return partes.scheme == "https" and partes.netloc.lower() == _HOST_VAGAS


class Recrutei:
    chave: str = "recrutei"
    nome: str = "Recrutei"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = (_HOST_API, _HOST_VAGAS)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return list(dict.fromkeys(e.identificador for e in ctx.empresas))

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        pulados = faltam = 0

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, faltam
            url = _API.format(label=quote(escopo, safe=""))
            try:
                resposta = await http.pedir("POST", url, corpo_json={})  # 202 também é sucesso
            except ErroDeRede as erro:
                if erro.status == 404:
                    raise _NaoEncontrado from erro
                raise
            if resposta.status == 304:
                yield SEM_MUDANCA  # o próprio objeto: `juntar_paginas` compara por identidade
                return
            vagas, pulados, total = _ler(escopo, resposta.texto)
            faltam = total - len(vagas) - pulados
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
        if resultado.estado != "ok":
            return resultado
        # shortcut: a contagem não vai no motivo (não há chave `saude.*` com `n`; D45).
        if pulados:
            motivo = "saude.formato_mudou"
        elif faltam > 0:
            motivo = "saude.listagem_incompleta"  # a resposta declara mais vagas do que trouxe
        else:
            return resultado
        return ResultadoEscopo(resultado.vagas, "parcial", motivo, resultado.pedidos)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """Completa a vaga com o HTML dela (`__NEXT_DATA__`); `None` se não houver o que somar.

        Só busca no host das vagas: o endereço vem da resposta da fonte. A `url` e o resto da
        lista ficam como estão (a URL é a chave da vaga). Vaga encerrada (`error`) dá `None`.
        """
        if not isinstance(item, VagaColetada) or not _no_host_das_vagas(item.url):
            return None
        try:
            resposta = await http.pedir("GET", item.url)
        except ErroDeRede as erro:
            if erro.status == 404:  # a vaga fechou entre a lista e o detalhe
                return None
            raise
        achado = _NEXT_DATA.search(resposta.texto)
        try:
            dados = json.loads(achado.group(1)) if achado else None
        except ValueError:
            return None
        paginas = dados.get("props") if isinstance(dados, dict) else None
        paginas = paginas.get("pageProps") if isinstance(paginas, dict) else None
        retorno = paginas.get("retorno") if isinstance(paginas, dict) else None
        vaga = retorno.get("vacancy") if isinstance(retorno, dict) else None
        if not isinstance(retorno, dict) or retorno.get("error") or not isinstance(vaga, dict):
            return None
        corpo = _texto(vaga.get("description"))
        if not corpo:
            return None
        beneficios = _texto(vaga.get("benefits"))
        habilidades = (h.strip() for h in _texto(vaga.get("skills")).split(","))
        prazo = _data(vaga.get("expired_at"))
        return replace(
            item,
            descricao=corpo + (f"<h2>Benefícios</h2>{beneficios}" if beneficios else ""),
            publicada_em=_data(vaga.get("published_at")) or item.publicada_em,
            prazo=prazo.date() if prazo else item.prazo,
            etiquetas=tuple(dict.fromkeys([*item.etiquetas, *filter(None, habilidades)])),
        )

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o `label` ou o endereço do quadro e devolve o `label`; não faz pedido.

        `ValueError` se não for um quadro da Recrutei. A caixa fica como veio.
        """
        texto = identificador.strip()
        label = texto
        if "/" in texto or "." in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            caminho = [p for p in partes.path.split("/") if p]
            host = (partes.hostname or "").lower()
            if partes.scheme not in ("http", "https"):
                raise ValueError(f"endereço não é http/https: {identificador!r}")
            if host == _HOST_VAGAS and caminho:
                label = caminho[0]
            elif host == _HOST_API and caminho[:4] == ["api", "v2", "vacancies", "per-departments"]:
                label = caminho[4] if len(caminho) > 4 else ""
            else:
                raise ValueError(f"não é um quadro da Recrutei: {identificador!r}")
        if not _LABEL.fullmatch(label):
            raise ValueError(f"identificador inválido: {identificador!r}")
        return {"identificador": label}


COLETOR = Recrutei()
