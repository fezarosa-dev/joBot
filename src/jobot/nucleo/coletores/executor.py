"""Executor de coleta (desenho 8.1, 8.3, 10.6 e 12.4; DR-09, DR-10, DR-12, DR-52, DR-64, DR-70).

Roda os escopos das fontes ligadas e entrega cada um, já terminado, ao `ao_terminar_escopo`.
Qualquer exceção do coletor vira "falhou"; nada da coleta sobe. Sobem só os erros do banco:
o de quem recebe a saída (o `ao_terminar_escopo`) e o de qualquer chamada ao `Historico`, num
`ExceptionGroup`, depois de cancelar as outras fontes.

Erro no `detalhar` não muda o estado (a lista veio inteira), mas vai para o motivo quando o
escopo não tem outro (o de parada vence o `sem_detalhe_n`). Bloqueio, LimiteAtingido,
OrcamentoGasto e Parou429 param os detalhes da fonte inteira nesta execução; outro erro pula
só aquela URL.

Motivo com parâmetro vai como `chave:valor` (`saude.excecao:TimeoutError`,
`saude.sem_detalhe_n:3`); o parâmetro é o único da chave (`tipo` ou `n`).

Exceção que escapa de `coletar` ou `escopos` vira `saude.excecao:<Tipo>`, menos RespostaGrande
(`saude.resposta_grande`) e ErroDeRede (`saude.erro_de_rede`), que têm motivo próprio.
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, Sequence, Set
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from jobot.nucleo.coletores.base import (
    Coletor,
    ContextoColeta,
    Estado,
    LimiteEscopo,
    ResultadoEscopo,
    UrlListada,
)
from jobot.nucleo.http import (
    Bloqueio,
    ClienteEducado,
    ErroDeRede,
    HttpDoEscopo,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    Resposta,
    RespostaGrande,
    Validadores,
)
from jobot.nucleo.modelo import VagaColetada
from jobot.nucleo.relogio import Relogio

PRAZO_ESCOPO_S = 300.0  # 5 minutos por escopo
MAX_FONTES_JUNTAS = 4  # até 4 hosts ao mesmo tempo; no mesmo host o ClienteEducado enfileira
JANELA_URL_NOVA = timedelta(days=30)
_SEM_DATA = datetime.min.replace(tzinfo=UTC)
_SEM_DETALHE = "saude.sem_detalhe_n:"
# Depois destes, nenhum detalhe a mais da fonte passa nesta execução.
_MOTIVO_DA_PARADA: dict[type[Exception], str] = {
    Bloqueio: "saude.bloqueio",
    LimiteAtingido: "saude.limite_atingido",
    OrcamentoGasto: "saude.orcamento",
    Parou429: "saude.parou_429",
}
_PARA_DETALHES = tuple(_MOTIVO_DA_PARADA)


class Historico(Protocol):
    def ultimo_inicio_com_pedido(self, fonte: str, escopo: str | None) -> datetime | None: ...
    def tres_ultimas_ok_trouxeram_vagas(self, fonte: str, escopo: str) -> bool: ...
    def tem_ocorrencia_aberta(self, fonte: str, escopo: str) -> bool: ...
    def ultima_coleta(self, fonte: str, escopo: str) -> datetime | None: ...
    def urls_conhecidas(self, fonte: str, urls: Sequence[str]) -> Set[str]: ...
    def detalhe_recente(self, fonte: str, urls: Sequence[str]) -> Set[str]: ...


@dataclass(frozen=True)
class SaidaEscopo:
    fonte: str
    escopo: str
    resultado: ResultadoEscopo  # `vagas` só com VagaColetada
    duracao_ms: int
    validadores: Mapping[str, Validadores]
    urls_vistas: tuple[str, ...] = ()
    urls_sem_detalhe: tuple[str, ...] = ()
    detalhes: int = 0


async def rodar(
    coletores: Mapping[str, Coletor],
    ctx: ContextoColeta,
    cliente: ClienteEducado,
    historico: Historico,
    relogio: Relogio,
    *,
    ligadas: Set[str],
    ao_terminar_escopo: Callable[[SaidaEscopo], Awaitable[None]],
    max_detalhes_por_fonte: int = 50,
) -> None:
    vagas = asyncio.Semaphore(MAX_FONTES_JUNTAS)

    async def uma(coletor: Coletor) -> None:
        async with vagas:
            await _Fonte(
                coletor, cliente, historico, relogio, ao_terminar_escopo, max_detalhes_por_fonte
            ).rodar(ctx)

    # TaskGroup: cancelar `rodar` ou um erro do ao_terminar_escopo cancela e espera todas.
    async with asyncio.TaskGroup() as grupo:
        for chave, coletor in coletores.items():
            if chave in ligadas:
                grupo.create_task(uma(coletor))


def estado_da_fonte(estados: Sequence[str]) -> str:
    """Estado da fonte pelos escopos (desenho 8.3): "no_limite" só conta se nenhum rodou."""
    rodaram = [e for e in estados if e != "no_limite"]
    if not rodaram:
        return "no_limite" if estados else "ok"
    if all(e in ("ok", "sem_mudanca") for e in rodaram):
        return "ok"
    if all(e == "falhou" for e in rodaram):
        return "falhou"
    return "parcial"


def _vencido(ultimo: datetime | None, intervalo_min: int | None, agora: datetime) -> bool:
    if intervalo_min is None or ultimo is None or ultimo > agora:  # futuro: relógio voltou (RF4)
        return True
    return agora - ultimo >= timedelta(minutes=intervalo_min)


def _motivo_do_detalhe(erro: Exception) -> str:
    for tipo, chave in _MOTIVO_DA_PARADA.items():
        if isinstance(erro, tipo):
            return chave
    if isinstance(erro, ErroDeRede):
        return "saude.erro_de_rede"
    if isinstance(erro, RespostaGrande):
        return "saude.resposta_grande"
    return f"saude.excecao:{type(erro).__name__}"


def _motivo_do_escopo(erro: Exception) -> str:
    """Exceção que escapou de `coletar` ou `escopos`: só estas duas têm motivo próprio."""
    if isinstance(erro, RespostaGrande):
        return "saude.resposta_grande"
    if isinstance(erro, ErroDeRede):
        return "saude.erro_de_rede"
    return f"saude.excecao:{type(erro).__name__}"


def _n_sem_detalhe(motivo: str | None) -> int | None:
    """O `n` de um motivo `saude.sem_detalhe_n:<n>` (o molde conta os itens que descartou)."""
    if motivo is None or not motivo.startswith(_SEM_DETALHE):
        return None
    return int(motivo.removeprefix(_SEM_DETALHE))


class _ErroDoHistorico(Exception):
    """Erro do `Historico` dentro do try do escopo: sobe com o erro original, não vira "falhou"."""

    def __init__(self, erro: Exception) -> None:
        self.erro = erro


def _no_limite(motivo: str) -> ResultadoEscopo:
    return ResultadoEscopo((), "no_limite", motivo, 0)


class _Espia:
    """`HttpEducado` do escopo que anota o status das respostas condicionais (DR-12)."""

    def __init__(self, http: HttpDoEscopo) -> None:
        self._http = http
        self.status: set[int] = set()

    @property
    def pedidos(self) -> int:
        return self._http.pedidos

    @property
    def validadores_novos(self) -> Mapping[str, Validadores]:
        return self._http.validadores_novos

    def misturou(self) -> bool:
        return 304 in self.status and any(200 <= s < 300 for s in self.status)

    async def pedir(
        self,
        metodo: Literal["GET", "POST"],
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        cabecalhos: Mapping[str, str] | None = None,
        corpo_json: object | None = None,
        condicional: bool = False,
        teto_bytes: int | None = None,
    ) -> Resposta:
        resposta = await self._http.pedir(
            metodo,
            url,
            params=params,
            cabecalhos=cabecalhos,
            corpo_json=corpo_json,
            condicional=condicional,
            teto_bytes=teto_bytes,
        )
        if condicional:
            self.status.add(resposta.status)
        return resposta

    def ler_em_fluxo(
        self, url: str, *, teto_bytes: int, cabecalhos: Mapping[str, str] | None = None
    ) -> AsyncGenerator[bytes]:
        return self._http.ler_em_fluxo(url, teto_bytes=teto_bytes, cabecalhos=cabecalhos)


class _Fonte:
    """Os escopos de uma fonte, um de cada vez: orçamento e detalhes valem para a fonte."""

    def __init__(
        self,
        coletor: Coletor,
        cliente: ClienteEducado,
        historico: Historico,
        relogio: Relogio,
        ao_terminar: Callable[[SaidaEscopo], Awaitable[None]],
        max_detalhes: int,
    ) -> None:
        self.c = coletor
        self.cliente = cliente
        self.historico = historico
        self.relogio = relogio
        self.ao_terminar = ao_terminar
        self.pedidos_livres = coletor.max_pedidos
        self.detalhes_livres = max(max_detalhes, 0)

    async def _parado(self, escopo: str, resultado: ResultadoEscopo) -> None:
        await self.ao_terminar(SaidaEscopo(self.c.chave, escopo, resultado, 0, {}))

    async def rodar(self, ctx: ContextoColeta) -> None:
        chave = self.c.chave
        empresas = tuple(e for e in ctx.empresas if e.fonte == chave)
        try:
            escopos = list(self.c.escopos(replace(ctx, empresas=empresas)))
        except Exception as erro:
            falhou = ResultadoEscopo((), "falhou", _motivo_do_escopo(erro), 0)
            await self._parado("", falhou)
            return
        if self.c.max_pedidos is not None:  # DR-52: os coletados há mais tempo primeiro
            escopos.sort(key=lambda e: self.historico.ultima_coleta(chave, e) or _SEM_DATA)
        agora = self.relogio.agora()
        fonte_vencida = _vencido(
            self.historico.ultimo_inicio_com_pedido(chave, None), self.c.intervalo_min, agora
        )
        for escopo in escopos:
            limite = self.c.por_escopo.get(escopo, LimiteEscopo())
            vencido = fonte_vencida
            if limite.intervalo_min is not None:  # o do escopo substitui o da fonte (DR-64)
                ultimo = self.historico.ultimo_inicio_com_pedido(chave, escopo)
                vencido = _vencido(ultimo, limite.intervalo_min, agora)
            if not vencido:
                await self._parado(escopo, _no_limite("saude.intervalo"))
            elif self.pedidos_livres is not None and self.pedidos_livres <= 0:
                await self._parado(escopo, _no_limite("saude.orcamento"))
            else:
                await self._escopo(escopo, limite)

    def _abrir(self, limite: LimiteEscopo, condicional: bool, gastos: int) -> _Espia:
        livres = None if self.pedidos_livres is None else self.pedidos_livres - gastos
        espera = self.c.espera_s if limite.espera_s is None else limite.espera_s
        return _Espia(
            self.cliente.escopo(
                espera_s=espera,
                condicional=condicional,
                max_pedidos=livres,
                para_no_429=limite.para_no_429,
            )
        )

    async def _escopo(self, escopo: str, limite: LimiteEscopo) -> None:
        chave = self.c.chave
        condicional = self.historico.tem_ocorrencia_aberta(chave, escopo)
        inicio = self.relogio.agora()
        gastos = 0
        http = self._abrir(limite, condicional, gastos)
        vistas: tuple[str, ...] = ()
        sem_detalhe: list[str] = []
        detalhes = 0
        erro_detalhe: str | None = None
        parou = False
        try:
            async with asyncio.timeout(PRAZO_ESCOPO_S):
                resultado = await self.c.coletar(escopo, http)
                if condicional and http.misturou() and resultado.estado == "parcial":
                    gastos += http.pedidos  # DR-12: 304 e 200 juntos, refaz sem condicional
                    http = self._abrir(limite, False, gastos)
                    resultado = await self.c.coletar(escopo, http)
                listadas = len(resultado.vagas)
                vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
                urls = [v for v in resultado.vagas if isinstance(v, UrlListada)]
                if urls:
                    try:
                        vistas, novas = self._separar(urls)
                    except Exception as erro:
                        raise _ErroDoHistorico(erro) from erro
                    for item in novas[: self.detalhes_livres]:
                        detalhes += 1
                        try:
                            vaga = await self.c.detalhar(item, http)
                        except _PARA_DETALHES as erro:
                            erro_detalhe, parou = _motivo_do_detalhe(erro), True
                            break
                        except Exception as erro:  # só esta URL; volta na próxima execução
                            erro_detalhe = erro_detalhe or _motivo_do_detalhe(erro)
                            continue
                        if vaga is None:
                            sem_detalhe.append(item.url)
                        else:
                            vagas.append(vaga)
            estado: Estado = resultado.estado
            motivo = resultado.motivo
            # shortcut: relógio de parede; um pulo para frente (NTP, suspensão) marca
            # tempo_esgotado num escopo que terminou. Trocar por relógio monotônico no Relogio.
            if self.relogio.agora() - inicio > timedelta(seconds=PRAZO_ESCOPO_S):
                raise TimeoutError  # o prazo pelo relógio injetado
            if estado == "ok" and listadas == 0:
                try:
                    tres_com_vagas = self.historico.tres_ultimas_ok_trouxeram_vagas(chave, escopo)
                except Exception as erro:
                    raise _ErroDoHistorico(erro) from erro
                if tres_com_vagas:
                    estado, motivo = "parcial", "saude.zero_inesperado"  # DR-10
            n_antes = _n_sem_detalhe(motivo)
            if motivo is None or n_antes is not None:
                if erro_detalhe is not None:
                    motivo = erro_detalhe
                elif sem_detalhe:
                    motivo = f"{_SEM_DETALHE}{(n_antes or 0) + len(sem_detalhe)}"
            final = replace(
                resultado,
                vagas=tuple(vagas),
                estado=estado,
                motivo=motivo,
                pedidos=gastos + http.pedidos,
            )
        except _ErroDoHistorico as erro:
            raise erro.erro from None
        except TimeoutError:
            final = ResultadoEscopo((), "falhou", "saude.tempo_esgotado", gastos + http.pedidos)
            vistas, sem_detalhe = (), []
        except Exception as erro:
            final = ResultadoEscopo((), "falhou", _motivo_do_escopo(erro), gastos + http.pedidos)
            vistas, sem_detalhe = (), []
        self.detalhes_livres = 0 if parou else self.detalhes_livres - detalhes
        if self.pedidos_livres is not None:
            self.pedidos_livres -= final.pedidos
        duracao = max((self.relogio.agora() - inicio) // timedelta(milliseconds=1), 0)
        saida = SaidaEscopo(
            chave,
            escopo,
            final,
            duracao,
            dict(http.validadores_novos),
            vistas,
            tuple(sem_detalhe),
            detalhes,
        )
        await self.ao_terminar(saida)

    def _separar(self, urls: Sequence[UrlListada]) -> tuple[tuple[str, ...], list[UrlListada]]:
        """URL conhecida conta como vista; das novas, as que vão ao `detalhar`, em ordem (DR-70)."""
        chave = self.c.chave
        unicas: dict[str, UrlListada] = {}
        for u in urls:
            unicas.setdefault(u.url, u)
        conhecidas = self.historico.urls_conhecidas(chave, list(unicas))
        corte = self.relogio.agora() - JANELA_URL_NOVA
        novas = [
            u
            for u in unicas.values()
            if u.url not in conhecidas and (u.atualizada_em is None or u.atualizada_em >= corte)
        ]
        recentes = self.historico.detalhe_recente(chave, [u.url for u in novas])
        novas = [u for u in novas if u.url not in recentes]
        novas.sort(key=lambda u: u.atualizada_em or _SEM_DATA, reverse=True)  # sem data por último
        return tuple(u for u in unicas if u in conhecidas), novas
