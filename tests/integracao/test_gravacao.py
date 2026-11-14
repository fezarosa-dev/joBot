"""Gravação do escopo, ciclo de vida no banco e reprocessamento (desenho 7.6, 10.2, 12.4; T19)."""

import json
import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from jobot.banco.acoes import corrigir
from jobot.banco.cadastros import gravar_config
from jobot.banco.conexao import abrir
from jobot.banco.cotacoes import aplicar_cotacoes, gravar_cotacao
from jobot.banco.gravacao import (
    ResumoEscopo,
    ValidadoresDoBanco,
    fechar_escopos_extintos,
    gravar_cache_detalhe,
    gravar_detalhe,
    gravar_escopo,
    reprocessar,
    reprocessar_vaga,
)
from jobot.banco.migrar import migrar
from jobot.nucleo.cambio import Cotacao
from jobot.nucleo.coletores.base import ResultadoEscopo
from jobot.nucleo.coletores.executor import SaidaEscopo
from jobot.nucleo.http import LeitorValidadores, Validadores
from jobot.nucleo.modelo import SalarioBruto, VagaColetada
from jobot.nucleo.texto import para_texto
from jobot.nucleo.tratamento.rotulos import VERSAO_REGRAS
from jobot.nucleo.tratamento.tratar import tratar
from jobot.nucleo.url import canonica, hash_url

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
HOJE = date(2026, 11, 13)
URL = "https://exemplo.test/vagas/1"
LISTA = "https://exemplo.test/api/vagas"
_MAX = 2**63 - 1


@pytest.fixture
def caminho(tmp_path: Path) -> Path:
    return tmp_path / "jobot.db"


@pytest.fixture
def con(caminho: Path) -> Iterator[sqlite3.Connection]:
    c = abrir(caminho)
    migrar(c, caminho)
    c.executemany(
        "INSERT INTO fonte (chave, leva) VALUES (?, 'A')", [("remotive",), ("himalayas",)]
    )
    c.commit()
    yield c
    c.close()


DESCRICAO_PT = (
    "Estamos contratando uma pessoa desenvolvedora Python para trabalhar remoto com a nossa"
    " equipe de produto, cuidando de serviços, testes automatizados e entregas semanais."
)


def _dias(n: float) -> datetime:
    return T0 + timedelta(days=n)


def _coletada(**campos: Any) -> VagaColetada:
    base: dict[str, Any] = {
        "fonte": "remotive",
        "escopo": "",
        "url": URL,
        "titulo": "Desenvolvedor Python",
        "empresa": "Acme",
        "descricao_formato": "texto",
        "descricao": "Vaga de desenvolvedor Python remoto.",
    }
    return VagaColetada(**(base | campos))


def _execucao(con: sqlite3.Connection, agora: datetime) -> int:
    cur = con.execute(
        "INSERT INTO execucao (tipo, motivo, iniciada_em, batimento_em, estado)"
        " VALUES ('busca', 'agenda', ?, ?, 'concluida')",
        (agora.isoformat(), agora.isoformat()),
    )
    con.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _gravar(
    con: sqlite3.Connection,
    vagas: Sequence[VagaColetada] = (),
    *,
    agora: datetime = T0,
    estado: str = "ok",
    escopo: str = "",
    fonte: str = "remotive",
    validadores: Mapping[str, Validadores] | None = None,
    urls_vistas: Sequence[str] = (),
    urls_sem_detalhe: Sequence[str] = (),
) -> ResumoEscopo:
    vagas = [replace(v, escopo=escopo, fonte=fonte) for v in vagas]
    resultado = ResultadoEscopo(tuple(vagas), estado, None, 1)  # type: ignore[arg-type]
    saida = SaidaEscopo(
        fonte,
        escopo,
        resultado,
        10,
        validadores or {},
        tuple(urls_vistas),
        tuple(urls_sem_detalhe),
    )
    return gravar_escopo(con, _execucao(con, agora), saida, [tratar(v) for v in vagas], agora)


def _um(con: sqlite3.Connection, sql: str, *params: object) -> Any:
    return con.execute(sql, params).fetchone()[0]


def _id(con: sqlite3.Connection, url: str = URL) -> int:
    return int(_um(con, "SELECT id FROM vaga WHERE url_hash = ?", hash_url(canonica(url))))


