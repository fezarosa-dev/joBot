"""Coletor Sólides (apêndice 3.1): API do portal de vagas, um escopo por empresa.

O escopo é o slug, que é o subdomínio de `{slug}.vagas.solides.com.br`. A lista já traz a
descrição: não há `detalhar`. A API não é documentada.
"""

import json
import re
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
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
from jobot.nucleo.modelo import SalarioBruto, VagaColetada

_LIMITES = limites("solides")
_HOST_API = "apigw.solides.com.br"
_API = f"https://{_HOST_API}/jobs/v3/companies/{{slug}}/vacancies"
_SUFIXO_VAGAS = ".vagas.solides.com.br"
_LINK = "https://{slug}.vagas.solides.com.br/vaga/{id}"
_TAKE = 25  # máximo que a API aceita (apêndice 3.1)
# shortcut: `fontes.json` não limita os pedidos desta fonte (`max_pedidos` nulo), então o teto
# de páginas fica aqui. Trocar quando a fonte ganhar um `max_pedidos` próprio (R4, `duvidas`).
MAX_PAGINAS = 200
# Rótulo de DNS: 1 a 63 letras, dígitos e hífen, sem hífen nas pontas.
_SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.ASCII | re.IGNORECASE)
_BRASILIA = timezone(timedelta(hours=-3))


class _NaoEncontrado(Exception):
    """404: a empresa não existe (chega como `ErroDeRede` com status 404)."""


