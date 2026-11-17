"""Memória total e o modelo local (T404; desenho 7; D185.19): valores de PCs reais."""

import ctypes
from typing import Any

import pytest

from jobot.nucleo.ia.contrato import limites
from jobot.sistema.memoria import GIB, escolher_modelo, memoria_total

# os cortes de produção, que o `jobot ferramentas baixar ia-local --modelo auto` lê (T409)
_GIB = limites()["memoria_gib"]
CORTES = {"desde_4b_gib": _GIB["modelo_4b_desde"], "aviso_gib": _GIB["aviso_lento_abaixo"]}

_PAGINA = 4096


def _sysconf(gib: float) -> Any:
    valores = {"SC_PHYS_PAGES": int(gib * GIB) // _PAGINA, "SC_PAGE_SIZE": _PAGINA}
    return valores.__getitem__


def _status(gib: float) -> Any:
    def chamar(ponteiro: Any) -> int:
        estrutura = ponteiro.contents
        assert estrutura.dwLength == ctypes.sizeof(estrutura)
        estrutura.ullTotalPhys = int(gib * GIB)
        return 1

    return chamar


@pytest.mark.parametrize("plataforma", ["linux", "darwin"])
def test_memoria_pelo_sysconf(plataforma: str) -> None:
    total = memoria_total(plataforma, sysconf=_sysconf(7.7))
    assert total == int(7.7 * GIB) // _PAGINA * _PAGINA


def test_memoria_pelo_global_memory_status_ex() -> None:
    assert memoria_total("win32", status=_status(11.5)) == int(11.5 * GIB)


def test_global_memory_status_ex_que_falha_levanta() -> None:
    with pytest.raises(OSError, match="GlobalMemoryStatusEx"):
        memoria_total("win32", status=lambda p: 0)


@pytest.mark.parametrize(
    ("gib", "esperado"),
    [
        (7.7, ("2b", False)),  # um PC de 8 GB
        (6.5, ("2b", True)),
        (11.5, ("4b", False)),  # um PC de 12 GB
        (13.3, ("4b", False)),  # um PC de 16 GB
        (11.0, ("4b", False)),  # "a partir de 11 GiB"
        (10.99, ("2b", False)),
        (7.0, ("2b", False)),  # aviso só abaixo de 7 GiB
    ],
)
def test_modelo_pela_memoria(gib: float, esperado: tuple[str, bool]) -> None:
    assert escolher_modelo(memoria_total("linux", sysconf=_sysconf(gib)), **CORTES) == esperado


def test_modelo_pela_memoria_do_windows() -> None:
    assert escolher_modelo(memoria_total("win32", status=_status(6.5)), **CORTES) == ("2b", True)
