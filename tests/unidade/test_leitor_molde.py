"""Testes do molde do leitor com login: são também os testes de partida do site novo.

Na cópia, mudam as duas linhas com `# MUDE:` (o módulo do leitor e a pasta dos exemplos) e os
valores esperados de cada exemplo (títulos, empresas, URLs). Só exemplos, sem rede.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from selectolax.lexbor import LexborHTMLParser

from apoio import molde_leitor as leitor_mod  # MUDE: o módulo do leitor novo
from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.leitores.base import Captura, EscopoLogado, LeitorComLogin, Leitura
from jobot.nucleo.leitores.estado import estado_do_escopo
from jobot.nucleo.modelo import VagaColetada

PASTA = Path(__file__).resolve().parents[1] / "fixtures" / "molde_logado"  # MUDE: a pasta

RAIZ = Path(__file__).resolve().parents[2]
LEITOR = leitor_mod.LEITOR
BUSCA = f"https://{leitor_mod._HOST}/busca?q=dev"
ESCOPO = EscopoLogado("dev", BUSCA)


def _html(nome: str) -> str:
    return (PASTA / f"{nome}.html").read_text(encoding="utf-8")


def _captura(nome: str, url: str = BUSCA) -> Captura:
    return Captura(url, 200, _html(nome), ())


def _carregar_capturar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capturar_script", RAIZ / "scripts/capturar.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _vaga() -> VagaColetada:
    return VagaColetada(
        fonte=leitor_mod.CHAVE,
        escopo="dev",
        url=f"https://{leitor_mod._HOST}/vagas/101",
        titulo="Desenvolvedora Python",
        empresa="Empresa Fictícia Alfa",
        descricao_formato="html",
    )


def _com_proxima(href: str) -> Captura:
    arvore = LexborHTMLParser(_html("lista"))
    link = arvore.css_first(leitor_mod._PROXIMA)
    assert link is not None
    link.attrs["href"] = href
    return Captura(BUSCA, 200, arvore.html or "", ())


def test_cumpre_o_protocolo() -> None:
    alvo: LeitorComLogin = leitor_mod.LEITOR
    assert alvo.chave.endswith("_logado")


def test_escopos_um_por_termo() -> None:
    ctx = ContextoColeta((), (" dev ", "dev", "", "c++ júnior"), ())
    assert list(LEITOR.escopos(ctx)) == [
        EscopoLogado("dev", "https://vagas.exemplo.invalid/busca?q=dev"),
        EscopoLogado("c++ júnior", "https://vagas.exemplo.invalid/busca?q=c%2B%2B+j%C3%BAnior"),
    ]


def test_e_login_pela_url() -> None:
    assert LEITOR.e_login(_captura("login", leitor_mod.URL_LOGIN)) is True
    assert LEITOR.e_login(_captura("lista")) is False
    # o mesmo caminho noutro host não é a entrada deste site
    assert LEITOR.e_login(_captura("login", "https://outro.exemplo.invalid/entrar")) is False


def test_pagina_de_login_nao_e_logada() -> None:
    assert LEITOR.pagina_logada(_html("login"), leitor_mod.URL_LOGIN) is False
    # nem com a marca da sessão: na URL de entrada, é login
    assert LEITOR.pagina_logada(_html("lista"), leitor_mod.URL_LOGIN) is False


def test_pagina_logada_pela_marca() -> None:
    assert LEITOR.pagina_logada(_html("lista"), BUSCA) is True
    assert LEITOR.pagina_logada(_html("bloqueio"), BUSCA) is False


def test_marca_dentro_da_descricao_nao_conta() -> None:
    vaga = _html("vaga")
    sem_cabecalho = re.sub(r"<header>.*?</header>", "", vaga, flags=re.DOTALL)
    # a marca segue na página, mas só dentro da descrição (texto de terceiro)
    assert LexborHTMLParser(sem_cabecalho).css_first(leitor_mod._MARCA_LOGADA) is not None
    url = f"https://{leitor_mod._HOST}/vagas/101"
    assert LEITOR.pagina_logada(sem_cabecalho, url) is False
    assert LEITOR.pagina_logada(vaga, url) is True


def test_pagina_bloqueada() -> None:
    assert LEITOR.pagina_bloqueada(_html("bloqueio"), BUSCA) is True
    assert LEITOR.pagina_bloqueada(_html("lista"), BUSCA) is False


def test_proxima_da_lista() -> None:
    assert LEITOR.proxima(_captura("lista")) == "https://vagas.exemplo.invalid/busca?q=dev&pagina=2"
    assert LEITOR.proxima(_captura("lista_p2", f"{BUSCA}&pagina=2")) is None


def test_proxima_fora_do_host_e_none() -> None:
    for href in (
        "https://outro.exemplo.invalid/busca?q=dev&pagina=2",
        "//outro.exemplo.invalid/busca?q=dev&pagina=2",
        "http://vagas.exemplo.invalid/busca?q=dev&pagina=2",
        "https://vagas.exemplo.invalid:8443/busca?q=dev&pagina=2",
        "https://conta@vagas.exemplo.invalid/busca?q=dev&pagina=2",
        "https://[vagas.exemplo.invalid/busca",
        "javascript:alert(1)",
    ):
        assert LEITOR.proxima(_com_proxima(href)) is None, href
    # controle: o mesmo caminho, absoluto e no host certo, passa
    certa = "https://vagas.exemplo.invalid/busca?q=dev&pagina=2"
    assert LEITOR.proxima(_com_proxima(certa)) == certa


def test_ler_lista() -> None:
    leitura = LEITOR.ler(_captura("lista"), ESCOPO)
    assert (leitura.pulados, leitura.formato_mudou) == (0, False)
    assert [(v.titulo, v.empresa, v.url, v.locais) for v in leitura.vagas] == [
        (
            "Desenvolvedora Python",
            "Empresa Fictícia Alfa",
            "https://vagas.exemplo.invalid/vagas/101",
            ("Cidade Exemplo",),
        ),
        (
            "Pessoa desenvolvedora back-end",
            "Empresa Fictícia Beta",
            "https://vagas.exemplo.invalid/vagas/102",
            ("Remoto",),
        ),
        (
            "Analista de dados",
            "Empresa Fictícia Gama",
            "https://vagas.exemplo.invalid/vagas/103",
            (),
        ),
    ]
    assert {(v.fonte, v.escopo, v.descricao) for v in leitura.vagas} == {
        (leitor_mod.CHAVE, ESCOPO.id, "")
    }


def test_ler_lista_vazia_e_valida() -> None:
    assert LEITOR.ler(_captura("vazia"), ESCOPO) == Leitura((), 0, False)


def test_sem_lista_e_formato_mudou() -> None:
    leitura = LEITOR.ler(_captura("login"), ESCOPO)
    assert (leitura.vagas, leitura.formato_mudou) == ((), True)


def test_item_torto_conta_pulado() -> None:
    leitura = LEITOR.ler(_captura("torta"), ESCOPO)
    assert [v.url for v in leitura.vagas] == ["https://vagas.exemplo.invalid/vagas/301"]
    assert (leitura.pulados, leitura.formato_mudou) == (4, False)


def test_so_itens_tortos_e_formato_mudou() -> None:
    arvore = LexborHTMLParser(_html("torta"))
    for legivel in arvore.css('li:has(a[href="/vagas/301"])'):
        legivel.decompose()
    leitura = LEITOR.ler(Captura(BUSCA, 200, arvore.html or "", ()), ESCOPO)
    assert leitura == Leitura((), 4, True)


def test_detalhar_traz_a_descricao() -> None:
    vaga = _vaga()
    url = vaga.url
    detalhada = LEITOR.detalhar(_captura("vaga", url), vaga)
    assert detalhada is not None
    assert "serviços em Python" in detalhada.descricao
    assert "<li>Git e revisão de código</li>" in detalhada.descricao
    assert detalhada.descricao_formato == "html"
    assert (detalhada.url, detalhada.titulo, detalhada.empresa) == (url, vaga.titulo, vaga.empresa)


def test_detalhar_sem_descricao_e_none() -> None:
    assert LEITOR.detalhar(_captura("lista"), _vaga()) is None


def test_estado_com_o_molde() -> None:
    # quem decide o estado é `estado_do_escopo`: o leitor só diz o que leu
    def estado(nome: str) -> tuple[str, str | None]:
        desfecho = estado_do_escopo(
            [LEITOR.ler(_captura(nome), ESCOPO)],
            parada=None,
            cortada=False,
            tres_ok_com_vagas=False,
        )
        return desfecho.estado, desfecho.motivo

    assert estado("lista") == ("ok", None)
    assert estado("torta") == ("parcial", "saude.formato_mudou")
    assert estado("login") == ("falhou", "saude.formato_mudou")


def test_fixtures_do_molde_sem_problemas() -> None:
    # `test_fixtures.py` só percorre `descobrir()`, que não vê leitores: a pasta se confere aqui.
    assert _carregar_capturar().problemas(PASTA) == []
