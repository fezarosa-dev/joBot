import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import base, registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.coletores.portais import ciee
from jobot.nucleo.http import ClienteEducado, HttpEducado, LeitorValidadores, Validadores
from jobot.nucleo.modelo import Empresa, SalarioBruto, VagaColetada
from jobot.nucleo.relogio import Relogio
from jobot.nucleo.tratamento.locais import ler_locais
from jobot.nucleo.tratamento.rotulos import rotular

pytestmark = pytest.mark.anyio

RAIZ = Path(__file__).resolve().parents[3]
PASTA = RAIZ / "tests" / "fixtures" / "ciee"
API = "https://api.ciee.org.br/vagas/vitrine-vaga/publicadas"
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.json").read_text(encoding="utf-8")


def _json(caso: str, status: int = 200) -> httpx.Response:
    """A captura real é um recorte da página 0 (`last` falso); aqui ela vira a página única."""
    corpo = {**json.loads(_texto(caso)), "last": True}
    return httpx.Response(
        status, text=json.dumps(corpo), headers={"Content-Type": "application/json;charset=UTF-8"}
    )


class LeitorFixo:
    def ler(self, url: str) -> Validadores | None:
        return None


class LeitorComEtag:
    """Guardou um ETag para qualquer URL: um coletor que pedisse condicional o mandaria."""

    def ler(self, url: str) -> Validadores | None:
        return Validadores(etag='"v1"', last_modified="Sat, 01 Nov 2026 00:00:00 GMT")


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = "ESTAGIO",
    condicional: bool = False,
    max_pedidos: int | None = None,
    leitor: LeitorValidadores | None = None,
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
        httpx.MockTransport(servidor), relogio, leitor or LeitorFixo(), "0.1.0", resolver=_sem_dns
    )
    try:
        http: HttpEducado = cli.escopo(condicional=condicional, max_pedidos=max_pedidos)
        resultado = await ciee.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def _item(n: int, **campos: Any) -> dict[str, Any]:
    return {
        "codigoVaga": n,
        "tipoVaga": "ESTAGIO",
        "nomeEmpresa": "Empresa Exemplo",
        "areaAtuacao": None,
        "areaProfissional": "Administrativa",
        "salario": None,
        "bolsaAuxilio": None,
        "tipoAuxilioBolsa": None,
        "tipoSalario": None,
        "bolsaAuxilioDe": None,
        "bolsaAuxilioAte": None,
        "salarioDe": None,
        "salarioAte": None,
        "beneficios": [],
        "descricao": None,
        "local": {"cidade": "Recife", "uf": "PE", "bairro": "Boa Viagem"},
        "horarioEntrada": None,
        "horarioSaida": None,
        "atividades": [],
        "requisitos": {"semestreInicio": 0, "semestreFinal": 0},
        "nivelEscolar": "SU",
    } | campos


def _pagina(
    inicio: int, quantos: int, *, ultima: bool | None, itens: list[dict[str, Any]] | None = None
) -> httpx.Response:
    corpo: dict[str, Any] = {
        "content": itens
        if itens is not None
        else [_item(n + 1) for n in range(inicio, inicio + quantos)]  # codigoVaga é positivo
    }
    if ultima is not None:
        corpo["last"] = ultima
    return httpx.Response(200, json=corpo)


def _com(**campos: Any) -> httpx.Response:
    # texto, não `json=`: o httpx recusa NaN e Infinity, que `json.loads` aceita
    corpo = {"last": True, "content": [_item(1, **campos)]}
    return httpx.Response(200, text=json.dumps(corpo))


async def _vaga_com(**campos: Any) -> VagaColetada:
    resultado, _ = await _coletar(_com(**campos))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert len(resultado.vagas) == 1
    return _vagas(resultado)[0]


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = ciee.COLETOR
    assert registro.descobrir()["ciee"] is prova
    limites = registro.limites(prova.chave)
    assert limites.leva == prova.leva == "B"
    assert (prova.intervalo_min, prova.max_pedidos, prova.espera_s) == (None, None, 1.0)
    assert prova.por_escopo == {} and prova.credito_obrigatorio is False
    assert prova.hosts == ("api.ciee.org.br",)


