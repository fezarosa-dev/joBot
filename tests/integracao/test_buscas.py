"""Buscas salvas e encaixe no banco (desenho 7.3 e 11; plano T24, decisões 1, 12, 17 e 18)."""

import json
import sqlite3
import threading
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from apoio.semear import AGORA, inserir_vaga
from jobot.banco.buscas import (
    apagar_busca,
    buscas,
    criar_busca,
    editar_busca,
    minimo_busca_brl,
    paises_das_buscas,
    recalcular_encaixe,
    termos_das_buscas,
)
from jobot.banco.conexao import abrir
from jobot.banco.cotacoes import gravar_cotacao
from jobot.banco.leitura import Filtros, listar
from jobot.banco.migrar import migrar
from jobot.nucleo.cambio import Cotacao
from jobot.nucleo.modelo import Busca, Local, Modalidade, Nivel

HOJE = date(2026, 11, 13)


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    yield c
    c.close()


def _cotar(con: sqlite3.Connection, moeda: str, venda: str, dia: date = HOJE) -> None:
    gravar_cotacao(con, Cotacao(moeda=moeda, data=dia, venda=Decimal(venda)), AGORA)


def _busca(con: sqlite3.Connection, **campos: Any) -> int:
    base: dict[str, Any] = {"nome": "Minha busca"}
    return criar_busca(con, Busca(**(base | campos)), AGORA, regras_ligadas=True, hoje=HOJE)


def _encaixe(con: sqlite3.Connection, busca_id: int, vaga_id: int) -> tuple[object, ...] | None:
    linha = con.execute(
        "SELECT nota, nivel, motivos, oculta_motivo FROM encaixe WHERE busca_id=? AND vaga_id=?",
        (busca_id, vaga_id),
    ).fetchone()
    return None if linha is None else tuple(linha)


def _chaves(motivos: str) -> list[str]:
    return [m["chave"] for m in json.loads(motivos)]


def _motivos_de(con: sqlite3.Connection, busca_id: int, vaga_id: int) -> list[str] | None:
    linha = _encaixe(con, busca_id, vaga_id)
    return None if linha is None else _chaves(str(linha[2]))


def _limpar_encaixe(con: sqlite3.Connection) -> None:
    con.execute("DELETE FROM encaixe")
    con.commit()


# --- cadastro das buscas ---


def test_criar_e_ler_busca_guarda_todos_os_campos(con: sqlite3.Connection) -> None:
    bid = criar_busca(
        con,
        Busca(
            nome="Backend",
            ativa=False,
            cargos=("python", "backend"),
            cidades=(Local(cidade="Recife", uf="PE", pais="BR"), Local(pais="PT")),
            modalidades=(Modalidade.REMOTO, Modalidade.HIBRIDO),
            niveis=(Nivel.JUNIOR,),
            salario_min_centavos=500000,
            salario_moeda="USD",
            idiomas=("pt", "en"),
            regras_ocultar={"salario": False},
        ),
        AGORA,
        regras_ligadas=True,
        hoje=HOJE,
    )
    lidas = buscas(con)
    assert len(lidas) == 1
    lida = lidas[0]
    assert lida.id == bid
    assert lida.nome == "Backend"
    assert lida.ativa is False
    assert lida.cargos == ("python", "backend")
    assert lida.cidades == (Local(cidade="Recife", uf="PE", pais="BR"), Local(pais="PT"))
    assert lida.modalidades == (Modalidade.REMOTO, Modalidade.HIBRIDO)
    assert lida.niveis == (Nivel.JUNIOR,)
    assert (lida.salario_min_centavos, lida.salario_moeda) == (500000, "USD")
    assert lida.idiomas == ("pt", "en")
    assert dict(lida.regras_ocultar) == {"salario": False}
    assert lida.criada_em == AGORA


