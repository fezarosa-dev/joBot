import json
from pathlib import Path

import pytest

from jobot.painel import i18n

AREAS = (
    "tecnologia dados design produto marketing vendas financas rh juridico operacoes "
    "engenharia saude educacao administrativo atendimento pesquisa outra"
).split()
NIVEIS = "estagio trainee junior pleno senior especialista lideranca nao_informado".split()
MODALIDADES = "presencial hibrido remoto nao_informado".split()
CONTRATOS = (
    "clt pj estagio trainee temporario aprendiz bolsa_pesquisa programa concurso freelance "
    "nao_informado"
).split()
AVISOS = "exige_visto exige_doutorado restrito_a_pais".split()
FONTES = (
    "github_issues remotive remoteok jobicy himalayas wwr hn_algolia greenhouse lever ashby "
    "smartrecruiters gupy inhire quickin recrutei solides abler ciee iel super_estagios "
    "cia_de_talentos eureca usp workday eightfold oracle_hcm google amazon"
).split()
MOTIVOS = (
    "formato_mudou zero_inesperado parcial_n sem_detalhe_n empresa_nao_encontrada bloqueio cota "
    "intervalo orcamento parou_429 limite_atingido tempo_esgotado erro_de_rede resposta_grande "
    "excecao"
).split()


def _chaves_fixas() -> list[str]:
    return [
        *[f"area.{v}" for v in AREAS],
        *[f"nivel.{v}" for v in NIVEIS],
        *[f"modalidade.{v}" for v in MODALIDADES],
        *[f"contrato.{v}" for v in CONTRATOS],
        *[f"aviso.{v}" for v in AVISOS],
        *[f"fonte.{v}" for v in FONTES],
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
