import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from datetime import datetime, timedelta

import pytest

from apoio.relogio import RelogioFalso
from jobot.agenda.agendador import Estado, laco, o_que_roda
from jobot.banco.execucoes import Tipo

pytestmark = pytest.mark.anyio

AGORA = RelogioFalso().agora()
LIGADOS = {"busca": True, "descoberta": True, "paginas": True}
RECENTE = AGORA - timedelta(minutes=1)
INICIOU = AGORA - timedelta(hours=1)


def _roda(
    busca: datetime | None = RECENTE,
    descoberta: datetime | None = RECENTE,
    paginas: datetime | None = RECENTE,
    iniciou_em: datetime = INICIOU,
    interruptores: Mapping[str, bool] = LIGADOS,
    pagina_nova: bool = False,
) -> list[Tipo]:
    return o_que_roda(
        AGORA, busca, descoberta, paginas, iniciou_em, interruptores, pagina_nova=pagina_nova
    )


def test_busca_3_h_depois_do_inicio_da_ultima_completa() -> None:
    assert _roda(busca=AGORA - timedelta(hours=2, minutes=59)) == []
    assert _roda(busca=AGORA - timedelta(hours=3)) == ["busca"]


def test_perdida_roda_60_s_depois_de_iniciar() -> None:
    perdida = AGORA - timedelta(hours=5)
    assert _roda(busca=perdida, iniciou_em=AGORA - timedelta(seconds=59)) == []
    assert _roda(busca=perdida, iniciou_em=AGORA - timedelta(seconds=60)) == ["busca"]
    assert _roda(busca=None, iniciou_em=AGORA) == []
    assert _roda(busca=None, iniciou_em=AGORA - timedelta(seconds=60)) == ["busca"]


def test_descoberta_7_dias_e_paginas_24_h() -> None:
    assert _roda(descoberta=AGORA - timedelta(days=6, hours=23, minutes=59)) == []
    assert _roda(descoberta=AGORA - timedelta(days=7)) == ["descoberta"]
    assert _roda(paginas=AGORA - timedelta(hours=23, minutes=59)) == []
    assert _roda(paginas=AGORA - timedelta(hours=24)) == ["paginas"]
    assert _roda(None, None, None) == ["busca", "descoberta", "paginas"]


def test_pagina_nova_torna_as_paginas_devidas_sem_esperar_24_h() -> None:
    # T149: a execução de páginas foi há 1 h e há uma página nunca lida
    assert _roda(paginas=AGORA - timedelta(hours=1), pagina_nova=True) == ["paginas"]
    # todas lidas há 1 h: nada
    assert _roda(paginas=AGORA - timedelta(hours=1), pagina_nova=False) == []
    # a execução passou de 24 h: vence como sempre
    assert _roda(paginas=AGORA - timedelta(hours=25), pagina_nova=False) == ["paginas"]
    # só as páginas pedem: a busca e a descoberta seguem o seu ritmo
    assert _roda(pagina_nova=True) == ["paginas"]


def test_pagina_nova_com_paginas_desligadas_nao_roda() -> None:
    desligadas = {"busca": True, "descoberta": True, "paginas": False}
    assert _roda(pagina_nova=True, interruptores=desligadas) == []


def test_pagina_nova_nos_primeiros_60_s_nao_roda() -> None:
    assert _roda(pagina_nova=True, iniciou_em=AGORA - timedelta(seconds=59)) == []


def test_interruptor_desligado_nao_roda() -> None:
    desligados = {"busca": True, "descoberta": False, "paginas": False}
    assert _roda(None, None, None, interruptores=desligados) == ["busca"]
    assert _roda(None, None, None, interruptores={"busca": False}) == ["descoberta", "paginas"]


def test_inicio_no_futuro_conta_como_vencido() -> None:
    futuro = AGORA + timedelta(days=1)
    assert _roda(futuro, futuro, futuro) == ["busca", "descoberta", "paginas"]
    # o relógio voltou depois de o app subir: a espera de 60 s não segura para sempre
    assert _roda(futuro, None, None, iniciou_em=futuro) == ["busca", "descoberta", "paginas"]


