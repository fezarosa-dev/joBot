"""Leitura do painel: abas, filtros, chips, busca e detalhe (desenho 13.3 a 13.5; plano T20).

Só SQL parametrizado. O termo da busca é sempre texto: cada palavra vira uma frase entre aspas
no FTS5, ou um padrão escapado no LIKE (RF1). Sem `vaga_fts`, a busca usa LIKE (DR-05).
"""

import json
import sqlite3
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from jobot.nucleo.modelo import Local, Motivo
from jobot.nucleo.texto import normalizar

POR_PAGINA = 50

# Sem "destaques": a aba sai da função pura de nucleo/destaques.py (desenho 11.4).
_OCULTA = "(v.oculta_manual = 1 OR (v.oculta_manual = 0 AND e.oculta_motivo IS NOT NULL))"
_VENCIDA = "COALESCE(date(v.prazo) < :hoje, 0)"
_FECHADA = f"(v.fechada_em IS NOT NULL OR {_VENCIDA})"
_NA_LISTA = f"NOT {_FECHADA} AND NOT {_OCULTA}"
_NOVA = "(v.status = 'nova' AND julianday(v.primeira_vista_em) >= julianday(:agora) - 3)"
_PROGRAMA = "v.contrato IN ('trainee', 'programa', 'bolsa_pesquisa', 'concurso')"
_FECHA_LOGO = "COALESCE(date(v.prazo) BETWEEN :hoje AND date(:hoje, '+7 days'), 0)"
ABAS = {
    "todas": _NA_LISTA,
    "novas": f"{_NA_LISTA} AND {_NOVA}",
    "fecham_logo": f"{_NA_LISTA} AND {_FECHA_LOGO}",
    "salvas": "v.status = 'salva'",  # inclui fechada e vencida, com selo (DR-24)
    "candidatei": "v.status IN ('candidatei', 'entrevista', 'recusada', 'oferta')",
    "programas": f"{_NA_LISTA} AND {_PROGRAMA}",
    "ocultas": f"NOT {_FECHADA} AND {_OCULTA}",
}
_FILTROS = {
    "area": "v.area = :area",
    "nivel": "v.nivel = :nivel",
    "modalidade": "v.modalidade = :modalidade",
    "contrato": "v.contrato = :contrato",
    "uf": "EXISTS (SELECT 1 FROM local_vaga l WHERE l.vaga_id = v.id AND l.uf = :uf)",
    "fonte": "EXISTS (SELECT 1 FROM ocorrencia o WHERE o.vaga_id = v.id AND o.fonte = :fonte)",
    "encaixe": "e.nivel = :encaixe",
}
_MOTIVO_OCULTA = "CASE WHEN v.oculta_manual = 1 THEN 'manual' ELSE e.oculta_motivo END"
# chip -> (valor, junção); "motivo" e "status" só contam, nas abas Ocultas e Candidatei
_CHIPS = {
    "area": ("v.area", ""),
    "nivel": ("v.nivel", ""),
    "modalidade": ("v.modalidade", ""),
    "contrato": ("v.contrato", ""),
    "uf": ("l.uf", "JOIN local_vaga l ON l.vaga_id = v.id"),
    "fonte": ("o.fonte", "JOIN ocorrencia o ON o.vaga_id = v.id"),
    "encaixe": ("e.nivel", ""),
}
_CHIPS_DA_ABA = {"ocultas": ("motivo", _MOTIVO_OCULTA), "candidatei": ("status", "v.status")}
_RECENTES = "julianday(COALESCE(v.publicada_em, v.primeira_vista_em)) DESC"
_SALARIO = "(CASE WHEN v.sal_plausivel = 0 THEN NULL ELSE v.sal_mensal_min_brl END)"
ORDENS = {
    "encaixe": f"e.nota IS NULL, e.nota DESC, {_RECENTES}",  # sem nota cai em mais recentes
    "recentes": _RECENTES,
    "prazo": "date(v.prazo) IS NULL, date(v.prazo)",
    "salario": f"{_SALARIO} IS NULL, {_SALARIO} DESC",
    "empresa": "jobot_normalizar(v.empresa)",
}
_DE = "vaga v LEFT JOIN encaixe e ON e.vaga_id = v.id AND e.busca_id = :busca"
_COLUNAS = f"""
  v.id, v.titulo, v.empresa, v.url, v.area, v.nivel, v.modalidade, v.contrato, v.status,
  v.avisos, v.sal_moeda, v.sal_min AS sal_min_centavos, v.sal_max AS sal_max_centavos,
  v.sal_periodo, v.sal_mensal_min AS sal_mensal_min_centavos, v.sal_mensal_min_brl,
  v.sal_mensal_max_brl, v.sal_cotacao_data,
  (SELECT c.venda FROM cotacao c
    WHERE c.moeda = v.sal_moeda AND c.data = v.sal_cotacao_data) AS sal_cotacao_venda,
  v.sal_plausivel, v.prazo, v.publicada_em, v.primeira_vista_em,
  {_FECHADA} AS fechada, {_NOVA} AS nova, {_FECHA_LOGO} AS fecha_logo,
  e.nota, e.nivel AS encaixe, COALESCE(e.motivos, '[]') AS motivos,
  CASE WHEN {_OCULTA} THEN {_MOTIVO_OCULTA} END AS oculta_motivo,
  (SELECT json_group_array(json_object('cidade', l.cidade, 'uf', l.uf, 'pais', l.pais))
     FROM local_vaga l WHERE l.vaga_id = v.id) AS locais
"""


