"""Conjunto fechado de vagas de exemplo (plano T20). Todo teste de tela parte dele.

Tela que precisar de outro dado semeia no próprio teste (com `inserir_vaga`), sem mexer aqui.
Grava por SQL direto no esquema da migração 0001, sem passar pelo tratamento.
"""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta

from jobot.nucleo.modelo import VagaColetada

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)

_VAGA = {
    "descricao_texto": "Descrição da vaga.",
    "idioma": "pt",
    "area": "tecnologia",
    "nivel": "pleno",
    "modalidade": "remoto",
    "contrato": "clt",
    "primeira_vista_em": (AGORA - timedelta(days=10)).isoformat(),
    "ultima_vista_em": AGORA.isoformat(),
    "versao_regras": "1",
}
_MOTIVOS = json.dumps([{"chave": "encaixe.cargo_no_titulo", "params": {"termo": "python"}}])


def _dias(n: float) -> str:
    return (AGORA - timedelta(days=n)).isoformat()


def inserir_vaga(
    con: sqlite3.Connection,
    *,
    fonte: str = "remotive",
    url_candidatura: str | None = None,
    uf: str | None = None,
    **campos: object,
) -> int:
    """Grava uma vaga com uma ocorrência (e um local, se `uf`); `campos` são colunas de `vaga`."""
    n = con.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM vaga").fetchone()[0]
    dados: dict[str, object] = _VAGA | {"titulo": f"Vaga {n}", "empresa": f"Empresa {n}"} | campos
    dados.setdefault("url", f"https://exemplo.test/vagas/{n}")
    dados["url_hash"] = hashlib.sha256(str(dados["url"]).encode()).hexdigest()
    colunas = ", ".join(dados)
    marcas = ", ".join("?" * len(dados))
    cur = con.execute(f"INSERT INTO vaga ({colunas}) VALUES ({marcas})", tuple(dados.values()))
    vaga_id = cur.lastrowid
    assert vaga_id is not None
    con.execute("INSERT INTO fonte (chave, leva) VALUES (?, 'A') ON CONFLICT DO NOTHING", (fonte,))
    coletada = VagaColetada(
        fonte=fonte,
        escopo="",
        url=str(dados["url"]),
        titulo=str(dados["titulo"]),
        empresa=str(dados["empresa"]),
        descricao_formato="texto",
        descricao=str(dados["descricao_texto"]),
        url_candidatura=url_candidatura,
    )
    fechada = dados.get("fechada_em")
    con.execute(
        "INSERT INTO ocorrencia (vaga_id, fonte, url, coletada, primeira_vista_em,"
        " ultima_vista_em, sumiu_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            vaga_id,
            fonte,
            dados["url"],
            coletada.para_json(),
            dados["primeira_vista_em"],
            dados["ultima_vista_em"],
            fechada,
        ),
    )
    if uf is not None:
        con.execute(
            "INSERT INTO local_vaga (vaga_id, cidade, uf, pais) VALUES (?, NULL, ?, 'BR')",
            (vaga_id, uf),
        )
    con.commit()
    return vaga_id


def _encaixe(
    con: sqlite3.Connection, busca_id: int, vaga_id: int, nota: int, motivo: str | None = None
) -> None:
    nivel = "bom" if nota >= 70 else "medio" if nota >= 40 else "fraco"
    con.execute(
        "INSERT INTO encaixe (busca_id, vaga_id, nota, nivel, motivos, oculta_motivo)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (busca_id, vaga_id, nota, nivel, _MOTIVOS, motivo),
    )


