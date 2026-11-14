"""Cadastros no banco: fontes, empresas e configuração (desenho 8.6 e 13.7; plano T23).

`semear` copia `fontes.json` e `empresas.json` para as tabelas `fonte` e `empresa` sem apagar
nem sobrescrever o que a pessoa mudou (`ligada`, `ativa`, `removida_em`, nome, área).
Remover empresa marca `removida_em` e deixa a linha (DR-68). Empresa se grava com
`INSERT ... ON CONFLICT DO UPDATE` ou `DO NOTHING`, nunca com `REPLACE`: o `id` não muda.

Quem grava chama `commit` aqui dentro (`with con`), como `cotacoes.py`; o `abrir()` deixa o modo
legado do sqlite3, em que um UPDATE solto já abriu transação.
Contrato de exceções (as rotas traduzem em 404 e 422): `LookupError` = fonte ou empresa que não
existe; `ValueError` = empresa sem nome ou identificador, fonte desconhecida, `agora` sem fuso,
valor de config que não vira JSON.
"""

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, cast

from jobot.nucleo.coletores.registro import carregar_fontes
from jobot.nucleo.modelo import Empresa

_DADOS = Path(__file__).resolve().parents[1] / "nucleo" / "dados"

# Padrões das chaves liga/desliga da 13.7 e do N dos destaques. Ficam aqui, num lugar só, para
# quem lê a chave não repetir o padrão (padrão `None` desligaria a regra em silêncio).
# `segundo_plano` não tem padrão: a pessoa escolhe na primeira execução.
PADROES: Mapping[str, object] = MappingProxyType(
    {
        "descoberta_cc_ligada": True,
        "paginas_ligadas": True,
        "enriquecimento_ligado": True,
        "destaques_ligados": True,
        "conversao_moeda_ligada": True,
        "regras_ocultar_ligadas": True,
        "destaques_n": 10,
    }
)
_SEM_PADRAO: Any = object()

_COLUNAS_EMPRESA = (
    "id, nome, area, pais, fonte, identificador, parametros, ativa, removida_em, origem,"
    " conferida_em"
)


@dataclass(frozen=True)
class FonteCadastrada:
    chave: str
    leva: Literal["A", "B"]
    ligada: bool
    intervalo_min: int | None  # minutos entre execuções; None = sem intervalo mínimo


def empresas_iniciais() -> tuple[Empresa, ...]:
    """As empresas de `empresas.json` (a lista inicial, desenho 8.6), na ordem do arquivo."""
    bruto = json.loads((_DADOS / "empresas.json").read_text(encoding="utf-8"))
    if bruto.get("versao") != 1:
        raise ValueError(f"versão de empresas.json desconhecida: {bruto.get('versao')!r}")
    return tuple(
        Empresa(
            nome=e["nome"],
            fonte=e["fonte"],
            identificador=e["identificador"],
            area=e.get("area"),
            pais=e.get("pais"),
            parametros=dict(e.get("parametros", {})),
            origem="lista_inicial",
            conferida_em=date.fromisoformat(e["conferida_em"]) if e.get("conferida_em") else None,
        )
        for e in bruto["empresas"]
    )


def semear(con: sqlite3.Connection) -> None:
    """Copia as fontes e a lista inicial de empresas para o banco; pode rodar quantas vezes quiser.

    Fonte: `leva` e `intervalo_min` seguem o arquivo; `ligada` é da pessoa e não é tocada.
    Empresa: casa por (`fonte`, `identificador`); quem já tem linha é pulada, mesmo desligada
    ou removida.
    """
    texto = (_DADOS / "fontes.json").read_text(encoding="utf-8")
    with con:
        for chave, limites in carregar_fontes(texto).items():
            con.execute(
                "INSERT INTO fonte (chave, leva, intervalo_min) VALUES (?, ?, ?)"
                " ON CONFLICT(chave) DO UPDATE SET leva = excluded.leva,"
                " intervalo_min = excluded.intervalo_min",
                (chave, limites.leva, limites.intervalo_min),
            )
        for e in empresas_iniciais():
            con.execute(
                "INSERT INTO empresa (nome, area, pais, fonte, identificador, parametros,"
                " origem, conferida_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(fonte, identificador) DO NOTHING",
                (
                    e.nome,
                    e.area,
                    e.pais,
                    e.fonte,
                    e.identificador,
                    _json(e.parametros),
                    e.origem,
                    e.conferida_em.isoformat() if e.conferida_em else None,
                ),
            )


def _json(parametros: Mapping[str, str]) -> str:
    return json.dumps(dict(parametros), ensure_ascii=False, sort_keys=True)


def fontes(con: sqlite3.Connection) -> list[FonteCadastrada]:
    """Todas as fontes, na ordem em que entraram (a do `fontes.json`)."""
    linhas = con.execute(
        "SELECT chave, leva, ligada, intervalo_min FROM fonte ORDER BY rowid"
    ).fetchall()
    return [
        FonteCadastrada(c, cast(Literal["A", "B"], lv), bool(li), im) for c, lv, li, im in linhas
    ]


