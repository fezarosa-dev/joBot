"""Assistente de primeira execução: IA, perfil, busca e segundo plano (desenho 13.6; plano T53).

Passo 1 grava o Meu país e a primeira busca (a busca é opcional) e passo 2 liga ou desliga o
segundo plano com `sistema.segundo_plano`. No fim grava `primeira_execucao_concluida` e
oferece "buscar agora" (o botão só aponta para `POST /buscar-agora`, que é da T49). Todo comando do
sistema passa pelo executor de `app.state.rodar_comando`, o ambiente de `app.state.ambiente` e a
plataforma de `app.state.plataforma`: o teste põe os falsos, o padrão é o sistema de verdade.

Escolhas do redator: sem nenhum critério o passo 1 não cria busca, e o painel mostra o
aviso de "diga o que você procura"; o país vem marcado pelo `Accept-Language` (ou pelo já gravado),
o `POST /pular` grava o marcado se ainda não há Meu país; o resumo vai na URL do passo 2
(`?busca=<id>`), para recarregar a página não criar outra busca. O "voltar" leva esse
`?busca=<id>` ao passo 1, que abre preenchido e edita a mesma busca (nome, `ativa`, regras e
`criada_em` ficam); formulário esvaziado de critérios com busca já gravada não mexe nela e segue
ao passo 2.

O passo opcional "Sites com login" (T241, ADR 0011) fica entre a busca e o segundo plano e só
existe com leitor registrado: sem leitor o assistente tem os dois passos de sempre. O
`/primeira-execucao/2` continua sendo o segundo plano, para não quebrar endereço guardado.

"Pular" (T263, desenho 5.4) existe em todo passo e vai para `POST /primeira-execucao/pular`: grava
os padrões (Meu país, segundo plano desligado, atalho do menu, primeira execução concluída) e manda
para `/vagas`, sem busca e com os sites com login desligados (D137.10). A rota fica antes de
`/{passo}`.

Os passos IA e Perfil (T439, desenho 10.4 da fase 4, D235) vêm antes da busca, opcionais. A IA
escolhe entre o modelo local, o serviço pago (a chave da Anthropic, guardada no cofre) e "Agora
não", com o custo à vista: escolher o pago já é a confirmação do custo do laço. O Perfil é o
questionário da aba Perfil (T437) e o currículo (T435, T436), gravados pelas funções de
`painel/rotas/perfil.py`; ele tem também "Pular este passo", que não grava nada. A busca chega
com o cargo atual e a cidade do perfil. O `?busca=<id>` anda pelos dois passos, como pelo dos sites.

Ligar recusado fica no passo 2 com o motivo em texto fixo (a saída do systemctl vai só para o
log, nunca para a tela). Desligar nunca prende (D49 b, T152): se desligar ou criar o atalho falha,
o passo 2 conclui mesmo assim e o fim mostra um aviso por código fixo em `?aviso=` (`_AVISOS`);
o detalhe da falha vai para o log.
"""

import json
import logging
import re
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from itertools import zip_longest
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData

from jobot.banco import buscas, perfil
from jobot.banco.cadastros import gravar_config, ler_config, ligar_fonte, meu_pais
from jobot.banco.ia import tarefa_ia
from jobot.nucleo.cambio import MOEDAS
from jobot.nucleo.modelo import Busca, Idioma, Local, Modalidade, Motivo, Nivel
from jobot.nucleo.tratamento.locais import codigos_de_pais, ler_locais
from jobot.painel import formatos
from jobot.painel.ambiente import (
    ambiente_do_painel,
    com_segundo_plano,
    leitores_do_painel,
    plataforma_do_painel,
    rodar_do_painel,
)
from jobot.painel.consultas import MAX_ID, inteiro_da_url, relogio_do_painel
from jobot.painel.i18n import pais_do_accept_language, t
from jobot.painel.moeda import INTEGER_MAX
from jobot.painel.rotas.configuracoes import (
    contexto_ferramenta_navegador,
    contexto_sites_com_login,
)
from jobot.painel.rotas.ia import IA, contexto_ia, gravar_ia
from jobot.painel.rotas.perfil import (
    SITUACOES,
    contexto_perguntas,
    curriculo_no_assistente,
    frase_de_privacidade,
    gravar_perfil,
    gravar_perguntas,
)
from jobot.painel.rotas.servicos import gravar_chave_ia
from jobot.painel.seguranca import Con, idioma_do_pedido, renderizar
from jobot.sistema import caso, segundo_plano
from jobot.sistema.segundo_plano_linux import Recusa