def _vaga(con: sqlite3.Connection, vaga_id: int) -> dict[str, Any]:
    con.row_factory = sqlite3.Row
    try:
        return dict(con.execute("SELECT * FROM vaga WHERE id = ?", (vaga_id,)).fetchone())
    finally:
        con.row_factory = None


def _ocorrencias(con: sqlite3.Connection, vaga_id: int) -> list[tuple[Any, ...]]:
    return con.execute(
        "SELECT id, escopo, ultima_vista_em, sumiu_em FROM ocorrencia WHERE vaga_id = ?"
        " ORDER BY escopo",
        (vaga_id,),
    ).fetchall()


def _coletada_gravada(con: sqlite3.Connection, vaga_id: int) -> VagaColetada:
    texto = _um(con, "SELECT coletada FROM ocorrencia WHERE vaga_id = ?", vaga_id)
    return VagaColetada.de_json(texto)


def _cotar(con: sqlite3.Connection, venda: str, dia: date = HOJE) -> None:
    gravar_cotacao(con, Cotacao(moeda="USD", data=dia, venda=Decimal(venda)), _dias(12))


def _brl(con: sqlite3.Connection, vaga_id: int) -> tuple[Any, ...]:
    return tuple(
        con.execute(
            "SELECT sal_mensal_min, sal_mensal_min_brl, sal_cotacao_data FROM vaga WHERE id = ?",
            (vaga_id,),
        ).fetchone()
    )


# ---------------------------------------------------------------- gravar_escopo


def test_mesma_url_de_dois_escopos_uma_vaga_duas_ocorrencias(con: sqlite3.Connection) -> None:
    primeiro = _gravar(con, [_coletada()], escopo="a")
    segundo = _gravar(con, [_coletada(url=URL + "/?utm_source=x")], escopo="b")

    assert primeiro == ResumoEscopo(novas=1, fechadas=0)
    assert segundo == ResumoEscopo(novas=0, fechadas=0)
    assert _um(con, "SELECT COUNT(*) FROM vaga") == 1
    assert [o[1] for o in _ocorrencias(con, _id(con))] == ["a", "b"]


def test_varias_cidades_uma_vaga_varios_locais(con: sqlite3.Connection) -> None:
    vaga = _coletada(locais=("São Paulo, SP", "Rio de Janeiro, RJ"))
    mesma_url_outra_cidade = _coletada(locais=("Curitiba, PR",))

    _gravar(con, [vaga, mesma_url_outra_cidade])

    assert _um(con, "SELECT COUNT(*) FROM vaga") == 1
    assert _um(con, "SELECT COUNT(*) FROM ocorrencia") == 1
    ufs = con.execute("SELECT uf FROM local_vaga WHERE vaga_id = ?", (_id(con),)).fetchall()
    assert sorted(u[0] for u in ufs) == ["PR", "RJ", "SP"]


def test_ciclo_de_vida_no_banco(con: sqlite3.Connection) -> None:
    url_b = "https://exemplo.test/vagas/2"
    _gravar(con, [_coletada(), _coletada(url=url_b)], agora=T0)
    a, b = _id(con), _id(con, url_b)

    # ok: B não veio, some e a vaga fecha
    assert _gravar(con, [_coletada()], agora=_dias(1)) == ResumoEscopo(novas=0, fechadas=1)
    assert _ocorrencias(con, b)[0][3] == _dias(1).isoformat()
    assert _vaga(con, b)["fechada_em"] == _dias(1).isoformat()

    # parcial: só o que tem mais de 30 dias some (par 30/31)
    assert _gravar(con, estado="parcial", agora=_dias(31)).fechadas == 0
    assert _ocorrencias(con, a)[0][3] is None
    # falhou: nada muda, nem com 31 dias
    assert _gravar(con, estado="falhou", agora=_dias(32)).fechadas == 0
    assert _ocorrencias(con, a)[0][3] is None
    assert _gravar(con, estado="parcial", agora=_dias(32)).fechadas == 1
    assert _ocorrencias(con, a)[0][3] == _dias(32).isoformat()
    assert _vaga(con, a)["fechada_em"] == _dias(32).isoformat()

    # reaparecer: a ocorrência volta e a vaga reabre
    _gravar(con, [_coletada(url=url_b)], agora=_dias(33))
    assert _ocorrencias(con, b)[0][2:] == (_dias(33).isoformat(), None)
    assert _vaga(con, b)["fechada_em"] is None


