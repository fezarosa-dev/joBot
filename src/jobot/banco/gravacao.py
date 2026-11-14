"""Gravação do escopo, ciclo de vida no banco e reprocessamento (desenho 7.6, 10.2, 12.4; T19).

Vaga e ocorrência sempre com `INSERT ... ON CONFLICT DO UPDATE`, nunca `REPLACE`: o REPLACE
apaga a linha e leva junto, por cascata, ocorrências, locais, correções e encaixes (DR-69).
"""

import json
import sqlite3
from collections.abc import Iterable, Iterator, Sequence, Set
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from typing import Any

from jobot.banco.cadastros import ler_config
from jobot.banco.cotacoes import aplicar_cotacoes
from jobot.nucleo.coletores.executor import SaidaEscopo
from jobot.nucleo.http import LeitorValidadores, Validadores
from jobot.nucleo.modelo import (
    Area,
    Contrato,
    Local,
    Modalidade,
    Nivel,
    Salario,
    VagaColetada,
    VagaTratada,
)
from jobot.nucleo.tratamento.ciclo_de_vida import OcorrenciaAberta, aplicar_ciclo, vaga_fechada
from jobot.nucleo.tratamento.duplicadas import agrupar
from jobot.nucleo.tratamento.salario import ler_salario
from jobot.nucleo.tratamento.tratar import tratar
from jobot.nucleo.url import canonica, hash_url

_MAX_INTEGER = 2**63 - 1  # maior INTEGER do SQLite (D26)
# 304 só toca e o http.py só traz validador de resposta 200, então guardar no "sem_mudanca"
# é guardar o das páginas que vieram inteiras; parcial e falhou deixam o cache como estava.
_GUARDA_VALIDADORES = {"ok", "sem_mudanca"}
_ROTULOS: dict[str, frozenset[str]] = {
    "area": frozenset(Area),
    "nivel": frozenset(Nivel),
    "modalidade": frozenset(Modalidade),
    "contrato": frozenset(Contrato),
}
_NAO = {"0", "nao", "não", "false", "no"}  # correção "fechada" que desfaz uma anterior
_SALARIO = ("sal_moeda", "sal_min", "sal_max", "sal_periodo", "sal_mensal_min", "sal_plausivel")
# Colunas da vaga que saem do tratamento; nomes fixos, nunca da entrada.
_DERIVADAS = (
    "titulo",
    "empresa",
    "idioma",
    "area",
    "nivel",
    "modalidade",
    "contrato",
    "avisos",
    *_SALARIO,
    "sal_texto",
    "beneficios",
    "requisitos_estagio",
    "publicada_em",
    "prazo",
    "inicio",
    "versao_regras",
)
# Ocorrência escolhida para reprocessar: aberta de preferência, depois a vista por último.
_OCORRENCIA_ESCOLHIDA = (
    "SELECT coletada FROM ocorrencia WHERE vaga_id = ?"
    " ORDER BY sumiu_em IS NOT NULL, julianday(ultima_vista_em) DESC, id DESC LIMIT 1"
)


@dataclass(frozen=True)
class ResumoEscopo:
    novas: int
    fechadas: int


class ValidadoresDoBanco(LeitorValidadores):
    """Lê os validadores guardados em `cache_http` para o pedido condicional (DR-12)."""

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    def ler(self, url: str) -> Validadores | None:
        linha = self._con.execute(
            "SELECT etag, last_modified FROM cache_http WHERE url = ?", (url,)
        ).fetchone()
        return None if linha is None else Validadores(linha[0], linha[1])


@contextmanager
def _transacao(con: sqlite3.Connection) -> Iterator[None]:
    # Transação do chamador não é nossa: commit/rollback aqui a consolidaria ou desfaria.
    if con.in_transaction:
        raise RuntimeError("conexão já está numa transação")
    con.execute("BEGIN IMMEDIATE")  # pega a escrita antes de ler
    try:
        yield
    except BaseException:
        con.rollback()
        raise
    con.commit()


