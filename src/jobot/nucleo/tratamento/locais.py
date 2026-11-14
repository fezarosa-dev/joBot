import json
import re
from collections.abc import Iterator, Sequence
from functools import cache
from pathlib import Path

from jobot.nucleo.modelo import Local
from jobot.nucleo.texto import normalizar

_UFS = Path(__file__).parent.parent / "dados" / "ufs.json"

# Países que aparecem nas fontes (chave sem acento, minúscula); ISO 3166-1 alfa-2.
_PAISES = {
    **dict.fromkeys(("brazil", "brasil"), "BR"),
    "portugal": "PT",
    **dict.fromkeys(
        ("united states", "usa", "us", "eua", "estados unidos da america", "estados unidos"), "US"
    ),
    **dict.fromkeys(("united kingdom", "uk", "reino unido"), "GB"),
    "canada": "CA",
    **dict.fromkeys(("germany", "alemanha"), "DE"),
    **dict.fromkeys(("spain", "espanha"), "ES"),
    **dict.fromkeys(("france", "franca"), "FR"),
    **dict.fromkeys(("italy", "italia"), "IT"),
    **dict.fromkeys(("netherlands", "holanda", "paises baixos"), "NL"),
    **dict.fromkeys(("ireland", "irlanda"), "IE"),
    "argentina": "AR",
    "chile": "CL",
    "colombia": "CO",
    **dict.fromkeys(("mexico",), "MX"),
    **dict.fromkeys(("uruguay", "uruguai"), "UY"),
    "peru": "PE",
    "india": "IN",
}

# Remoto e regiões não dizem país (D5): ficam sem país.
_SEM_PAIS = {
    "remote", "remoto", "remote work", "home office", "worldwide", "anywhere", "global",
    "latam", "latin america", "america latina", "americas", "emea", "apac", "europe", "europa",
    "north america", "south america", "asia", "africa",
}  # fmt: skip

# Modalidade não é lugar: nunca vira cidade ("Hybrid - Curitiba, PR").
_MODALIDADE = {
    "hybrid", "hibrido", "presencial", "on-site", "onsite", "on site", "in office", "in-office",
    "office", "semipresencial",
}  # fmt: skip

# Sigla que é de UF e também de estado dos EUA: sem país escrito, só estas cidades dos EUA saem do
# Brasil ("Pittsburgh, PA" não é o Pará). shortcut: lista curta de cidades conhecidas; upgrade:
# lista maior ou a fonte dizer o país.
_CIDADES_DOS_EUA = {
    "PA": {"pittsburgh", "philadelphia", "harrisburg", "allentown", "scranton", "king of prussia"},
    "MA": {"boston", "cambridge", "worcester", "springfield", "lowell", "waltham", "somerville"},
    "AL": {"birmingham", "huntsville", "montgomery", "mobile"},
    "SC": {"charleston", "greenville", "spartanburg", "mount pleasant"},
    "MS": {"jackson", "gulfport", "biloxi", "hattiesburg"},
    "MT": {"billings", "bozeman", "missoula", "helena", "great falls"},
}

_CONHECIDOS = _PAISES.keys() | _SEM_PAIS | _MODALIDADE

_PEDACOS = re.compile(r"[;|]")
# "Guarulhos-SP": hífen colado só separa quando vem antes de sigla de UF maiúscula.
_TOKENS = re.compile(r"\s*[,/()–—]\s*|\s+-\s+|(?<=\w)-(?=[A-Z]{2}\b)")


def _tokens(texto: str) -> Iterator[str]:
    for token in filter(None, _TOKENS.split(texto.strip())):
        partes = token.split("-")
        # "Remote-Brazil": hífen sem espaço só separa se algum lado for país, região ou modalidade.
        if (
            normalizar(token) not in _MODALIDADE
            and len(partes) > 1
            and any(normalizar(p) in _CONHECIDOS for p in partes)
        ):
            yield from filter(None, partes)
        else:
            yield token


@cache
def _ufs() -> tuple[dict[str, str], dict[str, str]]:
    """(siglas, nomes normalizados) -> sigla."""
    dados: list[dict[str, str]] = json.loads(_UFS.read_text(encoding="utf-8"))
    return (
        {u["sigla"]: u["sigla"] for u in dados},
        {normalizar(u["nome"]): u["sigla"] for u in dados},
    )


def _ler_um(texto: str) -> Local:
    siglas, nomes = _ufs()
    cidade = uf = pais = None
    for token in _tokens(texto):
        chave = normalizar(token)
        if token in siglas:  # sigla só em maiúsculas: "sp" ou "pa" soltos não valem
            uf = uf or token
        elif chave in _PAISES:
            pais = pais or _PAISES[chave]
        elif chave in _SEM_PAIS or chave in _MODALIDADE:
            continue
        elif cidade and chave in nomes:  # "Curitiba, Paraná": o nome do estado vem depois da cidade
            uf = uf or nomes[chave]
        elif cidade is None and re.search(r"[^\W\d_]", chave):
            cidade = token.strip()
    # shortcut: cidade só vale com UF ou país ("Curitiba" sozinha é vazio); upgrade: lista
    # Sigla de 2 letras também é código de estado/país de fora ("Boston, MA, USA"): com país
    # estrangeiro explícito ela não é UF. Sem país, vale `_CIDADES_DOS_EUA`.
    if uf and not pais and normalizar(cidade or "") in _CIDADES_DOS_EUA.get(uf, ()):
        pais = "US"
    if pais and pais != "BR":
        uf = None
    if uf and not pais:
        pais = "BR"
    if not (uf or pais):
        return Local()
    return Local(cidade=cidade, uf=uf, pais=pais)


def ler_locais(brutos: Sequence[str]) -> tuple[Local, ...]:
    """Um `Local` por cidade citada; texto que não se entende vira `Local()` vazio."""
    locais = (
        _ler_um(parte) for bruto in brutos for parte in _PEDACOS.split(bruto) if parte.strip()
    )
    unicos = tuple(dict.fromkeys(locais))
    uteis = tuple(local for local in unicos if local != Local())
    return uteis or unicos


_ACENTOS = {
    "canada": "Canadá", "franca": "França", "italia": "Itália", "paises baixos": "Países Baixos",
    "colombia": "Colômbia", "mexico": "México", "india": "Índia",
}  # fmt: skip
# Um nome por código: o último de cada grupo em `_PAISES`, que é o português.
_NOMES = {codigo: _ACENTOS.get(chave, chave.title()) for chave, codigo in _PAISES.items()}


def nome_do_pais(codigo: str) -> str | None:
    """Nome em português do país (ISO alfa-2 em maiúsculas); `None` se o código não consta."""
    return _NOMES.get(codigo)


# A primeira chave de cada código em `_PAISES` é o nome em inglês.
_INGLES = {codigo: chave.title() for chave, codigo in reversed(_PAISES.items())}


def nome_em_ingles(codigo: str) -> str | None:
    """Nome em inglês do país (ISO alfa-2 em maiúsculas), como o leitor de locais o entende;
    `None` se o código não consta."""
    return _INGLES.get(codigo)
