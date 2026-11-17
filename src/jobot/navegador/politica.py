"""Política de navegação (D132.42): que endereços abrir e o que é página de login."""

from collections.abc import Callable, Sequence
from urllib.parse import urlsplit

from jobot.nucleo.http import host_local

Politica = Callable[[str], bool]


def _partes(url: str) -> tuple[str, str, str] | None:
    """`(esquema, hostname, caminho)` em minúsculas; `None` se a URL é torta ou não tem host.

    `hostname` já ignora `usuário:senha@` e a porta. Recusa `\\` e caracteres de controle:
    o Chromium lê `\\` como `/` e `urlsplit` não, então os dois veriam hosts diferentes."""
    if "\\" in url or any(ord(c) < 0x20 or ord(c) == 0x7F for c in url):
        return None
    try:
        partes = urlsplit(url)
        host = partes.hostname
        partes.port  # noqa: B018  # só levanta ValueError se a porta é torta
    except ValueError:  # colchete sem par, porta torta
        return None
    if not host:
        return None
    return partes.scheme.lower(), host.lower(), partes.path


def dentro_dos_hosts(url: str, hosts: Sequence[str]) -> bool:
    """O host da URL é um dos `hosts` (igualdade exata, nunca sufixo)."""
    partes = _partes(url)
    return partes is not None and partes[1] in {h.lower() for h in hosts}


def politica_de_producao(hosts: Sequence[str]) -> Politica:
    """Só `https` dos `hosts`; host local fica de fora mesmo que esteja em `hosts`."""

    def permitida(url: str) -> bool:
        partes = _partes(url)
        return (
            partes is not None
            and partes[0] == "https"
            and dentro_dos_hosts(url, hosts)
            and not host_local(partes[1])
        )

    return permitida


def casa_login(url: str, prefixos: Sequence[str]) -> bool:
    """`host + caminho` (sem query) começa com algum dos `prefixos`."""
    partes = _partes(url)
    return partes is not None and (partes[1] + partes[2]).startswith(tuple(prefixos))
