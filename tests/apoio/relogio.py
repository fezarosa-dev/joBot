from datetime import UTC, datetime, timedelta


class RelogioFalso:
    """Relógio de teste: `dormir` só avança a hora, sem esperar de verdade."""

    def __init__(self, inicio: datetime | None = None) -> None:
        self._agora = inicio or datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
        self.dormidas: list[float] = []

    def agora(self) -> datetime:
        return self._agora

    async def dormir(self, s: float) -> None:
        self.dormidas.append(s)
        self._agora += timedelta(seconds=s)
