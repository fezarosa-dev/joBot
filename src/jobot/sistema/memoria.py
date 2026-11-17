"""Memória total do computador e o modelo local que cabe nela (desenho 7; D185.19; D189).

O sistema informa menos que o nominal (um PC de 16 GB informa uns 13,3 GiB): os cortes têm folga.
Os cortes vêm de quem chama, lidos do `memoria_gib` do `nucleo/dados/ia.json` (o `sistema` não lê a
IA; T409, D195): 4B a partir de 11 GiB, aviso só abaixo de 7 GiB.
"""

import ctypes
import os
import sys
from collections.abc import Callable
from typing import Any, Literal

GIB = 1 << 30

Modelo = Literal["2b", "4b"]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def memoria_total(
    plataforma: str = sys.platform,
    *,
    sysconf: Callable[[str], int] | None = None,
    status: Callable[[Any], int] | None = None,
) -> int:
    """Bytes de memória física: `sysconf` no Linux e no Mac; `GlobalMemoryStatusEx` no Windows."""
    if plataforma == "win32":
        estrutura = _MEMORYSTATUSEX()
        estrutura.dwLength = ctypes.sizeof(estrutura)
        chamar = status or ctypes.windll.kernel32.GlobalMemoryStatusEx  # type: ignore[attr-defined]
        if not chamar(ctypes.pointer(estrutura)):
            raise OSError("GlobalMemoryStatusEx falhou")
        return int(estrutura.ullTotalPhys)
    ler = sysconf or os.sysconf  # o `os.sysconf` não existe no Windows
    return ler("SC_PHYS_PAGES") * ler("SC_PAGE_SIZE")


def escolher_modelo(total: int, *, desde_4b_gib: float, aviso_gib: float) -> tuple[Modelo, bool]:
    """(modelo, avisar que pode ficar lento) pela memória total em bytes: 4B a partir de
    `desde_4b_gib`, aviso só abaixo de `aviso_gib`."""
    gib = total / GIB
    return ("4b" if gib >= desde_4b_gib else "2b"), gib < aviso_gib
