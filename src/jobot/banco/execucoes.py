"""Execuções, batimento e saúde no banco; `HistoricoDoBanco` para o executor (plano T22).

Desenho 7.3 (`execucao`, `saude`, `execucao_fonte`), 8.1 e 8.3 (histórico do executor), 12.3 e 12.4.
Datas entram e saem em UTC com fuso (`agora` vem de quem chama, nunca do relógio do
sistema aqui); `agora` sem fuso levanta `ValueError`.

Transações: `abrir_execucao`, `bater`, `fechar_execucao`, `interromper_execucao` e
`marcar_interrompidas` abrem e
confirmam a própria, e recusam conexão já numa transação (`RuntimeError`, como `acoes.py`),
para não consolidar nem desfazer o trabalho de quem chama. `gravar_saude` é o contrário: o
escopo grava a saúde junto com as vagas (desenho 12.4, passo 3), então ela só confirma
quando não há transação aberta; havendo, quem abriu confirma.
"""

import sqlite3
from collections.abc import Iterator, Sequence, Set
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from jobot.nucleo.coletores.executor import Historico
from jobot.nucleo.relogio import Relogio
from jobot.nucleo.url import canonica, hash_url

Tipo = Literal["busca", "descoberta", "paginas"]
Motivo = Literal["agenda", "agora", "recuperacao"]
EstadoSaude = Literal["ok", "sem_mudanca", "parcial", "falhou", "desligada", "no_limite"]

BATIMENTO_VELHO = timedelta(minutes=5)  # processo morto (desenho 12.3)
JANELA_DETALHE = timedelta(days=30)  # cache de `enriquecimento` (desenho 8.1, DR-70)
_LOTE = 500  # URLs por consulta, bem abaixo do limite de variáveis do SQLite


@dataclass(frozen=True)
class Andamento:
    """Execução que está rodando, para a tela de andamento (`GET /execucao/atual`)."""

    id: int
    tipo: str
    motivo: str
    iniciada_em: datetime
    batimento_em: datetime
    escopos_prontos: int  # linhas de `saude` já gravadas nesta execução
    fontes_rodando: tuple[str, ...] = ()  # começaram e não terminaram, na ordem de começo
    coleta_acabou: bool = False  # toda fonte ligada começou e terminou: seguem detalhes e encaixe


@dataclass(frozen=True)
class LinhaSaude:
    execucao_id: int
    iniciada_em: datetime
    fonte: str
    escopo: str
    estado: str
    vagas: int
    pedidos: int
    duracao_ms: int
    motivo: str | None  # chave de i18n, com `:valor` quando a chave tem parâmetro


def _iso(agora: datetime) -> str:
    if agora.tzinfo is None:
        raise ValueError("agora precisa ter fuso")
    return agora.astimezone(UTC).isoformat()


def _data(texto: str) -> datetime:
    data = datetime.fromisoformat(texto)
    return data if data.tzinfo else data.replace(tzinfo=UTC)


def _data_ou_none(texto: str | None) -> datetime | None:
    return None if texto is None else _data(texto)


def _sem_transacao(con: sqlite3.Connection) -> None:
    if con.in_transaction:
        raise RuntimeError("conexão já está numa transação: commit ou rollback antes")


def abrir_execucao(
    con: sqlite3.Connection, tipo: Tipo, motivo: Motivo, agora: datetime
) -> int | None:
    """Cria a execução "rodando". `None` se já há uma rodando do tipo (índice único do banco)."""
    _sem_transacao(con)
    instante = _iso(agora)
    try:
        cur = con.execute(
            "INSERT INTO execucao (tipo, motivo, iniciada_em, batimento_em, estado)"
            " VALUES (?, ?, ?, ?, 'rodando')",
            (tipo, motivo, instante, instante),
        )
    except sqlite3.IntegrityError as erro:
        con.rollback()
        if erro.sqlite_errorcode != sqlite3.SQLITE_CONSTRAINT_UNIQUE:
            raise
        return None
    con.commit()
    return cur.lastrowid


def bater(con: sqlite3.Connection, id: int, agora: datetime) -> None:
    """Batimento de uma execução que roda; em execução já encerrada não muda nada."""
    _sem_transacao(con)
    con.execute(
        "UPDATE execucao SET batimento_em=? WHERE id=? AND estado='rodando'", (_iso(agora), id)
    )
    con.commit()


