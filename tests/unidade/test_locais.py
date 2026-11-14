import json
from pathlib import Path

import pytest

from jobot.nucleo.modelo import Local
from jobot.nucleo.tratamento.locais import (
    _PAISES,
    ler_locais,
    nome_do_pais,
    nome_em_ingles,
    pais_escrito,
)

UFS = Path(__file__).resolve().parents[2] / "src" / "jobot" / "nucleo" / "dados" / "ufs.json"
SIGLAS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("São Paulo - SP", Local(cidade="São Paulo", uf="SP", pais="BR")),
        ("Sao Paulo, Brazil", Local(cidade="Sao Paulo", uf="SP", pais="BR")),
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


@pytest.mark.parametrize(
    "bruto", ["asdf qwerty", "???", "Victoria", "12345", "Remote US Timezones"]
)
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


def test_nome_do_pais_br_e_us() -> None:
    assert nome_do_pais("BR") == "Brasil"
    assert nome_do_pais("US") == "Estados Unidos"
    assert nome_do_pais("FR") == "França"
    assert nome_do_pais("ZZ") is None


def test_nome_em_ingles_br_us_gb() -> None:
    assert nome_em_ingles("BR") == "Brazil"
    assert nome_em_ingles("US") == "United States"
    assert nome_em_ingles("GB") == "United Kingdom"
    assert nome_em_ingles("MX") == "Mexico"
    assert nome_em_ingles("ZZ") is None
    assert nome_em_ingles("br") is None  # o código é ISO em maiúsculas, como em `nome_do_pais`
    # todo nome em inglês volta ao próprio código pelo leitor de locais
    for codigo in set(_PAISES.values()):
        nome = nome_em_ingles(codigo)
        assert nome is not None
        assert [lido.pais for lido in ler_locais([nome])] == [codigo]


def test_nome_do_pais_de_todo_codigo_volta_ao_mesmo_codigo() -> None:
    for codigo in set(_PAISES.values()):
        nome = nome_do_pais(codigo)
        assert nome is not None
        assert [local.pais for local in ler_locais([nome])] == [codigo]


def test_estados_unidos_da_america_e_us() -> None:
    assert ler_locais(["Estados Unidos da América"]) == (Local(pais="US"),)


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("São Paulo", Local(cidade="São Paulo", uf="SP", pais="BR")),
        ("SÃO PAULO", Local(cidade="SÃO PAULO", uf="SP", pais="BR")),
        ("Curitiba", Local(cidade="Curitiba", uf="PR", pais="BR")),
        ("Brasilia", Local(cidade="Brasilia", uf="DF", pais="BR")),
        ("Campinas", Local(cidade="Campinas", uf="SP", pais="BR")),
        ("São Paulo Office", Local(cidade="São Paulo", uf="SP", pais="BR")),
        ("Rio de Janeiro, Brasil", Local(cidade="Rio de Janeiro", uf="RJ", pais="BR")),
        ("Brazil, São Paulo, Campinas", Local(cidade="São Paulo", uf="SP", pais="BR")),
    ],
)
def test_capital_ou_cidade_grande_sem_uf_ganha_a_uf(bruto: str, esperado: Local) -> None:
    assert ler_locais([bruto]) == (esperado,)


def test_cidade_brasileira_com_pais_de_fora_nao_ganha_uf() -> None:
    # nome igual ao de capital, mas o país escrito é outro: o país vence
    assert ler_locais(["Natal, Portugal"]) == (Local(cidade="Natal", pais="PT"),)


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("Austin, TX", Local(cidade="Austin", pais="US")),
        ("Paris, TX", Local(cidade="Paris", pais="US")),
        ("Toronto, ON, CA", Local(cidade="Toronto", pais="CA")),
        ("Vancouver, BC, CA", Local(cidade="Vancouver", pais="CA")),
        ("Tel Aviv, IL", Local(cidade="Tel Aviv", pais="IL")),
        ("London, ON", Local(cidade="London", pais="CA")),
        ("Amsterdam, NL", Local(cidade="Amsterdam", pais="NL")),
        ("Berlin Office", Local(cidade="Berlin", pais="DE")),
        ("New York, NY", Local(cidade="New York", pais="US")),
        ("San Francisco, CA", Local(cidade="San Francisco", pais="US")),
        ("USA Only", Local(pais="US")),
        ("US only", Local(pais="US")),
        ("Remote US", Local(pais="US")),
        ("United States of America", Local(pais="US")),
        ("U.S.", Local(pais="US")),
        ("Philippines", Local(pais="PH")),
        ("Deutschland", Local(pais="DE")),
        ("Poland", Local(pais="PL")),
        ("Berlin", Local(cidade="Berlin", pais="DE")),
        ("Berlin, DE", Local(cidade="Berlin", pais="DE")),
        ("London", Local(cidade="London", pais="GB")),
        ("Toronto, ON", Local(cidade="Toronto", pais="CA")),
    ],
)
def test_pais_de_fora_por_estado_nome_ou_cidade_conhecida(bruto: str, esperado: Local) -> None:
    assert ler_locais([bruto]) == (esperado,)


def test_sigla_de_uf_vence_estado_dos_eua() -> None:
    # "ES" é Espírito Santo; "PA" é Pará fora da lista de cidades dos EUA
    assert ler_locais(["Vitória, ES"]) == (Local(cidade="Vitória", uf="ES", pais="BR"),)
    assert ler_locais(["Belém - PA"]) == (Local(cidade="Belém", uf="PA", pais="BR"),)


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("Austin, TX", None),
        ("Austin", None),
        ("Curitiba, PR", None),
        ("Austin, USA", "US"),
        ("Remote - Brazil", "BR"),
        ("Sao Paulo, Brasil", "BR"),
    ],
)
def test_pais_escrito_so_com_o_nome_do_pais(bruto: str, esperado: str | None) -> None:
    assert pais_escrito(bruto) == esperado