def test_304_toca_e_guarda_validadores(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()], agora=T0, validadores={LISTA: Validadores('"v1"', None)})
    vaga_id = _id(con)

    outra = "https://exemplo.test/api/vagas?pagina=2"
    _gravar(
        con,
        estado="sem_mudanca",
        agora=_dias(5),
        validadores={outra: Validadores(None, "Wed, 11 Nov 2026 10:00:00 GMT")},
    )

    assert _ocorrencias(con, vaga_id)[0][2:] == (_dias(5).isoformat(), None)
    assert _vaga(con, vaga_id)["fechada_em"] is None
    leitor: LeitorValidadores = ValidadoresDoBanco(con)
    assert leitor.ler(LISTA) == Validadores('"v1"', None)
    assert leitor.ler(outra) == Validadores(None, "Wed, 11 Nov 2026 10:00:00 GMT")
    assert leitor.ler("https://exemplo.test/nunca") is None


def test_erro_no_meio_desfaz_tudo_inclusive_validadores(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TRIGGER quebra BEFORE INSERT ON enriquecimento"
        " BEGIN SELECT RAISE(ABORT, 'quebrou'); END"
    )
    con.commit()

    with pytest.raises(sqlite3.DatabaseError, match="quebrou"):
        _gravar(
            con,
            [_coletada(locais=("São Paulo, SP",))],
            validadores={LISTA: Validadores('"v1"', None)},
            urls_sem_detalhe=["https://exemplo.test/vagas/9"],
        )

    assert not con.in_transaction
    for tabela in ("saude", "cache_http", "vaga", "ocorrencia", "local_vaga"):
        assert _um(con, f"SELECT COUNT(*) FROM {tabela}") == 0, tabela


def test_validadores_so_com_estado_ok(con: sqlite3.Connection) -> None:
    for estado in ("parcial", "falhou", "no_limite"):
        _gravar(con, estado=estado, validadores={LISTA: Validadores('"v1"', None)})
    assert _um(con, "SELECT COUNT(*) FROM cache_http") == 0

    _gravar(con, [_coletada()], validadores={LISTA: Validadores('"v2"', None)})
    assert con.execute("SELECT url, etag FROM cache_http").fetchall() == [(LISTA, '"v2"')]
    assert _um(con, "SELECT COUNT(*) FROM saude") == 4


def test_vaga_fechada_mantem_texto_e_descricao_bruta(con: sqlite3.Connection) -> None:
    html = "<p>Vaga de <b>desenvolvedor</b> Python.</p>" * 500
    _gravar(con, [_coletada(descricao=html, descricao_formato="html")], agora=T0)
    vaga_id = _id(con)

    _gravar(con, agora=_dias(1))  # estado ok sem a vaga: fecha

    assert _vaga(con, vaga_id)["fechada_em"] is not None
    assert _vaga(con, vaga_id)["descricao_texto"] == para_texto(html, "html")
    coletada = _coletada_gravada(con, vaga_id)
    assert (coletada.descricao, coletada.descricao_formato) == (html, "html")


def test_listagem_sem_descricao_nao_apaga_a_do_detalhar(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada(descricao="")], agora=T0)
    vaga_id = _id(con)
    ocorrencia_id = _ocorrencias(con, vaga_id)[0][0]
    detalhe = "<p>Descrição completa da página de detalhe.</p>"
    gravar_detalhe(con, ocorrencia_id, _coletada(descricao=detalhe, descricao_formato="html"))
    texto = _vaga(con, vaga_id)["descricao_texto"]
    assert texto == para_texto(detalhe, "html")

    _gravar(con, [_coletada(descricao="", titulo="Título novo")], agora=_dias(1))

    coletada = _coletada_gravada(con, vaga_id)
    assert (coletada.descricao, coletada.descricao_formato) == (detalhe, "html")
    assert coletada.titulo == "Título novo"
    assert _vaga(con, vaga_id)["descricao_texto"] == texto
    assert _vaga(con, vaga_id)["titulo"] == "Título novo"
    assert _ocorrencias(con, vaga_id)[0][2] == _dias(1).isoformat()
    with pytest.raises(LookupError):
        gravar_detalhe(con, 999, _coletada())


def _cache(con: sqlite3.Connection) -> tuple[Any, ...] | None:
    linha = con.execute(
        "SELECT buscado_em, conteudo FROM enriquecimento WHERE url_hash = ?",
        (hash_url(canonica(URL)),),
    ).fetchone()
    return None if linha is None else tuple(linha)


