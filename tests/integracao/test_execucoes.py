"""Execuções, batimento, saúde e `HistoricoDoBanco` (plano T22; desenho 7.3, 8.3 e 12.3)."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from apoio.relogio import RelogioFalso
from apoio.semear import inserir_vaga
from jobot.banco.conexao import abrir
from jobot.banco.execucoes import (
    EstadoSaude,
    HistoricoDoBanco,
    LinhaSaude,
    Tipo,
    abrir_execucao,
    bater,
    comecar_fonte,
    execucao_atual,
    fechar_execucao,
    gravar_saude,
    inicio_da_ultima_completa,
    interromper_execucao,
    marcar_interrompidas,
    saude_recente,
    terminar_fonte,
    ultimas_que_rodaram,
)
from jobot.banco.migrar import migrar
from jobot.nucleo.coletores.executor import Historico
from jobot.nucleo.relogio import Relogio
from jobot.nucleo.url import canonica, hash_url

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
relogio: Relogio = RelogioFalso(AGORA)


@pytest.fixture
def caminho(tmp_path: Path) -> Path:
    return tmp_path / "jobot.db"


@pytest.fixture
def con(caminho: Path) -> Iterator[sqlite3.Connection]:
    c = abrir(caminho)
    migrar(c, caminho)
    c.executemany(
        "INSERT INTO fonte (chave, leva) VALUES (?, 'A')", [("remotive",), ("gupy",), ("lever",)]
    )
    c.commit()
    yield c
    c.close()


def _historico(con: sqlite3.Connection, agora: datetime = AGORA) -> HistoricoDoBanco:
    return HistoricoDoBanco(con, RelogioFalso(agora))


def _rodada(
    con: sqlite3.Connection,
    inicio: datetime,
    saudes: list[tuple[str, str, EstadoSaude, int, int]],
    tipo: Tipo = "busca",
) -> int:
    """Uma execução concluída, com linhas (fonte, escopo, estado, vagas, pedidos) de saúde."""
    id_ = abrir_execucao(con, tipo, "agenda", inicio)
    assert id_ is not None
    for fonte, escopo, estado, vagas, pedidos in saudes:
        gravar_saude(con, id_, fonte, escopo, estado, vagas=vagas, pedidos=pedidos)
    fechar_execucao(con, id_, inicio + timedelta(minutes=1))
    return id_


def _estado(con: sqlite3.Connection, id_: int) -> tuple[str, str | None]:
    linha = con.execute("SELECT estado, terminada_em FROM execucao WHERE id=?", (id_,)).fetchone()
    return (linha[0], linha[1])


# --- execuções ---


def test_segunda_busca_recusada(con: sqlite3.Connection, caminho: Path) -> None:
    primeira = abrir_execucao(con, "busca", "agenda", AGORA)
    assert primeira is not None
    assert abrir_execucao(con, "busca", "agora", AGORA) is None
    outra = abrir(caminho)  # outra conexão: a garantia é do banco, não da memória
    try:
        assert abrir_execucao(outra, "busca", "agora", AGORA) is None
        assert not outra.in_transaction
    finally:
        outra.close()
    assert con.execute("SELECT count(*) FROM execucao").fetchone()[0] == 1
    fechar_execucao(con, primeira, AGORA)
    assert abrir_execucao(con, "busca", "agora", AGORA + timedelta(minutes=1)) is not None


def test_descoberta_rodando_nao_impede_busca(con: sqlite3.Connection) -> None:
    descoberta = abrir_execucao(con, "descoberta", "agenda", AGORA)
    busca = abrir_execucao(con, "busca", "agora", AGORA)
    assert descoberta is not None
    assert busca is not None
    assert busca != descoberta
    assert abrir_execucao(con, "descoberta", "agora", AGORA) is None
    assert abrir_execucao(con, "paginas", "agenda", AGORA) is not None


def test_batimento_velho_vira_interrompida(con: sqlite3.Connection) -> None:
    id_ = abrir_execucao(con, "busca", "agenda", AGORA)
    assert id_ is not None
    # exatamente 5 min não é "mais de 5 min"
    assert marcar_interrompidas(con, AGORA + timedelta(minutes=5)) == 0
    assert _estado(con, id_)[0] == "rodando"
    bater(con, id_, AGORA + timedelta(minutes=4))
    assert marcar_interrompidas(con, AGORA + timedelta(minutes=9)) == 0  # conta do batimento
    assert marcar_interrompidas(con, AGORA + timedelta(minutes=9, seconds=1)) == 1
    estado, terminada = _estado(con, id_)
    assert estado == "interrompida"
    assert terminada == (AGORA + timedelta(minutes=4)).isoformat()
    # a trava do tipo foi liberada e a execução interrompida não volta a rodar
    assert marcar_interrompidas(con, AGORA + timedelta(hours=1)) == 0
    assert abrir_execucao(con, "busca", "recuperacao", AGORA + timedelta(hours=1)) is not None


def test_batimento_no_futuro_nao_vira_interrompida(con: sqlite3.Connection) -> None:
    id_ = abrir_execucao(con, "busca", "agenda", AGORA + timedelta(hours=2))  # relógio voltou
    assert id_ is not None
    assert marcar_interrompidas(con, AGORA) == 0
    assert _estado(con, id_)[0] == "rodando"


def test_interrompida_nao_conta_como_completa(con: sqlite3.Connection) -> None:
    assert inicio_da_ultima_completa(con, "busca") is None
    velha = abrir_execucao(con, "busca", "agenda", AGORA)
    assert velha is not None
    marcar_interrompidas(con, AGORA + timedelta(hours=1))
    assert inicio_da_ultima_completa(con, "busca") is None
    completa = AGORA + timedelta(hours=2)
    _rodada(con, completa, [])
    _rodada(con, completa + timedelta(hours=3), [], tipo="descoberta")  # outro tipo não vale
    interrompida = abrir_execucao(con, "busca", "agenda", completa + timedelta(hours=4))
    assert interrompida is not None
    marcar_interrompidas(con, completa + timedelta(hours=9))
    assert inicio_da_ultima_completa(con, "busca") == completa
    assert inicio_da_ultima_completa(con, "descoberta") == completa + timedelta(hours=3)
    assert inicio_da_ultima_completa(con, "paginas") is None


def test_execucao_rodando_nao_conta_como_completa(con: sqlite3.Connection) -> None:
    abrir_execucao(con, "busca", "agenda", AGORA)
    assert inicio_da_ultima_completa(con, "busca") is None


def test_execucao_atual_traz_a_que_roda(con: sqlite3.Connection) -> None:
    assert execucao_atual(con) is None
    _rodada(con, AGORA - timedelta(hours=3), [])
    assert execucao_atual(con) is None
    descoberta = abrir_execucao(con, "descoberta", "agenda", AGORA)
    atual = execucao_atual(con)
    assert atual is not None
    assert (atual.id, atual.tipo, atual.motivo) == (descoberta, "descoberta", "agenda")
    assert atual.iniciada_em == AGORA
    assert atual.escopos_prontos == 0
    busca = abrir_execucao(con, "busca", "agora", AGORA + timedelta(minutes=1))
    assert busca is not None
    gravar_saude(con, busca, "remotive", "", "ok", vagas=2, pedidos=1)
    gravar_saude(con, busca, "gupy", "agriness", "falhou", pedidos=1)
    atual = execucao_atual(con)  # a busca vem antes da descoberta
    assert atual is not None
    assert (atual.id, atual.escopos_prontos) == (busca, 2)
    assert atual.batimento_em == AGORA + timedelta(minutes=1)


def test_execucao_atual_traz_as_fontes_que_comecaram_e_nao_terminaram(
    con: sqlite3.Connection,
) -> None:
    velha = abrir_execucao(con, "busca", "agenda", AGORA - timedelta(hours=3))
    assert velha is not None
    comecar_fonte(con, velha, "lever", AGORA - timedelta(hours=3))
    interromper_execucao(con, velha, AGORA - timedelta(hours=2))  # a pendência dela não conta
    busca = abrir_execucao(con, "busca", "agora", AGORA)
    assert busca is not None
    atual = execucao_atual(con)
    assert atual is not None
    assert atual.fontes_rodando == ()
    comecar_fonte(con, busca, "remotive", AGORA)
    comecar_fonte(con, busca, "gupy", AGORA + timedelta(seconds=1))
    comecar_fonte(con, busca, "gupy", AGORA + timedelta(seconds=1))  # de novo: a mesma linha
    atual = execucao_atual(con)
    assert atual is not None
    assert atual.fontes_rodando == ("remotive", "gupy")
    terminar_fonte(con, busca, "remotive", AGORA + timedelta(seconds=2))
    atual = execucao_atual(con)
    assert atual is not None
    assert atual.fontes_rodando == ("gupy",)
    terminar_fonte(con, busca, "gupy", AGORA + timedelta(seconds=3))
    atual = execucao_atual(con)
    assert atual is not None
    assert atual.fontes_rodando == ()
    linhas = con.execute(
        "SELECT fonte, comecou_em, terminou_em FROM execucao_fonte WHERE execucao_id = ?"
        " ORDER BY fonte",
        (busca,),
    ).fetchall()
    assert [(f, c < t) for f, c, t in linhas] == [("gupy", True), ("remotive", True)]


def test_agora_sem_fuso_recusado(con: sqlite3.Connection) -> None:
    sem_fuso = datetime(2026, 11, 13, 12, 0)
    with pytest.raises(ValueError, match="fuso"):
        abrir_execucao(con, "busca", "agenda", sem_fuso)
    assert con.execute("SELECT count(*) FROM execucao").fetchone()[0] == 0


def test_agora_com_fuso_vira_utc(con: sqlite3.Connection) -> None:
    brasilia = datetime(2026, 11, 13, 9, 0, tzinfo=timezone(timedelta(hours=-3)))
    id_ = abrir_execucao(con, "busca", "agenda", brasilia)
    assert id_ is not None
    linha = con.execute("SELECT iniciada_em FROM execucao WHERE id=?", (id_,)).fetchone()
    assert linha[0] == "2026-11-13T12:00:00+00:00"


def test_transacao_aberta_do_chamador_recusada(con: sqlite3.Connection) -> None:
    con.execute("UPDATE fonte SET leva='B' WHERE chave='lever'")
    with pytest.raises(RuntimeError, match="transação"):
        abrir_execucao(con, "busca", "agenda", AGORA)
    assert con.in_transaction  # a do chamador segue intacta
    con.rollback()


def test_fechar_execucao_inexistente_levanta(con: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        fechar_execucao(con, 999, AGORA)


def test_fechar_nao_ressuscita_interrompida(con: sqlite3.Connection) -> None:
    id_ = abrir_execucao(con, "busca", "agenda", AGORA)
    assert id_ is not None
    marcar_interrompidas(con, AGORA + timedelta(hours=1))
    fechar_execucao(con, id_, AGORA + timedelta(hours=2))
    assert _estado(con, id_)[0] == "interrompida"


def test_interromper_execucao_inexistente_levanta_lookuperror(con: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        interromper_execucao(con, 999, AGORA)
    assert not con.in_transaction


def test_interromper_marca_na_hora_e_nao_mexe_na_concluida(con: sqlite3.Connection) -> None:
    rodando = abrir_execucao(con, "busca", "agenda", AGORA)
    assert rodando is not None
    interromper_execucao(con, rodando, AGORA + timedelta(seconds=10))
    assert _estado(con, rodando) == ("interrompida", (AGORA + timedelta(seconds=10)).isoformat())

    concluida = abrir_execucao(con, "busca", "agenda", AGORA + timedelta(minutes=1))
    assert concluida is not None
    fechar_execucao(con, concluida, AGORA + timedelta(minutes=2))
    interromper_execucao(con, concluida, AGORA + timedelta(minutes=3))
    assert _estado(con, concluida) == ("concluida", (AGORA + timedelta(minutes=2)).isoformat())


# --- saúde ---


def test_gravar_saude_atualiza_a_mesma_chave(con: sqlite3.Connection) -> None:
    id_ = abrir_execucao(con, "busca", "agenda", AGORA)
    assert id_ is not None
    gravar_saude(con, id_, "remotive", "", "falhou", pedidos=1, motivo="saude.bloqueio")
    gravar_saude(con, id_, "remotive", "", "ok", vagas=4, pedidos=2, duracao_ms=900)
    linhas = con.execute(
        "SELECT estado, vagas, pedidos, duracao_ms, motivo FROM saude WHERE execucao_id=?", (id_,)
    ).fetchall()
    assert linhas == [("ok", 4, 2, 900, None)]


def test_gravar_saude_respeita_a_transacao_do_chamador(con: sqlite3.Connection) -> None:
    id_ = abrir_execucao(con, "busca", "agenda", AGORA)
    assert id_ is not None
    con.execute("BEGIN IMMEDIATE")
    gravar_saude(con, id_, "remotive", "", "ok", vagas=1)
    assert con.in_transaction  # quem abriu a transação é quem confirma
    con.rollback()
    assert con.execute("SELECT count(*) FROM saude").fetchone()[0] == 0
    gravar_saude(con, id_, "remotive", "", "ok", vagas=1)  # sem transação aberta: confirma
    assert not con.in_transaction
    assert con.execute("SELECT count(*) FROM saude").fetchone()[0] == 1


def test_gravar_saude_com_erro_nao_deixa_transacao_aberta(con: sqlite3.Connection) -> None:
    id_ = abrir_execucao(con, "busca", "agenda", AGORA)
    assert id_ is not None
    with pytest.raises(sqlite3.IntegrityError):
        gravar_saude(con, id_, "fonte_que_nao_existe", "", "ok")
    assert not con.in_transaction


def test_ultimo_inicio_com_pedido_ignora_pedidos_zero(con: sqlite3.Connection) -> None:
    h = _historico(con)
    assert h.ultimo_inicio_com_pedido("remotive", None) is None
    com_pedido = AGORA - timedelta(hours=6)
    _rodada(con, com_pedido, [("remotive", "", "ok", 3, 1), ("gupy", "agriness", "ok", 1, 2)])
    _rodada(con, AGORA - timedelta(hours=3), [("remotive", "", "no_limite", 0, 0)])
    _rodada(con, AGORA, [("remotive", "", "desligada", 0, 0), ("gupy", "weg", "ok", 1, 1)])
    assert h.ultimo_inicio_com_pedido("remotive", None) == com_pedido
    assert h.ultimo_inicio_com_pedido("remotive", "") == com_pedido
    assert h.ultimo_inicio_com_pedido("gupy", "agriness") == com_pedido
    assert h.ultimo_inicio_com_pedido("gupy", "weg") == AGORA
    assert h.ultimo_inicio_com_pedido("gupy", None) == AGORA  # qualquer escopo da fonte
    assert h.ultimo_inicio_com_pedido("gupy", "outro") is None
    assert h.ultimo_inicio_com_pedido("lever", None) is None


def test_tres_ultimas_ok(con: sqlite3.Connection) -> None:
    h = _historico(con)
    for dia in (4, 3):
        _rodada(con, AGORA - timedelta(days=dia), [("remotive", "", "ok", 5, 1)])
    assert not h.tres_ultimas_ok_trouxeram_vagas("remotive", "")  # só duas
    _rodada(con, AGORA - timedelta(days=2), [("remotive", "", "ok", 5, 1)])
    assert h.tres_ultimas_ok_trouxeram_vagas("remotive", "")
    # sem_mudanca, falhou e parcial no meio não contam como "ok" nem quebram a sequência
    _rodada(con, AGORA - timedelta(days=1), [("remotive", "", "falhou", 0, 1)])
    _rodada(con, AGORA - timedelta(hours=12), [("remotive", "", "sem_mudanca", 0, 1)])
    assert h.tres_ultimas_ok_trouxeram_vagas("remotive", "")
    # um "ok" com zero vagas entre as três últimas desfaz
    _rodada(con, AGORA - timedelta(hours=6), [("remotive", "", "ok", 0, 1)])
    assert not h.tres_ultimas_ok_trouxeram_vagas("remotive", "")
    # e as três mais antigas já não importam: com vagas de novo, só vale se as 3 últimas têm
    for hora in (5, 4):
        _rodada(con, AGORA - timedelta(hours=hora), [("remotive", "", "ok", 2, 1)])
    assert not h.tres_ultimas_ok_trouxeram_vagas("remotive", "")
    _rodada(con, AGORA - timedelta(hours=3), [("remotive", "", "ok", 2, 1)])
    assert h.tres_ultimas_ok_trouxeram_vagas("remotive", "")
    # outro escopo e outra fonte não se misturam
    assert not h.tres_ultimas_ok_trouxeram_vagas("remotive", "outro")
    assert not h.tres_ultimas_ok_trouxeram_vagas("gupy", "")


def test_tem_ocorrencia_aberta(con: sqlite3.Connection) -> None:
    h = _historico(con)
    assert not h.tem_ocorrencia_aberta("remotive", "")
    inserir_vaga(con, fonte="remotive")
    con.commit()
    assert h.tem_ocorrencia_aberta("remotive", "")
    assert not h.tem_ocorrencia_aberta("remotive", "outro")
    assert not h.tem_ocorrencia_aberta("gupy", "")
    con.execute("UPDATE ocorrencia SET sumiu_em = ?", (AGORA.isoformat(),))
    assert not h.tem_ocorrencia_aberta("remotive", "")  # só fechadas


def test_ultima_coleta_ignora_no_limite_e_desligada(con: sqlite3.Connection) -> None:
    h = _historico(con)
    assert h.ultima_coleta("gupy", "weg") is None
    coletada = AGORA - timedelta(hours=9)
    _rodada(con, coletada, [("gupy", "weg", "falhou", 0, 1)])
    _rodada(con, AGORA - timedelta(hours=6), [("gupy", "weg", "no_limite", 0, 0)])
    _rodada(con, AGORA - timedelta(hours=3), [("gupy", "weg", "desligada", 0, 0)])
    assert h.ultima_coleta("gupy", "weg") == coletada
    assert h.ultima_coleta("gupy", "outro") is None


def test_saude_recente_traz_8(con: sqlite3.Connection) -> None:
    assert saude_recente(con) == ()
    ids = [
        _rodada(
            con,
            AGORA - timedelta(hours=3 * (10 - i)),
            [("remotive", "", "ok", i, 1), ("gupy", "weg", "parcial", 0, 1)],
        )
        for i in range(10)
    ]
    _rodada(con, AGORA - timedelta(days=2), [("lever", "", "ok", 1, 1)], tipo="descoberta")
    linhas = saude_recente(con)
    assert all(isinstance(linha, LinhaSaude) for linha in linhas)
    # as 8 execuções mais recentes, da mais nova para a mais velha, 2 linhas cada
    assert [linha.execucao_id for linha in linhas] == [i for i in reversed(ids[2:]) for _ in (0, 1)]
    assert {linha.execucao_id for linha in linhas}.isdisjoint(ids[:2])
    primeira = linhas[0]
    assert (primeira.fonte, primeira.escopo, primeira.estado) == ("gupy", "weg", "parcial")
    assert primeira.iniciada_em == AGORA - timedelta(hours=3)
    assert (primeira.vagas, primeira.pedidos, primeira.duracao_ms, primeira.motivo) == (
        0,
        1,
        0,
        None,
    )
    assert len({linha.execucao_id for linha in saude_recente(con, 3)}) == 3


def test_ultimas_que_rodaram_traz_a_ultima_real_de_cada_fonte_e_escopo(
    con: sqlite3.Connection,
) -> None:
    assert ultimas_que_rodaram(con) == {}
    _rodada(
        con,
        AGORA - timedelta(hours=9),
        [
            ("remotive", "", "ok", 1, 1),
            ("gupy", "weg", "ok", 4, 1),
            ("gupy", "ambev", "parcial", 2, 1),
            ("lever", "", "falhou", 0, 1),
        ],
    )
    _rodada(
        con,
        AGORA - timedelta(hours=6),
        [
            ("remotive", "", "sem_mudanca", 7, 1),
            ("gupy", "weg", "no_limite", 0, 0),
            ("gupy", "ambev", "ok", 5, 1),
            ("lever", "", "desligada", 0, 0),
        ],
    )
    # mais nova que as outras, mas sem rodar: não conta
    _rodada(
        con,
        AGORA - timedelta(hours=1),
        [("remotive", "", "no_limite", 0, 0), ("gupy", "weg", "desligada", 0, 0)],
    )
    # execução de outro tipo não atrapalha: o que vale é a linha de saúde
    _rodada(con, AGORA - timedelta(hours=2), [("lever", "novo", "ok", 3, 1)], tipo="descoberta")
    por_fonte = ultimas_que_rodaram(con)
    assert set(por_fonte) == {"remotive", "gupy", "lever"}
    remotive = por_fonte["remotive"][""]
    assert (remotive.estado, remotive.vagas) == ("sem_mudanca", 7)
    assert remotive.iniciada_em == AGORA - timedelta(hours=6)
    assert {e: (ln.estado, ln.vagas) for e, ln in por_fonte["gupy"].items()} == {
        "weg": ("ok", 4),
        "ambev": ("ok", 5),
    }
    assert {e: (ln.estado, ln.vagas) for e, ln in por_fonte["lever"].items()} == {
        "": ("falhou", 0),
        "novo": ("ok", 3),
    }


def test_ultimas_que_rodaram_desempata_por_inicio_e_depois_por_id(con: sqlite3.Connection) -> None:
    mesma = AGORA - timedelta(hours=3)
    _rodada(con, mesma, [("remotive", "", "ok", 1, 1)])
    segunda = _rodada(con, mesma, [("remotive", "", "ok", 2, 1)])
    linha = ultimas_que_rodaram(con)["remotive"][""]
    assert (linha.execucao_id, linha.vagas) == (segunda, 2)
    # início mais novo vence, mesmo com id menor ficando para trás
    _rodada(con, AGORA - timedelta(hours=5), [("remotive", "", "ok", 9, 1)])
    assert ultimas_que_rodaram(con)["remotive"][""].vagas == 2


def test_ultimas_que_rodaram_com_fora_pula_os_estados_pedidos(con: sqlite3.Connection) -> None:
    _rodada(con, AGORA - timedelta(hours=9), [("gupy", "acme", "ok", 789, 1)])
    _rodada(con, AGORA - timedelta(hours=6), [("gupy", "acme", "falhou", 0, 1)])
    _rodada(con, AGORA - timedelta(hours=1), [("gupy", "acme", "sem_mudanca", 0, 1)])
    linha = ultimas_que_rodaram(con, ("no_limite", "desligada", "sem_mudanca", "falhou"))
    assert (linha["gupy"]["acme"].estado, linha["gupy"]["acme"].vagas) == ("ok", 789)
    assert ultimas_que_rodaram(con)["gupy"]["acme"].estado == "sem_mudanca"


# --- HistoricoDoBanco ---


def test_historico_do_banco_satisfaz_o_protocol(con: sqlite3.Connection) -> None:
    historico: Historico = HistoricoDoBanco(con, RelogioFalso(AGORA))
    assert historico.urls_conhecidas("remotive", []) == set()


def test_urls_conhecidas_compara_pela_canonica(con: sqlite3.Connection) -> None:
    url = "https://exemplo.test/vagas/python-dev"
    vaga = inserir_vaga(con, fonte="remotive", url=url)
    con.execute("UPDATE vaga SET url_hash=? WHERE id=?", (hash_url(canonica(url)), vaga))
    con.commit()
    h = _historico(con)
    variantes = [
        url,
        url + "/",
        url + "?utm_source=twitter&utm_medium=social",
        "HTTPS://Exemplo.test/vagas/python-dev#candidatar",
    ]
    nova = "https://exemplo.test/vagas/outra-vaga"
    assert h.urls_conhecidas("remotive", [*variantes, nova, "isto não é uma url"]) == set(variantes)
    # só tem ocorrência de outra fonte: não é conhecida
    assert h.urls_conhecidas("gupy", variantes) == set()
    assert h.urls_conhecidas("remotive", []) == set()
    # ocorrência já sumida continua conhecida (a URL segue no banco)
    con.execute("UPDATE ocorrencia SET sumiu_em = ?", (AGORA.isoformat(),))
    assert h.urls_conhecidas("remotive", [url]) == {url}


def test_urls_conhecidas_aceita_lista_grande(con: sqlite3.Connection) -> None:
    urls = [f"https://exemplo.test/vagas/{n}" for n in range(1500)]
    vaga = inserir_vaga(con, fonte="remotive", url=urls[1400])
    con.execute("UPDATE vaga SET url_hash=? WHERE id=?", (hash_url(canonica(urls[1400])), vaga))
    con.commit()
    assert _historico(con).urls_conhecidas("remotive", urls) == {urls[1400]}


def _tentativa(con: sqlite3.Connection, url: str, dias: float) -> None:
    con.execute(
        "INSERT INTO enriquecimento (url_hash, buscado_em, conteudo) VALUES (?, ?, '')",
        (hash_url(canonica(url)), (AGORA - timedelta(days=dias)).isoformat()),
    )
    con.commit()


def test_detalhe_recente_olha_30_dias(con: sqlite3.Connection) -> None:
    de_29 = "https://exemplo.test/vagas/29"
    de_31 = "https://exemplo.test/vagas/31"
    sem_tentativa = "https://exemplo.test/vagas/nunca"
    _tentativa(con, de_29, 29)
    _tentativa(con, de_31, 31)
    h = _historico(con)
    assert h.detalhe_recente("remotive", [de_29, de_31, sem_tentativa]) == {de_29}
    # pelo mesmo hash: a variante com rastreio e barra final também volta
    variante = de_29 + "/?utm_source=x"
    assert h.detalhe_recente("remotive", [variante, de_31]) == {variante}
    assert h.detalhe_recente("remotive", []) == set()
    # a janela anda com o relógio recebido, não com o do sistema
    assert _historico(con, AGORA + timedelta(days=2)).detalhe_recente("remotive", [de_29]) == set()
    assert _historico(con, AGORA - timedelta(days=10)).detalhe_recente("remotive", [de_31]) == {
        de_31
    }
