from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import registro, usp
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "usp"
URL_IF = "https://portal.if.usp.br/carreiras/pt-br/oportunidades"
NODE = "https://portal.if.usp.br/carreiras/pt-br/node/{}"
URL_FEA = "https://estagios.fea.usp.br/"
VAGA_FEA = "https://estagios.fea.usp.br/vagas/{}"
IDS_IF = ("2517", "2514", "2513", "2512", "2511")
IDS_FEA = ("132", "134", "135", "136")
SP = timezone(timedelta(hours=-3))
Responder = Callable[[httpx.Request], httpx.Response]


def _html(caso: str) -> str:
    return (PASTA / f"{caso}.html").read_text(encoding="utf-8")


def _resp(texto: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=texto, headers={"Content-Type": "text/html; charset=utf-8"})


def _detalhe_if(id_: str) -> str:
    """O detalhe capturado (nó 2511) com a descrição marcada pelo id: prova quem leu o quê."""
    return _html("if_vaga").replace("Vem para a Rede!", f"Vaga {id_}")


def _detalhe_fea(id_: str) -> str:
    marca = "• Auxílio na elaboração e revisão das principais políticas;"
    assert marca in _html("fea_vaga")
    return _html("fea_vaga").replace(marca, f"Vaga {id_}")


def _rotas_if(lista: str = "if_lista") -> dict[str, str]:
    return {URL_IF: _html(lista)} | {NODE.format(i): _detalhe_if(i) for i in IDS_IF}


def _rotas_fea(lista: str = "fea_lista") -> dict[str, str]:
    return {URL_FEA: _html(lista)} | {VAGA_FEA.format(i): _detalhe_fea(i) for i in IDS_FEA}


def _servir(rotas: Mapping[str, str | httpx.Response]) -> Responder:
    def responder(pedido: httpx.Request) -> httpx.Response:
        achado = rotas.get(str(pedido.url))
        if achado is None:
            raise AssertionError(f"pedido inesperado: {pedido.method} {pedido.url}")
        return achado if isinstance(achado, httpx.Response) else _resp(achado)

    return responder


class _SemValidadores:
    def ler(self, url: str) -> Validadores | None:
        return None


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    escopo: str, *respostas: httpx.Response | Responder
) -> tuple[ResultadoEscopo, list[httpx.Request]]:
    """Roda o coletor de verdade sobre o `ClienteEducado` com transporte falso."""
    pedidos: list[httpx.Request] = []
    fila = list(respostas)

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        return r if isinstance(r, httpx.Response) else r(pedido)

    relogio: Relogio = RelogioFalso()

    cli = ClienteEducado(
        httpx.MockTransport(servidor), relogio, _SemValidadores(), "0.1.0", resolver=_sem_dns
    )
    try:
        http: HttpEducado = cli.escopo()
        resultado = await usp.USP().coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    assert resultado.vagas, f"nenhuma vaga ({resultado.estado}, {resultado.motivo})"
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = usp.COLETOR
    assert registro.descobrir()["usp"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "B"
    assert (prova.intervalo_min, prova.max_pedidos, prova.espera_s) == (
        limites.intervalo_min,
        limites.max_pedidos,
        limites.espera_s,
    )
    assert prova.hosts == ("portal.if.usp.br", "estagios.fea.usp.br")


def test_escopos_sao_as_duas_unidades_sem_depender_do_contexto() -> None:
    ctx = ContextoColeta(
        empresas=[Empresa(nome="X", fonte="usp", identificador="x")], termos=["dev"], paises=["BR"]
    )
    assert list(usp.USP().escopos(ctx)) == ["if", "fea"]
    assert list(usp.USP().escopos(ContextoColeta((), (), ()))) == ["if", "fea"]


async def test_normal_if() -> None:
    resultado, pedidos = await _coletar("if", _servir(_rotas_if()))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 6)
    vagas = _vagas(resultado)
    assert [v.id_externo for v in vagas] == list(IDS_IF)
    primeira, ultima = vagas[0], vagas[-1]
    assert primeira.fonte == "usp" and primeira.escopo == "if"
    assert primeira.url == "https://portal.if.usp.br/carreiras/pt-br/node/2517"
    assert primeira.titulo == "Duas Vagas de Doutorado FAPESP"
    assert primeira.empresa == "LNLS-Sirius/CNPEM"
    assert primeira.contrato_declarado == "Outros"
    assert primeira.prazo == date(2026, 11, 30)
    assert ultima.titulo == "Programa de Estágio em Exatas 2027"
    assert (ultima.empresa, ultima.contrato_declarado) == ("Rede Decisão", "Estágio")
    assert ultima.prazo == date(2026, 12, 31)
    assert all(v.locais == () and v.url_candidatura is None for v in vagas)
    assert [str(p.url) for p in pedidos] == [URL_IF, *(NODE.format(i) for i in IDS_IF)]


