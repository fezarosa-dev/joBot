"""Endereço de candidatura achado no texto da vaga (desenho 5.7, D147.22).

O texto da vaga é dado de terceiro: o endereço só sai daqui se passar pela lista fechada de
caracteres abaixo, para nada do texto virar parâmetro de um `mailto:`.
"""

import re
import unicodedata
from bisect import bisect_left, bisect_right
from typing import Final

# Prefixos (`candidat`, `postula`) casam o começo da palavra; as outras casam a palavra inteira.
GATILHOS: Final[tuple[str, ...]] = (
    # pt
    "currículo",
    "candidat",
    "envie",
    "enviar",
    "mande",
    # en
    "cv",
    "resume",
    "send",
    "apply",
    "application",
    # es
    "curriculum",
    "postula",
    "hoja de vida",
)
_PREFIXOS: Final = ("candidat", "postula")

_ROTULO = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_ENDERECO = re.compile(rf"[A-Za-z0-9._+-]{{1,64}}@(?:{_ROTULO}\.)+{_ROTULO}", re.ASCII)
# Pedaço sem separador: antes e depois do endereço só valem estes (mais o ponto do fim).
_PEDACO = re.compile(r"[^\s()<>,;:]+", re.ASCII)
_FIM_DE_FRASE = re.compile(r"[.!?](?=\s|\Z)", re.ASCII)
_MAX_ENDERECO = 254


def _normalizar(texto: str) -> tuple[str, list[int] | None]:
    """Sem acento e em minúsculas, com o índice do texto cru de cada letra (None: o mesmo)."""
    if texto.isascii():
        return texto.lower(), None
    letras: list[str] = []
    origem: list[int] = []
    for i, c in enumerate(texto):
        for d in unicodedata.normalize("NFKD", c):
            if not unicodedata.combining(d):
                for f in d.casefold():
                    letras.append(f)
                    origem.append(i)
    return "".join(letras), origem


def _norm(palavra: str) -> str:
    return _normalizar(palavra)[0]


def _expressao_dos_gatilhos() -> re.Pattern[str]:
    inteiras = [re.escape(_norm(g)).replace(r"\ ", r"\s+") for g in GATILHOS if g not in _PREFIXOS]
    prefixos = [re.escape(p) for p in _PREFIXOS]
    return re.compile(
        rf"(?<![a-z0-9])(?:{'|'.join(prefixos)}|(?:{'|'.join(inteiras)})(?![a-z0-9]))", re.ASCII
    )


_GATILHO = _expressao_dos_gatilhos()


def _posicoes_dos_gatilhos(texto: str) -> list[int]:
    norm, origem = _normalizar(texto)
    inicios = [m.start() for m in _GATILHO.finditer(norm)]
    return inicios if origem is None else [origem[i] for i in inicios]


def _candidatos(texto: str) -> list[tuple[int, int, str]]:
    achados = []
    for m in _PEDACO.finditer(texto):
        inicio, fim = m.span()
        if "@" not in m.group():
            continue
        if texto[fim - 1] == ".":
            fim -= 1
        endereco = texto[inicio:fim]
        if len(endereco) > _MAX_ENDERECO or not _ENDERECO.fullmatch(endereco):
            continue
        local, dominio = endereco.split("@")
        if "noreply" in re.sub(r"[-_.]", "", local.casefold()):
            continue
        achados.append((inicio, fim, f"{local}@{dominio.lower()}"))
    return achados


def email_de_candidatura(texto: str) -> str | None:
    """Primeiro e-mail do texto que está na frase ou na linha de uma palavra de candidatura."""
    achados = _candidatos(texto)
    if not achados:
        return None
    gatilhos = _posicoes_dos_gatilhos(texto)
    quebras = [m.start() for m in re.finditer("\n", texto)]
    fins = [m.end() for m in _FIM_DE_FRASE.finditer(texto)]
    for inicio, fim, endereco in achados:
        q = bisect_left(quebras, inicio)
        linha_ini = quebras[q - 1] + 1 if q else 0
        q = bisect_left(quebras, fim)
        linha_fim = quebras[q] if q < len(quebras) else len(texto)
        f = bisect_right(fins, inicio)
        frase_ini = fins[f - 1] if f else 0
        f = bisect_right(fins, fim)
        frase_fim = fins[f] if f < len(fins) else len(texto)
        janela_ini, janela_fim = min(linha_ini, frase_ini), max(linha_fim, frase_fim)
        antes = bisect_left(gatilhos, janela_ini)
        depois = bisect_left(gatilhos, fim)
        if (antes < len(gatilhos) and gatilhos[antes] < inicio) or (
            depois < len(gatilhos) and gatilhos[depois] < janela_fim
        ):
            return endereco
    return None
