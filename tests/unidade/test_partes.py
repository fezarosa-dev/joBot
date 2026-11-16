"""Partição dos testes entre os jobs do CI (JOBOT_PARTE=i/n)."""

import pytest

from apoio.partes import parte_dos_itens
from conftest import pytest_collection_modifyitems


@pytest.mark.parametrize("n", range(1, 6))
@pytest.mark.parametrize("quantos", range(13))
def test_as_partes_juntas_dao_a_lista_inteira(n: int, quantos: int) -> None:
    itens = list(range(quantos))
    partes = [parte_dos_itens(itens, f"{i}/{n}") for i in range(1, n + 1)]
    juntas = [x for parte in partes for x in parte]
    assert sorted(juntas) == itens  # nada some e nada repete
    for parte in partes:
        assert parte == sorted(parte)  # cada parte mantém a ordem original


def test_parte_vazia_quando_ha_menos_itens_que_partes() -> None:
    assert parte_dos_itens(["a", "b"], "3/5") == []
    assert parte_dos_itens(["a", "b"], "2/5") == ["b"]


@pytest.mark.parametrize(
    "parte", ["0/3", "4/3", "1/0", "x", "1-3", "", "1/2/3", "a/b", "-1/3", "١/٣"]
)
def test_texto_invalido_levanta_erro(parte: str) -> None:
    with pytest.raises(ValueError, match="JOBOT_PARTE"):
        parte_dos_itens([1, 2, 3], parte)


class _GanchoFalso:
    def __init__(self) -> None:
        self.saiu: list[list[int]] = []

    def pytest_deselected(self, items: list[int]) -> None:
        self.saiu.append(list(items))


class _ConfigFalso:
    def __init__(self) -> None:
        self.hook = _GanchoFalso()


def _roda_gancho(itens: list[int]) -> _ConfigFalso:
    config = _ConfigFalso()
    pytest_collection_modifyitems(config, itens)  # type: ignore[arg-type]
    return config


def test_gancho_mantem_so_a_parte_e_avisa_o_que_saiu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBOT_PARTE", "2/3")
    itens = list(range(7))
    config = _roda_gancho(itens)
    assert itens == [1, 4]
    assert config.hook.saiu == [[0, 2, 3, 5, 6]]


def test_gancho_sem_a_variavel_nao_mexe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JOBOT_PARTE", raising=False)
    itens = list(range(5))
    config = _roda_gancho(itens)
    assert itens == [0, 1, 2, 3, 4]
    assert config.hook.saiu == []


def test_gancho_com_parte_invalida_levanta_erro_de_uso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBOT_PARTE", "0/3")
    with pytest.raises(pytest.UsageError, match="JOBOT_PARTE"):
        _roda_gancho([1, 2, 3])


def test_gancho_roda_depois_do_filtro_de_marcadores() -> None:
    opcoes = getattr(pytest_collection_modifyitems, "pytest_impl", {})
    assert opcoes.get("trylast") is True
