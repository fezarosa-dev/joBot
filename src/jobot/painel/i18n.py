import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Literal

from jobot.nucleo.tratamento.locais import codigos_de_pais

PASTA = Path(__file__).parent / "i18n"


def carregar() -> Mapping[str, Mapping[str, str]]:
    """Junta `<idioma>/*.json`; chave repetida em dois arquivos do mesmo idioma falha."""
    catalogo: dict[str, dict[str, str]] = {}
    for pasta in sorted(p for p in PASTA.iterdir() if p.is_dir()):
        textos = catalogo[pasta.name] = {}
        for arquivo in sorted(pasta.glob("*.json")):
            dados: dict[str, str] = json.loads(arquivo.read_text(encoding="utf-8"))
            repetidas = textos.keys() & dados.keys()
            if repetidas:
                raise ValueError(f"chave repetida em {arquivo}: {sorted(repetidas)}")
            textos.update(dados)
    return catalogo


@cache
def _catalogo() -> Mapping[str, Mapping[str, str]]:
    return carregar()


def t(idioma: str, chave: str, **params: object) -> str:
    """Texto da chave no idioma (pt se o idioma não existe); chave sem texto volta como está."""
    catalogo = _catalogo()
    texto = catalogo.get(idioma, catalogo["pt"]).get(chave)
    return chave if texto is None else texto.format(**params)


def _tags_por_peso(accept_language: str | None) -> list[str]:
    """As tags do Accept-Language por peso (q), sem as de peso zero; empate fica na ordem dada."""
    preferidos: list[tuple[float, int, str]] = []
    for ordem, item in enumerate((accept_language or "").split(",")):
        tag, *parametros = item.strip().split(";")
        peso = 1.0
        for p in parametros:
            nome, _, valor = p.strip().partition("=")
            if nome == "q":
                try:
                    peso = float(valor)
                except ValueError:
                    peso = 0.0
        if peso > 0:
            preferidos.append((-peso, ordem, tag.strip()))
    return [tag for _, _, tag in sorted(preferidos)]


def idioma_inicial(accept_language: str | None) -> Literal["pt", "en"]:
    """Primeiro idioma pt/en do Accept-Language, por peso (q); sem match, pt."""
    for tag in _tags_por_peso(accept_language):
        base = tag.lower().split("-")[0]
        if base == "en":
            return "en"
        if base == "pt":
            return "pt"
    return "pt"


def pais_do_accept_language(cabecalho: str | None) -> str:
    """País da primeira região de duas letras que conhecemos, por peso (q); sem região, `BR`."""
    conhecidos = codigos_de_pais()
    for tag in _tags_por_peso(cabecalho):
        for parte in tag.split("-")[1:]:
            regiao = parte.upper()
            if len(regiao) == 2 and regiao.isascii() and regiao.isalpha() and regiao in conhecidos:
                return regiao
    return "BR"