def fechar_execucao(con: sqlite3.Connection, id: int, agora: datetime) -> None:
    """Conclui a execução que roda. Já interrompida fica interrompida; `id` inexistente levanta."""
    _sem_transacao(con)
    cur = con.execute(
        "UPDATE execucao SET estado='concluida', terminada_em=? WHERE id=? AND estado='rodando'",
        (_iso(agora), id),
    )
    if (
        cur.rowcount == 0
        and con.execute("SELECT 1 FROM execucao WHERE id=?", (id,)).fetchone() is None
    ):
        con.rollback()
        raise LookupError(f"execução {id} não existe")
    con.commit()


def interromper_execucao(con: sqlite3.Connection, id: int, agora: datetime) -> None:
    """Marca como "interrompida" na hora a execução que roda (exceção no meio, D54).

    Já encerrada fica como está; `id` inexistente levanta `LookupError`."""
    _sem_transacao(con)
    cur = con.execute(
        "UPDATE execucao SET estado='interrompida', terminada_em=? WHERE id=? AND estado='rodando'",
        (_iso(agora), id),
    )
    if (
        cur.rowcount == 0
        and con.execute("SELECT 1 FROM execucao WHERE id=?", (id,)).fetchone() is None
    ):
        con.rollback()
        raise LookupError(f"execução {id} não existe")
    con.commit()


def marcar_interrompidas(con: sqlite3.Connection, agora: datetime) -> int:
    """Batimento com mais de 5 min vira "interrompida", terminada no último batimento."""
    _sem_transacao(con)
    limite = _iso(agora - BATIMENTO_VELHO)
    cur = con.execute(
        "UPDATE execucao SET estado='interrompida', terminada_em=batimento_em"
        " WHERE estado='rodando' AND batimento_em < ?",
        (limite,),
    )
    con.commit()
    return cur.rowcount


def gravar_saude(
    con: sqlite3.Connection,
    execucao_id: int,
    fonte: str,
    escopo: str,
    estado: EstadoSaude,
    *,
    vagas: int = 0,
    pedidos: int = 0,
    duracao_ms: int = 0,
    motivo: str | None = None,
) -> None:
    """Uma linha de saúde por (execução, fonte, escopo); gravar de novo atualiza a linha."""
    ja_aberta = con.in_transaction
    try:
        con.execute(
            "INSERT INTO saude (execucao_id, fonte, escopo, estado, vagas, pedidos, duracao_ms,"
            " motivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(execucao_id, fonte, escopo) DO UPDATE SET estado=excluded.estado,"
            " vagas=excluded.vagas, pedidos=excluded.pedidos, duracao_ms=excluded.duracao_ms,"
            " motivo=excluded.motivo",
            (execucao_id, fonte, escopo, estado, vagas, pedidos, duracao_ms, motivo),
        )
    except BaseException:
        if not ja_aberta:
            con.rollback()
        raise
    if not ja_aberta:
        con.commit()


def _marcar_fonte(con: sqlite3.Connection, sql: str, parametros: tuple[object, ...]) -> None:
    ja_aberta = con.in_transaction  # como `gravar_saude`: quem abriu a transação confirma
    try:
        con.execute(sql, parametros)
    except BaseException:
        if not ja_aberta:
            con.rollback()
        raise
    if not ja_aberta:
        con.commit()


def comecar_fonte(con: sqlite3.Connection, execucao_id: int, fonte: str, agora: datetime) -> None:
    """A fonte começou a rodar nesta execução; começar de novo zera o fim."""
    _marcar_fonte(
        con,
        "INSERT INTO execucao_fonte (execucao_id, fonte, comecou_em) VALUES (?, ?, ?)"
        " ON CONFLICT(execucao_id, fonte) DO UPDATE SET comecou_em=excluded.comecou_em,"
        " terminou_em=NULL",
        (execucao_id, fonte, _iso(agora)),
    )


def terminar_fonte(con: sqlite3.Connection, execucao_id: int, fonte: str, agora: datetime) -> None:
    """A fonte acabou (terminou, falhou ou foi cancelada); sem começo gravado, grava os dois."""
    _marcar_fonte(
        con,
        "INSERT INTO execucao_fonte (execucao_id, fonte, comecou_em, terminou_em)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT(execucao_id, fonte) DO UPDATE SET terminou_em=excluded.terminou_em",
        (execucao_id, fonte, _iso(agora), _iso(agora)),
    )