class _Estado:
    def __init__(
        self,
        busca: datetime | None = RECENTE,
        descoberta: datetime | None = RECENTE,
        paginas: datetime | None = RECENTE,
    ) -> None:
        self.datas: dict[Tipo, datetime | None] = {
            "busca": busca,
            "descoberta": descoberta,
            "paginas": paginas,
        }
        self.chaves: dict[str, bool] = dict(LIGADOS)
        self.nova = False

    def ultimas(self) -> Mapping[Tipo, datetime | None]:
        return self.datas

    def interruptores(self) -> Mapping[str, bool]:
        return self.chaves

    def pagina_nova(self) -> bool:
        return self.nova


class _Relogio(RelogioFalso):
    """Dá algumas voltas no laço e para de vez na última `dormir`, sem esperar de verdade."""

    def __init__(self, voltas: int) -> None:
        super().__init__(AGORA)
        self.voltas = voltas
        self.acabou = asyncio.Event()

    async def dormir(self, s: float) -> None:
        for _ in range(5):
            await asyncio.sleep(0)  # deixa as tarefas criadas nesta volta andarem
        await super().dormir(s)
        if len(self.dormidas) >= self.voltas:
            self.acabou.set()
            await asyncio.Event().wait()


async def _girar(
    tarefas: Mapping[str, Callable[[], Awaitable[None]]], estado: Estado, relogio: _Relogio
) -> None:
    tarefa = asyncio.create_task(laco(tarefas, estado, relogio))
    espera = asyncio.create_task(relogio.acabou.wait())
    await asyncio.wait({tarefa, espera}, timeout=5, return_when=asyncio.FIRST_COMPLETED)
    espera.cancel()
    assert not tarefa.done(), f"o laço caiu: {tarefa.exception()!r}"
    assert relogio.acabou.is_set(), "o laço não completou as voltas em 5 s"
    tarefa.cancel()
    with suppress(asyncio.CancelledError):
        await tarefa


async def test_laco_acorda_a_cada_60_s_e_a_perdida_sai_60_s_depois() -> None:
    relogio = _Relogio(voltas=3)
    inicios: list[datetime] = []

    async def busca() -> None:
        inicios.append(relogio.agora())

    estado = _Estado(busca=AGORA - timedelta(hours=5))
    await _girar({"busca": busca}, estado, relogio)
    assert relogio.dormidas == [60, 60, 60]
    # sem gravar a última busca, ela segue vencida e roda de novo na volta seguinte
    assert inicios == [AGORA + timedelta(seconds=60), AGORA + timedelta(seconds=120)]


async def test_busca_nao_espera_descoberta() -> None:
    relogio = _Relogio(voltas=3)
    iniciadas: list[str] = []
    solta = asyncio.Event()

    async def descoberta() -> None:
        iniciadas.append("descoberta")
        await solta.wait()

    async def busca() -> None:
        iniciadas.append("busca")

    # descoberta vence já; a busca só vence em 90 s, com a descoberta ainda rodando
    estado = _Estado(busca=AGORA - timedelta(hours=3) + timedelta(seconds=90), descoberta=None)
    await _girar({"busca": busca, "descoberta": descoberta}, estado, relogio)
    assert iniciadas == ["descoberta", "busca"]
    assert not solta.is_set()


async def test_laco_roda_paginas_quando_ha_pagina_nova() -> None:
    relogio = _Relogio(voltas=2)
    inicios: list[datetime] = []

    async def paginas() -> None:
        inicios.append(relogio.agora())

    estado = _Estado()  # a última execução de páginas foi há 1 min
    estado.nova = True
    await _girar({"paginas": paginas}, estado, relogio)
    assert inicios == [AGORA + timedelta(seconds=60)]


async def test_mesma_tarefa_nao_roda_duas_vezes() -> None:
    relogio = _Relogio(voltas=4)
    chamadas = 0

    async def busca() -> None:
        nonlocal chamadas
        chamadas += 1
        await asyncio.Event().wait()

    await _girar({"busca": busca}, _Estado(busca=None), relogio)
    assert chamadas == 1