router = APIRouter(prefix="/primeira-execucao")

_PASSO_IA = "/primeira-execucao/ia"
_PASSO_PERFIL = "/primeira-execucao/perfil"
_PASSO_1 = "/primeira-execucao/1"
_PASSO_2 = "/primeira-execucao/2"
_SITES = "/primeira-execucao/sites"
_MAX_CARGOS = 20
_MAX_CIDADES = 10
_MAX_TEXTO = 100
_MAX_DIGITOS = 20  # o INTEGER do SQLite guarda até 19 dígitos em centavos
_MILHAR = re.compile(r"[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?")
_SIMPLES = re.compile(r"[0-9]+(?:[,.][0-9]{1,2})?")
_UFS_JSON = Path(__file__).parents[2] / "nucleo" / "dados" / "ufs.json"
_MODALIDADES = (Modalidade.PRESENCIAL, Modalidade.HIBRIDO, Modalidade.REMOTO)
_NIVEIS = tuple(n for n in Nivel if n is not Nivel.NAO_INFORMADO)
_IDIOMAS: dict[str, Idioma] = {"pt": "pt", "en": "en", "es": "es"}
_PRIMEIRO = "primeira_execucao."
# a escolha do passo IA -> o atalho da aba IA que ela grava; "nenhum" não grava nada
_ATALHO_DA_ESCOLHA = {"local": "offline", "pago": "claude"}
_ESCOLHA_DO_MODO = {"offline": "local", "claude": "pago"}
_ESCOLHAS_IA = (*_ATALHO_DA_ESCOLHA, "nenhum")
_CAMPO_CHAVE = "ia-chave"
_LOG = logging.getLogger(__name__)
# Código fixo do `?aviso=` do fim (nunca texto livre na URL) -> chave do motivo em texto simples.
_AVISOS = {
    "desligar": _PRIMEIRO + "p2.aviso.arquivos",
    "sem_host_exec": "segundo_plano.sem_host_exec",
    "systemd_nao_responde": "segundo_plano.systemd_nao_responde",
    "home_diferente": "segundo_plano.home_diferente",
    "systemctl_falhou": _PRIMEIRO + "p2.aviso.systemctl_falhou",
    "schtasks_falhou": _PRIMEIRO + "p2.aviso.schtasks_falhou",
    "launchctl_falhou": _PRIMEIRO + "p2.aviso.launchctl_falhou",
}


def numeros_dos_passos(com_sites: bool) -> dict[str, int]:
    """Id do passo na URL -> o número que a pessoa vê; o passo dos sites só existe com leitor."""
    passos = ("ia", "perfil", "1", *(("sites",) if com_sites else ()), "2")
    return {passo: n for n, passo in enumerate(passos, 1)}


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
    pais: str | None = None  # `None`: o formulário não mandou o campo


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
    if not 0 < centavos <= INTEGER_MAX:
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
        pais=um("meu_pais") if "meu_pais" in form else None,
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


def _entrada_do_perfil(con: Con) -> Entrada:
    """O passo 1 sem busca chega com o cargo atual e a cidade do perfil (desenho 10.4). A cidade
    que não se entende vai como foi escrita, sem UF."""
    dados = perfil.dados(con)
    cidades = []
    if dados.cidade_moradia:
        achado = next(iter(ler_locais([dados.cidade_moradia])), Local())
        cidade = achado.cidade or ("" if achado.uf else dados.cidade_moradia)
        cidades = [(cidade, achado.uf or "")]
    return Entrada(cargos=dados.cargo_atual or "", cidades=cidades)


def _gravada(con: Con, busca_id: int | None) -> Busca | None:
    return next((b for b in buscas.buscas(con) if b.id == busca_id), None) if busca_id else None


def _pagina(request: Request, passo: str, status: int = 200, **ctx: Any) -> Response:
    numeros = numeros_dos_passos(bool(leitores_do_painel(request)))
    contexto: dict[str, Any] = {
        "passo": passo,
        "n": numeros[passo],
        "total": len(numeros),
        "etapa": "passo",
        "entrada": Entrada(),
        "modalidades": [m.value for m in _MODALIDADES],
        "niveis": [n.value for n in _NIVEIS],
        "idiomas": list(_IDIOMAS),
        "moedas": ["BRL", *MOEDAS],
        "ufs": _ufs(),
        "erro": None,
        "motivo": None,
        "aviso_motivo": None,
        "resumo": None,
        "busca_id": None,
        "voltar_url": None,  # só o passo 1 não tem o que voltar
        "voltar_n": None,
        "voltar_busca": None,
        "suportado": True,
        "container": None,
    } | ctx
    resposta = renderizar(request, "primeira_execucao/pagina.html", **contexto)
    resposta.status_code = status
    return resposta


