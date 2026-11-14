"""Coletor CIEE (apêndice 3.2): vitrine de vagas de estágio e aprendiz, um escopo por modalidade.

A API é a mesma que a página pública chama, em páginas Spring (`content[]`, `last`) de 1.000
vagas. A lista já traz tudo, menos título e data: o título sai de área e nível, e a data em que
o joBot viu a vaga pela primeira vez é a da ocorrência (`publicada_em` fica vazio). Sem
`ETag` nem `Last-Modified` na resposta: nenhum pedido condicional, então nunca há 304.
"""

import json
import re
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Literal

from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Estado,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    juntar_paginas,
)
from jobot.nucleo.coletores.registro import limites
from jobot.nucleo.http import HttpEducado
from jobot.nucleo.modelo import Periodo, SalarioBruto, VagaColetada

_LIMITES = limites("ciee")
_API = "https://api.ciee.org.br/vagas/vitrine-vaga/publicadas"
_LINK = "https://portal.ciee.org.br/quero-uma-vaga/?codigoVaga={}"
_TAMANHO = 1000
_MAX_PAGINAS = 30  # 6 páginas hoje; o teto só segura uma API que nunca diz `last`
_TIPOS = {"ESTAGIO": "Estágio", "APRENDIZ": "Aprendiz"}
_NIVEIS = {"SU": "Superior", "EM": "Médio", "TE": "Técnico", "T": "Técnico", "EF": "Fundamental"}
_PERIODOS: dict[str, Periodo] = {"Mensal": "mes", "Hora": "hora"}
_HORA = re.compile(r"\d{2}:\d{2}")


class _FormatoMudou(Exception):
    """A resposta não traz a lista `content`, ou nenhuma vaga dela é legível."""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _lista(valor: object) -> list[object]:
    return valor if isinstance(valor, list) else []


def _valor(valor: object) -> float | None:
    """Número positivo e finito, como a fonte mandou (inteiro continua inteiro)."""
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    # Comparar com o maior float evita converter inteiro gigante (OverflowError); nan/inf caem.
    return valor if 0 < valor <= sys.float_info.max else None


def _codigo(valor: object) -> str | None:
    """O `codigoVaga` (inteiro, ou texto só de dígitos: ele entra na URL), ou `None`."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        return str(valor) if valor > 0 else None
    if isinstance(valor, str) and valor.isascii() and valor.isdigit():
        return valor
    return None


def _titulo(tipo: str, item: Mapping[str, object]) -> str:
    area = _texto(item.get("areaProfissional")) or _texto(item.get("areaAtuacao"))
    nivel = _NIVEIS.get(_texto(item.get("nivelEscolar")), "")
    if nivel.lower() in area.lower():  # "Ensino Médio" já diz "Médio"
        nivel = ""
    return " - ".join(filter(None, [tipo, area, nivel]))


def _local(item: Mapping[str, object]) -> tuple[str, ...]:
    local = item.get("local")
    if not isinstance(local, dict):
        return ()
    juntos = ", ".join(filter(None, [_texto(local.get("cidade")), _texto(local.get("uf"))]))
    return (juntos,) if juntos else ()


def _salario(item: Mapping[str, object]) -> SalarioBruto | None:
    """Valor fixo (`bolsaAuxilio` ou `salario`) ou, sem ele, a faixa De/Ate; sempre em BRL."""
    fixo = _valor(item.get("bolsaAuxilio")) or _valor(item.get("salario"))
    maximo: float | None = None
    minimo: float | None = fixo
    if fixo is None:
        minimo = _valor(item.get("bolsaAuxilioDe")) or _valor(item.get("salarioDe"))
        maximo = _valor(item.get("bolsaAuxilioAte")) or _valor(item.get("salarioAte"))
    if minimo is None and maximo is None:
        return None
    periodo = _PERIODOS.get(_texto(item.get("tipoAuxilioBolsa"))) or _PERIODOS.get(
        _texto(item.get("tipoSalario"))
    )
    return SalarioBruto(
        moeda="BRL", minimo_unidades=minimo, maximo_unidades=maximo, periodo=periodo
    )


def _semestre(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0 else None


def _descricao(item: Mapping[str, object]) -> str:
    partes: list[str] = []
    atividades = [a for a in map(_texto, _lista(item.get("atividades"))) if a]
    if atividades:
        partes.append("Atividades:\n" + "\n".join(f"- {a}" for a in atividades))
    if ramo := _texto(item.get("descricao")):
        partes.append(f"Ramo da empresa: {ramo}")
    beneficios = [
        b
        for b in (
            _texto(x.get("beneficio"))
            for x in _lista(item.get("beneficios"))
            if isinstance(x, dict)
        )
        if b
    ]
    if beneficios:
        partes.append("Benefícios: " + "; ".join(beneficios))
    entrada, saida = (_HORA.match(_texto(item.get(c))) for c in ("horarioEntrada", "horarioSaida"))
    if entrada and saida:
        partes.append(f"Horário: {entrada.group()} às {saida.group()}")
    requisitos = item.get("requisitos")
    if isinstance(requisitos, dict):
        de, ate = (
            _semestre(requisitos.get("semestreInicio")),
            _semestre(requisitos.get("semestreFinal")),
        )
        if de and ate:
            faixa = f"{de}º semestre" if de == ate else f"{de}º ao {ate}º semestre"
            partes.append(f"Semestres exigidos: {faixa}")
    return "\n\n".join(partes)


def _vaga(escopo: str, item: object) -> VagaColetada | None:
    """Uma vaga da lista, ou `None` se faltar campo obrigatório (DR-08)."""
    if not isinstance(item, dict):
        return None
    codigo, empresa = _codigo(item.get("codigoVaga")), _texto(item.get("nomeEmpresa"))
    if codigo is None or not empresa:
        return None
    # a página sem filtro mistura as modalidades: o tipo do item vale mais que o do escopo
    tipo = _TIPOS.get(_texto(item.get("tipoVaga")), _TIPOS[escopo])
    return VagaColetada(
        fonte="ciee",
        escopo=escopo,
        url=_LINK.format(codigo),
        titulo=_titulo(tipo, item),
        empresa=empresa,
        descricao_formato="texto",
        descricao=_descricao(item),
        id_externo=codigo,
        locais=_local(item),
        contrato_declarado=tipo,
        salario_estruturado=_salario(item),
    )


def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, int, bool | None]:
    """(vagas, puladas por formato, itens na página, `last` ou `None` se não for booleano)."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _FormatoMudou from erro
    itens = dados.get("content") if isinstance(dados, dict) else None
    if not isinstance(itens, list):
        raise _FormatoMudou
    vagas = [v for v in (_vaga(escopo, i) for i in itens) if v is not None]
    if itens and not vagas:
        raise _FormatoMudou
    ultima = dados.get("last")
    return vagas, len(itens) - len(vagas), len(itens), ultima if isinstance(ultima, bool) else None