def inicio_da_ultima_completa(con: sqlite3.Connection, tipo: Tipo) -> datetime | None:
    """Início da última execução "concluida" do tipo; interrompida e rodando não contam."""
    linha = con.execute(
        "SELECT MAX(iniciada_em) FROM execucao WHERE tipo=? AND estado='concluida'", (tipo,)
    ).fetchone()
    return _data_ou_none(linha[0])


def execucao_atual(con: sqlite3.Connection) -> Andamento | None:
    """A execução que roda; havendo mais de uma (tipos diferentes), a busca vem primeiro."""
    linha = con.execute(
        "SELECT e.id, e.tipo, e.motivo, e.iniciada_em, e.batimento_em,"
        " (SELECT count(*) FROM saude WHERE execucao_id = e.id)"
        " FROM execucao e WHERE e.estado='rodando'"
        " ORDER BY e.tipo = 'busca' DESC, e.iniciada_em DESC LIMIT 1"
    ).fetchone()
    if linha is None:
        return None
    rodando = con.execute(
        "SELECT fonte FROM execucao_fonte WHERE execucao_id = ? AND terminou_em IS NULL"
        " ORDER BY comecou_em, fonte",
        (linha[0],),
    ).fetchall()
    # a fila do semáforo do executor deixa fonte ligada sem linha: só acabou quando nenhuma falta
    sem_fim_nem_fila = con.execute(
        "SELECT (SELECT count(*) FROM execucao_fonte WHERE execucao_id = ?) > 0"
        " AND NOT EXISTS (SELECT 1 FROM fonte f WHERE f.ligada = 1 AND NOT EXISTS"
        "  (SELECT 1 FROM execucao_fonte x WHERE x.execucao_id = ? AND x.fonte = f.chave))",
        (linha[0], linha[0]),
    ).fetchone()[0]
    return Andamento(
        linha[0],
        linha[1],
        linha[2],
        _data(linha[3]),
        _data(linha[4]),
        linha[5],
        tuple(f for (f,) in rodando),
        coleta_acabou=bool(sem_fim_nem_fila) and not rodando,
    )


def saude_recente(con: sqlite3.Connection, n: int = 8) -> tuple[LinhaSaude, ...]:
    """Linhas de saúde das `n` execuções mais recentes que gravaram alguma, da mais nova."""
    linhas = con.execute(
        "SELECT s.execucao_id, e.iniciada_em, s.fonte, s.escopo, s.estado, s.vagas, s.pedidos,"
        " s.duracao_ms, s.motivo FROM saude s JOIN execucao e ON e.id = s.execucao_id"
        " WHERE s.execucao_id IN (SELECT e2.id FROM execucao e2 WHERE EXISTS"
        "   (SELECT 1 FROM saude WHERE execucao_id = e2.id)"
        "   ORDER BY e2.iniciada_em DESC, e2.id DESC LIMIT ?)"
        " ORDER BY e.iniciada_em DESC, e.id DESC, s.fonte, s.escopo",
        (n,),
    ).fetchall()
    return tuple(LinhaSaude(r[0], _data(r[1]), *r[2:]) for r in linhas)


def ultimas_que_rodaram(
    con: sqlite3.Connection, fora: Sequence[str] = ("no_limite", "desligada")
) -> dict[str, dict[str, LinhaSaude]]:
    """Por fonte e escopo, a linha da última vez em que rodou de fato (fora os estados de
    `fora`), em qualquer execução, sem o corte das `n` mais recentes de `saude_recente`."""
    linhas = con.execute(
        "SELECT execucao_id, iniciada_em, fonte, escopo, estado, vagas, pedidos, duracao_ms,"
        " motivo FROM (SELECT s.execucao_id, e.iniciada_em, s.fonte, s.escopo, s.estado,"
        " s.vagas, s.pedidos, s.duracao_ms, s.motivo, ROW_NUMBER() OVER (PARTITION BY"
        " s.fonte, s.escopo ORDER BY e.iniciada_em DESC, e.id DESC) AS rn"
        " FROM saude s JOIN execucao e ON e.id = s.execucao_id"
        f" WHERE s.estado NOT IN ({', '.join('?' * len(fora))})) WHERE rn = 1",
        tuple(fora),
    ).fetchall()
    por_fonte: dict[str, dict[str, LinhaSaude]] = {}
    for r in linhas:
        por_fonte.setdefault(r[2], {})[r[3]] = LinhaSaude(r[0], _data(r[1]), *r[2:])
    return por_fonte


