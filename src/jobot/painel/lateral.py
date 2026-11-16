"""O que a barra lateral da casca precisa saber do banco, em toda página (desenho 5.2; E4; T251)."""

import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from starlette.requests import Request

from jobot.banco.cadastros import PADROES, ler_config
from jobot.banco.conexao import abrir
from jobot.banco.leitura import ABAS, contar_abas
from jobot.painel.consultas import (
    MAX_ID,
    busca_efetiva,
    ids_destaques,
    inteiro_da_url,
    relogio_do_painel,
)


@dataclass(frozen=True)
class Lateral:
    destaques_ligados: bool
    sugeridas_pendentes: int
    busca_id: int | None
    contagens: Mapping[str, int] = field(default_factory=dict)  # por aba, mais "destaques"

    @property
    def abas(self) -> tuple[str, ...]:
        """Os itens da seção Vagas, na ordem das abas da tela (Destaques primeiro, se ligado)."""
        return (*(("destaques",) if self.destaques_ligados else ()), *ABAS)


def ler_lateral(con: sqlite3.Connection, agora: datetime, pedida: int | None) -> Lateral:
    """A lateral numa conexão que já existe; `pedida` é a busca da URL (vence a escolhida)."""
    # `ler_config` cai no padrão com JSON estragado: o global está em toda página
    ligados = bool(ler_config(con, "destaques_ligados"))
    (pendentes,) = con.execute(
        "SELECT count(*) FROM empresa_sugerida WHERE estado = 'pendente'"
    ).fetchone()
    busca = busca_efetiva(con, pedida)
    contagens = dict(contar_abas(con, busca, agora))
    if ligados:
        contagens["destaques"] = len(ids_destaques(con, busca, agora))
    return Lateral(ligados, int(pendentes), busca, contagens)


def lateral(request: Request) -> Lateral:
    """Lido numa conexão curta e própria, como o tema; sem banco, não cria um arquivo vazio."""
    banco: Path = request.app.state.banco
    if not banco.exists():
        return Lateral(bool(PADROES["destaques_ligados"]), 0, None)
    pedida = inteiro_da_url(request.query_params.get("busca"), MAX_ID)
    with closing(abrir(banco)) as con:
        return ler_lateral(con, relogio_do_painel(request).agora(), pedida)


def grupos_configuracoes(request: Request) -> tuple[tuple[str, str], ...]:
    """Os grupos de Configurações da página, (slug, chave do nome), para a paleta (T265)."""
    # import tardio: rotas.configuracoes importa a seguranca, que importa os globais e esta
    from jobot.painel.rotas.configuracoes import grupos_visiveis, leitores_do_painel

    return tuple(
        (g, "configuracoes.grupo." + g.replace("-", "_"))
        for g in grupos_visiveis(leitores_do_painel(request))
    )
