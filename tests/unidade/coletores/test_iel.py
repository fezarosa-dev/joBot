import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from apoio.relogio import RelogioFalso
from jobot.nucleo.coletores import registro
from jobot.nucleo.coletores.base import Coletor, ContextoColeta, ResultadoEscopo
from jobot.nucleo.coletores.portais import iel
from jobot.nucleo.http import ClienteEducado, HttpEducado, Validadores
from jobot.nucleo.modelo import Empresa, VagaColetada
from jobot.nucleo.relogio import Relogio

pytestmark = pytest.mark.anyio

PASTA = Path(__file__).resolve().parents[2] / "fixtures" / "iel"
URL = "https://carreiras.iel.org.br/PE"
BRASILIA = timezone(timedelta(hours=-3))
Responder = Callable[[httpx.Request], httpx.Response]


def _texto(caso: str) -> str:
    return (PASTA / f"{caso}.html").read_text(encoding="utf-8")


def _html(caso_ou_texto: str, status: int = 200) -> httpx.Response:
    texto = _texto(caso_ou_texto) if (PASTA / f"{caso_ou_texto}.html").is_file() else caso_ou_texto
    return httpx.Response(status, text=texto, headers={"Content-Type": "text/html; charset=utf-8"})


def _push(rsc: str) -> str:
    """Um bloco `self.__next_f.push([1, ...])` como o Next.js escreve (com o escape de `<`)."""
    js = json.dumps([1, rsc], ensure_ascii=False).replace("<", "\\u003c")
    return f"<script>self.__next_f.push({js})</script>"


def _pagina(*objetos: object) -> str:
    """Página com cada objeto duas vezes, como o site faz."""
    lista = json.dumps(list(objetos), ensure_ascii=False)
    rsc = f'1c:["$","$L1d",null,{{"vagas":{lista},"vagasFiltradas":{lista}}}]\n'
    return f"<html><body>{_push(rsc)}</body></html>"


def _objetos(caso: str = "normal") -> list[dict[str, object]]:
    """Os objetos `vagaOrigem` do exemplo, sem repetição, para variar no teste."""
    resultado: list[dict[str, object]] = []
    vistos: set[object] = set()
    blocos = re.findall(r"self\.__next_f\.push\((\[1,.*?\])\)</script>", _texto(caso))
    texto = "".join(json.loads(b)[1] for b in blocos)
    decodificador = json.JSONDecoder()
    inicio = texto.find('{"vagaOrigem"')
    while inicio != -1:
        objeto, fim = decodificador.raw_decode(texto, inicio)
        if objeto["vagaIdentificador"] not in vistos:
            vistos.add(objeto["vagaIdentificador"])
            resultado.append(objeto)
        inicio = texto.find('{"vagaOrigem"', fim)
    return resultado


class LeitorFixo:
    def __init__(self, guardados: dict[str, Validadores] | None = None) -> None:
        self.guardados = guardados or {}

    def ler(self, url: str) -> Validadores | None:
        return self.guardados.get(url)


async def _sem_dns(host: str) -> list[str]:
    raise AssertionError(f"teste não consulta DNS: {host}")