def _utc(agora: datetime) -> str:
    if agora.utcoffset() is None:
        raise ValueError("agora precisa ter fuso")
    return agora.astimezone(UTC).isoformat()


def _data(texto: str | None) -> datetime | None:
    return None if texto is None else datetime.fromisoformat(texto)


# ---------------------------------------------------------------- colunas da vaga


def _salario(s: Salario | None, texto: str | None) -> dict[str, Any]:
    vazio: dict[str, Any] = dict.fromkeys(_SALARIO)
    if s is None:
        return vazio | {"sal_texto": texto, "beneficios": "[]"}
    base = {"sal_texto": s.texto, "beneficios": json.dumps(list(s.beneficios), ensure_ascii=False)}
    if any(v is not None and abs(v) > _MAX_INTEGER for v in (s.minimo, s.maximo, s.mensal_minimo)):
        return vazio | base  # não cabe em INTEGER: grava como sem salário, sem erro (D26)
    return base | {
        "sal_moeda": s.moeda,
        "sal_min": s.minimo,
        "sal_max": s.maximo,
        "sal_periodo": s.periodo,
        "sal_mensal_min": s.mensal_minimo,
        "sal_plausivel": int(s.plausivel),
    }


def _colunas(t: VagaTratada) -> dict[str, Any]:
    req = t.requisitos_estagio
    return {
        "titulo": t.titulo,
        "empresa": t.empresa,
        "descricao_texto": t.descricao_texto,
        "idioma": t.idioma,
        "area": t.area.value,
        "nivel": t.nivel.value,
        "modalidade": t.modalidade.value,
        "contrato": t.contrato.value,
        "avisos": json.dumps([a.value for a in t.avisos]),
        **_salario(t.salario, t.salario_texto),
        "requisitos_estagio": None if req is None else json.dumps(asdict(req), ensure_ascii=False),
        "publicada_em": None if t.publicada_em is None else _utc(t.publicada_em),
        "prazo": None if t.prazo is None else t.prazo.isoformat(),
        "inicio": None if t.inicio is None else t.inicio.isoformat(),
        "versao_regras": t.versao_regras,
    }


def _corrigir(
    con: sqlite3.Connection, vaga_id: int, cols: dict[str, Any], locais: tuple[Local, ...]
) -> tuple[dict[str, Any], tuple[Local, ...]]:
    """Aplica as correções da pessoa por cima das regras, da mais velha à mais nova (D11)."""
    for campo, valor in con.execute(
        "SELECT campo, valor_novo FROM correcao WHERE vaga_id = ? ORDER BY id", (vaga_id,)
    ):
        texto = (valor or "").strip()
        if campo in _ROTULOS:
            if texto in _ROTULOS[campo]:
                cols[campo] = texto
        elif campo == "uf":
            uf = texto.upper()
            if len(uf) == 2 and uf.isalpha():
                locais = tuple(replace(lo, uf=uf, pais="BR") for lo in locais) or (
                    Local(uf=uf, pais="BR"),
                )
        elif campo == "salario":
            beneficios = cols["beneficios"]
            if not texto:
                cols |= _salario(None, None)
            else:
                # "outro" primeiro: em pt/en o ler_salario cairia na moeda do idioma (DP4) antes
                # de herdar a que as regras leram ("6.000 por mês" numa vaga em USD fica USD)
                s = ler_salario(texto, None, "outro")
                if s is None and cols["sal_moeda"] is not None:
                    s = ler_salario(f"{cols['sal_moeda']} {texto}", None, "outro")
                if s is None:
                    s = ler_salario(texto, None, cols["idioma"])
                    if s is not None and cols["sal_moeda"] is not None:
                        # moeda que o leitor não reconhece no texto (NZD do salário estruturado):
                        # não cai na do idioma. shortcut: sem faixa para a moeda, não é plausível
                        # e o período deduzido segue a faixa da moeda do idioma; upgrade quando
                        # o leitor aceitar moeda por parâmetro
                        s = replace(s, moeda=cols["sal_moeda"], plausivel=False)
                if s is None:
                    continue
                cols |= _salario(replace(s, texto=texto), texto)
            if cols["beneficios"] == "[]":  # corrigir o valor não apaga VR/VA lidos da fonte
                cols["beneficios"] = beneficios
        # "fechada" vale em _retratar e no ciclo de vida; "outro" é só comentário.
    return cols, locais