@dataclass(frozen=True, kw_only=True)
class Filtros:
    aba: str = "todas"  # chave de ABAS; outra cai em "todas"
    busca_id: int | None = None
    q: str = ""
    area: str | None = None
    nivel: str | None = None
    modalidade: str | None = None
    contrato: str | None = None
    uf: str | None = None
    fonte: str | None = None
    encaixe: str | None = None  # bom, medio, fraco
    ordem: str = "encaixe"  # chave de ORDENS; outra cai em "encaixe"
    pagina: int = 1


@dataclass(frozen=True, kw_only=True)
class Item:
    """O que o cartão da vaga mostra. Dinheiro: centavos da moeda original ou reais (`_brl`)."""

    id: int
    titulo: str
    empresa: str
    url: str
    area: str | None
    nivel: str | None
    modalidade: str | None
    contrato: str | None
    status: str
    avisos: tuple[str, ...]
    sal_moeda: str | None
    sal_min_centavos: int | None
    sal_max_centavos: int | None
    sal_periodo: str | None
    sal_mensal_min_centavos: int | None
    sal_mensal_min_brl: int | None
    sal_mensal_max_brl: int | None
    sal_cotacao_data: str | None
    sal_cotacao_venda: str | None  # reais por 1 unidade da moeda, em decimal
    sal_plausivel: bool | None
    prazo: str | None
    publicada_em: str | None
    primeira_vista_em: str
    fechada: bool  # fechada na fonte ou prazo vencido: selo "fechada"
    nova: bool
    fecha_logo: bool
    nota: int | None
    encaixe: str | None
    motivos: tuple[Motivo, ...]
    oculta_motivo: str | None  # regra que escondeu, "manual" ou None
    locais: tuple[Local, ...]


@dataclass(frozen=True, kw_only=True)
class Fonte:
    fonte: str
    url: str
    url_candidatura: str | None  # como a fonte mandou, sem nenhuma mudança


@dataclass(frozen=True, kw_only=True)
class Detalhe(Item):
    descricao_texto: str
    beneficios: tuple[str, ...]
    requisitos_estagio: str | None  # JSON, como gravado
    inicio: str | None
    sal_texto: str | None
    oculta_manual: int
    fontes: tuple[Fonte, ...]
    url_candidatura: str | None  # a primeira que uma fonte mandou


@dataclass(frozen=True, kw_only=True)
class Pagina:
    itens: tuple[Item, ...]
    tem_mais: bool


def _preparar(con: sqlite3.Connection) -> None:
    con.create_function("jobot_normalizar", 1, normalizar, deterministic=True)


def _tem_fts(con: sqlite3.Connection) -> bool:
    sql = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'vaga_fts'"
    return con.execute(sql).fetchone() is not None


def _escapar_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _busca(con: sqlite3.Connection, q: str) -> tuple[str, dict[str, str]]:
    """Condição da busca de texto. Palavra sem letra nem número não busca nada (RF1)."""
    # o FTS5 corta a consulta no NUL (a frase fica sem a aspa final) e surrogate sozinho
    # não vira UTF-8: controle e surrogate viram espaço
    q = "".join(" " if unicodedata.category(c) in ("Cc", "Cs") else c for c in q)
    palavras = [p for p in q.split() if any(c.isalnum() for c in p)]
    if not palavras:
        return "", {}
    if _tem_fts(con):
        frases = " ".join('"' + p.replace('"', '""') + '"*' for p in palavras)
        return "v.id IN (SELECT rowid FROM vaga_fts WHERE vaga_fts MATCH :fts)", {"fts": frases}
    texto = "jobot_normalizar(v.titulo || ' ' || v.empresa || ' ' || v.descricao_texto)"
    params = {f"q{i}": f"%{_escapar_like(normalizar(p))}%" for i, p in enumerate(palavras)}
    return " AND ".join(f"{texto} LIKE :{k} ESCAPE '\\'" for k in params), params


def _hoje(agora: datetime) -> str:
    """O dia no fuso local: o relógio dá UTC, e prazo e início são dias de calendário daqui."""
    return agora.astimezone().date().isoformat()


def _onde(
    con: sqlite3.Connection, f: Filtros, agora: datetime, sem: str | None = None
) -> tuple[str, dict[str, Any]]:
    """WHERE da aba e dos filtros, menos o filtro `sem` (para o chip dele, DR-43)."""
    partes = [ABAS.get(f.aba, ABAS["todas"])]
    params: dict[str, Any] = {
        "agora": agora.isoformat(),
        "hoje": _hoje(agora),
        "busca": f.busca_id,
    }
    for nome, condicao in _FILTROS.items():
        valor = getattr(f, nome)
        if valor and nome != sem:
            partes.append(condicao)
            params[nome] = valor
    texto, params_texto = _busca(con, f.q)
    if texto:
        partes.append(texto)
        params |= params_texto
    return " AND ".join(f"({p})" for p in partes), params


