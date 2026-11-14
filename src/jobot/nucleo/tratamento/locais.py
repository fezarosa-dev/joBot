import json
import re
from collections.abc import Iterator, Sequence
from functools import cache
from pathlib import Path
from typing import Any

from jobot.nucleo.modelo import Local
from jobot.nucleo.texto import normalizar

_UFS = Path(__file__).parent.parent / "dados" / "ufs.json"

# Países que aparecem nas fontes (chave sem acento, minúscula); ISO 3166-1 alfa-2.
# Em cada grupo, a primeira chave é o nome em inglês e a última, o português (`_NOMES`, `_INGLES`).
_PAISES = {
    **dict.fromkeys(("brazil", "brasil"), "BR"),
    "portugal": "PT",
    **dict.fromkeys(
        (
            "united states", "usa", "us", "u.s.", "u.s.a.", "united states of america", "eua",
            "estados unidos da america", "estados unidos",
        ),
        "US",
    ),
    **dict.fromkeys(("united kingdom", "uk", "england", "reino unido"), "GB"),
    "canada": "CA",
    **dict.fromkeys(("germany", "deutschland", "alemanha"), "DE"),
    **dict.fromkeys(("spain", "espana", "espanha"), "ES"),
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
    **dict.fromkeys(("philippines", "filipinas"), "PH"),
    **dict.fromkeys(("poland", "polonia"), "PL"),
    "australia": "AU",
    **dict.fromkeys(("new zealand", "nova zelandia"), "NZ"),
    **dict.fromkeys(("japan", "japao"), "JP"),
    **dict.fromkeys(("singapore", "singapura"), "SG"),
    **dict.fromkeys(("switzerland", "suica"), "CH"),
    "austria": "AT",
    **dict.fromkeys(("belgium", "belgica"), "BE"),
    **dict.fromkeys(("sweden", "suecia"), "SE"),
    **dict.fromkeys(("denmark", "dinamarca"), "DK"),
    **dict.fromkeys(("norway", "noruega"), "NO"),
    **dict.fromkeys(("finland", "finlandia"), "FI"),
    **dict.fromkeys(("romania", "romenia"), "RO"),
    **dict.fromkeys(("ukraine", "ucrania"), "UA"),
    **dict.fromkeys(("czech republic", "czechia", "republica tcheca"), "CZ"),
    **dict.fromkeys(("greece", "grecia"), "GR"),
    **dict.fromkeys(("turkey", "turkiye", "turquia"), "TR"),
    "israel": "IL",
    **dict.fromkeys(("south africa", "africa do sul"), "ZA"),
    "nigeria": "NG",
    **dict.fromkeys(("kenya", "quenia"), "KE"),
    **dict.fromkeys(("egypt", "egito"), "EG"),
    **dict.fromkeys(("united arab emirates", "uae", "emirados arabes unidos"), "AE"),
    "china": "CN",
    **dict.fromkeys(("south korea", "coreia do sul"), "KR"),
    "indonesia": "ID",
    **dict.fromkeys(("vietnam", "vietna"), "VN"),
    **dict.fromkeys(("pakistan", "paquistao"), "PK"),
    "costa rica": "CR",
    **dict.fromkeys(("ecuador", "equador"), "EC"),
    "bolivia": "BO",
    **dict.fromkeys(("paraguay", "paraguai"), "PY"),
    "venezuela": "VE",
    "guatemala": "GT",
    **dict.fromkeys(("dominican republic", "republica dominicana"), "DO"),
    "panama": "PA",
}  # fmt: skip

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

# Sigla de estado dos EUA que não colide com UF nem com país frequente nas fontes ("DE" é
# Delaware e Alemanha, "IN" Indiana e Índia, "AR", "CO" e "ID" idem): só vale sem país escrito.
_ESTADOS_DOS_EUA = set(
    "AK AZ CA CT FL GA HI IL IA KS KY LA ME MD MI MN MO NE NV NH NJ NM NY NC ND OH OK OR RI SD TN "
    "TX UT VT VA WA WV WI WY DC".split()
)
# Províncias do Canadá ("Toronto, ON, CA"): vencem o "CA" de Califórnia. "PE" fica com Pernambuco.
_PROVINCIAS_DO_CANADA = set("ON BC QC AB MB NS NB NL SK".split())

# Cidade de fora que aparece sozinha no local ("Berlin", "London"): dá o país.
# shortcut: lista curta das cidades mais citadas; upgrade: base de cidades com licença aberta.
_CIDADES_DE_FORA = {
    **dict.fromkeys(
        (
            "new york", "new york city", "nyc", "san francisco", "los angeles", "seattle",
            "chicago", "austin", "boston", "miami", "denver", "atlanta",
        ),
        "US",
    ),
    "london": "GB", "berlin": "DE", "munich": "DE", "munchen": "DE", "hamburg": "DE",
    "paris": "FR", "amsterdam": "NL", "dublin": "IE", "lisbon": "PT", "lisboa": "PT",
    "porto": "PT", "madrid": "ES", "barcelona": "ES", "toronto": "CA", "vancouver": "CA",
    "montreal": "CA", "buenos aires": "AR", "mexico city": "MX", "cidade do mexico": "MX",
    "ciudad de mexico": "MX", "bogota": "CO", "manila": "PH", "bangalore": "IN",
    "bengaluru": "IN", "tel aviv": "IL", "warsaw": "PL", "krakow": "PL",
}  # fmt: skip