def _sets(origem: str) -> str:
    """SET das colunas derivadas; `origem` é "excluded." (upsert) ou ":" (UPDATE nomeado)."""
    partes = [f"{c} = {origem}{c}" for c in _DERIVADAS]
    # listagem sem descrição não apaga a do detalhar (seção 7.6, critério 33a)
    partes.append(
        f"descricao_texto = CASE WHEN {origem}descricao_texto <> ''"
        f" THEN {origem}descricao_texto ELSE vaga.descricao_texto END"
    )
    # sem salário, o valor em reais antigo não vale mais (aplicar_cotacoes só olha vaga com moeda)
    for c in ("sal_mensal_min_brl", "sal_mensal_max_brl", "sal_cotacao_data"):
        partes.append(f"{c} = CASE WHEN {origem}sal_moeda IS NULL THEN NULL ELSE vaga.{c} END")
    return ", ".join(partes)


def _gravar_locais(con: sqlite3.Connection, vaga_id: int, locais: Iterable[Local]) -> None:
    con.execute("DELETE FROM local_vaga WHERE vaga_id = ?", (vaga_id,))
    con.executemany(
        "INSERT INTO local_vaga (vaga_id, cidade, uf, pais) VALUES (?, ?, ?, ?)",
        [(vaga_id, lo.cidade, lo.uf, lo.pais) for lo in dict.fromkeys(locais)],
    )


def _retratar(con: sqlite3.Connection, vaga_id: int, coletada: VagaColetada) -> None:
    t = tratar(coletada)
    cols, locais = _corrigir(con, vaga_id, _colunas(t), t.locais)
    con.execute(f"UPDATE vaga SET {_sets(':')} WHERE id = :id", cols | {"id": vaga_id})
    _gravar_locais(con, vaga_id, locais)
    corrigida = _fechada_corrigida(con, vaga_id)
    if corrigida is not None:  # a pessoa marcou fechada: vale já, sem esperar a próxima busca
        con.execute(
            "UPDATE vaga SET fechada_em = COALESCE(fechada_em, ?) WHERE id = ?",
            (corrigida, vaga_id),
        )
    elif not vaga_fechada(_ocorrencias(con, vaga_id)):  # desfazer também vale já (D18)
        con.execute("UPDATE vaga SET fechada_em = NULL WHERE id = ?", (vaga_id,))


def _com_descricao_antiga(v: VagaColetada, antiga: str | None) -> VagaColetada:
    """Descrição vazia da listagem herda a que já estava gravada (seção 7.6)."""
    if v.descricao or antiga is None:
        return v
    velha = VagaColetada.de_json(antiga)
    if not velha.descricao:
        return v
    return replace(v, descricao=velha.descricao, descricao_formato=velha.descricao_formato)


# ---------------------------------------------------------------- ciclo de vida


def _fechada_corrigida(con: sqlite3.Connection, vaga_id: int) -> str | None:
    linha = con.execute(
        "SELECT valor_novo, criada_em FROM correcao WHERE vaga_id = ? AND campo = 'fechada'"
        " ORDER BY id DESC LIMIT 1",
        (vaga_id,),
    ).fetchone()
    if linha is None or (linha[0] or "").strip().lower() in _NAO:
        return None
    return str(linha[1])


