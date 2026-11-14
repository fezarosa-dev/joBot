import asyncio
from datetime import UTC, datetime
from typing import Protocol


class Relogio(Protocol):
    def agora(self) -> datetime: ...
    async def dormir(self, s: float) -> None: ...


class RelogioReal:
    def agora(self) -> datetime:
        return datetime.now(UTC)

    async def dormir(self, s: float) -> None:
        await asyncio.sleep(s)
