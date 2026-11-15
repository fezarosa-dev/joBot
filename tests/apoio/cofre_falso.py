"""Cofre de senhas falso: nenhum teste toca o cofre real de quem roda (keyring).

Guarda num `dict`. `falha` levanta em toda chamada; `engole=True` aceita o `set` e não guarda;
`recusa_apagar=True` aceita o `delete` e não apaga; `trava` faz toda chamada esperar o `Event`.
Apagar nome ausente levanta `PasswordDeleteError`, como o keyring real.
"""

import threading

from keyring.errors import PasswordDeleteError


class CofreFalso:
    def __init__(
        self,
        falha: Exception | None = None,
        engole: bool = False,
        recusa_apagar: bool = False,
        trava: threading.Event | None = None,
    ) -> None:
        self.falha = falha
        self.engole = engole
        self.recusa_apagar = recusa_apagar
        self.trava = trava
        self.guardado: dict[tuple[str, str], str] = {}

    def _antes(self) -> None:
        if self.trava is not None:
            self.trava.wait()
        if self.falha is not None:
            raise self.falha

    def get_password(self, service: str, username: str, /) -> str | None:
        self._antes()
        return self.guardado.get((service, username))

    def set_password(self, service: str, username: str, password: str, /) -> None:
        self._antes()
        if not self.engole:
            self.guardado[(service, username)] = password

    def delete_password(self, service: str, username: str, /) -> None:
        self._antes()
        if (service, username) not in self.guardado:
            raise PasswordDeleteError("não existe")
        if not self.recusa_apagar:
            del self.guardado[(service, username)]