def _pais_pre_escolhido(request: Request, con: Con) -> str:
    """O Meu país já gravado; sem ele, o do `Accept-Language` (que o `POST /pular` também grava)."""
    gravado = ler_config(con, "meu_pais", None)
    if isinstance(gravado, str) and gravado in codigos_de_pais():
        return gravado
    return pais_do_accept_language(request.headers.get("accept-language"))


def _gravar_pais(request: Request, con: Con, pais: str) -> None:
    """Grava o Meu país; se mudou, recalcula o encaixe de todas as buscas antes de gravar."""
    if pais != meu_pais(con):
        agora = relogio_do_painel(request).agora()
        regras = bool(ler_config(con, "regras_ocultar_ligadas"))
        buscas.recalcular_encaixe(con, None, regras, hoje=_dia_local(agora), pais_padrao=pais)
    gravar_config(con, "meu_pais", pais)


def _pais_do_formulario(form: FormData) -> str | None:
    """O `meu_pais` do formulário, `None` se não veio; fora da lista é 422 e nada se grava."""
    pais = form.get("meu_pais")
    if pais is not None and (not isinstance(pais, str) or pais not in codigos_de_pais()):
        raise HTTPException(422)
    return pais


def _gravar_pais_se_falta(request: Request, con: Con, pais: str | None) -> None:
    """Pular: o Meu país escolhido, ou o do `Accept-Language`; o já gravado nunca é trocado."""
    if ler_config(con, "meu_pais", None) is None:
        pais = pais or pais_do_accept_language(request.headers.get("accept-language"))
        _gravar_pais(request, con, pais)


def _formulario_1(
    request: Request,
    con: Con,
    entrada: Entrada,
    status: int = 200,
    erro: str | None = None,
    busca_id: int | None = None,
) -> Response:
    linhas = [*entrada.cidades, *[("", "")] * 3][:3]
    entrada.cidades = linhas
    if entrada.pais is None:
        entrada.pais = _pais_pre_escolhido(request, con)
    paises = formatos.opcoes_de_pais(idioma_do_pedido(request))
    return _pagina(
        request,
        "1",
        status,
        entrada=entrada,
        erro=erro,
        busca_id=busca_id,
        paises=paises,
        voltar_n=numeros_dos_passos(bool(leitores_do_painel(request)))["perfil"],
        voltar_url=_PASSO_PERFIL,
        voltar_busca=busca_id,
    )


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
) -> Response:
    env = ambiente_do_painel(request)
    achada = _gravada(con, busca_id)
    com_sites = bool(leitores_do_painel(request))
    return _pagina(
        request,
        "2",
        status,
        voltar_n=numeros_dos_passos(com_sites)["2"] - 1,
        voltar_url=_SITES if com_sites else _PASSO_1,
        voltar_busca=achada.id if achada else None,
        motivo=motivo,
        erro=erro,
        resumo=_resumo(achada, idioma_do_pedido(request)),
        busca_id=busca_id,
        suportado=com_segundo_plano(request),
        container=caso.nome_do_container(env),
    )


async def _formulario_sites(request: Request, con: Con, busca_id: int | None) -> Response:
    # o mesmo fragmento da tela "Ferramentas" (D137.15); o do navegador vale sobre o dos sites
    contexto = await contexto_sites_com_login(request, con) | contexto_ferramenta_navegador(request)
    return _pagina(
        request,
        "sites",
        busca_id=busca_id,
        voltar_n=numeros_dos_passos(True)["1"],
        voltar_url=_PASSO_1,
        voltar_busca=busca_id,
        **contexto,
    )