async def test_detalhe_do_if_traz_descricao_e_data_de_postagem() -> None:
    resultado, _ = await _coletar("if", _servir(_rotas_if()))
    assert len(_vagas(resultado)) == 5  # sem vaga o laço abaixo provaria nada
    for vaga in _vagas(resultado):
        assert vaga.descricao_formato == "html"
        assert f"Vaga {vaga.id_externo}</h1>" in vaga.descricao  # o detalhe é o da própria vaga
        assert "Requisitos e qualificações" in vaga.descricao and "<li>" in vaga.descricao
        assert "Data Início" not in vaga.descricao  # só o campo de descrição
        assert vaga.publicada_em == datetime(2026, 10, 27, 12, tzinfo=SP)  # sem hora: meio-dia


async def test_normal_fea() -> None:
    resultado, pedidos = await _coletar("fea", _servir(_rotas_fea()))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 5)
    vagas = _vagas(resultado)
    assert [v.id_externo for v in vagas] == list(IDS_FEA)
    ultima = vagas[-1]
    assert ultima.fonte == "usp" and ultima.escopo == "fea"
    assert ultima.url == "https://estagios.fea.usp.br/vagas/136"
    assert ultima.titulo == "Vaga de estágio em Middle Office | Brava Capital"
    assert ultima.empresa == usp.EMPRESA_FEA  # a FEA não diz quem contrata
    assert ultima.contrato_declarado == "Estágio"
    assert ultima.salario_texto == "R$ 1000"
    assert ultima.prazo == date(2027, 2, 26)
    assert ultima.publicada_em is None and ultima.locais == ()
    assert [str(p.url) for p in pedidos] == [URL_FEA, *(VAGA_FEA.format(i) for i in IDS_FEA)]


async def test_detalhe_da_fea_vira_texto_com_os_campos_do_apendice() -> None:
    resultado, _ = await _coletar("fea", _servir(_rotas_fea()))
    vaga = _vagas(resultado)[-1]
    assert vaga.descricao_formato == "texto"
    assert vaga.descricao.startswith("Vaga 136\n• Auxílio no monitoramento de conformidades")
    assert "Benefícios: Vaga no formato Home-Office" in vaga.descricao
    assert "Carga horária semanal: 30 Horas" in vaga.descricao
    assert "Horário do estágio: 09:30" in vaga.descricao
    assert "Contato para vaga: exemplo@exemplo.invalid; https://bravacapital.com/" in vaga.descricao
    assert "<" not in vaga.descricao and "Título da Vaga" not in vaga.descricao
    assert len(_vagas(resultado)) == 4
    assert all(f"Vaga {v.id_externo}\n" in v.descricao for v in _vagas(resultado))


async def test_fea_le_so_a_pagina_inicial_e_os_detalhes() -> None:
    _, pedidos = await _coletar("fea", _servir(_rotas_fea()))
    assert "https://estagios.fea.usp.br/vagas" not in {str(p.url) for p in pedidos}
    assert {p.url.path for p in pedidos} == {"/", *(f"/vagas/{i}" for i in IDS_FEA)}


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar("if", _servir(_rotas_if()))
    assert {p.method for p in pedidos} == {"GET"}
    assert all(not p.url.query and not p.content for p in pedidos)
    assert pedidos[0].headers["user-agent"].startswith("joBot/0.1.0")
    _, pedidos = await _coletar("fea", _servir(_rotas_fea()))
    assert {p.method for p in pedidos} == {"GET"}
    assert all(not p.url.query and not p.content for p in pedidos)


async def test_vazio() -> None:
    resultado, pedidos = await _coletar("if", _resp(_html("if_vazio")))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1
    lista_vazia = _html("fea_lista")
    corpo = lista_vazia[lista_vazia.index("<tbody>") : lista_vazia.index("</tbody>")]
    vazia = lista_vazia.replace(corpo, "<tbody>")
    resultado, pedidos = await _coletar("fea", _resp(vazia))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou_if() -> None:
    # na segunda linha o título deixou de ser um link: item pulado, o resto segue
    lista = _html("if_lista").replace(
        '<a href="/carreiras/pt-br/node/2514">Bolsa de PD em Geoquímica / Sensoriamento Remoto</a>',
        "Bolsa de PD em Geoquímica / Sensoriamento Remoto",
    )
    assert lista != _html("if_lista")
    rotas = _rotas_if() | {URL_IF: lista}
    resultado, _ = await _coletar("if", _servir(rotas))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["2517", "2513", "2512", "2511"]