class Ciee:
    chave: str = "ciee"
    nome: str = "CIEE"
    leva: Literal["A", "B"] = _LIMITES.leva
    hosts: tuple[str, ...] = ("api.ciee.org.br",)
    credito_obrigatorio: bool = _LIMITES.credito_obrigatorio
    intervalo_min: int | None = _LIMITES.intervalo_min
    max_pedidos: int | None = _LIMITES.max_pedidos
    espera_s: float = _LIMITES.espera_s
    por_escopo: Mapping[str, LimiteEscopo] = _LIMITES.por_escopo

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return list(_TIPOS)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        if escopo not in _TIPOS:
            raise ValueError(f"escopo inválido: {escopo!r}")
        pulados = 0
        parada: tuple[Estado, str] | None = None

        async def paginas() -> AsyncIterator[Sequence[Item]]:
            nonlocal pulados, parada
            for n in range(_MAX_PAGINAS):
                params = {
                    "page": str(n),
                    "size": str(_TAMANHO),
                    "sort": "codigoVaga,desc",
                    "tipoVaga": escopo,
                }
                resposta = await http.pedir("GET", _API, params=params)
                try:
                    vagas, ruins, itens, ultima = _ler(escopo, resposta.texto)
                except _FormatoMudou:
                    if n == 0:
                        raise
                    parada = ("parcial", "saude.formato_mudou")  # as páginas lidas ficam
                    return
                pulados += ruins
                yield vagas
                if ultima:
                    return
                if ultima is None or itens == 0:  # sem `last` ou sem fim à vista: não repete
                    parada = ("parcial", "saude.formato_mudou")
                    return
            parada = ("parcial", "saude.limite_atingido")

        try:
            resultado = await juntar_paginas(http, paginas())
        except _FormatoMudou:
            pedidos: int = getattr(http, "pedidos", 0)  # como em `juntar_paginas`
            return ResultadoEscopo((), "falhou", "saude.formato_mudou", pedidos)
        if resultado.estado != "ok":
            return resultado
        if parada is not None:
            return ResultadoEscopo(resultado.vagas, *parada, resultado.pedidos)
        if pulados:
            # shortcut: a contagem de pulados não vai no motivo (D45, como no Gupy).
            return ResultadoEscopo(
                resultado.vagas, "parcial", "saude.formato_mudou", resultado.pedidos
            )
        return resultado

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        """A lista já traz tudo o que a fonte tem: nada a detalhar."""
        return None

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        """Fonte sem cadastro de empresa: os escopos são as duas modalidades."""
        raise ValueError(f"ciee não tem empresa a resolver: {identificador!r}")


COLETOR = Ciee()
