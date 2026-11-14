import json
from functools import cache
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_DADOS = Path(__file__).parent / "dados" / "rastreamento.json"
_PORTA_PADRAO = {"http": 80, "https": 443}


@cache
def _rastreamento() -> tuple[tuple[str, ...], frozenset[str]]:
    dados: dict[str, list[str]] = json.loads(_DADOS.read_text(encoding="utf-8"))
    return tuple(dados["prefixos"]), frozenset(dados["exatos"])


def _rastreia(nome: str) -> bool:
    prefixos, exatos = _rastreamento()
    nome = nome.lower()
    return nome in exatos or nome.startswith(prefixos)


def canonica(url: str) -> str:
    """URL canônica: host minúsculo, sem #fragmento e barra final, query ordenada, sem rastreio."""
    partes = urlsplit(url.strip())
    esquema = partes.scheme.lower()
    if esquema not in _PORTA_PADRAO or not partes.hostname:
        raise ValueError(f"URL inválida (precisa de http/https e host): {url!r}")
    host = f"[{partes.hostname}]" if ":" in partes.hostname else partes.hostname
    if partes.port not in (None, _PORTA_PADRAO[esquema]):
        host = f"{host}:{partes.port}"
    query = sorted(
        (k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True) if not _rastreia(k)
    )
    return urlunsplit((esquema, host, partes.path.rstrip("/"), urlencode(query), ""))


def hash_url(canonica: str) -> str:
    return sha256(canonica.encode("utf-8")).hexdigest()