def _hashes(urls: Sequence[str]) -> dict[str, list[str]]:
    """Hash da URL canônica -> URLs de entrada. URL que não é http/https é ignorada."""
    por_hash: dict[str, list[str]] = {}
    for url in urls:
        try:
            por_hash.setdefault(hash_url(canonica(url)), []).append(url)
        except ValueError:
            continue
    return por_hash


def _lotes(hashes: Sequence[str]) -> Iterator[Sequence[str]]:
    for i in range(0, len(hashes), _LOTE):
        yield hashes[i : i + _LOTE]


class HistoricoDoBanco(Historico):
    """O `Historico` do executor lido do banco. `relogio` vem de fora (a janela de 30 dias)."""

    def __init__(self, con: sqlite3.Connection, relogio: Relogio) -> None:
        self.con = con
        self.relogio = relogio

    def ultimo_inicio_com_pedido(self, fonte: str, escopo: str | None) -> datetime | None:
        """Início da última execução em que a fonte (ou o escopo) fez algum pedido (8.1)."""
        filtro, params = (
            ("", (fonte,)) if escopo is None else (" AND s.escopo = ?", (fonte, escopo))
        )
        linha = self.con.execute(
            "SELECT MAX(e.iniciada_em) FROM saude s JOIN execucao e ON e.id = s.execucao_id"
            f" WHERE s.fonte = ? AND s.pedidos > 0{filtro}",
            params,
        ).fetchone()
        return _data_ou_none(linha[0])

    def tres_ultimas_ok_trouxeram_vagas(self, fonte: str, escopo: str) -> bool:
        """As três últimas execuções "ok" do escopo trouxeram vagas (zero inesperado, DR-10)."""
        linhas = self.con.execute(
            "SELECT s.vagas FROM saude s JOIN execucao e ON e.id = s.execucao_id"
            " WHERE s.fonte = ? AND s.escopo = ? AND s.estado = 'ok'"
            " ORDER BY e.iniciada_em DESC, e.id DESC LIMIT 3",
            (fonte, escopo),
        ).fetchall()
        return len(linhas) == 3 and all(vagas > 0 for (vagas,) in linhas)

    def tem_ocorrencia_aberta(self, fonte: str, escopo: str) -> bool:
        return (
            self.con.execute(
                "SELECT 1 FROM ocorrencia WHERE fonte = ? AND escopo = ? AND sumiu_em IS NULL"
                " LIMIT 1",
                (fonte, escopo),
            ).fetchone()
            is not None
        )

    def ultima_coleta(self, fonte: str, escopo: str) -> datetime | None:
        """Início da última execução que de fato tentou o escopo (limite e desligada não valem)."""
        linha = self.con.execute(
            "SELECT MAX(e.iniciada_em) FROM saude s JOIN execucao e ON e.id = s.execucao_id"
            " WHERE s.fonte = ? AND s.escopo = ? AND s.estado NOT IN ('no_limite', 'desligada')",
            (fonte, escopo),
        ).fetchone()
        return _data_ou_none(linha[0])

    def urls_conhecidas(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        """URLs que já têm ocorrência (aberta ou sumida) dessa fonte, pelo hash da canônica."""
        por_hash = _hashes(urls)
        conhecidas: set[str] = set()
        for lote in _lotes(list(por_hash)):
            marcas = ", ".join("?" * len(lote))
            for (h,) in self.con.execute(
                "SELECT DISTINCT v.url_hash FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id"
                f" WHERE o.fonte = ? AND v.url_hash IN ({marcas})",
                (fonte, *lote),
            ):
                conhecidas.update(por_hash[h])
        return conhecidas

    def detalhe_recente(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        """URLs com detalhe tentado nos últimos 30 dias (o cache é por URL: `fonte` não entra)."""
        por_hash = _hashes(urls)
        desde = self.relogio.agora() - JANELA_DETALHE
        recentes: set[str] = set()
        for lote in _lotes(list(por_hash)):
            marcas = ", ".join("?" * len(lote))
            for h, buscado_em in self.con.execute(
                f"SELECT url_hash, buscado_em FROM enriquecimento WHERE url_hash IN ({marcas})",
                tuple(lote),
            ):
                if _data(buscado_em) >= desde:
                    recentes.update(por_hash[h])
        return recentes
