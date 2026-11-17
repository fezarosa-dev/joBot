"""Memória total do computador e o modelo local que cabe nela (desenho 7; D185.19; D189).

O sistema informa menos que o nominal (um PC de 16 GB informa uns 13,3 GiB): os cortes têm folga.
Os cortes moram aqui até a T409 lê-los do `ia.json` (D189).
"""

import ctypes
import os
import sys
from collections.abc import Callable
from typing import Any, Literal

GIB = 1 << 30
CORTE_4B_GIB = 11.0  # 4B a partir daqui: um PC de 12 GB (uns 11,5 GiB) leva o 4B
AVISO_GIB = 7.0  # "pode ficar lento" só abaixo daqui: um PC de 8 GB (uns 7,7 GiB) não avisa

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


def escolher_modelo(total: int) -> tuple[Modelo, bool]:
    """(modelo, avisar que pode ficar lento) pela memória total em bytes."""
    gib = total / GIB
    return ("4b" if gib >= CORTE_4B_GIB else "2b"), gib < AVISO_GIB
