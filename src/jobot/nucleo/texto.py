import re
import unicodedata
from html.parser import HTMLParser
from typing import Literal


def normalizar(s: str) -> str:
    """Minúsculas, sem acento e com espaços simples: base para comparar texto."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


# Conteúdo que o leitor não vê: some junto com a tag.
_OCULTOS = frozenset(
    "script style noscript template iframe object svg applet noembed noframes".split()
)
_BLOCOS = frozenset(
    "address article aside blockquote br dd details dialog dir div dl dt fieldset figcaption "
    "figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr legend li listing main menu nav ol p "
    "pre search section summary table td th tr ul".split()
)
# Resto dos elementos HTML5 e dos obsoletos: a tag some, o texto fica.
_EM_LINHA = frozenset(
    "a abbr acronym area audio b base basefont bdi bdo bgsound big blink body button canvas "
    "caption center cite code col colgroup data datalist del dfn em embed font frame frameset "
    "head html i img input ins isindex kbd keygen label link map mark marquee math menuitem meta "
    "meter multicol nextid nobr optgroup option output param picture plaintext progress q rb rp "
    "rt rtc ruby s samp select slot small source spacer span strike strong sub sup tbody "
    "textarea tfoot thead time title track tt u var video wbr xmp".split()
)
# Prefixos de namespace do HTML colado do Word (<o:p>, <v:shape>); "std::string" não é tag.
_NAMESPACES = frozenset("o v w m x xml st1".split())
# Só estas são tag de verdade; "<String>" ou "<K,V>" de uma vaga de TI é texto e fica.
_CONHECIDAS = _BLOCOS | _OCULTOS | _EM_LINHA


def _conhecida(tag: str) -> bool:
    prefixo, dois_pontos, _ = tag.partition(":")
    return tag in _CONHECIDAS or (bool(dois_pontos) and prefixo in _NAMESPACES)


class _Extrator(HTMLParser):
    """Junta só o texto visível; script e style somem, tags de bloco viram quebra de linha."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.tags = 0  # quantas tags conhecidas abriram: zero indica HTML ainda escapado
        self._oculto = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._oculto and tag not in _OCULTOS:
            return
        if not _conhecida(tag):
            self.partes.append(self.get_starttag_text() or "")
            return
        self.tags += 1
        if tag in _OCULTOS:
            self._oculto += 1
        elif tag in _BLOCOS:
            self.partes.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # "<script/>" não fecha no navegador: esconde até </script>; os outros não têm conteúdo
        if tag not in _OCULTOS or tag in ("script", "style"):
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _OCULTOS:
            self._oculto = max(0, self._oculto - 1)
        elif tag in _BLOCOS:
            self.partes.append("\n")
        elif not _conhecida(tag) and not self._oculto:
            self.partes.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._oculto:
            self.partes.append(data)


def _linhas(s: str) -> str:
    """Espaços simples dentro da linha e nenhuma linha vazia."""
    linhas = (" ".join(x.split()) for x in s.splitlines())
    return "\n".join(linha for linha in linhas if linha)


def _de_html(bruto: str) -> str:
    # shortcut: HTML escapado (Greenhouse) só se repete enquanto a passada não achar tag de verdade;
    # máx. 3 passadas. Escapado 4+ vezes deixa entidade no texto; subir o limite se aparecer.
    texto = bruto
    for _ in range(3):
        extrator = _Extrator()
        extrator.feed(texto)
        extrator.close()
        novo = "".join(extrator.partes)
        if extrator.tags or novo == texto:
            texto = novo
            break
        texto = novo
    return _linhas(texto)


_CERCA = re.compile(r"\s*(```|~~~)")
_REGUA = re.compile(r"\s*([-*_]\s*){3,}$")
_PREFIXO = re.compile(r"^\s{0,3}(#{1,6}\s+|>+\s?|[-*+]\s+|\d+[.)]\s+)")
_TITULO_FIM = re.compile(r"\s+#+\s*$")
_AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_CODIGO = re.compile(r"`+([^`]*)`+")
_NEGRITO = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)")
_ITALICO = re.compile(r"\*(?=[^\s*])(.+?)(?<=[^\s*])\*|(?<!\w)_(?=[^\s_])(.+?)(?<=[^\s_])_(?!\w)")


_TRECHO = 2000