# Palavras em volta do lugar que não o mudam ("USA Only", "Remote US", "Curitiba Office").
_ENFEITES = {
    "only", "apenas", "somente", "remote", "remoto", "remota", "fully", "based", "office",
    "escritorio", "hq",
}  # fmt: skip

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
def _ufs() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """(siglas, nomes normalizados, capitais e cidades grandes normalizadas) -> sigla."""
    dados: list[dict[str, Any]] = json.loads(_UFS.read_text(encoding="utf-8"))
    return (
        {u["sigla"]: u["sigla"] for u in dados},
        {normalizar(u["nome"]): u["sigla"] for u in dados},
        {normalizar(c): u["sigla"] for u in dados for c in [u["capital"], *u.get("cidades", ())]},
    )


def _ler_um(texto: str) -> Local:
    siglas, nomes, cidades = _ufs()
    cidade = uf = pais = None
    siglas_de_fora: set[str] = set()
    for token in _tokens(texto):
        chave = normalizar(token)
        nucleo = " ".join(p for p in chave.split() if p not in _ENFEITES)
        if token in siglas:  # sigla só em maiúsculas: "sp" ou "pa" soltos não valem
            uf = uf or token
        elif token in _ESTADOS_DOS_EUA or token in _PROVINCIAS_DO_CANADA:
            siglas_de_fora.add(token)
        elif chave in _PAISES or nucleo in _PAISES:
            pais = pais or _PAISES.get(chave) or _PAISES[nucleo]
        elif chave in _SEM_PAIS or chave in _MODALIDADE or not nucleo:
            continue
        elif cidade and chave in nomes:  # "Curitiba, Paraná": o nome do estado vem depois da cidade
            uf = uf or nomes[chave]
        elif cidade is None and re.search(r"[^\W\d_]", chave):
            # "São Paulo Office" -> "São Paulo", com a grafia da fonte
            cidade = " ".join(p for p in token.split() if normalizar(p) not in _ENFEITES)
    chave_cidade = normalizar(cidade or "")
    # Cidade sozinha só vale se for capital ou cidade grande de `ufs.json`, ou cidade de fora
    # conhecida; as outras ("Itu") ficam vazias sem UF ou país escrito.
    # shortcut: só as cidades das listas; upgrade: base de municípios e cidades com licença aberta.
    if not uf and pais in (None, "BR") and not siglas_de_fora:
        uf = cidades.get(chave_cidade)
    if not (uf or pais):
        de_fora = _CIDADES_DE_FORA.get(chave_cidade)
        # Cidade conhecida vale sozinha ou com a sigla do próprio país ("Tel Aviv, IL",
        # "Toronto, ON, CA"); com outra sigla, vale a sigla ("Paris, TX", "London, ON").
        if de_fora and (not siglas_de_fora or de_fora in siglas_de_fora):
            pais = de_fora
        elif siglas_de_fora & _PROVINCIAS_DO_CANADA:
            pais = "CA"
        elif siglas_de_fora:
            pais = "US"
    # Sigla de 2 letras também é código de estado/país de fora ("Boston, MA, USA"): com país
    # estrangeiro explícito ela não é UF. Sem país, vale `_CIDADES_DOS_EUA`.
    if uf and not pais and chave_cidade in _CIDADES_DOS_EUA.get(uf, ()):
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
    "colombia": "Colômbia", "mexico": "México", "india": "Índia", "polonia": "Polônia",
    "australia": "Austrália", "nova zelandia": "Nova Zelândia", "japao": "Japão", "suica": "Suíça",
    "austria": "Áustria", "belgica": "Bélgica", "suecia": "Suécia", "finlandia": "Finlândia",
    "romenia": "Romênia", "ucrania": "Ucrânia", "republica tcheca": "República Tcheca",
    "grecia": "Grécia", "africa do sul": "África do Sul", "nigeria": "Nigéria", "quenia": "Quênia",
    "emirados arabes unidos": "Emirados Árabes Unidos", "coreia do sul": "Coreia do Sul",
    "indonesia": "Indonésia", "vietna": "Vietnã", "paquistao": "Paquistão", "bolivia": "Bolívia",
    "republica dominicana": "República Dominicana", "panama": "Panamá",
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


def pais_escrito(texto: str) -> str | None:
    """País cujo nome está escrito no texto ("Austin, USA"); sigla de estado ou UF não conta."""
    for token in _tokens(texto):
        chave = normalizar(token)
        nucleo = " ".join(p for p in chave.split() if p not in _ENFEITES)
        if codigo := _PAISES.get(chave) or _PAISES.get(nucleo):
            return codigo
    return None
