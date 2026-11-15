"""Uma navegação com as checagens, contra o site falso (T212; desenho A7 e seção 8)."""

import logging
from collections.abc import Iterator, Sequence
from urllib.parse import urlsplit

import pytest
from playwright.async_api import BrowserContext, Page

from apoio.site_falso import LeitorFalso, RelogioDoNavegador, SiteFalso
from jobot.navegador.limites import ESPERA_CLOUDFLARE_S, MAX_RESPOSTAS
from jobot.navegador.pagina import Recusada, ouvir_respostas, visitar
from jobot.navegador.politica import Politica
from jobot.nucleo.http import ESPERAS_LIMITE, MAX_RETRY_AFTER_S
from jobot.nucleo.leitores.base import Captura, EscopoLogado, RespostaCapturada

pytestmark = [pytest.mark.tela, pytest.mark.anyio]

ESCOPO = EscopoLogado("python", "")


def _caminho(url: str) -> str:
    return urlsplit(url).path


def _hosts(respostas: Sequence[RespostaCapturada]) -> set[str | None]:
    return {urlsplit(r.url).hostname for r in respostas}


@pytest.fixture(autouse=True)
def _so_leitura(site: SiteFalso) -> Iterator[None]:
    """Nenhuma navegação do joBot envia formulário nem muda campo (D132.11)."""
    yield
    assert (site.posts, site.campos_mudados) == (0, 0)


async def _pagina(contexto: BrowserContext) -> Page:
    return contexto.pages[0] if contexto.pages else await contexto.new_page()