def _sem_marcas(trecho: str) -> str:
    trecho = _AUTOLINK.sub(r"\1", trecho)
    trecho = _LINK.sub(r"\1", trecho)
    trecho = _CODIGO.sub(r"\1", trecho)
    for padrao in (_NEGRITO, _ITALICO):
        trecho = padrao.sub(lambda m: m.group(1) or m.group(2), trecho)
    return trecho


def _de_markdown(bruto: str) -> str:
    saida: list[str] = []
    em_codigo = False
    for linha in bruto.splitlines():
        if _CERCA.match(linha):
            em_codigo = not em_codigo
        elif em_codigo:
            saida.append(linha)
        elif not _REGUA.match(linha):
            linha = " ".join(linha.split())  # corta o custo das regexes em linha de espaços
            linha = _TITULO_FIM.sub("", _PREFIXO.sub("", linha, count=1))
            # shortcut: marca que cruza um corte de _TRECHO caracteres fica no texto; é o preço de
            # as regexes de marca não ficarem quadráticas em linha longa e sem par
            saida.append(
                "".join(_sem_marcas(linha[i : i + _TRECHO]) for i in range(0, len(linha), _TRECHO))
            )
    return _de_html("\n".join(saida))  # sobra de HTML solto no meio do Markdown


def para_texto(bruto: str, formato: Literal["html", "markdown", "texto"]) -> str:
    """Texto puro de uma descrição: sem tag, sem marca, sem script, entidades decodificadas."""
    if formato == "html":
        return _de_html(bruto)
    if formato == "markdown":
        return _de_markdown(bruto)
    return _linhas(bruto)


_PALAVRAS = {
    "pt": (
        "a o os de do da com para por que se como eu ele ela isso esse essa este estao vai vamos "
        "foi pode podem ou um uns uma umas e em no nos na nas ao aos dos das pelo pela pelos pelas "
        "nao sao voce voces tambem mais mas ainda ja seu seus sua suas nosso nossa nossos nossas "
        "vaga vagas equipe trabalho trabalhar empresa oportunidade conhecimento requisitos "
        "ter tem temos fazer ser esta estamos sobre quando onde muito muitos "
        "ate depois antes alem porque entre desde sempre"
    ),
    "en": (
        "a do no so if the and of to in is are we you with for that will our your have has be "
        "as on or an this from by at it its they their which not can all new about who what work "
        "team role job skills ability experience looking join help also more other such into out "
        "than must should within across"
    ),
    "es": (
        "a o lo le les me mi el la los las de y en un una unos unas del al es son se su sus con "
        "por para que nuestro nuestra nuestros nuestras tu tus usted ustedes somos estamos "
        "buscamos trabajo trabajar equipo empresa experiencia tambien mas pero sobre cuando "
        "donde muy muchos tener tiene tenemos hacer ser esta como hasta despues antes ademas "
        "porque entre desde siempre sin"
    ),
}
# palavra que existe em mais de um idioma não prova nenhum: sai das listas
_CONJUNTOS = {
    lang: frozenset(
        p
        for p in normalizar(txt).split()
        if sum(p in normalizar(outro).split() for outro in _PALAVRAS.values()) == 1
    )
    for lang, txt in _PALAVRAS.items()
}
_MIN_PALAVRAS = 20  # abaixo disso (título, frase solta) o resultado seria sorte
_MIN_ACERTOS = 5
_MIN_PARTE = 0.75  # o vencedor precisa ter este tanto dos acertos; senão o texto é misto


_IDIOMAS: tuple[Literal["pt", "en", "es"], ...] = ("pt", "en", "es")


def detectar_idioma(texto: str) -> Literal["pt", "en", "es", "outro"]:
    """Conta palavras comuns de pt, en e es; texto curto ou misto dá "outro"."""
    palavras = re.findall(r"[a-z]+", normalizar(texto))
    if len(palavras) < _MIN_PALAVRAS:
        return "outro"
    acertos = {lang: sum(p in _CONJUNTOS[lang] for p in palavras) for lang in _IDIOMAS}
    total = sum(acertos.values())
    vencedor = max(_IDIOMAS, key=lambda lang: acertos[lang])
    if total < _MIN_ACERTOS or acertos[vencedor] / total < _MIN_PARTE:
        return "outro"
    return vencedor
