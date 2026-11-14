"""Empresas acompanhadas: lista, testar, adicionar, ligar, desligar e remover (plano T51).

O "testar" usa o coletor pelo núcleo: monta o `ContextoColeta` da empresa, pega os escopos de
`COLETOR.escopos(ctx)` e chama `coletar` na mesma instância, sem montar o escopo à mão (D50).
O identificador é o que o resolver do coletor devolve, com a caixa dele: a rota nunca a muda (D45).
O que o resolver devolve além do identificador (o `careerPageName` da Gupy, D53) vai para os
`parametros`, juntos aos já gravados (D37). Zero vagas no teste avisa que o identificador pode
estar errado (D52). Endereço que o resolver recusa é 422 com a mensagem e o texto de volta; fonte
que não é de empresa é 422 seco; fonte fora do ar é 502; empresa que não existe é 404.
A rede vem do `ClienteEducado`; `app.state.transporte` troca o transporte nos testes.
"""

import asyncio
import copy
import json
import logging
import sqlite3
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import cache
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from jobot import __version__
from jobot.banco.cadastros import adicionar_empresa, ativar_empresa, empresas, remover_empresa
from jobot.nucleo.coletores.base import Coletor, ContextoColeta
from jobot.nucleo.coletores.registro import descobrir
from jobot.nucleo.http import (
    Bloqueio,
    ClienteEducado,
    ErroDeRede,
    HttpDoEscopo,
    LimiteAtingido,
    OrcamentoGasto,
    Parou429,
    RespostaGrande,
    Validadores,
)
from jobot.nucleo.modelo import Empresa
from jobot.nucleo.relogio import Relogio, RelogioReal
from jobot.painel.seguranca import Con, renderizar

router = APIRouter(prefix="/empresas")
registro = logging.getLogger(__name__)

EmpresaId = Annotated[int, Path(ge=1, le=2**63 - 1)]  # o INTEGER do SQLite tem 64 bits com sinal
# Fontes que se acompanham por empresa. Escopo único (Remotive, WWR...) e busca por cargo
# (Himalayas) não têm identificador de empresa; fonte nova por empresa entra aqui.
ATS_POR_EMPRESA = ("greenhouse", "lever", "ashby", "smartrecruiters", "gupy")
# D37: o apêndice marca o quadro como banco de talentos; a tela reconhece pelo nome, sem campo novo.
ETIQUETA_BANCO_DE_TALENTOS = frozenset({"Agibank (quadro de vagas futuras)"})
PRAZO_S = 120.0  # por resolver e por escopo do teste
_MAX_NOME = 100
_MAX_ENDERECO = 500
# a exceção do HTTP educado (ou do prazo) vira a chave `saude.*` do motivo, como no executor
_MOTIVO_DA_EXCECAO: tuple[tuple[type[Exception], str], ...] = (
    (Bloqueio, "saude.bloqueio"),
    (LimiteAtingido, "saude.limite_atingido"),
    (OrcamentoGasto, "saude.orcamento"),
    (Parou429, "saude.parou_429"),
    (RespostaGrande, "saude.resposta_grande"),
    (ErroDeRede, "saude.erro_de_rede"),
    (TimeoutError, "saude.tempo_esgotado"),
)

_coletores = cache(descobrir)


@dataclass(frozen=True)
class Formulario:
    """O que a pessoa digitou ou escolheu: volta igual ao formulário num erro."""

    fonte: str = ""
    nome: str = ""
    endereco: str = ""


@dataclass(frozen=True)
class Teste:
    n: int
    motivo: tuple[str, str] | None  # (chave `saude.*`, parâmetro)
    zero: bool  # nenhuma vaga e a fonte não falhou: o identificador pode estar errado (D52)


class _Erro(Exception):
    """Erro que a tela mostra: chave de i18n, parâmetros e, se houver, o motivo `saude.*`."""

    def __init__(
        self,
        chave: str,
        status: int,
        motivo: tuple[str, str] | None = None,
        **params: str,
    ) -> None:
        super().__init__(chave)
        self.chave = chave
        self.status = status
        self.motivo = motivo
        self.params = params


class _SemValidadores:
    """Teste e cadastro não usam pedido condicional: não há validador guardado."""

    def ler(self, url: str) -> Validadores | None:
        return None


def _relogio(request: Request) -> Relogio:
    relogio: Relogio = getattr(request.app.state, "relogio", None) or RelogioReal()
    return relogio


