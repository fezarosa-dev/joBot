"""Encaixe por regras e ocultação (desenho 11.2 e 11.3). Puro: dinheiro chega em reais inteiros."""

import json
import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any, Literal

from jobot.nucleo.modelo import (
    Aviso,
    Busca,
    Encaixe,
    Local,
    Modalidade,
    Motivo,
    Nivel,
    VagaTratada,
)
from jobot.nucleo.texto import normalizar

# critério preenchido: (pontos obtidos, peso do critério, motivo)
_Parte = tuple[int, int, Motivo]


@cache
def _dados() -> dict[str, Any]:
    texto = (Path(__file__).parent / "dados" / "encaixe.json").read_text(encoding="utf-8")
    dados: dict[str, Any] = json.loads(texto)
    return dados


def _arredondar(pontos: int, soma: int) -> int:
    """100 × pontos ÷ soma, para o inteiro mais próximo; metade sobe (DP5)."""
    return (200 * pontos + soma) // (2 * soma)


def _tem(texto: str, palavra: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(palavra)}(?!\w)", texto) is not None


def _cargo(v: VagaTratada, b: Busca) -> _Parte | None:
    palavras = [(o, n) for o, n in ((c.strip(), normalizar(c)) for c in b.cargos) if n]
    if not palavras:
        return None
    pontos, peso = _dados()["pontos"], _dados()["pesos"]["cargo"]
    titulo = normalizar(v.titulo)
    for o, p in palavras:
        if _tem(titulo, p):
            return (
                pontos["cargo_titulo"],
                peso,
                Motivo(chave="encaixe.cargo_titulo", params={"palavra": o}),
            )
    descricao = normalizar(v.descricao_texto)
    for o, p in palavras:
        if _tem(descricao, p):
            return (
                pontos["cargo_descricao"],
                peso,
                Motivo(chave="encaixe.cargo_descricao", params={"palavra": o}),
            )
    return 0, peso, Motivo(chave="encaixe.cargo_ausente")


def _mesma_cidade(a: Local, b: Local) -> bool:
    if not a.cidade or not b.cidade or normalizar(a.cidade) != normalizar(b.cidade):
        return False
    return not (a.uf and b.uf) or a.uf.upper() == b.uf.upper()


def _mesma_uf(a: Local, b: Local) -> bool:
    return bool(a.uf and b.uf and a.uf.upper() == b.uf.upper())


def _local(v: VagaTratada, b: Busca) -> _Parte | None:
    if not b.cidades and not b.modalidades:
        return None
    pontos, peso = _dados()["pontos"], _dados()["pesos"]["local"]
    # modalidades vazias: critério neutro (D20), remoto não perde por "local fora"
    if v.modalidade == Modalidade.REMOTO and (
        not b.modalidades or Modalidade.REMOTO in b.modalidades
    ):
        return pontos["local_remoto"], peso, Motivo(chave="encaixe.local_remoto")
    conhecida = v.modalidade != Modalidade.NAO_INFORMADO
    if b.modalidades and conhecida and v.modalidade not in b.modalidades:
        return 0, peso, Motivo(chave="encaixe.modalidade_fora")
    if not b.cidades:  # só modalidade escolhida
        if conhecida:
            return pontos["modalidade_ok"], peso, Motivo(chave="encaixe.modalidade_ok")
        return (
            pontos["modalidade_nao_informada"],
            peso,
            Motivo(chave="encaixe.modalidade_nao_informada"),
        )
    if any(_mesma_cidade(c, loc) for c in b.cidades for loc in v.locais):
        return pontos["local_cidade"], peso, Motivo(chave="encaixe.local_cidade")
    if any(_mesma_uf(c, loc) for c in b.cidades for loc in v.locais):
        return pontos["local_uf"], peso, Motivo(chave="encaixe.local_uf")
    return 0, peso, Motivo(chave="encaixe.local_fora")


def _nivel(v: VagaTratada, b: Busca) -> _Parte | None:
    if not b.niveis:
        return None
    pontos, peso = _dados()["pontos"], _dados()["pesos"]["nivel"]
    if v.nivel == Nivel.NAO_INFORMADO:
        return pontos["nivel_nao_informado"], peso, Motivo(chave="encaixe.nivel_nao_informado")
    if v.nivel in b.niveis:
        return pontos["nivel_ok"], peso, Motivo(chave="encaixe.nivel_ok")
    return 0, peso, Motivo(chave="encaixe.nivel_fora")


def _salario_comparavel(v: VagaTratada, sal_mensal_brl: int | None) -> int | None:
    """Salário mensal em reais, só quando a vaga o traz, é plausível e há cotação."""
    if v.salario is None or not v.salario.plausivel:
        return None
    return sal_mensal_brl


