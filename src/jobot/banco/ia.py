"""IA no banco (desenho 5.4; plano T403): o que cada vaga pede, a contagem do dia e `ia_tarefas`.

`habilidades_vaga` tem uma linha por vaga, gravada por `ON CONFLICT DO UPDATE`. O acerto troca o
`pede` e não mexe na falha; a falha não apaga o `pede` anterior. `tentativas` conta as falhas
seguidas com a mesma `falha_chave` e recomeça com chave nova.
"""

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from jobot.banco.cadastros import gravar_config, ler_config


@dataclass(frozen=True)
class TarefaIA:
    ligada: bool
    backend: str  # "" = nenhum
    modelo: str


def tarefa_ia(con: sqlite3.Connection, tarefa: str) -> TarefaIA:
    """A configuração da tarefa em `ia_tarefas`. Ausente ou estranha: desligada.

    Só liga com `ligada` igual a `true` e backend e modelo em texto não vazio.
    """
    tarefas = ler_config(con, "ia_tarefas")
    item = tarefas.get(tarefa) if isinstance(tarefas, dict) else None
    if not isinstance(item, dict):
        return TarefaIA(ligada=False, backend="", modelo="")
    backend, modelo = item.get("backend"), item.get("modelo")
    backend = backend if isinstance(backend, str) else ""
    modelo = modelo if isinstance(modelo, str) else ""
    ligada = item.get("ligada") is True and bool(backend) and bool(modelo)
    return TarefaIA(ligada=ligada, backend=backend, modelo=modelo)


def gravar_tarefas_ia(con: sqlite3.Connection, tarefas: Mapping[str, TarefaIA]) -> None:
    """Grava as tarefas dadas em `ia_tarefas`; as outras do dicionário ficam como estão."""
    valor = ler_config(con, "ia_tarefas")
    todas = dict(valor) if isinstance(valor, dict) else {}
    for nome, t in tarefas.items():
        todas[nome] = {"ligada": t.ligada, "backend": t.backend, "modelo": t.modelo}
    gravar_config(con, "ia_tarefas", todas)


def gravar_pede(
    con: sqlite3.Connection,
    vaga_id: int,
    *,
    chave: str,
    pede: Sequence[str],
    backend: str,
    modelo: str,
    versao: int,
    agora: datetime,
) -> None:
    """Grava o que a vaga pede (já conferido) e de onde veio. Não mexe na falha."""
    with con:
        con.execute(
            "INSERT INTO habilidades_vaga (vaga_id, chave, pede, backend, modelo, versao, feito_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(vaga_id) DO UPDATE SET chave = excluded.chave, pede = excluded.pede,"
            " backend = excluded.backend, modelo = excluded.modelo, versao = excluded.versao,"
            " feito_em = excluded.feito_em",
            (
                vaga_id,
                chave,
                json.dumps(list(pede), ensure_ascii=False),
                backend,
                modelo,
                versao,
                agora.isoformat(),
            ),
        )


def gravar_falha(
    con: sqlite3.Connection,
    vaga_id: int,
    *,
    chave: str,
    motivo: str,
    backend: str,
    agora: datetime,
) -> None:
    """Grava a falha da vaga (`recusa`, `formato` ou `contexto`) e soma `tentativas` por chave."""
    with con:
        con.execute(
            "INSERT INTO habilidades_vaga"
            " (vaga_id, falha, falha_em, falha_chave, falha_backend, tentativas)"
            " VALUES (?, ?, ?, ?, ?, 1)"
            " ON CONFLICT(vaga_id) DO UPDATE SET falha = excluded.falha,"
            " falha_em = excluded.falha_em, falha_backend = excluded.falha_backend,"
            " tentativas = CASE WHEN habilidades_vaga.falha_chave IS excluded.falha_chave"
            " THEN habilidades_vaga.tentativas + 1 ELSE 1 END,"
            " falha_chave = excluded.falha_chave",
            (vaga_id, motivo, agora.isoformat(), chave, backend),
        )


