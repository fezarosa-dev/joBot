"""O que a barra lateral da casca precisa saber do banco, em toda página (desenho 5.2; E4; T251)."""

from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from starlette.requests import Request

from jobot.banco.cadastros import PADROES, ler_config
from jobot.banco.conexao import abrir
from jobot.banco.leitura import ABAS
from jobot.painel.consultas import busca_efetiva


@dataclass(frozen=True)
class Lateral:
    destaques_ligados: bool
    sugeridas_pendentes: int
    busca_id: int | None
    contagens: Mapping[str, int] = field(default_factory=dict)  # vazio até a T253

    @property
    def abas(self) -> tuple[str, ...]:
        """Os itens da seção Vagas, na ordem das abas da tela (Destaques primeiro, se ligado)."""
        return (*(("destaques",) if self.destaques_ligados else ()), *ABAS)


def lateral(request: Request) -> Lateral:
    """Lido numa conexão curta e própria, como o tema; sem banco, não cria um arquivo vazio."""
    banco: Path = request.app.state.banco
    if not banco.exists():
        return Lateral(bool(PADROES["destaques_ligados"]), 0, None)
    with closing(abrir(banco)) as con:
        # `ler_config` cai no padrão com JSON estragado: o global está em toda página
        ligados = bool(ler_config(con, "destaques_ligados"))
        (pendentes,) = con.execute(
            "SELECT count(*) FROM empresa_sugerida WHERE estado = 'pendente'"
        ).fetchone()
        return Lateral(ligados, int(pendentes), busca_efetiva(con, None))
