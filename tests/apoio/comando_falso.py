"""O `jobot ferramentas ... ia-local` falso da tela Ferramentas (T417): entra por
`app.state.abrir_ia_local` e não roda processo nenhum."""

import asyncio
import json
import threading
from collections.abc import AsyncIterator, Sequence
from pathlib import Path


class ComandoFalso:
    """Escreve `antes`, espera o teste liberar (prazo de 5 s) e escreve `depois`; o `wait()`
    devolve `codigo`."""

    def __init__(self) -> None:
        self.antes: list[dict[str, object]] = []
        self.depois: list[dict[str, object]] = [{"fim": "pronto"}]
        self.codigo = 0
        self.liberar = threading.Event()

    @property
    def stdout(self) -> AsyncIterator[bytes]:
        return self._linhas()

    async def _linhas(self) -> AsyncIterator[bytes]:
        for linha in self.antes:
            yield json.dumps(linha).encode() + b"\n"
        for _ in range(500):
            if self.liberar.is_set():
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("o teste não liberou o comando")
        yield b"linha que nao e json\n"
        for linha in self.depois:
            yield json.dumps(linha).encode() + b"\n"

    async def wait(self) -> int:
        return self.codigo


class AbrirFalso:
    """O `abrir_ia_local`: anota os argumentos e a pasta e devolve o `comando` da vez."""

    def __init__(self) -> None:
        self.comando = ComandoFalso()
        self.comandos: list[tuple[list[str], Path]] = []

    async def __call__(self, argumentos: Sequence[str], dados: Path) -> ComandoFalso:
        self.comandos.append((list(argumentos), dados))
        return self.comando