async def _formulario_ia(
    request: Request,
    con: Con,
    busca_id: int | None,
    status: int = 200,
    *,
    escolha: str | None = None,
    erro: str | None = None,
    erro_campo: str | None = None,
) -> Response:
    """O passo IA: os atalhos da aba IA em três escolhas, com o custo do pago à vista."""
    ia = await contexto_ia(request, con)
    marcada = escolha or _ESCOLHA_DO_MODO.get(ia["ia_modo"], "nenhum")
    if marcada == "local" and ia["ia_local"] is None:  # o modelo sumiu: a opção vem desativada
        marcada = "nenhum"
    return _pagina(
        request,
        "ia",
        status,
        busca_id=busca_id,
        ia_escolha=marcada,
        ia_local=ia["ia_local"],
        ia_teto=ia["ia_teto"],
        ia_tem_chave="anthropic" in ia["ia_backends"],
        erro=erro,
        erro_campo=erro_campo,
    )


async def _formulario_perfil(
    request: Request, con: Con, busca_id: int | None, status: int = 200, **extra: Any
) -> Response:
    """O passo Perfil: o envio do currículo e o questionário da aba Perfil (T437)."""
    contexto = await contexto_perguntas(request, con)
    tarefa = tarefa_ia(con, "curriculo")
    proprio: dict[str, Any] = {
        "busca_id": busca_id,
        "voltar_n": numeros_dos_passos(bool(leitores_do_painel(request)))["ia"],
        "voltar_url": _PASSO_IA,
        "voltar_busca": busca_id,
        "curriculo_privacidade": frase_de_privacidade(
            tarefa, "configuracoes.ia.privacidade.curriculo."
        ),
        "curriculo_assistente": curriculo_no_assistente(busca_id),
        "curriculo_salvo": request.query_params.get("curriculo") == "1",
        "revisao": None,
        "situacoes": SITUACOES,
        "assistente": True,  # as perguntas que se respondem noutra seção ficam para a aba Perfil
    }
    # o questionário vale sobre o padrão de `_pagina` (`niveis` aqui é o do idioma, não o da
    # busca) e o `extra` (erro, digitado, revisão do currículo) vale sobre os dois
    return _pagina(request, "perfil", status, **(proprio | contexto | extra))


def _busca_da_url(con: Con, texto: object) -> int | None:
    """O `?busca=` só vale se for uma busca que existe (`registros/padroes.md`, modo edição)."""
    achada = _gravada(con, inteiro_da_url(texto if isinstance(texto, str) else None, MAX_ID))
    return achada.id if achada else None


def _com_busca(destino: str, busca_id: int | None) -> str:
    return destino + (f"?busca={busca_id}" if busca_id else "")


@router.get("/{passo}")
async def mostrar(request: Request, con: Con, passo: str) -> Response:
    if passo not in numeros_dos_passos(bool(leitores_do_painel(request))):
        raise HTTPException(404)
    params = request.query_params
    if passo == "ia":
        return await _formulario_ia(request, con, _busca_da_url(con, params.get("busca")))
    if passo == "perfil":
        return await _formulario_perfil(request, con, _busca_da_url(con, params.get("busca")))
    if passo == "sites":
        return await _formulario_sites(request, con, _busca_da_url(con, params.get("busca")))
    if passo == "1":
        voltando = _gravada(con, inteiro_da_url(params.get("busca"), MAX_ID))
        if voltando is None:
            return _formulario_1(request, con, _entrada_do_perfil(con))
        return _formulario_1(request, con, _entrada_de(voltando), busca_id=voltando.id)

    if params.get("feito") == "1" and ler_config(con, "primeira_execucao_concluida", False) is True:
        aviso = params.get("aviso", "")
        return _pagina(request, "2", etapa="pronto", aviso_motivo=_AVISOS.get(aviso))
    return _formulario_2(request, con, busca_id=inteiro_da_url(params.get("busca"), MAX_ID))


def _proximo_do_passo_1(request: Request) -> str:
    return _SITES if leitores_do_painel(request) else _PASSO_2


def _depois_do_passo_1(request: Request, existente: Busca | None) -> str:
    return _com_busca(_proximo_do_passo_1(request), existente.id if existente else None)


