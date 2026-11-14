"""Buscas salvas e encaixe no banco (desenho 7.3 e 11; plano T24, decisões 1, 12, 17 e 18).

`recalcular_encaixe` lê só as colunas da vaga (e `local_vaga`), nunca a `ocorrencia.coletada`:
uma correção já aplicada na vaga pelo reprocessamento (T19, D11) vale no encaixe e não se desfaz.
`oculta_manual` não é lido aqui: o -1 ("mostrar mesmo assim") vence a regra na leitura, e o
`oculta_motivo` gravado continua dizendo o que as regras decidiram.
Dinheiro: o `Busca.salario_min_centavos` é centavos da moeda da busca; o encaixe compara em reais
inteiros (colunas `_brl`). Quem grava chama `commit` aqui dentro (como `cotacoes.py`); erro desfaz.
Exceções (contrato com a rota da T49): `ValueError` busca inválida, `LookupError` busca inexistente.
"""

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from jobot.banco.cotacoes import cotacao_mais_recente
from jobot.nucleo.cambio import MOEDAS, em_reais
from jobot.nucleo.encaixe import calcular
from jobot.nucleo.modelo import (
    Area,
    Aviso,
    Busca,
    Contrato,
    Idioma,
    Local,
    Modalidade,
    Nivel,
    Periodo,
    Salario,
    VagaTratada,
)
from jobot.nucleo.texto import normalizar

_BRL = "BRL"
_MAX_INT = 2**63 - 1  # maior INTEGER do SQLite
_IDIOMAS: dict[str, Idioma] = {"pt": "pt", "en": "en", "es": "es"}
_PERIODOS: dict[str, Periodo] = {p: p for p in ("hora", "dia", "semana", "mes", "ano")}

_COLUNAS_BUSCA = (
    "id, nome, ativa, cargos, cidades, modalidades, niveis, salario_min, salario_moeda,"
    " idiomas, regras_ocultar, criada_em"
)
_NOMES_VAGA = (
    "id url url_hash titulo empresa descricao_texto idioma area nivel modalidade contrato avisos"
    " sal_moeda sal_min sal_max sal_periodo sal_mensal_min sal_mensal_min_brl sal_plausivel"
    " sal_texto versao_regras"
).split()
_COLUNAS_VAGA = ", ".join(_NOMES_VAGA)


@contextmanager
def _escrita(con: sqlite3.Connection) -> Iterator[None]:
    """Pega a escrita antes de ler; confirma no fim e desfaz tudo se algo falhar."""
    if not con.in_transaction:
        con.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        con.rollback()
        raise
    con.commit()


def _validar(b: Busca) -> None:
    if not b.nome.strip():
        raise ValueError("a busca precisa de um nome")
    if b.salario_min_centavos is not None:
        if not 0 < b.salario_min_centavos <= _MAX_INT:
            raise ValueError(f"salário mínimo fora do alcance: {b.salario_min_centavos!r}")
        moeda = (b.salario_moeda or _BRL).upper()
        if moeda != _BRL and moeda not in MOEDAS:
            raise ValueError(f"moeda sem cotação: {b.salario_moeda!r}")


def _valores(b: Busca) -> tuple[Any, ...]:
    """Os campos da busca na ordem de `nome` a `regras_ocultar` do esquema."""
    cidades = [{"cidade": c.cidade, "uf": c.uf, "pais": c.pais} for c in b.cidades]
    moeda = b.salario_moeda.upper() if b.salario_moeda else None
    dump = json.dumps
    return (
        b.nome.strip(),
        int(b.ativa),
        dump(list(b.cargos), ensure_ascii=False),
        dump(cidades, ensure_ascii=False),
        dump([m.value for m in b.modalidades]),
        dump([n.value for n in b.niveis]),
        b.salario_min_centavos,
        moeda,
        dump(list(b.idiomas)),
        dump(dict(b.regras_ocultar)),
    )


def _ler(linha: Sequence[Any]) -> Busca:
    (
        id_,
        nome,
        ativa,
        cargos,
        cidades,
        modalidades,
        niveis,
        minimo,
        moeda,
        idiomas,
        regras,
        criada,
    ) = linha
    return Busca(
        id=id_,
        nome=nome,
        ativa=bool(ativa),
        cargos=tuple(json.loads(cargos)),
        cidades=tuple(Local(**c) for c in json.loads(cidades)),
        modalidades=tuple(Modalidade(m) for m in json.loads(modalidades)),
        niveis=tuple(Nivel(n) for n in json.loads(niveis)),
        salario_min_centavos=minimo,
        salario_moeda=moeda,
        idiomas=tuple(json.loads(idiomas)),
        regras_ocultar=json.loads(regras),
        criada_em=datetime.fromisoformat(criada),
    )