async def test_formato_mudou_fea() -> None:
    lista = _html("fea_lista").replace('href="/vagas/134"', 'href="/outra/134"')
    assert lista != _html("fea_lista")
    rotas = _rotas_fea() | {URL_FEA: lista}
    resultado, _ = await _coletar("fea", _servir(rotas))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["132", "135", "136"]


@pytest.mark.parametrize("escopo", ["if", "fea"])
@pytest.mark.parametrize(
    "corpo",
    ["", "isto não é html", "<html><body><p>Manutenção</p></body></html>", "<table></table>"],
)
async def test_pagina_sem_lista_falhou(escopo: str, corpo: str) -> None:
    resultado, pedidos = await _coletar(escopo, _resp(corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"
    assert len(pedidos) == 1


@pytest.mark.parametrize("escopo", ["if", "fea"])
async def test_lista_sem_nenhuma_vaga_legivel_falhou(escopo: str) -> None:
    if escopo == "if":
        lista = _html("if_lista").replace("/carreiras/pt-br/node/", "/carreiras/pt-br/x/")
    else:
        lista = _html("fea_lista").replace('href="/vagas/', 'href="/x/')
    resultado, pedidos = await _coletar(escopo, _resp(lista))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"
    assert len(pedidos) == 1  # sem vaga legível, nenhum detalhe


async def test_if_sem_empresa_ou_titulo_pula_a_vaga() -> None:
    lista = _html("if_lista")
    sem_empresa = lista.replace("Instituição: Campus France", "Instituição: ")
    assert sem_empresa != lista
    resultado, _ = await _coletar("if", _servir(_rotas_if() | {URL_IF: sem_empresa}))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert "2513" not in [v.id_externo for v in _vagas(resultado)]
    assert len(resultado.vagas) == 4


async def test_link_para_outro_host_ou_esquema_pula_a_vaga() -> None:
    lista = _html("if_lista").replace(
        'href="/carreiras/pt-br/node/2514"', 'href="https://evil.example/carreiras/pt-br/node/2514"'
    )
    lista = lista.replace('href="/carreiras/pt-br/node/2513"', 'href="javascript:alert(1)"')
    resultado, pedidos = await _coletar("if", _servir(_rotas_if() | {URL_IF: lista}))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["2517", "2512", "2511"]
    assert {p.url.host for p in pedidos} == {"portal.if.usp.br"}


async def test_id_repetido_conta_uma_vez() -> None:
    lista = _html("if_lista")
    linha = lista[lista.index('<tr class="row-1">') : lista.index("</tr>") + 5]
    repetida = lista.replace(linha, linha + linha)
    resultado, pedidos = await _coletar("if", _servir(_rotas_if() | {URL_IF: repetida}))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert [v.id_externo for v in _vagas(resultado)] == list(IDS_IF)
    assert len(pedidos) == 6


async def test_prazo_do_detalhe_vale_quando_a_lista_nao_traz() -> None:
    lista = _html("if_lista").replace(
        "Data Término Inscrição: 30/11/2026", "Data Término Inscrição:"
    )
    assert lista != _html("if_lista")
    resultado, _ = await _coletar("if", _servir(_rotas_if() | {URL_IF: lista}))
    vagas = _vagas(resultado)
    assert vagas[0].prazo == date(2026, 12, 31)  # o detalhe tem 31/12/2026
    assert vagas[1].prazo == date(2026, 11, 20)  # a lista manda quando traz


@pytest.mark.parametrize("data", ["31/02/2026", "ontem", "2026-11-30", "30/11/26", ""])
async def test_prazo_fora_de_formato_fica_sem_data(data: str) -> None:
    lista = _html("if_lista").replace("30/11/2026", data)
    detalhe = _detalhe_if("2517").replace("31/12/2026", data)
    rotas = _rotas_if() | {URL_IF: lista, NODE.format("2517"): detalhe}
    resultado, _ = await _coletar("if", _servir(rotas))
    assert resultado.estado == "ok"
    assert _vagas(resultado)[0].prazo is None


async def test_data_de_postagem_fora_de_formato_fica_sem_data() -> None:
    detalhe = _detalhe_if("2517").replace(
        '<div class="month">out</div>', '<div class="month">xx</div>'
    )
    assert detalhe != _detalhe_if("2517")
    resultado, _ = await _coletar("if", _servir(_rotas_if() | {NODE.format("2517"): detalhe}))
    assert resultado.estado == "ok"
    vagas = _vagas(resultado)
    assert vagas[0].publicada_em is None and vagas[1].publicada_em is not None


async def test_detalhe_ilegivel_mantem_a_vaga_da_lista_e_deixa_parcial() -> None:
    # o detalhe do IF sem o campo de descrição, o da FEA sem "Descrição da Vaga"
    sem_descricao = _html("if_vaga").replace("field-name-field-descricao", "field-name-outro")
    resultado, _ = await _coletar("if", _servir(_rotas_if() | {NODE.format("2517"): sem_descricao}))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    vagas = _vagas(resultado)
    assert len(vagas) == 5 and vagas[0].descricao == "" and vagas[1].descricao != ""
    assert vagas[0].titulo == "Duas Vagas de Doutorado FAPESP"
    sem_descricao = _html("fea_vaga").replace("Descrição da Vaga:", "Resumo:")
    resultado, _ = await _coletar(
        "fea", _servir(_rotas_fea() | {VAGA_FEA.format("132"): sem_descricao})
    )
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    vagas = _vagas(resultado)
    assert len(vagas) == 4 and vagas[0].salario_estruturado is None
    # sem detalhe, a vaga fica com o que a lista trouxe
    assert (vagas[0].salario_texto, vagas[0].prazo) == ("R$ 1.621", None)
    assert vagas[0].descricao == "Carga horária semanal: 30 horas"


async def test_erro_no_detalhe_mantem_a_vaga_da_lista_e_deixa_parcial() -> None:
    rotas = _rotas_fea() | {VAGA_FEA.format("134"): httpx.Response(404)}
    resultado, pedidos = await _coletar("fea", _servir(rotas))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    vagas = _vagas(resultado)
    assert [v.id_externo for v in vagas] == list(IDS_FEA)
    assert vagas[1].salario_texto == "R$ 2700" and "Vaga 134" not in vagas[1].descricao
    assert "Vaga 135\n" in vagas[2].descricao  # os outros detalhes seguem
    assert len(pedidos) == 5
    rotas_if = _rotas_if() | {NODE.format("2514"): httpx.Response(500)}
    resultado, _ = await _coletar("if", _servir(rotas_if))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert [v.id_externo for v in _vagas(resultado)] == list(IDS_IF)


async def test_item_pulado_ganha_de_detalhe_com_erro_no_motivo() -> None:
    lista = _html("fea_lista").replace('href="/vagas/134"', 'href="/outra/134"')
    rotas: dict[str, str | httpx.Response] = {**_rotas_fea(), URL_FEA: lista}
    rotas[VAGA_FEA.format("135")] = httpx.Response(404)
    resultado, _ = await _coletar("fea", _servir(rotas))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")


async def test_429_no_detalhe_para_os_detalhes_sem_perder_a_lista() -> None:
    rotas = _rotas_fea() | {VAGA_FEA.format("134"): httpx.Response(429)}
    resultado, pedidos = await _coletar("fea", _servir(rotas))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert [v.id_externo for v in _vagas(resultado)] == list(IDS_FEA)
    caminhos = [p.url.path for p in pedidos]
    assert "/vagas/135" not in caminhos and "/vagas/136" not in caminhos  # parou de detalhar
    assert caminhos[:2] == ["/", "/vagas/132"]


async def test_bloqueio_no_detalhe_falha_a_fonte() -> None:
    rotas = _rotas_if() | {NODE.format("2517"): httpx.Response(403)}
    resultado, pedidos = await _coletar("if", _servir(rotas))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 2  # a lista e o primeiro detalhe, sem repetir


@pytest.mark.parametrize("escopo", ["if", "fea"])
async def test_429_e_erro_de_rede(escopo: str) -> None:
    resultado, _ = await _coletar(escopo, httpx.Response(429))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.limite_atingido")
    resultado, pedidos = await _coletar(escopo, httpx.Response(500))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.erro_de_rede")
    assert len(pedidos) == 3  # duas novas tentativas do HttpEducado

    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    resultado, _ = await _coletar(escopo, cai)
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.erro_de_rede"


@pytest.mark.parametrize("escopo", ["if", "fea"])
async def test_bloqueio(escopo: str) -> None:
    resultado, pedidos = await _coletar(escopo, httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_escopo_desconhecido_e_erro() -> None:
    with pytest.raises(ValueError, match="poli"):
        await _coletar("poli", _resp(""))


async def test_detalhar_e_resolver_nao_se_aplicam() -> None:
    def recusa(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não faz pedido: {pedido.url}")

    relogio: Relogio = RelogioFalso()
    cli = ClienteEducado(
        httpx.MockTransport(recusa), relogio, _SemValidadores(), "0.1.0", resolver=_sem_dns
    )
    vaga = VagaColetada(
        fonte="usp", escopo="if", url=NODE.format("1"), titulo="x", empresa="y",
        descricao_formato="html",
    )  # fmt: skip
    try:
        http = cli.escopo()
        assert await usp.COLETOR.detalhar(vaga, http) is None
        with pytest.raises(ValueError):
            await usp.COLETOR.resolver("if", http)
    finally:
        await cli.fechar()
