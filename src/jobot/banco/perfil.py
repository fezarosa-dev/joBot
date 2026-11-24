"""Perfil da pessoa (desenho 8; planos T403 e T430). Tudo aqui é dado da pessoa e fica no PC.

A linha única de `perfil` guarda as habilidades (0.5.0) e, desde a 0.6.0, os dados de contato e o
resumo; `experiencia`, `curso` e `pergunta_perfil` guardam as listas. O que vai para a IA sai da
lista permitida de cada tarefa (desenho 5.2), não daqui. Normalizar é da tela; aqui só se lê e
grava, sempre com `ON CONFLICT DO UPDATE`. "Apagar perfil" apaga tudo isso e os preparos.
"""

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


def _lista_json(texto: str | None) -> list[object]:
    """O JSON da coluna, se for lista; senão (NULL, estragado, outro tipo), lista vazia."""
    try:
        valor = json.loads(texto) if texto is not None else None
    except ValueError:
        return []
    return valor if isinstance(valor, list) else []


def _textos(texto: str | None) -> tuple[str, ...]:
    """Só os textos da lista em JSON."""
    return tuple(v for v in _lista_json(texto) if isinstance(v, str))


def habilidades(con: sqlite3.Connection) -> list[str]:
    """As habilidades gravadas. Sem perfil, ou com valor estranho, lista vazia; só textos ficam."""
    linha = con.execute("SELECT habilidades FROM perfil WHERE id = 1").fetchone()
    return [] if linha is None else list(_textos(linha[0]))


def gravar_habilidades(con: sqlite3.Connection, lista: Sequence[str], agora: datetime) -> None:
    """Grava as habilidades na linha única (`ON CONFLICT DO UPDATE`); os outros dados ficam."""
    with con:
        con.execute(
            "INSERT INTO perfil (id, habilidades, atualizado_em) VALUES (1, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET habilidades = excluded.habilidades,"
            " atualizado_em = excluded.atualizado_em",
            (json.dumps(list(lista), ensure_ascii=False), agora.isoformat()),
        )


Formacao = Literal["medio", "tecnico", "graduacao", "pos_graduacao", "mestrado", "doutorado"]


@dataclass(frozen=True)
class Dados:
    """As colunas da 0.6.0 na linha única. Vazio = `None` (ou tupla vazia, nas listas)."""

    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    cidade_moradia: str | None = None
    cargo_atual: str | None = None
    anos_de_experiencia: int | None = None  # 0 a 60 (CHECK)
    formacao_nivel: Formacao | None = None
    resumo: str | None = None
    idiomas_falados: tuple[tuple[str, str], ...] = ()  # (idioma, nível)
    links: tuple[str, ...] = ()


_TEXTOS = ("nome", "email", "telefone", "cidade_moradia", "cargo_atual")
_COLUNAS = (*_TEXTOS, "anos_de_experiencia", "formacao_nivel", "resumo", "idiomas_falados", "links")


def dados(con: sqlite3.Connection) -> Dados:
    """Os dados gravados. Sem perfil, `Dados()`; listas estragadas viram vazias."""
    linha = con.execute(f"SELECT {', '.join(_COLUNAS)} FROM perfil WHERE id = 1").fetchone()
    if linha is None:
        return Dados()
    nome, email, telefone, cidade, cargo, anos, formacao, resumo, idiomas, links = linha
    pares = tuple(
        (p[0], p[1])
        for p in _lista_json(idiomas)
        if isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p)
    )
    return Dados(
        nome,
        email,
        telefone,
        cidade,
        cargo,
        anos_de_experiencia=anos,
        formacao_nivel=formacao,
        resumo=resumo,
        idiomas_falados=pares,
        links=_textos(links),
    )


def gravar_dados(con: sqlite3.Connection, novos: Dados, agora: datetime) -> None:
    """Grava todas as colunas de `Dados` na linha única; as habilidades ficam como estão.

    Sem a linha, ela nasce com a lista de habilidades vazia.
    """
    valores = (
        *(getattr(novos, c) for c in _TEXTOS),
        novos.anos_de_experiencia,
        novos.formacao_nivel,
        novos.resumo,
        json.dumps([list(p) for p in novos.idiomas_falados], ensure_ascii=False),
        json.dumps(list(novos.links), ensure_ascii=False),
    )
    with con:
        con.execute(
            f"INSERT INTO perfil (id, habilidades, atualizado_em, {', '.join(_COLUNAS)})"
            f" VALUES (1, '[]', ?, {', '.join('?' * len(_COLUNAS))})"
            " ON CONFLICT(id) DO UPDATE SET atualizado_em = excluded.atualizado_em, "
            + ", ".join(f"{c} = excluded.{c}" for c in _COLUNAS),
            (agora.isoformat(), *valores),
        )


@dataclass(frozen=True)
class Experiencia:
    cargo: str
    empresa: str | None = None
    inicio: str | None = None  # AAAA-MM
    fim: str | None = None  # AAAA-MM; None = o emprego de hoje
    descricao: str | None = None
    id: int | None = None  # None = nova