async def _gravar_passo_1(request: Request, con: Con) -> Response:
    form = await request.form()
    # o "voltar" do passo 2 edita a mesma busca
    pedido = inteiro_da_url(str(form.get("busca", "")), MAX_ID)
    existente = _gravada(con, pedido)
    pais = _pais_do_formulario(form)
    entrada = await _ler_entrada(request)
    idioma = idioma_do_pedido(request)
    if pedido is not None and existente is None:
        raise HTTPException(404)
    nome = existente.nome if existente else t(idioma, _PRIMEIRO + "nome_busca")
    try:
        busca = _montar(entrada, nome)
        if pais is not None:  # depois de validar o formulário, antes de a busca ser encaixada
            _gravar_pais(request, con, pais)
        if busca is None:
            return RedirectResponse(_depois_do_passo_1(request, existente), status_code=303)
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
        return _formulario_1(request, con, entrada, 422, _PRIMEIRO + invalido.chave, pedido)
    # shortcut: o país gravado fica se criar/editar_busca falhar aqui, trocar por transação única
    except ValueError:  # o banco recusou o valor (o salário não cabe)
        return _formulario_1(request, con, entrada, 422, _PRIMEIRO + "erro.salario", pedido)
    return RedirectResponse(_com_busca(_proximo_do_passo_1(request), busca_id), status_code=303)


def _dia_local(agora: datetime) -> date:
    return agora.astimezone().date()


async def _desligar_sem_prender(request: Request) -> str | None:
    """Desliga e cria o atalho; falha vira log e o código fixo do aviso (D49 b), nunca trava."""
    rodar, env = rodar_do_painel(request), ambiente_do_painel(request)
    plataforma = plataforma_do_painel(request)
    codigo = None
    # sempre: um ligar recusado no meio já deixou o arquivo do serviço, mesmo sem a config
    # DR-37: sem ligar o segundo plano, o atalho do menu é criado mesmo assim
    for passo in (segundo_plano.desligar, segundo_plano.criar_atalho):
        try:
            await run_in_threadpool(passo, rodar, env=env, plataforma=plataforma)
        except Recusa as recusa:
            _LOG.warning("segundo plano: não consegui desligar: %s", recusa.motivo.chave)
            sufixo = recusa.motivo.chave.removeprefix("segundo_plano.")
            codigo = codigo or (sufixo if sufixo in _AVISOS else "desligar")
        except ValueError, OSError:  # caractere de controle no caminho, disco, permissão
            _LOG.warning("segundo plano: não consegui desligar", exc_info=True)
            codigo = codigo or "desligar"
    return codigo


async def _gravar_passo_2(request: Request, con: Con) -> Response:
    form = await request.form()
    escolha = form.get("segundo_plano")
    busca_id = inteiro_da_url(str(form.get("busca", "")), MAX_ID)
    if escolha not in ("ligar", "desligar"):
        raise HTTPException(422)
    suportado = com_segundo_plano(request)
    ligar = escolha == "ligar" and suportado  # sem suporte o segundo plano é desativado
    aviso = None
    if ligar:
        try:
            await run_in_threadpool(
                segundo_plano.ligar,
                rodar_do_painel(request),
                env=ambiente_do_painel(request),
                plataforma=plataforma_do_painel(request),
            )
        except Recusa as recusa:
            return _formulario_2(request, con, busca_id=busca_id, motivo=recusa.motivo)
        except ValueError, OSError:  # o detalhe vai para o log, a tela leva texto fixo
            _LOG.warning("segundo plano: não consegui ligar", exc_info=True)
            return _formulario_2(
                request, con, busca_id=busca_id, erro=_PRIMEIRO + "p2.erro_arquivos"
            )
    elif suportado:
        aviso = await _desligar_sem_prender(request)
    gravar_config(con, "segundo_plano", ligar)
    gravar_config(con, "primeira_execucao_concluida", True)
    return RedirectResponse(
        "/primeira-execucao/2?feito=1" + (f"&aviso={aviso}" if aviso else ""), status_code=303
    )