def _ocorrencias(con: sqlite3.Connection, vaga_id: int) -> list[OcorrenciaAberta]:
    return [
        OcorrenciaAberta(url_hash="", ultima_vista_em=datetime.min, sumiu_em=_data(s))
        for (s,) in con.execute("SELECT sumiu_em FROM ocorrencia WHERE vaga_id = ?", (vaga_id,))
    ]


def _fechar_ou_abrir(con: sqlite3.Connection, vaga_ids: Iterable[int], quando: str) -> int:
    """Fecha a vaga cujas ocorrências sumiram todas (ou que a pessoa marcou fechada) e reabre a
    que voltou. Devolve quantas fecharam agora."""
    fechadas = 0
    for vaga_id in set(vaga_ids):
        corrigida = _fechada_corrigida(con, vaga_id)
        fecha = corrigida is not None or vaga_fechada(_ocorrencias(con, vaga_id))
        atual = con.execute("SELECT fechada_em FROM vaga WHERE id = ?", (vaga_id,)).fetchone()[0]
        if fecha and atual is None:
            con.execute(
                "UPDATE vaga SET fechada_em = ? WHERE id = ?", (corrigida or quando, vaga_id)
            )
            fechadas += 1
        elif not fecha and atual is not None:
            con.execute("UPDATE vaga SET fechada_em = NULL WHERE id = ?", (vaga_id,))
    return fechadas


# ---------------------------------------------------------------- interfaces


