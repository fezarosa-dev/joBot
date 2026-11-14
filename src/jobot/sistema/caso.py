from collections.abc import Mapping


def nome_do_container(env: Mapping[str, str]) -> str | None:
    return env.get("CONTAINER_ID") or None


def no_distrobox(env: Mapping[str, str]) -> bool:
    return nome_do_container(env) is not None


def prefixo_host(env: Mapping[str, str]) -> tuple[str, ...]:
    return ("distrobox-host-exec",) if no_distrobox(env) else ()
