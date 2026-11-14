"""Cadastros no banco: fontes, empresas e configuração (plano T23; desenho 8.6 e 13.7)."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from apoio.semear import inserir_vaga
from jobot.banco.cadastros import (
    PADROES,
    adicionar_empresa,
    ativar_empresa,
    empresas,
    empresas_da_coleta,
    empresas_iniciais,
    fontes,
    gravar_config,
    ler_config,
    ligar_fonte,
    remover_empresa,
    semear,
)
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.modelo import Empresa

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
DEPOIS = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)

TOTAL = 83  # as 67 da leva A (seção 7 do apêndice) e as 16 da leva B (T76)

# Identificadores da seção 7 do apêndice de fontes (7.1 a 7.5).
IDENTIFICADORES = {
    "greenhouse": {
        "c6bank",
        "xpinc",
        "bancopan",
        "agibankvagasfuturas",
        "ebanx",
        "ifoodcarreiras",
        "vtex",
        "bees",
        "gympass",
        "vitta",
        "arcoeducacao",
        "quintoandar",
        "wildlifestudios",
        "jusbrasil",
        "kunumi",
    },
    "lever": {
        "bv",
        "starkbank",
        "flashapp",
        "tryjeeves",
        "zippi",
        "ciandt",
        "minders",
        "handoff",
    },
    "ashby": {
        "openai",
        "airwallex",
        "belvo",
        "supabase",
        "zapier",
    },
    "smartrecruiters": {
        "BoschGroup",
        "Experian",
        "SyngentaGroup",
        "Eurofins",
        "Wabtec",
        "NielsenIQ",
        "AveryDennison",
        "ServiceNow",
        "Netbr1",
        "Ubisoft2",
        "Endava",
    },
    "gupy": {
        "localiza",
        "grupotecnospeed",
        "agriness",
        "certsys",
        "montreal",
        "qualitydigital",
        "porto",
        "sicredi",
        "carajas",
        "fortbras",
        "clamedfarma",
        "ambev",
        "weg",
        "suzano",
        "vempracbc",
        "vagasache",
        "beepsaude",
        "hapvidandi",
        "spdmpaisfor",
        "tpc",
        "gruposc",
        "positivo",
        "redebatistadeeducacao",
        "afyamedicina",
        "cnaidiomas",
        "cocamar",
        "ihara",
        "ourofinoagro",
    },
}
INTERRUPTORES = (
    "descoberta_cc_ligada",
    "paginas_ligadas",
    "enriquecimento_ligado",
    "destaques_ligados",
    "conversao_moeda_ligada",
    "regras_ocultar_ligadas",
)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    yield c
    c.close()


def _linha(con: sqlite3.Connection, fonte: str, identificador: str) -> tuple[int, ...]:
    """(id, ativa, removida) da empresa; `removida` é 1 se `removida_em` está preenchido."""
    achou = con.execute(
        "SELECT id, ativa, removida_em IS NOT NULL FROM empresa"
        " WHERE fonte = ? AND identificador = ?",
        (fonte, identificador),
    ).fetchall()
    assert len(achou) == 1, f"esperava uma linha de {fonte}/{identificador}, achei {len(achou)}"
    return tuple(achou[0])


def _total(con: sqlite3.Connection, tabela: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0])


def test_empresas_json_tem_67() -> None:
    assert len(empresas_iniciais()) == TOTAL
    lista = [e for e in empresas_iniciais() if e.fonte in IDENTIFICADORES]  # a leva A
    assert len(lista) == 67
    por_fonte: dict[str, set[str]] = {}
    for e in lista:
        por_fonte.setdefault(e.fonte, set()).add(e.identificador)
    assert {f: len(v) for f, v in por_fonte.items()} == {
        "greenhouse": 15,
        "lever": 8,
        "ashby": 5,
        "smartrecruiters": 11,
        "gupy": 28,
    }
    assert por_fonte == IDENTIFICADORES
    assert len({(e.fonte, e.identificador) for e in lista}) == 67
    assert all(e.origem == "lista_inicial" and e.ativa and e.removida_em is None for e in lista)
    assert all(e.nome and e.area and e.conferida_em == date(2026, 11, 13) for e in lista)


def test_semear_grava_fontes_e_empresas(con: sqlite3.Connection) -> None:
    semear(con)
    assert _total(con, "fonte") == 28
    assert _total(con, "empresa") == TOTAL
    origem = con.execute("SELECT DISTINCT origem FROM empresa").fetchall()
    assert origem == [("lista_inicial",)]
    c6 = [e for e in empresas(con) if e.identificador == "c6bank"][0]
    assert (c6.nome, c6.fonte, c6.pais, c6.parametros) == ("C6 Bank", "greenhouse", "BR", {})
    assert c6.conferida_em == date(2026, 11, 13)
    assert c6.id is not None


def test_semear_duas_vezes_nao_duplica(con: sqlite3.Connection) -> None:
    semear(con)
    ids = con.execute("SELECT id, fonte, identificador FROM empresa ORDER BY id").fetchall()
    semear(con)
    assert _total(con, "fonte") == 28
    assert _total(con, "empresa") == TOTAL
    assert con.execute("SELECT id, fonte, identificador FROM empresa ORDER BY id").fetchall() == ids


def test_semear_nao_sobrescreve_o_que_a_pessoa_mudou(con: sqlite3.Connection) -> None:
    semear(con)
    ligar_fonte(con, "remotive", False)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    ativar_empresa(con, c6, False)
    con.execute("UPDATE empresa SET nome = 'Meu C6', area = 'minha' WHERE id = ?", (c6,))
    con.commit()
    semear(con)
    assert [f.chave for f in fontes(con) if not f.ligada] == ["remotive"]
    assert _linha(con, "greenhouse", "c6bank") == (c6, 0, 0)
    assert con.execute("SELECT nome, area FROM empresa WHERE id = ?", (c6,)).fetchone() == (
        "Meu C6",
        "minha",
    )


def test_semear_acrescenta_so_o_que_falta(con: sqlite3.Connection) -> None:
    semear(con)
    xp = _linha(con, "greenhouse", "xpinc")[0]
    con.execute("DELETE FROM empresa WHERE id = ?", (xp,))  # lista atualizada: entrada nova
    con.commit()
    semear(con)
    assert _total(con, "empresa") == TOTAL
    assert _linha(con, "greenhouse", "xpinc")[1:] == (1, 0)


def test_intervalo_min_copiado_para_fonte(con: sqlite3.Connection) -> None:
    semear(con)
    por_chave = {f.chave: f for f in fontes(con)}
    assert len(por_chave) == 28
    assert por_chave["remotive"].intervalo_min == 360
    assert por_chave["jobicy"].intervalo_min == 60
    assert por_chave["google"].intervalo_min == 1440
    assert por_chave["greenhouse"].intervalo_min is None
    assert por_chave["gupy"].leva == "A"
    assert por_chave["workday"].leva == "B"
    # o valor do arquivo vale sobre o da tabela; `ligada` não é tocada
    con.execute("UPDATE fonte SET intervalo_min = 5 WHERE chave = 'remotive'")
    con.commit()
    semear(con)
    assert {f.chave: f.intervalo_min for f in fontes(con)}.get("remotive") == 360


def test_ligar_e_desligar_fonte(con: sqlite3.Connection) -> None:
    semear(con)
    assert all(f.ligada for f in fontes(con))
    ligar_fonte(con, "wwr", False)
    assert [f.chave for f in fontes(con) if not f.ligada] == ["wwr"]
    ligar_fonte(con, "wwr", True)
    assert all(f.ligada for f in fontes(con))


def test_ligar_fonte_inexistente_levanta_lookup(con: sqlite3.Connection) -> None:
    semear(con)
    with pytest.raises(LookupError):
        ligar_fonte(con, "nao_existe", False)


def test_remover_marca_removida_em_e_mantem_linha(con: sqlite3.Connection) -> None:
    semear(con)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    remover_empresa(con, c6, AGORA)
    assert _total(con, "empresa") == TOTAL
    assert con.execute("SELECT removida_em FROM empresa WHERE id = ?", (c6,)).fetchone() == (
        AGORA.isoformat(),
    )
    assert c6 not in {e.id for e in empresas(con)}
    assert len(empresas(con)) == TOTAL - 1


def test_remover_duas_vezes_mantem_a_primeira_data(con: sqlite3.Connection) -> None:
    semear(con)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    remover_empresa(con, c6, AGORA)
    remover_empresa(con, c6, DEPOIS)
    assert con.execute("SELECT removida_em FROM empresa WHERE id = ?", (c6,)).fetchone() == (
        AGORA.isoformat(),
    )


def test_remover_exige_fuso_e_empresa_existente(con: sqlite3.Connection) -> None:
    semear(con)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    with pytest.raises(ValueError):
        remover_empresa(con, c6, datetime(2026, 11, 13, 12, 0))
    with pytest.raises(LookupError):
        remover_empresa(con, 99999, AGORA)
    assert _linha(con, "greenhouse", "c6bank") == (c6, 1, 0)


def test_semear_pula_removida_sem_criar_linha(con: sqlite3.Connection) -> None:
    semear(con)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    remover_empresa(con, c6, AGORA)
    semear(con)
    assert _total(con, "empresa") == TOTAL
    assert _linha(con, "greenhouse", "c6bank") == (c6, 1, 1)
    assert c6 not in {e.id for e in empresas(con)}


def test_readicionar_limpa_removida_em(con: sqlite3.Connection) -> None:
    semear(con)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    ativar_empresa(con, c6, False)
    remover_empresa(con, c6, AGORA)
    novo = adicionar_empresa(
        con,
        Empresa(nome="C6 Bank S.A.", fonte="greenhouse", identificador="c6bank", origem="pessoa"),
    )
    assert novo == c6
    assert _total(con, "empresa") == TOTAL
    assert _linha(con, "greenhouse", "c6bank") == (c6, 1, 0)
    volta = [e for e in empresas(con) if e.id == c6][0]
    assert volta.nome == "C6 Bank S.A."
    assert volta.origem == "lista_inicial"  # a linha é a mesma; a origem não muda


def test_adicionar_empresa_nova(con: sqlite3.Connection) -> None:
    semear(con)
    novo = adicionar_empresa(
        con,
        Empresa(
            nome="Acme",
            fonte="smartrecruiters",
            identificador="AcmeBR",
            area="tecnologia",
            pais="BR",
            parametros={"account_id": "a1"},
            origem="pessoa",
        ),
    )
    assert _total(con, "empresa") == TOTAL + 1
    acme = [e for e in empresas(con) if e.id == novo][0]
    assert (acme.nome, acme.fonte, acme.identificador, acme.area, acme.pais) == (
        "Acme",
        "smartrecruiters",
        "AcmeBR",
        "tecnologia",
        "BR",
    )
    assert dict(acme.parametros) == {"account_id": "a1"}
    assert acme.origem == "pessoa" and acme.ativa and acme.removida_em is None
    assert acme in empresas_da_coleta(con)


def test_adicionar_empresa_recusa_dado_invalido(con: sqlite3.Connection) -> None:
    semear(con)
    with pytest.raises(ValueError):
        adicionar_empresa(con, Empresa(nome=" ", fonte="greenhouse", identificador="x"))
    with pytest.raises(ValueError):
        adicionar_empresa(con, Empresa(nome="X", fonte="greenhouse", identificador=" "))
    with pytest.raises(ValueError):
        adicionar_empresa(con, Empresa(nome="X", fonte="nao_existe", identificador="x"))
    assert _total(con, "empresa") == TOTAL


def test_ativar_empresa(con: sqlite3.Connection) -> None:
    semear(con)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    ativar_empresa(con, c6, False)
    assert _linha(con, "greenhouse", "c6bank") == (c6, 0, 0)
    assert c6 in {e.id for e in empresas(con)}  # desligada continua na tela, só não é buscada
    ativar_empresa(con, c6, True)
    assert _linha(con, "greenhouse", "c6bank") == (c6, 1, 0)
    with pytest.raises(LookupError):
        ativar_empresa(con, 99999, True)


def test_contexto_coleta_ignora_removida(con: sqlite3.Connection) -> None:
    semear(con)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    xp = _linha(con, "greenhouse", "xpinc")[0]
    remover_empresa(con, c6, AGORA)
    ativar_empresa(con, xp, False)
    da_coleta = empresas_da_coleta(con)
    assert isinstance(da_coleta, tuple)
    assert len(da_coleta) == TOTAL - 2
    assert {e.id for e in da_coleta}.isdisjoint({c6, xp})
    assert all(e.ativa and e.removida_em is None and e.id is not None for e in da_coleta)


def test_remover_empresa_mantem_as_vagas(con: sqlite3.Connection) -> None:
    semear(con)
    c6 = _linha(con, "greenhouse", "c6bank")[0]
    vaga = inserir_vaga(con, fonte="greenhouse", empresa="C6 Bank", descricao_texto="Texto da vaga")
    remover_empresa(con, c6, AGORA)
    assert con.execute(
        "SELECT empresa, descricao_texto, fechada_em FROM vaga WHERE id = ?", (vaga,)
    ).fetchone() == ("C6 Bank", "Texto da vaga", None)
    assert _total(con, "ocorrencia") == 1


def test_padroes_de_config(con: sqlite3.Connection) -> None:
    for chave in INTERRUPTORES:
        assert ler_config(con, chave) is True, chave
    assert ler_config(con, "destaques_n") == 10
    assert set(PADROES) == {*INTERRUPTORES, "destaques_n"}


def test_gravar_e_ler_config(con: sqlite3.Connection) -> None:
    gravar_config(con, "destaques_ligados", False)
    gravar_config(con, "destaques_n", 5)
    gravar_config(con, "idioma", "en")
    assert ler_config(con, "destaques_ligados") is False
    assert ler_config(con, "destaques_n") == 5
    assert ler_config(con, "idioma", "pt") == "en"
    gravar_config(con, "destaques_n", 7)  # grava por cima, sem duplicar a chave
    assert ler_config(con, "destaques_n") == 7
    assert _total(con, "config") == 3
    assert con.execute("SELECT valor FROM config WHERE chave = 'idioma'").fetchone() == ('"en"',)
    assert not con.in_transaction


def test_config_sem_gravar_devolve_o_padrao_dado(con: sqlite3.Connection) -> None:
    assert ler_config(con, "idioma", "pt") == "pt"
    assert ler_config(con, "segundo_plano", None) is None
    with pytest.raises(KeyError):  # sem padrão do código nem padrão dado, não chuta
        ler_config(con, "segundo_plano")


def test_config_com_json_estragado_devolve_o_padrao(con: sqlite3.Connection) -> None:
    con.execute("INSERT INTO config (chave, valor) VALUES ('destaques_n', 'não é json')")
    con.commit()
    assert ler_config(con, "destaques_n") == 10


def test_config_recusa_valor_que_nao_e_json(con: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        gravar_config(con, "destaques_n", float("nan"))
    with pytest.raises(TypeError):
        gravar_config(con, "destaques_n", object())
    assert _total(con, "config") == 0