@asynccontextmanager
async def _cliente(request: Request) -> AsyncIterator[ClienteEducado]:
    cliente = ClienteEducado(
        getattr(request.app.state, "transporte", None),
        _relogio(request),
        _SemValidadores(),
        __version__,
    )
    try:
        yield cliente
    finally:
        await cliente.fechar()


def _escopo_http(cliente: ClienteEducado, coletor: Coletor) -> HttpDoEscopo:
    return cliente.escopo(
        espera_s=coletor.espera_s, condicional=False, max_pedidos=coletor.max_pedidos
    )


def _motivo(erro: Exception) -> tuple[str, str]:
    for tipo, chave in _MOTIVO_DA_EXCECAO:
        if isinstance(erro, tipo):
            return chave, ""
    return "saude.excecao", type(erro).__name__


def _partir_motivo(motivo: str) -> tuple[str, str]:
    chave, _, parametro = motivo.partition(":")  # `chave:valor` (regra do executor)
    return chave, parametro


def _texto(valor: str) -> str:
    return "".join(c for c in valor if c.isprintable()).strip()


async def _ler(request: Request) -> Formulario:
    form = await request.form()

    def um(campo: str) -> str:
        valor = form.get(campo)
        return _texto(valor) if isinstance(valor, str) else ""

    return Formulario(fonte=um("fonte"), nome=um("nome"), endereco=um("endereco"))


def _fontes() -> list[tuple[str, str]]:
    todos = _coletores()
    return [(c, todos[c].nome) for c in ATS_POR_EMPRESA if c in todos]


def _coletor(f: Formulario) -> Coletor:
    if f.fonte not in ATS_POR_EMPRESA or f.fonte not in _coletores():
        raise HTTPException(422)  # a tela só oferece as fontes por empresa
    return _coletores()[f.fonte]


def _conferir(coletor: Coletor, f: Formulario) -> None:
    if not f.endereco or len(f.endereco) > _MAX_ENDERECO:
        raise _Erro("empresas.erro.endereco", 422, fonte=coletor.nome)
    if len(f.nome) > _MAX_NOME:
        raise _Erro("empresas.erro.nome", 422)


async def _resolver(request: Request, coletor: Coletor, f: Formulario) -> Mapping[str, str]:
    """O que o resolver do coletor devolve; sem `identificador` é como se ele tivesse recusado."""
    try:
        async with _cliente(request) as cliente, asyncio.timeout(PRAZO_S):
            resolvido = await coletor.resolver(f.endereco, _escopo_http(cliente, coletor))
    except ValueError as erro:
        raise _Erro("empresas.erro.endereco", 422, fonte=coletor.nome) from erro
    except Exception as erro:
        registro.warning("resolver de %s falhou: %r", coletor.chave, erro)
        raise _Erro("empresas.erro.fonte_fora", 502, _motivo(erro)) from erro
    if not resolvido.get("identificador"):
        raise _Erro("empresas.erro.endereco", 422, fonte=coletor.nome)
    return resolvido


def _empresa(coletor: Coletor, f: Formulario, resolvido: Mapping[str, str]) -> Empresa:
    identificador = resolvido["identificador"]  # com a caixa do resolver (D45)
    return Empresa(
        nome=f.nome or resolvido.get("careerPageName") or identificador,
        fonte=coletor.chave,
        identificador=identificador,
        parametros={k: v for k, v in resolvido.items() if k != "identificador"},
        origem="pessoa",
    )


async def _testar(request: Request, coletor: Coletor, empresa: Empresa) -> Teste:
    # Cópia rasa: `escopos` guarda estado no coletor (Lever, Ashby) e o compartilhado é o da busca
    # real, no mesmo laço de eventos. Escopos e `coletar` seguem na mesma instância (D50).
    coletor = copy.copy(coletor)
    ctx = ContextoColeta(empresas=[empresa], termos=(), paises=())
    n = 0
    motivo: tuple[str, str] | None = None
    falhou = False
    async with _cliente(request) as cliente:
        for escopo in coletor.escopos(ctx):  # D50: os escopos são do coletor, na mesma instância
            try:
                async with asyncio.timeout(PRAZO_S):
                    resultado = await coletor.coletar(escopo, _escopo_http(cliente, coletor))
            except Exception as erro:
                registro.warning("teste de %s falhou: %r", coletor.chave, erro)
                falhou, motivo = True, motivo or _motivo(erro)
                continue
            n += len(resultado.vagas)
            falhou |= resultado.estado == "falhou"
            if resultado.motivo and motivo is None:
                motivo = _partir_motivo(resultado.motivo)
    return Teste(n=n, motivo=motivo, zero=n == 0 and not falhou)


