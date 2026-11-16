"""Janela falsa dos testes do processo filho (janela comum e instalador do navegador)."""

import asyncio


class JanelaFalsa:
    """Grava os sinais; o `wait()` volta quando `saiu` é solto (na hora, se `ja_saiu`).

    `erro` sai só no primeiro `wait()`; `sumiu` é o sinal que encontra o processo já morto
    (solta o `wait()` e levanta `ProcessLookupError`, como o `Process` do `asyncio`).
    """

    def __init__(
        self,
        *,
        ja_saiu: bool = False,
        sai_no: str = "kill",
        erro: Exception | None = None,
        codigo: int = 0,
        sumiu: str | None = None,
    ) -> None:
        self.sinais: list[str] = []
        self.saiu = asyncio.Event()
        self.sai_no = sai_no
        self.erro = erro
        self.codigo = codigo
        self.sumiu = sumiu
        if ja_saiu:
            self.saiu.set()

    async def wait(self) -> int:
        if self.erro is not None:
            erro, self.erro = self.erro, None
            raise erro
        await self.saiu.wait()
        return self.codigo

    def _sinal(self, nome: str) -> None:
        self.sinais.append(nome)
        if self.sumiu == nome:
            self.saiu.set()
            raise ProcessLookupError

    def terminate(self) -> None:
        self._sinal("terminate")
        if self.sai_no == "terminate":
            self.saiu.set()

    def kill(self) -> None:
        self._sinal("kill")
        self.saiu.set()
