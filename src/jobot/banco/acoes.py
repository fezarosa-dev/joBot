"""Ações da pessoa no painel e o histórico delas em `evento` (desenho 7.6, DR-66).

Cada ação e o seu evento vão na mesma transação: falhou, nada fica gravado.
`evento` só recebe acréscimo (os gatilhos do esquema recusam UPDATE e DELETE).

Contrato de exceções com a T45 (as rotas traduzem em resposta HTTP, nunca em 500):
`LookupError` = vaga inexistente (404); `ValueError` = status, campo ou estado
inválido (422) (`mostrar` em vaga ocultada à mão, `trazer_de_volta` em vaga não ocultada à mão,
`desfazer_status` em "nova"). `trazer_de_volta` zera `oculta_manual` para 0 e não
restaura um -1 anterior.
`RuntimeError` = conexão já em transação (erro de quem chama, não de entrada).
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

# Ordem do fluxo (ADR 0008). `recusada` e `oferta` saem de `entrevista` e valem o mesmo degrau.
DEGRAU = {"nova": 0, "salva": 1, "candidatei": 2, "entrevista": 3, "recusada": 4, "oferta": 4}
_ANTERIOR = {"salva": "nova", "candidatei": "salva", "entrevista": "candidatei"} | {
    "recusada": "entrevista",
    "oferta": "entrevista",
}
# Campos aceitos em "Algo errado nesta vaga?" (esquema, tabela `correcao`).
_CAMPOS_CORRECAO = {"area", "nivel", "modalidade", "contrato", "uf", "salario", "fechada", "outro"}
# Campos cujo valor de antes está numa coluna da própria vaga.
_COLUNA_DO_CAMPO = {
    "area": "area",
    "nivel": "nivel",
    "modalidade": "modalidade",
    "contrato": "contrato",
    "fechada": "fechada_em",
}


@contextmanager
def _transacao(con: sqlite3.Connection) -> Iterator[None]:
    # Pega a escrita antes de ler o estado: duas abas não leem o mesmo status velho.
    # Transação do chamador não é nossa: commit/rollback aqui a consolidaria ou desfaria.
    if con.in_transaction:
        raise RuntimeError("conexão já está numa transação: commit ou rollback antes da ação")
    con.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        con.rollback()
        raise
    con.commit()


def _estado(con: sqlite3.Connection, vaga_id: int) -> tuple[str, int]:
    linha = con.execute("SELECT status, oculta_manual FROM vaga WHERE id=?", (vaga_id,)).fetchone()
    if linha is None:
        raise LookupError(f"vaga {vaga_id} não existe")
    return linha[0], linha[1]


def _evento(
    con: sqlite3.Connection,
    vaga_id: int,
    acao: str,
    agora: datetime,
    de: str | None = None,
    para: str | None = None,
) -> None:
    con.execute(
        "INSERT INTO evento (vaga_id, acao, de, para, criado_em) VALUES (?, ?, ?, ?, ?)",
        (vaga_id, acao, de, para, agora.isoformat()),
    )


def _trocar_status(
    con: sqlite3.Connection, vaga_id: int, atual: str, novo: str, acao: str, agora: datetime
) -> None:
    con.execute(
        "UPDATE vaga SET status=?, status_em=? WHERE id=?", (novo, agora.isoformat(), vaga_id)
    )
    _evento(con, vaga_id, acao, agora, atual, novo)


def mudar_status(con: sqlite3.Connection, vaga_id: int, novo: str, agora: datetime) -> None:
    """Muda o status. Para trás é `desfez`; "nova" para "salva" é `salvou`; o resto, `mudou_status`.

    Status igual ao de agora não faz nada e não grava evento.
    """
    if novo not in DEGRAU:
        raise ValueError(f"status inválido: {novo!r}")
    with _transacao(con):
        atual, _ = _estado(con, vaga_id)
        if novo == atual:
            return
        if DEGRAU[novo] < DEGRAU[atual]:
            acao = "desfez"
        elif (atual, novo) == ("nova", "salva"):
            acao = "salvou"
        else:
            acao = "mudou_status"
        _trocar_status(con, vaga_id, atual, novo, acao, agora)


def desfazer_status(con: sqlite3.Connection, vaga_id: int, agora: datetime) -> None:
    """Volta o status para o anterior do fluxo (grava `desfez`). "nova" não tem anterior."""
    with _transacao(con):
        atual, _ = _estado(con, vaga_id)
        if atual not in _ANTERIOR:
            raise ValueError(f"status {atual!r} não tem anterior")
        _trocar_status(con, vaga_id, atual, _ANTERIOR[atual], "desfez", agora)


def ocultar(con: sqlite3.Connection, vaga_id: int, agora: datetime) -> None:
    """Oculta à mão (`oculta_manual` = 1). Já oculta à mão: nada a fazer."""
    with _transacao(con):
        _, oculta = _estado(con, vaga_id)
        if oculta == 1:
            return
        con.execute("UPDATE vaga SET oculta_manual=1 WHERE id=?", (vaga_id,))
        _evento(con, vaga_id, "ocultou", agora)


def mostrar(con: sqlite3.Connection, vaga_id: int, agora: datetime) -> None:
    """Faz o "mostrar mesmo assim" numa vaga oculta por regra (`oculta_manual` = -1)."""
    with _transacao(con):
        _, oculta = _estado(con, vaga_id)
        if oculta == 1:
            raise ValueError("vaga ocultada à mão: use trazer_de_volta")
        if oculta == -1:
            return
        con.execute("UPDATE vaga SET oculta_manual=-1 WHERE id=?", (vaga_id,))
        _evento(con, vaga_id, "mostrou", agora)


def trazer_de_volta(con: sqlite3.Connection, vaga_id: int, agora: datetime) -> None:
    """Traz de volta uma vaga ocultada à mão: as regras voltam a decidir (grava `desfez`)."""
    with _transacao(con):
        _, oculta = _estado(con, vaga_id)
        if oculta != 1:
            raise ValueError("vaga não estava ocultada à mão")
        con.execute("UPDATE vaga SET oculta_manual=0 WHERE id=?", (vaga_id,))
        _evento(con, vaga_id, "desfez", agora)


def corrigir(
    con: sqlite3.Connection,
    vaga_id: int,
    campo: str,
    valor_novo: str | None,
    comentario: str | None,
    agora: datetime,
) -> None:
    """Guarda a correção em `correcao` (histórico próprio, sem `evento`).

    Só grava: não altera a vaga. Quem aplica a correção por cima das regras é o
    reprocessamento (decisão 1 da sessão); a rota de correção chama `corrigir()` e em
    seguida reprocessa a vaga, para a tela já mostrar o valor corrigido.
    """
    if campo not in _CAMPOS_CORRECAO:
        raise ValueError(f"campo de correção inválido: {campo!r}")
    with _transacao(con):
        _estado(con, vaga_id)  # vaga tem de existir
        antigo = None
        if campo in _COLUNA_DO_CAMPO:
            # nome da coluna vem do dicionário fixo acima, nunca da entrada
            antigo = con.execute(
                f"SELECT {_COLUNA_DO_CAMPO[campo]} FROM vaga WHERE id=?", (vaga_id,)
            ).fetchone()[0]
        con.execute(
            "INSERT INTO correcao (vaga_id, campo, valor_antigo, valor_novo, comentario,"
            " criada_em) VALUES (?, ?, ?, ?, ?, ?)",
            (vaga_id, campo, antigo, valor_novo, comentario, agora.isoformat()),
        )


_ABERTOS = ("nova", "salva")  # status em que a pergunta "Você se candidatou?" faz sentido


def abriu_candidatura(con: sqlite3.Connection, vaga_id: int, agora: datetime) -> bool:
    """Registra que a pessoa abriu a candidatura e reabre a pergunta. Só com `nova` ou `salva`."""
    with _transacao(con):
        atual, _ = _estado(con, vaga_id)
        if atual not in _ABERTOS:
            return False
        con.execute(
            "INSERT INTO candidatura (vaga_id, abriu_em, perguntar) VALUES (?, ?, 1)"
            " ON CONFLICT(vaga_id) DO UPDATE SET abriu_em = excluded.abriu_em, perguntar = 1",
            (vaga_id, agora.isoformat()),
        )
        return True


def responder_candidatura(
    con: sqlite3.Connection, vaga_id: int, sim: bool, agora: datetime
) -> str | None:
    """Responde a pergunta pendente. Com `sim`, vai a `candidatei` e devolve o status de antes.

    Pergunta já respondida ou vaga fora de `nova`/`salva`: nada muda e devolve `None`.
    """
    with _transacao(con):
        atual, _ = _estado(con, vaga_id)
        linha = con.execute(
            "SELECT perguntar FROM candidatura WHERE vaga_id = ?", (vaga_id,)
        ).fetchone()
        if linha is None or linha[0] != 1 or atual not in _ABERTOS:
            return None
        con.execute("UPDATE candidatura SET perguntar = 0 WHERE vaga_id = ?", (vaga_id,))
        if not sim:
            return None
        _trocar_status(con, vaga_id, atual, "candidatei", "mudou_status", agora)
        return atual


def desfazer_candidatura(con: sqlite3.Connection, vaga_id: int, agora: datetime) -> bool:
    """Desfaz o Sim: volta ao `de` do último evento de status, se ele foi o Sim (E18).

    Não lê o status de antes do formulário e não reabre a pergunta.
    """
    with _transacao(con):
        atual, _ = _estado(con, vaga_id)
        # o `desfez` de `trazer_de_volta` não tem `para`: não é troca de status; `id` é a ordem
        # real de gravação (o instante erra quando o relógio volta, D151)
        ultimo = con.execute(
            "SELECT acao, de, para FROM evento WHERE vaga_id = ?"
            " AND acao IN ('salvou', 'mudou_status', 'desfez') AND para IS NOT NULL"
            " ORDER BY id DESC LIMIT 1",
            (vaga_id,),
        ).fetchone()
        if atual != "candidatei" or ultimo is None:
            return False
        acao, de, para = ultimo
        if acao != "mudou_status" or para != "candidatei" or de not in _ABERTOS:
            return False
        _trocar_status(con, vaga_id, atual, de, "desfez", agora)
        return True
