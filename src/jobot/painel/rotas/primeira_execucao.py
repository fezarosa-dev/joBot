"""Assistente de primeira execução: busca e segundo plano (desenho 13.6; plano T53).

Passo 1 grava a primeira busca (tudo opcional) e passo 2 liga ou desliga o segundo plano com
`sistema.segundo_plano_linux`. No fim grava `primeira_execucao_concluida` e oferece "buscar
agora" (o botão só aponta para `POST /buscar-agora`, que é da T49). Todo comando do sistema passa
pelo executor de `app.state.rodar_comando`, o ambiente de `app.state.ambiente` e a plataforma de
`app.state.plataforma`: o teste põe os falsos, o padrão é o sistema de verdade.

Escolhas do redator: sem nenhum critério (ou "pular") o passo 1 não cria busca, e o painel mostra o
aviso de "diga o que você procura"; o resumo vai na URL do passo 2 (`?busca=<id>`), para recarregar
a página não criar outra busca. O "voltar" leva esse `?busca=<id>` ao passo 1, que abre preenchido
e edita a mesma busca (nome, `ativa`, regras e `criada_em` ficam); formulário esvaziado de
critérios com busca já gravada não mexe nela e segue ao passo 2.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from itertools import zip_longest
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from jobot.banco import buscas
from jobot.banco.cadastros import gravar_config, ler_config
from jobot.nucleo.cambio import MOEDAS
from jobot.nucleo.modelo import Busca, Idioma, Local, Modalidade, Motivo, Nivel
from jobot.painel import formatos
from jobot.painel.ambiente import ambiente_do_painel, no_linux, rodar_do_painel
from jobot.painel.i18n import t
from jobot.painel.rotas.vagas import relogio_do_painel
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar
from jobot.sistema import caso, segundo_plano_linux
from jobot.sistema.segundo_plano_linux import Recusa

router = APIRouter(prefix="/primeira-execucao")

PASSOS = {"1": 1, "2": 2}
_MAX_CARGOS = 20
_MAX_CIDADES = 10
_MAX_TEXTO = 100
_MAX_DIGITOS = 20  # o INTEGER do SQLite guarda até 19 dígitos em centavos
_MAX_CENTAVOS = 2**63 - 1
_MILHAR = re.compile(r"[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?")
_SIMPLES = re.compile(r"[0-9]+(?:[,.][0-9]{1,2})?")
_UFS_JSON = Path(__file__).parents[2] / "nucleo" / "dados" / "ufs.json"
_MODALIDADES = (Modalidade.PRESENCIAL, Modalidade.HIBRIDO, Modalidade.REMOTO)
_NIVEIS = tuple(n for n in Nivel if n is not Nivel.NAO_INFORMADO)
_IDIOMAS: dict[str, Idioma] = {"pt": "pt", "en": "en", "es": "es"}
_PRIMEIRO = "primeira_execucao."


@cache
def _ufs() -> tuple[str, ...]:
    dados: list[dict[str, str]] = json.loads(_UFS_JSON.read_text(encoding="utf-8"))
    return tuple(u["sigla"] for u in dados)


class _Invalido(Exception):
    def __init__(self, chave: str) -> None:
        super().__init__(chave)
        self.chave = chave


@dataclass
class Entrada:
    """O que veio do formulário do passo 1, para voltar preenchido quando algo é recusado."""

    cargos: str = ""
    cidades: list[tuple[str, str]] = field(default_factory=list)
    modalidades: set[str] = field(default_factory=set)
    niveis: set[str] = field(default_factory=set)
    salario: str = ""
    moeda: str = "BRL"
    idiomas: set[str] = field(default_factory=set)


def _texto(valor: str) -> str:
    return "".join(c for c in valor if c.isprintable()).strip()[:_MAX_TEXTO]


def _cargos(texto: str) -> tuple[str, ...]:
    vistos: dict[str, str] = {}
    for parte in re.split(r"[\n\r,;]+", texto):
        cargo = _texto(parte)
        if cargo:
            vistos.setdefault(cargo.casefold(), cargo)
    return tuple(vistos.values())[:_MAX_CARGOS]


def _local(cidade: str, uf: str) -> Local | None:
    cidade, uf = _texto(cidade), uf.strip().upper()
    if uf and uf not in _ufs():
        raise _Invalido("erro.uf")
    if not cidade and not uf:
        return None
    return Local(cidade=cidade or None, uf=uf or None, pais="BR" if uf else None)


def _centavos(digitado: str) -> int | None:
    """Salário em centavos; vazio é `None`. Decimal, nunca float: `5.000,50` e `5000.5` valem."""
    texto = "".join(digitado.split())
    if not texto:
        return None
    if _MILHAR.fullmatch(texto):
        texto = texto.replace(".", "")
    elif not _SIMPLES.fullmatch(texto):
        raise _Invalido("erro.salario")
    if len(texto) > _MAX_DIGITOS:
        raise _Invalido("erro.salario")
    centavos = int(Decimal(texto.replace(",", ".")).scaleb(2))
    if not 0 < centavos <= _MAX_CENTAVOS:
        raise _Invalido("erro.salario")
    return centavos


def _escolhidos[E](opcoes: Sequence[E], marcados: set[str]) -> tuple[E, ...]:
    return tuple(o for o in opcoes if str(o) in marcados)


async def _ler_entrada(request: Request) -> Entrada:
    form = await request.form()

    def textos(nome: str) -> list[str]:
        return [v for v in form.getlist(nome) if isinstance(v, str)]

    def um(nome: str, padrao: str = "") -> str:
        valores = textos(nome)
        return valores[0] if valores else padrao

    return Entrada(
        cargos=um("cargos"),
        cidades=list(
            zip_longest(textos("cidade")[:_MAX_CIDADES], textos("uf")[:_MAX_CIDADES], fillvalue="")
        ),
        modalidades=set(textos("modalidades")),
        niveis=set(textos("niveis")),
        salario=um("salario_min"),
        moeda=um("moeda", "BRL"),
        idiomas=set(textos("idiomas")),
    )


def _montar(entrada: Entrada, nome: str) -> Busca | None:
    """A busca do formulário; `None` quando não há nenhum critério. `_Invalido` se algo não vale."""
    locais = tuple(filter(None, (_local(c, u) for c, u in entrada.cidades)))
    centavos = _centavos(entrada.salario)
    moeda = entrada.moeda.strip().upper()
    if centavos is not None and moeda != "BRL" and moeda not in MOEDAS:
        raise _Invalido("erro.moeda")
    busca = Busca(
        nome=nome,
        cargos=_cargos(entrada.cargos),
        cidades=locais,
        modalidades=_escolhidos(_MODALIDADES, entrada.modalidades),
        niveis=_escolhidos(_NIVEIS, entrada.niveis),
        salario_min_centavos=centavos,
        salario_moeda=moeda if centavos is not None else None,
        idiomas=tuple(i for chave, i in _IDIOMAS.items() if chave in entrada.idiomas),
    )
    tem_criterio = (
        busca.cargos or busca.cidades or busca.modalidades or busca.niveis or busca.idiomas
    ) or busca.salario_min_centavos
    return busca if tem_criterio else None


def _entrada_de(busca: Busca) -> Entrada:
    """O formulário do passo 1 preenchido com a busca já gravada (o inverso de `_montar`)."""
    reais, centavos = divmod(busca.salario_min_centavos or 0, 100)
    salario = "" if busca.salario_min_centavos is None else f"{reais},{centavos:02d}"
    return Entrada(
        cargos="\n".join(busca.cargos),
        cidades=[(c.cidade or "", c.uf or "") for c in busca.cidades],
        modalidades={str(m) for m in busca.modalidades},
        niveis={str(n) for n in busca.niveis},
        salario=salario,
        moeda=busca.salario_moeda or "BRL",
        idiomas=set(busca.idiomas),
    )


def _gravada(con: Con, busca_id: int | None) -> Busca | None:
    return next((b for b in buscas.buscas(con) if b.id == busca_id), None) if busca_id else None


def _id_valido(texto: str | None) -> int | None:
    if texto is None or not texto.isascii() or not texto.isdigit():
        return None
    numero = int(texto) if len(texto) <= 19 else 0
    return numero if 1 <= numero <= _MAX_CENTAVOS else None


def _pagina(request: Request, passo: int, status: int = 200, **ctx: Any) -> Response:
    contexto: dict[str, Any] = {
        "passo": passo,
        "etapa": "passo",
        "entrada": Entrada(),
        "modalidades": [m.value for m in _MODALIDADES],
        "niveis": [n.value for n in _NIVEIS],
        "idiomas": list(_IDIOMAS),
        "moedas": ["BRL", *MOEDAS],
        "ufs": _ufs(),
        "erro": None,
        "motivo": None,
        "desligando": False,
        "resumo": None,
        "busca_id": None,
        "linux": True,
        "container": None,
    } | ctx
    resposta = renderizar(request, "primeira_execucao/pagina.html", **contexto)
    resposta.status_code = status
    return resposta


def _formulario_1(
    request: Request,
    entrada: Entrada,
    status: int = 200,
    erro: str | None = None,
    busca_id: int | None = None,
) -> Response:
    linhas = [*entrada.cidades, *[("", "")] * 3][:3]
    entrada.cidades = linhas
    return _pagina(request, 1, status, entrada=entrada, erro=erro, busca_id=busca_id)


def _resumo(busca: Busca | None, idioma: str) -> dict[str, Any] | None:
    if busca is None:
        return None
    salario = None
    if busca.salario_min_centavos is not None:
        valor = formatos.dinheiro(busca.salario_min_centavos, busca.salario_moeda or "BRL", idioma)
        salario = t(idioma, _PRIMEIRO + "resumo.salario_mes", valor=valor)
    return {
        "busca": busca,
        "cidades": formatos.locais_texto(busca.cidades),
        "salario": salario,
    }


def _formulario_2(
    request: Request,
    con: Con,
    *,
    busca_id: int | None = None,
    status: int = 200,
    motivo: Motivo | None = None,
    erro: str | None = None,
    desligando: bool = False,
) -> Response:
    env = ambiente_do_painel(request)
    achada = _gravada(con, busca_id)
    return _pagina(
        request,
        2,
        status,
        motivo=motivo,
        desligando=desligando,
        erro=erro,
        resumo=_resumo(achada, idioma_do_pedido(request)),
        busca_id=busca_id,
        linux=no_linux(request),
        container=caso.nome_do_container(env),
    )


@router.get("/{passo}")
async def mostrar(request: Request, con: Con, passo: str) -> Response:
    numero = PASSOS.get(passo)
    if numero is None:
        raise HTTPException(404)
    params = request.query_params
    if numero == 1:
        voltando = _gravada(con, _id_valido(params.get("busca")))
        if voltando is None:
            return _formulario_1(request, Entrada())
        return _formulario_1(request, _entrada_de(voltando), busca_id=voltando.id)

    if params.get("feito") == "1" and ler_config(con, "primeira_execucao_concluida", False) is True:
        return _pagina(request, 2, etapa="pronto")
    return _formulario_2(request, con, busca_id=_id_valido(params.get("busca")))


async def _gravar_passo_1(request: Request, con: Con) -> Response:
    form = await request.form()
    pedido = _id_valido(str(form.get("busca", "")))  # o "voltar" do passo 2 edita a mesma busca
    existente = _gravada(con, pedido)
    if "pular" in form:
        return RedirectResponse(
            "/primeira-execucao/2" + (f"?busca={pedido}" if existente else ""), status_code=303
        )
    entrada = await _ler_entrada(request)
    idioma = idioma_do_pedido(request)
    if pedido is not None and existente is None:
        raise HTTPException(404)
    nome = existente.nome if existente else t(idioma, _PRIMEIRO + "nome_busca")
    try:
        busca = _montar(entrada, nome)
        if busca is None:
            destino = "/primeira-execucao/2" + (f"?busca={pedido}" if existente else "")
            return RedirectResponse(destino, status_code=303)
        agora = relogio_do_painel(request).agora()
        regras = bool(ler_config(con, "regras_ocultar_ligadas"))
        if existente is None:
            busca_id = buscas.criar_busca(
                con, busca, agora, regras_ligadas=regras, hoje=_dia_local(agora)
            )
        else:
            busca_id = existente.id or 0
            editada = replace(
                busca,
                id=existente.id,
                ativa=existente.ativa,
                regras_ocultar=existente.regras_ocultar,
                criada_em=existente.criada_em,
            )
            try:
                buscas.editar_busca(con, editada, regras_ligadas=regras, hoje=_dia_local(agora))
            except LookupError:  # apagada entre a leitura e a gravação
                raise HTTPException(404) from None
    except _Invalido as invalido:
        return _formulario_1(request, entrada, 422, _PRIMEIRO + invalido.chave, pedido)
    except ValueError:  # o banco recusou o valor (o salário não cabe)
        return _formulario_1(request, entrada, 422, _PRIMEIRO + "erro.salario", pedido)
    return RedirectResponse(f"/primeira-execucao/2?busca={busca_id}", status_code=303)


def _dia_local(agora: datetime) -> date:
    return agora.astimezone().date()


async def _gravar_passo_2(request: Request, con: Con) -> Response:
    form = await request.form()
    escolha = form.get("segundo_plano")
    busca_id = _id_valido(str(form.get("busca", "")))
    if escolha not in ("ligar", "desligar"):
        raise HTTPException(422)
    rodar, env = rodar_do_painel(request), ambiente_do_painel(request)
    ligar = escolha == "ligar" and no_linux(request)  # fora do Linux o segundo plano é desativado
    try:
        if ligar:
            await run_in_threadpool(segundo_plano_linux.ligar, rodar, env=env)
        elif no_linux(request):
            # sempre: um ligar recusado no meio já deixou o arquivo do serviço, mesmo sem a config
            await run_in_threadpool(segundo_plano_linux.desligar, rodar, env=env)
            # DR-37: sem ligar o segundo plano, o atalho do menu é criado mesmo assim
            await run_in_threadpool(segundo_plano_linux.criar_atalho, rodar, env=env)
    except Recusa as recusa:
        return _formulario_2(
            request, con, busca_id=busca_id, motivo=recusa.motivo, desligando=not ligar
        )
    except (ValueError, OSError) as falha:  # caractere de controle no caminho, disco, permissão
        return _formulario_2(request, con, busca_id=busca_id, erro=str(falha))
    gravar_config(con, "segundo_plano", ligar)
    gravar_config(con, "primeira_execucao_concluida", True)
    return RedirectResponse("/primeira-execucao/2?feito=1", status_code=303)


@router.post("/{passo}")
async def gravar(request: Request, con: Con, passo: str) -> Response:
    numero = PASSOS.get(passo)
    if numero is None:
        raise HTTPException(404)
    if numero == 1:
        return await _gravar_passo_1(request, con)
    return await _gravar_passo_2(request, con)
