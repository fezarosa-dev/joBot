"""O log do enriquecimento traz o texto do erro que parou os detalhes (T123, A36)."""

import asyncio
import logging
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.agenda.execucao import executar_busca
from jobot.banco.conexao import abrir
from jobot.banco.migrar import migrar
from jobot.nucleo.coletores.base import ContextoColeta, Item, LimiteEscopo, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, LimiteAtingido, Parou429, Validadores
from jobot.nucleo.modelo import VagaColetada

pytestmark = pytest.mark.anyio

AGORA = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)
FONTE = "falsa"


class _RelogioParado(RelogioFalso):
    """O batimento dorme para sempre; só a hora do teste importa."""

    async def dormir(self, s: float) -> None:
        await asyncio.Event().wait()


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


@dataclass
class _Coletor:
    erro: Exception
    chave: str = FONTE
    nome: str = "Falsa"
    leva: str = "A"
    hosts: tuple[str, ...] = ()
    credito_obrigatorio: bool = False
    intervalo_min: int | None = None
    max_pedidos: int | None = None
    espera_s: float = 1.0
    por_escopo: Mapping[str, LimiteEscopo] = field(default_factory=dict)

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return ("",)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        vaga = VagaColetada(
            fonte=FONTE,
            escopo="",
            url="https://falsa.exemplo.test/vagas/1",
            titulo="Desenvolvedor Python",
            empresa="Acme",
            descricao_formato="texto",
            descricao="",
        )
        return ResultadoEscopo((vaga,), "ok", None, 0)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        raise self.erro

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        return {}


@pytest.fixture
def con(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    caminho = tmp_path / "jobot.db"
    c = abrir(caminho)
    migrar(c, caminho)
    c.execute("INSERT INTO fonte (chave, leva, ligada) VALUES (?, 'A', 1)", (FONTE,))
    c.commit()
    yield c
    c.close()


@pytest.mark.parametrize(
    ("erro", "tipo", "texto"),
    [
        (
            LimiteAtingido("https://falsa.exemplo.test/vagas/1: HTTP 429 com a cota zerada"),
            "LimiteAtingido",
            "com a cota zerada",
        ),
        (
            Parou429("https://falsa.exemplo.test/vagas/1: HTTP 429 Retry-After 120"),
            "Parou429",
            "Retry-After 120",
        ),
    ],
)
async def test_detalhe_parado_registra_o_texto_do_erro(
    con: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
    erro: Exception,
    tipo: str,
    texto: str,
) -> None:
    cliente = ClienteEducado(
        httpx.MockTransport(lambda p: httpx.Response(404)),
        RelogioFalso(AGORA),
        _SemValidadores(),
        "9.9.9",
        resolver=_sem_dns,
    )
    try:
        with caplog.at_level(logging.WARNING, logger="jobot.agenda.execucao"):
            await executar_busca(
                con,
                cliente,
                _RelogioParado(AGORA),
                "agenda",
                coletores={FONTE: _Coletor(erro)},  # type: ignore[dict-item]
            )
    finally:
        await cliente.fechar()
    avisos = [r.getMessage() for r in caplog.records if "parados" in r.getMessage()]
    assert len(avisos) == 1
    assert tipo in avisos[0]
    assert texto in avisos[0]