def experiencias(con: sqlite3.Connection) -> list[Experiencia]:
    """As experiências, na ordem em que entraram."""
    return [
        Experiencia(cargo, empresa, inicio, fim, descricao, id_)
        for id_, cargo, empresa, inicio, fim, descricao in con.execute(
            "SELECT id, cargo, empresa, inicio, fim, descricao FROM experiencia ORDER BY id"
        )
    ]


def gravar_experiencia(con: sqlite3.Connection, exp: Experiencia) -> int:
    """Grava a experiência (nova com `id` None; senão, no lugar) e devolve o `id`."""
    with con:
        (id_,) = con.execute(
            "INSERT INTO experiencia (id, cargo, empresa, inicio, fim, descricao)"
            " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET cargo = excluded.cargo,"
            " empresa = excluded.empresa, inicio = excluded.inicio, fim = excluded.fim,"
            " descricao = excluded.descricao RETURNING id",
            (exp.id, exp.cargo, exp.empresa, exp.inicio, exp.fim, exp.descricao),
        ).fetchone()
    return int(id_)


def apagar_experiencia(con: sqlite3.Connection, id_: int) -> None:
    """Tira a experiência: a linha some (é dado da pessoa, não vaga)."""
    with con:
        con.execute("DELETE FROM experiencia WHERE id = ?", (id_,))


Situacao = Literal["concluido", "cursando", "trancado"]


@dataclass(frozen=True)
class Curso:
    nome: str
    instituicao: str | None = None
    situacao: Situacao | None = None
    previsao: str | None = None  # AAAA-MM: fim ou previsão de formatura
    id: int | None = None  # None = novo


def cursos(con: sqlite3.Connection) -> list[Curso]:
    """Os cursos, na ordem em que entraram."""
    return [
        Curso(nome, instituicao, situacao, previsao, id_)
        for id_, nome, instituicao, situacao, previsao in con.execute(
            "SELECT id, nome, instituicao, situacao, previsao FROM curso ORDER BY id"
        )
    ]


def gravar_curso(con: sqlite3.Connection, curso: Curso) -> int:
    """Grava o curso (novo com `id` None; senão, no lugar) e devolve o `id`."""
    with con:
        (id_,) = con.execute(
            "INSERT INTO curso (id, nome, instituicao, situacao, previsao) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET nome = excluded.nome,"
            " instituicao = excluded.instituicao, situacao = excluded.situacao,"
            " previsao = excluded.previsao RETURNING id",
            (curso.id, curso.nome, curso.instituicao, curso.situacao, curso.previsao),
        ).fetchone()
    return int(id_)


def apagar_curso(con: sqlite3.Connection, id_: int) -> None:
    """Tira o curso: a linha some."""
    with con:
        con.execute("DELETE FROM curso WHERE id = ?", (id_,))


Origem = Literal["base", "ia"]


@dataclass(frozen=True)
class PerguntaPerfil:
    chave: str
    pergunta: str
    origem: Origem
    por_que: str | None = None
    resposta: str | None = None  # None = ainda sem resposta


def perguntas(con: sqlite3.Connection) -> list[PerguntaPerfil]:
    """As perguntas do perfil, na ordem em que entraram."""
    return [
        PerguntaPerfil(*linha)
        for linha in con.execute(
            "SELECT chave, pergunta, origem, por_que, resposta FROM pergunta_perfil ORDER BY id"
        )
    ]


def gravar_pergunta(
    con: sqlite3.Connection,
    chave: str,
    pergunta: str,
    origem: Origem,
    agora: datetime,
    *,
    por_que: str | None = None,
) -> None:
    """Grava a pergunta pela `chave`. A mesma chave troca o texto e o porquê, nunca a resposta."""
    with con:
        con.execute(
            "INSERT INTO pergunta_perfil (chave, pergunta, por_que, origem, criada_em)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT(chave) DO UPDATE SET"
            " pergunta = excluded.pergunta, por_que = excluded.por_que, origem = excluded.origem",
            (chave, pergunta, por_que, origem, agora.isoformat()),
        )


def responder_pergunta(con: sqlite3.Connection, chave: str, resposta: str, agora: datetime) -> None:
    """Grava a resposta da pergunta que já existe; chave desconhecida não cria nada."""
    with con:
        con.execute(
            "UPDATE pergunta_perfil SET resposta = ?, respondida_em = ? WHERE chave = ?",
            (resposta, agora.isoformat(), chave),
        )


def apagar_perfil(con: sqlite3.Connection) -> None:
    """ "Apagar perfil": a linha, as experiências, os cursos, as perguntas e os preparos.

    `habilidades_vaga` e `candidatura` ficam: são da vaga e não dependem do perfil.
    """
    with con:
        for tabela in ("perfil", "experiencia", "curso", "pergunta_perfil", "preparo_candidatura"):
            con.execute(f"DELETE FROM {tabela}")