async def _coletar(
    *respostas: httpx.Response | Responder,
    escopo: str = "PE",
    leitor: LeitorFixo | None = None,
    condicional: bool = False,
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
        http: HttpEducado = cli.escopo(condicional=condicional)
        resultado = await iel.COLETOR.coletar(escopo, http)
    finally:
        await cli.fechar()
    return resultado, pedidos


def _vagas(resultado: ResultadoEscopo) -> list[VagaColetada]:
    vagas = [v for v in resultado.vagas if isinstance(v, VagaColetada)]
    assert len(vagas) == len(resultado.vagas)
    return vagas


def test_coletor_registrado_com_a_chave_de_fontes_json() -> None:
    prova: Coletor = iel.COLETOR
    assert registro.descobrir()["iel"] is prova
    limites = registro.limites("iel")
    assert limites.leva == prova.leva == "B"
    assert prova.hosts == ("carreiras.iel.org.br",)
    assert (prova.intervalo_min, prova.max_pedidos) == (limites.intervalo_min, limites.max_pedidos)
    assert (prova.espera_s, prova.credito_obrigatorio) == (limites.espera_s, False)
    assert prova.por_escopo == limites.por_escopo


def test_escopos_por_uf_quando_a_busca_e_do_brasil() -> None:
    empresas = [Empresa(nome="Vitta", fonte="greenhouse", identificador="vitta")]
    com_brasil = ContextoColeta(empresas=empresas, termos=["dev"], paises=["US", " br "])
    escopos = list(iel.COLETOR.escopos(com_brasil))
    assert escopos == list(iel.UFS_COM_VAGA)
    assert len(escopos) == 19 and "PE" in escopos and len(set(escopos)) == 19
    assert all(len(uf) == 2 and uf.isupper() for uf in escopos)
    assert list(iel.COLETOR.escopos(ContextoColeta((), ["dev"], ["US"]))) == []
    assert list(iel.COLETOR.escopos(ContextoColeta((), (), ()))) == []


async def test_normal() -> None:
    resultado, pedidos = await _coletar(_html("normal"))
    assert (resultado.estado, resultado.motivo, resultado.pedidos) == ("ok", None, 1)
    vagas = _vagas(resultado)
    assert len(vagas) == 5
    primeira = vagas[0]
    assert (primeira.fonte, primeira.escopo) == ("iel", "PE")
    assert primeira.url == "https://carreiras.iel.org.br/PE/vaga/efetivo/33340/profissional"
    assert primeira.titulo == "Profissional"
    assert primeira.empresa == "IEL Pernambuco"  # vagaEmpresaNome vazio: empresa em sigilo
    assert primeira.id_externo == "33340"
    assert primeira.locais == ("Araripina, PE",)
    assert primeira.modalidade_declarada == "Presencial"
    assert primeira.contrato_declarado == "Efetivo"
    assert primeira.salario_texto == "R$ 5000.00"  # como veio, sem interpretar
    assert primeira.publicada_em == datetime(2026, 11, 13, 15, 6, tzinfo=BRASILIA)
    assert primeira.descricao_formato == "texto"
    assert primeira.descricao.startswith("Atividades: Ativodade para teste")
    assert "Requisitos: Administração. Requisitos Teste" in primeira.descricao
    assert "Escolaridade: Ensino Superior/Graduação Completo a Pós-doutorado" in primeira.descricao
    assert "Cursos: ADMINISTRAÇÃO;" in primeira.descricao
    assert "Benefícios" not in primeira.descricao  # o campo não veio nesta vaga
    assert primeira.prazo is None and primeira.url_candidatura is None
    estagio = vagas[1]
    assert estagio.contrato_declarado == "Estágio"
    assert "Benefícios: Auxílio Transporte (ajuda em espécie)  - 180,40;" in estagio.descricao
    assert vagas[4].salario_texto is None  # 33324 não traz vagaSalario
    assert all(v.url.startswith("https://carreiras.iel.org.br/PE/vaga/") for v in vagas)
    assert len(pedidos) == 1


async def test_sem_repetir_vaga_identificador() -> None:
    texto = _texto("normal")
    assert texto.count('{\\"vagaOrigem') == 10  # cada vaga aparece duas vezes no HTML
    assert texto.count("self.__next_f.push([1,") == 2  # a linha RSC vem partida em dois blocos
    resultado, _ = await _coletar(_html("normal"))
    ids = [v.id_externo for v in _vagas(resultado)]
    assert ids == ["33340", "33337", "33328", "33327", "33324"]


async def test_copia_ilegivel_nao_derruba_a_legivel_da_mesma_vaga() -> None:
    boa, outra = _objetos()[:2]
    ruim = boa | {"vagaTitulo": ""}
    lista_a = json.dumps([ruim, outra], ensure_ascii=False)
    lista_b = json.dumps([boa, outra], ensure_ascii=False)
    rsc = f'1c:["$","$L1d",null,{{"vagas":{lista_a},"vagasFiltradas":{lista_b}}}]\n'
    resultado, _ = await _coletar(_html(f"<html>{_push(rsc)}</html>"))
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    assert [v.id_externo for v in _vagas(resultado)] == ["33340", "33337"]


async def test_le_os_objetos_como_texto_sem_executar_javascript() -> None:
    objeto = _objetos()[0] | {"vagaTitulo": "</script><script>alert(1)</script> Analista"}
    texto = (
        "<script>self.__next_f.push([1, eval('x')])</script>"  # não é JSON: ignorado
        "<script>self.__next_f.push([2,null])</script>" + _pagina(objeto)
    )
    resultado, _ = await _coletar(_html(texto))
    assert resultado.estado == "ok"
    assert [v.titulo for v in _vagas(resultado)] == ["</script><script>alert(1)</script> Analista"]


async def test_empresa_com_nome_vale_o_nome() -> None:
    objeto = _objetos()[0] | {"vagaEmpresaNome": " Indústria Exemplo "}
    sem_estado = _objetos()[1] | {"vagaEstado": ""}
    resultado, _ = await _coletar(_html(_pagina(objeto, sem_estado)))
    vagas = _vagas(resultado)
    assert [v.empresa for v in vagas] == ["Indústria Exemplo", "IEL PE"]


async def test_valores_de_referencia_do_rsc() -> None:
    """`$undefined` (prop ausente) não vira texto; `$$` é o `$` escapado do RSC."""
    objeto = _objetos()[0] | {"vagaSalario": "$undefined", "vagaModeloTrabalho": "$$Remoto"}
    resultado, _ = await _coletar(_html(_pagina(objeto)))
    vaga = _vagas(resultado)[0]
    assert (vaga.salario_texto, vaga.modalidade_declarada) == (None, "$Remoto")


def _linha_t(id_rsc: str, texto: str) -> str:
    """Linha de texto do RSC: `<id>:T<bytes UTF-8 em hex>,<texto>`, sem `\\n` no fim."""
    return f"{id_rsc}:T{len(texto.encode()):x},{texto}"


async def test_texto_longo_vem_da_linha_t_do_rsc() -> None:
    """String de 1024 caracteres ou mais sai numa linha T e o campo guarda só `$<id>`."""
    longo = "Atenção ao público, emissão de relatórios e conferência de notas. " * 20 + "até 2025"
    cursos = "Excel avançado\nGestão de estoque"
    objeto = _objetos()[0] | {"vagaObservacao": "$2a", "vagaCursos": "$2b"}
    lista = json.dumps([objeto], ensure_ascii=False)
    rsc = (
        _linha_t("2a", longo)  # o texto termina em dígito e a linha seguinte vem colada
        + _linha_t("2b", cursos)
        + f'1c:["$","$L1d",null,{{"vagas":{lista},"vagasFiltradas":{lista}}}]\n'
    )
    meio = rsc.index("emissão", 500)  # a linha T partida em dois blocos, no meio de um acento
    resultado, _ = await _coletar(
        _html(f"<html>{_push(rsc[: meio + 3])}{_push(rsc[meio + 3 :])}</html>")
    )
    assert (resultado.estado, resultado.motivo) == ("ok", None)
    descricao = _vagas(resultado)[0].descricao
    assert f"Atividades: {longo.strip()}" in descricao
    assert f"Cursos: {cursos}" in descricao


@pytest.mark.parametrize("referencia", ["$3f", "$L1d", "$@4"])
async def test_referencia_sem_texto_nao_some_calada(referencia: str) -> None:
    """Referência do RSC sem texto resolvido pula a vaga (parcial), nunca descrição vazia."""
    objetos = _objetos()[:2]
    objetos[1] = objetos[1] | {"vagaRequisitos": referencia}
    resultado, _ = await _coletar(_html(_pagina(*objetos)))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["33340"]


async def test_vaga_inclusao_sem_fuso_vale_horario_de_brasilia() -> None:
    objetos = _objetos()[:4]
    objetos[0] = objetos[0] | {"vagaInclusao": "2026-11-13T15:06:00"}
    objetos[1] = objetos[1] | {"vagaInclusao": "2026-11-13T14:12:00Z"}
    objetos[2] = objetos[2] | {"vagaInclusao": "ontem"}
    objetos[3] = objetos[3] | {"vagaInclusao": None}
    resultado, _ = await _coletar(_html(_pagina(*objetos)))
    vagas = _vagas(resultado)
    assert resultado.estado == "ok"
    assert vagas[0].publicada_em == datetime(2026, 11, 13, 15, 6, tzinfo=BRASILIA)
    assert vagas[0].publicada_em is not None
    assert vagas[0].publicada_em.utcoffset() == timedelta(hours=-3)
    assert vagas[1].publicada_em == datetime(2026, 11, 13, 14, 12, tzinfo=UTC)
    assert (vagas[2].publicada_em, vagas[3].publicada_em) == (None, None)


async def test_campo_opcional_estranho_nao_derruba_a_vaga() -> None:
    objeto = _objetos()[0] | {
        "vagaSalario": 5000,
        "vagaCidade": None,
        "vagaObservacao": ["x"],
        "vagaRequisitos": None,
        "vagaCursos": {},
        "vagaModeloTrabalho": True,
        "vagaTipo": "",
    }
    resultado, _ = await _coletar(_html(_pagina(objeto)))
    assert resultado.estado == "ok"
    vaga = _vagas(resultado)[0]
    assert (vaga.salario_texto, vaga.locais) == (None, ("PE",))
    assert (vaga.modalidade_declarada, vaga.contrato_declarado) == (None, None)
    assert "Atividades" not in vaga.descricao and "Cursos" not in vaga.descricao


async def test_url_fora_de_http_pula_a_vaga() -> None:
    objetos = _objetos()[:2]
    objetos[1] = objetos[1] | {"vagaUrl": "javascript:alert(1)"}
    resultado, _ = await _coletar(_html(_pagina(*objetos)))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["33340"]


@pytest.mark.parametrize("identificador", [None, "", True, 1.5, [], " "])
async def test_vaga_sem_identificador_e_pulada(identificador: object) -> None:
    objetos = _objetos()[:2]
    objetos[1] = objetos[1] | {"vagaIdentificador": identificador}
    resultado, _ = await _coletar(_html(_pagina(*objetos)))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["33340"]


async def test_identificador_numerico_vale() -> None:
    objeto = _objetos()[0] | {"vagaIdentificador": 33340}
    resultado, _ = await _coletar(_html(_pagina(objeto)))
    assert [v.id_externo for v in _vagas(resultado)] == ["33340"]


async def test_vazio() -> None:
    resultado, _ = await _coletar(_html("vazio"))
    assert (resultado.vagas, resultado.estado, resultado.motivo) == ((), "ok", None)


async def test_formato_mudou() -> None:
    resultado, _ = await _coletar(_html("formato_mudou"))
    assert (resultado.estado, resultado.motivo) == ("parcial", "saude.formato_mudou")
    assert [v.id_externo for v in _vagas(resultado)] == ["33340", "33328", "33327", "33324"]


@pytest.mark.parametrize(
    "corpo",
    [
        "<html><body><p>Manutenção</p></body></html>",  # sem nenhum bloco RSC
        "<html><script>self.__next_f.push([2,null])</script></html>",  # sem bloco de texto
        _push('1c:{"vagaOrigem":"x","vagaIdentificador":"1"'),  # objeto cortado
        _pagina({"vagaOrigem": "x", "vagaIdentificador": "1"}),  # sem título nem url
        _pagina({"vagaOrigem": "x"}, {"vagaOrigem": "y"}),
        "isto não é html",
    ],
)
async def test_formato_mudou_sem_vaga_legivel_falhou(corpo: str) -> None:
    resultado, _ = await _coletar(_html(corpo))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.formato_mudou"


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


async def test_bloqueio() -> None:
    resultado, pedidos = await _coletar(httpx.Response(403))
    assert (resultado.vagas, resultado.estado) == ((), "falhou")
    assert resultado.motivo == "saude.bloqueio"
    assert len(pedidos) == 1


async def test_endereco_e_parametros() -> None:
    _, pedidos = await _coletar(_html("vazio"), escopo="SC")
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.method == "GET"
    assert str(pedido.url) == "https://carreiras.iel.org.br/SC"
    assert dict(pedido.url.params) == {}


async def test_sem_pedido_condicional() -> None:
    """A conferência não viu `ETag` nem `Last-Modified`: o coletor nunca pede condicional."""
    leitor = LeitorFixo({URL: Validadores('"v1"', "Fri, 13 Nov 2026 14:44:36 GMT")})
    _, pedidos = await _coletar(_html("normal"), leitor=leitor, condicional=True)
    assert len(pedidos) == 1
    assert pedidos[0].headers.get("If-None-Match") is None
    assert pedidos[0].headers.get("If-Modified-Since") is None


@pytest.mark.parametrize("escopo", ["pe", "", "PE/vaga", "../PE", "PEX", "P1"])
async def test_escopo_que_nao_e_uf_recusado_sem_pedido(escopo: str) -> None:
    def nao_pede(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError(f"pediu {pedido.url}")

    with pytest.raises(ValueError, match="escopo"):
        await _coletar(nao_pede, escopo=escopo)


async def test_detalhar_e_resolver() -> None:
    vaga = _vagas((await _coletar(_html("normal")))[0])[0]

    class SemRede:
        async def pedir(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("não pede")

    assert await iel.COLETOR.detalhar(vaga, SemRede()) is None  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await iel.COLETOR.resolver("PE", SemRede())  # type: ignore[arg-type]
