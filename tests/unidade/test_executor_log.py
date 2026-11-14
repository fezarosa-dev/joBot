"""O executor registra o texto da exceção que para o escopo (T123, A36)."""

import logging
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import datetime

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import executor
from jobot.nucleo.coletores.base import (
    ContextoColeta,
    Item,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
)
from jobot.nucleo.coletores.executor import SaidaEscopo
from jobot.nucleo.http import (
    Bloqueio,
    ClienteEducado,
    HttpEducado,
    LimiteAtingido,
    Parou429,
    Validadores,
)
from jobot.nucleo.modelo import VagaColetada

pytestmark = pytest.mark.anyio

LOG = "jobot.nucleo.coletores.executor"
CTX = ContextoColeta(empresas=(), termos=("dev",), paises=("BR",))


class _SemHistorico:
    def ultimo_inicio_com_pedido(self, fonte: str, escopo: str | None) -> datetime | None:
        return None

    def tres_ultimas_ok_trouxeram_vagas(self, fonte: str, escopo: str) -> bool:
        return False

    def tem_ocorrencia_aberta(self, fonte: str, escopo: str) -> bool:
        return False

    def ultima_coleta(self, fonte: str, escopo: str) -> datetime | None:
        return None

    def urls_conhecidas(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        return set()

    def detalhe_recente(self, fonte: str, urls: Sequence[str]) -> Set[str]:
        return set()


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


@dataclass
class _Coletor:
    """Lista uma URL e para onde o teste mandar: no `coletar` ou no `detalhar`."""

    erro: Exception
    onde: str
    chave: str = "fonte-a"
    nome: str = "Falso"
    leva: str = "A"
    hosts: tuple[str, ...] = ()
    credito_obrigatorio: bool = False
    intervalo_min: int | None = None
    max_pedidos: int | None = None
    espera_s: float = 1.0
    por_escopo: Mapping[str, LimiteEscopo] = field(default_factory=dict)

    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        return ("e1",)

    async def coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo:
        if self.onde == "coletar":
            raise self.erro
        return ResultadoEscopo((UrlListada("https://a.exemplo/v/1"),), "ok", None, 1)

    async def detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None:
        raise self.erro

    async def resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]:
        return {}


async def _rodar(coletor: _Coletor) -> list[SaidaEscopo]:
    relogio = RelogioFalso()
    cliente = ClienteEducado(
        httpx.MockTransport(lambda p: httpx.Response(200)), relogio, _SemValidadores(), "9.9.9"
    )
    saidas: list[SaidaEscopo] = []

    async def guardar(saida: SaidaEscopo) -> None:
        saidas.append(saida)

    try:
        await executor.rodar(
            {coletor.chave: coletor},  # type: ignore[dict-item]
            CTX,
            cliente,
            _SemHistorico(),
            relogio,
            ligadas={coletor.chave},
            ao_terminar_escopo=guardar,
            max_detalhes_por_fonte=5,
        )
    finally:
        await cliente.fechar()
    return saidas


@pytest.mark.parametrize("onde", ["detalhar", "coletar"])
async def test_parou429_no_escopo_vai_para_o_log_com_retry_after(
    onde: str, caplog: pytest.LogCaptureFixture
) -> None:
    erro = Parou429("https://a.exemplo/v/1: HTTP 429 (Retry-After 120)")
    with caplog.at_level(logging.WARNING, logger=LOG):
        await _rodar(_Coletor(erro, onde))
    avisos = [r for r in caplog.records if r.name == LOG and r.levelno == logging.WARNING]
    assert len(avisos) == 1
    mensagem = avisos[0].getMessage()
    assert "fonte-a" in mensagem
    assert "e1" in mensagem
    assert "Retry-After 120" in mensagem


@pytest.mark.parametrize("erro", [LimiteAtingido("cota zerada"), Bloqueio("HTTP 403")])
@pytest.mark.parametrize("onde", ["detalhar", "coletar"])
async def test_limite_e_bloqueio_no_escopo_vao_para_o_log(
    erro: Exception, onde: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOG):
        await _rodar(_Coletor(erro, onde))
    avisos = [r.getMessage() for r in caplog.records if r.name == LOG]
    assert len(avisos) == 1
    assert "fonte-a" in avisos[0]
    assert "e1" in avisos[0]
    assert str(erro) in avisos[0]


async def test_parou429_que_escapa_do_coletar_da_parou_429() -> None:
    saidas = await _rodar(_Coletor(Parou429("429"), "coletar"))
    assert [(s.resultado.estado, s.resultado.motivo) for s in saidas] == [
        ("falhou", "saude.parou_429")
    ]


class _ColetorEscoposQuebrado(_Coletor):
    def escopos(self, ctx: ContextoColeta) -> Sequence[str]:
        raise self.erro


async def test_escopos_que_falha_por_429_vai_para_o_log_com_o_escopo_nomeado(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOG):
        saidas = await _rodar(_ColetorEscoposQuebrado(Parou429("429 Retry-After 9"), "coletar"))
    assert [s.resultado.motivo for s in saidas] == ["saude.parou_429"]
    mensagem = [r.getMessage() for r in caplog.records if r.name == LOG][0]
    assert "fonte-a/(escopos)" in mensagem
    assert "Retry-After 9" in mensagem