async def _gravar_ia(request: Request, con: Con) -> Response:
    """Grava a escolha do passo IA pelos atalhos da aba IA. O pago guarda antes a chave digitada;
    a confirmação do custo do laço é a própria escolha, com o custo escrito ao lado (D235)."""
    form = await request.form()
    escolha = form.get("ia")
    busca_id = _busca_da_url(con, form.get("busca"))
    if not isinstance(escolha, str) or escolha not in _ESCOLHAS_IA:
        raise HTTPException(422)
    seguir = RedirectResponse(_com_busca(_PASSO_PERFIL, busca_id), status_code=303)
    if escolha == "nenhum":  # deixa a IA como está, ligada ou não
        return seguir
    chave = form.get("chave")
    if escolha == "pago" and isinstance(chave, str) and chave.strip():
        recusa = await gravar_chave_ia(
            request, con, FormData([("servico", "anthropic"), ("chave", chave)])
        )
        if recusa is not None:  # a chave nunca volta: o campo vem vazio
            status, contexto = recusa
            campo = _CAMPO_CHAVE if contexto["erro_ia"]["campo"] else None
            erro = contexto["erro_ia"]["erro"]
            return await _formulario_ia(
                request, con, busca_id, status, escolha=escolha, erro=erro, erro_campo=campo
            )
    atalho = FormData([("atalho", _ATALHO_DA_ESCOLHA[escolha]), ("confirmar", "1")])
    feito = await gravar_ia(request, con, atalho)
    if isinstance(feito, str) and feito.startswith(IA):
        return seguir
    # o atalho levaria a Ferramentas ou a Serviços: falta o modelo baixado ou a chave
    falta = "sem_chave" if escolha == "pago" else "sem_modelo"
    return await _formulario_ia(
        request,
        con,
        busca_id,
        422,
        escolha=escolha,
        erro=_PRIMEIRO + "ia.erro." + falta,
        erro_campo=_CAMPO_CHAVE if escolha == "pago" else None,
    )


async def _gravar_perfil(request: Request, con: Con) -> Response:
    """Grava o questionário (T437). Sem "sugerir", segue para a busca; com ele, volta ao passo
    com as perguntas novas, como o questionário volta a si mesmo."""
    form = await request.form()
    busca_id = _busca_da_url(con, form.get("busca"))
    feito = await gravar_perguntas(request, con, form)
    if isinstance(feito, tuple):
        status, extra = feito
        return await _formulario_perfil(request, con, busca_id, status, **extra)
    if "sugerir" not in form:
        return RedirectResponse(_com_busca(_PASSO_1, busca_id), status_code=303)
    volta = urlsplit(feito)  # o endereço do questionário: só a consulta e a âncora mudam de casa
    consulta = parse_qsl(volta.query) + ([("busca", str(busca_id))] if busca_id else [])
    destino = f"{_PASSO_PERFIL}?{urlencode(consulta)}#{volta.fragment}"
    return RedirectResponse(destino, status_code=303)


async def _gravar_sites(request: Request, con: Con) -> Response:
    """Continuar segue com o que a pessoa ligou; o Pular é o `POST /pular` (desliga os sites)."""
    form = await request.form()
    return RedirectResponse(_com_busca(_PASSO_2, _busca_da_url(con, form.get("busca"))), 303)


@router.post("/pular")
async def pular(request: Request, con: Con) -> Response:
    """Pular em qualquer passo: os padrões de quem não quer escolher agora, e Vagas (D143.18)."""
    pais = _pais_do_formulario(await request.form())
    _gravar_pais_se_falta(request, con, pais)
    if com_segundo_plano(request):  # o atalho sai como no "Não ligar agora"; falha só vai ao log
        await _desligar_sem_prender(request)
    # D137.10: Pular deixa os padrões, sem site com login
    for leitor in leitores_do_painel(request):
        with suppress(LookupError):
            ligar_fonte(con, leitor.chave, False)
    gravar_config(con, "segundo_plano", False)
    gravar_config(con, "primeira_execucao_concluida", True)
    return RedirectResponse("/vagas", status_code=303)


@router.post("/perfil/curriculo")
async def gravar_curriculo(request: Request, con: Con) -> Response:
    """A revisão do currículo aberta no passo Perfil: grava como a da aba e volta ao passo."""
    form = await request.form()
    if form.get("secao") != "curriculo":  # só a revisão: as outras seções são da aba
        raise HTTPException(422)
    busca_id = _busca_da_url(con, request.query_params.get("busca"))
    feito = await gravar_perfil(request, con, form)
    if isinstance(feito, tuple):
        status, extra = feito
        return await _formulario_perfil(request, con, busca_id, status, **extra)
    destino = _PASSO_PERFIL + "?curriculo=1" + (f"&busca={busca_id}" if busca_id else "")
    return RedirectResponse(destino, status_code=303)


@router.post("/{passo}")
async def gravar(request: Request, con: Con, passo: str) -> Response:
    if passo not in numeros_dos_passos(bool(leitores_do_painel(request))):
        raise HTTPException(404)
    if passo == "ia":
        return await _gravar_ia(request, con)
    if passo == "perfil":
        return await _gravar_perfil(request, con)
    if passo == "1":
        return await _gravar_passo_1(request, con)
    if passo == "sites":
        return await _gravar_sites(request, con)
    return await _gravar_passo_2(request, con)
