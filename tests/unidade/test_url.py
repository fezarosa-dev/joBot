import pytest

from jobot.nucleo.url import canonica, hash_url


def test_canonica() -> None:
    assert canonica("HTTPS://Jobs.Example.COM/Vaga/42/?b=2&a=1#candidatar") == (
        "https://jobs.example.com/Vaga/42?a=1&b=2"
    )
    # rastreamento sai: utm_* por prefixo, gclid, fbclid, jobBoardSource (sem distinguir caixa)
    assert canonica(
        "https://x.com/v?utm_source=a&UTM_Medium=b&gclid=1&fbclid=2&jobBoardSource=x&id=7"
    ) == ("https://x.com/v?id=7")
    # parâmetro que identifica a vaga fica; porta padrão e barra da raiz saem
    assert canonica("http://x.com:80/") == "http://x.com"
    assert canonica("https://x.com:8443/v/?gh_jid=99") == "https://x.com:8443/v?gh_jid=99"
    # prefixos mc_ e pk_ saem; userinfo cai; IPv6 mantém colchetes; repetidos ordenam
    assert canonica("https://x.com/v?mc_cid=1&pk_campaign=2&id=7") == "https://x.com/v?id=7"
    assert canonica("https://u:p@X.com/v") == "https://x.com/v"
    assert canonica("http://[::1]:80/v") == "http://[::1]/v"
    assert canonica("https://x.com/v?a=2&a=1") == "https://x.com/v?a=1&a=2"


def test_rastreio_de_fontes_sai() -> None:
    # gh_src acompanha gh_jid (Greenhouse): só gh_jid identifica a vaga
    assert canonica("https://x.com/v?gh_src=x&gh_jid=9") == "https://x.com/v?gh_jid=9"
    assert canonica("https://x.com/v?wbraid=1&gbraid=2&ttclid=3&_gl=4&_ga=5&id=7") == (
        "https://x.com/v?id=7"
    )


def test_mesma_vaga_mesmo_hash() -> None:
    a = canonica("https://Jobs.example.com/v/1/?utm_source=x&id=3&z=9#topo")
    b = canonica("https://jobs.example.com/v/1?z=9&id=3&gclid=abc")
    assert a == b
    assert hash_url(a) == hash_url(b)
    assert len(hash_url(a)) == 64


def test_urls_diferentes_hashes_diferentes() -> None:
    a = canonica("https://x.com/v/1?id=1")
    b = canonica("https://x.com/v/1?id=2")
    c = canonica("https://x.com/v/2?id=1")
    assert len({hash_url(a), hash_url(b), hash_url(c)}) == 3


@pytest.mark.parametrize(
    "url",
    [
        "ftp://x.com/v",
        "javascript:alert(1)",
        "mailto:a@b.com",
        "x.com/v",
        "https://",
        "",
        "https://x.com:abc/",
    ],
)
def test_esquema_invalido_levanta(url: str) -> None:
    with pytest.raises(ValueError):
        canonica(url)