def gravar_escopo(
    con: sqlite3.Connection,
    execucao_id: int,
    saida: SaidaEscopo,
    tratadas: Sequence[VagaTratada],
    agora: datetime,
) -> ResumoEscopo:
    """Grava saúde, validadores, vagas, ocorrências, locais, cache de detalhe e ciclo de vida do
    escopo numa transação só: um erro no meio desfaz tudo, validadores inclusive (DR-12)."""
    quando = _utc(agora)
    r = saida.resultado
    coletadas: dict[str, VagaColetada] = {}
    locais_brutos: dict[str, dict[str, None]] = {}  # hash da URL -> locais de todas as cópias
    for item in r.vagas:
        if isinstance(item, VagaColetada):
            coletadas.setdefault(item.url, item)
            locais_brutos.setdefault(hash_url(canonica(item.url)), {}).update(
                dict.fromkeys(item.locais)
            )
    novas = 0
    mexidas: set[int] = set()
    with _transacao(con):
        con.execute(
            "INSERT INTO saude (execucao_id, fonte, escopo, estado, vagas, pedidos, duracao_ms,"
            " motivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(execucao_id, fonte, escopo)"
            " DO UPDATE SET estado = excluded.estado, vagas = excluded.vagas,"
            " pedidos = excluded.pedidos, duracao_ms = excluded.duracao_ms,"
            " motivo = excluded.motivo",
            (
                execucao_id,
                saida.fonte,
                saida.escopo,
                r.estado,
                len(coletadas),
                r.pedidos,
                saida.duracao_ms,
                r.motivo,
            ),
        )
        if r.estado in _GUARDA_VALIDADORES:
            con.executemany(
                "INSERT INTO cache_http (url, etag, last_modified, visto_em) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(url) DO UPDATE SET etag = excluded.etag,"
                " last_modified = excluded.last_modified, visto_em = excluded.visto_em",
                [(u, v.etag, v.last_modified, quando) for u, v in saida.validadores.items()],
            )

        for url_hash, grupo in agrupar(tratadas).items():
            # mesma URL em várias cidades: uma vaga só, com a união dos locais
            v = replace(coletadas[grupo[0].url], locais=tuple(locais_brutos[url_hash]))
            linha = con.execute("SELECT id FROM vaga WHERE url_hash = ?", (url_hash,)).fetchone()
            vaga_id: int | None = None if linha is None else linha[0]
            antiga = None
            if vaga_id is not None:
                antiga = con.execute(
                    "SELECT coletada FROM ocorrencia"
                    " WHERE vaga_id = ? AND fonte = ? AND escopo = ?",
                    (vaga_id, saida.fonte, saida.escopo),
                ).fetchone()
            v = _com_descricao_antiga(v, None if antiga is None else antiga[0])
            t = grupo[0] if v == coletadas[grupo[0].url] else tratar(v)
            cols, locais = _colunas(t), t.locais
            if vaga_id is not None:
                cols, locais = _corrigir(con, vaga_id, cols, locais)
            else:
                novas += 1
            nomes = ", ".join(cols)
            vaga_id = con.execute(
                f"INSERT INTO vaga (url_hash, url, primeira_vista_em, ultima_vista_em, {nomes})"
                f" VALUES (:url_hash, :url, :agora, :agora, {', '.join(':' + c for c in cols)})"
                f" ON CONFLICT(url_hash) DO UPDATE SET ultima_vista_em = excluded.ultima_vista_em,"
                f" {_sets('excluded.')} RETURNING id",
                cols | {"url_hash": url_hash, "url": t.url_canonica, "agora": quando},
            ).fetchone()[0]
            con.execute(
                "INSERT INTO ocorrencia (vaga_id, fonte, escopo, id_externo, url, coletada,"
                " primeira_vista_em, ultima_vista_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(vaga_id, fonte, escopo) DO UPDATE SET"
                " id_externo = COALESCE(excluded.id_externo, ocorrencia.id_externo),"
                " url = excluded.url,"
                " coletada = excluded.coletada, ultima_vista_em = excluded.ultima_vista_em,"
                " sumiu_em = NULL",
                (
                    vaga_id,
                    saida.fonte,
                    saida.escopo,
                    v.id_externo,
                    v.url,
                    v.para_json(),
                    quando,
                    quando,
                ),
            )
            _gravar_locais(con, vaga_id, locais)
            mexidas.add(vaga_id)

        con.executemany(
            "INSERT INTO enriquecimento (url_hash, buscado_em, conteudo) VALUES (?, ?, '')"
            " ON CONFLICT(url_hash) DO UPDATE SET buscado_em = excluded.buscado_em,"
            " conteudo = excluded.conteudo",
            [(hash_url(canonica(u)), quando) for u in dict.fromkeys(saida.urls_sem_detalhe)],
        )

        # ciclo de vida do escopo (seção 10.2); URL vista sem vaga também conta (DR-70)
        vistas_sem_vaga = {hash_url(canonica(u)) for u in saida.urls_vistas}
        linhas = con.execute(
            "SELECT o.id, o.vaga_id, v.url_hash, o.ultima_vista_em, o.sumiu_em"
            " FROM ocorrencia o JOIN vaga v ON v.id = o.vaga_id"
            " WHERE o.fonte = ? AND o.escopo = ?",
            (saida.fonte, saida.escopo),
        ).fetchall()
        por_hash = {h: (oid, vid) for oid, vid, h, _, _ in linhas}
        abertas = [
            OcorrenciaAberta(
                url_hash=h,
                ultima_vista_em=datetime.fromisoformat(ultima),
                sumiu_em=_data(sumiu),
            )
            for _, _, h, ultima, sumiu in linhas
        ]
        vistas = {t.url_hash for t in tratadas} | vistas_sem_vaga
        mudancas = aplicar_ciclo(abertas, vistas, r.estado, agora.astimezone(UTC))
        sumidas = {a.url_hash for a in abertas if a.sumiu_em is not None}
        tocar = set(mudancas.tocar) | set(mudancas.reviram)
        if r.estado in ("ok", "parcial", "sem_mudanca"):  # nos outros estados nada muda (T14)
            tocar |= vistas_sem_vaga - sumidas
        for h in mudancas.sumiram:
            con.execute("UPDATE ocorrencia SET sumiu_em = ? WHERE id = ?", (quando, por_hash[h][0]))
        for h in tocar & por_hash.keys():
            con.execute(
                "UPDATE ocorrencia SET ultima_vista_em = ?, sumiu_em = NULL WHERE id = ?",
                (quando, por_hash[h][0]),
            )
        fechadas = _fechar_ou_abrir(con, mexidas | {vid for _, vid in por_hash.values()}, quando)
    return ResumoEscopo(novas=novas, fechadas=fechadas)


