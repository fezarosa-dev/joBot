from dataclasses import replace
from typing import Any

import pytest

from jobot.nucleo.modelo import (
    Area,
    Aviso,
    Local,
    Modalidade,
    Nivel,
    VagaColetada,
    VagaTratada,
)
from jobot.nucleo.tratamento.medicao import (
    Acerto,
    Esperado,
    Medicao,
    esperado_da_linha,
    medir,
    vaga_do_bruto,
)
from jobot.nucleo.tratamento.tratar import tratar

ROTULOS: dict[str, Any] = {
    "area": "tecnologia",
    "nivel": "junior",
    "modalidade": "remoto",
    "contrato": "clt",
    "pais": "BR",
    "uf": "SP",
    "avisos": [],
}


def _tratada(**campos: Any) -> VagaTratada:
    base = VagaColetada(
        fonte="teste",
        escopo="",
        url="https://exemplo.com/vaga/1",
        titulo="Desenvolvedor Python Júnior",
        empresa="Acme",
        descricao_formato="texto",
        descricao="Vaga para desenvolvedor Python júnior, contratação CLT, em São Paulo.",
        locais=("São Paulo, SP",),
    )
    return replace(tratar(base), **campos)


def _esperado(**campos: Any) -> Esperado:
    return esperado_da_linha({"id": "x", "rotulos": ROTULOS | campos})[1]


def _bruto(**campos: Any) -> dict[str, Any]:
    base = {
        "id": "b1",
        "fonte": "fonte_a",
        "url": "https://exemplo.com/vagas/b1",
        "titulo": "Analista de Dados",
        "empresa": "Acme Exemplo",
        "local": "Recife, PE",
        "descricao_texto": "texto puro da vaga",
        "descricao_html": "",
        "metadados": {},
        "coletado_em": "2026-11-13T12:00:00+00:00",
    }
    return base | campos


def test_monta_vaga_do_bruto() -> None:
    com_html = vaga_do_bruto(_bruto(descricao_html="<p>html da vaga</p>"))
    assert (com_html.descricao_formato, com_html.descricao) == ("html", "<p>html da vaga</p>")

    so_texto = vaga_do_bruto(_bruto())
    assert (so_texto.descricao_formato, so_texto.descricao) == ("texto", "texto puro da vaga")
    assert so_texto.locais == ("Recife, PE",)
    assert (so_texto.fonte, so_texto.url) == ("fonte_a", "https://exemplo.com/vagas/b1")
    assert (so_texto.titulo, so_texto.empresa) == ("Analista de Dados", "Acme Exemplo")
    assert so_texto.modalidade_declarada is None
    assert so_texto.contrato_declarado is None


def test_monta_vaga_do_bruto_sem_local() -> None:
    assert vaga_do_bruto(_bruto(local="Recife, PE")).locais == ("Recife, PE",)
    assert vaga_do_bruto(_bruto(local="")).locais == ()
    assert vaga_do_bruto(_bruto(local=None)).locais == ()


def test_metadados_nao_entram_na_vaga() -> None:
    a = vaga_do_bruto(_bruto(metadados={"workplaceType": "hybrid", "salaryPeriod": "year"}))
    b = vaga_do_bruto(_bruto(metadados={}))
    assert a == b
    assert a.titulo == "Analista de Dados"


def test_esperado_da_linha_le_so_id_e_rotulos() -> None:
    linha = {"id": "z9", "rotulos": ROTULOS | {"avisos": ["exige_visto"]}, "divergencias": {"a": 1}}
    assert esperado_da_linha(linha) == (
        "z9",
        Esperado(
            area="tecnologia",
            nivel="junior",
            modalidade="remoto",
            contrato="clt",
            pais="BR",
            uf="SP",
            avisos=frozenset({"exige_visto"}),
        ),
    )


def test_uf_nula_e_uf_ausente_sao_sem_uf() -> None:
    sem_chave = {k: v for k, v in ROTULOS.items() if k != "uf"}
    nula = esperado_da_linha({"id": "a", "rotulos": ROTULOS | {"uf": None}})[1]
    ausente = esperado_da_linha({"id": "a", "rotulos": sem_chave})[1]
    assert (nula.pais, nula.uf) == ("BR", None)
    assert (ausente.pais, ausente.uf) == ("BR", None)


def test_linha_sem_rotulo_obrigatorio_levanta_valueerror() -> None:
    sem_area = {k: v for k, v in ROTULOS.items() if k != "area"}
    with pytest.raises(ValueError, match="area"):
        esperado_da_linha({"id": "a", "rotulos": sem_area})