class _FormatoMudou(Exception):
    """A resposta não traz a lista `data`, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _valor(valor: object) -> int | float | None:
    """Um valor de faixa: número positivo e finito; zero é "sem valor"."""
    if not isinstance(valor, int | float) or isinstance(valor, bool):
        return None
    # A comparação entre int e float é exata: um inteiro enorme não estoura aqui.
    return valor if 0 < valor <= sys.float_info.max else None


def _salario(faixa: object) -> SalarioBruto | None:
    if not isinstance(faixa, dict):
        return None
    if faixa.get("negotiable") is True or faixa.get("showRangeToApplicant") is False:
        return None
    minimo, maximo = _valor(faixa.get("initialRange")), _valor(faixa.get("finalRange"))
    if minimo is None and maximo is None:
        return None
    # A Sólides só opera no Brasil e a faixa não traz moeda nem período.
    return SalarioBruto(moeda="BRL", minimo_unidades=minimo, maximo_unidades=maximo)


def _publicada(valor: object) -> datetime | None:
    """`createdAt` vem só com a data (`2026-11-10`): meia-noite em Brasília."""
    try:
        lida = datetime.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None
    if lida is not None and lida.utcoffset() is None:
        lida = lida.replace(tzinfo=_BRASILIA)
    return lida


def _prazo(valor: object) -> date | None:
    if not isinstance(valor, dict) or not isinstance(valor.get("due"), str):
        return None
    try:
        return datetime.fromisoformat(valor["due"]).date()
    except ValueError:
        return None


def _nomes(valor: object) -> tuple[str, ...]:
    """Os `name` de uma lista de objetos (`seniority`, `recruitmentContractType`)."""
    if not isinstance(valor, list):
        return ()
    nomes = (_texto(i.get("name")) for i in valor if isinstance(i, dict))
    return tuple(dict.fromkeys(filter(None, nomes)))


def _local(job: dict[str, object]) -> tuple[str, ...]:
    cidade, estado = job.get("city"), job.get("state")
    nome = _texto(cidade.get("name")) if isinstance(cidade, dict) else ""
    uf = _texto(estado.get("code")) if isinstance(estado, dict) else ""
    return (f"{nome}, {uf}" if uf else nome,) if nome else ()


def _id(valor: object) -> str | None:
    if isinstance(valor, int) and not isinstance(valor, bool):
        return str(valor)
    return _texto(valor) or None


def _vaga(escopo: str, job: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(job, dict):
        return None
    id_externo, titulo = _id(job.get("id")), _texto(job.get("title"))
    if id_externo is None or not titulo:
        return None
    contratos = _nomes(job.get("recruitmentContractType"))
    modalidade = _texto(job.get("jobType")) or ("remoto" if job.get("homeOffice") is True else None)
    return VagaColetada(
        fonte="solides",
        escopo=escopo,
        # `redirectLink` vem quebrado (`https://diefra./...`): o link é montado.
        url=_LINK.format(slug=escopo.lower(), id=quote(id_externo, safe="")),
        titulo=titulo,
        empresa=_texto(job.get("companyName")) or escopo,
        descricao_formato="html",
        descricao=_texto(job.get("description")),
        id_externo=id_externo,
        locais=_local(job),
        modalidade_declarada=modalidade,
        contrato_declarado=contratos[0] if len(contratos) == 1 else None,
        salario_estruturado=_salario(job.get("salary")),
        publicada_em=_publicada(job.get("createdAt")),
        prazo=_prazo(job.get("date")),
        etiquetas=_nomes(job.get("seniority")),
    )


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, int, int | None]:
    """Vagas legíveis, quantas foram puladas, quantas vieram e `totalPages` (se for válido)."""
    try:
        corpo = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    if not isinstance(corpo, dict) or not isinstance(corpo.get("data"), list):
        raise _FormatoMudou
    jobs: list[object] = corpo["data"]
    vagas = [v for v in (_vaga(escopo, j) for j in jobs) if v is not None]
    if jobs and not vagas:
        raise _FormatoMudou
    total = corpo.get("totalPages")
    valido = isinstance(total, int) and not isinstance(total, bool) and total >= 0
    return vagas, len(jobs) - len(vagas), len(jobs), total if valido else None


class Solides:
    chave: str = "solides"
    nome: str = "Sólides"
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
        if not _SLUG.fullmatch(escopo):  # o slug vira host do link: nada além de um rótulo
            return ResultadoEscopo((), "falhou", "saude.empresa_nao_encontrada", pedidos)
        pulados = 0
        truncou = False

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, truncou
            pagina = 1
            while True:
                params = {"page": str(pagina), "take": str(_TAKE)}
                try:
                    resposta = await http.pedir("GET", _API.format(slug=escopo), params=params)
                except ErroDeRede as erro:
                    if erro.status == 404:
                        raise _NaoEncontrado from erro
                    raise
                try:
                    vagas, ruins, itens, total = _ler(escopo, resposta.texto)
                except _FormatoMudou:
                    if pagina == 1:
                        raise
                    pulados += 1  # as páginas anteriores ficam
                    return
                pulados += ruins
                yield vagas
                if itens == 0:
                    return
                if total is None:
                    # Sem total e com a página cheia não há como saber se vem mais.
                    pulados += itens >= _TAKE
                    return
                if pagina >= total:
                    return
                if pagina >= MAX_PAGINAS:
                    truncou = True
                    return
                pagina += 1

        try:
            resultado = await juntar_paginas(http, paginas())
        except (_NaoEncontrado, _FormatoMudou) as erro:
            motivo = (
                "saude.empresa_nao_encontrada"
                if isinstance(erro, _NaoEncontrado)
                else "saude.formato_mudou"
            )
            return ResultadoEscopo((), "falhou", motivo, getattr(http, "pedidos", 0))
        if resultado.estado == "ok" and (truncou or pulados):
            # shortcut: a contagem de pulados não vai no motivo (D45, como no Lever).
            motivo = "saude.limite_atingido" if truncou else "saude.formato_mudou"
            return ResultadoEscopo(resultado.vagas, "parcial", motivo, resultado.pedidos)
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz a descrição: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Aceita o slug ou o endereço do quadro da empresa e devolve o slug; não faz pedido.

        O slug sai em minúsculas (é subdomínio, D45). `ValueError` se não for da Sólides.
        """
        texto = identificador.strip()
        slug = texto
        if "/" in texto or "." in texto or ":" in texto:
            partes = urlsplit(texto if "://" in texto else f"https://{texto}")
            if partes.scheme not in ("http", "https"):
                raise ValueError(f"endereço não é http/https: {identificador!r}")
            host = (partes.hostname or "").lower()
            caminho = [p for p in partes.path.split("/") if p]
            if host.endswith(_SUFIXO_VAGAS):
                slug = host.removesuffix(_SUFIXO_VAGAS)
            elif host == _HOST_API and caminho[:3] == ["jobs", "v3", "companies"]:
                slug = caminho[3] if len(caminho) > 3 else ""
            else:
                raise ValueError(f"não é um quadro da Sólides: {identificador!r}")
        if not _SLUG.fullmatch(slug):
            raise ValueError(f"identificador inválido: {identificador!r}")
        return {"identificador": slug.lower()}


COLETOR = Solides()