def fechar_escopos_extintos(
    con: sqlite3.Connection, fonte: str, escopos_vivos: Set[str], agora: datetime
) -> int:
    """Marca como sumidas as ocorrências abertas de escopos que a fonte não tem mais (empresa
    removida ou desligada) e fecha as vagas que ficaram sem ocorrência aberta. Devolve quantas
    ocorrências foram marcadas."""
    quando = _utc(agora)
    with _transacao(con):
        linhas = con.execute(
            "SELECT id, vaga_id, escopo FROM ocorrencia WHERE fonte = ? AND sumiu_em IS NULL",
            (fonte,),
        ).fetchall()
        extintas = [(oid, vid) for oid, vid, escopo in linhas if escopo not in escopos_vivos]
        con.executemany(
            "UPDATE ocorrencia SET sumiu_em = ? WHERE id = ?",
            [(quando, oid) for oid, _ in extintas],
        )
        _fechar_ou_abrir(con, (vid for _, vid in extintas), quando)
    return len(extintas)


def gravar_detalhe(con: sqlite3.Connection, ocorrencia_id: int, v: VagaColetada) -> None:
    """Grava o resultado do `detalhar` na ocorrência e trata a vaga de novo com ele."""
    with _transacao(con):
        linha = con.execute(
            "SELECT vaga_id, coletada FROM ocorrencia WHERE id = ?", (ocorrencia_id,)
        ).fetchone()
        if linha is None:
            raise LookupError(f"ocorrência {ocorrencia_id} não existe")
        vaga_id, antiga = linha
        v = _com_descricao_antiga(v, antiga)
        con.execute(
            "UPDATE ocorrencia SET coletada = ?, id_externo = COALESCE(?, id_externo) WHERE id = ?",
            (v.para_json(), v.id_externo, ocorrencia_id),
        )
        _retratar(con, vaga_id, v)


def reprocessar(con: sqlite3.Connection, versao: str) -> int:
    """Trata de novo, a partir de `ocorrencia.coletada`, as vagas abertas com regras de outra
    versão. Não mexe nas `_brl`: o passo 5 da execução chama `aplicar_cotacoes` depois."""
    with _transacao(con):
        ids = [
            vid
            for (vid,) in con.execute(
                "SELECT id FROM vaga WHERE fechada_em IS NULL AND versao_regras <> ?", (versao,)
            ).fetchall()
        ]
        feitas = 0
        for vaga_id in ids:
            linha = con.execute(_OCORRENCIA_ESCOLHIDA, (vaga_id,)).fetchone()
            if linha is not None:
                _retratar(con, vaga_id, VagaColetada.de_json(linha[0]))
                feitas += 1
    return feitas


def reprocessar_vaga(con: sqlite3.Connection, vaga_id: int, *, hoje: date) -> None:
    """Reprocessa uma vaga só, aplica a correção por cima das regras e recalcula `sal_*` e `_brl`.

    `aplicar_cotacoes` entra na transação aberta aqui (só abre uma quando não há) e faz o commit
    no fim: o reprocesso e as `_brl` saem juntos, ou nada sai (D11, D29).
    """
    with _transacao(con):
        if con.execute("SELECT 1 FROM vaga WHERE id = ?", (vaga_id,)).fetchone() is None:
            raise LookupError(f"vaga {vaga_id} não existe")
        linha = con.execute(_OCORRENCIA_ESCOLHIDA, (vaga_id,)).fetchone()
        if linha is not None:
            _retratar(con, vaga_id, VagaColetada.de_json(linha[0]))
        ligada = bool(ler_config(con, "conversao_moeda_ligada"))
        aplicar_cotacoes(con, conversao_ligada=ligada, hoje=hoje, vaga_id=vaga_id)
