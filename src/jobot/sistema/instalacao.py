"""O `<dados>/instalacao.json` que a casca grava (desenho 6.2; D174).

Sem o arquivo, o joBot veio do clone ou do `uv tool`. Hoje só a T330 o lê, pelo manifesto.
"""

import json
from pathlib import Path

ARQUIVO = "instalacao.json"


def manifesto_da_casca(dados: Path) -> Path | None:
    """O `manifesto-<versão>.json` no canal `casca`; `None` sem o arquivo ou noutro canal.
    Arquivo quebrado dá `ValueError` (o `OSError` de leitura passa)."""
    caminho = dados / ARQUIVO
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        conteudo = json.loads(texto)
    except ValueError as erro:
        raise ValueError(f"{caminho} não é JSON válido") from erro
    if not isinstance(conteudo, dict) or conteudo.get("canal") != "casca":
        return None
    manifesto = conteudo.get("manifesto")
    if not isinstance(manifesto, str) or not manifesto:
        raise ValueError(f"{caminho} não diz onde está o manifesto")
    return Path(manifesto)
