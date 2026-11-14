import json
import re
from pathlib import Path

import pytest

from jobot.nucleo import encaixe
from jobot.nucleo.modelo import Area, Aviso, Contrato, Modalidade, Nivel
from jobot.painel import i18n

AREAS = [e.value for e in Area]
NIVEIS = [e.value for e in Nivel]
MODALIDADES = [e.value for e in Modalidade]
CONTRATOS = [e.value for e in Contrato]
AVISOS = [e.value for e in Aviso]
FONTES = (
    "github_issues remotive remoteok jobicy himalayas wwr hn_algolia greenhouse lever ashby "
    "smartrecruiters gupy inhire quickin recrutei solides abler ciee iel super_estagios "
    "cia_de_talentos eureca usp workday eightfold oracle_hcm google amazon"
).split()
ENCAIXE = (
    "cargo_titulo cargo_descricao cargo_ausente local_remoto modalidade_fora modalidade_ok "
    "modalidade_nao_informada local_cidade local_uf local_fora nivel_nao_informado nivel_ok "
    "nivel_fora salario_nao_informado salario_ok salario_abaixo idioma_ok idioma_nao_detectado "
    "idioma_fora"
).split()
MOTIVOS = (
    "formato_mudou zero_inesperado parcial_n sem_detalhe_n empresa_nao_encontrada bloqueio cota "
    "intervalo orcamento parou_429 limite_atingido tempo_esgotado erro_de_rede resposta_grande "
    "excecao listagem_incompleta"
).split()


def _chaves_fixas() -> list[str]:
    return [
        *[f"area.{v}" for v in AREAS],
        *[f"nivel.{v}" for v in NIVEIS],
        *[f"modalidade.{v}" for v in MODALIDADES],
        *[f"contrato.{v}" for v in CONTRATOS],
        *[f"aviso.{v}" for v in AVISOS],
        *[f"fonte.{v}" for v in FONTES],
        *[f"encaixe.{v}" for v in ENCAIXE],
        *[f"saude.{v}" for v in MOTIVOS],
        "seguranca.recarregue",
    ]


def test_mesmas_chaves_em_pt_e_en() -> None:
    catalogo = i18n.carregar()
    assert set(catalogo) == {"pt", "en"}
    assert set(catalogo["pt"]) == set(catalogo["en"])
    assert catalogo["pt"]


def test_chave_repetida_em_dois_arquivos_falha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pt").mkdir()
    (tmp_path / "pt" / "a.json").write_text(json.dumps({"x.y": "um"}), encoding="utf-8")
    (tmp_path / "pt" / "b.json").write_text(json.dumps({"x.y": "dois"}), encoding="utf-8")
    monkeypatch.setattr(i18n, "PASTA", tmp_path)
    with pytest.raises(ValueError, match="x.y"):
        i18n.carregar()


@pytest.mark.parametrize(
    ("cabecalho", "esperado"),
    [
        ("en-US,en;q=0.9", "en"),
        ("pt-BR,pt;q=0.9,en;q=0.8", "pt"),
        ("fr,en;q=0.5", "en"),
        ("en;q=0.2,pt;q=0.9", "pt"),
        (None, "pt"),
        ("", "pt"),
        ("fr", "pt"),
    ],
)
def test_idioma_inicial(cabecalho: str | None, esperado: str) -> None:
    assert i18n.idioma_inicial(cabecalho) == esperado


def test_parametros() -> None:
    assert "3" in i18n.t("pt", "saude.parcial_n", n=3)
    assert "3" in i18n.t("en", "saude.parcial_n", n=3)
    assert "KeyError" in i18n.t("pt", "saude.excecao", tipo="KeyError")


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_motivos_fixos_existem(idioma: str) -> None:
    catalogo = i18n.carregar().get(idioma, {})
    faltam = [c for c in _chaves_fixas() if not catalogo.get(c)]
    assert faltam == []


def test_textos_pt_e_en_diferem_nos_motivos() -> None:
    assert i18n.t("pt", "seguranca.recarregue") != i18n.t("en", "seguranca.recarregue")


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_chaves_encaixe_existem_em_pt_e_en(idioma: str) -> None:
    """Toda chave `encaixe.*` que o núcleo grava num motivo tem texto no catálogo."""
    usadas = set(re.findall(r'chave="(encaixe\.\w+)"', Path(encaixe.__file__).read_text("utf-8")))
    esperadas = {f"encaixe.{v}" for v in ENCAIXE}
    assert usadas == esperadas, "a lista ENCAIXE saiu de dia com o núcleo"
    arquivo = i18n.PASTA / idioma / "vagas.json"
    textos: dict[str, str] = json.loads(arquivo.read_text("utf-8")) if arquivo.exists() else {}
    assert sorted(c for c in usadas if not textos.get(c)) == []
