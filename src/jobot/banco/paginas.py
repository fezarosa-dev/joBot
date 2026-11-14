"""Páginas acompanhadas no banco (desenho 8.8; plano T72).

Leitura que falha muda só o `estado` e deixa o texto da última leitura boa; só `remover_pagina`
apaga.
Datas gravadas como texto ISO em UTC, como em `execucoes.py`.
Contrato de exceções (a rota de sites traduz em 404 e 422): `LookupError` = página ou mudança
que não existe; `ValueError` = endereço não permitido (DR-19), nome vazio, `agora` sem fuso.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from jobot.nucleo.coletores.paginas import Mudanca, Pagina, endereco_permitido


@dataclass(frozen=True)
class MudancaPagina:
    id: int
    pagina_id: int
    nome: str
    url: str
    detectada_em: datetime
    diferenca: str  # saída do `difflib.unified_diff`
    vista: bool


def _iso(agora: datetime) -> str:
    if agora.utcoffset() is None:
        raise ValueError("agora precisa ter fuso")
    return agora.astimezone(UTC).isoformat()


def _data(texto: str | None) -> datetime | None:
    return None if texto is None else datetime.fromisoformat(texto)


def adicionar_pagina(con: sqlite3.Connection, url: str, nome: str) -> int:
    """Grava a página (ou renomeia e reativa a do mesmo endereço) e devolve o `id`."""
    nome = nome.strip()
    if not nome:
        raise ValueError("a página precisa de um nome")
    if not endereco_permitido(url):
        raise ValueError(f"endereço não permitido: {url!r}")
    with con:
        linha = con.execute(
            "INSERT INTO pagina_acompanhada (url, nome) VALUES (?, ?)"
            " ON CONFLICT(url) DO UPDATE SET nome=excluded.nome, ativa=1 RETURNING id",
            (url, nome),
        ).fetchone()
    return int(linha[0])


def paginas(con: sqlite3.Connection) -> list[Pagina]:
    linhas = con.execute(
        "SELECT id, url, nome, ativa, texto, hash_texto, verificada_em, mudou_em, estado"
        " FROM pagina_acompanhada ORDER BY nome, id"
    ).fetchall()
    return [
        Pagina(
            id=r[0],
            url=r[1],
            nome=r[2],
            ativa=bool(r[3]),
            texto=r[4],
            hash_texto=r[5],
            verificada_em=_data(r[6]),
            mudou_em=_data(r[7]),
            estado=r[8],
        )
        for r in linhas
    ]


def mudancas(con: sqlite3.Connection) -> list[MudancaPagina]:
    """Todas as mudanças, a mais nova primeiro."""
    linhas = con.execute(
        "SELECT m.id, m.pagina_id, p.nome, p.url, m.detectada_em, m.diferenca, m.vista"
        " FROM mudanca_pagina m JOIN pagina_acompanhada p ON p.id = m.pagina_id"
        " ORDER BY m.detectada_em DESC, m.id DESC"
    ).fetchall()
    return [
        MudancaPagina(
            id=r[0],
            pagina_id=r[1],
            nome=r[2],
            url=r[3],
            detectada_em=datetime.fromisoformat(r[4]),
            diferenca=r[5],
            vista=bool(r[6]),
        )
        for r in linhas
    ]


def ultimas_diferencas(con: sqlite3.Connection) -> dict[int, str]:
    """A diferença da mudança mais nova de cada página que já mudou."""
    linhas = con.execute(
        "SELECT pagina_id, diferenca FROM mudanca_pagina"
        " WHERE id IN (SELECT MAX(id) FROM mudanca_pagina GROUP BY pagina_id)"
    ).fetchall()
    return dict(linhas)


def marcar_vista(con: sqlite3.Connection, id: int) -> None:
    with con:
        cur = con.execute("UPDATE mudanca_pagina SET vista=1 WHERE id=?", (id,))
    if cur.rowcount == 0:
        raise LookupError(f"mudança {id} não existe")


def gravar_leitura(
    con: sqlite3.Connection, pagina_id: int, mudanca: Mudanca | None, agora: datetime
) -> None:
    """Leitura que deu certo: estado "ok" e, se o texto mudou, o texto novo e a diferença.

    O texto novo e a linha de `mudanca_pagina` saem juntos ou nada sai. Página apagada no meio
    da execução: nada a gravar.
    """
    instante = _iso(agora)
    with con:
        if mudanca is None:
            con.execute(
                "UPDATE pagina_acompanhada SET estado='ok', verificada_em=? WHERE id=?",
                (instante, pagina_id),
            )
            return
        mudou = mudanca.diferenca is not None
        cur = con.execute(
            "UPDATE pagina_acompanhada SET estado='ok', verificada_em=?, texto=?, hash_texto=?,"
            " mudou_em=CASE WHEN ? THEN ? ELSE mudou_em END WHERE id=?",
            (instante, mudanca.texto, mudanca.hash_texto, mudou, instante, pagina_id),
        )
        if mudou and cur.rowcount:
            con.execute(
                "INSERT INTO mudanca_pagina (pagina_id, detectada_em, diferenca) VALUES (?, ?, ?)",
                (pagina_id, instante, mudanca.diferenca),
            )


def marcar_falhou(con: sqlite3.Connection, pagina_id: int) -> None:
    """Leitura que falhou: só o estado muda; texto, hash e `verificada_em` ficam (8.8)."""
    with con:
        con.execute("UPDATE pagina_acompanhada SET estado='falhou' WHERE id=?", (pagina_id,))


def desativar_pagina(con: sqlite3.Connection, id: int) -> None:
    """Para de acompanhar a página, sem apagar o texto nem as mudanças; `LookupError` se não existe.

    `adicionar_pagina` com o mesmo endereço a reativa.
    """
    with con:
        cur = con.execute("UPDATE pagina_acompanhada SET ativa=0 WHERE id=?", (id,))
    if cur.rowcount == 0:
        raise LookupError(f"página {id} não existe")


def remover_pagina(con: sqlite3.Connection, id: int) -> None:
    """Apaga a página e, em cascata (`ON DELETE CASCADE`), as mudanças dela.

    É a única remoção de verdade do banco: a pessoa pediu para esquecer a página. `LookupError`
    se não existe.
    """
    with con:
        cur = con.execute("DELETE FROM pagina_acompanhada WHERE id=?", (id,))
    if cur.rowcount == 0:
        raise LookupError(f"página {id} não existe")