def ligar_fonte(con: sqlite3.Connection, chave: str, ligada: bool) -> None:
    with con:
        cur = con.execute("UPDATE fonte SET ligada = ? WHERE chave = ?", (int(ligada), chave))
        if cur.rowcount == 0:
            raise LookupError(f"fonte inexistente: {chave!r}")


def _empresa(linha: tuple[Any, ...]) -> Empresa:
    id_, nome, area, pais, fonte, identificador, parametros, ativa, removida, origem, conferida = (
        linha
    )
    return Empresa(
        id=id_,
        nome=nome,
        area=area,
        pais=pais,
        fonte=fonte,
        identificador=identificador,
        parametros=json.loads(parametros),
        ativa=bool(ativa),
        removida_em=datetime.fromisoformat(removida) if removida else None,
        origem=origem,
        conferida_em=date.fromisoformat(conferida) if conferida else None,
    )


def empresas(con: sqlite3.Connection) -> list[Empresa]:
    """As empresas da tela Empresas: desligadas incluídas, removidas não."""
    linhas = con.execute(
        f"SELECT {_COLUNAS_EMPRESA} FROM empresa WHERE removida_em IS NULL ORDER BY id"
    ).fetchall()
    return [_empresa(linha) for linha in linhas]


def empresas_da_coleta(con: sqlite3.Connection) -> tuple[Empresa, ...]:
    """O que entra em `ContextoColeta.empresas`: ativas e não removidas."""
    linhas = con.execute(
        f"SELECT {_COLUNAS_EMPRESA} FROM empresa WHERE ativa = 1 AND removida_em IS NULL"
        " ORDER BY id"
    ).fetchall()
    return tuple(_empresa(linha) for linha in linhas)


def adicionar_empresa(con: sqlite3.Connection, empresa: Empresa) -> int:
    """Grava a empresa ativa e devolve o `id`; `id`, `ativa` e `removida_em` da entrada não contam.

    Se (`fonte`, `identificador`) já tem linha, é a mesma linha: limpa `removida_em`, liga
    de novo e põe o nome e os parâmetros dados (área e país só se vierem). `origem` e
    `conferida_em` da linha antiga ficam.
    """
    nome = empresa.nome.strip()
    identificador = empresa.identificador.strip()
    if not nome or not identificador:
        raise ValueError("empresa precisa de nome e identificador")
    if con.execute("SELECT 1 FROM fonte WHERE chave = ?", (empresa.fonte,)).fetchone() is None:
        raise ValueError(f"fonte desconhecida: {empresa.fonte!r}")
    with con:
        linhas = con.execute(
            "INSERT INTO empresa (nome, area, pais, fonte, identificador, parametros, origem,"
            " conferida_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(fonte, identificador) DO UPDATE SET nome = excluded.nome,"
            " area = COALESCE(excluded.area, area), pais = COALESCE(excluded.pais, pais),"
            " parametros = excluded.parametros, ativa = 1, removida_em = NULL RETURNING id",
            (
                nome,
                empresa.area,
                empresa.pais,
                empresa.fonte,
                identificador,
                _json(empresa.parametros),
                empresa.origem,
                empresa.conferida_em.isoformat() if empresa.conferida_em else None,
            ),
        ).fetchall()
    return int(linhas[0][0])


def ativar_empresa(con: sqlite3.Connection, id: int, ativa: bool) -> None:
    with con:
        cur = con.execute("UPDATE empresa SET ativa = ? WHERE id = ?", (int(ativa), id))
        if cur.rowcount == 0:
            raise LookupError(f"empresa inexistente: {id}")


def remover_empresa(con: sqlite3.Connection, id: int, agora: datetime) -> None:
    """Marca `removida_em` e deixa a linha e as vagas (DR-68). Remover de novo não muda a data."""
    if agora.utcoffset() is None:
        raise ValueError("agora precisa ter fuso")
    with con:
        cur = con.execute(
            "UPDATE empresa SET removida_em = COALESCE(removida_em, ?) WHERE id = ?",
            (agora.astimezone(UTC).isoformat(), id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"empresa inexistente: {id}")


def ler_config(con: sqlite3.Connection, chave: str, padrao: Any = _SEM_PADRAO) -> Any:
    """Valor da chave (JSON decodificado). Sem linha, ou com JSON estragado, vale `padrao`.

    Sem `padrao`, vale o de `PADROES`; chave que não está lá levanta `KeyError`.
    """
    linha = con.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    if linha is not None:
        try:
            return json.loads(linha[0])
        except ValueError:
            pass
    return PADROES[chave] if padrao is _SEM_PADRAO else padrao


def gravar_config(con: sqlite3.Connection, chave: str, valor: object) -> None:
    """Grava `valor` como JSON; valor que não vira JSON levanta `ValueError` ou `TypeError`."""
    texto = json.dumps(valor, ensure_ascii=False, allow_nan=False)
    with con:
        con.execute(
            "INSERT INTO config (chave, valor) VALUES (?, ?)"
            " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            (chave, texto),
        )
