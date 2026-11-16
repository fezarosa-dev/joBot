import re
from collections.abc import Sequence


def parte_dos_itens[T](itens: Sequence[T], parte: str) -> list[T]:
    """Os itens da parte `i/n` (i de 1 a n): os de índice k com `k % n == i - 1`, na ordem original.

    O CI divide a bateria entre jobs com `JOBOT_PARTE=i/n`; as partes juntas dão a lista inteira.
    """
    achou = re.fullmatch(r"([0-9]+)/([0-9]+)", parte)
    if achou is None or not 1 <= int(achou[1]) <= int(achou[2]):
        raise ValueError(f"JOBOT_PARTE deve ser 'i/n' com 1 <= i <= n, recebi {parte!r}")
    i, n = int(achou[1]), int(achou[2])
    return [item for k, item in enumerate(itens) if k % n == i - 1]