def test_cache_e_detalhe_na_mesma_transacao(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada(descricao="")], agora=T0)
    vaga_id = _id(con)
    ocorrencia_id = _ocorrencias(con, vaga_id)[0][0]
    detalhe = _coletada(descricao="Descrição completa da página de detalhe.")
    con.execute(
        "CREATE TRIGGER quebra BEFORE INSERT ON enriquecimento"
        " BEGIN SELECT RAISE(ABORT, 'cache quebrou'); END"
    )
    con.commit()

    with pytest.raises(sqlite3.IntegrityError, match="cache quebrou"):
        gravar_cache_detalhe(con, ocorrencia_id, URL, detalhe, _dias(1))

    assert _coletada_gravada(con, vaga_id).descricao == ""  # o detalhe saiu junto
    assert _vaga(con, vaga_id)["descricao_texto"] == ""
    assert _cache(con) is None
    assert not con.in_transaction

    # controle: sem o gatilho, os dois ficam
    con.execute("DROP TRIGGER quebra")
    con.commit()
    gravar_cache_detalhe(con, ocorrencia_id, URL, detalhe, _dias(1))
    assert _coletada_gravada(con, vaga_id).descricao == detalhe.descricao
    assert _cache(con) == (_dias(1).isoformat(), detalhe.para_json())


def test_detalhe_none_grava_so_o_cache(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada(descricao="")], agora=T0)
    vaga_id = _id(con)
    ocorrencia_id = _ocorrencias(con, vaga_id)[0][0]
    antes = _coletada_gravada(con, vaga_id)

    gravar_cache_detalhe(con, ocorrencia_id, URL, None, _dias(1))

    assert _cache(con) == (_dias(1).isoformat(), "")
    assert _coletada_gravada(con, vaga_id) == antes
    assert not con.in_transaction


def test_descricao_nova_nao_vazia_substitui_a_anterior(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada(descricao="Descrição antiga.")], agora=T0)
    _gravar(con, [_coletada(descricao="Descrição nova.")], agora=_dias(1))

    vaga_id = _id(con)
    assert _coletada_gravada(con, vaga_id).descricao == "Descrição nova."
    assert _vaga(con, vaga_id)["descricao_texto"] == "Descrição nova."


def test_regravar_vaga_mantem_id_e_ocorrencias(con: sqlite3.Connection) -> None:
    vaga = _coletada(locais=("São Paulo, SP", "Rio de Janeiro, RJ"))
    _gravar(con, [vaga], escopo="a", agora=T0)
    _gravar(con, [vaga], escopo="b", agora=T0)
    vaga_id = _id(con)
    ocorrencias = [o[0] for o in _ocorrencias(con, vaga_id)]
    corrigir(con, vaga_id, "outro", None, "comentário", T0)
    con.execute("INSERT INTO busca (nome, criada_em) VALUES ('b', ?)", (T0.isoformat(),))
    con.execute("INSERT INTO encaixe (busca_id, vaga_id, motivos) VALUES (1, ?, '[]')", (vaga_id,))
    con.commit()

    _gravar(con, [replace(vaga, titulo="Título novo")], escopo="a", agora=_dias(1))

    assert _id(con) == vaga_id
    assert _vaga(con, vaga_id)["titulo"] == "Título novo"
    assert [o[0] for o in _ocorrencias(con, vaga_id)] == ocorrencias
    assert _um(con, "SELECT COUNT(*) FROM local_vaga WHERE vaga_id = ?", vaga_id) == 2
    assert _um(con, "SELECT COUNT(*) FROM correcao") == 1
    assert _um(con, "SELECT COUNT(*) FROM encaixe") == 1


def test_url_vista_sem_vaga_toca_a_ocorrencia(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()], agora=T0)
    vaga_id = _id(con)

    resumo = _gravar(con, agora=_dias(3), urls_vistas=[URL + "?utm_source=sitemap"])

    assert resumo.fechadas == 0
    assert _ocorrencias(con, vaga_id)[0][2:] == (_dias(3).isoformat(), None)
    assert _vaga(con, vaga_id)["fechada_em"] is None


