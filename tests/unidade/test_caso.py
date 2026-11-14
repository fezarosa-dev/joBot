from jobot.sistema.caso import no_distrobox, nome_do_container, prefixo_host


def test_container_id_define_o_caso() -> None:
    env = {"CONTAINER_ID": "fedora-dev"}
    assert no_distrobox(env) is True
    assert nome_do_container(env) == "fedora-dev"
    assert prefixo_host(env) == ("distrobox-host-exec",)


def test_sem_container_id_e_sistema_direto() -> None:
    for env in ({}, {"CONTAINER_ID": ""}):
        assert no_distrobox(env) is False
        assert nome_do_container(env) is None
        assert prefixo_host(env) == ()
