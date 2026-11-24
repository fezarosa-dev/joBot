"""Memória total e o aviso de lentidão do modelo local (T404; desenho 7; D185.19; D219.20):
valores de PCs reais."""

import ctypes
from typing import Any

import pytest

from jobot.nucleo.ia.contrato import limites
from jobot.sistema import memoria
from jobot.sistema.memoria import GIB, memoria_total

# o corte de produção, que o `jobot ferramentas baixar ia-local --modelo auto` lê (T409)
CORTE = {"aviso_gib": limites()["memoria_gib"]["aviso_lento_abaixo"]}

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
    ("gib", "curta"),
    [
        (7.7, False),  # um PC de 8 GB
        (6.5, True),
        (11.5, False),  # um PC de 12 GB
        (7.0, False),  # aviso só abaixo de 7 GiB
        (6.99, True),
    ],
)
def test_aviso_pela_memoria(gib: float, curta: bool) -> None:
    total = memoria_total("linux", sysconf=_sysconf(gib))
    assert getattr(memoria, "memoria_curta", None) is not None
    assert memoria.memoria_curta(total, **CORTE) is curta


def test_aviso_pela_memoria_do_windows() -> None:
    total = memoria_total("win32", status=_status(6.5))
    assert getattr(memoria, "memoria_curta", None) is not None
    assert memoria.memoria_curta(total, **CORTE) is True


def test_o_modelo_nao_sai_mais_da_memoria() -> None:
    """D219.20: o Laya é o padrão em todo computador; a memória só decide o aviso."""
    assert not hasattr(memoria, "escolher_modelo")
    assert set(limites()["memoria_gib"]) == {"aviso_lento_abaixo"}
