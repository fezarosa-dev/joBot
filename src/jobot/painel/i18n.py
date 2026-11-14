import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Literal

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


def idioma_inicial(accept_language: str | None) -> Literal["pt", "en"]:
    """Primeiro idioma pt/en do Accept-Language, por peso (q); sem match, pt."""
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
            preferidos.append((-peso, ordem, tag.strip().lower().split("-")[0]))
    for _, _, base in sorted(preferidos):
        if base == "en":
            return "en"
        if base == "pt":
            return "pt"
    return "pt"