def test_url_sem_detalhe_entra_no_cache(con: sqlite3.Connection) -> None:
    nova = "https://exemplo.test/vagas/7?utm_source=x"
    _gravar(con, agora=T0, urls_sem_detalhe=[nova])
    _gravar(con, agora=_dias(1), urls_sem_detalhe=[nova])

    assert con.execute("SELECT url_hash, buscado_em, conteudo FROM enriquecimento").fetchall() == [
        (hash_url(canonica(nova)), _dias(1).isoformat(), "")
    ]
    assert _um(con, "SELECT COUNT(*) FROM vaga") == 0


def test_salario_gigante_nao_quebra_gravacao(con: sqlite3.Connection) -> None:
    gigante = "R$ 99999999999999999999999 por mês"
    por_hora = "R$ 90.000.000.000.000.000 por hora"  # sal_min cabe; o mensal (x 160) não
    url_hora = "https://exemplo.test/vagas/2"
    lido = tratar(_coletada(salario_texto=por_hora)).salario
    assert lido is not None and lido.minimo is not None and lido.minimo < _MAX
    assert lido.mensal_minimo is not None and lido.mensal_minimo > _MAX

    _gravar(
        con, [_coletada(salario_texto=gigante), _coletada(url=url_hora, salario_texto=por_hora)]
    )

    for url, texto in ((URL, gigante), (url_hora, por_hora)):
        vaga = _vaga(con, _id(con, url))
        nulos = ("sal_moeda", "sal_min", "sal_max", "sal_periodo", "sal_mensal_min")
        assert {c: vaga[c] for c in (*nulos, "sal_plausivel")} == dict.fromkeys(
            (*nulos, "sal_plausivel")
        )
        assert vaga["sal_texto"] == texto


def test_fechar_escopos_extintos(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()], escopo="a", agora=T0)
    _gravar(con, [_coletada()], escopo="b", agora=T0)
    _gravar(con, [_coletada(url="https://exemplo.test/h/1")], fonte="himalayas", escopo="x")
    vaga_id = _id(con)

    assert fechar_escopos_extintos(con, "remotive", {"a"}, _dias(1)) == 1
    assert [o[3] for o in _ocorrencias(con, vaga_id)] == [None, _dias(1).isoformat()]
    assert _vaga(con, vaga_id)["fechada_em"] is None

    assert fechar_escopos_extintos(con, "remotive", set(), _dias(2)) == 1
    assert _vaga(con, vaga_id)["fechada_em"] == _dias(2).isoformat()
    assert _vaga(con, _id(con, "https://exemplo.test/h/1"))["fechada_em"] is None
    with pytest.raises(ValueError, match="fuso"):
        fechar_escopos_extintos(con, "remotive", set(), datetime(2026, 11, 3))


# ---------------------------------------------------------------- reprocessar


def test_correcao_vence_regra_no_reprocesso(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()], agora=T0)
    vaga_id = _id(con)
    assert _vaga(con, vaga_id)["area"] != "juridico"
    corrigir(con, vaga_id, "area", "juridico", None, T0)
    con.execute("UPDATE vaga SET versao_regras = 'velha' WHERE id = ?", (vaga_id,))
    con.commit()

    assert reprocessar(con, VERSAO_REGRAS) == 1
    assert _vaga(con, vaga_id)["area"] == "juridico"
    assert _vaga(con, vaga_id)["versao_regras"] == VERSAO_REGRAS

    _gravar(con, [_coletada()], agora=_dias(1))  # outra busca não desfaz a correção
    assert _vaga(con, vaga_id)["area"] == "juridico"


def test_reprocessar_le_de_ocorrencia_coletada(con: sqlite3.Connection) -> None:
    url_fechada = "https://exemplo.test/vagas/2"
    _gravar(con, [_coletada(), _coletada(url=url_fechada)], agora=T0)
    _gravar(con, [_coletada()], agora=_dias(1))  # fecha a segunda
    aberta, fechada = _id(con), _id(con, url_fechada)
    con.execute(
        "UPDATE vaga SET titulo = 'estragado', descricao_texto = 'x', versao_regras = 'velha'"
    )
    con.commit()

    assert reprocessar(con, VERSAO_REGRAS) == 1

    assert _vaga(con, aberta)["titulo"] == "Desenvolvedor Python"
    assert _vaga(con, aberta)["descricao_texto"] == "Vaga de desenvolvedor Python remoto."
    assert _vaga(con, fechada)["titulo"] == "estragado"  # vaga fechada não se reprocessa
    assert reprocessar(con, VERSAO_REGRAS) == 0