def test_busca_invalida_levanta_value_error_sem_gravar(con: sqlite3.Connection) -> None:
    for campos in (
        {"nome": "  "},
        {"salario_min_centavos": -1},
        {"salario_min_centavos": 2**63},  # estoura o INTEGER do SQLite
        {"salario_min_centavos": 100, "salario_moeda": "XYZ"},
    ):
        with pytest.raises(ValueError):
            criar_busca(
                con, Busca(**({"nome": "x"} | campos)), AGORA, regras_ligadas=True, hoje=HOJE
            )
    assert buscas(con) == []
    assert not con.in_transaction


def test_editar_e_apagar_busca_inexistente_levanta_lookup_error(con: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        editar_busca(con, Busca(nome="x", id=99), regras_ligadas=True, hoje=HOJE)
    with pytest.raises(LookupError):
        apagar_busca(con, 99)
    with pytest.raises(ValueError):  # sem id
        editar_busca(con, Busca(nome="x"), regras_ligadas=True, hoje=HOJE)


def test_termos_e_paises_so_das_buscas_ativas(con: sqlite3.Connection) -> None:
    _busca(con, cargos=("Python ", "backend"), cidades=(Local(cidade="Lisboa", pais="pt"),))
    _busca(con, cargos=("PYTHON", "Dados", " "), cidades=(Local(cidade="Recife", pais="BR"),))
    _busca(con, cargos=("Cobol",), cidades=(Local(pais="US"),), ativa=False)
    _busca(con, cargos=("Java",))  # sem cidade: o país é o Brasil (11.1)
    assert termos_das_buscas(con) == ("Python", "backend", "Dados", "Java")
    assert paises_das_buscas(con) == ("BR", "PT")


def test_sem_busca_ativa_termos_e_paises_vazios(con: sqlite3.Connection) -> None:
    assert termos_das_buscas(con) == ()
    assert paises_das_buscas(con) == ()


# --- mínimo da busca em reais ---


def test_minimo_da_busca_vira_reais(con: sqlite3.Connection) -> None:
    brl = Busca(nome="a", salario_min_centavos=500000, salario_moeda="BRL")
    assert minimo_busca_brl(con, brl, hoje=HOJE) == 5000
    usd = Busca(nome="b", salario_min_centavos=100000, salario_moeda="USD")
    assert minimo_busca_brl(con, usd, hoje=HOJE) is None  # sem cotação
    _cotar(con, "USD", "5.65")
    assert minimo_busca_brl(con, usd, hoje=HOJE) == 5650
    assert minimo_busca_brl(con, Busca(nome="c"), hoje=HOJE) is None  # sem salário mínimo


def test_minimo_da_busca_sem_moeda_conta_como_real_e_arredonda(con: sqlite3.Connection) -> None:
    assert minimo_busca_brl(con, Busca(nome="a", salario_min_centavos=500050), hoje=HOJE) == 5001
    assert minimo_busca_brl(con, Busca(nome="a", salario_min_centavos=500049), hoje=HOJE) == 5000


def test_cotacao_de_mais_de_7_dias_nao_vale_no_minimo(con: sqlite3.Connection) -> None:
    usd = Busca(nome="b", salario_min_centavos=100000, salario_moeda="USD")
    _cotar(con, "USD", "5.65", HOJE - timedelta(days=7))
    assert minimo_busca_brl(con, usd, hoje=HOJE) == 5650  # 7 dias ainda vale
    assert minimo_busca_brl(con, usd, hoje=HOJE + timedelta(days=1)) is None  # 8 dias, não


# --- encaixe ---


def test_recalcular_grava_nota_nivel_motivos_e_motivo_de_ocultar(con: sqlite3.Connection) -> None:
    bom = inserir_vaga(con, titulo="Dev Python", nivel="junior", modalidade="remoto")
    oculta = inserir_vaga(con, titulo="Dev Java", nivel="senior", modalidade="presencial")
    bid = _busca(
        con,
        cargos=("python",),
        modalidades=(Modalidade.REMOTO,),
        niveis=(Nivel.JUNIOR,),
    )
    _limpar_encaixe(con)
    assert recalcular_encaixe(con, None, True, hoje=HOJE) == 2
    nota, nivel, motivos, motivo = _encaixe(con, bid, bom) or (None,) * 4
    assert (nota, nivel, motivo) == (100, "bom", None)
    assert _chaves(str(motivos)) == [
        "encaixe.cargo_titulo",
        "encaixe.local_remoto",
        "encaixe.nivel_ok",
    ]
    nota, nivel, motivos, motivo = _encaixe(con, bid, oculta) or (None,) * 4
    assert (nota, nivel, motivo) == (0, "fraco", "modalidade")  # a primeira regra que bate
    assert "encaixe.cargo_ausente" in _chaves(str(motivos))
    assert not con.in_transaction


def test_regras_desligadas_nao_ocultam(con: sqlite3.Connection) -> None:
    vaga = inserir_vaga(con, modalidade="presencial")
    bid = _busca(con, modalidades=(Modalidade.REMOTO,))
    _limpar_encaixe(con)
    recalcular_encaixe(con, None, True, hoje=HOJE)
    assert (_encaixe(con, bid, vaga) or (0,) * 4)[3] == "modalidade"  # controle positivo
    recalcular_encaixe(con, None, False, hoje=HOJE)
    assert (_encaixe(con, bid, vaga) or (0,) * 4)[3] is None


def test_busca_sem_criterio_grava_nota_vazia(con: sqlite3.Connection) -> None:
    vaga = inserir_vaga(con)
    bid = _busca(con)
    assert _encaixe(con, bid, vaga) == (None, None, "[]", None)


def test_local_usa_as_cidades_da_vaga(con: sqlite3.Connection) -> None:
    na_cidade = inserir_vaga(con, modalidade="presencial")
    no_estado = inserir_vaga(con, modalidade="presencial")
    fora = inserir_vaga(con, modalidade="presencial", uf="RJ")
    con.execute(
        "INSERT INTO local_vaga (vaga_id, cidade, uf, pais) VALUES (?, 'Recife', 'PE', 'BR')",
        (na_cidade,),
    )
    con.execute("INSERT INTO local_vaga (vaga_id, uf, pais) VALUES (?, 'PE', 'BR')", (no_estado,))
    con.commit()
    bid = _busca(con, cidades=(Local(cidade="Recife", uf="PE", pais="BR"),))
    assert _motivos_de(con, bid, na_cidade) == ["encaixe.local_cidade"]
    assert _motivos_de(con, bid, no_estado) == ["encaixe.local_uf"]
    assert _motivos_de(con, bid, fora) == ["encaixe.local_fora"]


def test_recalcular_so_das_buscas_ativas_quando_none(con: sqlite3.Connection) -> None:
    vaga = inserir_vaga(con, titulo="Dev Python")
    ativa = _busca(con, cargos=("python",))
    parada = _busca(con, cargos=("python",), ativa=False)
    _limpar_encaixe(con)
    assert recalcular_encaixe(con, None, True, hoje=HOJE) == 1
    assert _encaixe(con, ativa, vaga) is not None
    assert _encaixe(con, parada, vaga) is None
    assert recalcular_encaixe(con, [parada], True, hoje=HOJE) == 1  # pedida pelo id, calcula
    assert _encaixe(con, parada, vaga) is not None


def test_editar_busca_recalcula_so_a_dela(con: sqlite3.Connection) -> None:
    vaga = inserir_vaga(con, titulo="Dev Python", nivel="junior")
    a = _busca(con, cargos=("python",))
    b = _busca(con, cargos=("python",))
    antes_b = _encaixe(con, b, vaga)
    # mudo o encaixe de b à mão: se editar a recalculasse b, o valor voltaria
    con.execute("UPDATE encaixe SET nota = 1 WHERE busca_id = ?", (b,))
    con.commit()
    editar_busca(
        con, Busca(nome="Outro nome", id=a, cargos=("java",)), regras_ligadas=True, hoje=HOJE
    )
    (nota_a, _, motivos_a, _) = _encaixe(con, a, vaga) or (None,) * 4
    assert nota_a == 0 and "encaixe.cargo_ausente" in _chaves(str(motivos_a))
    assert (_encaixe(con, b, vaga) or (None,))[0] == 1 and antes_b is not None
    assert [x.nome for x in buscas(con)] == ["Outro nome", "Minha busca"]
    assert buscas(con)[0].criada_em == AGORA  # editar não mexe na criação


def test_filtro_de_salario_usa_valor_em_brl(con: sqlite3.Connection) -> None:
    """Mínimo da busca 5.000 reais. A comparação é em reais, nunca em centavos nem na moeda."""
    _cotar(con, "USD", "5.65")
    dolar = inserir_vaga(
        con, sal_moeda="USD", sal_mensal_min=500000, sal_mensal_min_brl=28250, sal_plausivel=1
    )
    baixa = inserir_vaga(
        con, sal_moeda="BRL", sal_mensal_min=300000, sal_mensal_min_brl=3000, sal_plausivel=1
    )
    alta = inserir_vaga(
        con, sal_moeda="BRL", sal_mensal_min=800000, sal_mensal_min_brl=8000, sal_plausivel=1
    )
    implausivel = inserir_vaga(
        con, sal_moeda="BRL", sal_mensal_min=100, sal_mensal_min_brl=1, sal_plausivel=0
    )
    sem_cotacao = inserir_vaga(
        con, sal_moeda="BRL", sal_mensal_min=100, sal_mensal_min_brl=None, sal_plausivel=1
    )
    sem_salario = inserir_vaga(con)
    bid = _busca(con, salario_min_centavos=500000, salario_moeda="BRL")
    vagas = {
        "dolar": dolar,
        "baixa": baixa,
        "alta": alta,
        "implausivel": implausivel,
        "sem_cotacao": sem_cotacao,
        "sem_salario": sem_salario,
    }
    ocultas = {}
    for nome, v in vagas.items():
        linha = _encaixe(con, bid, v)
        ocultas[nome] = "sem encaixe" if linha is None else linha[3]
    assert ocultas == {
        "dolar": None,
        "baixa": "salario",
        "alta": None,
        "implausivel": None,
        "sem_cotacao": None,
        "sem_salario": None,
    }
    assert _motivos_de(con, bid, dolar) == ["encaixe.salario_ok"]
    assert _motivos_de(con, bid, baixa) == ["encaixe.salario_abaixo"]
    for v in (implausivel, sem_cotacao, sem_salario):
        assert _motivos_de(con, bid, v) == ["encaixe.salario_nao_informado"]


def test_minimo_em_dolar_converte_antes_de_comparar(con: sqlite3.Connection) -> None:
    _cotar(con, "USD", "5.65")
    vaga = inserir_vaga(con, sal_moeda="BRL", sal_mensal_min_brl=5000, sal_plausivel=1)
    bid = _busca(con, salario_min_centavos=100000, salario_moeda="USD")  # 5.650 reais
    assert (_encaixe(con, bid, vaga) or (0,) * 4)[3] == "salario"
    _limpar_encaixe(con)
    recalcular_encaixe(con, None, True, hoje=HOJE + timedelta(days=8))  # cotação vencida
    assert (_encaixe(con, bid, vaga) or (0,) * 4)[3] is None  # sem cotação, a regra não vale


def test_oculta_manual_menos_um_vence_a_regra(con: sqlite3.Connection) -> None:
    mostrada = inserir_vaga(con, modalidade="presencial", oculta_manual=-1)
    controle = inserir_vaga(con, modalidade="presencial")
    bid = _busca(con, modalidades=(Modalidade.REMOTO,))
    _limpar_encaixe(con)
    recalcular_encaixe(con, None, True, hoje=HOJE)
    assert con.execute("SELECT oculta_manual FROM vaga WHERE id=?", (mostrada,)).fetchone() == (-1,)
    na_lista = {i.id for i in listar(con, Filtros(busca_id=bid), AGORA).itens}
    nas_ocultas = {i.id for i in listar(con, Filtros(aba="ocultas", busca_id=bid), AGORA).itens}
    assert na_lista == {mostrada}  # o -1 continua valendo depois do recálculo
    assert nas_ocultas == {controle}  # controle: a mesma regra oculta quando oculta_manual é 0


def test_recalcular_encaixe_so_da_vaga(con: sqlite3.Connection) -> None:
    alvo = inserir_vaga(con, titulo="Dev Python")
    outra = inserir_vaga(con, titulo="Dev Python")
    a = _busca(con, cargos=("python",))
    b = _busca(con, cargos=("java",), ativa=False)
    con.execute("UPDATE encaixe SET nota = 1, nivel = 'fraco'")
    con.commit()
    assert recalcular_encaixe(con, None, True, hoje=HOJE, vaga_id=alvo) == 1  # só a ativa
    assert _encaixe(con, a, alvo) is not None and (_encaixe(con, a, alvo) or (0,))[0] == 100
    assert (_encaixe(con, a, outra) or (0,))[0] == 1  # a outra vaga fica como estava
    assert (_encaixe(con, b, alvo) or (0,))[0] == 1  # busca parada também
    assert recalcular_encaixe(con, [a, b], True, hoje=HOJE, vaga_id=alvo) == 2
    assert (_encaixe(con, b, alvo) or (1,))[0] == 0
    assert (_encaixe(con, a, outra) or (0,))[0] == 1
    assert recalcular_encaixe(con, None, True, hoje=HOJE, vaga_id=9999) == 0  # vaga inexistente


def test_correcao_vale_depois_do_reprocesso(con: sqlite3.Connection) -> None:
    """D11: a coluna da vaga já está corrigida e há linha em `correcao`; o recálculo usa o
    valor corrigido e não o desfaz. Quem aplica a correção na vaga é o reprocessamento (T19)."""
    vaga = inserir_vaga(con, titulo="Dev Python", nivel="senior", modalidade="remoto")
    con.execute(
        "INSERT INTO correcao (vaga_id, campo, valor_antigo, valor_novo, criada_em)"
        " VALUES (?, 'nivel', 'pleno', 'senior', ?)",
        (vaga, AGORA.isoformat()),
    )
    con.commit()
    bid = _busca(con, niveis=(Nivel.SENIOR,))
    _limpar_encaixe(con)
    recalcular_encaixe(con, None, True, hoje=HOJE)
    nota, nivel, motivos, motivo = _encaixe(con, bid, vaga) or (None,) * 4
    assert (nota, nivel, motivo) == (100, "bom", None)
    assert _chaves(str(motivos)) == ["encaixe.nivel_ok"]
    assert con.execute("SELECT nivel FROM vaga WHERE id=?", (vaga,)).fetchone() == ("senior",)
    assert con.execute("SELECT valor_novo FROM correcao").fetchall() == [("senior",)]


def test_apagar_busca_apaga_o_encaixe_dela(con: sqlite3.Connection) -> None:
    vaga = inserir_vaga(con, titulo="Dev Python")
    a = _busca(con, cargos=("python",))
    b = _busca(con, cargos=("python",))
    assert con.execute("SELECT COUNT(*) FROM encaixe").fetchone() == (2,)
    apagar_busca(con, a)
    assert [x.id for x in buscas(con)] == [b]
    assert con.execute("SELECT busca_id FROM encaixe").fetchall() == [(b,)]
    assert con.execute("SELECT COUNT(*) FROM vaga WHERE id=?", (vaga,)).fetchone() == (1,)
    assert not con.in_transaction


def test_recalcular_nao_toca_vaga_nem_correcao_e_nunca_apaga(con: sqlite3.Connection) -> None:
    vaga = inserir_vaga(con, titulo="Dev Python", oculta_manual=1, status="salva")
    _busca(con, cargos=("python",))
    antes = con.execute("SELECT * FROM vaga WHERE id=?", (vaga,)).fetchone()
    recalcular_encaixe(con, None, True, hoje=HOJE)
    recalcular_encaixe(con, None, True, hoje=HOJE)
    assert con.execute("SELECT * FROM vaga WHERE id=?", (vaga,)).fetchone() == antes
    assert con.execute("SELECT COUNT(*) FROM encaixe").fetchone() == (1,)


def test_recalcular_encaixe_trava_antes_de_ler(con: sqlite3.Connection) -> None:
    """A leitura das vagas vem de dentro da trava da escrita (`BEGIN IMMEDIATE`)."""
    vaga = inserir_vaga(con, titulo="Dev Python")
    bid = _busca(con, cargos=("python",))
    _limpar_encaixe(con)
    caminho = Path(con.execute("PRAGMA database_list").fetchone()[2])
    leu, gravou = threading.Event(), threading.Event()
    erros: list[BaseException] = []

    def outra_conexao() -> None:
        assert leu.wait(timeout=10)
        c = abrir(caminho)
        c.execute("PRAGMA busy_timeout=0")  # travada, recusa na hora em vez de esperar
        try:
            c.execute("UPDATE vaga SET titulo = 'Dev Java' WHERE id = ?", (vaga,))
            c.commit()
        except sqlite3.OperationalError as erro:
            erros.append(erro)
        finally:
            c.close()
            gravou.set()

    def espia(sql: str) -> None:
        # já leu as vagas e vai gravar o encaixe: sem a trava, a outra conexão muda a vaga aqui
        # no meio e o encaixe gravado fica com o título que foi lido antes
        if sql.lstrip().startswith("INSERT INTO encaixe") and not leu.is_set():
            leu.set()
            gravou.wait(timeout=10)

    fio = threading.Thread(target=outra_conexao)
    fio.start()
    con.set_trace_callback(espia)
    try:
        recalcular_encaixe(con, None, True, hoje=HOJE)
    finally:
        con.set_trace_callback(None)
        fio.join(timeout=10)

    gravado = _encaixe(con, bid, vaga)
    recalcular_encaixe(con, None, True, hoje=HOJE)
    assert gravado == _encaixe(con, bid, vaga)  # o encaixe gravado bate com a vaga do banco
    assert len(erros) == 1 and "locked" in str(erros[0])  # a escrita estava travada


def test_recalcular_confirma_a_transacao_aberta_do_chamador(con: sqlite3.Connection) -> None:
    inserir_vaga(con)
    _busca(con, cargos=("python",))
    con.execute("UPDATE busca SET nome = 'x'")  # abre transação implícita do chamador
    recalcular_encaixe(con, None, True, hoje=HOJE)
    assert not con.in_transaction  # a função confirma o que fez, como as outras da camada


def test_criada_em_converte_para_utc(con: sqlite3.Connection) -> None:
    nove_em_brasilia = datetime(2026, 11, 13, 9, 0, tzinfo=timezone(timedelta(hours=-3)))
    bid = criar_busca(con, Busca(nome="x"), nove_em_brasilia, regras_ligadas=True, hoje=HOJE)
    linha = con.execute("SELECT criada_em FROM busca WHERE id=?", (bid,)).fetchone()
    assert linha == ("2026-11-13T12:00:00+00:00",)


def test_agora_sem_fuso_levanta_value_error_sem_gravar(con: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        criar_busca(
            con, Busca(nome="x"), datetime(2026, 11, 13, 9, 0), regras_ligadas=True, hoje=HOJE
        )
    assert con.execute("SELECT count(*) FROM busca").fetchone() == (0,)