def buscas(con: sqlite3.Connection) -> list[Busca]:
    """Todas as buscas salvas, ativas ou não, em ordem de criação."""
    linhas = con.execute(f"SELECT {_COLUNAS_BUSCA} FROM busca ORDER BY id").fetchall()
    return [_ler(linha) for linha in linhas]


def criar_busca(
    con: sqlite3.Connection,
    busca: Busca,
    agora: datetime,
    *,
    regras_ligadas: bool,
    hoje: date,
) -> int:
    """Grava a busca (a `criada_em` é `agora`) e já calcula o encaixe dela. Devolve o id."""
    _validar(busca)
    if agora.utcoffset() is None:
        raise ValueError("agora precisa ter fuso")
    with _escrita(con):
        cur = con.execute(
            "INSERT INTO busca (nome, ativa, cargos, cidades, modalidades, niveis, salario_min,"
            " salario_moeda, idiomas, regras_ocultar, criada_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*_valores(busca), agora.astimezone(UTC).isoformat()),
        )
        busca_id = cur.lastrowid
        assert busca_id is not None
        _recalcular(con, [busca_id], regras_ligadas, hoje, None)
    return busca_id


def editar_busca(
    con: sqlite3.Connection, busca: Busca, *, regras_ligadas: bool, hoje: date
) -> None:
    """Troca todos os campos da busca (menos `criada_em`) e recalcula só o encaixe dela."""
    if busca.id is None:
        raise ValueError("editar_busca precisa de uma busca com id")
    _validar(busca)
    with _escrita(con):
        cur = con.execute(
            "UPDATE busca SET nome = ?, ativa = ?, cargos = ?, cidades = ?, modalidades = ?,"
            " niveis = ?, salario_min = ?, salario_moeda = ?, idiomas = ?, regras_ocultar = ?"
            " WHERE id = ?",
            (*_valores(busca), busca.id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"busca {busca.id} não existe")
        _recalcular(con, [busca.id], regras_ligadas, hoje, None)


def apagar_busca(con: sqlite3.Connection, busca_id: int) -> None:
    """Apaga a busca; o encaixe dela vai junto (ON DELETE CASCADE). A vaga não é tocada."""
    with _escrita(con):
        if con.execute("DELETE FROM busca WHERE id = ?", (busca_id,)).rowcount == 0:
            raise LookupError(f"busca {busca_id} não existe")


def minimo_busca_brl(con: sqlite3.Connection, b: Busca, *, hoje: date) -> int | None:
    """Salário mínimo da busca em reais inteiros, ou `None` (sem mínimo ou sem cotação).

    `salario_min_centavos` está em centavos da `salario_moeda` (sem moeda, reais). `hoje` é o dia
    local do `Relogio` (`agora.astimezone().date()`, nunca o dia UTC): cotação com mais de 7
    dias não vale (decisão 17).
    """
    if b.salario_min_centavos is None:
        return None
    moeda = (b.salario_moeda or _BRL).upper()
    if moeda == _BRL:
        return em_reais(b.salario_min_centavos, Decimal(1))
    cotacao = cotacao_mais_recente(con, moeda, hoje=hoje)
    return None if cotacao is None else em_reais(b.salario_min_centavos, cotacao.venda)


def _ativas(con: sqlite3.Connection) -> list[Busca]:
    return [b for b in buscas(con) if b.ativa]


def termos_das_buscas(con: sqlite3.Connection) -> tuple[str, ...]:
    """Cargos das buscas ativas, sem repetição (ignora caixa e acento); vai ao `ContextoColeta`."""
    vistos: dict[str, str] = {}
    for b in _ativas(con):
        for cargo in b.cargos:
            vistos.setdefault(normalizar(cargo), cargo.strip())
    return tuple(termo for chave, termo in vistos.items() if chave)


def paises_das_buscas(con: sqlite3.Connection) -> tuple[str, ...]:
    """Países das buscas ativas, em ordem alfabética: os das cidades, ou o Brasil (11.1, DR-30)."""
    paises: set[str] = set()
    for b in _ativas(con):
        achados = {c.pais.upper() for c in b.cidades if c.pais}
        paises |= achados or {"BR"}
    return tuple(sorted(paises))


def _enum[E: StrEnum](tipo: type[E], valor: str | None, padrao: E) -> E:
    try:
        return tipo(valor or "")
    except ValueError:
        return padrao


def _avisos(texto: str) -> tuple[Aviso, ...]:
    avisos: list[Aviso] = []
    for a in json.loads(texto):
        try:
            avisos.append(Aviso(a))
        except ValueError:
            continue
    return tuple(avisos)


def _vaga(v: dict[str, Any], locais: tuple[Local, ...]) -> VagaTratada:
    """Monta a `VagaTratada` só com o que o encaixe lê; o resto fica vazio."""
    salario = None
    if v["sal_moeda"] is not None:
        salario = Salario(
            moeda=v["sal_moeda"],
            minimo=v["sal_min"],
            maximo=v["sal_max"],
            periodo=_PERIODOS.get(v["sal_periodo"], "mes"),  # o encaixe não lê o período
            mensal_minimo=v["sal_mensal_min"],
            plausivel=bool(v["sal_plausivel"]),
            texto=v["sal_texto"] or "",
        )
    return VagaTratada(
        fonte="",
        escopo="",
        url=v["url"],
        titulo=v["titulo"],
        empresa=v["empresa"],
        descricao_formato="texto",
        descricao=v["descricao_texto"],
        id_externo=None,
        url_candidatura=None,
        modalidade_declarada=None,
        contrato_declarado=None,
        salario_texto=v["sal_texto"],
        salario_estruturado=None,
        publicada_em=None,
        prazo=None,
        inicio=None,
        etiquetas=(),
        url_canonica=v["url"],
        url_hash=v["url_hash"],
        descricao_texto=v["descricao_texto"],
        idioma=_IDIOMAS.get(v["idioma"], "outro"),
        locais=locais,
        area=_enum(Area, v["area"], Area.OUTRA),
        nivel=_enum(Nivel, v["nivel"], Nivel.NAO_INFORMADO),
        modalidade=_enum(Modalidade, v["modalidade"], Modalidade.NAO_INFORMADO),
        contrato=_enum(Contrato, v["contrato"], Contrato.NAO_INFORMADO),
        avisos=_avisos(v["avisos"]),
        salario=salario,
        requisitos_estagio=None,
        versao_regras=v["versao_regras"],
    )


def _recalcular(
    con: sqlite3.Connection,
    busca_ids: Sequence[int] | None,
    regras_ligadas: bool,
    hoje: date,
    vaga_id: int | None,
) -> int:
    if busca_ids is None:
        alvo = _ativas(con)
    else:
        marcas = ", ".join("?" * len(busca_ids))
        linhas = con.execute(
            f"SELECT {_COLUNAS_BUSCA} FROM busca WHERE id IN ({marcas}) ORDER BY id",
            tuple(busca_ids),
        ).fetchall()
        alvo = [_ler(linha) for linha in linhas]
    if not alvo:
        return 0
    minimos = {b.id: minimo_busca_brl(con, b, hoje=hoje) for b in alvo}
    params = () if vaga_id is None else (vaga_id,)

    def onde(coluna: str) -> str:
        return "" if vaga_id is None else f" WHERE {coluna} = ?"

    locais: dict[int, list[Local]] = {}
    for vid, cidade, uf, pais in con.execute(
        "SELECT vaga_id, cidade, uf, pais FROM local_vaga" + onde("vaga_id"), params
    ):
        locais.setdefault(vid, []).append(Local(cidade=cidade, uf=uf, pais=pais))
    gravar: list[tuple[Any, ...]] = []
    for linha in con.execute(f"SELECT {_COLUNAS_VAGA} FROM vaga" + onde("id"), params):
        dados = dict(zip(_NOMES_VAGA, linha, strict=True))
        vaga = _vaga(dados, tuple(locais.get(dados["id"], ())))
        for b in alvo:
            e = calcular(
                vaga,
                b,
                sal_mensal_brl=dados["sal_mensal_min_brl"],
                minimo_busca_brl=minimos[b.id],
                regras_ligadas=regras_ligadas,
            )
            motivos = [{"chave": m.chave, "params": dict(m.params)} for m in e.motivos]
            texto = json.dumps(motivos, ensure_ascii=False)
            gravar.append((b.id, dados["id"], e.nota, e.nivel, texto, e.oculta_motivo))
    con.executemany(
        "INSERT INTO encaixe (busca_id, vaga_id, nota, nivel, motivos, oculta_motivo)"
        " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(busca_id, vaga_id) DO UPDATE SET"
        " nota = excluded.nota, nivel = excluded.nivel, motivos = excluded.motivos,"
        " oculta_motivo = excluded.oculta_motivo",
        gravar,
    )
    return len(gravar)


def recalcular_encaixe(
    con: sqlite3.Connection,
    busca_ids: Sequence[int] | None,
    regras_ligadas: bool,
    *,
    hoje: date,
    vaga_id: int | None = None,
) -> int:
    """Grava nota, nível, motivos e `oculta_motivo` de cada vaga para cada busca; devolve quantas.

    `busca_ids` `None`: as buscas ativas; uma lista: essas, ativas ou não. `vaga_id`: só aquela
    vaga (decisão 18: a rota de correção recalcula uma vaga). `regras_ligadas` é a chave geral de
    ocultar (11.3). `hoje` é o dia local do `Relogio` (`agora.astimezone().date()`), para a validade
    de 7 dias da cotação.
    """
    with _escrita(con):
        return _recalcular(con, busca_ids, regras_ligadas, hoje, vaga_id)