def test_reprocessar_vaga_aplica_correcao(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada(), _coletada(url="https://exemplo.test/vagas/2")], agora=T0)
    vaga_id, outra = _id(con), _id(con, "https://exemplo.test/vagas/2")
    corrigir(con, vaga_id, "nivel", "especialista", None, T0)
    corrigir(con, vaga_id, "uf", "MG", None, T0)
    antes = _vaga(con, outra)

    reprocessar_vaga(con, vaga_id, hoje=HOJE)

    assert _vaga(con, vaga_id)["nivel"] == "especialista"
    locais = con.execute("SELECT uf, pais FROM local_vaga WHERE vaga_id = ?", (vaga_id,))
    assert locais.fetchall() == [("MG", "BR")]
    assert _vaga(con, outra) == antes
    with pytest.raises(LookupError):
        reprocessar_vaga(con, 999, hoje=HOJE)


def test_correcao_fechada_fecha_e_resiste_a_proxima_busca(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()], agora=T0)
    vaga_id = _id(con)
    corrigir(con, vaga_id, "fechada", "1", "a empresa já preencheu", _dias(1))

    reprocessar_vaga(con, vaga_id, hoje=HOJE)
    assert _vaga(con, vaga_id)["fechada_em"] == _dias(1).isoformat()

    _gravar(con, [_coletada()], agora=_dias(2))  # a fonte ainda mostra: continua fechada
    assert _vaga(con, vaga_id)["fechada_em"] == _dias(1).isoformat()

    corrigir(con, vaga_id, "fechada", "não", None, _dias(3))
    assert _gravar(con, [_coletada()], agora=_dias(4)).fechadas == 0
    assert _vaga(con, vaga_id)["fechada_em"] is None


def test_desfazer_correcao_fechada_reabre_no_reprocesso(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()], agora=T0)
    vaga_id = _id(con)
    corrigir(con, vaga_id, "fechada", "1", None, _dias(1))
    reprocessar_vaga(con, vaga_id, hoje=HOJE)
    assert _vaga(con, vaga_id)["fechada_em"] == _dias(1).isoformat()

    corrigir(con, vaga_id, "fechada", "não", None, _dias(2))
    reprocessar_vaga(con, vaga_id, hoje=HOJE)  # vale já, sem esperar a próxima busca
    assert _vaga(con, vaga_id)["fechada_em"] is None


def test_desfazer_correcao_fechada_sem_ocorrencia_aberta_continua_fechada(
    con: sqlite3.Connection,
) -> None:
    _gravar(con, [_coletada()], agora=T0)
    vaga_id = _id(con)
    corrigir(con, vaga_id, "fechada", "1", None, _dias(1))
    _gravar(con, agora=_dias(2))  # a fonte tirou a vaga
    corrigir(con, vaga_id, "fechada", "não", None, _dias(3))
    reprocessar_vaga(con, vaga_id, hoje=HOJE)
    assert _vaga(con, vaga_id)["fechada_em"] is not None


def test_correcao_de_salario_mantem_beneficios_das_regras(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada(salario_texto="R$ 5.000/mês + VR + VA", descricao=DESCRICAO_PT)])
    vaga_id = _id(con)
    beneficios = _vaga(con, vaga_id)["beneficios"]
    assert beneficios != "[]"

    corrigir(con, vaga_id, "salario", "6.000 por mês", None, T0)
    reprocessar_vaga(con, vaga_id, hoje=HOJE)
    assert _vaga(con, vaga_id)["beneficios"] == beneficios

    corrigir(con, vaga_id, "salario", "", None, T0)
    reprocessar_vaga(con, vaga_id, hoje=HOJE)
    assert _vaga(con, vaga_id)["sal_moeda"] is None
    assert _vaga(con, vaga_id)["beneficios"] == beneficios


