import json
import re
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any

from jobot.nucleo.modelo import Area, Aviso, Contrato, Local, Modalidade, Nivel, VagaColetada
from jobot.nucleo.tratamento.locais import ler_locais
from jobot.nucleo.tratamento.rotulos import (
    _REGRAS,
    ARQUIVO,
    VERSAO_REGRAS,
    Rotulos,
    rotular,
    versao_de,
)

CASOS: list[dict[str, Any]] = json.loads(
    (Path(__file__).parents[1] / "casos" / "rotulos.json").read_text(encoding="utf-8")
)
ENUMS: dict[str, type[StrEnum]] = {
    "area": Area,
    "nivel": Nivel,
    "modalidade": Modalidade,
    "contrato": Contrato,
    "avisos": Aviso,
}
BRASIL = (Local(cidade="São Paulo", uf="SP", pais="BR"),)
EUA = (Local(cidade="Austin", pais="US"),)


def _vaga(**campos: Any) -> VagaColetada:
    base: dict[str, Any] = {
        "fonte": "teste",
        "escopo": "",
        "url": "https://exemplo.com/vaga/1",
        "titulo": "Vaga",
        "empresa": "Acme",
        "descricao_formato": "texto",
    }
    return VagaColetada(**(base | campos))


def _rotular_caso(caso: dict[str, Any]) -> Rotulos:
    vaga = _vaga(
        titulo=caso["titulo"],
        etiquetas=tuple(caso.get("etiquetas", ())),
        modalidade_declarada=caso.get("modalidade_declarada"),
        contrato_declarado=caso.get("contrato_declarado"),
        locais=tuple(caso.get("local", ())),
    )
    # "local" é o texto cru da fonte; sem "locais" explícitos, vale o que o leitor de locais lê dele
    if "locais" in caso:
        locais = tuple(Local(**local) for local in caso["locais"])
    else:
        locais = ler_locais(vaga.locais)
    return rotular(vaga, caso.get("texto", ""), locais)


def test_casos_do_json() -> None:
    erros: list[str] = []
    vistos: dict[str, set[str]] = {nome: set() for nome in ENUMS}
    for caso in CASOS:
        r = _rotular_caso(caso)
        obtido: dict[str, object] = {
            "area": r.area.value,
            "nivel": r.nivel.value,
            "modalidade": r.modalidade.value,
            "contrato": r.contrato.value,
            "avisos": sorted(a.value for a in r.avisos),
        }
        for chave, esperado in caso["esperado"].items():
            if chave == "avisos":
                esperado = sorted(esperado)
                vistos[chave].update(esperado)
            else:
                vistos[chave].add(esperado)
            if obtido[chave] != esperado:
                erros.append(f"{caso['nome']}: {chave} {obtido[chave]!r} != {esperado!r}")
    assert erros == []
    faltam = {nome: sorted({e.value for e in enum} - vistos[nome]) for nome, enum in ENUMS.items()}
    assert faltam == {nome: [] for nome in ENUMS}


def test_declarado_vence_descricao() -> None:
    texto = "Trabalho presencial no escritório. Contratação CLT."
    so_texto = rotular(_vaga(), texto, BRASIL)
    assert so_texto.modalidade == Modalidade.PRESENCIAL
    assert so_texto.contrato == Contrato.CLT
    declarado = rotular(
        _vaga(modalidade_declarada="remote", contrato_declarado="vacancy_type_internship"),
        texto,
        BRASIL,
    )
    assert declarado.modalidade == Modalidade.REMOTO
    assert declarado.contrato == Contrato.ESTAGIO


def _expressoes(no: object) -> Iterator[str]:
    if isinstance(no, dict):
        for chave, valor in no.items():
            if chave == "expressoes":
                yield from valor
            else:
                yield from _expressoes(valor)
    elif isinstance(no, list):
        for item in no:
            yield from _expressoes(item)


def test_regex_no_subconjunto_comum() -> None:
    expressoes = list(_expressoes(json.loads(ARQUIVO.read_text(encoding="utf-8"))))
    assert expressoes, "rotulos.json sem nenhuma expressão"
    # também os padrões montados a partir dos 'termos', que são o que a fase 7 vai portar
    montados = [p.pattern for regras in _REGRAS.values() for r in regras for p in r.padroes]
    for e in expressoes + montados:
        re.compile(e)
        # com a flag u, o JavaScript só aceita escape de sintaxe ou "/" (re.escape gera "\-")
        assert not re.search(r"\\[^0-9A-Za-z^$\\.*+?()[\]{}|/]", e), e
        # (?P<, (?<nome>, (?<=, (?<!, (?i), (?> não existem nas duas linguagens
        assert not re.search(r"\(\?(?![:=!])", e), e
        assert not re.search(r"\\[AZz]", e), e


def test_versao_muda_com_o_json() -> None:
    bruto = ARQUIVO.read_bytes()
    assert re.fullmatch(r"[0-9a-f]{64}", VERSAO_REGRAS)
    assert VERSAO_REGRAS == versao_de(bruto)
    original = json.loads(bruto)
    modificado = json.loads(bruto)
    modificado["area"]["regras"][0]["termos"].append("termo novo")
    # as duas serializadas do mesmo jeito: só a regra nova pode mudar o hash
    assert versao_de(json.dumps(original).encode()) != versao_de(json.dumps(modificado).encode())


def test_faixa_de_nivel_conta_o_menor() -> None:
    esperados = {
        "Desenvolvedor Pleno/Sênior": Nivel.PLENO,
        "Mid-Senior Software Engineer": Nivel.PLENO,
        "Analista de Dados Júnior/Pleno": Nivel.JUNIOR,
        "Senior Software Engineer": Nivel.SENIOR,
    }
    obtidos = {titulo: rotular(_vaga(titulo=titulo), "", ()).nivel for titulo in esperados}
    assert obtidos == esperados


def test_clt_pj_so_no_brasil() -> None:
    def contrato(texto: str, locais: tuple[Local, ...], **campos: Any) -> Contrato:
        return rotular(_vaga(titulo="Desenvolvedor", **campos), texto, locais).contrato

    assert contrato("Contratação CLT.", BRASIL) == Contrato.CLT
    assert contrato("Contratação PJ.", BRASIL) == Contrato.PJ
    assert contrato("Contratação CLT.", EUA) == Contrato.NAO_INFORMADO
    assert contrato("Contratação PJ.", EUA) == Contrato.NAO_INFORMADO
    # sem local, ou local sem país, o "CLT" escrito vale (só país de fora barra)
    assert contrato("Contratação CLT.", ()) == Contrato.CLT
    assert contrato("Contratação PJ.", (Local(),)) == Contrato.PJ
    assert contrato("Contratação CLT.", (Local(cidade="Lisboa", pais="PT"),)) == (
        Contrato.NAO_INFORMADO
    )
    texas = (Local(cidade="Austin", uf="TX", pais="US"),)
    assert contrato("", texas, contrato_declarado="clt") == Contrato.NAO_INFORMADO
    assert contrato("", EUA, contrato_declarado="vacancy_type_effective") == (
        Contrato.NAO_INFORMADO
    )
    assert contrato("", BRASIL, contrato_declarado="vacancy_type_effective") == Contrato.CLT
