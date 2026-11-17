"""Leitor do LinkedIn com login (T235, D136.12 a D136.18): só fixtures, sem rede."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from selectolax.lexbor import LexborHTMLParser

from apoio.relogio import RelogioFalso
from jobot.navegador.politica import casa_login
from jobot.nucleo.coletores.base import ContextoColeta
from jobot.nucleo.leitores.base import Captura, EscopoLogado, LeitorComLogin, Leitura
from jobot.nucleo.leitores.linkedin import LinkedIn, _data_relativa
from jobot.nucleo.modelo import Busca, Local, Modalidade, VagaColetada

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "linkedin_logado"
AGORA = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
BUSCA = "https://www.linkedin.com/jobs/search-results/?keywords=enfermeiro&currentJobId=1"
ESCOPO = EscopoLogado("enfermeiro", "https://www.linkedin.com/jobs/search/?keywords=enfermeiro")
_ID = re.compile(r'componentkey="job-card-component-ref-([0-9]+)"')


def _leitor() -> LinkedIn:
    return LinkedIn(RelogioFalso(AGORA))


def _html(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def _captura(html: str, url: str = BUSCA) -> Captura:
    return Captura(url, 200, html, ())


def _ids(html: str) -> list[str]:
    return list(dict.fromkeys(_ID.findall(html)))


def _cartao(
    id_: str, titulo: str = "Vaga {id}", empresa: str = "Empresa Fictícia", local: str = "X"
) -> str:
    chave = f"job-card-component-ref-{id_}"
    return (
        f'<div componentkey="{chave}"><div componentkey="{chave}">'
        f'<p><span>{titulo.format(id=id_)}</span><span aria-hidden="true">'
        f"{titulo.format(id=id_)}</span></p><p>{empresa}</p><p>{local}</p></div></div>"
    )


def _lista(n: int) -> str:
    return "<html><body>" + "".join(_cartao(str(1000 + i)) for i in range(n)) + "</body></html>"


def _vaga(id_: str) -> VagaColetada:
    return VagaColetada(
        fonte="linkedin_logado",
        escopo="enfermeiro",
        url=f"https://www.linkedin.com/jobs/view/{id_}/",
        titulo="Vaga",
        empresa="Empresa",
        descricao_formato="html",
        id_externo=id_,
    )


def _detalhar(nome: str, id_: str) -> VagaColetada | None:
    vaga = _vaga(id_)
    return _leitor().detalhar(_captura(_html(nome), vaga.url), vaga)


def test_atributos_do_leitor() -> None:
    leitor: LeitorComLogin = _leitor()
    assert leitor.chave == "linkedin_logado"
    assert leitor.nome == "LinkedIn"
    assert leitor.hosts == ("www.linkedin.com",)
    assert leitor.url_login == "https://www.linkedin.com/login"
    assert leitor.url_entrada == "https://www.linkedin.com/jobs/"
    assert leitor.prefixos_login == (
        "www.linkedin.com/login",
        "www.linkedin.com/checkpoint/",
        "www.linkedin.com/authwall",
        "www.linkedin.com/uas/login",
        "www.linkedin.com/signup",
    )
    assert (leitor.respostas, leitor.campos_conta) == ((), ())
    assert leitor.rolar is True
    assert leitor.lista_tem_descricao is False


def test_escopos_um_por_termo() -> None:
    ctx = ContextoColeta(empresas=(), termos=("enfermeiro", "enfermeiro", "dev python"), paises=())
    assert list(_leitor().escopos(ctx)) == [
        EscopoLogado(
            "enfermeiro",
            "https://www.linkedin.com/jobs/search/?keywords=enfermeiro&f_TPR=r604800",
        ),
        EscopoLogado(
            "dev python",
            "https://www.linkedin.com/jobs/search/?keywords=dev+python&f_TPR=r604800",
        ),
    ]


def _ids_e_urls(*buscas: Busca) -> list[EscopoLogado]:
    # `termos` difere dos cargos: o leitor tem de usar as buscas, não os termos
    ctx = ContextoColeta(empresas=(), termos=("outro termo",), paises=(), buscas=buscas)
    return list(_leitor().escopos(ctx))


def test_escopos_com_cidade_e_remoto() -> None:
    busca = Busca(
        nome="b",
        cargos=("Enfermeiro", "Dev Python"),
        cidades=(Local(cidade="São Paulo", uf="SP", pais="BR"),),
        modalidades=(Modalidade.REMOTO,),
    )
    escopos = _ids_e_urls(busca)
    assert [e.id for e in escopos] == [
        "Enfermeiro em São Paulo, SP",
        "Enfermeiro remoto",
        "Dev Python em São Paulo, SP",
        "Dev Python remoto",
    ]
    assert escopos[1].url == (
        "https://www.linkedin.com/jobs/search/?keywords=Enfermeiro+remoto&f_TPR=r604800"
    )


def test_escopos_cidade_sem_uf() -> None:
    busca = Busca(nome="b", cargos=("Enfermeiro",), cidades=(Local(cidade="Belo Horizonte"),))
    assert [e.id for e in _ids_e_urls(busca)] == ["Enfermeiro em Belo Horizonte"]


def test_escopos_pulam_local_sem_cidade() -> None:
    busca = Busca(nome="b", cargos=("Enfermeiro",), cidades=(Local(uf="MG"), Local(pais="PT")))
    assert [e.id for e in _ids_e_urls(busca)] == ["Enfermeiro"]


def test_escopos_repetidos_contam_uma_vez() -> None:
    a = Busca(nome="a", cargos=("Enfermeiro",))
    b = Busca(nome="b", cargos=("enfermeiro",))
    assert [e.id for e in _ids_e_urls(a, b)] == ["Enfermeiro"]


def test_escopos_limpam_espacos_de_cidade_e_uf() -> None:
    def ids(*locais: Local) -> list[str]:
        return [e.id for e in _ids_e_urls(Busca(nome="b", cargos=("Cargo",), cidades=locais))]

    assert ids(Local(cidade="  ", uf="MG")) == ["Cargo"]
    assert ids(Local(cidade=" Belo Horizonte ", uf=" MG ")) == ["Cargo em Belo Horizonte, MG"]
    assert ids(Local(cidade="Contagem", uf="  ")) == ["Cargo em Contagem"]


def test_escopos_cargo_com_espacos() -> None:
    busca = Busca(nome="b", cargos=("  ", " Enfermeiro "), cidades=(Local(cidade="Contagem"),))
    assert [e.id for e in _ids_e_urls(busca)] == ["Enfermeiro em Contagem"]


def test_escopos_mesmo_cargo_em_duas_buscas() -> None:
    a = Busca(nome="a", cargos=("Enfermeiro",), cidades=(Local(cidade="Contagem"),))
    b = Busca(nome="b", cargos=("Enfermeiro",), cidades=(Local(cidade="Betim"),))
    assert [e.id for e in _ids_e_urls(a, b)] == ["Enfermeiro em Contagem", "Enfermeiro em Betim"]


def test_proxima_soma_25_sem_current_job_id() -> None:
    url = "https://www.linkedin.com/jobs/search/?keywords=enfermeiro&f_TPR=r604800&currentJobId=9"
    u = _leitor().proxima(_captura(_lista(25), url))
    assert u is not None
    assert urlsplit(u).path == "/jobs/search/"
    assert parse_qs(urlsplit(u).query) == {
        "keywords": ["enfermeiro"],
        "f_TPR": ["r604800"],
        "start": ["25"],
    }


def test_proxima_para_com_menos_de_25() -> None:
    assert _leitor().proxima(_captura(_lista(24))) is None


def test_proxima_repoe_o_filtro_da_semana() -> None:
    u = _leitor().proxima(_captura(_lista(25), BUSCA))
    assert u is not None
    assert urlsplit(u).path == "/jobs/search-results/"
    assert parse_qs(urlsplit(u).query) == {
        "keywords": ["enfermeiro"],
        "f_TPR": ["r604800"],
        "start": ["25"],
    }


def test_proxima_le_o_start_da_url() -> None:
    url = "https://www.linkedin.com/jobs/search-results/?keywords=enfermeiro&start=25"
    u = _leitor().proxima(_captura(_lista(25), url))
    assert u is not None
    assert urlsplit(u).path == "/jobs/search-results/"
    assert parse_qs(urlsplit(u).query) == {
        "keywords": ["enfermeiro"],
        "f_TPR": ["r604800"],
        "start": ["50"],
    }


@pytest.mark.parametrize("start", ["abc", "1234567", "١"])
def test_proxima_com_start_torto_para(start: str) -> None:
    url = f"https://www.linkedin.com/jobs/search-results/?keywords=enfermeiro&start={start}"
    assert _leitor().proxima(_captura(_lista(25), url)) is None


def test_ler_busca_p2_da_fixture() -> None:
    html = _html("busca_p2.html")
    url = "https://www.linkedin.com/jobs/search-results/?keywords=enfermeiro&start=25"
    leitura = _leitor().ler(_captura(html, url), ESCOPO)
    assert leitura.vagas
    assert [v.id_externo for v in leitura.vagas] == _ids(html)
    assert (leitura.pulados, leitura.formato_mudou) == (0, False)
    assert _leitor().proxima(_captura(html, url)) is None


def test_ler_cartoes_da_fixture() -> None:
    html = _html("busca.html")
    leitura = _leitor().ler(_captura(html), ESCOPO)
    assert len(leitura.vagas) == len(_ids(html)) == 5
    assert (leitura.pulados, leitura.formato_mudou) == (0, False)
    primeira = leitura.vagas[0]
    assert primeira.fonte == "linkedin_logado"
    assert primeira.escopo == "enfermeiro"
    assert primeira.titulo == "Enfermeiro Escalista"
    assert primeira.empresa == "ISA Saúde"
    assert primeira.locais == ("Belo Horizonte, MG",)
    assert primeira.modalidade_declarada == "On-site"
    assert primeira.id_externo == "4488964135"
    assert primeira.url == "https://www.linkedin.com/jobs/view/4488964135/"
    assert primeira.publicada_em is None  # o cartão diz só "Viewed"
    assert leitura.vagas[1].publicada_em == AGORA - timedelta(days=1)
    verificada = leitura.vagas[3]  # "(Verified job)" no título, local sem modalidade
    assert verificada.titulo == "Enfermeiro(a)- Apoio as Unidades- Área Imagem"
    assert (verificada.locais, verificada.modalidade_declarada) == (("Belo Horizonte, MG",), None)
    assert all(v.descricao == "" and v.descricao_formato == "html" for v in leitura.vagas)


def test_cartao_em_portugues() -> None:
    leitura = _leitor().ler(_captura(_html("busca_pt.html")), ESCOPO)
    assert leitura.vagas
    primeira = leitura.vagas[0]
    assert primeira.titulo == "Técnico de Enfermagem"
    assert primeira.empresa == "Clínica Horizonte Fictícia"
    assert primeira.modalidade_declarada == "Remoto"
    assert primeira.publicada_em == AGORA - timedelta(days=14)
    assert primeira.salario_texto == "R$ 3.000/mês"
    assert [v.titulo for v in leitura.vagas[1:]] == [
        "Enfermeiro Assistente",
        "Enfermeiro de Auditoria",
    ]
    assert [v.modalidade_declarada for v in leitura.vagas[1:]] == ["Presencial", "Híbrido"]
    assert [v.publicada_em for v in leitura.vagas[1:]] == [
        AGORA - timedelta(days=3),
        AGORA - timedelta(days=30),
    ]


def test_frase_pessoal_do_cartao_e_descartada() -> None:
    leitura = _leitor().ler(_captura(_html("cartao_pessoal.html")), ESCOPO)
    assert len(leitura.vagas) == 1
    vaga = leitura.vagas[0]
    textos = [str(valor) for valor in vars(vaga).values() if valor is not None]
    assert not any("alumni" in texto for texto in textos)
    assert (vaga.titulo, vaga.empresa, vaga.locais) == (
        "Enfermeiro Plantonista",
        "Hospital Exemplo Fictício",
        ("Recife, PE",),
    )
    assert vaga.publicada_em == AGORA - timedelta(days=3)


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("Posted 30 minutes ago", AGORA - timedelta(minutes=30)),
        ("2 hours ago", AGORA - timedelta(hours=2)),
        ("3 days ago", AGORA - timedelta(days=3)),
        ("1 week ago", AGORA - timedelta(days=7)),
        ("2 months ago", AGORA - timedelta(days=60)),
        ("há 1 mês", AGORA - timedelta(days=30)),
        ("Reposted 5 days ago", AGORA - timedelta(days=5)),
        ("Publicada há 2 semanas", AGORA - timedelta(days=14)),
        ("Republicada há 4 horas", AGORA - timedelta(hours=4)),
        ("Posted a few days ago", None),
    ],
)
def test_datas_relativas(texto: str, esperada: datetime | None) -> None:
    assert _data_relativa(texto, AGORA) == esperada


def test_lista_vazia_e_valida() -> None:
    assert _leitor().ler(_captura(_html("vazia.html")), ESCOPO) == Leitura((), 0, False)


@pytest.mark.parametrize(
    "aviso",
    [
        "No results found",
        "No matching jobs found",
        "Nenhum resultado encontrado",
        "Nenhuma vaga encontrada",
    ],
)
def test_avisos_de_lista_vazia(aviso: str) -> None:
    html = f"<html><body><section><h2>{aviso}</h2></section></body></html>"
    assert _leitor().ler(_captura(html), ESCOPO) == Leitura((), 0, False)


def test_sem_cartoes_e_sem_aviso_e_formato_mudou() -> None:
    leitura = _leitor().ler(_captura(_html("visitante.html")), ESCOPO)
    assert (leitura.vagas, leitura.formato_mudou) == ((), True)


def test_cartao_sem_titulo_conta_pulado() -> None:
    html = (
        "<html><body>"
        + _cartao("1001")
        + _cartao("1002", titulo="")
        + _cartao("abc")
        + "</body></html>"
    )
    leitura = _leitor().ler(_captura(html), ESCOPO)
    assert [v.id_externo for v in leitura.vagas] == ["1001"]
    assert (leitura.pulados, leitura.formato_mudou) == (2, False)


def test_titulo_repetido_conta_uma_vez_e_salario_em_ingles() -> None:
    chave = "job-card-component-ref-1001"
    html = (
        f'<html><body><div componentkey="{chave}"><p>Enfermeiro</p><p>Enfermeiro</p>'
        "<p>Empresa Fictícia</p><p>Recife, PE (Remote)</p>"
        "<p>1,621 BRL/month - 2,000 BRL/month</p><p>Easy Apply</p></div></body></html>"
    )
    vaga = _leitor().ler(_captura(html), ESCOPO).vagas[0]
    assert (vaga.titulo, vaga.empresa, vaga.locais) == (
        "Enfermeiro",
        "Empresa Fictícia",
        ("Recife, PE",),
    )
    assert vaga.modalidade_declarada == "Remote"
    assert vaga.salario_texto == "1,621 BRL/month - 2,000 BRL/month"


def test_so_cartoes_pulados_e_formato_mudou() -> None:
    html = "<html><body>" + _cartao("1002", titulo="") + "</body></html>"
    assert _leitor().ler(_captura(html), ESCOPO) == Leitura((), 1, True)


def _texto(html: str) -> str:
    return LexborHTMLParser(html).text(separator=" ", strip=True)


def test_detalhar_le_descricao_e_contrato() -> None:
    vaga = _detalhar("vaga_externa.html", "4488964135")
    assert vaga is not None
    texto = _texto(vaga.descricao)
    assert texto.startswith("Buscamos um(a) enfermeiro(a) para assumir a gestão das escalas")
    assert "Graduação em Enfermagem com COREN ativo em MG" in texto  # a lista fora da caixa
    assert "About the job" not in texto
    assert "…" not in texto  # o botão "… more" sai
    assert not texto.endswith("more")
    assert vaga.descricao_formato == "html"
    assert vaga.contrato_declarado == "Full-time"


def test_link_de_candidatura_sem_rastreio() -> None:
    vaga = _detalhar("vaga_externa.html", "4488964135")
    assert vaga is not None
    assert vaga.url_candidatura == (
        "https://vagasisasaude.gupy.io/job/"
        "eyJqb2JJZCI6MTI4MzMyNjgsInNvdXJjZSI6ImxpbmtlZGluIn0=?jobBoardSource=linkedin"
    )
    assert "mt=" not in (vaga.url_candidatura or "")
    assert "urlhash=" not in (vaga.url_candidatura or "")


def test_easy_apply_sem_link() -> None:
    vaga = _detalhar("vaga_easy.html", "4487938776")
    assert vaga is not None
    assert vaga.url_candidatura is None
    assert _texto(vaga.descricao).startswith("Somos um dos principais ecossistemas")
    assert vaga.contrato_declarado == "Full-time"


def test_link_que_nao_e_http_vira_none() -> None:
    vaga = _detalhar("vaga_link_ruim.html", "4300000001")
    assert vaga is not None
    assert vaga.url_candidatura is None
    assert vaga.contrato_declarado == "Part-time"


_SECAO = (
    '<div componentkey="JobDetails_AboutTheJob_1"><h2>About the job</h2>'
    "<p>Descrição fictícia.</p></div>"
)


def _detalhar_sintetico(miolo: str) -> VagaColetada | None:
    vaga = _vaga("1")
    html = f"<html><body>{miolo}{_SECAO}</body></html>"
    return _leitor().detalhar(_captura(html, vaga.url), vaga)


@pytest.mark.parametrize(
    ("rotulo", "esperada"),
    [
        ("Apply on company website", "https://empresa.example/vaga"),
        ("Candidatar-se no site da empresa", "https://empresa.example/vaga"),
        ("Save the job", None),
    ],
)
def test_candidatura_pelo_rotulo_en_ou_pt(rotulo: str, esperada: str | None) -> None:
    href = "https://www.linkedin.com/safety/go/?url=https%3A%2F%2Fempresa.example%2Fvaga"
    vaga = _detalhar_sintetico(f'<a href="{href}" aria-label="{rotulo}">x</a>')
    assert vaga is not None
    assert vaga.url_candidatura == esperada


@pytest.mark.parametrize(
    "href",
    [
        "https://empresa.example/apply?url=https%3A%2F%2Foutra.example%2F",  # direto, sem safety/go
        "https://www.linkedin.com.example/safety/go/?url=https%3A%2F%2Fx.example%2F",
        "https://www.linkedin.com/safety/go/?urlhash=abc",  # sem o parâmetro url
    ],
)
def test_candidatura_fora_do_safety_go_vira_none(href: str) -> None:
    vaga = _detalhar_sintetico(f'<a href="{href}" aria-label="Apply on company website">x</a>')
    assert vaga is not None
    assert vaga.url_candidatura is None


def test_detalhar_ignora_link_com_host_torto() -> None:
    vaga = _detalhar_sintetico(
        '<a href="http://[::1">Contract</a><a href="https://www.linkedin.com/jobs/view/1/">'
        "Full-time</a>"
    )
    assert vaga is not None
    assert vaga.contrato_declarado == "Full-time"


def test_detalhar_sem_descricao_devolve_none() -> None:
    assert _detalhar("busca.html", "4488964135") is None


def test_pagina_logada_com_fixtures() -> None:
    leitor = _leitor()
    entrada = _html("entrada.html")
    assert "job-card-component-ref-" not in entrada
    assert leitor.pagina_logada(entrada, "https://www.linkedin.com/jobs/") is True
    assert leitor.pagina_logada(_html("visitante.html"), "https://www.linkedin.com/jobs/") is False
    assert leitor.pagina_logada(entrada, "https://www.linkedin.com/login") is False


@pytest.mark.parametrize(
    ("link", "esperado"),
    [
        ('<a data-view-name="navigation-notifications" href="/x">x</a>', True),
        ('<a href="/notifications/">x</a>', True),
        ('<a href="https://www.linkedin.com/notifications/?filter=all">x</a>', True),
        ('<a href="https://www.linkedin.com.example/notifications/">x</a>', False),
        ('<a href="https://www.linkedin.com/jobs/">x</a>', False),
        ('<a href="http://[::1">x</a><a href="/notifications/">x</a>', True),
        ('<a href="http://[::1">x</a>', False),
        (
            '<div componentkey="JobDetails_AboutTheJob_1"><a href="/notifications/">x</a></div>',
            False,
        ),
        (
            '<div componentkey="JobDetails_AboutTheJob_1"><a href="/notifications/">x</a></div>'
            '<a href="/notifications/">x</a>',
            True,
        ),
    ],
)
def test_pagina_logada_pela_marca(link: str, esperado: bool) -> None:
    html = f"<html><body>{link}</body></html>"
    assert _leitor().pagina_logada(html, "https://www.linkedin.com/jobs/") is esperado


@pytest.mark.parametrize(
    ("caminho", "esperado"),
    [
        ("/login", True),
        ("/checkpoint/challenge/x", True),
        ("/authwall?trk=x", True),
        ("/uas/login?session_redirect=x", True),
        ("/signup/cold-join", True),
        ("/jobs/", False),
    ],
)
def test_e_login_pelo_prefixo(caminho: str, esperado: bool) -> None:
    captura = _captura("<html></html>", f"https://www.linkedin.com{caminho}")
    assert _leitor().e_login(captura) is esperado


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://www.linkedin.com/login", True),
        ("https://www.linkedin.com/checkpoint/challenge/x", True),
        ("https://www.linkedin.com/authwall?trk=x", True),
        ("https://www.linkedin.com/uas/login?session_redirect=x", True),
        ("https://www.linkedin.com/signup/cold-join", True),
        ("https://www.linkedin.com/jobs/", False),
        ("https://outro.com/login", False),
        ("https://www.linkedin.com.mal.io/login", False),
    ],
)
def test_prefixos_login_casam_por_host_e_caminho(url: str, esperado: bool) -> None:
    """O navegador casa `prefixos_login` com `host + caminho` (`casa_login`): sessão vencida
    numa página recusada pela política vira `precisa_login`, não `bloqueio`."""
    leitor = _leitor()
    assert casa_login(url, leitor.prefixos_login) is esperado
    assert leitor.e_login(_captura("<html></html>", url)) is esperado
