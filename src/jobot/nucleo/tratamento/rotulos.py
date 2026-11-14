"""Rótulos por regra (desenho 10.4): área, nível, modalidade, contrato e avisos.

As regras ficam em `nucleo/dados/rotulos.json` (como funcionam: chave "sobre" do arquivo).
"""

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from jobot.nucleo.modelo import Area, Aviso, Contrato, Local, Modalidade, Nivel, VagaColetada
from jobot.nucleo.texto import normalizar

ARQUIVO = Path(__file__).parent.parent / "dados" / "rotulos.json"

_ENUMS: dict[str, type[StrEnum]] = {
    "area": Area,
    "nivel": Nivel,
    "modalidade": Modalidade,
    "contrato": Contrato,
    "avisos": Aviso,
}


@dataclass(frozen=True, kw_only=True)
class Rotulos:
    area: Area
    nivel: Nivel
    modalidade: Modalidade
    contrato: Contrato
    avisos: tuple[Aviso, ...] = ()


@dataclass(frozen=True, kw_only=True)
class _Regra:
    valor: str
    onde: tuple[str, ...]
    peso: int
    padroes: tuple[re.Pattern[str], ...]


def versao_de(bruto: bytes) -> str:
    """Hash dos bytes do arquivo de regras: muda quando o JSON muda (dispara o reprocessar).

    Mudança de lógica aqui em rotulos.py não muda o hash: suba "versao_algoritmo" no JSON.
    """
    return hashlib.sha256(bruto).hexdigest()


def _termo(termo: str) -> str:
    # palavra inteira; só (?:...), que Python e JavaScript leem igual. Escapa só a sintaxe:
    # o "\-" e o "\ " do re.escape o JavaScript com a flag u recusa.
    escapado = re.sub(r"[.*+?^${}()|[\]\\/]", r"\\\g<0>", normalizar(termo))
    return r"(?:^|[^a-z0-9])" + escapado + r"(?:[^a-z0-9]|$)"


def _regras(nome: str, secao: Mapping[str, Any]) -> tuple[_Regra, ...]:
    regras = []
    for r in secao["regras"]:
        _ENUMS[nome](r["valor"])  # valor fora do enum falha ao carregar, não ao rotular
        padroes = [_termo(t) for t in r.get("termos", ())] + list(r.get("expressoes", ()))
        regras.append(
            _Regra(
                valor=r["valor"],
                onde=tuple(r["onde"]),
                peso=r.get("peso", 1),
                padroes=tuple(re.compile(p) for p in padroes),
            )
        )
    return tuple(regras)


_BRUTO = ARQUIVO.read_bytes()
VERSAO_REGRAS = versao_de(_BRUTO)
_DADOS: dict[str, Any] = json.loads(_BRUTO)
_PESOS_CAMPO: dict[str, int] = _DADOS["pesos_campo"]
_REGRAS = {nome: _regras(nome, _DADOS[nome]) for nome in _ENUMS}


def _pontos(regra: _Regra, campos: Mapping[str, str]) -> int:
    return max(
        (
            regra.peso * _PESOS_CAMPO[campo]
            for campo in regra.onde
            if any(p.search(campos[campo]) for p in regra.padroes)
        ),
        default=0,
    )


def _escolher(nome: str, campos: Mapping[str, str], vale: Callable[[str], bool]) -> str:
    """Valor com mais pontos; no empate, a regra que vem antes no JSON."""
    melhor, pontos = _DADOS[nome]["padrao"], 0
    for regra in _REGRAS[nome]:
        if vale(regra.valor):
            p = _pontos(regra, campos)
            if p > pontos:
                melhor, pontos = regra.valor, p
    return str(melhor)


def _declarado(nome: str, declarado: str | None) -> str | None:
    if declarado is None:
        return None
    valor: str | None = _DADOS[nome]["declarados"].get(normalizar(declarado))
    return valor


def rotular(v: VagaColetada, texto: str, locais: Sequence[Local]) -> Rotulos:
    """`texto` é a descrição já em texto puro; `locais` já lidos (desenho 10.4)."""
    campos = {
        "titulo": normalizar(v.titulo),
        "etiquetas": normalizar(" ; ".join(v.etiquetas)),
        "local": normalizar(" ; ".join(v.locais)),  # texto cru da fonte ("Remote - US only")
        "descricao": normalizar(texto),
    }
    # uf só conta como Brasil quando o país veio vazio
    no_brasil = any(local.pais == "BR" or (local.pais is None and local.uf) for local in locais)
    # clt e pj são do Brasil (D5): só local com país de fora os barra; sem país, vale o texto
    fora = any(local.pais not in (None, "BR") for local in locais)
    so_no_brasil = set(_DADOS["contrato"]["so_no_brasil"])

    def contrato_vale(valor: str) -> bool:
        return no_brasil or not fora or valor not in so_no_brasil

    def todos(_: str) -> bool:
        return True

    modalidade = _declarado("modalidade", v.modalidade_declarada) or _escolher(
        "modalidade", campos, todos
    )
    contrato = _declarado("contrato", v.contrato_declarado)
    if contrato is None or not contrato_vale(contrato):
        contrato = _escolher("contrato", campos, contrato_vale)
    avisos = dict.fromkeys(r.valor for r in _REGRAS["avisos"] if _pontos(r, campos))
    return Rotulos(
        area=Area(_escolher("area", campos, todos)),
        nivel=Nivel(_escolher("nivel", campos, todos)),
        modalidade=Modalidade(modalidade),
        contrato=Contrato(contrato),
        avisos=tuple(Aviso(a) for a in avisos),
    )
