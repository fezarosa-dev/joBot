"""Memória total do computador e o aviso de que o modelo local pode ficar lento (desenho 7;
D185.19; D189; D219.20).

O modelo não sai mais da memória: o `auto` baixa o `padrao` do `ia_local.json` (o Laya) em todo
computador. O sistema informa menos que o nominal (um PC de 16 GB informa uns 13,3 GiB): o corte tem
folga e vem de quem chama, lido do `memoria_gib` do `nucleo/dados/ia.json` (o `sistema` não lê a IA;
T409, D195): aviso só abaixo de 7 GiB.
"""

import ctypes
import os
import sys
from collections.abc import Callable
from typing import Any, Literal

GIB = 1 << 30

# as chaves de `modelos` no `nucleo/dados/ia_local.json` (o teste do manifesto confere)
Modelo = Literal["laya", "2b", "4b"]


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


def memoria_curta(total: int, *, aviso_gib: float) -> bool:
    """Avisar que o modelo local pode ficar lento: memória total em bytes abaixo de `aviso_gib`."""
    return total / GIB < aviso_gib
