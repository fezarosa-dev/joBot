import logging
from collections.abc import AsyncIterator, Sequence
from typing import cast

import pytest

from jobot.nucleo.coletores.base import Item, juntar_paginas
from jobot.nucleo.http import Bloqueio, ErroDeRede, HttpEducado, LimiteAtingido, Parou429

pytestmark = pytest.mark.anyio


class HttpFalso:
    pedidos = 2


async def _paginas(erro: Exception) -> AsyncIterator[Sequence[Item]]:
    yield ()
    raise erro


@pytest.mark.parametrize(
    ("erro", "motivo"),
    [
        (Parou429("https://a.example/p: HTTP 429 (Retry-After 120)"), "saude.parou_429"),
        (LimiteAtingido("https://a.example/p: Retry-After 3600 s acima do teto"), None),
        (Bloqueio("https://a.example/p: HTTP 403"), "saude.bloqueio"),
        (ErroDeRede("https://a.example/p: redirecionamento recusado: x"), "saude.erro_de_rede"),
    ],
)
async def test_juntar_paginas_registra_o_texto_do_erro(
    erro: Exception, motivo: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    # o estado guarda só a chave `saude.*`: o detalhe (Retry-After, URL) só fica no log
    with caplog.at_level(logging.WARNING, logger="jobot.nucleo.coletores.base"):
        resultado = await juntar_paginas(cast(HttpEducado, HttpFalso()), _paginas(erro))
    assert resultado.motivo == (motivo or "saude.limite_atingido")
    registros = [r for r in caplog.records if r.name == "jobot.nucleo.coletores.base"]
    assert len(registros) == 1
    registro = registros[0]
    assert str(erro) in registro.getMessage()
    assert type(erro).__name__ in registro.getMessage()
    assert registro.levelno == logging.WARNING


async def test_juntar_paginas_sem_erro_nao_registra(caplog: pytest.LogCaptureFixture) -> None:
    async def paginas() -> AsyncIterator[Sequence[Item]]:
        yield ()

    with caplog.at_level(logging.DEBUG, logger="jobot.nucleo.coletores.base"):
        resultado = await juntar_paginas(cast(HttpEducado, HttpFalso()), paginas())
    assert (resultado.estado, resultado.pedidos) == ("ok", 2)
    assert [r for r in caplog.records if r.name == "jobot.nucleo.coletores.base"] == []