def semear(con: sqlite3.Connection) -> dict[str, int]:
    """Grava o conjunto fechado e devolve os ids por nome (mais `busca`, a busca salva)."""
    ids = {
        "usd": inserir_vaga(
            con,
            titulo="Desenvolvedor Python",
            empresa="Zeta Corp",
            nivel="senior",
            sal_moeda="USD",
            sal_min=500000,
            sal_periodo="mes",
            sal_mensal_min=500000,
            sal_mensal_min_brl=28250,
            sal_cotacao_data="2026-11-13",
            sal_plausivel=1,
            sal_texto="US$ 5,000/month",
            primeira_vista_em=_dias(4),
        ),
        "brl": inserir_vaga(
            con,
            titulo="Analista de Sistemas",
            empresa="Ágil Tech",
            modalidade="presencial",
            uf="SP",
            sal_moeda="BRL",
            sal_min=800000,
            sal_periodo="mes",
            sal_mensal_min=800000,
            sal_mensal_min_brl=8000,
            sal_plausivel=1,
            sal_texto="R$ 8.000/mês",
            primeira_vista_em=_dias(5),
        ),
        "himalayas": inserir_vaga(
            con,
            fonte="himalayas",
            url="https://himalayas.app/companies/beta/jobs/42",
            url_candidatura="https://himalayas.app/companies/beta/jobs/42/apply",
            titulo="Backend Engineer",
            empresa="beta labs",
            idioma="en",
            contrato="pj",
            primeira_vista_em=_dias(6),
        ),
        "script": inserir_vaga(
            con,
            titulo="Dev C++ e C# python",
            empresa="Casa Script",
            descricao_texto="Olá <script>alert('x')</script> mundo",
            area="dados",
            nivel="junior",
            modalidade="hibrido",
            uf="RJ",
            sal_moeda="BRL",
            sal_mensal_min_brl=999999,
            sal_plausivel=0,
            primeira_vista_em=_dias(7),
        ),
        "nova": inserir_vaga(
            con,
            titulo="Engenheira de Integração",
            empresa="Nova SA",
            primeira_vista_em=_dias(1),
        ),
        "prazo_3_dias": inserir_vaga(
            con,
            titulo="Analista de Dados python",
            empresa="Prazo Ltda",
            area="dados",
            uf="SP",
            prazo="2026-11-16",
            primeira_vista_em=_dias(8),
        ),
        "trainee": inserir_vaga(
            con,
            titulo="Programa Trainee",
            empresa="Trainee Co",
            nivel="trainee",
            modalidade="presencial",
            contrato="trainee",
            uf="SP",
            prazo="2026-12-20",
            primeira_vista_em=_dias(9),
        ),
        "fechada_salva": inserir_vaga(
            con,
            titulo="Vaga Fechada",
            empresa="Fechou SA",
            status="salva",
            status_em=_dias(3),
            fechada_em=_dias(2),
        ),
        "oculta_regra": inserir_vaga(
            con, titulo="Vaga Presencial Longe", empresa="Longe SA", modalidade="presencial"
        ),
        "oculta_manual": inserir_vaga(
            con, titulo="Vaga Ocultada", empresa="Oculta SA", oculta_manual=1
        ),
        "prazo_vencido": inserir_vaga(
            con, titulo="Vaga Vencida", empresa="Venceu SA", prazo="2026-11-10"
        ),
    }
    con.execute(
        "INSERT INTO cotacao (moeda, data, venda, buscada_em)"
        " VALUES ('USD', '2026-11-13', '5.65', ?)",
        (AGORA.isoformat(),),
    )
    cur = con.execute(
        "INSERT INTO busca (nome, cargos, modalidades, criada_em)"
        " VALUES ('Python remoto', '[\"python\"]', '[\"remoto\"]', ?)",
        (AGORA.isoformat(),),
    )
    busca = cur.lastrowid
    assert busca is not None
    notas = {
        "usd": 90,
        "nova": 80,
        "himalayas": 70,
        "prazo_3_dias": 60,
        "brl": 50,
        "fechada_salva": 45,
        "oculta_manual": 45,
        "script": 30,
        "trainee": 20,
        "prazo_vencido": 85,
    }
    for nome, nota in notas.items():
        _encaixe(con, busca, ids[nome], nota)
    _encaixe(con, busca, ids["oculta_regra"], 10, "modalidade")
    con.commit()
    return ids | {"busca": busca}