def test_reprocessar_vaga_erro_nas_cotacoes_desfaz_o_reprocesso(con: sqlite3.Connection) -> None:
    # Caracterização: o código já é atômico, o teste nasce verde. Prova por mutação: um
    # `con.commit()` e um novo `BEGIN IMMEDIATE` antes do `aplicar_cotacoes` deixam o reprocesso
    # gravado quando as cotações falham.
    _gravar(con, [_coletada(salario_texto="US$ 5,000/month")])
    vaga_id = _id(con)
    antes = (_vaga(con, vaga_id)["sal_mensal_min"], _vaga(con, vaga_id)["sal_texto"])
    _cotar(con, "5.65")  # guardada, ainda não aplicada: o `_brl` da vaga é NULL
    corrigir(con, vaga_id, "salario", "US$ 7,000/month", None, T0)
    con.execute(
        "CREATE TRIGGER falha_brl BEFORE UPDATE OF sal_mensal_min_brl ON vaga"
        " WHEN NEW.sal_mensal_min_brl IS NOT NULL"
        " BEGIN SELECT RAISE(ABORT, 'cotação recusada'); END"
    )
    con.commit()

    with pytest.raises(sqlite3.DatabaseError, match="cotação recusada"):
        reprocessar_vaga(con, vaga_id, hoje=HOJE)

    assert (_vaga(con, vaga_id)["sal_mensal_min"], _vaga(con, vaga_id)["sal_texto"]) == antes
    assert not con.in_transaction


def test_correcao_de_salario_herda_moeda_fora_da_lista(con: sqlite3.Connection) -> None:
    _gravar(
        con,
        [
            _coletada(
                descricao=DESCRICAO_PT,
                salario_estruturado=SalarioBruto(moeda="NZD", minimo_unidades=5000, periodo="mes"),
            )
        ],
    )
    vaga_id = _id(con)
    assert _vaga(con, vaga_id)["idioma"] == "pt"
    assert _vaga(con, vaga_id)["sal_moeda"] == "NZD"
    corrigir(con, vaga_id, "salario", "6.000 por mês", None, T0)

    reprocessar_vaga(con, vaga_id, hoje=HOJE)

    assert _vaga(con, vaga_id)["sal_moeda"] == "NZD"  # não cai em BRL, a moeda do idioma
    assert _vaga(con, vaga_id)["sal_mensal_min"] == 600_000
    assert _vaga(con, vaga_id)["sal_texto"] == "6.000 por mês"


def test_listagem_sem_id_externo_mantem_o_do_detalhe(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()])
    oid = _um(con, "SELECT id FROM ocorrencia")
    gravar_detalhe(con, oid, _coletada(id_externo="abc-1"))
    _gravar(con, [_coletada()], agora=_dias(1))
    assert _um(con, "SELECT id_externo FROM ocorrencia WHERE id = ?", oid) == "abc-1"


def test_url_vista_em_escopo_falhou_nao_toca(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()], agora=T0)
    antes = _ocorrencias(con, _id(con))
    _gravar(con, agora=_dias(1), estado="falhou", urls_vistas=[URL])
    assert _ocorrencias(con, _id(con)) == antes


def test_reprocessar_vaga_recalcula_sal_e_brl(con: sqlite3.Connection) -> None:
    url_brl = "https://exemplo.test/vagas/2"
    _gravar(
        con,
        [
            _coletada(salario_texto="US$ 5,000/month", descricao=DESCRICAO_PT),
            _coletada(url=url_brl, salario_texto="R$ 8.000/mês"),
        ],
    )
    usd, brl = _id(con), _id(con, url_brl)
    assert _vaga(con, usd)["idioma"] == "pt"  # com "outro" a moeda padrão do idioma não entra
    _cotar(con, "5.65")
    aplicar_cotacoes(con, hoje=HOJE)
    assert _brl(con, usd) == (500_000, 28250, "2026-11-13")
    antes = _vaga(con, brl)
    corrigir(con, usd, "salario", "6.000 por mês", None, T0)

    reprocessar_vaga(con, usd, hoje=HOJE)

    assert _brl(con, usd) == (600_000, 33900, "2026-11-13")
    assert _vaga(con, usd)["sal_moeda"] == "USD"
    assert _vaga(con, usd)["sal_texto"] == "6.000 por mês"
    assert _vaga(con, brl) == antes

    gravar_config(con, "conversao_moeda_ligada", False)
    reprocessar_vaga(con, usd, hoje=HOJE)
    reprocessar_vaga(con, brl, hoje=HOJE)
    assert _brl(con, usd) == (600_000, None, None)
    assert _brl(con, brl) == (800_000, 8000, None)


