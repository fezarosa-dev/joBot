import unicodedata


def normalizar(s: str) -> str:
    """Minúsculas, sem acento e com espaços simples: base para comparar texto."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())
