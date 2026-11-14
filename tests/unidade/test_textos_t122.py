import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2] / "src" / "jobot" / "painel" / "i18n"
IDIOMAS = ["pt", "en"]


def _chaves(idioma: str, arquivo: str) -> dict[str, str]:
    dados: dict[str, str] = json.loads(
        (RAIZ / idioma / f"{arquivo}.json").read_text(encoding="utf-8")
    )
    return dados


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_texto_do_pronto_nao_pergunta(idioma: str) -> None:
    assert "?" not in _chaves(idioma, "primeira_execucao")["primeira_execucao.pronto.texto"]


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_chave_buscar_agora_do_pronto_nao_existe(idioma: str) -> None:
    assert "primeira_execucao.pronto.buscar_agora" not in _chaves(idioma, "primeira_execucao")


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_listagem_incompleta_nao_fala_so_de_304(idioma: str) -> None:
    texto = _chaves(idioma, "comum")["saude.listagem_incompleta"].lower()
    assert not any(p in texto for p in ("não mudou", "did not change", "304", "unchanged"))