def _salario(
    v: VagaTratada, b: Busca, sal_mensal_brl: int | None, minimo_busca_brl: int | None
) -> _Parte | None:
    if b.salario_min_centavos is None:
        return None
    pontos, peso = _dados()["pontos"], _dados()["pesos"]["salario"]
    sal = _salario_comparavel(v, sal_mensal_brl)
    # mínimo da busca sem cotação: critério preenchido, nota neutra (desenho, seção 10)
    if sal is None or minimo_busca_brl is None:
        return pontos["salario_neutro"], peso, Motivo(chave="encaixe.salario_nao_informado")
    if sal >= minimo_busca_brl:
        return pontos["salario_ok"], peso, Motivo(chave="encaixe.salario_ok")
    return 0, peso, Motivo(chave="encaixe.salario_abaixo")


def _idioma(v: VagaTratada, b: Busca) -> _Parte | None:
    if not b.idiomas:
        return None
    pontos, peso = _dados()["pontos"], _dados()["pesos"]["idioma"]
    if v.idioma in b.idiomas:
        return pontos["idioma_ok"], peso, Motivo(chave="encaixe.idioma_ok")
    if v.idioma == "outro":
        return pontos["idioma_nao_detectado"], peso, Motivo(chave="encaixe.idioma_nao_detectado")
    return 0, peso, Motivo(chave="encaixe.idioma_fora")


def _pais_da_pessoa(b: Busca) -> set[str]:
    return {c.pais.upper() for c in b.cidades if c.pais} or {"BR"}


def _regra_que_bate(
    v: VagaTratada, b: Busca, sal_mensal_brl: int | None, minimo_busca_brl: int | None
) -> list[str]:
    """Ids das regras de ocultar que batem, na ordem do desenho 11.3."""
    bate: list[tuple[str, bool]] = []
    conhecida = v.modalidade != Modalidade.NAO_INFORMADO
    bate.append(
        ("modalidade", bool(b.modalidades) and conhecida and v.modalidade not in b.modalidades)
    )
    bate.append(
        ("nivel", bool(b.niveis) and v.nivel != Nivel.NAO_INFORMADO and v.nivel not in b.niveis)
    )
    sal = _salario_comparavel(v, sal_mensal_brl)
    bate.append(
        ("salario", minimo_busca_brl is not None and sal is not None and sal < minimo_busca_brl)
    )
    bate.append(("idioma", bool(b.idiomas) and v.idioma != "outro" and v.idioma not in b.idiomas))
    paises = {loc.pais.upper() for loc in v.locais if loc.pais}
    bate.append(
        (
            "pais",
            v.modalidade == Modalidade.REMOTO
            and Aviso.RESTRITO_A_PAIS in v.avisos
            and bool(paises)
            and paises.isdisjoint(_pais_da_pessoa(b)),
        )
    )
    return [regra for regra, bateu in bate if bateu]


def _faixa(nota: int) -> Literal["bom", "medio", "fraco"]:
    faixas = _dados()["faixas"]
    return (
        "bom" if nota >= faixas["bom_min"] else "medio" if nota >= faixas["medio_min"] else "fraco"
    )


def calcular(
    v: VagaTratada,
    b: Busca,
    *,
    sal_mensal_brl: int | None,
    minimo_busca_brl: int | None,
    regras_ligadas: bool,
) -> Encaixe:
    """Nota, motivos e ocultação de uma vaga para uma busca.

    `sal_mensal_brl` e `minimo_busca_brl` em reais inteiros (None = sem cotação ou sem dado).
    """
    partes = [
        p
        for p in (
            _cargo(v, b),
            _local(v, b),
            _nivel(v, b),
            _salario(v, b, sal_mensal_brl, minimo_busca_brl),
            _idioma(v, b),
        )
        if p is not None
    ]
    oculta: str | None = None
    if regras_ligadas:
        ligadas: Mapping[str, bool] = b.regras_ocultar
        oculta = next(
            (
                r
                for r in _regra_que_bate(v, b, sal_mensal_brl, minimo_busca_brl)
                if ligadas.get(r, True)
            ),
            None,
        )
    motivos = tuple(m for _, _, m in partes)
    if not partes:
        return Encaixe(nota=None, nivel=None, motivos=motivos, oculta_motivo=oculta)
    nota = _arredondar(sum(p for p, _, _ in partes), sum(w for _, w, _ in partes))
    return Encaixe(nota=nota, nivel=_faixa(nota), motivos=motivos, oculta_motivo=oculta)