async def test_erro_numa_tarefa_nao_derruba_o_laco() -> None:
    relogio = _Relogio(voltas=3)
    chamadas = 0

    async def busca() -> None:
        nonlocal chamadas
        chamadas += 1
        raise RuntimeError("fonte caiu")

    await _girar({"busca": busca}, _Estado(busca=None), relogio)
    assert chamadas == 2


async def test_tipo_sem_tarefa_e_ignorado() -> None:
    relogio = _Relogio(voltas=2)
    iniciadas: list[str] = []

    async def busca() -> None:
        iniciadas.append("busca")

    await _girar({"busca": busca}, _Estado(busca=None, descoberta=None, paginas=None), relogio)
    assert iniciadas == ["busca"]


class _EstadoQueFalhaUmaVez(_Estado):
    def __init__(self) -> None:
        super().__init__(busca=None)
        self.falhou = False

    def ultimas(self) -> Mapping[Tipo, datetime | None]:
        if not self.falhou:
            self.falhou = True
            raise RuntimeError("database is locked")
        return super().ultimas()


async def test_erro_ao_ler_o_estado_nao_derruba_o_laco() -> None:
    relogio = _Relogio(voltas=3)
    inicios: list[datetime] = []

    async def busca() -> None:
        inicios.append(relogio.agora())
        await asyncio.Event().wait()

    await _girar({"busca": busca}, _EstadoQueFalhaUmaVez(), relogio)
    assert relogio.dormidas == [60, 60, 60]
    assert inicios == [AGORA + timedelta(seconds=60)]


async def test_laco_sem_travas_cria_as_suas() -> None:
    # caracterização (D55): quem chama sem `travas` segue com uma trava por tipo criada no laço
    relogio = _Relogio(voltas=4)
    chamadas = 0

    async def busca() -> None:
        nonlocal chamadas
        chamadas += 1
        await asyncio.Event().wait()

    await _girar({"busca": busca}, _Estado(busca=None), relogio)
    assert chamadas == 1


async def test_laco_usa_as_travas_de_fora() -> None:
    # D55: com a trava `busca` presa por fora (o "buscar agora"), o laço não dispara outra busca
    relogio = _Relogio(voltas=3)
    travas = {"busca": asyncio.Lock()}
    await travas["busca"].acquire()
    chamadas = 0

    async def busca() -> None:
        nonlocal chamadas
        chamadas += 1

    tarefa = asyncio.create_task(
        laco({"busca": busca}, _Estado(busca=None), relogio, travas=travas)
    )
    espera = asyncio.create_task(relogio.acabou.wait())
    await asyncio.wait({tarefa, espera}, timeout=5, return_when=asyncio.FIRST_COMPLETED)
    espera.cancel()
    assert not tarefa.done(), f"o laço caiu: {tarefa.exception()!r}"
    assert chamadas == 0
    travas["busca"].release()
    tarefa.cancel()
    with suppress(asyncio.CancelledError):
        await tarefa


async def test_travas_de_fora_com_tipo_sem_tarefa_nao_derrubam_o_laco() -> None:
    # a T48 passa travas dos três tipos e, por ora, só a tarefa de busca
    relogio = _Relogio(voltas=2)
    iniciadas: list[str] = []
    travas = {tipo: asyncio.Lock() for tipo in ("busca", "descoberta", "paginas")}

    async def busca() -> None:
        iniciadas.append("busca")

    estado = _Estado(busca=None, descoberta=None, paginas=None)
    tarefa = asyncio.create_task(laco({"busca": busca}, estado, relogio, travas=travas))
    espera = asyncio.create_task(relogio.acabou.wait())
    await asyncio.wait({tarefa, espera}, timeout=5, return_when=asyncio.FIRST_COMPLETED)
    espera.cancel()
    assert not tarefa.done(), f"o laço caiu: {tarefa.exception()!r}"
    assert iniciadas == ["busca"]
    assert not any(trava.locked() for trava in travas.values())  # tipo sem tarefa não prende
    tarefa.cancel()
    with suppress(asyncio.CancelledError):
        await tarefa
