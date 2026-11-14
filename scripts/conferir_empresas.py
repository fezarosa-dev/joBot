"""Confere ao vivo se cada empresa de `empresas.json` responde no seu ATS (T76, desenho 8.6).

Usa o cliente educado do projeto, no ritmo e com os limites de `fontes.json`, e o coletor da
fonte de cada empresa (`escopos` com as `parametros` dela, depois `coletar`). Não pede detalhe
e gasta no máximo `MAX_PEDIDOS` pedidos por empresa. Escreve um relatório curto na saída
padrão (empresa, fonte, estado, vagas); NÃO muda o `empresas.json`: quem decide o que sai da
lista, ou a nova `conferida_em`, é a pessoa que lê o relatório.

Uso: `uv run python scripts/conferir_empresas.py [fonte ...] > relatorio.txt`. Sem argumento,
confere todas as fontes; com argumentos, só as fontes citadas (ex.: `workday oracle_hcm`).
"""

import asyncio
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import version

from jobot.banco.cadastros import empresas_iniciais
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, LimiteEscopo
from jobot.nucleo.coletores.executor import PRAZO_ESCOPO_S, motivo_do_escopo
from jobot.nucleo.coletores.registro import descobrir
from jobot.nucleo.http import ClienteEducado, Validadores
from jobot.nucleo.modelo import Empresa
from jobot.nucleo.relogio import RelogioReal

MAX_PEDIDOS = 5  # por empresa; a conferência não lê o quadro inteiro
TERMOS = ("developer",)
PAISES = ("BR",)
RESPONDEM = frozenset({"ok", "sem_mudanca", "parcial"})


@dataclass(frozen=True)
class Linha:
    empresa: str
    fonte: str
    estado: str  # o do coletor, ou `sem_escopo` (parametros que o coletor não lê)
    vagas: int  # lidas nos pedidos feitos (`parcial` ou `no_limite` é um mínimo)
    motivo: str | None = None

    @property
    def responde(self) -> bool:
        # `saude.orcamento` é o teto desta conferência: o quadro já tinha respondido
        return self.estado in RESPONDEM or self.motivo == "saude.orcamento"


class _SemValidadores:
    """Sem banco: nenhum pedido é condicional."""

    def ler(self, url: str) -> Validadores | None:
        return None


async def _uma(cliente: ClienteEducado, coletor: Coletor, empresa: Empresa) -> Linha:
    def linha(estado: str, vagas: int = 0, motivo: str | None = None) -> Linha:
        return Linha(empresa.nome, empresa.fonte, estado, vagas, motivo)

    try:
        escopos = list(coletor.escopos(ContextoColeta((empresa,), TERMOS, PAISES)))
        if not escopos:
            return linha("sem_escopo")
        escopo = escopos[0]  # com um país só, cada empresa tem um escopo
        limite = coletor.por_escopo.get(escopo, LimiteEscopo())
        maximo = MAX_PEDIDOS
        if coletor.max_pedidos is not None:
            maximo = min(maximo, coletor.max_pedidos)
        http = cliente.escopo(
            espera_s=coletor.espera_s if limite.espera_s is None else limite.espera_s,
            condicional=False,
            max_pedidos=maximo,
            para_no_429=limite.para_no_429,
        )
        async with asyncio.timeout(PRAZO_ESCOPO_S):
            resultado = await coletor.coletar(escopo, http)
    except Exception as erro:  # uma empresa que cai não para as outras
        return linha("falhou", 0, motivo_do_escopo(erro))
    return linha(resultado.estado, len(resultado.vagas), resultado.motivo)


async def conferir(
    cliente: ClienteEducado,
    empresas: Sequence[Empresa],
    coletores: Mapping[str, Coletor],
    fontes: Sequence[str] | None = None,
) -> list[Linha]:
    """Uma linha por empresa, uma de cada vez; `fontes` restringe, `None` confere todas."""
    linhas = []
    for e in empresas:
        if fontes is None or e.fonte in fontes:
            linhas.append(await _uma(cliente, coletores[e.fonte], e))
    return linhas


def relatorio(linhas: Sequence[Linha]) -> str:
    cabecalho = ("empresa", "fonte", "estado", "motivo", "vagas")
    corpo = [(x.empresa, x.fonte, x.estado, x.motivo or "-", str(x.vagas)) for x in linhas]
    larguras = [max(len(c[i]) for c in [cabecalho, *corpo]) for i in range(4)]
    texto = [
        "  ".join(c[i].ljust(larguras[i]) for i in range(4)) + "  " + c[4]
        for c in [cabecalho, *corpo]
    ]
    texto.append(f"{sum(x.responde for x in linhas)} de {len(linhas)} respondem")
    return "\n".join(texto)


async def _principal(fontes: Sequence[str]) -> int:
    cliente = ClienteEducado(None, RelogioReal(), _SemValidadores(), version("jobot"))
    try:
        linhas = await conferir(cliente, empresas_iniciais(), descobrir(), fontes or None)
    finally:
        await cliente.fechar()
    print(relatorio(linhas))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_principal(sys.argv[1:])))