def _contagem(con: sqlite3.Connection, agora: datetime) -> dict[str, int]:
    """`ia_chamadas` do dia local de `agora`, por backend; de outro dia ou estragada: vazia."""
    valor = ler_config(con, "ia_chamadas", None)
    if not isinstance(valor, dict) or valor.get("dia") != agora.astimezone().date().isoformat():
        return {}
    por_backend = valor.get("por_backend")
    if not isinstance(por_backend, dict):
        return {}
    return {b: n for b, n in por_backend.items() if isinstance(n, int)}


def chamadas_do_dia(con: sqlite3.Connection, backend: str, agora: datetime) -> int:
    """Chamadas do laço naquele backend no dia local de `agora` (teto do dia; D198.10)."""
    return _contagem(con, agora).get(backend, 0)


def contar_chamada(con: sqlite3.Connection, backend: str, agora: datetime) -> None:
    """Soma uma chamada antes do pedido: a que falha (pela vaga ou pelo backend) também conta.

    Guarda só o dia de hoje em `config.ia_chamadas`; o dia novo recomeça do zero.
    """
    # ponytail: ler e gravar sem trava; o laço é o único que conta (uma rodada por vez)
    contagem = _contagem(con, agora)
    contagem[backend] = contagem.get(backend, 0) + 1
    dia = agora.astimezone().date().isoformat()  # DP8: o dia é o local
    gravar_config(con, "ia_chamadas", {"dia": dia, "por_backend": contagem})


@dataclass(frozen=True)
class PedeVaga:
    pede: list[str]
    backend: str
    modelo: str


def pedes(con: sqlite3.Connection, vaga_id: int | None = None) -> dict[int, PedeVaga]:
    """O `pede` gravado de cada vaga (ou só de `vaga_id`) e de onde veio.

    Linha só com falha (`pede` NULL) ou com JSON estranho fica de fora: o critério é neutro.
    """
    onde, params = ("", ()) if vaga_id is None else (" AND vaga_id = ?", (vaga_id,))
    achados: dict[int, PedeVaga] = {}
    for vid, texto, backend, modelo in con.execute(
        "SELECT vaga_id, pede, backend, modelo FROM habilidades_vaga WHERE pede IS NOT NULL" + onde,
        params,
    ):
        try:
            valor = json.loads(texto)
        except ValueError:
            continue
        if isinstance(valor, list):
            lista = [h for h in valor if isinstance(h, str)]
            achados[vid] = PedeVaga(pede=lista, backend=backend or "", modelo=modelo or "")
    return achados


@dataclass(frozen=True)
class Candidata:
    vaga_id: int
    titulo: str
    descricao: str
    chave: str | None  # a do `pede` gravado
    falha_chave: str | None
    tentativas: int  # falhas seguidas com `falha_chave`


def candidatas(con: sqlite3.Connection) -> list[Candidata]:
    """As vagas que a fila do laço olha (desenho 5.4): abertas e, em alguma busca ativa, visíveis e
    com `nivel_base` bom ou médio; das mais novas para as mais velhas. A chave é conferida por quem
    chama, que sabe o texto enviado, o backend e o modelo."""
    return [
        Candidata(*linha)
        for linha in con.execute(
            "SELECT v.id, v.titulo, v.descricao_texto, h.chave, h.falha_chave,"
            " COALESCE(h.tentativas, 0)"
            " FROM vaga v LEFT JOIN habilidades_vaga h ON h.vaga_id = v.id"
            " WHERE v.fechada_em IS NULL AND v.oculta_manual <> 1 AND EXISTS ("
            "  SELECT 1 FROM encaixe e JOIN busca b ON b.id = e.busca_id"
            "  WHERE e.vaga_id = v.id AND b.ativa = 1 AND e.nivel_base IN ('bom', 'medio')"
            "  AND (v.oculta_manual = -1 OR e.oculta_motivo IS NULL))"
            " ORDER BY v.primeira_vista_em DESC, v.id DESC"
        )
    ]