def _gravado(con: sqlite3.Connection, fonte: str, identificador: str) -> tuple[str, dict[str, str]]:
    """Nome e `parametros` da linha, removida ou não, ou `("", {})`: o `adicionar_empresa` os
    sobrescreve, e o que a pessoa não digitou não pode se perder (D37)."""
    linha = con.execute(
        "SELECT nome, parametros FROM empresa WHERE fonte = ? AND identificador = ?",
        (fonte, identificador),
    ).fetchone()
    return ("", {}) if linha is None else (linha[0], dict(json.loads(linha[1])))


def _pagina(
    request: Request,
    con: sqlite3.Connection,
    f: Formulario,
    *,
    erro: _Erro | None = None,
    teste: Teste | None = None,
) -> HTMLResponse:
    todos = _coletores()
    linhas = [
        {
            "e": e,
            "fonte_nome": todos[e.fonte].nome if e.fonte in todos else e.fonte,
            "talentos": e.nome in ETIQUETA_BANCO_DE_TALENTOS,
        }
        for e in empresas(con)
    ]
    resposta = renderizar(
        request, "empresas/lista.html", linhas=linhas, fontes=_fontes(), f=f, erro=erro, teste=teste
    )
    resposta.status_code = erro.status if erro else 200
    return resposta


@router.get("")
async def lista(request: Request, con: Con) -> HTMLResponse:
    return _pagina(request, con, Formulario())


@router.post("/testar")
async def testar(request: Request, con: Con) -> HTMLResponse:
    f = await _ler(request)
    coletor = _coletor(f)
    try:
        _conferir(coletor, f)
        empresa = _empresa(coletor, f, await _resolver(request, coletor, f))
        return _pagina(request, con, f, teste=await _testar(request, coletor, empresa))
    except _Erro as erro:
        return _pagina(request, con, f, erro=erro)


@router.post("")
async def adicionar(request: Request, con: Con) -> Response:
    f = await _ler(request)
    coletor = _coletor(f)
    try:
        _conferir(coletor, f)
        empresa = _empresa(coletor, f, await _resolver(request, coletor, f))
        nome, parametros = _gravado(con, empresa.fonte, empresa.identificador)
        try:
            adicionar_empresa(
                con,
                Empresa(
                    **{
                        **vars(empresa),
                        "nome": f.nome or nome or empresa.nome,  # nome gravado vale sem o digitado
                        "parametros": parametros | dict(empresa.parametros),
                    }
                ),
            )
        except ValueError as erro:
            raise _Erro("empresas.erro.valor", 422) from erro
    except _Erro as erro:
        return _pagina(request, con, f, erro=erro)
    return RedirectResponse("/empresas", status_code=303)


def _achar(con: sqlite3.Connection, empresa_id: int) -> Empresa:
    """A empresa da tela (removida não conta): 404 se não existe."""
    achada = next((e for e in empresas(con) if e.id == empresa_id), None)
    if achada is None:
        raise HTTPException(404)
    return achada


def _ligar(con: sqlite3.Connection, empresa_id: int, ativa: bool) -> Response:
    _achar(con, empresa_id)
    try:
        ativar_empresa(con, empresa_id, ativa)
    except LookupError as erro:
        raise HTTPException(404) from erro
    return RedirectResponse("/empresas", status_code=303)


@router.post("/{empresa_id}/ligar")
async def ligar(con: Con, empresa_id: EmpresaId) -> Response:
    return _ligar(con, empresa_id, True)


@router.post("/{empresa_id}/desligar")
async def desligar(con: Con, empresa_id: EmpresaId) -> Response:
    return _ligar(con, empresa_id, False)


@router.post("/{empresa_id}/remover")
async def remover(request: Request, con: Con, empresa_id: EmpresaId) -> Response:
    _achar(con, empresa_id)
    try:
        remover_empresa(con, empresa_id, _relogio(request).agora())
    except LookupError as erro:
        raise HTTPException(404) from erro
    return RedirectResponse("/empresas", status_code=303)
