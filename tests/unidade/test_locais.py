import json
from pathlib import Path

import pytest

from jobot.nucleo.modelo import Local
from jobot.nucleo.tratamento.locais import ler_locais

UFS = Path(__file__).resolve().parents[2] / "src" / "jobot" / "nucleo" / "dados" / "ufs.json"
SIGLAS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("São Paulo - SP", Local(cidade="São Paulo", uf="SP", pais="BR")),
        ("Sao Paulo, Brazil", Local(cidade="Sao Paulo", pais="BR")),
        ("Remote - Brazil", Local(pais="BR")),
        ("Lisboa, Portugal", Local(cidade="Lisboa", pais="PT")),
        ("Curitiba, Paraná, BRASIL", Local(cidade="Curitiba", uf="PR", pais="BR")),
        ("Belo Horizonte/MG", Local(cidade="Belo Horizonte", uf="MG", pais="BR")),
        ("SP", Local(uf="SP", pais="BR")),
        ("Hybrid - Curitiba, PR", Local(cidade="Curitiba", uf="PR", pais="BR")),
        ("Híbrido - São Paulo, SP", Local(cidade="São Paulo", uf="SP", pais="BR")),
        ("Presencial - Recife - PE", Local(cidade="Recife", uf="PE", pais="BR")),
        ("On-site, Lisboa, Portugal", Local(cidade="Lisboa", pais="PT")),
        ("Guarulhos-SP", Local(cidade="Guarulhos", uf="SP", pais="BR")),
        ("Remote-Brazil", Local(pais="BR")),
        ("Boston, MA, USA", Local(cidade="Boston", pais="US")),
        ("Madrid, ES, Spain", Local(cidade="Madrid", pais="ES")),
        ("Fortaleza, CE, Brazil", Local(cidade="Fortaleza", uf="CE", pais="BR")),
    ],
)
def test_cidade_uf(bruto: str, esperado: Local) -> None:
    assert ler_locais([bruto]) == (esperado,)


@pytest.mark.parametrize(
    ("bruto", "cidade"),
    [
        ("Pittsburgh, PA", "Pittsburgh"),
        ("Pittsburgh - PA", "Pittsburgh"),
        ("Boston, MA", "Boston"),
        ("Birmingham, AL", "Birmingham"),
        ("Charleston, SC", "Charleston"),
        ("Jackson, MS", "Jackson"),
        ("Billings, MT", "Billings"),
    ],
)
def test_cidade_estrangeira_com_estado_nao_vira_estado_brasileiro(bruto: str, cidade: str) -> None:
    # sigla de estado dos EUA que também é de UF (PA, MA, AL, SC, MS, MT): cidade dos EUA conhecida
    assert ler_locais([bruto]) == (Local(cidade=cidade, pais="US"),)


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("Belém, PA", Local(cidade="Belém", uf="PA", pais="BR")),
        ("Florianópolis - SC", Local(cidade="Florianópolis", uf="SC", pais="BR")),
        ("São Luís/MA", Local(cidade="São Luís", uf="MA", pais="BR")),
        ("Campo Grande, MS", Local(cidade="Campo Grande", uf="MS", pais="BR")),
    ],
)
def test_cidade_brasileira_com_sigla_que_os_eua_tambem_usam_segue_brasileira(
    bruto: str, esperado: Local
) -> None:
    assert ler_locais([bruto]) == (esperado,)


def test_varias_cidades_viram_varios_locais() -> None:
    sp = Local(cidade="São Paulo", uf="SP", pais="BR")
    rj = Local(cidade="Rio de Janeiro", uf="RJ", pais="BR")
    assert ler_locais(["São Paulo - SP", "Rio de Janeiro - RJ"]) == (sp, rj)
    assert ler_locais(["São Paulo - SP; Rio de Janeiro - RJ"]) == (sp, rj)


def test_27_ufs_no_json() -> None:
    ufs = json.loads(UFS.read_text(encoding="utf-8"))
    assert len(ufs) == 27
    assert len({u["sigla"] for u in ufs}) == 27
    assert all(len(u["sigla"]) == 2 and u["nome"] for u in ufs)
    assert {u["sigla"] for u in ufs} == set(SIGLAS)


@pytest.mark.parametrize("bruto", ["asdf qwerty", "???", "Curitiba", "12345"])
def test_texto_desconhecido_vira_local_vazio_sem_erro(bruto: str) -> None:
    assert ler_locais([bruto]) == (Local(),)


def test_sem_entrada_ou_so_espacos_nao_devolve_local() -> None:
    assert ler_locais([]) == ()
    assert ler_locais(["", "   "]) == ()


@pytest.mark.parametrize(
    "bruto", ["Remote", "Worldwide", "Anywhere", "LATAM", "Americas", "Europe", "Remote - LATAM"]
)
def test_remoto_mundial_ou_regiao_fica_sem_pais(bruto: str) -> None:
    assert ler_locais([bruto]) == (Local(),)


def test_texto_desconhecido_ao_lado_de_local_real_e_descartado() -> None:
    assert ler_locais(["asdf; SP"]) == (Local(uf="SP", pais="BR"),)
    assert ler_locais(["asdf", "São Paulo - SP"]) == (
        Local(cidade="São Paulo", uf="SP", pais="BR"),
    )
