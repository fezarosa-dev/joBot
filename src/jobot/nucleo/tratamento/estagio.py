import re
import unicodedata

from jobot.nucleo.modelo import RequisitosEstagio

# Casa no texto sem acento (mesmo tamanho do original, então o trecho sai com acento)
# e sem diferenciar maiúscula. Só pt e en; numeral por extenso ("quinto semestre") não é lido.
_F = re.IGNORECASE
_ORD = r"[ºo°ª]"
_FIM = r"(?=\s*(?:[,.;:()/\n]|$)|\s+(?:a partir|ou|e|com|from|with|and|or|at|who)\b)"
_CURSO = (
    r"(?:cursando|estudante\s+de|graduando\s+em|matriculad[oa]s?\s+em|enrolled\s+in|majoring\s+in"
    r"|studying|pursuing\s+(?:an?\s+)?(?:(?:bachelor|undergraduate|degree)\S*\s+)*(?:in|of))\s+"
    r"(?:(?:o\s+)?curso\s+de\s+|ensino\s+superior\s+em\s+|graduacao\s+em\s+)?"
    r"(?!\d|(?:a\s+partir|entre|do|no|o|at)\s)"  # "cursando a partir do 5º semestre" não tem curso
    r"([^\s,.;:()/\n][^,.;:()/\n]*?)" + _FIM
)
_SEMESTRE = [
    r"(\d{1,2})\s*"
    + _ORD
    + r"?\s*(?:(?:e|a|ao|ate|-|to|and)\s*(?:o\s*)?\d{1,2}\s*"
    + _ORD
    + r"?\s*)?(?:semestre|periodo)\b",
    r"(\d{1,2})(?:st|nd|rd|th)\s+semester\b",
]
_ANO = [
    r"(\d{1,2})\s*" + _ORD + r"\s*ano\b",
    r"(?:a\s+partir\s+do|desde\s+o)\s+(\d{1,2})\s*ano\b",
    r"(\d{1,2})(?:st|nd|rd|th)[\s-]year\b",
]
_DATA = r"((?:(?:[a-z]+|\d{1,2}" + _ORD + r"?\s*semestre)\s+(?:de\s+)?)?(?:\d{1,2}/)?20\d{2})"
_FORMATURA = (
    r"(?:previsao\s+de\s+(?:formatura|conclusao|termino)|formatura(?:\s+prevista)?|conclusao\s+prevista"
    r"|formando\s+em|expected\s+graduation(?:\s+date)?|expected\s+to\s+graduate|graduating|graduation)"
    r"(?:\s*[:\-]\s*|\s+)(?:(?:em|ate|no|para|in|by|on|date|is|of)\s+)*" + _DATA
)
_PERIODO = (
    r"(?:\s*(?:/|por|per|a)\s*(?:dia|semana|day|week)\b|\s+(?:semanais|diarias|weekly|daily)\b)"
)
_HORAS = r"(?<![\d.,])\d{1,2}(?:\s*(?:a|as|ate|-|e|to)\s*\d{1,2})?\s*(?:horas?|hours?|hrs?|hs?)\b"
_CARGA = [
    r"(?:carga\s+horaria|jornada|workload|schedule|work\s+hours)[^\d\n]{0,25}("
    + _HORAS
    + _PERIODO
    + r"?)",
    r"(" + _HORAS + _PERIODO + r")",
]
_NUM = r"\d(?:[\d.,]*\d)?"
_BOLSA = (
    r"(?:bolsa(?:[\s-]*auxilio)?|stipend|allowance|compensation|remuneracao)"
    r"(?:\s*[:\-]\s*|\s+)(?:(?:de|of|is|around|approx\.?|ate|up\s+to|a\s+partir\s+de)\s+)*"
    r"((?:(?:r\$|us\$|\$|usd|brl|eur|€)\s*"
    + _NUM
    + r"|"
    + _NUM
    + r"\s*(?:reais|dolares|dollars|usd|brl|euros))"
    r"(?:\s*(?:/|por|per)\s*(?:mes|month|hora|hour)\b)?)"
)


def _dobrar(s: str) -> str:
    return "".join(unicodedata.normalize("NFD", c)[0] for c in s)


def ler_requisitos(texto: str) -> RequisitosEstagio | None:
    """Curso, semestre ou ano mínimo, formatura, carga horária e bolsa; None se não achar nenhum.

    Limites: o curso lido é só o primeiro ("Letras e Pedagogia" dá "Letras") e o ano mínimo
    pode casar fora de contexto de curso ("1º ano de contrato").
    """
    texto = unicodedata.normalize("NFC", texto)  # "e" + acento solto vira "é" (1 caractere)
    dobrado = _dobrar(texto)

    def trecho(*padroes: str) -> str | None:
        for p in padroes:
            m = re.search(p, dobrado, _F)
            if m:
                return " ".join(texto[slice(*m.span(1))].split())
        return None

    def numero(padroes: list[str]) -> int | None:
        achado = trecho(*padroes)
        return int(achado) if achado else None

    r = RequisitosEstagio(
        curso=trecho(_CURSO),
        semestre_minimo=numero(_SEMESTRE),
        ano_minimo=numero(_ANO),
        previsao_formatura=trecho(_FORMATURA),
        carga_horaria=trecho(*_CARGA),
        bolsa=trecho(_BOLSA),
    )
    return r if r != RequisitosEstagio() else None