def test_reprocessar_vaga_recalcula_brl(con: sqlite3.Connection) -> None:
    outra_url = "https://exemplo.test/vagas/2"
    _gravar(
        con,
        [
            _coletada(salario_texto="US$ 5,000/month"),
            _coletada(url=outra_url, salario_texto="US$ 5,000/month"),
        ],
    )
    vaga_id, outra = _id(con), _id(con, outra_url)
    _cotar(con, "5.65", HOJE - timedelta(days=1))
    aplicar_cotacoes(con, hoje=HOJE)
    _cotar(con, "6.00")  # cotação nova guardada depois
    corrigir(con, vaga_id, "salario", "US$ 7,000/month", None, T0)

    reprocessar_vaga(con, vaga_id, hoje=HOJE)

    assert _brl(con, vaga_id) == (700_000, 42000, "2026-11-13")
    assert _brl(con, outra) == (500_000, 28250, "2026-11-12")  # só a vaga pedida muda


def test_reprocessar_vaga_cotacao_de_8_dias_nao_vale(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada(salario_texto="US$ 5,000/month")])
    vaga_id = _id(con)
    _cotar(con, "5.65", HOJE)

    reprocessar_vaga(con, vaga_id, hoje=HOJE + timedelta(days=8))
    assert _brl(con, vaga_id) == (500_000, None, None)

    reprocessar_vaga(con, vaga_id, hoje=HOJE + timedelta(days=7))
    assert _brl(con, vaga_id) == (500_000, 28250, "2026-11-13")


def test_reprocessar_vaga_usa_ocorrencia_aberta_mais_recente(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada(titulo="Título da aberta")], escopo="a", agora=T0)
    _gravar(con, [_coletada(titulo="Título da sumida")], escopo="b", agora=_dias(1))
    _gravar(con, escopo="b", agora=_dias(2))  # b some, com ultima_vista_em maior que a
    vaga_id = _id(con)
    assert _vaga(con, vaga_id)["titulo"] == "Título da sumida"

    reprocessar_vaga(con, vaga_id, hoje=HOJE)
    assert _vaga(con, vaga_id)["titulo"] == "Título da aberta"

    _gravar(con, escopo="a", agora=_dias(3))  # sem aberta: vale a de ultima_vista_em maior
    reprocessar_vaga(con, vaga_id, hoje=HOJE)
    assert _vaga(con, vaga_id)["titulo"] == "Título da sumida"


def test_reprocessar_vaga_recusa_transacao_aberta(con: sqlite3.Connection) -> None:
    _gravar(con, [_coletada()])
    vaga_id = _id(con)
    con.execute("INSERT INTO config (chave, valor) VALUES ('idioma', '\"en\"')")
    assert con.in_transaction

    with pytest.raises(RuntimeError):
        reprocessar_vaga(con, vaga_id, hoje=HOJE)

    assert con.in_transaction  # nada confirmado nem desfeito por ela
    con.rollback()
    assert _um(con, "SELECT COUNT(*) FROM config") == 0


def test_reprocessar_vaga_corrida_com_gravar_escopo(con: sqlite3.Connection, caminho: Path) -> None:
    _gravar(con, [_coletada(titulo="Título velho")], agora=T0)
    vaga_id = _id(con)
    leu, gravou = threading.Event(), threading.Event()
    erros: list[BaseException] = []

    def outra_conexao() -> None:
        leu.wait(timeout=5)
        c2 = abrir(caminho)
        try:
            _gravar(c2, [_coletada(titulo="Título novo")], agora=_dias(1))
        except BaseException as erro:
            erros.append(erro)
        finally:
            c2.close()
            gravou.set()

    def espia(sql: str) -> None:
        # já leu a coletada e vai gravar: sem a trava da escrita, a outra conexão grava aqui
        # no meio e o reprocesso sobrescreve o título novo com o que leu antes
        if sql.lstrip().startswith("UPDATE vaga SET") and not leu.is_set():
            leu.set()
            gravou.wait(timeout=1)  # com a escrita travada, a outra conexão espera

    fio = threading.Thread(target=outra_conexao)
    fio.start()
    con.set_trace_callback(espia)
    try:
        reprocessar_vaga(con, vaga_id, hoje=HOJE)
    finally:
        con.set_trace_callback(None)
        fio.join(timeout=10)

    assert erros == []
    assert _vaga(con, vaga_id)["titulo"] == "Título novo"
    assert json.loads(_um(con, "SELECT coletada FROM ocorrencia"))["titulo"] == "Título novo"