def test_medir_conta_certos_e_lista_erros() -> None:
    vagas = {
        "a": _tratada(area=Area.TECNOLOGIA, nivel=Nivel.JUNIOR, modalidade=Modalidade.REMOTO),
        "b": _tratada(area=Area.DADOS, nivel=Nivel.JUNIOR, modalidade=Modalidade.REMOTO),
    }
    rotulos = {"a": _esperado(), "b": _esperado()}
    m = medir(vagas, rotulos)
    assert isinstance(m, Medicao)
    assert (m.por_rotulo["area"].certos, m.por_rotulo["area"].total) == (1, 2)
    assert (m.por_rotulo["nivel"].certos, m.por_rotulo["nivel"].total) == (2, 2)
    erro_area = [e for e in m.erros if e.rotulo == "area"]
    assert [(e.id, e.esperado, e.obtido) for e in erro_area] == [("b", "tecnologia", "dados")]


def test_medir_mede_os_sete_rotulos() -> None:
    m = medir({"a": _tratada()}, {"a": _esperado()})
    assert set(m.por_rotulo) == {
        "area",
        "nivel",
        "modalidade",
        "contrato",
        "avisos",
        "pais",
        "uf",
    }


def test_acerto_de_avisos_compara_conjuntos() -> None:
    esperado = _esperado(avisos=["exige_visto", "restrito_a_pais"])
    ordem_trocada = _tratada(avisos=(Aviso.RESTRITO_A_PAIS, Aviso.EXIGE_VISTO))
    so_um = _tratada(avisos=(Aviso.EXIGE_VISTO,))
    sobrando = _tratada(avisos=(Aviso.EXIGE_VISTO, Aviso.RESTRITO_A_PAIS, Aviso.EXIGE_DOUTORADO))
    m = medir(
        {"a": ordem_trocada, "b": so_um, "c": sobrando},
        {"a": esperado, "b": esperado, "c": esperado},
    )
    assert m.por_rotulo["avisos"].certos == 1
    assert [e.id for e in m.erros if e.rotulo == "avisos"] == ["b", "c"]


def test_sem_aviso_dos_dois_lados_conta_como_certo() -> None:
    m = medir({"a": _tratada(avisos=())}, {"a": _esperado(avisos=[])})
    assert m.por_rotulo["avisos"] == Acerto(certos=1, total=1)


def test_vaga_sem_rotulo_fica_fora_da_amostra() -> None:
    vagas = {"a": _tratada(), "b": _tratada(), "c": _tratada(area=Area.DADOS)}
    rotulos = {"a": _esperado(), "b": _esperado(), "orfao": _esperado(pais="BR")}
    m = medir(vagas, rotulos)
    assert {a.total for a in m.por_rotulo.values()} == {2}
    # nem a vaga sem rótulo (c) nem o rótulo sem vaga (orfao) geram erro ou entram na proporção
    assert {e.id for e in m.erros} <= {"a", "b"}
    assert m.proporcao_br == 1.0


def test_pais_nulo_nao_conta_como_br() -> None:
    vagas = {
        "br": _tratada(),
        "nulo": _tratada(locais=()),
        "de": _tratada(locais=(Local(cidade="Berlin", pais="DE"),)),
        "nulo2": _tratada(locais=(Local(),)),
    }
    rotulos = {
        "br": _esperado(),
        "nulo": _esperado(pais=None, uf=None),
        "de": _esperado(pais="DE", uf=None),
        "nulo2": _esperado(pais=None, uf=None),
    }
    m = medir(vagas, rotulos)
    assert m.proporcao_br == 0.25  # 1 BR sobre 4; os dois null contam no total, não em BR
    assert m.por_rotulo["pais"].certos == 4  # null esperado e null obtido é acerto
    assert m.por_rotulo["uf"].certos == 4


def test_pais_nulo_com_obtido_diferente_e_erro_sem_quebrar() -> None:
    m = medir({"a": _tratada()}, {"a": _esperado(pais=None, uf=None)})
    assert m.proporcao_br == 0.0
    achados = {(e.rotulo, e.esperado, e.obtido) for e in m.erros}
    assert ("pais", "nenhum", "BR") in achados
    assert ("uf", "nenhum", "SP") in achados


def test_uf_sem_pais_no_local_vale_como_brasil() -> None:
    v = _tratada(locais=(Local(cidade="Recife", uf="PE", pais=None),))
    m = medir({"a": v}, {"a": _esperado(uf="PE")})
    assert m.por_rotulo["pais"].certos == 1
    assert m.por_rotulo["uf"].certos == 1


def test_sem_vagas_na_amostra_nao_divide_por_zero() -> None:
    m = medir({}, {})
    assert m.proporcao_br == 0.0
    assert all(a.total == 0 for a in m.por_rotulo.values())