def _linhas(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    nomes = [d[0] for d in cur.description]
    return [dict(zip(nomes, linha, strict=True)) for linha in cur.fetchall()]


def _item(linha: dict[str, Any]) -> dict[str, Any]:
    linha["avisos"] = tuple(json.loads(linha["avisos"]))
    linha["motivos"] = tuple(
        Motivo(chave=m["chave"], params=m.get("params", {})) for m in json.loads(linha["motivos"])
    )
    linha["locais"] = tuple(Local(**local) for local in json.loads(linha["locais"]))
    for chave in ("fechada", "nova", "fecha_logo"):
        linha[chave] = bool(linha[chave])
    if linha["sal_plausivel"] is not None:
        linha["sal_plausivel"] = bool(linha["sal_plausivel"])
    return linha


def listar(con: sqlite3.Connection, f: Filtros, agora: datetime) -> Pagina:
    """Uma página de 50 vagas da aba, com os filtros, a busca e a ordem escolhidos."""
    _preparar(con)
    onde, params = _onde(con, f, agora)
    ordem = ORDENS.get(f.ordem, ORDENS["encaixe"])
    params |= {"limite": POR_PAGINA + 1, "pulo": (max(f.pagina, 1) - 1) * POR_PAGINA}
    cur = con.execute(
        f"SELECT {_COLUNAS} FROM {_DE} WHERE {onde} ORDER BY {ordem}, v.id"
        " LIMIT :limite OFFSET :pulo",
        params,
    )
    itens = tuple(Item(**_item(linha)) for linha in _linhas(cur))
    return Pagina(itens=itens[:POR_PAGINA], tem_mais=len(itens) > POR_PAGINA)


def contar_chips(
    con: sqlite3.Connection, f: Filtros, agora: datetime
) -> Mapping[str, Mapping[str, int]]:
    """Contagem por valor de cada chip; cada uma considera os outros filtros (DR-43)."""
    _preparar(con)
    chips = {nome: (valor, juncao, nome) for nome, (valor, juncao) in _CHIPS.items()}
    if f.aba in _CHIPS_DA_ABA:
        nome, valor = _CHIPS_DA_ABA[f.aba]
        chips[nome] = (valor, "", "")
    contagens: dict[str, dict[str, int]] = {}
    for nome, (valor, juncao, sem) in chips.items():
        onde, params = _onde(con, f, agora, sem=sem)
        cur = con.execute(
            f"SELECT {valor}, COUNT(DISTINCT v.id) FROM {_DE} {juncao}"
            f" WHERE {onde} AND {valor} IS NOT NULL GROUP BY 1",
            params,
        )
        contagens[nome] = {chave: n for chave, n in cur.fetchall()}
    return contagens


def contar_abas(
    con: sqlite3.Connection, busca_id: int | None, agora: datetime
) -> Mapping[str, int]:
    """Quantas vagas cada aba tem, sem filtro nem busca."""
    _preparar(con)
    contagens: dict[str, int] = {}
    for aba in ABAS:
        onde, params = _onde(con, Filtros(aba=aba, busca_id=busca_id), agora)
        contagens[aba] = con.execute(f"SELECT COUNT(*) FROM {_DE} WHERE {onde}", params).fetchone()[
            0
        ]
    return contagens


def detalhe(
    con: sqlite3.Connection, vaga_id: int, busca_id: int | None, agora: datetime | None = None
) -> Detalhe | None:
    """A vaga inteira, com as fontes das ocorrências abertas (todas, se a vaga fechou)."""
    _preparar(con)
    momento = agora or datetime.now().astimezone()
    params = {
        "id": vaga_id,
        "busca": busca_id,
        "agora": momento.isoformat(),
        "hoje": _hoje(momento),
    }
    cur = con.execute(
        f"SELECT {_COLUNAS}, v.descricao_texto, v.beneficios, v.requisitos_estagio, v.inicio,"
        f" v.sal_texto, v.oculta_manual FROM {_DE} WHERE v.id = :id",
        params,
    )
    linhas = _linhas(cur)
    if not linhas:
        return None
    linha = _item(linhas[0])
    linha["beneficios"] = tuple(json.loads(linha["beneficios"]))
    fontes = tuple(
        Fonte(fonte=fonte, url=url, url_candidatura=candidatura)
        for fonte, url, candidatura in con.execute(
            "SELECT o.fonte, o.url, json_extract(o.coletada, '$.url_candidatura')"
            " FROM ocorrencia o WHERE o.vaga_id = :id AND (o.sumiu_em IS NULL OR NOT EXISTS"
            " (SELECT 1 FROM ocorrencia a WHERE a.vaga_id = o.vaga_id AND a.sumiu_em IS NULL))"
            " ORDER BY o.primeira_vista_em, o.id",
            params,
        )
    )
    candidatura = next((x.url_candidatura for x in fontes if x.url_candidatura), None)
    return Detalhe(**linha, fontes=fontes, url_candidatura=candidatura)
