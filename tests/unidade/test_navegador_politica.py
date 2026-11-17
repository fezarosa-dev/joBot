"""Política de produção (D132.42): só https, só os hosts do leitor, nunca host local."""

import pytest

from jobot.navegador.politica import casa_login, dentro_dos_hosts, politica_de_producao

HOSTS = ("www.site.com", "api.site.com")


def test_producao_recusa_http() -> None:
    assert not politica_de_producao(HOSTS)("http://www.site.com/vagas")


def test_producao_recusa_127_0_0_1() -> None:
    politica = politica_de_producao(("127.0.0.1", *HOSTS))
    assert not politica("https://127.0.0.1/vagas")
    assert not politica("http://127.0.0.1:8000/vagas")


def test_producao_recusa_host_fora() -> None:
    assert not politica_de_producao(HOSTS)("https://outro.com/vagas")


def test_producao_aceita_https_do_leitor() -> None:
    politica = politica_de_producao(HOSTS)
    assert politica("https://www.site.com/vagas?pagina=2")
    assert politica("HTTPS://API.SITE.COM/x")


def test_producao_recusa_host_parecido() -> None:
    politica = politica_de_producao(("site.com",))
    assert not politica("https://site.com.mal.io/")
    assert not politica("https://xsite.com/")
    assert not politica("https://mal.io/?u=site.com")
    assert not politica("https://site.com@mal.io/")  # o host real é o que vem depois do @
    assert politica("https://mal.io@site.com/")


@pytest.mark.parametrize(
    "url",
    [
        "https://mal.io\\@site.com/",  # o Chromium lê "\" como "/" e abre mal.io
        "https://site.com\\@mal.io/",
        "https://site.com/\\x",
        "https://site.com/\tx",
        "https://site.com/\x00",
        "https://site.com:abc/",
        "https://site.com:99999/",
    ],
)
def test_producao_recusa_o_que_o_chromium_le_diferente(url: str) -> None:
    assert not politica_de_producao(("site.com",))(url)
    assert not dentro_dos_hosts(url, ("site.com",))
    assert not casa_login(url, ("site.com/",))


@pytest.mark.parametrize(
    "url", ["", "https://", "https:///x", "nada", "https://[::1/x", "/relativa"]
)
def test_url_torta_ou_sem_host_e_recusada_sem_levantar(url: str) -> None:
    assert not politica_de_producao(("site.com",))(url)
    assert not dentro_dos_hosts(url, ("site.com",))
    assert not casa_login(url, ("site.com/login",))


def test_dentro_dos_hosts_nao_exige_https() -> None:
    assert dentro_dos_hosts("http://www.site.com/x", HOSTS)
    assert not dentro_dos_hosts("http://outro.com/x", HOSTS)


def test_casa_login_por_host_e_caminho() -> None:
    prefixos = ("www.site.com/login", "::1/sso")
    assert casa_login("https://www.site.com/login", prefixos)
    assert casa_login("https://www.site.com/login/entrar?x=1", prefixos)
    assert casa_login("http://[::1]:8000/sso/idp", prefixos)
    assert not casa_login("https://www.site.com/vagas", prefixos)
    assert not casa_login("https://outro.com/login", prefixos)
    assert not casa_login("https://www.site.com/vagas", ())