def test_escopos_sao_as_duas_modalidades() -> None:
    vazio = ContextoColeta(empresas=[], termos=[], paises=[])
    assert list(ciee.COLETOR.escopos(vazio)) == ["ESTAGIO", "APRENDIZ"]
    cheio = ContextoColeta(
        empresas=[Empresa(nome="X", fonte="ciee", identificador="x")], termos=["dev"], paises=["BR"]
    )
    assert list(ciee.COLETOR.escopos(cheio)) == ["ESTAGIO", "APRENDIZ"]


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_json("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 5 and len(pedidos) == 1
    primeira, superior = vagas[0], vagas[1]
    assert primeira.fonte == "ciee" and primeira.escopo == "ESTAGIO"
    assert primeira.url == "https://portal.ciee.org.br/quero-uma-vaga/?codigoVaga=6299866"
    assert primeira.id_externo == "6299866"
    assert primeira.titulo == "Estágio - Ensino Médio"
    assert primeira.empresa == "Pessoa Exemplo LTDA"
    assert primeira.locais == ("São Vicente, SP",)
    assert primeira.contrato_declarado == "Estágio"
    assert primeira.modalidade_declarada is None
    assert primeira.descricao_formato == "texto"
    assert primeira.salario_estruturado == SalarioBruto(
        moeda="BRL", minimo_unidades=1300, maximo_unidades=None, periodo="mes"
    )
    assert primeira.url_candidatura is None and primeira.salario_texto is None
    assert superior.titulo == "Estágio - Saúde - Superior"
    assert superior.locais == ("Teresina, PI",)
    assert all(v.url.startswith("https://portal.ciee.org.br/") for v in vagas)


async def test_descricao_junta_ramo_atividades_horario_e_semestres() -> None:
    resultado, _ = await _coletar(_json("normal"))
    assert len(resultado.vagas) == 5
    primeira, superior = _vagas(resultado)[:2]
    assert "Auxiliar a separação de produtos e pedidos" in primeira.descricao
    assert "Comércio varejista de artigos do vestuário e acessórios" in primeira.descricao
    assert "13:30" in primeira.descricao and "19:00" in primeira.descricao
    assert "1º ao 4º semestre" in primeira.descricao
    assert "4º ao 7º semestre" in superior.descricao
    assert "None" not in primeira.descricao and "null" not in primeira.descricao
    assert "Horário" not in superior.descricao  # entrada e saída nulas (A_COMBINAR)


async def test_descricao_com_beneficios_e_sem_nada() -> None:
    vaga = await _vaga_com(
        beneficios=[{"beneficio": "Vale-transporte"}, {"beneficio": "Seguro"}, {"x": 1}, "y"]
    )
    assert "Vale-transporte" in vaga.descricao and "Seguro" in vaga.descricao
    assert (await _vaga_com()).descricao == ""


async def test_aprendiz() -> None:
    resultado, pedidos = await _coletar(_json("aprendiz"), escopo="APRENDIZ")
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert len(pedidos) == 1 and pedidos[0].url.params["tipoVaga"] == "APRENDIZ"
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert primeira.escopo == "APRENDIZ" and primeira.contrato_declarado == "Aprendiz"
    assert primeira.id_externo == "6299857"
    assert primeira.titulo == "Aprendiz - Arco Administrativo - Técnico"
    assert (
        primeira.empresa == "SURGITEC COMERCIO E FABRICACAO DE PRODUTOS MEDICOS E HOSPITALARES LTDA"
    )
    assert primeira.locais == ("Boituva, SP",)
    assert primeira.salario_estruturado == SalarioBruto(
        moeda="BRL", minimo_unidades=1600, maximo_unidades=None, periodo="mes"
    )
    assert "Semestre" not in primeira.descricao  # semestres 0 e 0 não dizem nada
    assert vagas[2].salario_estruturado is not None
    assert vagas[2].salario_estruturado.minimo_unidades == 1069.48


async def test_modalidade_do_item_vale_sobre_o_escopo() -> None:
    # a página sem filtro mistura as duas modalidades: o contrato sai do item, não do escopo
    resultado, _ = await _coletar(_json("sem_filtro"))
    assert len(resultado.vagas) == 5
    contratos = {v.id_externo: v.contrato_declarado for v in _vagas(resultado)}
    assert contratos["6299857"] == "Aprendiz" and contratos["6299866"] == "Estágio"
    titulos = {v.id_externo: v.titulo for v in _vagas(resultado)}
    assert titulos["6299857"].startswith("Aprendiz - ")


async def test_rotulos_do_tratamento_leem_contrato_e_titulo() -> None:
    resultado, _ = await _coletar(_json("sem_filtro"))
    assert len(resultado.vagas) == 5
    por_id = {v.id_externo: v for v in _vagas(resultado)}
    assert (
        rotular(
            por_id["6299866"], por_id["6299866"].descricao, ler_locais(por_id["6299866"].locais)
        ).contrato
        == "estagio"
    )
    assert (
        rotular(
            por_id["6299857"], por_id["6299857"].descricao, ler_locais(por_id["6299857"].locais)
        ).contrato
        == "aprendiz"
    )


@pytest.mark.parametrize(
    ("campos", "titulo"),
    [
        (
            {"areaProfissional": "Administrativa", "nivelEscolar": "SU"},
            "Estágio - Administrativa - Superior",
        ),
        (
            {"areaProfissional": "Administrativa", "nivelEscolar": "EM"},
            "Estágio - Administrativa - Médio",
        ),
        (
            {"areaProfissional": "Administrativa", "nivelEscolar": "TE"},
            "Estágio - Administrativa - Técnico",
        ),
        (
            {"areaProfissional": "Administrativa", "nivelEscolar": "T"},
            "Estágio - Administrativa - Técnico",
        ),
        (
            {"areaProfissional": "Administrativa", "nivelEscolar": "EF"},
            "Estágio - Administrativa - Fundamental",
        ),
        ({"areaProfissional": "Administrativa", "nivelEscolar": "XX"}, "Estágio - Administrativa"),
        ({"areaProfissional": "Administrativa", "nivelEscolar": None}, "Estágio - Administrativa"),
        (
            {"areaProfissional": None, "areaAtuacao": "Arco Vendas"},
            "Estágio - Arco Vendas - Superior",
        ),
        ({"areaProfissional": "  ", "areaAtuacao": None}, "Estágio - Superior"),
        ({"areaProfissional": "Ensino Médio", "nivelEscolar": "EM"}, "Estágio - Ensino Médio"),
        ({"areaProfissional": " Direito ", "nivelEscolar": "SU"}, "Estágio - Direito - Superior"),
    ],
)
async def test_titulo_montado_de_area_e_nivel(campos: dict[str, Any], titulo: str) -> None:
    assert (await _vaga_com(**campos)).titulo == titulo


async def test_sem_data_de_publicacao_nem_prazo() -> None:
    resultado, _ = await _coletar(_json("normal"))
    for vaga in _vagas(resultado):
        assert vaga.publicada_em is None and vaga.prazo is None and vaga.inicio is None
    # a fonte não traz data nem se a gente inventar campo com cara de data
    vaga = await _vaga_com(dataPublicacao="2026-11-01T00:00:00Z", publicadaEm=1700000000)
    assert vaga.publicada_em is None


async def test_link_leva_o_codigo_da_vaga() -> None:
    assert (await _vaga_com(codigoVaga=77)).url == (
        "https://portal.ciee.org.br/quero-uma-vaga/?codigoVaga=77"
    )
    assert (await _vaga_com(codigoVaga="88")).url.endswith("?codigoVaga=88")


async def test_local_sem_cidade_ou_sem_uf() -> None:
    assert (await _vaga_com(local={"cidade": "Recife", "uf": None})).locais == ("Recife",)
    assert (await _vaga_com(local={"cidade": None, "uf": "PE"})).locais == ("PE",)
    assert (await _vaga_com(local=None)).locais == ()
    assert (await _vaga_com(local={"cidade": 7, "uf": ["PE"]})).locais == ()


@pytest.mark.parametrize(
    ("campos", "esperado"),
    [
        (
            {"bolsaAuxilio": 1300, "tipoAuxilioBolsa": "Mensal"},
            SalarioBruto(moeda="BRL", minimo_unidades=1300, periodo="mes"),
        ),
        (
            {"bolsaAuxilio": 12.5, "tipoAuxilioBolsa": "Hora"},
            SalarioBruto(moeda="BRL", minimo_unidades=12.5, periodo="hora"),
        ),
        (
            {"bolsaAuxilio": 900, "tipoAuxilioBolsa": "Quinzenal"},
            SalarioBruto(moeda="BRL", minimo_unidades=900, periodo=None),
        ),
        (
            {
                "bolsaAuxilio": None,
                "bolsaAuxilioDe": 800,
                "bolsaAuxilioAte": 1200,
                "tipoAuxilioBolsa": "Mensal",
            },
            SalarioBruto(moeda="BRL", minimo_unidades=800, maximo_unidades=1200, periodo="mes"),
        ),
        (
            {
                "bolsaAuxilio": 0,
                "bolsaAuxilioDe": 800,
                "bolsaAuxilioAte": None,
                "tipoAuxilioBolsa": "Mensal",
            },
            SalarioBruto(moeda="BRL", minimo_unidades=800, periodo="mes"),
        ),
        (
            {"salario": 1069.48, "tipoSalario": "Mensal"},
            SalarioBruto(moeda="BRL", minimo_unidades=1069.48, periodo="mes"),
        ),
        (
            {"salario": None, "salarioDe": 700, "salarioAte": 900, "tipoSalario": "Hora"},
            SalarioBruto(moeda="BRL", minimo_unidades=700, maximo_unidades=900, periodo="hora"),
        ),
    ],
)
async def test_salario(campos: dict[str, Any], esperado: SalarioBruto) -> None:
    assert (await _vaga_com(**campos)).salario_estruturado == esperado


@pytest.mark.parametrize("invalido", [None, 0, -5, True, False, "1300", math.nan, math.inf, [], {}])
async def test_salario_invalido_nao_vira_salario(invalido: object) -> None:
    vaga = await _vaga_com(bolsaAuxilio=invalido, tipoAuxilioBolsa="Mensal")
    assert vaga.salario_estruturado is None


async def test_salario_gigante_nao_estoura() -> None:
    assert (await _vaga_com(bolsaAuxilio=10**400)).salario_estruturado is None
    assert (await _vaga_com(bolsaAuxilio=1e308)).salario_estruturado is not None
    texto = json.dumps({"last": True, "content": [_item(1)]})
    resultado, _ = await _coletar(
        httpx.Response(200, text=texto.replace('"bolsaAuxilio": null', '"bolsaAuxilio": 1e400'))
    )  # json.loads lê 1e400 como infinito
    assert resultado.estado == "ok" and len(resultado.vagas) == 1
    assert _vagas(resultado)[0].salario_estruturado is None


async def test_vazio() -> None:
    resultado, pedidos = await _coletar(_json("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)
    assert len(pedidos) == 1


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_json("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["6299866"]


@pytest.mark.parametrize(
    "corpo",
    ['{"results": []}', "[]", '{"content": {}}', "isto não é json", '{"content": [1, "x"]}'],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(httpx.Response(200, text=corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


@pytest.mark.parametrize(
    "estragos",
    [
        {"codigoVaga": None},
        {"codigoVaga": True},
        {"codigoVaga": ""},
        {"codigoVaga": "abc"},
        {"nomeEmpresa": None},
        {"nomeEmpresa": 12},
    ],
)
async def test_item_sem_campo_obrigatorio_e_pulado_e_deixa_parcial(
    estragos: dict[str, Any],
) -> None:
    resposta = _pagina(0, 0, ultima=True, itens=[_item(1), _item(2, **estragos), _item(3)])
    resultado, _ = await _coletar(resposta)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["1", "3"]


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    vaga = await _vaga_com(
        areaProfissional=7,
        areaAtuacao=["x"],
        nivelEscolar=3,
        tipoVaga=None,
        atividades="texto solto",
        descricao=5,
        beneficios="vale",
        horarioEntrada=1,
        horarioSaida=[],
        requisitos="nada",
        local="Recife",
    )
    assert vaga.titulo == "Estágio"  # sem área e sem nível, a modalidade vem do escopo
    assert (vaga.locais, vaga.descricao, vaga.salario_estruturado) == ((), "", None)
    assert vaga.contrato_declarado == "Estágio"


async def test_paginacao_segue_ate_last() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = int(pedido.url.params["page"])
        return _pagina(n * 1000, 1000 if n < 2 else 186, ultima=n == 2)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 3)
    assert [p.url.params["page"] for p in pedidos] == ["0", "1", "2"]
    assert len(resultado.vagas) == 2186
    assert len({v.id_externo for v in _vagas(resultado)}) == 2186


async def test_ultima_pagina_cheia_nao_pede_a_seguinte() -> None:
    # `last` manda, não o tamanho da página: página cheia com last=true encerra
    resultado, pedidos = await _coletar(_pagina(0, 1000, ultima=True))
    assert (resultado.estado, len(resultado.vagas), len(pedidos)) == ("ok", 1000, 1)


async def test_last_ausente_ou_estranho_emite_a_pagina_e_fica_parcial() -> None:
    for ultima in (None, "true", 1):
        corpo: dict[str, Any] = {"content": [_item(1), _item(2)]}
        if ultima is not None:
            corpo["last"] = ultima
        resultado, pedidos = await _coletar(httpx.Response(200, json=corpo))
        assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
        assert [v.id_externo for v in _vagas(resultado)] == ["1", "2"]
        assert len(pedidos) == 1


async def test_pagina_vazia_sem_last_encerra_em_vez_de_repetir() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = int(pedido.url.params["page"])
        return _pagina(0, 3, ultima=False) if n == 0 else _pagina(0, 0, ultima=False)

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert (len(resultado.vagas), len(pedidos)) == (3, 2)


async def test_pagina_seguinte_ilegivel_mantem_as_vagas_lidas() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        if int(pedido.url.params["page"]) == 0:
            return _pagina(0, 3, ultima=False)
        return httpx.Response(200, text="<html>manutenção</html>")

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["1", "2", "3"]
    assert len(pedidos) == 2


async def test_pagina_seguinte_com_erro_de_rede_fica_parcial_com_o_que_leu() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        if int(pedido.url.params["page"]) == 0:
            return _pagina(0, 3, ultima=False)
        return httpx.Response(500)

    resultado, _ = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.erro_de_rede")
    assert len(resultado.vagas) == 3


async def test_31o_pedido_nao_sai() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        n = int(pedido.url.params["page"])
        return _pagina(n * 10, 10, ultima=False)  # ids distintos por página; nunca termina

    resultado, pedidos = await _coletar(pagina)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.limite_atingido")
    assert (resultado.pedidos, len(pedidos)) == (30, 30)
    assert len(resultado.vagas) == 300


async def test_orcamento_de_pedidos_do_escopo_fica_no_limite() -> None:
    def pagina(pedido: httpx.Request) -> httpx.Response:
        return _pagina(int(pedido.url.params["page"]) * 10, 10, ultima=False)

    resultado, pedidos = await _coletar(pagina, max_pedidos=2)
    assert (resultado.estado, resultado.motivo) == ("no_limite", "saude.orcamento")
    assert len(pedidos) == 2


async def test_429_e_erro_de_rede() -> None:
    resultado, _ = await _coletar(httpx.Response(429))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.limite_atingido")
    resultado, pedidos = await _coletar(httpx.Response(500))
    assert (resultado.estado, resultado.motivo) == ("falhou", "saude.erro_de_rede")
    assert len(pedidos) == 3  # duas novas tentativas do HttpEducado

    def cai(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    resultado, _ = await _coletar(cai)
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.erro_de_rede"


async def test_sem_validador_na_resposta_nunca_e_304() -> None:
    # a captura não mostrou ETag nem Last-Modified: o coletor não pede condicional e nunca
    # devolve SEM_MUDANCA (um 304 chegaria como "ok" vazio e fecharia vaga). O leitor guarda
    # um ETag e o servidor responde 304 a quem o mandar: pedir condicional deixa o teste vermelho.
    def servidor(pedido: httpx.Request) -> httpx.Response:
        if pedido.headers.get("If-None-Match") or pedido.headers.get("If-Modified-Since"):
            return httpx.Response(304)
        return _json("normal")

    resultado, pedidos = await _coletar(servidor, condicional=True, leitor=LeitorComEtag())
    assert resultado.estado == "ok" and resultado.vagas
    assert resultado.vagas is not base.SEM_MUDANCA
    assert pedidos[0].headers.get("If-None-Match") is None
    assert pedidos[0].headers.get("If-Modified-Since") is None


async def test_empresa_em_branco_vira_ciee() -> None:
    # empresa confidencial: a fonte manda o nome vazio; a vaga fica, como no IEL ("IEL <estado>")
    resposta = _pagina(
        0,
        0,
        ultima=True,
        itens=[_item(1, nomeEmpresa=""), _item(2, nomeEmpresa="   "), _item(3)],
    )
    resultado, _ = await _coletar(resposta)
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert [(v.id_externo, v.empresa) for v in _vagas(resultado)] == [
        ("1", "CIEE"),
        ("2", "CIEE"),
        ("3", "Empresa Exemplo"),
    ]


@pytest.mark.parametrize("codigo", [0, "0", "000"])
async def test_codigo_zero_e_recusado(codigo: object) -> None:
    resposta = _pagina(0, 0, ultima=True, itens=[_item(1), _item(2, codigoVaga=codigo)])
    resultado, _ = await _coletar(resposta)
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["1"]


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


@pytest.mark.parametrize("escopo", ["ESTAGIO", "APRENDIZ"])
async def test_endereco_e_parametros(escopo: str) -> None:
    _, pedidos = await _coletar(_json("vazio"), escopo=escopo)
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert f"{pedido.url.scheme}://{pedido.url.host}{pedido.url.path}" == API
    assert dict(pedido.url.params) == {
        "page": "0",
        "size": "1000",
        "sort": "codigoVaga,desc",
        "tipoVaga": escopo,
    }
    for proibido in ("origin", "cookie", "authorization", "referer"):
        assert proibido not in pedido.headers


@pytest.mark.parametrize("escopo", ["", "estagio", "TODOS", "ESTAGIO,APRENDIZ", "ESTAGIO "])
async def test_escopo_que_nao_e_do_coletor_levanta(escopo: str) -> None:
    pedidos: list[httpx.Request] = []

    def servidor(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return _json("vazio")

    with pytest.raises(ValueError):
        await _coletar(servidor, escopo=escopo)
    assert pedidos == []


async def test_detalhar_nao_faz_nada() -> None:
    vaga = await _vaga_com()
    assert await ciee.COLETOR.detalhar(vaga, None) is None  # type: ignore[arg-type]


async def test_resolver_nao_se_aplica() -> None:
    with pytest.raises(ValueError):
        await ciee.COLETOR.resolver("qualquer", None)  # type: ignore[arg-type]