async def test_lista_carregada_pela_pagina_e_capturada(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    visita = await visitar(page, site.url("/lista"), leitor, politica_local, RelogioDoNavegador())
    assert isinstance(visita, Captura)
    assert visita.status == 200
    # a página pede o JSON 100 ms depois do `load`: só aparece se a espera assentou a página
    assert [_caminho(r.url) for r in visita.respostas] == ["/api/vagas"]
    assert [v.titulo for v in leitor.ler(visita, ESCOPO).vagas] == ["Vaga 1", "Vaga 2"]


async def test_captura_so_respostas_que_casam(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    todas = ouvir_respostas(page, leitor.hosts, None)  # controle: sem padrão, tudo do host
    visita = await visitar(page, site.url("/lista"), leitor, politica_local, RelogioDoNavegador())
    await todas.prontas()
    assert isinstance(visita, Captura)
    assert {_caminho(r.url) for r in visita.respostas} == {"/api/vagas"}
    assert {"/lista", "/api/vagas", "/api/outra"} <= {_caminho(r.url) for r in todas}
    resposta = visita.respostas[0]
    assert (resposta.status, resposta.tipo) == (200, "application/json")
    assert '"Vaga 1"' in resposta.texto


async def test_resposta_acima_de_5_mb_e_ignorada(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    todas = ouvir_respostas(page, leitor.hosts, None)
    visita = await visitar(page, site.url("/grande"), leitor, politica_local, RelogioDoNavegador())
    await todas.prontas()
    assert isinstance(visita, Captura)
    caminhos = {_caminho(r.url) for r in todas}
    assert "/api/vagas" in caminhos  # a pequena, da mesma página, entra
    assert site.visitas["/api/grande-com-tamanho"] == 1  # com Content-Length
    assert site.visitas["/api/grande-sem"] == 1  # sem Content-Length
    assert not caminhos & {"/api/grande-com-tamanho", "/api/grande-sem"}


async def test_rolar_traz_mais_itens(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    sem_rolar = await visitar(
        page, site.url("/rolar"), LeitorFalso.para(site), politica_local, relogio
    )
    leitor = LeitorFalso.para(site, rolar=True)
    rolando = await visitar(page, site.url("/rolar"), leitor, politica_local, relogio)
    assert isinstance(sem_rolar, Captura) and isinstance(rolando, Captura)
    assert len(leitor.ler(sem_rolar, ESCOPO).vagas) == 2  # controle: sem rolar, só a 1ª parte
    assert [v.titulo for v in leitor.ler(rolando, ESCOPO).vagas] == [
        "Vaga 1",
        "Vaga 2",
        "Vaga 3",
        "Vaga 4",
    ]


async def test_url_fora_da_politica_nao_e_visitada(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    url = site.url6("/qualquer")
    visita = await visitar(page, url, LeitorFalso.para(site), politica_local, RelogioDoNavegador())
    assert visita == Recusada("::1")
    assert site.visitas["/qualquer"] == 0
    await page.goto(url)  # controle: o contador vê a visita quando ela acontece
    assert site.visitas["/qualquer"] == 1


async def test_url_torta_e_recusada_sem_quebrar(
    site: SiteFalso,
    contexto_de_teste: BrowserContext,
    politica_local: Politica,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="jobot.navegador.pagina")
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    relogio = RelogioDoNavegador()
    # host com caractere de controle (vem do `proxima` do leitor, conteúdo de terceiro)
    assert await visitar(page, "http://a\x1bb/x", leitor, politica_local, relogio) == (
        Recusada("a\x1bb")
    )
    assert "'a\\x1bb'" in caplog.text and "\x1b" not in caplog.text  # %r, não o byte cru
    # colchete sem par: o `urlsplit` levanta, a navegação só recusa
    assert await visitar(page, "http://[::1/x", leitor, politica_local, relogio) == Recusada("")
    assert sum(site.visitas.values()) == 0


async def _salto(
    site: SiteFalso, contexto: BrowserContext, politica: Politica, caminho: str, parada: str
) -> None:
    page = await _pagina(contexto)
    leitor = LeitorFalso.para(site)
    todas = ouvir_respostas(page, leitor.hosts, None)
    de_fora = ouvir_respostas(page, ("::1",), None)  # controle: a página de ::1 chegou
    visita = await visitar(page, site.url(caminho), leitor, politica, RelogioDoNavegador())
    await todas.prontas()
    await de_fora.prontas()
    assert visita == parada
    assert _hosts(de_fora) == {"::1"}
    assert "::1" not in _hosts(todas)


async def test_salto_para_sso_e_precisa_login(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    await _salto(site, contexto_de_teste, politica_local, "/salto-sso", "precisa_login")
    assert site.visitas["/sso/entrar"] == 1


async def test_salto_para_outro_host_e_bloqueio(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    await _salto(site, contexto_de_teste, politica_local, "/salto-fora", "bloqueio")
    assert site.visitas["/qualquer"] == 1


async def test_pagina_de_login_e_precisa_login(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    relogio = RelogioDoNavegador()
    # só o `input[type=password]` diz que é login: o leitor não reconhece e o prefixo não casa
    assert await visitar(page, site.url("/login"), leitor, politica_local, relogio) == (
        "precisa_login"
    )
    controle = await visitar(page, site.url("/logado"), leitor, politica_local, relogio)
    assert isinstance(controle, Captura)


async def test_prefixo_de_login_e_precisa_login(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    url = site.url("/entrar/sem-senha")  # sem campo de senha
    relogio = RelogioDoNavegador()
    leitor = LeitorFalso.para(site, prefixos_login=("::1/sso", "127.0.0.1/entrar"))
    assert await visitar(page, url, leitor, politica_local, relogio) == "precisa_login"
    controle = await visitar(page, url, LeitorFalso.para(site), politica_local, relogio)
    assert isinstance(controle, Captura)


async def test_cloudflare_que_sai_sozinho_segue(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    relogio = RelogioDoNavegador()
    visita = await visitar(page, site.url("/cloudflare-sai"), leitor, politica_local, relogio)
    assert isinstance(visita, Captura)
    assert visita.status == 200  # o 403 do desafio não vira bloqueio
    assert len(leitor.ler(visita, ESCOPO).vagas) == 2
    assert site.visitas["/cloudflare-sai"] == 2  # o desafio recarregou a página sozinho
    assert relogio.dormidas and set(relogio.dormidas) == {1}  # olhou a cada 1 s
    assert len(relogio.dormidas) < ESPERA_CLOUDFLARE_S


async def test_cloudflare_que_leva_ao_login_e_precisa_login(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    relogio = RelogioDoNavegador()
    # depois do desafio, host e login são conferidos de novo sobre a página nova
    url = site.url("/cloudflare-login")
    assert await visitar(page, url, leitor, politica_local, relogio) == "precisa_login"
    assert site.visitas["/login"] == 1
    url = site.url("/cloudflare-sso")
    assert await visitar(page, url, leitor, politica_local, relogio) == "precisa_login"
    assert site.visitas["/sso/entrar"] == 1


async def test_cloudflare_que_leva_a_url_com_fragmento_segue(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    url = site.url("/cloudflare-fragmento")
    visita = await visitar(page, url, leitor, politica_local, RelogioDoNavegador())
    assert isinstance(visita, Captura)
    assert visita.status == 200  # a resposta de /lista, não o 403 do desafio


async def test_429_depois_do_cloudflare_le_o_retry_after_novo(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    relogio = RelogioDoNavegador()
    visita = await visitar(page, site.url("/cloudflare-429"), leitor, politica_local, relogio)
    assert isinstance(visita, Captura)
    assert len(leitor.ler(visita, ESCOPO).vagas) == 2
    assert relogio.dormidas[-1] == 7.0  # o Retry-After do 429, não a espera padrão
    assert set(relogio.dormidas[:-1]) == {1}  # antes, só os passos do desafio
    assert site.visitas["/cloudflare-429"] == 3


async def test_403_e_pagina_de_bloqueio_sao_bloqueio(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    relogio = RelogioDoNavegador()
    assert await visitar(page, site.url("/403"), leitor, politica_local, relogio) == "bloqueio"
    assert await visitar(page, site.url("/bloqueio"), leitor, politica_local, relogio) == "bloqueio"
    controle = await visitar(page, site.url("/lista-html"), leitor, politica_local, relogio)
    assert isinstance(controle, Captura)


async def test_429_espera_o_retry_after(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    relogio = RelogioDoNavegador()
    visita = await visitar(page, site.url("/429"), leitor, politica_local, relogio)
    assert isinstance(visita, Captura)
    assert len(leitor.ler(visita, ESCOPO).vagas) == 2
    assert relogio.dormidas == [7.0]
    assert site.visitas["/429"] == 2


async def test_429_sem_retry_after_espera_o_padrao(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site)
    relogio = RelogioDoNavegador()
    visita = await visitar(page, site.url("/429-sem-tempo"), leitor, politica_local, relogio)
    assert isinstance(visita, Captura)
    assert relogio.dormidas == [ESPERAS_LIMITE[0]]
    assert site.visitas["/429-sem-tempo"] == 2


async def test_respostas_acima_do_teto_sao_ignoradas(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    visita = await visitar(
        page, site.url("/muitas"), LeitorFalso.para(site), politica_local, RelogioDoNavegador()
    )
    assert isinstance(visita, Captura)
    assert site.visitas["/api/vagas"] == MAX_RESPOSTAS + 11  # controle: a página pediu todas
    assert len(visita.respostas) == MAX_RESPOSTAS


async def test_retry_after_acima_do_teto_e_no_limite(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    assert MAX_RETRY_AFTER_S == 600  # o site falso pede 601
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    url = site.url("/429-longo")
    assert await visitar(page, url, LeitorFalso.para(site), politica_local, relogio) == "no_limite"
    assert relogio.dormidas == []
    assert site.visitas["/429-longo"] == 1


async def test_429_repetido_e_no_limite(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    relogio = RelogioDoNavegador()
    url = site.url("/429-sempre")
    assert await visitar(page, url, LeitorFalso.para(site), politica_local, relogio) == "no_limite"
    assert relogio.dormidas == [7.0]
    assert site.visitas["/429-sempre"] == 2


CAMINHOS_ACIMA = (
    "/lista",
    "/grande",
    "/rolar",
    "/salto-sso",
    "/salto-fora",
    "/login",
    "/login-recaptcha",
    "/entrar/sem-senha",
    "/cloudflare-sai",
    "/403",
    "/bloqueio",
    "/429",
    "/429-longo",
)


async def test_navegacao_nao_faz_post(
    site: SiteFalso, contexto_de_teste: BrowserContext, politica_local: Politica
) -> None:
    page = await _pagina(contexto_de_teste)
    leitor = LeitorFalso.para(site, rolar=True)
    for caminho in CAMINHOS_ACIMA:
        await visitar(page, site.url(caminho), leitor, politica_local, RelogioDoNavegador())
    assert all(site.visitas[c] for c in CAMINHOS_ACIMA)  # todas foram mesmo visitadas
    assert (site.posts, site.campos_mudados) == (0, 0)

    # controle, num site à parte: o teste preenche e envia o login, e os contadores veem
    with SiteFalso() as controle:
        await page.goto(controle.url("/login"))
        async with page.expect_request("**/campo-mudou*"):
            await page.fill("input[name=usuario]", "pessoa")
        async with page.expect_navigation():
            await page.click("button[type=submit]")
        assert controle.posts == 1
        assert controle.campos_mudados >= 1
