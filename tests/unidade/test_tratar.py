from typing import Any

from jobot.nucleo.modelo import (
    Area,
    Contrato,
    Local,
    Modalidade,
    Nivel,
    VagaColetada,
    VagaTratada,
)
from jobot.nucleo.tratamento.duplicadas import agrupar
from jobot.nucleo.tratamento.rotulos import VERSAO_REGRAS
from jobot.nucleo.tratamento.tratar import tratar
from jobot.nucleo.url import canonica, hash_url

DESCRICAO = (
    "<p>Estamos contratando uma pessoa desenvolvedora para o nosso time. "
    "Você vai trabalhar com Python e participar das decisões de produto da empresa, "
    "com foco em qualidade para os clientes e em entrega contínua de valor.</p>"
    "<p>Contratação CLT. Estágio não se aplica.</p>"
)


def _vaga(**campos: Any) -> VagaColetada:
    base: dict[str, Any] = {
        "fonte": "teste",
        "escopo": "",
        "url": "https://exemplo.com/vaga/1?utm_source=x#topo",
        "titulo": "Desenvolvedor Python Júnior",
        "empresa": "Acme",
        "descricao_formato": "html",
        "descricao": DESCRICAO,
        "locais": ("São Paulo, SP",),
        "salario_texto": "R$ 5.000 - R$ 7.000 por mês",
    }
    return VagaColetada(**(base | campos))


def test_tratar_preenche_tudo() -> None:
    v = _vaga(modalidade_declarada="remoto")
    t = tratar(v)
    assert t.url_canonica == canonica(v.url) == "https://exemplo.com/vaga/1"
    assert t.url_hash == hash_url(t.url_canonica)
    assert "<p>" not in t.descricao_texto and "Python" in t.descricao_texto
    assert t.idioma == "pt"
    assert t.locais == (Local(cidade="São Paulo", uf="SP", pais="BR"),)
    assert t.nivel is Nivel.JUNIOR
    assert t.modalidade is Modalidade.REMOTO
    assert t.contrato is Contrato.CLT
    assert t.area is Area.TECNOLOGIA
    assert t.salario is not None
    assert (t.salario.minimo, t.salario.maximo) == (500_000, 700_000)
    assert t.versao_regras == VERSAO_REGRAS
    assert isinstance(t, VagaTratada)
    # campos da coleta passam sem mudança
    assert (t.fonte, t.titulo, t.empresa, t.url, t.descricao) == (
        v.fonte,
        v.titulo,
        v.empresa,
        v.url,
        v.descricao,
    )


def test_url_candidatura_intacta() -> None:
    link = "https://exemplo.com/apply/1?utm_source=x&ref=ABC#Form/"
    t = tratar(_vaga(url_candidatura=link))
    assert t.url_candidatura == link
    assert tratar(_vaga()).url_candidatura is None


def test_mesma_canonica_um_grupo() -> None:
    a = tratar(_vaga(url="https://Exemplo.com/vaga/1/?utm_source=a", escopo="a"))
    b = tratar(_vaga(url="https://exemplo.com/vaga/1#x", escopo="b"))
    grupos = agrupar([a, b])
    assert list(grupos) == [a.url_hash]
    assert grupos[a.url_hash] == [a, b]


def test_urls_diferentes_grupos_separados() -> None:
    a = tratar(_vaga(url="https://exemplo.com/vaga/1"))
    b = tratar(_vaga(url="https://exemplo.com/vaga/2"))
    assert (a.titulo, a.empresa) == (b.titulo, b.empresa)
    grupos = agrupar([a, b])
    assert set(grupos) == {a.url_hash, b.url_hash}
    assert grupos[a.url_hash] == [a]
    assert grupos[b.url_hash] == [b]
