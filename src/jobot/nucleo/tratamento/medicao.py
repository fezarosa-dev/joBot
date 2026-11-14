"""Medição dos rótulos contra um gabarito (desenho 10.7). Puro: quem lê os arquivos é a CLI.

A amostra é só o que tem vaga e rótulo ao mesmo tempo; o resto fica fora de tudo, inclusive
da proporção de vagas no Brasil (DR-29).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from jobot.nucleo.modelo import FormatoDescricao, Local, VagaColetada, VagaTratada

ROTULOS = ("area", "nivel", "modalidade", "contrato", "avisos", "pais", "uf")


@dataclass(frozen=True, kw_only=True)
class Acerto:
    certos: int
    total: int


@dataclass(frozen=True, kw_only=True)
class Erro:
    id: str
    rotulo: str
    esperado: str
    obtido: str


@dataclass(frozen=True, kw_only=True)
class Esperado:
    area: str
    nivel: str
    modalidade: str
    contrato: str
    pais: str | None
    uf: str | None
    avisos: frozenset[str]


@dataclass(frozen=True, kw_only=True)
class Medicao:
    por_rotulo: Mapping[str, Acerto]
    erros: tuple[Erro, ...]
    proporcao_br: float  # 0 a 1; pais null conta no total, não em BR


def _texto(linha: Mapping[str, Any], chave: str) -> str:
    valor = linha.get(chave)
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise ValueError(f"{chave!r} precisa ser texto")
    return valor


# A captura antiga usava estes nomes de fonte; o produto usa os de `fontes.json`.
_NOMES_DA_CAPTURA: dict[str, str] = {
    "hackernews-whoishiring": "hn_algolia",
    "weworkremotely": "wwr",
    "iel_carreiras": "iel",
    "usp_fea": "usp",
    "usp_if": "usp",
    "google_careers": "google",
    "amazon_jobs": "amazon",
    "eightfold_bayer": "eightfold",
    "eightfold_mercadolibre": "eightfold",
    "workday_mastercard": "workday",
    "workday_santander": "workday",
}


def _fonte_do_produto(nome: str) -> str:
    # um repositório por nome na captura: "github-<repositório>" é o github_issues
    if nome.startswith("github-"):
        return "github_issues"
    return _NOMES_DA_CAPTURA.get(nome, nome)


def vaga_do_bruto(linha: Mapping[str, Any]) -> VagaColetada:
    """Uma linha de `bruto/*.jsonl` vira `VagaColetada`. `metadados` não é lido."""
    html = _texto(linha, "descricao_html")
    formato: FormatoDescricao = "html" if html else "texto"
    local = _texto(linha, "local")
    return VagaColetada(
        fonte=_fonte_do_produto(_texto(linha, "fonte")),
        escopo="",
        url=_texto(linha, "url"),
        titulo=_texto(linha, "titulo"),
        empresa=_texto(linha, "empresa"),
        descricao_formato=formato,
        descricao=html or _texto(linha, "descricao_texto"),
        locais=(local,) if local else (),
    )


def _rotulo(rotulos: Mapping[str, Any], chave: str) -> str:
    valor = rotulos.get(chave)
    if not isinstance(valor, str):
        raise ValueError(f"rótulo {chave!r} ausente ou fora do formato")
    return valor


def _opcional(rotulos: Mapping[str, Any], chave: str) -> str | None:
    valor = rotulos.get(chave)
    if valor is not None and not isinstance(valor, str):
        raise ValueError(f"rótulo {chave!r} precisa ser texto ou null")
    return valor


def esperado_da_linha(linha: Mapping[str, Any]) -> tuple[str, Esperado]:
    """Linha de `rotulos.jsonl`. Só `id` e `rotulos` são lidos; `uf` ausente e null valem igual."""
    rotulos = linha.get("rotulos")
    if "id" not in linha or not isinstance(rotulos, Mapping):
        raise ValueError("linha sem 'id' ou sem 'rotulos'")
    avisos = rotulos.get("avisos") or ()
    if not isinstance(avisos, Sequence) or isinstance(avisos, str):
        raise ValueError("rótulo 'avisos' precisa ser lista")
    return str(linha["id"]), Esperado(
        area=_rotulo(rotulos, "area"),
        nivel=_rotulo(rotulos, "nivel"),
        modalidade=_rotulo(rotulos, "modalidade"),
        contrato=_rotulo(rotulos, "contrato"),
        pais=_opcional(rotulos, "pais"),
        uf=_opcional(rotulos, "uf"),
        avisos=frozenset(str(a) for a in avisos),
    )


def _pais_e_uf(locais: Sequence[Local]) -> tuple[str | None, str | None]:
    # shortcut: só o primeiro local conta; vaga em vários países é medida pelo primeiro.
    if not locais:
        return None, None
    primeiro = locais[0]
    # uf sem país é Brasil, como em rotular()
    return primeiro.pais or ("BR" if primeiro.uf else None), primeiro.uf


def _obtidos(v: VagaTratada) -> dict[str, str | frozenset[str] | None]:
    pais, uf = _pais_e_uf(v.locais)
    return {
        "area": str(v.area),
        "nivel": str(v.nivel),
        "modalidade": str(v.modalidade),
        "contrato": str(v.contrato),
        "avisos": frozenset(str(a) for a in v.avisos),
        "pais": pais,
        "uf": uf,
    }


def _como_texto(valor: str | frozenset[str] | None) -> str:
    if isinstance(valor, frozenset):
        return ",".join(sorted(valor)) or "nenhum"
    return valor or "nenhum"


def medir(vagas: Mapping[str, VagaTratada], rotulos: Mapping[str, Esperado]) -> Medicao:
    """`vagas` e `rotulos` são ligados pelo id; quem só aparece num dos lados fica fora."""
    amostra = [(id_, v, rotulos[id_]) for id_, v in vagas.items() if id_ in rotulos]
    certos = dict.fromkeys(ROTULOS, 0)
    erros: list[Erro] = []
    for id_, vaga, esperado in amostra:
        for nome, obtido in _obtidos(vaga).items():
            valor = getattr(esperado, nome)
            if valor == obtido:
                certos[nome] += 1
            else:
                erros.append(
                    Erro(
                        id=id_,
                        rotulo=nome,
                        esperado=_como_texto(valor),
                        obtido=_como_texto(obtido),
                    )
                )
    no_brasil = sum(1 for _, _, esperado in amostra if esperado.pais == "BR")
    return Medicao(
        por_rotulo={n: Acerto(certos=certos[n], total=len(amostra)) for n in ROTULOS},
        erros=tuple(erros),
        proporcao_br=no_brasil / len(amostra) if amostra else 0.0,
    )
